from __future__ import annotations

import json
from pathlib import Path

import pytest

from stagehand_verifier.loader import load_stagehand_trajectory


def test_n_actions_have_n_plus_one_states(stagehand_task: Path) -> None:
    trajectory, preflight = load_stagehand_trajectory(stagehand_task)
    assert len(trajectory.actions) == 2
    assert preflight.state_count == 3
    assert [(frame.before.ordinal, frame.after.ordinal) for frame in trajectory.frames] == [
        (0, 1), (1, 2)
    ]
    assert trajectory.terminal_state.ordinal == 3


def test_missing_terminal_is_rejected(stagehand_task: Path) -> None:
    terminal = stagehand_task / "step_003"
    (terminal / "action.json").write_text(
        json.dumps({"action": "think", "arguments": {}}), encoding="utf-8"
    )
    (terminal / "tool_result.json").write_text(
        json.dumps({"ok": True, "result": {"toolName": "think"}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="final no-action step"):
        load_stagehand_trajectory(stagehand_task)


def test_synthetic_initial_requires_about_blank(stagehand_task: Path) -> None:
    payload = json.loads((stagehand_task / "task.json").read_text())
    payload["start_url"] = "https://already-loaded.test"
    (stagehand_task / "task.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic state"):
        load_stagehand_trajectory(stagehand_task)
