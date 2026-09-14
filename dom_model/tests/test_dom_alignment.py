import pytest

from dom_model.alignment import validate_alignment
from dom_model.state_parser import load_dom_model_states


def test_alignment_receipt_has_initial_transition_and_final(pair_factory):
    pair = pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    action = {
        "action": "left_click",
        "url": "https://example.test/done",
        "arguments": {"action": "left_click", "ref": "save-button"},
    }
    receipt = validate_alignment(
        task_id="internal-task-1",
        initial_url="https://example.test/start",
        actions=[action],
        states=states,
    )
    assert receipt.initial_state == 0
    assert receipt.final_state == 1
    assert receipt.transitions[0]["from_state"] == 0
    assert receipt.transitions[0]["to_state"] == 1
    assert not receipt.warnings


def test_initial_url_mismatch_fails(pair_factory):
    pair = pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    with pytest.raises(ValueError, match="Initial URL differs"):
        validate_alignment(task_id="x", initial_url="https://wrong.test", actions=[{"action": "click", "arguments": {}}], states=states)

def test_same_origin_landing_redirect_is_a_warning(pair_factory):
    pair = pair_factory()
    initial = pair["dom"] / "dom_model0.txt"
    initial.write_text(
        initial.read_text(encoding="utf-8").replace("https://example.test/start", "https://example.test/en-US/"),
        encoding="utf-8",
    )
    states = load_dom_model_states(pair["dom"], action_count=1)
    receipt = validate_alignment(
        task_id="x",
        initial_url="https://example.test/",
        actions=[{"action": "click", "url": "https://example.test/done", "arguments": {}}],
        states=states,
    )
    assert [warning.code for warning in receipt.warnings] == ["initial_url_same_origin_redirect"]
