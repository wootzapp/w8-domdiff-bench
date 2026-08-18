from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_compaction import compact_text_frame
from webeval.rubric_agent.dom_diff_text_evidence import (
    SemanticRecord,
    SourceSpan,
    parse_dom_diff_text,
)
from webeval.rubric_agent.dom_diff_text_retrieval import (
    render_batched_relevance_evidence,
    render_packed_analysis_evidence,
)
from webeval.rubric_agent.dom_diff_text_s3_capping import (
    S3_FIELD_CHAR_LIMIT,
    apply_s3_prompt_cap,
    clip_model_facing_fields,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "dom_diff_text"
    / "changes_present"
    / "dom_diff1.txt"
)


def _span(line: int, step: int = 1) -> SourceSpan:
    return SourceSpan(
        task_id="task",
        action_ordinal=step,
        source_file=f"/evidence/dom_diff{step}.txt",
        source_line_start=line,
        source_line_end=line,
        source_line_sha256=f"hash-{step}-{line}",
    )


def _rubric() -> dict:
    return {
        "items": [
            {
                "criterion": "Report target evidence and final state",
                "description": "Use exact target evidence and confirmation values",
                "max_points": 1,
            }
        ]
    }


def _dense_frames():
    parsed = parse_dom_diff_text(FIXTURE, task_id="task", action_ordinal=1)
    records = [
        SemanticRecord(
            record_id="s1r1",
            operation="navigation",
            scope="page",
            record_kind="navigation",
            navigation_from="https://example.test/start",
            navigation_to="https://example.test/result",
            source_spans=(_span(10),),
        ),
        SemanticRecord(
            record_id="s1r2",
            operation="changed",
            scope="interactive",
            record_kind="element",
            role="button",
            accessible_name="Target evidence",
            changed_field="pressed",
            before_value=False,
            after_value=True,
            source_spans=(_span(11),),
        ),
    ]
    for index in range(3, 14):
        records.append(
            SemanticRecord(
                record_id=f"s1r{index}",
                operation="added",
                scope="document_text",
                record_kind="text",
                text=(
                    f"Target evidence supporting detail {index} "
                    + " ".join(f"ordinary-{index}-{word}" for word in range(150))
                ),
                source_spans=(_span(8 + index),),
            )
        )
    return [
        compact_text_frame(
            replace(parsed, records=tuple(records)),
            max_chunk_tokens=2000,
        )
    ]


def _base_packs():
    frames = _dense_frames()
    rubric = _rubric()
    relevance = render_batched_relevance_evidence(
        frames,
        rubric,
        task="Report target evidence and final state",
        predicted_output="",
        starting_target_tokens=16000,
        model_context_window_tokens=128000,
        completion_reserve_tokens=4096,
        prompt_headroom_tokens=1024,
        fixed_prompt_tokens=10,
    )
    analysis = render_packed_analysis_evidence(
        frames,
        {0: [0]},
        rubric,
        task="Report target evidence and final state",
        predicted_output="",
        starting_target_tokens=24000,
        model_context_window_tokens=128000,
        completion_reserve_tokens=8192,
        prompt_headroom_tokens=1024,
        fixed_prompt_tokens=10,
    )
    return frames, relevance, analysis


def test_clips_each_model_field_at_600_characters() -> None:
    value = "A" * 650
    line = (
        '[s1r1] +EL[interactive] role="button" '
        f'name="{value}" states=[{{"name":"pressed","value":"true"}}]'
    )
    clipped, count, suffixes = clip_model_facing_fields(line)
    assert count == 1
    assert len(suffixes) == 1
    assert "A" * S3_FIELD_CHAR_LIMIT not in clipped
    assert "states=" in clipped
    assert '"pressed"' in clipped
    assert clipped.endswith('states=[{"name":"pressed","value":"true"}]')


@pytest.mark.parametrize("cap", [10000, 15000, 20000])
def test_configured_total_cap_is_a_true_user_prompt_ceiling(cap: int) -> None:
    frames, relevance, analysis = _base_packs()
    assert "experimental_s3_cap_receipt" not in relevance.to_dict()
    estimator = TokenEstimator("gpt-5.2")
    render_relevance = lambda evidence: "STATIC RELEVANCE\n" + evidence
    render_analysis = lambda evidence: "STATIC ANALYSIS\n" + evidence
    capped_relevance = apply_s3_prompt_cap(
        relevance,
        frames,
        stage="relevance",
        total_prompt_cap_tokens=cap,
        empty_prompt_tokens=estimator.count(render_relevance("")),
        render_prompt=render_relevance,
    )
    capped_analysis = apply_s3_prompt_cap(
        analysis,
        frames,
        stage="analysis",
        total_prompt_cap_tokens=cap,
        empty_prompt_tokens=estimator.count(render_analysis("")),
        render_prompt=render_analysis,
    )
    assert estimator.count(render_relevance(capped_relevance.text)) <= cap
    assert estimator.count(render_analysis(capped_analysis.text)) <= cap
    assert capped_relevance.experimental_s3_cap_receipt["reserve_tokens"] == 64
    assert capped_analysis.experimental_s3_cap_receipt["reserve_tokens"] == 64
    assert "experimental_s3_cap_receipt" in capped_relevance.to_dict()
    assert "experimental_s3_cap_receipt" in capped_analysis.to_dict()


def test_priority_packing_omits_whole_records_and_surfaces_receipt() -> None:
    frames, relevance, _ = _base_packs()
    estimator = TokenEstimator("gpt-5.2")
    render_prompt = lambda evidence: "STATIC\n" + evidence
    capped = apply_s3_prompt_cap(
        relevance,
        frames,
        stage="relevance",
        total_prompt_cap_tokens=650,
        empty_prompt_tokens=estimator.count(render_prompt("")),
        render_prompt=render_prompt,
    )
    receipt = capped.experimental_s3_cap_receipt
    assert receipt["records_omitted"] > 0
    assert "s3_cap_budget=" in capped.text
    assert "https://example.test/result" in capped.text
    omitted_ids = {
        item.item_id
        for item in capped.omission_receipts
        if item.reason == "s3_prompt_cap"
    }
    assert omitted_ids
    for item_id in omitted_ids:
        assert f"[{item_id}]" not in capped.text


def test_analysis_allowlist_and_validator_mapping_share_final_capped_set() -> None:
    frames, _, analysis = _base_packs()
    estimator = TokenEstimator("gpt-5.2")
    render_prompt = lambda evidence: "STATIC ANALYSIS\n" + evidence
    capped = apply_s3_prompt_cap(
        analysis,
        frames,
        stage="analysis",
        total_prompt_cap_tokens=650,
        empty_prompt_tokens=estimator.count(render_prompt("")),
        render_prompt=render_prompt,
    )
    allowed = capped.criterion_frame_assignments
    expected_line = (
        "C0=[" + ",".join(str(value) for value in allowed[0]) + "]"
    )
    assert expected_line in capped.text
    assert set(capped.criterion_chunk_assignments[0]) == {
        record.item_id
        for record in capped.model_records
        if 0 in record.criterion_indices
    }


def test_no_omission_preserves_criterion_specific_assignment_order() -> None:
    frames, _, analysis = _base_packs()
    original = tuple(reversed(analysis.criterion_chunk_assignments[0]))
    analysis = replace(
        analysis,
        criterion_chunk_assignments={0: original},
    )
    estimator = TokenEstimator("gpt-5.2")
    render_prompt = lambda evidence: "STATIC ANALYSIS\n" + evidence

    capped = apply_s3_prompt_cap(
        analysis,
        frames,
        stage="analysis",
        total_prompt_cap_tokens=20000,
        empty_prompt_tokens=estimator.count(render_prompt("")),
        render_prompt=render_prompt,
    )

    assert capped.experimental_s3_cap_receipt["records_omitted"] == 0
    assert capped.criterion_chunk_assignments[0] == original
    assert capped.criterion_frame_assignments[0] == (0,)
    assert "C0=[0]" in capped.text


def test_too_small_cap_fails_instead_of_expanding() -> None:
    frames, relevance, _ = _base_packs()
    estimator = TokenEstimator("gpt-5.2")
    render_prompt = lambda evidence: "STATIC\n" + evidence
    with pytest.raises(ValueError, match="leaves only"):
        apply_s3_prompt_cap(
            relevance,
            frames,
            stage="relevance",
            total_prompt_cap_tokens=100,
            empty_prompt_tokens=estimator.count(render_prompt("")),
            render_prompt=render_prompt,
        )
