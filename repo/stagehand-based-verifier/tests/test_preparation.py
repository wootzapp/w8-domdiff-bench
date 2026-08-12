from __future__ import annotations

import json
from pathlib import Path

from stagehand_verifier.loader import load_stagehand_trajectory
from stagehand_verifier.preparation import prepare_stagehand_trajectory


def test_prepared_act_keeps_canonical_name_separate(stagehand_task: Path, tmp_path: Path) -> None:
    output = tmp_path / "prepared"
    prepare_stagehand_trajectory(stagehand_task, output)
    lines = [json.loads(line) for line in (output / "web_surfer.log").read_text().splitlines()]
    assert lines[1]["action"] == "act"
    assert lines[1]["arguments"]["action"] == "Enable Alpha"
    trajectory, preflight = load_stagehand_trajectory(output)
    assert trajectory.actions[1].name == "act"
    assert preflight.alignment_complete
