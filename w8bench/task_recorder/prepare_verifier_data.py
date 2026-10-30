"""Prepare paired screenshot and DOM verifier inputs from local recordings.

Usage: python -m w8bench.task_recorder.prepare_verifier_data RECORDINGS OUTPUT
   or: python w8bench/task_recorder/prepare_verifier_data.py RECORDINGS OUTPUT
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
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
    input_sha256: dict[str, str]
    manifest_status: str
    coordinate_provenance: list[dict[str, Any]]
    metadata_warnings: list[dict[str, Any]]


def input_hashes(source: Path) -> dict[str, str]:
    """Identify consumed files and reject evidence links outside this run."""
    paths = [source / name for name in (
        "task.json", "manifest.json", "final.json", "trajectory.jsonl", "web_surfer.log"
    )]
    for state in (source / "steps").iterdir():
        step_directory_number(state)
        if not state.is_dir():
            raise ValueError(f"Not a captured state directory: {state}")
        paths.extend(state / name for name in ("dom.json", "dom_model.txt", "screenshot.png"))
        if (state / "action.json").exists():
            paths.append(state / "action.json")
    hashes = {}
    for path in sorted(paths):
        if not path.resolve(strict=True).is_relative_to(source):
            raise ValueError(f"Recording evidence escapes its source directory: {path}")
        hashes[path.relative_to(source).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


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
    source = source.resolve(strict=True)
    hashes = input_hashes(source)
    task = read_object(source / "task.json")
    manifest = read_object(source / "manifest.json")
    final = read_object(source / "final.json")
    for field in ("task_id", "instruction", "start_url"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise ValueError(f"{source}: task.json needs non-empty {field}")
    if manifest.get("task_id") != task["task_id"]:
        raise ValueError(f"{source}: task and manifest IDs differ")
    if manifest.get("status") in {None, "running"}:
        raise ValueError(f"{source}: recording has not been finalized")
    if not isinstance(final.get("status"), str) or not isinstance(
        final.get("final_answer"), str
    ):
        raise ValueError(f"{source}: final.json needs a completed status and final_answer text")
    # A recorded failure or runtime error is not an evidence-format failure.
    # Usability depends on the action/state checks below, not on task outcome.
    if manifest.get("final") != final:
        raise ValueError(f"{source}: final.json differs from the manifest's final result")
    for name in ("steps", "states"):
        rows = manifest.get(name)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"{source}: manifest {name} must be a list of objects")
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
    metadata_warnings = []
    for state, metadata in zip(states, recorded_states):
        url = snapshot_url(state / "dom.json")
        text = (state / "dom_model.txt").read_text(encoding="utf-8")
        dom_url = next((line[4:].strip() for line in text.splitlines() if line.startswith("URL:")), "")
        if dom_url != url:
            raise ValueError(f"{state}: snapshot and DOM text URLs differ")
        if metadata.get("document_url") != url:
            # The manifest URL is a separate live read. Keep the captured URL
            # and action chronology authoritative, and disclose that mismatch.
            metadata_warnings.append({
                "code": "manifest_document_url_mismatch", "state": state.name,
                "manifest_url": metadata.get("document_url"), "snapshot_url": url,
            })
        with Image.open(state / "screenshot.png") as screenshot:
            if screenshot.format != "PNG":
                raise ValueError(f"{state}: screenshot.png is not a PNG image")
            screenshot.verify()
        urls.append(url)

    coordinate_provenance = []
    for index, (row, event) in enumerate(zip(trajectory, events)):
        action_record = read_object(states[index] / "action.json")
        if not isinstance(action_record.get("started_at"), str) or not action_record["started_at"].strip():
            raise ValueError(f"{source}: action {index + 1} has no recorded timestamp")
        action, arguments, thought = websurfer_action(action_record)
        result = action_record.get("action_result")
        succeeded = (
            action_record.get("action_succeeded") is True
            and action_record.get("action_error") in (None, "")
            and isinstance(result, dict) and result.get("success") is True
        )
        expected = {
            "action_number": index + 1,
            "source_step": states[index].name,
            "next_step": states[index + 1].name,
            "state_url": urls[index],
            "next_state_url": urls[index + 1],
            "action": action,
            "arguments": arguments,
            "timestamp": action_record.get("started_at"),
            "thought": thought,
            "execution_status": "success" if succeeded else "failure",
        }
        for key, value in expected.items():
            if row.get(key) != value:
                raise ValueError(f"{source}: trajectory action {index + 1} disagrees with capture for {key}")
        for key in ("action", "arguments", "timestamp", "execution_status"):
            if event.get(key) != row.get(key):
                raise ValueError(f"{source}: WebSurfer action {index + 1} differs for {key}")
        if event.get("url") != urls[index + 1]:
            raise ValueError(f"{source}: WebSurfer action {index + 1} has the wrong after-URL")
        # Copy the recorded resolver result, including unresolved/error cases.
        # This stays outside verifier inputs: it must not change judge context.
        coordinate_provenance.append({
            "action_number": index + 1,
            "action_record": f"steps/{states[index].name}/action.json",
            "coordinate_capture": action_record.get("coordinate_capture"),
        })
    if (states[-1] / "action.json").exists():
        raise ValueError(f"{source}: final state has an action without an after-state")

    source_id = str(task.get("source_task_id") or task["task_id"])
    numeric = re.fullmatch(r"(?:browser_)?task[_-]?(\d+)", source_id)
    alias = f"task_{int(numeric.group(1)):02d}" if numeric else source.name
    if input_hashes(source) != hashes:
        raise ValueError(f"Recording changed during inspection: {source}")
    return Recording(source, alias, task, final, states, count, hashes,
                     str(manifest["status"]), coordinate_provenance, metadata_warnings)


def copy_evidence(source: Path, destination: Path, expected: str) -> None:
    """Keep every physical state, including repeated images, byte-for-byte."""
    shutil.copyfile(source, destination)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Evidence changed while copying: {source}")


def prepare_recording(recording: Recording, staging: Path) -> dict[str, Any]:
    if input_hashes(recording.source) != recording.input_sha256:
        raise ValueError(f"Recording changed after inspection: {recording.source}")
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
        "env_state_json": recording.final.get("env_state_json", "<no_answer>"),
        "env_state_raw": recording.final.get("env_state_raw", "<no_answer>"),
        "is_aborted": recording.final.get("is_aborted", False)
        or recording.final.get("run_status") == "interrupted",
        "is_rel_paths": True,
        "token_usage": {},
    }
    for root in (screenshot, dom):
        write_json(root / "task_data.json", task_data)
        copy_evidence(recording.source / "web_surfer.log", root / "web_surfer.log",
                      recording.input_sha256["web_surfer.log"])
    write_json(dom / "final_answer.json", answer)
    write_json(screenshot / "final_answer.json", {
        **answer,
        "screenshots": [f"screenshot{index}.png" for index in range(len(recording.states))],
    })
    for index, state in enumerate(recording.states):
        for name, destination in (
            ("screenshot.png", screenshot / f"screenshot{index}.png"),
            ("dom_model.txt", dom / f"dom_model{index}.txt"),
        ):
            original = state / name
            copy_evidence(original, destination,
                          recording.input_sha256[original.relative_to(recording.source).as_posix()])

    receipt = dataset_only_preflight(screenshot, dom)
    preflight_screenshot_task(screenshot)
    if Trajectory.from_folder(screenshot) is None:
        raise ValueError(f"Screenshot trajectory parser could not load {screenshot}")
    if input_hashes(recording.source) != recording.input_sha256:
        raise ValueError(f"Recording changed during preparation: {recording.source}")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", nargs="?", default=Path("recordings"), type=Path,
                        help="Recordings directory or a single recorded run (default: recordings)")
    parser.add_argument("output_dir", nargs="?", default=Path("trajectories"), type=Path,
                        help="New folder for paired verifier inputs (default: trajectories)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check conversion in temporary storage without publishing inputs")
    args = parser.parse_args(argv)
    source = args.input_dir.resolve(strict=True)
    output = args.output_dir.resolve()
    if not source.is_dir():
        raise ValueError(f"Input is not a directory: {source}")
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Input and output directories must not overlap")
    previous = None
    report_hash = None
    if output.is_symlink():
        raise ValueError(f"Output must not be a symlink: {output}")
    if output.exists():
        if not (output / "preparation_report.json").is_file():
            raise ValueError(f"Refusing to mix with or overwrite unrecognised verifier inputs: {output}")
        previous = read_object(output / "preparation_report.json")
        report_hash = hashlib.sha256((output / "preparation_report.json").read_bytes()).hexdigest()
        if (previous.get("schema_version") != "1.0"
            or (output / previous.get("source_root", "")).resolve() != source
            or not isinstance(previous.get("prepared"), list)
            or not isinstance(previous.get("excluded"), list)):
            raise ValueError("Existing preparation report does not describe this source collection")
        if (previous.get("prepared_count") != len(previous["prepared"])
            or previous.get("excluded_count") != len(previous["excluded"])
            or previous.get("selected_recordings") != len(previous["prepared"]) + len(previous["excluded"])):
            raise ValueError("Existing preparation report counts disagree")
    runs = [source] if (source / "task.json").is_file() else sorted(
        path for path in source.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    if not runs:
        raise ValueError(f"No recordings found: {source}")
    if previous:
        prior_sources = {str((output / row["source"]).resolve())
                         for row in previous["prepared"] + previous["excluded"]}
        if prior_sources != {str(run.resolve()) for run in runs}:
            raise ValueError("Append must use the same recorded attempts; source collection changed")
        prior_aliases = {row["task"] for row in previous["prepared"]}
        if len(prior_aliases) != len(previous["prepared"]):
            raise ValueError("Existing preparation report has duplicate task aliases")
        for side in ("data-ss", "data-dom"):
            if {p.name for p in (output / side).iterdir()} != prior_aliases:
                raise ValueError(f"Existing {side} folders differ from the preparation report")
        for row in previous["prepared"]:
            actual = {}
            for side in ("data-ss", "data-dom"):
                for path in (output / side / row["task"]).rglob("*"):
                    if path.is_symlink():
                        raise ValueError(f"Existing verifier input must not be a symlink: {path}")
                    if path.is_file():
                        actual[path.relative_to(output).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            if not actual or actual != row.get("output_sha256"):
                raise ValueError(f"Existing verifier inputs changed: {row['task']}")
    recordings = []
    excluded = []
    for run in runs:
        try:
            if run.is_symlink():
                raise ValueError(f"Recording directory must not be a symlink: {run}")
            recordings.append(inspect_recording(run))
        except (OSError, ValueError, TypeError, KeyError, RunnerError) as error:
            excluded.append({"source": os.path.relpath(run, output),
                             "error": f"{type(error).__name__}: {error}".replace(
                                 str(run), os.path.relpath(run, output))})
    counts = Counter(recording.alias for recording in recordings)
    for recording in recordings:
        if counts[recording.alias] > 1:
            recording.alias = f"{recording.alias}-{recording.source.name}"
    aliases = [recording.alias for recording in recordings]
    if len(set(aliases)) != len(aliases):
        raise ValueError("Recordings map to duplicate output task names")
    if not args.dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
    # Stage each task separately: a bad task cannot leave half a published pair.
    # Append only to a verified report for the same source attempts. Existing
    # inputs are reused byte-for-byte, not regenerated or selected by outcome.
    with tempfile.TemporaryDirectory(
        prefix=".prepare-verifier-", dir=None if args.dry_run else output.parent
    ) as name:
        staging = Path(name)
        bundle = staging / "inputs"
        bundle.mkdir()
        prepared = []
        for recording in recordings:
            existing = next((row for row in previous["prepared"]
                             if row["task"] == recording.alias), None) if previous else None
            if existing:
                if ((output / existing["source"]).resolve() != recording.source
                    or existing.get("source_sha256") != recording.input_sha256):
                    raise ValueError(f"Previously prepared source changed: {recording.alias}")
                prepared.append(existing)
                continue
            try:
                with tempfile.TemporaryDirectory(prefix="task-", dir=staging) as task_stage:
                    task_root = Path(task_stage)
                    receipt = prepare_recording(recording, task_root)
                    for modality in ("data-ss", "data-dom"):
                        destination = bundle / modality / recording.alias
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        (task_root / modality / recording.alias).rename(destination)
                prepared.append({
                    "source": os.path.relpath(recording.source, output),
                    "task": recording.alias,
                    "recorded_status": recording.final["status"],
                    "run_status": recording.final.get("run_status"),
                    "manifest_status": recording.manifest_status,
                    "coordinate_provenance": recording.coordinate_provenance,
                    "metadata_warnings": recording.metadata_warnings,
                    "source_sha256": recording.input_sha256,
                    "output_sha256": {
                        path.relative_to(bundle).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                        for modality in ("data-ss", "data-dom")
                        for path in (bundle / modality / recording.alias).iterdir()
                        if path.is_file()
                    },
                    "actions": receipt["actions"],
                    "screenshots": receipt["screenshots"],
                    "dom_model_states": receipt["dom_model_states"],
                    "alignment_warnings": receipt["alignment"].get("warnings", []),
                })
            except (OSError, ValueError, TypeError, KeyError, RunnerError) as error:
                # Only these exact paths in our owned staging directory can be removed.
                for modality in ("data-ss", "data-dom"):
                    target = bundle / modality / recording.alias
                    if target.exists():
                        shutil.rmtree(target)
                excluded.append({"source": os.path.relpath(recording.source, output),
                                 "error": f"{type(error).__name__}: {error}".replace(
                                     str(recording.source), os.path.relpath(recording.source, output))})
        report = {
            "schema_version": "1.0", "source_root": os.path.relpath(source, output),
            "output_root": ".", "dry_run": args.dry_run,
            "selected_recordings": len(runs), "prepared_count": len(prepared),
            "excluded_count": len(excluded), "prepared": prepared, "excluded": excluded,
            "coordinate_semantics": (
                "Recorder coordinates describe matched element centres, not exact pointer-event positions. "
                "Per-action coordinate_capture preserves the recorded source, phase, and resolution status."
            ),
        }
        if not args.dry_run:
            write_json(bundle / "preparation_report.json", report)
            if previous is None:
                bundle.rename(output)
            else:
                if hashlib.sha256((output / "preparation_report.json").read_bytes()).hexdigest() != report_hash:
                    raise ValueError("Preparation report changed during append")
                if not {row["source"] for row in previous["prepared"]}.issubset(
                    {row["source"] for row in prepared}
                ):
                    raise ValueError("Append would remove previously prepared inputs")
                created = []
                try:
                    for side in ("data-ss", "data-dom"):
                        for path in sorted((bundle / side).iterdir()) if (bundle / side).exists() else []:
                            target = output / side / path.name
                            if target.exists() or target.is_symlink():
                                raise ValueError(f"Refusing to overwrite existing task: {target}")
                            path.rename(target)
                            created.append(target)
                    write_json(output / "preparation_report.json", report)
                except BaseException:
                    for target in reversed(created):
                        shutil.rmtree(target)
                    raise
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if excluded else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RunnerError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
