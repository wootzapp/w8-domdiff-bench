from __future__ import annotations

import json
from pathlib import Path

import pytest

from webeval.rubric_agent.dom_diff_text_grep_tools import (
    TOOL_SCHEMAS,
    GrepEvidenceExecutor,
    RawEvidenceBundle,
    assert_no_raw_evidence_in_initial_payload,
)


def _bundle(tmp_path: Path, texts: list[str]) -> RawEvidenceBundle:
    actions = []
    for ordinal, text in enumerate(texts, start=1):
        path = tmp_path / f"dom_diff{ordinal}.txt"
        path.write_text(text, encoding="utf-8")
        actions.append(
            {
                "id": ordinal,
                "dom_action_ordinal": ordinal,
                "dom_action_id": str(ordinal),
                "dom_task_id": "fixture-task",
                "dom_diff_text_path": str(path),
            }
        )
    return RawEvidenceBundle.from_dom_actions(actions)


def test_manifest_has_metadata_only_and_payload_has_no_raw_sentinel(tmp_path):
    sentinel = "RAW_ONLY_SENTINEL_928374"
    bundle = _bundle(tmp_path, [f"status=changes_present\ntext_added {sentinel}\n"])
    manifest = bundle.manifest()
    assert "FRAME 0 | STEP 1" in manifest
    assert "evidence_frame_0000" in manifest
    assert sentinel not in manifest
    payload = {
        "messages": [{"role": "user", "content": manifest}],
        "tools": TOOL_SCHEMAS,
    }
    assert_no_raw_evidence_in_initial_payload(
        payload, bundle, sentinels=[sentinel]
    )


def test_literal_grep_returns_exact_lines_and_provenance(tmp_path):
    bundle = _bundle(
        tmp_path,
        [
            "status=changes_present\nfirst\nPublished by Microsoft Studios\nlast\n",
            "status=viewport_content_changed\nno match here\n",
        ],
    )
    executor = GrepEvidenceExecutor(bundle)
    result = executor.grep_evidence(
        query="microsoft studios",
        file_ids=[],
        mode="literal",
        case_sensitive=False,
        context_before=1,
        context_after=1,
        match_offset=0,
        max_matches=10,
    )
    assert result["ok"] is True
    assert result["matches_total"] == 1
    match = result["matches"][0]
    assert match["frame"] == 0
    assert match["step"] == 1
    assert match["matched_line"] == 3
    assert match["text"] == "first\nPublished by Microsoft Studios\nlast"
    assert executor.coverage_receipt()["frames_returned"] == [0]


def test_regex_pagination_and_stage_file_allowlist(tmp_path):
    bundle = _bundle(
        tmp_path,
        ["value 11\nvalue 22\nvalue 33\n", "value 99\n"],
    )
    executor = GrepEvidenceExecutor(
        bundle, allowed_file_ids=["evidence_frame_0000"], max_matches=2
    )
    first = executor.grep_evidence(
        query=r"value [0-9]+",
        file_ids=[],
        mode="regex",
        case_sensitive=True,
        context_before=0,
        context_after=0,
        match_offset=0,
        max_matches=2,
    )
    assert first["matches_total"] == 3
    assert first["matches_returned"] == 2
    assert first["complete"] is False
    second = executor.grep_evidence(
        query=r"value [0-9]+",
        file_ids=[],
        mode="regex",
        case_sensitive=True,
        context_before=0,
        context_after=0,
        match_offset=first["next_match_offset"],
        max_matches=2,
    )
    assert second["matches_returned"] == 1
    assert second["complete"] is True
    denied = executor.execute(
        "grep_evidence",
        {
            "query": "value",
            "file_ids": ["evidence_frame_0001"],
            "mode": "literal",
            "case_sensitive": True,
            "context_before": 0,
            "context_after": 0,
            "match_offset": 0,
            "max_matches": 1,
        },
    )
    assert denied["ok"] is False
    assert "not allowed" in denied["error"]


def test_read_file_uses_exact_continuation_coordinates(tmp_path):
    bundle = _bundle(tmp_path, ["ABCDEFGHIJK\nsecond line\n"])
    executor = GrepEvidenceExecutor(bundle, max_result_chars=5)
    first = executor.read_file(
        file_id="evidence_frame_0000",
        start_line=1,
        end_line=2,
        start_column=0,
    )
    assert first["segments"] == [
        {
            "line": 1,
            "column_start": 0,
            "column_end": 5,
            "text": "ABCDE",
            "complete_line": False,
        }
    ]
    assert first["continuation"] == {"start_line": 1, "start_column": 5}
    second = executor.read_file(
        file_id="evidence_frame_0000",
        start_line=1,
        end_line=1,
        start_column=5,
    )
    assert second["segments"][0]["text"] == "FGHIJ"
    assert second["continuation"] == {"start_line": 1, "start_column": 10}


def test_source_mutation_is_detected(tmp_path):
    bundle = _bundle(tmp_path, ["status=changes_present\n"])
    bundle.files[0].path.write_text("status=document_replaced\n", encoding="utf-8")
    result = GrepEvidenceExecutor(bundle).execute(
        "read_file",
        {
            "file_id": "evidence_frame_0000",
            "start_line": 1,
            "end_line": 1,
            "start_column": 0,
        },
    )
    assert result["ok"] is False
    assert result["error_type"] == "RuntimeError"
    assert "changed after registration" in result["error"]


def test_unknown_path_arguments_and_symlink_escape_are_rejected(tmp_path):
    bundle = _bundle(tmp_path, ["status=changes_present\n"])
    invalid = GrepEvidenceExecutor(bundle).execute(
        "read_file",
        {"file_id": "../../etc/passwd", "start_line": 1, "end_line": 1, "start_column": 0},
    )
    assert invalid["ok"] is False
    outside = tmp_path.parent / "outside-dom-diff.txt"
    outside.write_text("secret", encoding="utf-8")
    link_root = tmp_path / "linked"
    link_root.mkdir()
    (link_root / "dom_diff1.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink escapes"):
        RawEvidenceBundle.from_dom_actions(
            [
                {
                    "id": 1,
                    "dom_action_ordinal": 1,
                    "dom_diff_text_path": str(link_root / "dom_diff1.txt"),
                }
            ]
        )


def test_tool_schemas_are_strict_and_serializable():
    encoded = json.dumps(TOOL_SCHEMAS)
    assert "grep_evidence" in encoded
    assert "read_file" in encoded
    assert all(tool["function"]["strict"] is True for tool in TOOL_SCHEMAS)
