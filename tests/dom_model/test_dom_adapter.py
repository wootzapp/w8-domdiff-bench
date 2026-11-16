from w8bench.verifier.dom_model.adapter import create_datapoint
from w8bench.verifier.trajectory import load_trajectory
from w8bench.verifier.dom_model.models import Trajectory
from w8bench.verifier.dom_model.rubric_agent import MMRubricAgent


def test_adapter_preserves_screenshot_action_history_without_writes(pair_factory):
    pair = pair_factory()
    before = sorted(path.name for path in pair["dom"].iterdir())
    trajectory = load_trajectory(pair["dom"], Trajectory)
    task = {**pair["task"], "precomputed_rubric": {"items": []}}
    datapoint = create_datapoint(task, trajectory)
    extracted = MMRubricAgent._extract_input_from_datapoint(datapoint, str(pair["dom"]), True)
    after = sorted(path.name for path in pair["dom"].iterdir())
    assert before == after
    assert "Action 1: left_click" in extracted["action_history"]
    assert extracted["actions_list"] == [{"id": 1}]

