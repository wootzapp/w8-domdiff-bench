from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from webeval.rubric_agent.dom_diff_adapter import (
    build_dom_diff_input,
    create_dom_diff_datapoint,
    discover_dom_diff_paths,
    load_dom_diff_trajectory,
)
from webeval.rubric_agent.dom_diff_evidence import (
    CHROMIUMRL_DIFF_SCHEMA,
    load_dom_diff,
    load_dom_diff_frames,
    project_dom_diff_frame,
)


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import verify_trajectories_dom_diff as runner


def _diff(*, text_changes: list | None = None) -> dict:
    result = {
        "summary": {"matchedNodes": 2},
        "textChanges": text_changes or [],
        "insertions": [],
        "deletions": [],
        "attributeChanges": [],
        "moves": [],
        "typeChanges": [],
        "layoutChanges": [],
        "styleChanges": [],
    }
    return {
        "schema_version": "1.0",
        "method": "ChromiumRL.compareDOMState",
        "reference": "before/chromiumrl_dom.json",
        "current": "after/chromiumrl_dom.json",
        "timing": {"ok": True, "elapsed_ms": 1.0},
        "chromiumrl_result": result,
    }


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _trajectory(root: Path, action_count: int = 2) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    events = []
    for ordinal in range(1, action_count + 1):
        events.append(
            {
                "action": "click" if ordinal < action_count else "stop_execution",
                "arguments": {
                    "action": "click" if ordinal < action_count else "stop_execution",
                    "x": 10,
                    "y": 20,
                    "thoughts": "test",
                },
                "url": "https://example.test/",
            }
        )
    (root / "web_surfer.log").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    _write_json(
        root / "final_answer.json",
        {
            "final_answer": "Done",
            "is_aborted": False,
            "is_rel_paths": True,
            "screenshots": ["must-not-be-opened.png"],
            "token_usage": {},
        },
    )
    for ordinal in range(1, action_count + 1):
        _write_json(
            root / f"step_{ordinal:03d}" / "dom_diff.json",
            _diff(
                text_changes=(
                    [{"nodeId": ordinal, "oldValue": "0", "newValue": "1"}]
                    if ordinal == 1
                    else []
                )
            ),
        )
    return root


def _task(rubric=None) -> dict:
    value = {
        "id": "task",
        "question": "Change the counter to one.",
        "init_url": "https://example.test/",
    }
    if rubric is not None:
        value["precomputed_rubric"] = rubric
    return value


def test_valid_and_explicit_empty_terminal_diff_are_accepted(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task")
    paths = discover_dom_diff_paths(root, 2)
    assert [path.parent.name for path in paths] == ["step_001", "step_002"]
    assert load_dom_diff(paths[1])["chromiumrl_result"]["textChanges"] == []


def test_missing_diff_is_rejected(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task")
    (root / "step_002" / "dom_diff.json").unlink()
    with pytest.raises(ValueError, match="Missing DOM diff"):
        discover_dom_diff_paths(root, 2)


def test_duplicate_ordinal_is_rejected(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task", action_count=1)
    _write_json(root / "step_1" / "dom_diff.json", _diff())
    with pytest.raises(ValueError, match="Duplicate DOM diff step ordinals"):
        discover_dom_diff_paths(root, 1)


def test_out_of_order_or_extra_step_is_rejected(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task", action_count=2)
    (root / "step_002").rename(root / "step_003")
    with pytest.raises(ValueError, match=r"expected \[1, 2\], got \[1, 3\]"):
        discover_dom_diff_paths(root, 2)


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda value: value.update(schema_version="9.9"), "Unsupported"),
        (lambda value: value.update(method="other"), "method"),
        (
            lambda value: value["chromiumrl_result"].update(textChanges={}),
            "must be a list",
        ),
    ],
)
def test_malformed_diff_is_rejected(tmp_path: Path, mutation, message: str) -> None:
    path = tmp_path / "dom_diff.json"
    value = _diff()
    mutation(value)
    _write_json(path, value)
    with pytest.raises(ValueError, match=message):
        load_dom_diff(path)


def test_datapoint_contains_only_diff_browser_state_paths(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task")
    trajectory = load_dom_diff_trajectory(root)
    datapoint = create_dom_diff_datapoint(_task(), trajectory)
    summaries = datapoint.solver_log.get_step_summaries()
    assert len(summaries) == 2
    for summary in summaries:
        assert summary.evidence_mode == "dom"
        assert summary.dom_diff_path.endswith("dom_diff.json")
        assert summary.dom_evidence_schema_version == CHROMIUMRL_DIFF_SCHEMA
        assert summary.screenshot_path == ""
        assert summary.dom_before_snapshot_path == ""
        assert summary.dom_after_snapshot_path == ""
        assert summary.dom_before_page_state_path == ""
        assert summary.dom_after_page_state_path == ""
        assert summary.dom_verifier_action_path == ""


def test_diff_only_path_never_opens_forbidden_state_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _trajectory(tmp_path / "task")
    forbidden_names = {
        "screenshot.png",
        "chromiumrl_dom.json",
        "page_state.json",
        "verifier_action.json",
    }
    for ordinal in range(1, 3):
        for side in ("before", "after"):
            for name in ("screenshot.png", "chromiumrl_dom.json", "page_state.json"):
                path = root / f"step_{ordinal:03d}" / side / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("not valid and must not be opened", encoding="utf-8")
        (root / f"step_{ordinal:03d}" / "verifier_action.json").write_text(
            "not valid and must not be opened", encoding="utf-8"
        )

    real_open = Path.open
    opened: list[Path] = []

    def guarded_open(path: Path, *args, **kwargs):
        opened.append(path)
        if path.name in forbidden_names:
            raise AssertionError(f"Forbidden evidence file opened: {path}")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    trajectory = load_dom_diff_trajectory(root)
    input_dict = build_dom_diff_input(_task(), trajectory)
    frames = load_dom_diff_frames(input_dict["dom_actions"])
    assert len(frames) == 2
    assert not any(path.name in forbidden_names for path in opened)


def test_projection_marks_unknown_state_and_keeps_explicit_change(tmp_path: Path) -> None:
    root = _trajectory(tmp_path / "task", action_count=1)
    trajectory = load_dom_diff_trajectory(root)
    input_dict = build_dom_diff_input(_task(), trajectory)
    frame = load_dom_diff_frames(input_dict["dom_actions"])[0]
    text = project_dom_diff_frame(frame, terms=["newvalue", "counter"])
    assert "DECLARED OMISSIONS" in text
    assert "no before snapshot" in text
    assert "textChanges" in text
    assert "text=0 | 1" in text
    assert "BEFORE STATE" not in text
    assert "AFTER STATE" not in text


def test_frozen_rubric_is_passed_without_mutation(tmp_path: Path) -> None:
    rubric = {
        "items": [
            {
                "criterion": "Counter changed",
                "description": "Counter explicitly changes to one",
                "max_points": 10,
                "justification": "",
                "earned_points": "",
            }
        ]
    }
    root = _trajectory(tmp_path / "task", action_count=1)
    trajectory = load_dom_diff_trajectory(root)
    input_dict = build_dom_diff_input(_task(rubric), trajectory)
    assert input_dict["precomputed_rubric"] == rubric
    assert input_dict["precomputed_rubric"] is rubric


def test_cache_and_output_identity_are_dom_diff() -> None:
    args = {
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
        "request_timeout_seconds": 180.0,
        "max_api_retries": 2,
    }
    path = runner._score_path(Path("/tmp/example"), args)
    _, identity = runner._verifier_identity(args)
    assert "dom_diff" in path.name
    assert identity["requested_evidence_mode"] == "dom_diff"
    assert identity["model_roles"] == {
        "judge": "gpt-5.2",
        "action_rubric": "o4-mini",
    }
    assert identity["request_timeout_seconds"] == 180.0
    assert identity["max_api_retries"] == 2


def test_timeout_and_retry_cli_controls() -> None:
    args = runner.parse_args(
        [
            "--input",
            "/tmp/input",
            "--task-data",
            "/tmp/tasks.json",
            "--task-data-format",
            "om2w",
            "--eval-config",
            "/tmp/endpoints",
            "--request-timeout-seconds",
            "45",
            "--max-api-retries",
            "3",
        ]
    )
    assert args.request_timeout_seconds == 45.0
    assert args.max_api_retries == 3


def test_malformed_input_fails_before_client_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _trajectory(tmp_path / "traj" / "task", action_count=1)
    (root / "step_001" / "dom_diff.json").write_text("[]", encoding="utf-8")
    task_path = tmp_path / "tasks.json"
    _write_json(
        task_path,
        [
            {
                "task_id": "task",
                "confirmed_task": "Change the counter to one.",
                "website": "https://example.test/",
            }
        ],
    )
    endpoint_dir = tmp_path / "endpoints"
    endpoint_dir.mkdir()
    called = False

    def forbidden_pool_init(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Judge clients must not be initialized")

    monkeypatch.setattr(runner, "_pool_init", forbidden_pool_init)
    with pytest.raises(SystemExit, match="no judge clients were initialized"):
        runner.main(
            [
                "--input",
                str(root.parent),
                "--task-data",
                str(task_path),
                "--task-data-format",
                "om2w",
                "--eval-config",
                str(endpoint_dir),
                "--report",
                str(tmp_path / "report.jsonl"),
            ]
        )
    assert called is False
