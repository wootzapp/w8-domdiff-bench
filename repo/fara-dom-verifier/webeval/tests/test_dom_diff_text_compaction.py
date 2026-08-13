from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_compaction import (
    build_trajectory_ledger,
    compact_text_frame,
    normalize_text,
    render_full_compact_frame,
    render_ledger_record,
)
from webeval.rubric_agent.dom_diff_text_evidence import (
    SemanticRecord,
    SourceSpan,
    parse_dom_diff_text,
)


FIXTURES = Path(__file__).parent / "fixtures" / "dom_diff_text"


def _frame():
    return parse_dom_diff_text(
        FIXTURES / "changes_present" / "dom_diff1.txt",
        task_id="task",
        action_ordinal=1,
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


def test_unicode_whitespace_normalization_preserves_facts() -> None:
    value = "  Price:\u200b  $1,299.00\n on 7/6/2022  "
    assert normalize_text(value) == "Price: $1,299.00 on 7/6/2022"


def test_exact_duplicates_merge_only_with_all_provenance() -> None:
    frame = _frame()
    original = frame.records[0]
    duplicate = replace(
        original, record_id="duplicate", source_spans=(_span(100),)
    )
    compact = compact_text_frame(replace(frame, records=(original, duplicate)))
    assert len(compact.records) == 1
    assert compact.receipt.exact_duplicates_removed == 1
    spans = compact.records[0].record.source_spans
    assert {span.source_line_start for span in spans} == {
        original.source_spans[0].source_line_start,
        100,
    }


def test_operation_and_scope_direction_never_cancel() -> None:
    records = (
        SemanticRecord(
            record_id="added",
            operation="added",
            scope="document_text",
            record_kind="text",
            text="Shared fact",
            source_spans=(_span(1),),
        ),
        SemanticRecord(
            record_id="removed",
            operation="removed",
            scope="document_text",
            record_kind="text",
            text="Shared fact",
            source_spans=(_span(2),),
        ),
        SemanticRecord(
            record_id="entered",
            operation="viewport_entered",
            scope="viewport_text",
            record_kind="text",
            text="Shared fact",
            source_spans=(_span(3),),
        ),
        SemanticRecord(
            record_id="exited",
            operation="viewport_exited",
            scope="viewport_text",
            record_kind="text",
            text="Shared fact",
            source_spans=(_span(4),),
        ),
    )
    compact = compact_text_frame(replace(_frame(), records=records))
    assert len(compact.records) == 4
    assert [record.record.operation for record in compact.records] == [
        "added",
        "removed",
        "viewport_entered",
        "viewport_exited",
    ]


def test_containment_retains_both_distinct_labels_and_maps_leaf_provenance() -> None:
    records = (
        SemanticRecord(
            record_id="publisher-label",
            operation="viewport_entered",
            scope="viewport_text",
            record_kind="text",
            text="Published by Microsoft Studios",
            source_spans=(_span(1),),
        ),
        SemanticRecord(
            record_id="publisher-value",
            operation="viewport_entered",
            scope="viewport_text",
            record_kind="text",
            text="Microsoft Studios",
            source_spans=(_span(2),),
        ),
        SemanticRecord(
            record_id="developer-label",
            operation="viewport_entered",
            scope="viewport_text",
            record_kind="text",
            text="Developed by Microsoft Studios",
            source_spans=(_span(3),),
        ),
    )
    compact = compact_text_frame(replace(_frame(), records=records))
    assert [item.record.record_id for item in compact.records] == [
        "publisher-label",
        "developer-label",
    ]
    assert compact.receipt.contained_fragments_removed == 1
    assert compact.receipt.source_to_compact["s1:L2"] == (
        "publisher-label",
        "developer-label",
    )
    # The semantically distinct relationships are both retained. The bare leaf
    # is removed only because its exact text remains in each maximal label.
    rendered = render_full_compact_frame(compact)
    assert "Published by Microsoft Studios" in rendered
    assert "Developed by Microsoft Studios" in rendered


def test_same_element_direct_and_visible_exact_text_merge_safely() -> None:
    source = next(
        record
        for record in _frame().records
        if record.operation == "removed" and record.direct_text == "Old state"
    )
    compact = compact_text_frame(replace(_frame(), records=(source,)))
    retained = compact.records[0].record
    assert retained.direct_text == "Old state"
    assert retained.visible_text is None
    assert compact.receipt.element_field_duplicates_removed == 1


def test_duplicate_attribute_names_remain_explicit_records() -> None:
    record = SemanticRecord(
        record_id="states",
        operation="added",
        scope="node",
        record_kind="element",
        selected_attributes=(("aria-label", "First"), ("aria-label", "Second")),
        states=(("selected", "false"), ("selected", "true")),
        source_spans=(_span(8),),
    )
    rendered = render_full_compact_frame(
        compact_text_frame(replace(_frame(), records=(record,)))
    )
    assert rendered.count('"name":"aria-label"') == 2
    assert rendered.count('"name":"selected"') == 2


def test_large_record_is_semantically_chunked_without_clipping() -> None:
    text = " ".join(f"fact-{index} 7/{index + 1}/2026" for index in range(80))
    record = SemanticRecord(
        record_id="large",
        operation="added",
        scope="document_text",
        record_kind="text",
        text=text,
        source_spans=(_span(9),),
    )
    compact = compact_text_frame(
        replace(_frame(), records=(record,)), max_chunk_tokens=40
    )
    retained = compact.records[0]
    assert retained.record.text == text
    assert len(retained.chunks) > 1
    assert [chunk.chunk_index for chunk in retained.chunks] == list(
        range(1, len(retained.chunks) + 1)
    )
    assert all(chunk.chunk_count == len(retained.chunks) for chunk in retained.chunks)
    assert compact.receipt.records_truncated_by_char_limit == 0
    assert "fact-79" in retained.chunks[-1].search_text


def test_full_paths_are_audit_only_in_normal_model_rendering() -> None:
    frame = _frame()
    compact = compact_text_frame(frame)
    rendered = render_full_compact_frame(compact)
    assert "html[1]/body[1]" not in rendered
    assert any("html[1]/body[1]" in path for path in frame.audit.raw_paths)
    assert compact.receipt.model_path_exceptions == ()


def test_geometry_is_removed_but_viewport_text_remains() -> None:
    compact = compact_text_frame(_frame())
    rendered = render_full_compact_frame(compact)
    assert "viewport_geometry" not in rendered
    assert compact.receipt.geometry_only_changes_removed == 1
    assert "+VIEW" in rendered
    assert "-VIEW" in rendered


def test_cross_step_ledger_keeps_every_occurrence_and_step_header() -> None:
    record1 = SemanticRecord(
        record_id="s1",
        operation="added",
        scope="document_text",
        record_kind="text",
        text="Chronological fact",
        source_spans=(_span(1, 1),),
    )
    record2 = replace(
        record1, record_id="s2", source_spans=(_span(1, 2),)
    )
    frame1 = compact_text_frame(replace(_frame(), records=(record1,)))
    second_source = replace(
        _frame(),
        action_ordinal=2,
        action_id="2",
        text_path="/evidence/dom_diff2.txt",
        records=(record2,),
    )
    frame2 = compact_text_frame(second_source)
    ledger = build_trajectory_ledger([frame1, frame2])
    assert len(ledger.ordered_step_headers) == 2
    assert len(ledger.records) == 1
    assert ledger.records[0].occurs_at_steps == (1, 2)
    rendered = render_ledger_record(ledger.records[0])
    assert rendered.startswith("@1,2 ")
    assert "s1:L1" not in rendered and "s2:L1" not in rendered
    assert ledger.records[0].occurrences[0].source_refs == ("s1:L1",)
    assert ledger.records[0].occurrences[1].source_refs == ("s2:L1",)


def test_compaction_is_byte_stable_for_same_input() -> None:
    first = compact_text_frame(_frame()).to_dict()
    second = compact_text_frame(_frame()).to_dict()
    assert first == second


def test_model_and_audit_serializations_are_separate() -> None:
    compact = compact_text_frame(_frame())
    model = json.dumps(compact.to_model_dict(), sort_keys=True)
    audit = json.dumps(compact.to_audit_dict(), sort_keys=True)
    assert "source_spans" not in model
    assert "source_sha256" not in model
    assert "source_to_compact" not in model
    assert "source_spans" in audit
    assert "source_sha256" in audit
    assert "source_to_compact" in audit
    assert compact.compact_bytes == compact.model_bytes
    assert compact.model_bytes < compact.audit_bytes


def test_model_lines_do_not_repeat_audit_bookkeeping() -> None:
    rendered = render_full_compact_frame(compact_text_frame(_frame()))
    evidence_lines = [line for line in rendered.splitlines() if line.startswith("[")]
    assert evidence_lines
    for line in evidence_lines:
        assert " ref=" not in line
        assert " scope=" not in line
        assert " id=" not in line
        assert line.count("[") >= 1


def test_model_facing_render_matches_reviewed_golden_file() -> None:
    expected = (FIXTURES / "compact_model_frame.golden.txt").read_text(
        encoding="utf-8"
    ).rstrip("\n")
    actual = render_full_compact_frame(compact_text_frame(_frame()))
    assert actual == expected


def test_task5_maximal_containment_is_lossless_and_compressive() -> None:
    project_root = Path(__file__).resolve().parents[4]
    source = project_root / "data-new-short-dom" / "task5" / "dom_diff1.txt"
    if not source.is_file():
        return
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    frame = parse_dom_diff_text(source, task_id="task5", action_ordinal=1)
    compact = compact_text_frame(frame)
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    assert before == after

    original_by_id = {record.record_id: record for record in frame.records}
    retained_by_id = {item.record.record_id: item.record for item in compact.records}
    assert compact.receipt.contained_fragments_removed > 0
    for merge in compact.receipt.containment_merges:
        removed = original_by_id[str(merge["merged_record_id"])]
        targets = [retained_by_id[str(value)] for value in merge["retained_record_ids"]]
        assert targets
        assert all(target.operation == removed.operation for target in targets)
        assert all(target.scope == removed.scope for target in targets)
        assert all((removed.text or "") in (target.text or "") for target in targets)
        for span in removed.source_spans:
            assert span.compact_ref in compact.receipt.source_to_compact

    estimator = TokenEstimator("gpt-5.2")
    raw_tokens = estimator.count(source.read_text(encoding="utf-8"))
    model_tokens = estimator.count(render_full_compact_frame(compact))
    assert compact.receipt.compact_text_chars < compact.receipt.source_text_chars
    assert model_tokens < raw_tokens
