import hashlib
import json
import pytest
from PIL import Image

from w8bench.task_recorder.trajectory import generate_trajectory_artifacts
from w8bench.verifier.prepare_dataset import main, prepare_recording
from w8bench.verifier import run_full_comparison
from w8bench.verifier.validate_inputs import dataset_only_preflight


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _recording(root, actions=2):
    root.mkdir(parents=True)
    _write(root / "task.json", {
        "task_id": root.name, "source_task_id": "browser_task_008",
        "instruction": "Read the recorded page.\nPreserve this instruction exactly.",
        "start_url": "https://example.test/0",
    })
    manifest = {"task_id": root.name, "states": [], "steps": []}
    for index in range(actions + 1):
        step = root / "steps" / f"step_{index + 1:03d}"
        url = f"https://example.test/{index}"
        _write(step / "dom.json", {"result": {"snapshot": {"url": url, "nodes": []}}})
        (step / "dom_model.txt").write_text(
            f"URL: {url}\nTitle: Recorded\nSnapshot: truncated=False\n=== VISIBLE CONTENT ===\nState {index}\n",
            encoding="utf-8",
        )
        # Equal pixels remain distinct state evidence and must never be deduplicated.
        Image.new("RGB", (3, 3), color="red").save(step / "screenshot.png")
        manifest["states"].append({
            "state": index + 1,
            "snapshot": f"steps/{step.name}/dom.json",
            "screenshot": f"steps/{step.name}/screenshot.png",
            "model_text": f"steps/{step.name}/dom_model.txt",
            "document_url": url,
        })
        if index < actions:
            action = {
                "step": index + 1,
                "action": {"action": "navigate", "url": f"https://example.test/{index + 1}"},
                "thought": f"Recorded thought {index + 1}",
                "started_at": f"2026-10-17T08:22:{index:02d}.000Z",
                "action_result": {"success": True}, "action_succeeded": True,
            }
            _write(step / "action.json", action)
            manifest["steps"].append(action)
    _write(root / "manifest.json", manifest)
    manifest["trajectory_export"] = generate_trajectory_artifacts(root)
    _write(root / "manifest.json", manifest)
    _write(root / "final.json", {
        "status": "failure", "run_status": "error", "recorded_steps": actions,
        "final_answer": "Exact recorded failure; do not invent a successful answer.\n",
    })
    return root


def _hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_converts_all_states_and_preserves_recorded_content(tmp_path):
    recording = _recording(tmp_path / "recording", actions=11)
    before = _hashes(recording)
    output = tmp_path / "dataset"
    receipt = prepare_recording(recording, output, "task_101")
    screenshot = output / "data-ss/task_101"
    dom = output / "data-dom/task_101"
    assert receipt["actions"] == 11
    assert receipt["states"] == 12
    assert receipt["source_status"] == "failure"
    task = json.loads((recording / "task.json").read_text())
    final = json.loads((recording / "final.json").read_text())
    for directory in (screenshot, dom):
        assert json.loads((directory / "final_answer.json").read_text()) == {"final_answer": final["final_answer"]}
        assert json.loads((directory / "task_data.json").read_text())[0]["confirmed_task"] == task["instruction"]
        assert (directory / "web_surfer.log").read_bytes() == (recording / "web_surfer.log").read_bytes()
    for index in range(12):
        source = recording / "steps" / f"step_{index + 1:03d}"
        assert (screenshot / f"screenshot{index}.png").read_bytes() == (source / "screenshot.png").read_bytes()
        assert (dom / f"dom_model{index}.txt").read_bytes() == (source / "dom_model.txt").read_bytes()
    assert len(list(screenshot.glob("*.png"))) == 12
    assert not list(dom.rglob("*.png"))
    assert not list(output.rglob("*rubric*"))
    assert dataset_only_preflight(screenshot, dom)["actions"] == 11
    assert _hashes(recording) == before
    mapping = json.loads((output / "preparation/task_101.json").read_text())["states_mapping"]
    assert mapping[10]["screenshot_source"] == "steps/step_011/screenshot.png"


@pytest.mark.parametrize("damage", ["missing_frame", "stale_log", "state_gap", "missing_answer"])
def test_rejects_incomplete_or_inconsistent_sources_before_writing(tmp_path, damage):
    recording = _recording(tmp_path / "recording")
    if damage == "missing_frame":
        (recording / "steps/step_002/screenshot.png").unlink()
    elif damage == "stale_log":
        log = recording / "web_surfer.log"
        rows = [json.loads(line) for line in log.read_text().splitlines()]
        rows[0]["arguments"]["url"] = "https://wrong.test"
        log.write_text("".join(json.dumps(row) + "\n" for row in rows))
    elif damage == "state_gap":
        (recording / "steps/step_002").rename(recording / "steps/step_012")
    else:
        _write(recording / "final.json", {"recorded_steps": 2})
    before = _hashes(recording)
    output = tmp_path / "dataset"
    with pytest.raises((ValueError, OSError)):
        prepare_recording(recording, output, "task_01")
    assert not output.exists()
    assert _hashes(recording) == before


def test_does_not_replace_existing_tasks_or_rubrics(tmp_path):
    recording = _recording(tmp_path / "recording")
    output = tmp_path / "dataset"
    existing = output / "data-dom/task_01/task_data_with_canonical_rubric.json"
    _write(existing, {"leave": "unchanged"})
    before = _hashes(output)
    with pytest.raises(ValueError, match="overwrite"):
        prepare_recording(recording, output, "task_01")
    assert _hashes(output) == before


def test_zero_actions_still_retains_initial_evidence(tmp_path):
    recording = _recording(tmp_path / "recording", actions=0)
    result = prepare_recording(recording, tmp_path / "dataset", "task_01")
    assert result["actions"] == 0
    assert result["states"] == 1


def test_batch_reports_recordings_with_no_captured_states(tmp_path, capsys):
    recordings = tmp_path / "recordings"
    _recording(recordings / "a-complete")
    missing = recordings / "b-no-captures"
    missing.mkdir()
    _write(missing / "task.json", {"instruction": "Read", "start_url": "https://example.test"})
    _write(missing / "manifest.json", {"trajectory_export": {"status": "complete"}})
    _write(missing / "final.json", {"final_answer": "Connection failed"})
    (missing / "trajectory.jsonl").touch()
    (missing / "web_surfer.log").touch()
    assert main(["--recordings-dir", str(recordings), "--output-dir", str(tmp_path / "dataset")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["prepared"][0]["task"] == "task_01"
    assert "no captured states" in report["failed"][0]["error"]


def test_prepared_task_can_be_selected_without_a_hosted_copy(tmp_path, monkeypatch, capsys):
    recording = _recording(tmp_path / "recording")
    output = tmp_path / "dataset"
    prepare_recording(recording, output, "task_101")
    monkeypatch.setattr(run_full_comparison, "DEFAULT_DATASET_ROOT", output)

    def unexpected_download(**kwargs):
        pytest.fail("An existing local recording must not require a hosted task")

    monkeypatch.setattr(run_full_comparison, "fetch_trajectories", unexpected_download)
    assert run_full_comparison.main(["--task", "task_101"]) == 0
    assert '"status": "resolved_from_local_dataset"' in capsys.readouterr().out
