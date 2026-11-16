from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from w8bench.task_recorder import prepare_verifier_data as prepare, runner
from w8bench.task_recorder.agent_browser import AgentBrowserClient, AgentBrowserObservation
from w8bench.task_recorder.recorder_support import write_json
from tests.turn_benchmark.test_modes import FakeCDP, no_network


def digest(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def recording_factory(tmp_path, monkeypatch, no_network):
    monkeypatch.setenv("RUNNER_BROWSER_PROFILE_PROVENANCE", json.dumps({
        "container_id": "offline", "container_created_at": "fixture", "profile_fresh_at_run_start": True,
        "tasks_previously_run_in_container": 0, "browser_build": {"image_id": "offline"},
        "browser_environment": {"LANG": "en_US.UTF-8"}}))
    monkeypatch.setattr(runner, "CDPClient", FakeCDP)
    monkeypatch.setattr(runner, "synchronize_recorder_target", AsyncMock(return_value={}))
    monkeypatch.setattr(AgentBrowserClient, "connect", AsyncMock())
    monkeypatch.setattr(AgentBrowserClient, "close", AsyncMock())
    monkeypatch.setattr(AgentBrowserClient, "_invoke", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(AgentBrowserClient, "snapshot", AsyncMock(return_value=AgentBrowserObservation(
        text='- button "Save" [ref=e1]', refs=frozenset({"e1"}), origin="fixture", command=("snapshot", "-i"),
        targets={"e1": {"role": "button", "name": "Save"}})))
    def make(name="run", *, status="success", actions=1, keyboard=False, mode="dom"):
        queue = [{"action": "type", "text": "recorded", "thought": "Type into focused control"} if keyboard else
                 {"action": "click", **({"id": "e1"} if mode == "dom" else {"x": 10, "y": 20}), "thought": "Inspect"}
                 for _ in range(actions)]
        status = status if actions else "failure"
        queue.append({"action": "terminate", "status": status, "termination_reason": "completed" if status == "success" else "blocked",
            "final_answer": "The recorded answer.", "thought": "Finished"})
        def post(self, payload):
            return {"model": "gemini-3.1-pro-preview", "output_text": json.dumps(queue.pop(0)),
                "usage": {"input_tokens": 20, "output_tokens": 10}}
        monkeypatch.setattr(runner.ModelClient, "_post", post)
        output = tmp_path / "recordings" / name
        args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
            "--task", "Inspect the example page.", "--task-id", name, "--source-task-id", "task1",
            "--start-url", "https://example.test/", "--output-dir", str(output), "--run-name", name,
            "--model", "gemini-3.1-pro-preview", "--api-key", "offline", "--max-turns", str(actions + 2), "--settle-seconds", "0"])
        assert asyncio.run(runner.run(args)) in {0, 2}
        return output / name
    return make


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


def test_dry_run_checks_without_publishing(recording_factory, tmp_path, capsys):
    source = recording_factory()
    output = tmp_path / "inputs"
    before = digest(source)
    capsys.readouterr()
    assert prepare.main([str(source), str(output), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["status"] == "valid"
    assert not output.exists() and digest(source) == before


def test_duplicate_attempts_are_retained_not_silently_selected(recording_factory, tmp_path):
    first, second = recording_factory("first"), recording_factory("second")
    output = tmp_path / "inputs"
    assert prepare.main([str(first.parent.parent), str(output)]) == 0
    tasks = list(output.rglob("data-dom/task1"))
    assert len(tasks) == 2
    assert {json.loads((path / "task_data.json").read_text())[0]["evaluation_context"]["trial_id"] for path in tasks} == {"first", "second"}


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


def test_overlapping_paths_and_changed_source_are_protected(recording_factory, tmp_path):
    source = recording_factory()
    with pytest.raises(ValueError, match="outside"):
        prepare.main([str(source), str(source / "inputs")])
    recording = prepare.inspect_recording(source)
    path = source / "steps/step_001/dom_model.txt"
    path.write_text(path.read_text() + "Changed after inspection")
    with pytest.raises(ValueError, match="changed during export"):
        prepare.prepare_recording(recording, tmp_path / "inputs")


def test_execution_targets_are_preserved_without_fabricating_coordinates(recording_factory, tmp_path):
    for mode in ("dom", "screenshot"):
        source = recording_factory(mode, mode=mode)
        before = digest(source)
        exported = prepare.prepare_recording(prepare.inspect_recording(source), tmp_path / "inputs")
        action = json.loads((Path(exported["dom_task"]) / "web_surfer.log").read_text())["arguments"]
        if mode == "dom":
            assert action["ref"] == "e1" and "coordinate" not in action
        else:
            assert action["coordinate"] == [10, 20] and "ref" not in action
        assert digest(source) == before


def test_external_evidence_symlink_is_rejected(recording_factory, tmp_path):
    source = recording_factory()
    outside = tmp_path / "outside.txt"; outside.write_text("unrelated evidence")
    evidence = source / "steps/step_001/dom_model.txt"
    evidence.unlink(); evidence.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes|forbidden"):
        prepare.inspect_recording(source)


def test_shared_action_projection_withholds_actor_notes_and_dom_target_descriptions(recording_factory, tmp_path):
    from w8bench.verifier.evidence_audit import verifier_action_history, shared_trajectory_payload
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


def test_missing_url_metadata_warns_without_excluding_complete_paired_state(recording_factory, tmp_path):
    from w8bench.verifier.evidence_audit import verifier_action_history, shared_trajectory_payload
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
