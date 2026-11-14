import json
from pathlib import Path

import pytest

from w8bench.verifier.validate_inputs import dataset_only_preflight, parse_actions
from w8bench.verifier.run_comparison import commands, validate_command_parity
from .conftest import tree_digest
from .test_automated_evidence_audit import _paired_capture_context


def test_local_pair_preflight_never_downloads_or_calls_models(pair_factory, monkeypatch):
    pair = pair_factory()
    before = tree_digest(pair["staged"])
    monkeypatch.setattr("httpx.Client.send", lambda *args, **kwargs: pytest.fail("Unexpected network request"))
    monkeypatch.setattr("httpx.AsyncClient.send", lambda *args, **kwargs: pytest.fail("Unexpected network request"))
    receipt = dataset_only_preflight(pair["screenshot"], pair["dom"])
    assert receipt["actions"] == 1 and receipt["screenshots"] == receipt["dom_model_states"] == 2
    assert tree_digest(pair["staged"]) == before


def test_local_missing_input_does_not_fall_back(pair_factory, tmp_path):
    pair = pair_factory()
    with pytest.raises((ValueError, FileNotFoundError)):
        dataset_only_preflight(tmp_path / "missing", pair["dom"])


@pytest.mark.parametrize("mutation", ["instruction", "answer", "action", "state"])
def test_local_pair_mismatch_fails_before_clients(pair_factory, mutation):
    pair = pair_factory()
    if mutation == "instruction":
        path = pair["dom"] / "task_data.json"
        value = json.loads(path.read_text()); value["confirmed_task"] = "Another task"
        path.write_text(json.dumps(value))
    elif mutation == "answer":
        path = pair["dom"] / "final_answer.json"
        value = json.loads(path.read_text()); value["final_answer"] = "Another answer"
        path.write_text(json.dumps(value))
    elif mutation == "action":
        path = pair["dom"] / "web_surfer.log"
        value = json.loads(path.read_text()); value["arguments"]["coordinate"] = [90, 80]
        path.write_text(json.dumps(value))
    else:
        (pair["dom"] / "dom_model1.txt").unlink()
    with pytest.raises(ValueError):
        dataset_only_preflight(pair["screenshot"], pair["dom"])


def test_coordinate_only_history_is_identical_without_invented_dom_targets(pair_factory):
    pair = pair_factory()
    for key in ("screenshot", "dom"):
        path = pair[key] / "web_surfer.log"
        value = json.loads(path.read_text())
        value["arguments"].pop("ref"); value["arguments"].pop("target")
        path.write_text(json.dumps(value))
    left = parse_actions(pair["screenshot"] / "web_surfer.log", mode="screenshot")
    right = parse_actions(pair["dom"] / "web_surfer.log", mode="dom_model")
    assert left == right
    assert left[0]["coordinate"] == [10, 20]
    assert "ref" not in right[0] and "target_name" not in right[0]
    assert dataset_only_preflight(pair["screenshot"], pair["dom"])["actions"] == 1


def test_paired_preflight_reports_gaps_without_deleting_opposite_evidence(pair_factory):
    pair = pair_factory(sidecars=False, metrics=False)
    _paired_capture_context(pair, dom_gaps=(2,))
    receipt = dataset_only_preflight(pair["screenshot"], pair["dom"])
    assert receipt["screenshots"] == 2 and receipt["dom_model_states"] == 1
    assert receipt["audit_eligible_states"] == [1]
    assert receipt["format_gaps"] == {"screenshot": [], "dom_model": [2]}
    assert (pair["screenshot"] / "screenshot2.png").is_file()


def test_controlled_commands_bind_only_selected_inputs_and_frozen_rubric(pair_factory, tmp_path):
    pair = pair_factory()
    selected = commands(screenshot_task=pair["screenshot"], dom_task=pair["dom"], rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"], eval_config=pair["config"], run_root=tmp_path / "evaluation")
    controls = validate_command_parity(selected)
    assert controls["judge_model"] == "gpt-5.2"
    assert controls["action_judge_model"] == "gpt-5.6-terra"
    for name, command in selected.items():
        expected = pair["screenshot"] if name == "screenshot_verifier" else pair["dom"]
        assert Path(command[command.index("--input") + 1]) == expected
        assert Path(command[command.index("--rubric-file") + 1]) == pair["rubric"]
        assert command[command.index("--majority-vote-instances") + 1] == "1"


@pytest.mark.parametrize("missing_format", ["dom_model", "screenshot"])
def test_fully_missing_passive_format_does_not_block_available_format_preflight(pair_factory, missing_format):
    pair = pair_factory(sidecars=False, metrics=False)
    kwargs = {"dom_gaps": (1, 2)} if missing_format == "dom_model" else {"screenshot_gaps": (1, 2)}
    _paired_capture_context(pair, **kwargs)
    receipt = dataset_only_preflight(pair["screenshot"], pair["dom"])
    assert receipt["audit_eligible_states"] == []
    assert receipt["dom_model_states"] == (0 if missing_format == "dom_model" else 2)
    assert receipt["screenshots"] == (0 if missing_format == "screenshot" else 2)
    assert len(receipt["alignment"]["transitions"]) == 1
