from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image
import pytest

from w8bench.task_recorder import prepare_verifier_data as prepare
from w8bench.task_recorder.recorder_support import write_json
from w8bench.task_recorder.trajectory import generate_trajectory_artifacts


def digest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def recording_factory(tmp_path):
    def make(name="run", *, status="success", run_status=None, actions=1, keyboard=False):
        root = tmp_path / "recordings" / name
        root.mkdir(parents=True)
        task = {"task_id": name, "source_task_id": "task1",
                "instruction": "Inspect the example page.", "start_url": "https://example.test/"}
        write_json(root / "task.json", task)
        state_metadata, action_records = [], []
        for i in range(1, actions + 2):
            state = root / "steps" / f"step_{i:03d}"
            write_json(state / "dom.json", {"result": {"snapshot": {
                "url": task["start_url"], "nodes": []}}})
            (state / "dom_model.txt").write_text(
                "URL: https://example.test/\nTitle: Example\n=== VISIBLE CONTENT ===\n"
                "A recorded fact: café \U0001f680.\n", encoding="utf-8")
            Image.new("RGB", (2, 2), "white").save(state / "screenshot.png")
            state_metadata.append({"state": i, "document_url": task["start_url"]})
            if i <= actions:
                action = {"started_at": f"2026-01-01T00:00:{i:02d}Z",
                          "thought": "Inspect the page through the interface.",
                          "action": {"action": "type", "text": "recorded"} if keyboard else
                                    {"action": "navigate", "url": task["start_url"]},
                          "action_result": {"success": True}, "action_succeeded": True,
                          "action_error": None}
                write_json(state / "action.json", action)
                action_records.append(action)
        final = {"status": status, "final_answer": "The recorded answer.",
                 "recorded_steps": actions}
        if run_status:
            final["run_status"] = run_status
        manifest = {"task_id": name, "status": "error" if run_status else status,
                    "states": state_metadata, "steps": action_records, "final": final}
        write_json(root / "final.json", final)
        write_json(root / "manifest.json", manifest)
        manifest["trajectory_export"] = generate_trajectory_artifacts(root)
        write_json(root / "manifest.json", manifest)
        return root
    return make


@pytest.mark.parametrize("status,run_status", [("success", None), ("failure", None),
                                              ("failure", "error")])
def test_conversion_preserves_every_state_and_source(recording_factory, tmp_path, status, run_status):
    source = recording_factory(status=status, run_status=run_status)
    before = digest(source)
    output = tmp_path / "trajectories"
    assert prepare.main([str(source), str(output)]) == 0
    for i, state in enumerate(sorted((source / "steps").iterdir())):
        assert (output / "data-dom/task_01" / f"dom_model{i}.txt").read_bytes() == (state / "dom_model.txt").read_bytes()
        assert (output / "data-ss/task_01" / f"screenshot{i}.png").read_bytes() == (state / "screenshot.png").read_bytes()
    for side in ("data-dom", "data-ss"):
        root = output / side / "task_01"
        assert (root / "web_surfer.log").read_bytes() == (source / "web_surfer.log").read_bytes()
        answer = json.loads((root / "final_answer.json").read_text())
        assert answer["final_answer"] == "The recorded answer."
        assert answer["token_usage"] == {}
        assert ("screenshots" in answer) == (side == "data-ss")
    assert not list((output / "data-dom").rglob("*.png"))
    report = json.loads((output / "preparation_report.json").read_text())
    assert report["prepared_count"] == 1 and report["excluded_count"] == 0
    assert report["prepared"][0]["recorded_status"] == status
    assert report["prepared"][0]["run_status"] == run_status
    assert report["prepared"][0]["source_sha256"]["task.json"] == before["task.json"]
    assert digest(source) == before
    derived = digest(output)
    assert prepare.main([str(source), str(output)]) == 0
    assert digest(output) == derived
    # Relative provenance must still work after moving a whole collection.
    moved = tmp_path / "moved"
    shutil.copytree(source.parent, moved / "recordings")
    shutil.copytree(output, moved / "trajectories")
    assert prepare.main([str(moved / "recordings" / source.name),
                         str(moved / "trajectories")]) == 0
    assert digest(moved / "trajectories") == derived


@pytest.mark.parametrize("actions,keyboard", [(0, False), (1, True)])
def test_zero_action_and_keyboard_trajectories(recording_factory, tmp_path, actions, keyboard):
    source = recording_factory(actions=actions, keyboard=keyboard)
    output = tmp_path / "inputs"
    assert prepare.main([str(source), str(output)]) == 0
    assert len(list((output / "data-dom/task_01").glob("dom_model*.txt"))) == actions + 1


def test_mixed_batch_reports_exclusion_and_keeps_valid_failure(recording_factory, tmp_path):
    valid = recording_factory("valid", status="failure")
    invalid = recording_factory("invalid")
    task = json.loads((invalid / "task.json").read_text())
    task["source_task_id"] = "task2"
    write_json(invalid / "task.json", task)
    png = (invalid / "steps/step_002/screenshot.png").read_bytes()
    (invalid / "steps/step_002/screenshot.png").unlink()
    before = digest(valid.parent)
    output = tmp_path / "inputs"
    assert prepare.main([str(valid.parent), str(output)]) == 1
    report = json.loads((output / "preparation_report.json").read_text())
    assert report["selected_recordings"] == 2
    assert report["prepared_count"] == report["excluded_count"] == 1
    assert (output / report["prepared"][0]["source"]).resolve() == valid
    assert (output / report["excluded"][0]["source"]).resolve() == invalid
    assert not Path(report["prepared"][0]["source"]).is_absolute()
    assert not Path(report["source_root"]).is_absolute()
    assert digest(valid.parent) == before
    existing = {side: digest(output / side / "task_01") for side in ("data-ss", "data-dom")}
    (invalid / "steps/step_002/screenshot.png").write_bytes(png)
    assert prepare.main([str(valid.parent), str(output)]) == 0
    report = json.loads((output / "preparation_report.json").read_text())
    assert report["prepared_count"] == 2 and report["excluded_count"] == 0
    for side in existing:
        assert digest(output / side / "task_01") == existing[side]
        assert (output / side / "task_02").is_dir()
    changed = output / "data-dom/task_01/dom_model0.txt"
    changed.write_text(changed.read_text() + "Altered after preparation.\n")
    with pytest.raises(ValueError, match="Existing verifier inputs changed"):
        prepare.main([str(valid.parent), str(output)])


def test_dry_run_checks_full_conversion_without_publishing(recording_factory, tmp_path, capsys):
    source = recording_factory()
    output = tmp_path / "inputs"
    assert prepare.main([str(source), str(output), "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] and report["prepared_count"] == 1
    assert not output.exists()


def test_duplicate_attempts_are_retained_not_silently_selected(recording_factory, tmp_path):
    first = recording_factory("first")
    recording_factory("second")
    output = tmp_path / "inputs"
    assert prepare.main([str(first.parent), str(output)]) == 0
    assert {p.name for p in (output / "data-dom").iterdir()} == {"task_01-first", "task_01-second"}


@pytest.mark.parametrize("case", ["url", "count", "pending", "changed_action"])
def test_invalid_evidence_is_reported_not_repaired(recording_factory, tmp_path, case):
    source = recording_factory()
    if case == "url":
        path = source / "steps/step_001/dom_model.txt"
        path.write_text(path.read_text().replace("https://example.test/", "https://other.test/"))
    elif case == "count":
        (source / "web_surfer.log").write_text("")
    elif case == "pending":
        (source / "steps/step_002/action.json").write_text("{}")
    else:
        path = source / "steps/step_001/action.json"
        data = json.loads(path.read_text()); data["action"]["url"] = "https://other.test/"
        write_json(path, data)
    before = digest(source)
    output = tmp_path / "inputs"
    assert prepare.main([str(source), str(output)]) == 1
    assert json.loads((output / "preparation_report.json").read_text())["prepared_count"] == 0
    assert digest(source) == before


def test_existing_output_and_overlapping_paths_are_protected(recording_factory, tmp_path):
    source = recording_factory()
    output = tmp_path / "inputs"; output.mkdir()
    with pytest.raises(ValueError, match="overwrite"):
        prepare.main([str(source), str(output)])
    with pytest.raises(ValueError, match="overlap"):
        prepare.main([str(source), str(source / "inputs")])


def test_changed_source_is_not_copied(recording_factory, tmp_path):
    source = recording_factory()
    recording = prepare.inspect_recording(source)
    with (source / "steps/step_001/dom_model.txt").open("a") as stream:
        stream.write("Changed after inspection\n")
    with pytest.raises(ValueError, match="changed after inspection"):
        prepare.prepare_recording(recording, tmp_path / "stage")


def test_coordinate_provenance_is_report_only_and_logs_remain_unchanged(recording_factory, tmp_path):
    source = recording_factory()
    action_path = source / "steps/step_001/action.json"
    action = json.loads(action_path.read_text())
    action["action"] = {"action": "click", "id": "e1"}
    action["target"] = {"ref": "e1", "role": "button", "name": "Save"}
    capture = {"status": "resolved", "coordinate_source": "structured_snapshot_bounds",
               "coordinate": [10, 20], "phase": "pre_action"}
    action["coordinate_capture"] = capture
    write_json(action_path, action)
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["steps"] = [action]
    manifest["trajectory_export"] = generate_trajectory_artifacts(source)
    write_json(source / "manifest.json", manifest)
    before = digest(source)
    output = tmp_path / "inputs"
    assert prepare.main([str(source), str(output)]) == 0
    report = json.loads((output / "preparation_report.json").read_text())
    assert "not exact pointer-event" in report["coordinate_semantics"]
    assert report["prepared"][0]["coordinate_provenance"] == [{
        "action_number": 1, "action_record": "steps/step_001/action.json",
        "coordinate_capture": capture,
    }]
    for side in ("data-ss", "data-dom"):
        root = output / side / "task_01"
        assert (root / "web_surfer.log").read_bytes() == (source / "web_surfer.log").read_bytes()
        event = json.loads((root / "web_surfer.log").read_text())
        assert event["arguments"]["coordinate"] == [10, 20]
        assert event["arguments"]["target"] == action["target"]
        assert "coordinate_provenance" not in event
        assert not (root / "preparation_report.json").exists()
    assert digest(source) == before


def test_external_evidence_symlink_is_rejected(recording_factory, tmp_path):
    source = recording_factory()
    outside = tmp_path / "outside.txt"; outside.write_text("unrelated evidence")
    evidence = source / "steps/step_001/dom_model.txt"
    evidence.unlink(); evidence.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        prepare.inspect_recording(source)
