from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from dom_diff_text.compaction import compact_text_frame
from dom_diff_text.evidence import parse_dom_diff_text
from dom_diff_text.evidence import SemanticRecord, SourceSpan
from dom_diff_text.retrieval import (
    DETERMINISTIC_FALLBACK_RECORDS,
    build_criterion_query,
    build_selection_receipts,
    build_text_retrieval_terms,
    local_relevance_scores,
    parse_criterion_assignment_tag,
    render_batched_relevance_evidence,
    render_criterion_assignment_tag,
    render_packed_analysis_evidence,
)


FIXTURES = Path(__file__).parent / "fixtures" / "dom_diff_text"


def _frames():
    paths = [
        FIXTURES / "changes_present" / "dom_diff1.txt",
        FIXTURES / "document_replaced" / "dom_diff1.txt",
        FIXTURES / "viewport_content_changed" / "dom_diff1.txt",
    ]
    frames = []
    for ordinal, path in enumerate(paths, start=1):
        parsed = parse_dom_diff_text(path, task_id="task", action_ordinal=1)
        if ordinal != 1:
            records = tuple(
                replace(
                    record,
                    record_id=f"s{ordinal}r{index}",
                    source_spans=tuple(
                        replace(
                            span,
                            action_ordinal=ordinal,
                            source_file=f"/evidence/dom_diff{ordinal}.txt",
                        )
                        for span in record.source_spans
                    ),
                )
                for index, record in enumerate(parsed.records, start=1)
            )
            parsed = replace(
                parsed,
                action_ordinal=ordinal,
                action_id=str(ordinal),
                text_path=f"/evidence/dom_diff{ordinal}.txt",
                records=records,
            )
        frames.append(compact_text_frame(parsed))
    return frames


def _rubric():
    return {
        "items": [
            {
                "criterion": "Report the publisher and release date",
                "description": "Verify Microsoft Studios and exact date 7/6/2022",
                "max_points": 7,
            },
            {
                "criterion": "Preserve page navigation",
                "description": "Confirm navigation to the result URL",
                "max_points": 3,
            },
        ]
    }


def _displayed_allowed_frames(
    text: str, criterion_count: int
) -> dict[int, tuple[int, ...]]:
    lines = text.splitlines()
    start = lines.index("ALLOWED FRAMES") + 1
    output: dict[int, tuple[int, ...]] = {}
    for line in lines[start : start + criterion_count]:
        criterion, raw_values = line.split("=", 1)
        assert criterion.startswith("C")
        assert raw_values.startswith("[") and raw_values.endswith("]")
        values = raw_values[1:-1]
        output[int(criterion[1:])] = tuple(
            int(value) for value in values.split(",") if value
        )
    return output


def test_terms_preserve_phrases_numbers_dates_and_units() -> None:
    terms = build_text_retrieval_terms(
        task="Report a price in USD and release date",
        rubric_items=_rubric()["items"],
        predicted_output='Publisher "Microsoft Studios"; 7/6/2022; $69.99; 60 fps',
    )
    assert "microsoft studios" in terms
    assert "7/6/2022" in terms
    assert "$69.99" in terms
    assert any("60 fps" == term for term in terms)


def test_answer_terms_are_used_only_when_criterion_relevant() -> None:
    query = build_criterion_query(
        0,
        _rubric()["items"][0],
        "Publisher Microsoft Studios; unrelated secret 9999",
    )
    assert "microsoft" in query.lexical_terms
    assert "9999" not in query.exact_numbers


def test_task_instruction_contributes_exact_criterion_query_values() -> None:
    query = build_criterion_query(
        0,
        {"criterion": "Report the requested fact", "description": "Be exact"},
        "",
        task="Report the height 330 m and year 2022",
    )
    assert "330 m" in query.exact_numbers
    assert "2022" in query.exact_numbers


def test_local_relevance_is_stable_and_has_all_criteria() -> None:
    frames = _frames()
    first = local_relevance_scores(
        frames,
        _rubric(),
        task="Report publisher and date",
        predicted_output="Microsoft Studios 7/6/2022",
    )
    second = local_relevance_scores(
        frames,
        _rubric(),
        task="Report publisher and date",
        predicted_output="Microsoft Studios 7/6/2022",
    )
    assert first == second
    assert list(first) == [0, 1, 2]
    assert all(
        {0, 1, "screenshot_idx", "evidence_idx"} == set(row) for row in first.values()
    )


def test_selection_receipt_preserves_top_k_steps() -> None:
    frames = _frames()
    scores = local_relevance_scores(
        frames,
        _rubric(),
        task="Report publisher and date",
        predicted_output="Microsoft Studios 7/6/2022",
    )
    grouped = {0: [0, 1], 1: [1]}
    receipts = build_selection_receipts(
        frames,
        grouped,
        scores,
        _rubric(),
        predicted_output="Microsoft Studios 7/6/2022",
    )
    assert receipts[0].selected_frame_indices == (0, 1)
    assert receipts[0].selected_steps == (1, 2)
    assert receipts[0].dropped_candidate_count == 1


def test_soft_starting_target_expands_without_context_omissions() -> None:
    packed = render_batched_relevance_evidence(
        _frames(),
        _rubric(),
        task="Report publisher and release date",
        predicted_output="Microsoft Studios 7/6/2022",
        starting_target_tokens=20,
        model_context_window_tokens=16000,
        completion_reserve_tokens=1000,
        prompt_headroom_tokens=500,
        fixed_prompt_tokens=1000,
    )
    assert packed.budget_receipt.expansion_tokens > 0
    assert not packed.budget_receipt.overflow
    assert not packed.omission_receipts
    assert packed.estimated_tokens <= packed.budget_receipt.max_evidence_tokens
    assert all(
        "starting_target" not in item.reason for item in packed.omission_receipts
    )


def test_disabling_expansion_fails_instead_of_dropping_for_soft_cap() -> None:
    with pytest.raises(ValueError, match="artificial cap"):
        render_batched_relevance_evidence(
            _frames(),
            _rubric(),
            task="Report publisher and release date",
            predicted_output="Microsoft Studios 7/6/2022",
            starting_target_tokens=20,
            model_context_window_tokens=16000,
            completion_reserve_tokens=1000,
            prompt_headroom_tokens=500,
            fixed_prompt_tokens=1000,
            allow_budget_expansion=False,
        )


def test_true_context_limit_omits_complete_chunks_with_receipts() -> None:
    packed = render_batched_relevance_evidence(
        _frames(),
        _rubric(),
        task="Published Microsoft release date Old result Earlier release navigation",
        predicted_output="Microsoft Studios 7/6/2022",
        starting_target_tokens=50,
        model_context_window_tokens=500,
        completion_reserve_tokens=100,
        prompt_headroom_tokens=50,
        fixed_prompt_tokens=100,
    )
    assert packed.budget_receipt.overflow
    assert packed.omission_receipts
    assert all(item.reason == "context_limit" for item in packed.omission_receipts)
    assert all(item.source_refs for item in packed.omission_receipts)
    assert "context_limit_omitted_relevant_records" in packed.text
    assert packed.estimated_tokens <= packed.budget_receipt.max_evidence_tokens


def test_ledger_context_receipts_keep_every_cross_step_occurrence() -> None:
    source = parse_dom_diff_text(
        FIXTURES / "changes_present" / "dom_diff1.txt",
        task_id="task",
        action_ordinal=1,
    )
    fact = "criterion fact " + " ".join(
        f"supporting-detail-{index}" for index in range(300)
    )
    span1 = SourceSpan(
        task_id="task",
        action_ordinal=1,
        source_file="/evidence/dom_diff1.txt",
        source_line_start=20,
        source_line_end=20,
        source_line_sha256="one",
    )
    record1 = SemanticRecord(
        record_id="s1r1",
        operation="added",
        scope="document_text",
        record_kind="text",
        text=fact,
        source_spans=(span1,),
    )
    span2 = replace(
        span1,
        action_ordinal=2,
        source_file="/evidence/dom_diff2.txt",
        source_line_sha256="two",
    )
    record2 = replace(record1, record_id="s2r1", source_spans=(span2,))
    frame1 = compact_text_frame(
        replace(source, records=(record1,)), max_chunk_tokens=40
    )
    frame2 = compact_text_frame(
        replace(
            source,
            action_ordinal=2,
            action_id="2",
            text_path="/evidence/dom_diff2.txt",
            records=(record2,),
        ),
        max_chunk_tokens=40,
    )
    packed = render_batched_relevance_evidence(
        [frame1, frame2],
        {
            "items": [
                {"criterion": "criterion fact", "description": "exact", "max_points": 1}
            ]
        },
        task="Report criterion facts",
        predicted_output="",
        starting_target_tokens=20,
        model_context_window_tokens=800,
        completion_reserve_tokens=100,
        prompt_headroom_tokens=50,
        fixed_prompt_tokens=100,
    )
    ledger_omissions = list(packed.omission_receipts)
    assert ledger_omissions
    assert all(
        {"s1:L20", "s2:L20"} <= set(item.source_refs) for item in ledger_omissions
    )


def test_mandatory_envelope_overflow_fails_before_model_call() -> None:
    with pytest.raises(ValueError, match="mandatory"):
        render_batched_relevance_evidence(
            _frames(),
            _rubric(),
            task="publisher",
            predicted_output="",
            starting_target_tokens=10,
            model_context_window_tokens=120,
            completion_reserve_tokens=40,
            prompt_headroom_tokens=30,
            fixed_prompt_tokens=30,
        )


def test_packed_analysis_is_criterion_specific_and_auditable() -> None:
    frames = _frames()
    packed = render_packed_analysis_evidence(
        frames,
        {0: [0, 2], 1: [1]},
        _rubric(),
        predicted_output="Microsoft Studios 7/6/2022",
        starting_target_tokens=24000,
        model_context_window_tokens=32000,
        completion_reserve_tokens=4000,
        prompt_headroom_tokens=1000,
        fixed_prompt_tokens=2000,
    )
    assert packed.frame_indices == (0, 1, 2)
    assert "FRAME 0 | STEP 1 " in packed.text
    assert "FRAME 1 | STEP 2 " in packed.text
    assert "FRAME 2 | STEP 3 " in packed.text
    assert packed.criterion_frame_assignments == {
        0: (2,),
        1: (1,),
    }
    assert set(packed.criterion_chunk_assignments) == {0, 1}
    assert packed.criterion_chunk_assignments[0]
    assert packed.criterion_chunk_assignments[1]
    assert _displayed_allowed_frames(packed.text, 2) == dict(
        packed.criterion_frame_assignments
    )
    assert "ALLOWED FRAMES\nC0=[2]\nC1=[1]" in packed.text
    allowed_block = packed.text.split("ALLOWED FRAMES\n", 1)[1].splitlines()[:2]
    assert all("STEP" not in line and "s1r" not in line and "L" not in line for line in allowed_block)
    observed: dict[int, list[str]] = {0: [], 1: []}
    for line in packed.text.splitlines():
        if not line.startswith("C["):
            continue
        tag, rest = line.split(" ", 1)
        chunk_id = rest.split("]", 1)[0].removeprefix("[")
        for criterion_idx in parse_criterion_assignment_tag(tag):
            observed[criterion_idx].append(chunk_id)
    assert {
        key: tuple(value) for key, value in observed.items()
    } == packed.criterion_chunk_assignments
    assert {item.reason for item in packed.retrieval_omissions} <= {
        "criterion_not_retrieved",
        "below_relevance_threshold",
    }


def test_context_omitted_frames_are_removed_from_final_criterion_allowlists() -> None:
    frames = _frames()
    packed = render_packed_analysis_evidence(
        frames,
        {0: [0, 2], 1: [1]},
        _rubric(),
        predicted_output="Microsoft Studios 7/6/2022",
        starting_target_tokens=10,
        model_context_window_tokens=500,
        completion_reserve_tokens=100,
        prompt_headroom_tokens=50,
        fixed_prompt_tokens=100,
    )
    assert packed.budget_receipt.overflow
    assert packed.omission_receipts
    assert packed.criterion_frame_assignments == {
        0: (),
        1: (1,),
    }
    assert _displayed_allowed_frames(packed.text, 2) == {
        0: (),
        1: (1,),
    }
    assert "ALLOWED FRAMES\nC0=[]\nC1=[1]" in packed.text
    assert all(item.reason == "context_limit" for item in packed.omission_receipts)


def test_criterion_assignment_tag_round_trips_without_lexical_ranges() -> None:
    values = (0, 2, 10)
    rendered = render_criterion_assignment_tag(values)
    assert rendered == "C[0,2,10]"
    assert parse_criterion_assignment_tag(rendered) == values


def test_weak_single_token_overlap_is_excluded_with_distinct_receipt() -> None:
    source = parse_dom_diff_text(
        FIXTURES / "changes_present" / "dom_diff1.txt",
        task_id="task",
        action_ordinal=1,
    )
    records = (
        SemanticRecord(
            record_id="s1r1",
            operation="added",
            scope="document_text",
            record_kind="text",
            text="Mission overview",
            source_spans=(_span_for_test(1),),
        ),
        SemanticRecord(
            record_id="s1r2",
            operation="added",
            scope="document_text",
            record_kind="text",
            text="Scheduled for 2027",
            source_spans=(_span_for_test(2),),
        ),
    )
    frame = compact_text_frame(replace(source, records=records))
    packed = render_packed_analysis_evidence(
        [frame],
        {0: [0]},
        {
            "items": [
                {
                    "criterion": "Report mission planned launch year",
                    "description": "Use the exact year 2027",
                    "max_points": 1,
                }
            ]
        },
        predicted_output="2027",
        task="Report the planned launch year",
        starting_target_tokens=100,
        model_context_window_tokens=4000,
        completion_reserve_tokens=500,
        prompt_headroom_tokens=100,
        fixed_prompt_tokens=500,
    )
    weak = next(item for item in packed.retrieval_omissions if item.item_id == "s1r1")
    assert weak.reason == "below_relevance_threshold"
    assert "Scheduled for 2027" in packed.text


def _span_for_test(line: int, step: int = 1) -> SourceSpan:
    return SourceSpan(
        task_id="task",
        action_ordinal=step,
        source_file=f"/evidence/dom_diff{step}.txt",
        source_line_start=line,
        source_line_end=line,
        source_line_sha256=f"hash-{step}-{line}",
    )


def test_no_match_fallback_is_small_and_deterministic() -> None:
    source = parse_dom_diff_text(
        FIXTURES / "changes_present" / "dom_diff1.txt",
        task_id="task",
        action_ordinal=1,
    )
    records = tuple(
        SemanticRecord(
            record_id=f"s1r{index}",
            operation="added",
            scope="document_text",
            record_kind="text",
            text=f"Unrelated value {chr(64 + index)}",
            source_spans=(_span_for_test(index),),
        )
        for index in range(1, 6)
    )
    frame = compact_text_frame(replace(source, records=records))
    kwargs = dict(
        frames=[frame],
        grouped_frames={0: [0]},
        rubric={
            "items": [
                {
                    "criterion": "Report publisher",
                    "description": "Find publisher name",
                    "max_points": 1,
                }
            ]
        },
        predicted_output="",
        task="Report publisher",
        starting_target_tokens=100,
        model_context_window_tokens=4000,
        completion_reserve_tokens=500,
        prompt_headroom_tokens=100,
        fixed_prompt_tokens=500,
    )
    first = render_packed_analysis_evidence(**kwargs)
    second = render_packed_analysis_evidence(**kwargs)
    assert first.text == second.text
    assert len(first.criterion_chunk_assignments[0]) == DETERMINISTIC_FALLBACK_RECORDS


def test_five_frame_ledger_preserves_headers_and_discrete_occurrences() -> None:
    source = parse_dom_diff_text(
        FIXTURES / "changes_present" / "dom_diff1.txt",
        task_id="task",
        action_ordinal=1,
    )
    frames = []
    for step in range(1, 6):
        record = SemanticRecord(
            record_id=f"s{step}r1",
            operation="added",
            scope="document_text",
            record_kind="text",
            text="Shared chronological fact",
            source_spans=(_span_for_test(10, step),),
        )
        frames.append(
            compact_text_frame(
                replace(
                    source,
                    action_ordinal=step,
                    action_id=str(step),
                    text_path=f"/evidence/dom_diff{step}.txt",
                    records=(record,),
                )
            )
        )
    packed = render_batched_relevance_evidence(
        frames,
        {
            "items": [
                {
                    "criterion": "Report chronological fact",
                    "description": "Use the shared fact",
                    "max_points": 1,
                }
            ]
        },
        task="Report the shared chronological fact",
        predicted_output="",
        starting_target_tokens=100,
        model_context_window_tokens=4000,
        completion_reserve_tokens=500,
        prompt_headroom_tokens=100,
        fixed_prompt_tokens=500,
    )
    headers = [line for line in packed.text.splitlines() if line.startswith("FRAME ")]
    assert len(headers) == 5
    assert all(
        header.startswith(f"FRAME {frame_idx} | STEP {frame_idx + 1} ")
        for frame_idx, header in enumerate(headers)
    )
    assert '@1,2,3,4,5 [s1r1] +DOC "Shared chronological fact"' in packed.text


def test_budget_inputs_change_receipts() -> None:
    common = dict(
        frames=_frames(),
        rubric=_rubric(),
        task="publisher date",
        predicted_output="Microsoft Studios 7/6/2022",
        model_context_window_tokens=16000,
        completion_reserve_tokens=1000,
        prompt_headroom_tokens=500,
        fixed_prompt_tokens=1000,
    )
    first = render_batched_relevance_evidence(**common, starting_target_tokens=100)
    second = render_batched_relevance_evidence(**common, starting_target_tokens=200)
    assert first.budget_receipt.starting_target_tokens == 100
    assert second.budget_receipt.starting_target_tokens == 200
    assert first.budget_receipt.to_dict() != second.budget_receipt.to_dict()
