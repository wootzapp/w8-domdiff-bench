from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_evidence import parse_dom_diff_text
from webeval.rubric_agent.dom_diff_text_summary_agent import (
    DOMDiffTextSummaryMMRubricAgent,
)
from webeval.rubric_agent.dom_diff_text_summary_projection import (
    DocumentStateOccurrence,
    project_text_summary_frame,
    project_text_summary_frames,
)
from webeval.rubric_agent.dom_diff_text_summary_rendering import (
    render_batched_text_summary_relevance_evidence,
    render_compact_text_summary_frame,
    render_packed_text_summary_analysis_evidence,
)


FIXTURES = Path(__file__).parent / "fixtures" / "dom_diff_text"


def _project(name: str):
    parsed = parse_dom_diff_text(
        FIXTURES / name / "dom_diff1.txt",
        task_id="fixture-task",
        action_ordinal=1,
    )
    return project_text_summary_frame(parsed, max_record_chars=600)


def test_document_replacement_projection_is_dense_and_directional():
    frame = _project("document_replaced")
    rendered = render_compact_text_summary_frame(
        frame, frame_index=0, token_budget=1500
    ).text
    assert "FRAME 0 | STEP 1 action=navigate status=document_replaced" in rendered
    assert '+FRAME 0/STEP 1 url="https://example.test/result"' in rendered
    assert '-FRAME 0/STEP 1 url="https://example.test/start"' in rendered
    assert 'TEXT ["Published by Microsoft Studios"]' in rendered
    assert 'TEXT ["Release date 7/6/2022"]' in rendered
    assert 'TEXT ["Old result"]' in rendered
    assert "PAGE url=" in rendered
    assert frame.document_page_states[0].blocks[0].provenance[0].source_spans
    assert "[s1r" not in rendered
    assert "C[" not in rendered


def test_viewport_and_element_semantics_remain_distinct():
    changed = _project("changes_present")
    rendered = render_compact_text_summary_frame(
        changed, frame_index=0, token_budget=1500
    ).text
    assert '+VIEW "Release date: 7/6/2022"' in rendered
    assert '-VIEW "Earlier release"' in rendered
    assert "+ELEMENT" in rendered
    assert "-ELEMENT" in rendered
    assert "~ELEMENT" in rendered
    assert "coverage=live_control_state_not_covered" in rendered

    viewport = _project("viewport_content_changed")
    viewport_text = render_compact_text_summary_frame(
        viewport, frame_index=0, token_budget=1500
    ).text
    assert "action=scroll status=viewport_content_changed" in viewport_text
    assert '+VIEW "Published by"' in viewport_text
    assert '-VIEW "Overview"' in viewport_text
    assert "+DOC" not in viewport_text


def test_whole_record_packing_omits_without_partial_token_clipping():
    frame = _project("changes_present")
    rendered = render_compact_text_summary_frame(frame, frame_index=0, token_budget=180)
    assert rendered.estimated_tokens <= 180
    assert rendered.records_omitted_by_budget > 0
    assert "budget=" in rendered.text
    for line in rendered.text.splitlines():
        if line.startswith(
            ("+DOC", "-DOC", "+VIEW", "-VIEW", "+ELEMENT", "-ELEMENT", "~ELEMENT")
        ):
            assert not line.endswith("…")


def test_relevance_packing_has_all_frames_and_no_retrieval_contract():
    frames = [_project("document_replaced"), _project("viewport_content_changed")]
    packed = render_batched_text_summary_relevance_evidence(
        frames,
        token_budget=4000,
    )
    assert packed.frame_indices == (0, 1)
    assert packed.starting_per_frame_allowance_tokens == 2000
    assert packed.per_frame_allowance_tokens == 2000
    assert "FRAME 0 | STEP 1" in packed.text
    assert "FRAME 1 | STEP 1" in packed.text
    assert "C[" not in packed.text
    assert "chunk" not in packed.text.casefold()
    assert packed.estimated_tokens <= 4000


def test_projection_factors_inverse_document_replacements_with_provenance():
    source = parse_dom_diff_text(
        FIXTURES / "document_replaced" / "dom_diff1.txt",
        task_id="fixture-task",
        action_ordinal=1,
    )
    reversed_records = []
    for record in source.records:
        operation = {
            "added": "removed",
            "removed": "added",
        }.get(record.operation, record.operation)
        spans = tuple(
            replace(span, action_ordinal=2)
            for span in record.source_spans
        )
        reversed_records.append(
            replace(record, operation=operation, source_spans=spans)
        )
    second = replace(
        source,
        action_ordinal=2,
        action_id="2",
        before_url=source.after_url,
        after_url=source.before_url,
        before_identity=source.after_identity,
        after_identity=source.before_identity,
        records=tuple(reversed_records),
        audit=replace(source.audit, action_ordinal=2),
    )

    compact = [
        frame.compact for frame in project_text_summary_frames([source, second])
    ]
    states = {
        state.state_sha256: state
        for frame in compact
        for state in frame.document_page_states
    }
    matching = [
        state
        for state in states.values()
        if any("Release date 7/6/2022" in block.values for block in state.blocks)
    ]
    assert len(matching) == 1
    state = matching[0]
    assert [item.direction for item in state.occurrences] == ["added", "removed"]
    assert [item.frame_index for item in state.occurrences] == [0, 1]
    provenance_steps = {
        span.action_ordinal
        for block in state.blocks
        for item in block.provenance
        for span in item.source_spans
    }
    assert provenance_steps == {1, 2}


def test_document_page_state_is_rendered_once_and_reowned_for_selected_union():
    original = _project("document_replaced")
    state = next(
        state
        for state in original.document_page_states
        if any("Release date 7/6/2022" in block.values for block in state.blocks)
    )
    shared = replace(
        state,
        occurrences=(
            DocumentStateOccurrence(
                frame_index=0,
                action_ordinal=1,
                direction="added",
                url="https://example.test/result",
            ),
            DocumentStateOccurrence(
                frame_index=1,
                action_ordinal=2,
                direction="removed",
                url="https://example.test/result",
            ),
        ),
    )
    first = replace(original, document_page_states=(shared,))
    second = replace(
        original,
        action_ordinal=2,
        before_url="https://example.test/result",
        after_url="https://example.test/end",
        page={
            "url_before": "https://example.test/result",
            "url_after": "https://example.test/end",
            "document_replaced": True,
        },
        document_page_states=(shared,),
    )

    relevance = render_batched_text_summary_relevance_evidence(
        [first, second], token_budget=4000
    )
    assert relevance.text.count('TEXT ["Release date 7/6/2022"]') == 1
    assert '+FRAME 0/STEP 1 url="https://example.test/result"' in relevance.text
    assert '-FRAME 1/STEP 2 url="https://example.test/result"' in relevance.text

    analysis = render_packed_text_summary_analysis_evidence(
        [first, second], {0: [1]}, token_budget=4000
    )
    assert analysis.frame_indices == (1,)
    assert analysis.text.count('TEXT ["Release date 7/6/2022"]') == 1
    assert '-FRAME 1/STEP 2 url="https://example.test/result"' in analysis.text
    assert "+FRAME 0/STEP 1" not in analysis.text


def test_analysis_renders_unique_frame_union_and_summary_assignments():
    frames = [_project("document_replaced"), _project("viewport_content_changed")]
    grouped = {0: [0, 1], 1: [1]}
    packed = render_packed_text_summary_analysis_evidence(
        frames,
        grouped,
        token_budget=5000,
    )
    assert packed.frame_indices == (0, 1)
    assert packed.starting_per_frame_allowance_tokens == 2500
    assert packed.per_frame_allowance_tokens == 2500
    assert packed.text.count("FRAME 0 |") == 1
    assert packed.text.count("FRAME 1 |") == 1
    assert "CRITERION EVIDENCE ASSIGNMENTS" in packed.text
    assert "criterion_0: frame_indices=[0, 1]" in packed.text
    assert "criterion_1: frame_indices=[1]" in packed.text
    assert "C[" not in packed.text


def test_new_agent_does_not_import_legacy_text_pipeline_modules():
    source = inspect.getsource(inspect.getmodule(DOMDiffTextSummaryMMRubricAgent))
    forbidden = (
        "dom_diff_text_compaction",
        "dom_diff_text_retrieval",
        "dom_diff_text_s3_capping",
        "dom_diff_text_agent",
        "dom_diff_text_prompts",
    )
    for module in forbidden:
        assert module not in source


def test_stage_evidence_budget_math_reserves_static_prompt_and_64_tokens():
    estimator = TokenEstimator("gpt-5.2")
    static_prompt = "fixed rubric and task context"
    relevance_budget = 16000 - estimator.count(static_prompt) - 64
    analysis_budget = 24000 - estimator.count(static_prompt) - 64
    assert relevance_budget < 16000
    assert analysis_budget < 24000
    assert analysis_budget - relevance_budget == 8000


def test_s3_batched_packing_does_not_apply_1500_frame_ceiling():
    frames = [
        _project("document_replaced"),
        _project("viewport_content_changed"),
        _project("changes_present"),
    ]
    relevance = render_batched_text_summary_relevance_evidence(
        frames,
        token_budget=14830,
    )
    assert relevance.starting_per_frame_allowance_tokens == 14830 // 3

    grouped = {0: [0, 1], 1: [1, 2]}
    analysis = render_packed_text_summary_analysis_evidence(
        frames,
        grouped,
        token_budget=22078,
    )
    assert analysis.starting_per_frame_allowance_tokens == 22078 // 3
