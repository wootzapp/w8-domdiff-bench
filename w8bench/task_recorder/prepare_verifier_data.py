"""Convert recorder runs into paired screenshot and DOM verifier datasets.

Usage: python -m w8bench.task_recorder.prepare_verifier_data RECORDINGS OUTPUT
   or: python w8bench/task_recorder/prepare_verifier_data.py RECORDINGS OUTPUT
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from w8bench.screenshot_verifier.trajectory import Trajectory
from w8bench.screenshot_verifier.utils.preflight import preflight_screenshot_task
from w8bench.verifier.validate_inputs import dataset_only_preflight

from w8bench.task_recorder.recorder_support import RunnerError, write_json
from w8bench.task_recorder.trajectory import snapshot_url, step_directory_number, websurfer_action


@dataclass
class Recording:
    source: Path
    alias: str
    task: dict[str, Any]
    final: dict[str, Any]
    states: list[Path]
    actions: int


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def read_events(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object: {path}:{number}")
        rows.append(value)
    return rows


def inspect_recording(source: Path) -> Recording:
    """Check source metadata, executed actions, and all corresponding states."""
    task = read_object(source / "task.json")
    manifest = read_object(source / "manifest.json")
    final = read_object(source / "final.json")
    for field in ("task_id", "instruction", "start_url"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise ValueError(f"{source}: task.json needs non-empty {field}")
    if manifest.get("task_id") != task["task_id"]:
        raise ValueError(f"{source}: task and manifest IDs differ")
    if manifest.get("status") not in {"success", "failure"}:
        raise ValueError(f"{source}: recording is unfinished, interrupted, or errored")
    if final.get("status") not in {"success", "failure"} or not isinstance(
        final.get("final_answer"), str
    ):
        raise ValueError(f"{source}: final.json needs a completed status and final_answer text")
    if final.get("run_status") in {"interrupted", "error"} or manifest.get("interruption"):
        raise ValueError(f"{source}: interrupted or errored recordings cannot be prepared")
    if manifest.get("final") != final:
        raise ValueError(f"{source}: final.json differs from the manifest's final result")
    if manifest["status"] != final["status"]:
        raise ValueError(f"{source}: final and manifest completion statuses differ")
    if "is_aborted" in final and not isinstance(final["is_aborted"], bool):
        raise ValueError(f"{source}: is_aborted must be a boolean")
    export = manifest.get("trajectory_export")
    if not isinstance(export, dict) or export.get("status") != "complete" or export.get("errors"):
        raise ValueError(f"{source}: trajectory export is incomplete or invalid")
    if export.get("skipped"):
        raise ValueError(f"{source}: skipped human-intervention states need separate preparation")

    trajectory = read_events(source / "trajectory.jsonl")
    events = read_events(source / "web_surfer.log")
    count = len(trajectory)
    states = sorted((source / "steps").iterdir(), key=step_directory_number)
    if [step_directory_number(path) for path in states] != list(range(1, count + 2)):
        raise ValueError(f"{source}: N actions require contiguous step_001 through step_{count + 1:03d}")
    if (
        len(events) != count
        or len(manifest.get("steps", [])) != count
        or final.get("recorded_steps") != count
        or export.get("exported_actions") != count
        or export.get("captured_states") != len(states)
    ):
        raise ValueError(f"{source}: action/state counts disagree across source artifacts")
    recorded_states = manifest.get("states", [])
    if [row.get("state") for row in recorded_states] != list(range(1, count + 2)):
        raise ValueError(f"{source}: manifest state sequence differs from captured steps")

    urls = []
    for state, metadata in zip(states, recorded_states):
        url = snapshot_url(state / "dom.json")
        text = (state / "dom_model.txt").read_text(encoding="utf-8")
        dom_url = next((line[4:].strip() for line in text.splitlines() if line.startswith("URL:")), "")
        if dom_url != url or metadata.get("document_url") != url:
            raise ValueError(f"{state}: snapshot, DOM text, and manifest URLs differ")
        with Image.open(state / "screenshot.png") as screenshot:
            if screenshot.format != "PNG":
                raise ValueError(f"{state}: screenshot.png is not a PNG image")
            screenshot.verify()
        urls.append(url)

    for index, (row, event) in enumerate(zip(trajectory, events)):
        action_record = read_object(states[index] / "action.json")
        action, arguments, _thought = websurfer_action(action_record)
        expected = {
            "action_number": index + 1,
            "source_step": states[index].name,
            "next_step": states[index + 1].name,
            "state_url": urls[index],
            "next_state_url": urls[index + 1],
            "action": action,
            "arguments": arguments,
            "timestamp": action_record.get("started_at"),
        }
        for key, value in expected.items():
            if row.get(key) != value:
                raise ValueError(f"{source}: trajectory action {index + 1} disagrees with capture for {key}")
        for key in ("action", "arguments", "timestamp", "execution_status"):
            if event.get(key) != row.get(key):
                raise ValueError(f"{source}: WebSurfer action {index + 1} differs for {key}")
        if event.get("url") != urls[index + 1]:
            raise ValueError(f"{source}: WebSurfer action {index + 1} has the wrong after-URL")
    if (states[-1] / "action.json").exists():
        raise ValueError(f"{source}: final state has an action without an after-state")

    source_id = str(task.get("source_task_id") or task["task_id"])
    numeric = re.fullmatch(r"(?:browser_)?task[_-]?(\d+)", source_id)
    alias = f"task_{int(numeric.group(1)):02d}" if numeric else source.name
    return Recording(source, alias, task, final, states, count)


def copy_evidence(source: Path, destination: Path) -> None:
    """Keep every physical state, including repeated images, byte-for-byte."""
    expected = hashlib.sha256(source.read_bytes()).digest()
    shutil.copyfile(source, destination)
    if hashlib.sha256(destination.read_bytes()).digest() != expected:
        raise ValueError(f"Evidence changed while copying: {source}")


def prepare_recording(recording: Recording, staging: Path) -> dict[str, Any]:
    screenshot = staging / "data-ss" / recording.alias
    dom = staging / "data-dom" / recording.alias
    screenshot.mkdir(parents=True)
    dom.mkdir(parents=True)
    task_data = [{
        "task_id": recording.task["task_id"],
        "confirmed_task": recording.task["instruction"],
        "website": recording.task["start_url"],
        "level": "recorded_browser_task",
    }]
    answer = {
        "final_answer": recording.final["final_answer"],
        "env_state_json": "<no_answer>",
        "env_state_raw": "<no_answer>",
        "is_aborted": recording.final.get("is_aborted", False),
        "is_rel_paths": True,
        "token_usage": {},
    }
    for root in (screenshot, dom):
        write_json(root / "task_data.json", task_data)
        copy_evidence(recording.source / "web_surfer.log", root / "web_surfer.log")
    write_json(dom / "final_answer.json", answer)
    write_json(screenshot / "final_answer.json", {
        **answer,
        "screenshots": [f"screenshot{index}.png" for index in range(len(recording.states))],
    })
    for index, state in enumerate(recording.states):
        copy_evidence(state / "screenshot.png", screenshot / f"screenshot{index}.png")
        copy_evidence(state / "dom_model.txt", dom / f"dom_model{index}.txt")

    receipt = dataset_only_preflight(screenshot, dom)
    preflight_screenshot_task(screenshot)
    if Trajectory.from_folder(screenshot) is None:
        raise ValueError(f"Screenshot trajectory parser could not load {screenshot}")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Recordings directory or a single recorded run")
    parser.add_argument("output_dir", type=Path, help="Destination for data-ss/ and data-dom/")
    parser.add_argument("--dry-run", action="store_true", help="Inspect sources and destinations without writing")
    args = parser.parse_args(argv)
    source = args.input_dir.resolve(strict=True)
    output = args.output_dir.resolve()
    if not source.is_dir():
        raise ValueError(f"Input is not a directory: {source}")
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Input and output directories must not overlap")
    runs = [source] if (source / "task.json").is_file() else sorted(
        path for path in source.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    if not runs:
        raise ValueError(f"No recordings found: {source}")
    recordings = [inspect_recording(run) for run in runs]
    counts = Counter(recording.alias for recording in recordings)
    for recording in recordings:
        if counts[recording.alias] > 1:
            recording.alias = f"{recording.alias}-{recording.source.name}"
    aliases = [recording.alias for recording in recordings]
    if len(set(aliases)) != len(aliases):
        raise ValueError("Recordings map to duplicate output task names")
    for alias in aliases:
        for modality in ("data-ss", "data-dom"):
            target = output / modality / alias
            if target.exists() or target.is_symlink():
                raise ValueError(f"Refusing to overwrite existing task: {target}")
    if args.dry_run:
        for recording in recordings:
            print(
                f"{recording.source} -> {output}/{{data-ss,data-dom}}/{recording.alias} "
                f"(actions={recording.actions}, states={len(recording.states)})"
            )
        return 0

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-verifier-", dir=output) as name:
        staging = Path(name)
        receipts = [prepare_recording(recording, staging) for recording in recordings]
        created = []
        try:
            for alias in aliases:
                for modality in ("data-ss", "data-dom"):
                    target = output / modality / alias
                    target.mkdir(parents=True)
                    created.append(target)
                    for path in (staging / modality / alias).iterdir():
                        path.rename(target / path.name)
        except BaseException:
            for target in reversed(created):
                shutil.rmtree(target)
            raise
    for recording, receipt in zip(recordings, receipts):
        print(json.dumps({
            "source": str(recording.source),
            "task": recording.alias,
            "screenshot_task": str(output / "data-ss" / recording.alias),
            "dom_task": str(output / "data-dom" / recording.alias),
            "actions": receipt["actions"],
            "screenshots": receipt["screenshots"],
            "dom_model_states": receipt["dom_model_states"],
            "alignment_warnings": receipt["alignment"].get("warnings", []),
        }, ensure_ascii=False))
    print(f"Prepared {len(recordings)} paired task(s) in {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RunnerError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
