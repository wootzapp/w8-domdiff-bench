"""Recording export, modality adapters, state alignment and paired input integrity."""
from __future__ import annotations
import asyncio
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from tests.conftest import tree_digest, _paired_capture_context
from tests.capture.conftest import make_trajectory_dir, digest
from w8bench.task_recorder import runner, prepare_verifier_data as prepare
from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.task_recorder.recorder_support import write_json
from w8bench.verifier.dom_model.adapter import create_datapoint
from w8bench.verifier.dom_model.models import Trajectory
from w8bench.verifier.dom_model.rubric_agent import MMRubricAgent
from w8bench.verifier.dom_model.alignment import validate_alignment
from w8bench.verifier.dom_model.states import load_dom_model_states
from w8bench.verifier.trajectory import load_trajectory
from w8bench.verifier.screenshot_verifier.preflight import preflight_screenshot_task
from w8bench.verifier.validate_inputs import dataset_only_preflight, parse_actions
from w8bench.verifier.run_comparison import commands, validate_command_parity

def _task(tmp_path, screenshots=2):
    root = tmp_path / "task"
    root.mkdir()
    (root / "web_surfer.log").write_text(
        json.dumps({"action": "left_click", "arguments": {"coordinate": [1, 2]}}) + "\n"
    )
    (root / "final_answer.json").write_text(
        json.dumps(
            {
                "final_answer": "done",
                "screenshots": [f"screenshot{index}.png" for index in range(screenshots)],
            }
        )
    )
    for index in range(screenshots):
        (root / f"screenshot{index}.png").write_bytes(b"png")
    return root

def test_create_datapoint_normalizes_actions(tmp_path):
    from w8bench.verifier.dom_model.adapter import create_datapoint
    from w8bench.verifier.dom_model.models import Trajectory

    traj_dir = make_trajectory_dir(tmp_path, n_actions=3, screenshots=False)
    traj = Trajectory(traj_dir, gpt_solver=True)

    task_data = {
        "id": "sample_traj",
        "question": "pretend to click buttons",
        "init_url": "https://example.com",
    }
    dp = create_datapoint(task_data, traj)

    assert dp.task.task_id == "sample_traj"
    assert dp.task.instruction == "pretend to click buttons"
    assert dp.task.environment_config["init_url"] == "https://example.com"

    summaries = dp.solver_log.get_step_summaries()
    assert len(summaries) == 3
    # Last action must have been normalized stop_execution → terminate.
    assert summaries[-1].action_name == "terminate"
    # DOM-model evidence is loaded separately from the action data point.
    for i, s in enumerate(summaries, start=1):
        assert s.index == i
        assert s.evidence_path == ""

def test_dom_datapoint_defaults_missing_initial_url(tmp_path):
    """Task_data without ``init_url`` should default to an empty string
    rather than crashing — WebTailBench TSV does not ship init_url."""
    from w8bench.verifier.dom_model.adapter import create_datapoint
    from w8bench.verifier.dom_model.models import Trajectory

    traj_dir = make_trajectory_dir(tmp_path, n_actions=1, screenshots=False)
    traj = Trajectory(traj_dir, gpt_solver=True)

    dp = create_datapoint({"id": "x", "question": "noop"}, traj)
    assert dp.task.environment_config["init_url"] == ""

def test_adapter_preserves_screenshot_action_history_without_writes(dom_pair_factory):
    pair = dom_pair_factory()
    before = sorted(path.name for path in pair["dom"].iterdir())
    trajectory = load_trajectory(pair["dom"], Trajectory)
    task = {**pair["task"], "precomputed_rubric": {"items": []}}
    datapoint = create_datapoint(task, trajectory)
    extracted = MMRubricAgent._extract_input_from_datapoint(datapoint, str(pair["dom"]), True)
    after = sorted(path.name for path in pair["dom"].iterdir())
    assert before == after
    assert "Action 1: left_click" in extracted["action_history"]
    assert extracted["actions_list"] == [{"id": 1}]

def test_alignment_receipt_has_initial_transition_and_final(dom_pair_factory):
    pair = dom_pair_factory()
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

def test_initial_url_mismatch_fails(dom_pair_factory):
    pair = dom_pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    with pytest.raises(ValueError, match="Initial URL differs"):
        validate_alignment(task_id="x", initial_url="https://wrong.test", actions=[{"action": "click", "arguments": {}}], states=states)

@pytest.mark.parametrize("initial,observed", [
    ("https://www.example.test/start", "https://example.test/start"),
    ("https://example.test/start", "https://www.example.test/start"),
    ("https://WWW.EXAMPLE.TEST/start", "https://example.test:443/start/"),
    ("https://www.example.test/start?q=one", "https://example.test/start?q=one#details"),
    ("http://www.example.test/start", "http://example.test:80/start"),
])
def test_initial_www_alias_preserves_both_urls_with_warning(dom_pair_factory, initial, observed):
    pair = dom_pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    states[0] = replace(states[0], url=observed)
    receipt = validate_alignment(
        task_id="x", initial_url=initial,
        actions=[{"action": "click", "arguments": {}}], states=states,
    )
    assert [warning.code for warning in receipt.warnings] == ["initial_url_www_alias"]
    assert initial in receipt.warnings[0].message
    assert observed in receipt.warnings[0].message
    assert receipt.transitions[0]["before_url"] == observed

@pytest.mark.parametrize("observed", [
    "https://other.test/start", "https://accounts.example.test/start",
    "https://example.test.evil.test/start", "https://example.test:8443/start",
    "http://example.test/start", "https://example.test/other",
    "https://example.test/start?q=different", "https://user@example.test/start",
    "https://@example.test/start",
])
def test_initial_alias_check_rejects_other_differences(dom_pair_factory, observed):
    pair = dom_pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    states[0] = replace(states[0], url=observed)
    with pytest.raises(ValueError, match="Initial URL differs"):
        validate_alignment(
            task_id="x", initial_url="https://www.example.test/start",
            actions=[{"action": "click", "arguments": {}}], states=states,
        )

def test_same_origin_landing_redirect_is_a_warning(dom_pair_factory):
    pair = dom_pair_factory()
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

def test_same_origin_canonical_path_redirect_is_a_warning(dom_pair_factory):
    pair = dom_pair_factory()
    initial = pair["dom"] / "dom_model0.txt"
    initial.write_text(
        initial.read_text(encoding="utf-8").replace(
            "https://example.test/start",
            "https://example.test/canonical/start?period=P7D#details",
        ),
        encoding="utf-8",
    )
    states = load_dom_model_states(pair["dom"], action_count=1)
    receipt = validate_alignment(
        task_id="x",
        initial_url="https://example.test/start",
        actions=[{"action": "click", "url": "https://example.test/done", "arguments": {}}],
        states=states,
    )
    assert [warning.code for warning in receipt.warnings] == ["initial_url_same_origin_redirect"]

def test_sparse_alignment_keeps_full_transitions_without_inventing_missing_state(dom_pair_factory):
    pair = dom_pair_factory()
    original = load_dom_model_states(pair["dom"], action_count=1)
    states = [replace(original[0], index=1), replace(original[1], index=3)]
    context = {"expected_state_ids": [1, 2, 3], "format_gaps": {"dom_model": [2]}}
    receipt = validate_alignment(task_id="x", initial_url=states[0].url,
        actions=[{"action": "click", "arguments": {}}, {"action": "wait", "arguments": {}}],
        states=states, evaluation_context=context)
    assert [(item["from_state"], item["to_state"]) for item in receipt.transitions] == [(1, 2), (2, 3)]
    assert receipt.transitions[0]["after_sha256"] is None
    assert receipt.transitions[1]["before_sha256"] is None
    assert receipt.transitions[1]["after_sha256"] == states[1].sha256
    assert receipt.initial_state == 1 and receipt.final_state == 3
    assert [warning.state_index for warning in receipt.warnings if warning.code == "missing_recorded_state"] == [2]

def test_lossless_ordered_state_loading(dom_pair_factory):
    pair = dom_pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    assert [state.index for state in states] == [0, 1]
    assert states[0].url == "https://example.test/start"
    assert "value=Saved" in states[1].raw_text
    assert "save-button" in states[0].control_refs
    assert states[1].provenance.startswith("m1:L1-L")
    assert states[1].raw_text == (pair["dom"] / "dom_model1.txt").read_text(encoding="utf-8")

def test_rejects_gaps_and_malformed_names(dom_pair_factory):
    pair = dom_pair_factory()
    (pair["dom"] / "dom_model1.txt").rename(pair["dom"] / "dom_model2.txt")
    with pytest.raises(ValueError, match="contiguous"):
        load_dom_model_states(pair["dom"])
    (pair["dom"] / "dom_model2.txt").rename(pair["dom"] / "dom_model01.txt")
    with pytest.raises(ValueError, match="Malformed"):
        load_dom_model_states(pair["dom"])

def test_rejects_n_action_n_plus_two_states(dom_pair_factory):
    pair = dom_pair_factory()
    (pair["dom"] / "dom_model2.txt").write_text("URL: https://example.test/extra\nTitle: Extra\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"N\+1"):
        load_dom_model_states(pair["dom"], action_count=1)

def test_sparse_capture_loads_every_available_state_with_original_ids(tmp_path):
    import json
    context = {"expected_state_ids": [1, 2, 3, 4], "format_gaps": {"dom_model": [2]}}
    (tmp_path / "task_data.json").write_text(json.dumps({"evaluation_context": context}))
    for index in (1, 3, 4):
        (tmp_path / f"dom_model{index}.txt").write_text(f"URL: https://example.test/{index}\nTitle: State {index}\n")
    states = load_dom_model_states(tmp_path, action_count=3)
    assert [state.index for state in states] == [1, 3, 4]
    assert [state.path.name for state in states] == ["dom_model1.txt", "dom_model3.txt", "dom_model4.txt"]
    assert "initial browser state" in states[0].model_text(action_count=3, initial_state_index=1)
    assert "after action 2" in states[1].model_text(action_count=3, initial_state_index=1)
    assert "final browser state" in states[2].model_text(action_count=3, initial_state_index=1)
    # An available state may never be silently dropped by its own verifier.
    (tmp_path / "dom_model2.txt").write_text("URL: https://example.test/2\nTitle: Available\n")
    with pytest.raises(ValueError, match="contiguous"):
        load_dom_model_states(tmp_path, action_count=3)

def test_contiguous_loader_and_rendering_preserve_original_contract(dom_pair_factory):
    import hashlib
    pair = dom_pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    for index, state in enumerate(states):
        path = pair["dom"] / f"dom_model{index}.txt"
        assert state.index == index
        assert state.raw_text == path.read_text()
        assert state.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
        phase = "initial browser state (before action 1)" if index == 0 else "final browser state (after action 1)"
        assert state.model_text(action_count=1) == (
            f"DOM_MODEL_STATE_INDEX: {index}\nDOM_MODEL_PHASE: {phase}\n"
            f"DOM_MODEL_PROVENANCE: m{index}:L1-L{state.line_count}\nDOM_MODEL_SHA256: {state.sha256}\n"
            "DOM_MODEL_LIMITATION: This is structured textual browser evidence, not pixels. "
            "Do not infer pixel-only appearance. Missing content is unproven, especially when "
            "the source declares truncation.\n\n" + path.read_text()
        )

def test_create_datapoint_normalizes_screenshots_and_actions(tmp_path):
    from w8bench.verifier.screenshot_verifier.adapter import (
        create_datapoint,
        normalize_all_screenshot_evidence,
    )
    from w8bench.verifier.screenshot_verifier.models import Trajectory

    traj_dir = make_trajectory_dir(tmp_path, n_actions=3, screenshots=True)
    traj = Trajectory(traj_dir, gpt_solver=True)

    task_data = {
        "id": "sample_traj",
        "question": "pretend to click buttons",
        "init_url": "https://example.com",
    }
    dp = create_datapoint(task_data, traj)

    assert dp.task.task_id == "sample_traj"
    assert dp.task.instruction == "pretend to click buttons"
    assert dp.task.environment_config["init_url"] == "https://example.com"

    summaries = dp.solver_log.get_step_summaries()
    assert len(summaries) == 3
    # Last action must have been normalized stop_execution → terminate.
    assert summaries[-1].action_name == "terminate"
    # Action summaries keep post-action states while all evidence states remain
    # available separately to the evidence loader.
    for i, s in enumerate(summaries, start=1):
        assert s.index == i
        assert s.screenshot_path.endswith(f"screenshot_{i + 1}.png")
    assert normalize_all_screenshot_evidence(traj) == [
        f"screenshot_{i}.png" for i in range(1, 5)
    ]

def test_runner_binds_all_states_without_changing_action_history():
    from w8bench.verifier.screenshot_verifier.runner import _bind_all_screenshot_evidence

    original = {
        "action_history": "State 1: example\\nAction 1: click({})",
        "actions_list": [{"id": 1, "screenshot": "screenshot_2.png"}],
    }
    bound = _bind_all_screenshot_evidence(
        original, ["screenshot_1.png", "screenshot_2.png"], action_count=1
    )

    assert bound["action_history"] == original["action_history"]
    assert bound["actions_list"] == [
        {"id": 1, "screenshot": "screenshot_1.png"},
        {"id": 2, "screenshot": "screenshot_2.png"},
    ]
    assert original["actions_list"] == [{"id": 1, "screenshot": "screenshot_2.png"}]

def test_screenshot_datapoint_defaults_missing_initial_url(tmp_path):
    """Task_data without ``init_url`` should default to an empty string
    rather than crashing — WebTailBench TSV does not ship init_url."""
    from w8bench.verifier.screenshot_verifier.adapter import create_datapoint
    from w8bench.verifier.screenshot_verifier.models import Trajectory

    traj_dir = make_trajectory_dir(tmp_path, n_actions=1, screenshots=True)
    traj = Trajectory(traj_dir, gpt_solver=True)

    dp = create_datapoint({"id": "x", "question": "noop"}, traj)
    assert dp.task.environment_config["init_url"] == ""

def test_accepts_intentional_n_plus_one_screenshots(tmp_path):
    assert preflight_screenshot_task(_task(tmp_path)) == {
        "actions": 1,
        "screenshots": 2,
    }

def test_accepts_zero_actions_with_one_initial_screenshot(tmp_path):
    root = _task(tmp_path, screenshots=1)
    (root / "web_surfer.log").write_text("")

    assert preflight_screenshot_task(root) == {
        "actions": 0,
        "screenshots": 1,
    }

def test_rejects_misaligned_screenshot_count(tmp_path):
    with pytest.raises(ValueError, match="exactly N\\+1"):
        preflight_screenshot_task(_task(tmp_path, screenshots=3))

def test_capture_gaps_are_explicit_and_own_available_states_are_never_dropped(tmp_path):
    root = _task(tmp_path, screenshots=3)
    (root / "web_surfer.log").write_text("\n".join(json.dumps({"action": "wait", "arguments": {}}) for _ in range(3)))
    for path in list(root.glob("screenshot*.png")):
        path.unlink()
    for index in (1, 3, 4):
        (root / f"screenshot{index}.png").write_bytes(b"png")
    (root / "final_answer.json").write_text(json.dumps({"final_answer": "done", "screenshots": ["screenshot1.png", "screenshot3.png", "screenshot4.png"]}))
    (root / "task_data.json").write_text(json.dumps({"evaluation_context": {"expected_state_ids": [1, 2, 3, 4], "format_gaps": {"screenshot": [2]}, "navigation_states": [3]}}))
    receipt = preflight_screenshot_task(root)
    assert receipt["available_state_ids"] == [1, 3, 4]
    assert receipt["missing_states"] == [2]
    assert receipt["navigation_states"] == [3]
    (root / "screenshot2.png").write_bytes(b"available")
    with pytest.raises(ValueError, match="capture gaps"):
        preflight_screenshot_task(root)

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
@pytest.mark.parametrize("status", ["success", "failure"])
def test_conversion_preserves_every_state_and_source(recording_factory, tmp_path, mode, status):
    source = recording_factory(mode=mode, status=status)
    before = digest(source)
    recording = prepare.inspect_recording(source)
    exported = prepare.prepare_recording(recording, tmp_path / "inputs")
    ss, dom = Path(exported["screenshot_task"]), Path(exported["dom_task"])
    for state in recording["manifest"]["states"]:
        index = state["state"]
        for root, original, projected in ((ss, "screenshot.png", f"screenshot{index}.png"), (dom, "dom_model.txt", f"dom_model{index}.txt")):
            assert (root / projected).read_bytes() == (source / state["artifacts"][original]["path"]).read_bytes()
    assert (ss / "web_surfer.log").read_bytes() == (dom / "web_surfer.log").read_bytes()
    assert not list(dom.rglob("*.png"))
    left, right = [json.loads((path / "task_data.json").read_text())[0] for path in (ss, dom)]
    assert left == right
    assert left["evaluation_context"]["recording_sha256"] == recording["recording_sha256"]
    assert left["evaluation_context"]["actor_arm"] == mode
    for root in (ss, dom):
        answer = json.loads((root / "final_answer.json").read_text())
        assert answer["final_answer"] == "The recorded answer."
        assert answer["token_usage"] == {}
        assert ("screenshots" in answer) == (root == ss)
    assert digest(source) == before
    immutable = digest(Path(exported["output"]))
    with pytest.raises(ValueError, match="already exists"):
        prepare.prepare_recording(recording, tmp_path / "inputs")
    assert digest(Path(exported["output"])) == immutable

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("actions,keyboard", [(0, False), (1, True)])
def test_zero_action_and_keyboard_trajectories(recording_factory, tmp_path, actions, keyboard):
    source = recording_factory(actions=actions, keyboard=keyboard)
    exported = prepare.prepare_recording(prepare.inspect_recording(source), tmp_path / "inputs")
    for field, glob in (("screenshot_task", "screenshot*.png"), ("dom_task", "dom_model*.txt")):
        assert len(list(Path(exported[field]).glob(glob))) == actions + 1
    logs = [Path(exported[field]) / "web_surfer.log" for field in ("screenshot_task", "dom_task")]
    assert logs[0].read_bytes() == logs[1].read_bytes()
    if keyboard:
        action = json.loads(logs[0].read_text())
        assert action["arguments"]["text"] == "recorded"
        assert "ref" not in action["arguments"]

@pytest.mark.usefixtures("no_network")
def test_dry_run_checks_without_publishing(recording_factory, tmp_path, capsys):
    source = recording_factory()
    output = tmp_path / "inputs"
    before = digest(source)
    capsys.readouterr()
    assert prepare.main([str(source), str(output), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["status"] == "valid"
    assert not output.exists() and digest(source) == before

@pytest.mark.usefixtures("no_network")
def test_duplicate_attempts_are_retained_not_silently_selected(recording_factory, tmp_path):
    first, second = recording_factory("first"), recording_factory("second")
    output = tmp_path / "inputs"
    assert prepare.main([str(first.parent.parent), str(output)]) == 0
    tasks = list(output.rglob("data-dom/task1"))
    assert len(tasks) == 2
    assert {json.loads((path / "task_data.json").read_text())[0]["evaluation_context"]["trial_id"] for path in tasks} == {"first", "second"}

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("case", ["artifact", "count", "pending", "changed_action"])
def test_invalid_evidence_is_rejected_not_repaired(recording_factory, tmp_path, case):
    source = recording_factory()
    if case == "artifact":
        path = source / "steps/step_001/dom_model.txt"; path.write_text(path.read_text() + "Unrecorded fact")
    elif case == "count":
        path = source / "manifest.json"; value = json.loads(path.read_text()); value["model_turns"] += 1; write_json(path, value)
    elif case == "pending":
        write_json(source / "steps/step_002/action.json", {})
    else:
        path = source / "steps/step_001/action.json"; value = json.loads(path.read_text()); value["action"]["id"] = "e2"; write_json(path, value)
    before = digest(source)
    with pytest.raises(ValueError):
        prepare.main([str(source), str(tmp_path / "inputs")])
    assert digest(source) == before

@pytest.mark.usefixtures("no_network")
def test_overlapping_paths_and_changed_source_are_protected(recording_factory, tmp_path):
    source = recording_factory()
    with pytest.raises(ValueError, match="outside"):
        prepare.main([str(source), str(source / "inputs")])
    recording = prepare.inspect_recording(source)
    path = source / "steps/step_001/dom_model.txt"
    path.write_text(path.read_text() + "Changed after inspection")
    with pytest.raises(ValueError, match="changed during export"):
        prepare.prepare_recording(recording, tmp_path / "inputs")

@pytest.mark.usefixtures("no_network")
def test_execution_targets_are_preserved_without_fabricating_coordinates(recording_factory, tmp_path):
    for mode in ("dom", "screenshot"):
        source = recording_factory(mode, mode=mode)
        before = digest(source)
        exported = prepare.prepare_recording(prepare.inspect_recording(source), tmp_path / "inputs")
        action = json.loads((Path(exported["dom_task"]) / "web_surfer.log").read_text())["arguments"]
        if mode == "dom":
            assert action["ref"] == "e1" and "coordinate" not in action
        else:
            assert action["coordinate"] == [14, 15] and "ref" not in action
        assert digest(source) == before

@pytest.mark.usefixtures("no_network")
def test_external_evidence_symlink_is_rejected(recording_factory, tmp_path):
    source = recording_factory()
    outside = tmp_path / "outside.txt"; outside.write_text("unrelated evidence")
    evidence = source / "steps/step_001/dom_model.txt"
    evidence.unlink(); evidence.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes|forbidden"):
        prepare.inspect_recording(source)

@pytest.mark.usefixtures("no_network")
def test_shared_action_projection_withholds_actor_notes_and_dom_target_descriptions(recording_factory, tmp_path):
    from w8bench.verifier.audit_evidence import verifier_action_history, shared_trajectory_payload
    source = recording_factory()
    manifest = json.loads((source / "manifest.json").read_text())
    step = manifest["steps"][0]
    step["thought"] = "DOM_DERIVED_PRIVATE_ACTOR_NOTE"
    step["target"] = {"ref": "e1", "role": "button", "name": "DOM_DERIVED_PRIVATE_TARGET"}
    write_json(source / "steps/step_001/action.json", step)
    write_json(source / "manifest.json", manifest)
    exported = prepare.prepare_recording(prepare.inspect_recording(source), tmp_path / "inputs")
    roots = [Path(exported[key]) for key in ("screenshot_task", "dom_task")]
    histories = [verifier_action_history(root) for root in roots]
    assert histories[0] == histories[1]
    assert "DOM_DERIVED_PRIVATE" not in histories[0]
    assert '"ref": "e1"' in histories[0]
    for root in roots:
        event = json.loads((root / "web_surfer.log").read_text())
        assert event["arguments"]["thoughts"] == ""
        assert "target" not in event["arguments"]
    assert "DOM_DERIVED_PRIVATE" not in json.dumps(shared_trajectory_payload(*roots))

@pytest.mark.usefixtures("no_network")
def test_missing_url_metadata_warns_without_excluding_complete_paired_state(recording_factory, tmp_path):
    from w8bench.verifier.audit_evidence import verifier_action_history, shared_trajectory_payload
    source = recording_factory()
    manifest = json.loads((source / "manifest.json").read_text())
    state = manifest["states"][0]
    state["capture"]["url_metadata_complete"] = False
    capture_path = source / state["directory"] / "capture.json"
    write_json(capture_path, state["capture"])
    state["artifacts"]["capture.json"]["sha256"] = hashlib.sha256(capture_path.read_bytes()).hexdigest()
    write_json(source / "manifest.json", manifest)
    recording = prepare.inspect_recording(source)
    coverage = recording["coverage"]
    assert 1 in coverage["audit_eligible_states"]
    assert coverage["states"][0]["eligible"] is True
    assert coverage["states"][0]["reasons"] == []
    assert coverage["states"][0]["metadata_warnings"] == ["observed_url_metadata_missing"]
    assert coverage["observed_url_timeline"][0] == {"state": 1, "url": None, "verified": False}
    exported = prepare.prepare_recording(recording, tmp_path / "inputs")
    roots = [Path(exported[field]) for field in ("screenshot_task", "dom_task")]
    history = [verifier_action_history(root) for root in roots]
    assert history[0] == history[1]
    assert "State 1: unavailable (not verified)" in history[0]
    payload = shared_trajectory_payload(*roots)
    assert 1 in payload["evaluation_context"]["audit_eligible_states"]
    assert payload["evaluation_context"]["observed_url_timeline"][0]["url"] is None

class TrajectoryExportTests(unittest.TestCase):
    def write_state(self, run_dir: Path, number: int, url: str) -> Path:
        state_dir = run_dir / "steps" / f"step_{number:03d}"
        state_dir.mkdir(parents=True)
        runner.write_json(
            state_dir / "dom.json",
            {"result": {"snapshot": {"url": url, "nodes": []}}},
        )
        (state_dir / "dom_model.txt").write_text("URL: " + url + "\n")
        return state_dir

    def write_action(self, state_dir: Path, number: int) -> dict[str, Any]:
        record: dict[str, Any] = {
            "state": number,
            "next_state": number + 1,
            "model_turn": number,
            "started_at": "2026-08-10T05:45:01.071Z",
            "completed_at": "2026-08-10T05:45:01.171Z",
            "action": {"action": "navigate", "url": "https://example.test/next"},
            "thought": "Open the public page.",
            "target": None,
            "coordinate_capture": None,
            "action_driver": "agent-browser",
            "action_result": {"success": True, "data": {}},
            "action_error": None,
            "action_succeeded": True,
        }
        runner.write_json(state_dir / "action.json", record)
        return record

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_export_uses_adjacent_states_without_duplicate_state_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            first = self.write_state(run_dir, 1, "https://example.test/start")
            self.write_state(run_dir, 2, "https://example.test/next")
            action = self.write_action(first, 1)
            manifest = {
                "task_id": "fixture",
                "status": "running", "observation_mode": "dom", "model_turns": 2,
                "states": [{"state": n, "directory": f"steps/step_{n:03d}",
                    "observation": f"steps/step_{n:03d}/dom_model.txt", "artifacts": {},
                    "capture": {"url_after": url}} for n, url in
                    [(1, "https://example.test/start"), (2, "https://example.test/next")]],
                "steps": [action],
            }
            final, report = runner.finalize_recording_artifacts(
                run_dir,
                manifest,
                {"status": "success", "run_status": "completed", "final_answer": "done"},
            )
            self.assertEqual(final["recorded_steps"], 1)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["captured_states"], 2)
            row = self.read_jsonl(run_dir / "trajectory.jsonl")[0]
            self.assertEqual(row["before_capture"]["url_after"], "https://example.test/start")
            self.assertEqual(row["after_capture"]["url_after"], "https://example.test/next")
            self.assertEqual(row["source_step"], "steps/step_001")
            self.assertEqual(row["next_step"], "steps/step_002")
            self.assertEqual(row["model_turn"], 1)
            self.assertEqual(row["execution_status"], "success")
            self.assertFalse((first / "before").exists())
            self.assertFalse((first / "after").exists())

    def test_error_before_first_action_writes_empty_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            manifest = {"task_id": "fixture", "status": "running", "observation_mode": "dom", "model_turns": 0, "states": [], "steps": []}
            final, report = runner.finalize_recording_artifacts(
                run_dir,
                manifest,
                {"status": "failure", "run_status": "error", "final_answer": "CDP connection failed"},
                manifest_status="error",
                error="CDP connection failed",
            )
            self.assertEqual(final["recorded_steps"], 0)
            self.assertEqual(report["status"], "incomplete")
            self.assertEqual((run_dir / "trajectory.jsonl").read_text(), "")
            self.assertEqual((run_dir / "web_surfer.log").read_text(), "")

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("mode,forbidden", [("dom", "extra.txt"), ("screenshot", "agent_browser_actions.txt")])
def test_inspector_rejects_forbidden_artifacts(run_pair, mode, forbidden):
    paths, *_ = run_pair
    (paths[mode] / "steps/step_001" / forbidden).write_text("contamination")
    with pytest.raises(ValueError, match="forbidden"):
        inspect_recording(paths[mode])

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_inspector_rejects_passive_observation_text_in_actor_request(run_pair, mode):
    paths, *_ = run_pair
    request = paths[mode] / "turns/turn_000001/request.json"
    payload = json.loads(request.read_text())
    payload["contents"][0]["parts"][0]["text"] += "\nPASSIVE_OBSERVATION_SECRET"
    write_json(request, payload)
    with pytest.raises(ValueError, match="unapproved|prompt|actor text"):
        inspect_recording(paths[mode])

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
    assert controls["judge_model"] == "gemini-3.1-pro-preview"
    assert controls["action_judge_model"] == "gemini-3.8-flash"
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


@pytest.mark.skipif(not __import__('os').environ.get('W8_CALIBRATION_CDP_URL'),
    reason="requires the local W8 browser and W8_CALIBRATION_CDP_URL")
def test_normalized_coordinate_calibration_in_w8(tmp_path):
    """Exercise real pointer input against known targets without model calls."""
    import io
    import os
    from urllib.parse import quote
    from PIL import Image
    from w8bench.task_recorder import capture
    from w8bench.task_recorder.agent_browser import AgentBrowserClient

    async def calibrate():
        viewport = (1365, 768)
        html = (Path(__file__).resolve().parents[1] / 'fixtures' / 'coordinate_calibration.html').read_text()
        receipts = []
        async with capture.CDPClient(os.environ['W8_CALIBRATION_CDP_URL'], observation_mode='screenshot',
                viewport=viewport) as cdp:
            try:
                await cdp.call('Page.navigate', {'url': 'data:text/html;charset=utf-8,' + quote(html)})
                await asyncio.sleep(0.2)
                metrics = await cdp.call('Runtime.evaluate', {'expression':
                    '({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})', 'returnByValue': True})
                assert metrics['result']['value'] == {'width': 1365, 'height': 768, 'dpr': 1}
                saved = await capture._capture_screenshot(cdp, tmp_path)
                with Image.open(io.BytesIO(saved.read_bytes())) as image:
                    assert image.size == viewport
                driver = AgentBrowserClient('unused', session='coordinate-calibration',
                    cdp_url=os.environ['W8_CALIBRATION_CDP_URL'], timeout=90)
                points = [('north-west', 0, 0), ('north-east', 1000, 0),
                    ('south-west', 0, 1000), ('south-east', 1000, 1000),
                    ('small', round(825 * 1000 / viewport[0]), round(358 * 1000 / viewport[1]))]
                for name, x, y in points:
                    result = await driver.execute({'action': 'click', 'x': x, 'y': y}, cdp=cdp, viewport=viewport)
                    hit = await cdp.call('Runtime.evaluate', {'expression': 'hitTargets.at(-1)', 'returnByValue': True})
                    assert hit['result']['value'] == name
                    receipts.append({'target': name, 'result': result, 'hit': hit['result']['value']})
                wheel = await driver.execute({'action': 'scroll', 'x': 500, 'y': 500, 'pixels': 1000},
                    cdp=cdp, viewport=viewport)
                await asyncio.sleep(0.2)
                position = await cdp.call('Runtime.evaluate', {'expression': 'scrollY', 'returnByValue': True})
                scroll_y = position['result']['value']
                assert 800 <= scroll_y <= 1200
                result = await driver.execute({'action': 'click', 'x': round(660 * 1000 / viewport[0]),
                    'y': round((1460 - scroll_y) * 1000 / viewport[1])}, cdp=cdp, viewport=viewport)
                hit = await cdp.call('Runtime.evaluate', {'expression': 'hitTargets.at(-1)', 'returnByValue': True})
                assert hit['result']['value'] == 'scrolled'
                receipts.append({'target': 'scrolled', 'scroll_y': scroll_y, 'wheel': wheel,
                    'result': result, 'hit': hit['result']['value']})
                target = Path(__file__).resolve().parents[2] / 'reports' / 'implementation_fixes' / 'calibration.json'
                write_json(target, {'viewport': list(viewport), 'device_pixel_ratio': 1,
                    'screenshot_sha256': hashlib.sha256(saved.read_bytes()).hexdigest(),
                    'hits': len(receipts), 'targets': len(points) + 1, 'receipts': receipts})
            finally:
                await cdp.close_owned_target_on_failure()
        return receipts
    assert len(asyncio.run(calibrate())) == 6


def test_verifier_history_uses_executed_css_coordinates():
    from w8bench.task_recorder.trajectory import websurfer_action
    record = {"action": {"action": "click", "x": 500, "y": 500}, "thought": "Click the button",
        "model_turn": 1, "state": 1, "action_succeeded": True,
        "model_coordinates": {"x": 500, "y": 500, "units": "normalized_1000"},
        "executed_coordinates": {"x": 682, "y": 384, "units": "css_pixels"}}
    _, arguments, _ = websurfer_action(record)
    assert (arguments['x'], arguments['y']) == (682, 384)
    events = prepare._verifier_events({"steps": [record]})
    assert events[0]['arguments']['coordinate'] == [682, 384]
    assert record['action'] == {"action": "click", "x": 500, "y": 500}
