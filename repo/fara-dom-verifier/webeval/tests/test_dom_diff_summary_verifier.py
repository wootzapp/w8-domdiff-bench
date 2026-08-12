from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from webeval.rubric_agent.dom_diff_adapter import load_dom_diff_trajectory
from webeval.rubric_agent.dom_diff_summary_adapter import (
    build_dom_diff_summary_input,
    validate_summary_input_paths,
)
from webeval.rubric_agent.dom_diff_summary_compaction import (
    COMPACT_SUMMARY_SCHEMA,
    build_trajectory_ledger,
    compact_summary_frame,
    render_compact_frame,
)
from webeval.rubric_agent.dom_diff_summary_evidence import (
    load_dom_diff_summary_frames,
    render_summary_result,
    summary_compaction_metrics,
)
from webeval.rubric_agent.dom_diff_summary_retrieval import (
    build_selection_receipts,
    build_summary_retrieval_terms,
    local_relevance_scores,
    render_batched_relevance_evidence,
    render_packed_analysis_evidence,
)


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import verify_trajectories_dom_diff_summary as runner


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _summary(
    *,
    url_before: str = "https://example.test/",
    url_after: str = "https://example.test/",
    url_changed: bool = False,
    title_before: str = "Example",
    title_after: str = "Example",
    title_changed: bool = False,
    text_added: list[str] | None = None,
    text_removed: list[str] | None = None,
    interactive_added: list[dict] | None = None,
    interactive_removed: list[dict] | None = None,
    interactive_changed: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": "1.0",
        "method": "local_agent_observation_summary",
        "captured_at": "2026-01-01T00:00:00Z",
        "url": {
            "before": url_before,
            "after": url_after,
            "changed": url_changed,
        },
        "title": {
            "before": title_before,
            "after": title_after,
            "changed": title_changed,
        },
        "scroll": {
            "before": {"scrollY": 0, "scrollHeight": 1000},
            "after": {"scrollY": 100, "scrollHeight": 1000},
            "changed": True,
        },
        "stats": {
            "before": {
                "candidateInteractives": 2,
                "returnedInteractives": 2,
                "candidateContentBlocks": 0,
                "returnedContentBlocks": 0,
            },
            "after": {
                "candidateInteractives": 2,
                "returnedInteractives": 2,
                "candidateContentBlocks": 0,
                "returnedContentBlocks": 0,
            },
            "elements_added": len(interactive_added or []),
            "elements_removed": len(interactive_removed or []),
            "elements_changed": len(interactive_changed or []),
        },
        "visible_text_added": text_added or [],
        "visible_text_removed": text_removed or [],
        "interactive_added": interactive_added or [],
        "interactive_removed": interactive_removed or [],
        "interactive_changed": interactive_changed or [],
    }


def _trajectory(root: Path, summaries: list[dict]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    events = []
    for ordinal in range(1, len(summaries) + 1):
        action = "stop_execution" if ordinal == len(summaries) else "scroll"
        events.append(
            {
                "action": action,
                "arguments": {"action": action, "delta_y": 100, "thoughts": "test"},
                "url": "https://example.test/",
            }
        )
    (root / "web_surfer.log").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    _write_json(
        root / "final_answer.json",
        {"final_answer": "Height: 330 m", "is_aborted": False, "token_usage": {}},
    )
    for ordinal, summary in enumerate(summaries, start=1):
        _write_json(
            root / f"step_{ordinal:03d}" / "dom_diff_summary.json", summary
        )
    return root


def _task() -> dict:
    return {
        "id": "task",
        "question": "Report the height.",
        "init_url": "https://example.test/",
        "precomputed_rubric": {
            "items": [
                {
                    "criterion": "Report height",
                    "description": "Report the exact height with units.",
                    "max_points": 10,
                    "justification": "",
                    "earned_points": "",
                }
            ]
        },
    }


def _frame(summary: dict, ordinal: int = 1):
    raw = json.dumps(summary, separators=(",", ":")).encode()
    return compact_summary_frame(
        summary,
        action_ordinal=ordinal,
        action_id=str(ordinal),
        source_path=f"/tmp/step_{ordinal:03d}/dom_diff_summary.json",
        source_hash=hashlib.sha256(raw).hexdigest(),
        source_bytes=len(raw),
    )


def test_geometry_only_changes_are_removed_but_semantic_changes_survive() -> None:
    value = _summary(
        interactive_changed=[
            {
                "element": {
                    "idx": 1,
                    "nodeId": 9,
                    "role": "link",
                    "accessibleName": "Height",
                    "text": "330 m",
                    "bounds": {"x": 0, "y": 10, "width": 20, "height": 10},
                    "centerX": 10,
                    "centerY": 15,
                },
                "changes": {
                    "bounds": {
                        "before": {"x": 0, "y": 10},
                        "after": {"x": 0, "y": 110},
                    },
                    "centerY": {"before": 15, "after": 115},
                },
            },
            {
                "element": {
                    "role": "status",
                    "accessibleName": "Height",
                    "text": "330 m",
                },
                "changes": {"text": {"before": "300 m", "after": "330 m"}},
            },
        ]
    )
    frame = _frame(value)
    assert frame.receipt.geometry_only_changes_removed == 1
    assert len(frame.interactive_changed) == 1
    assert frame.interactive_changed[0].changes == (("text", "300 m", "330 m"),)


def test_compact_render_is_budgeted_and_contains_no_geometry_or_timestamp() -> None:
    elements = [
        {
            "idx": index,
            "nodeId": index,
            "role": "link",
            "accessibleName": f"Fact {index}",
            "text": f"Fact {index} is {index} metres",
            "context": "context " * 20,
            "href": f"https://example.test/{index}",
            "bounds": {"x": 1, "y": 2, "width": 3, "height": 4},
            "centerX": 2,
            "centerY": 4,
        }
        for index in range(50)
    ]
    rendered = render_compact_frame(
        _frame(_summary(interactive_added=elements)), token_budget=300
    )
    assert rendered.estimated_tokens <= 300
    assert rendered.records_omitted_by_budget > 0
    assert "OMITTED" in rendered.text
    for forbidden in ("bounds", "centerX", "centerY", "nodeId", "captured_at"):
        assert forbidden not in rendered.text


def test_deduplication_preserves_longest_text_and_exact_number() -> None:
    frame = _frame(
        _summary(
            text_added=[
                "The tower is 330 metres",
                "The tower is 330 metres (1,083 ft) tall.",
                "The tower is 330 metres (1,083 ft) tall.",
            ]
        )
    )
    assert frame.text_added == ("The tower is 330 metres (1,083 ft) tall.",)
    assert frame.receipt.exact_duplicates_removed == 1
    assert frame.receipt.contained_fragments_removed == 1


def test_cross_frame_ledger_retains_steps_and_change_direction() -> None:
    first = _frame(_summary(text_added=["Height 330 m"]), 1)
    second = compact_summary_frame(
        _summary(text_added=["Height 330 m"], text_removed=["Old height 300 m"]),
        action_ordinal=2,
        action_id="2",
        source_path="/tmp/step_002/dom_diff_summary.json",
        source_hash="b" * 64,
        source_bytes=100,
        previous_url="https://example.test/",
        previous_title="Example",
    )
    ledger = build_trajectory_ledger([first, second])
    height = next(record for record in ledger.records if "+TEXT" in record.line)
    removed = next(record for record in ledger.records if "-TEXT" in record.line)
    assert height.steps == (1, 2)
    assert removed.steps == (2,)


def test_summary_adapter_exposes_only_explicit_summary_paths(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task", [_summary(), _summary()])
    trajectory = load_dom_diff_trajectory(root)
    input_dict = build_dom_diff_summary_input(_task(), trajectory)
    validate_summary_input_paths(input_dict, 2)
    assert len(input_dict["dom_actions"]) == 2
    for action in input_dict["dom_actions"]:
        assert action["dom_diff_summary_path"].endswith("dom_diff_summary.json")
        assert action["dom_diff_path"] == ""
        assert action["dom_before_snapshot_path"] == ""
        assert action["dom_after_snapshot_path"] == ""
        assert action["dom_before_page_state_path"] == ""
        assert action["dom_after_page_state_path"] == ""
        assert action["dom_verifier_action_path"] == ""


def test_summary_loader_never_falls_back_to_dom_diff_path(tmp_path: Path) -> None:
    path = tmp_path / "step_001" / "dom_diff_summary.json"
    _write_json(path, _summary(text_added=["Height 330 m"]))
    action = {
        "id": 1,
        "dom_action_ordinal": 1,
        "dom_action_id": "1",
        "dom_diff_path": str(path),
        "dom_diff_summary_path": "",
    }
    with pytest.raises(ValueError, match="no dom_diff_summary_path"):
        load_dom_diff_summary_frames([action])


def test_source_file_hash_and_bytes_are_unchanged(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task", [_summary(text_added=["Height 330 m"])])
    path = root / "step_001" / "dom_diff_summary.json"
    before = path.read_bytes()
    actions = [
        {
            "id": 1,
            "dom_action_ordinal": 1,
            "dom_action_id": "1",
            "dom_diff_summary_path": str(path),
        }
    ]
    frames = load_dom_diff_summary_frames(actions)
    assert path.read_bytes() == before
    assert frames[0].source_sha256 == hashlib.sha256(before).hexdigest()
    assert frames[0].source_bytes == len(before)


def test_compaction_metrics_and_schema_are_explicit(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task", [_summary(text_added=["Height 330 m"])])
    actions = [
        {
            "id": 1,
            "dom_action_ordinal": 1,
            "dom_action_id": "1",
            "dom_diff_summary_path": str(
                root / "step_001" / "dom_diff_summary.json"
            ),
        }
    ]
    frames = load_dom_diff_summary_frames(actions)
    metrics = summary_compaction_metrics(frames)
    rendered = render_summary_result(frames[0], projection="compact", token_budget=500)
    assert metrics["compact_schema_version"] == COMPACT_SUMMARY_SCHEMA
    assert metrics["source_frame_count"] == 1
    assert metrics["compact_bytes"] > 0
    assert len(rendered.text.encode("utf-8")) < metrics["source_bytes"]
    assert rendered.estimated_tokens <= 500


def test_retrieval_is_deterministic_and_top_k_bounded() -> None:
    frames = [
        _frame(_summary(text_added=["Unrelated text"]), 1),
        _frame(_summary(text_added=["The tower is 330 metres (1,083 ft) tall"]), 2),
        _frame(_summary(text_added=["Another fact"]), 3),
    ]
    rubric = _task()["precomputed_rubric"]
    first = local_relevance_scores(
        frames, rubric, task="Report the height", predicted_output="330 m"
    )
    second = local_relevance_scores(
        frames, rubric, task="Report the height", predicted_output="330 m"
    )
    assert first == second
    assert first[1][0] > first[0][0]
    grouped = {0: [1, 2]}
    receipts = build_selection_receipts(
        frames, grouped, first, rubric, predicted_output="330 m"
    )
    assert receipts[0].selected_steps == (2, 3)
    assert len(receipts[0].selected_steps) <= 2


def test_batched_and_packed_evidence_respect_budgets() -> None:
    frames = [
        _frame(_summary(text_added=[f"Height fact {index}: 330 m"]), index + 1)
        for index in range(8)
    ]
    relevance = render_batched_relevance_evidence(frames, token_budget=1400)
    packed = render_packed_analysis_evidence(
        frames, {0: [0, 1, 2, 3, 4]}, token_budget=1200
    )
    assert relevance.estimated_tokens <= 1400
    assert packed.estimated_tokens <= 1200
    for index in range(8):
        assert f"STEP {index + 1}" in relevance.text


def _runner_args(**overrides) -> dict:
    value = {
        "judge_model": "gpt-5.2",
        "o4mini_model": "o4-mini",
        "rubric_threshold": 0.8,
        "max_evidence_per_criterion": 5,
        "mm_keypoint_score_threshold": 3,
        "majority_vote_instances": 1,
        "success_criterion": "outcome",
        "dom_frame_char_budget": 16000,
        "dom_context_char_budget": 48000,
        "dom_top_k": None,
        "summary_mode": "s1",
        "summary_projection": "compact",
        "summary_relevance_mode": "per_frame_llm",
        "summary_analysis_mode": "selected_frames",
        "summary_frame_token_budget": 1500,
        "summary_trajectory_token_budget": 16000,
        "summary_analysis_token_budget": 24000,
        "summary_max_record_chars": 600,
        "request_timeout_seconds": 180.0,
        "max_api_retries": 2,
    }
    value.update(overrides)
    return value


def test_cache_identity_changes_across_summary_modes(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task", [_summary()])
    identities = {
        runner._verifier_identity(
            _runner_args(
                summary_mode=mode,
                summary_projection="raw" if mode == "s0" else "compact",
                summary_relevance_mode=(
                    "batched_llm" if mode in {"s2", "s3"} else "per_frame_llm"
                ),
                summary_analysis_mode="packed" if mode == "s3" else "selected_frames",
            ),
            root,
        )[0]
        for mode in ("s0", "s1", "s2", "s3")
    }
    assert len(identities) == 4


def test_cli_derives_expected_summary_modes() -> None:
    common = [
        "--input",
        "/tmp/input",
        "--task-data",
        "/tmp/tasks.tsv",
        "--task-data-format",
        "webtailbench",
        "--eval-config",
        "/tmp/endpoints",
    ]
    s1 = runner.parse_args(common + ["--summary-mode", "s1"])
    s3 = runner.parse_args(common + ["--summary-mode", "s3"])
    assert (s1.summary_projection, s1.summary_relevance_mode, s1.summary_analysis_mode) == (
        "compact",
        "per_frame_llm",
        "selected_frames",
    )
    assert (s3.summary_projection, s3.summary_relevance_mode, s3.summary_analysis_mode) == (
        "compact",
        "batched_llm",
        "packed",
    )


def test_retrieval_terms_include_rubric_and_answer_numbers() -> None:
    terms = build_summary_retrieval_terms(
        task="Report the Eiffel Tower height",
        rubric_items=_task()["precomputed_rubric"]["items"],
        predicted_output="330 m (1,083 ft)",
    )
    assert "height" in terms
    assert any("330" in term for term in terms)

