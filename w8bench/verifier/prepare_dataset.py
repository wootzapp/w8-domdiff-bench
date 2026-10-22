"""Convert recorder runs into paired, model-free verifier input datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from w8bench.screenshot_verifier.utils.preflight import preflight_screenshot_task
from w8bench.task_recorder.trajectory import (
    snapshot_url,
    step_directory_number,
    websurfer_action,
)

from .common import load_json, write_json
from .validate_inputs import dataset_only_preflight


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TASK_RE = re.compile(r"task_(\d+)")


def _object(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object: {path}:{number}")
        rows.append(value)
    return rows


def _source(root: Path, path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"Recording artifact must be a file inside {root}: {path}")
    return resolved


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inspect_recording(root: Path) -> tuple[dict, dict, list[dict]]:
    """Check every state/action before writing any derived task files."""
    task = _object(root / "task.json")
    manifest = _object(root / "manifest.json")
    final = _object(root / "final.json")
    for field in ("instruction", "start_url"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise ValueError(f"task.json must contain recorded {field} text")
    if not isinstance(final.get("final_answer"), str):
        raise ValueError("final.json must contain recorded final_answer text")
    export = manifest.get("trajectory_export") or {}
    if export.get("status") != "complete":
        raise ValueError("Recording requires a complete trajectory export before preparation")
    trajectory = _rows(root / "trajectory.jsonl")
    events = _rows(root / "web_surfer.log")
    steps_root = root / "steps"
    directories = [path for path in steps_root.iterdir() if path.is_dir()] if steps_root.is_dir() else []
    if not directories:
        raise ValueError("Recording has no captured states; screenshot/DOM evidence is missing")
    directories.sort(key=step_directory_number)
    if [step_directory_number(path) for path in directories] != list(range(1, len(directories) + 1)):
        raise ValueError("Recorded state directories must be contiguous from step_001")
    if len(events) != len(trajectory) or len(directories) != len(trajectory) + 1:
        raise ValueError("Recording requires N trajectory actions, N WebSurfer rows, and N+1 captured states")
    recorded_states = manifest.get("states")
    recorded_actions = manifest.get("steps")
    if not isinstance(recorded_states, list) or len(recorded_states) != len(directories):
        raise ValueError("Manifest state count differs from recorded state directories")
    if not isinstance(recorded_actions, list) or len(recorded_actions) != len(trajectory):
        raise ValueError("Manifest action count differs from trajectory.jsonl")
    if final.get("recorded_steps") != len(trajectory):
        raise ValueError("Final recorded_steps differs from trajectory.jsonl")
    if export.get("captured_states") != len(directories) or export.get("exported_actions") != len(trajectory):
        raise ValueError("Manifest trajectory export counts differ from recorded evidence")

    states = []
    for index, directory in enumerate(directories):
        snapshot = _source(root, directory / "dom.json")
        screenshot = _source(root, directory / "screenshot.png")
        dom = _source(root, directory / "dom_model.txt")
        url = snapshot_url(snapshot)
        declared = recorded_states[index]
        if not isinstance(declared, dict) or declared.get("state") != index + 1:
            raise ValueError(f"Manifest state order differs at {directory.name}")
        for field, path in (("snapshot", snapshot), ("screenshot", screenshot), ("model_text", dom)):
            if declared.get(field) != path.relative_to(root).as_posix():
                raise ValueError(f"Manifest {field} differs at {directory.name}")
        if declared.get("document_url") != url:
            raise ValueError(f"Manifest URL differs from snapshot at {directory.name}")
        dom_text = dom.read_text(encoding="utf-8")
        if not dom_text.strip() or f"URL: {url}" not in dom_text.splitlines():
            raise ValueError(f"DOM text URL differs from snapshot at {directory.name}")
        with Image.open(screenshot) as image:
            image.verify()
        states.append({
            "directory": directory,
            "url": url,
            "screenshot": screenshot,
            "dom": dom,
            "screenshot_sha256": _digest(screenshot),
            "dom_sha256": _digest(dom),
        })

    for index, (row, event) in enumerate(zip(trajectory, events)):
        directory = directories[index]
        action = _object(_source(root, directory / "action.json"))
        name, arguments, thought = websurfer_action(action)
        if (
            row.get("action_number") != index + 1
            or row.get("step") != index + 1
            or row.get("source_step") != directory.name
            or row.get("next_step") != directories[index + 1].name
            or row.get("state_url") != states[index]["url"]
            or row.get("next_state_url") != states[index + 1]["url"]
            or row.get("thought") != thought
        ):
            raise ValueError(f"Trajectory state/action alignment differs at {directory.name}")
        for record in (row, event):
            if (
                record.get("action") != name
                or record.get("arguments") != arguments
                or record.get("timestamp") != action.get("started_at")
                or not record.get("timestamp")
            ):
                raise ValueError(f"Exported action differs from action.json at {directory.name}")
        if event.get("url") != states[index + 1]["url"]:
            raise ValueError(f"WebSurfer after-URL differs at {directory.name}")
    if (directories[-1] / "action.json").exists():
        raise ValueError("Last recorded action has no following captured state")
    return task, final, states


def prepare_recording(recording: str | Path, output_dir: str | Path, task_alias: str) -> dict[str, Any]:
    """Prepare one logical task, preserving the source and refusing replacements."""
    if TASK_RE.fullmatch(task_alias) is None:
        raise ValueError("Task alias must have the form task_N, for example task_101")
    root = Path(recording).resolve(strict=True)
    output = Path(output_dir).resolve()
    if output.is_relative_to(root):
        raise ValueError("Dataset output must be outside the source recording")
    destinations = [output / mode / task_alias for mode in ("data-ss", "data-dom")]
    receipt_path = output / "preparation" / f"{task_alias}.json"
    for path in [*destinations, receipt_path]:
        if path.exists() or path.is_symlink():
            raise ValueError(f"Refusing to overwrite existing prepared task: {path}")
    task, final, states = _inspect_recording(root)
    task_data = [{
        "task_id": task_alias,
        "confirmed_task": task["instruction"],
        "website": task["start_url"],
        "source_recording": root.name,
        "source_task_id": task.get("source_task_id", task.get("task_id", root.name)),
    }]
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=output) as temporary:
        staged = [Path(temporary) / mode / task_alias for mode in ("data-ss", "data-dom")]
        for directory in staged:
            directory.mkdir(parents=True)
            write_json(directory / "task_data.json", task_data)
            write_json(directory / "final_answer.json", {"final_answer": final["final_answer"]})
            shutil.copyfile(root / "web_surfer.log", directory / "web_surfer.log")
        mappings = []
        for index, state in enumerate(states):
            image_name, dom_name = f"screenshot{index}.png", f"dom_model{index}.txt"
            shutil.copyfile(state["screenshot"], staged[0] / image_name)
            shutil.copyfile(state["dom"], staged[1] / dom_name)
            if _digest(staged[0] / image_name) != state["screenshot_sha256"] or _digest(staged[1] / dom_name) != state["dom_sha256"]:
                raise ValueError(f"Copied state {index} differs from its recording")
            mappings.append({
                "index": index,
                "url": state["url"],
                "screenshot": image_name,
                "screenshot_source": state["screenshot"].relative_to(root).as_posix(),
                "screenshot_sha256": state["screenshot_sha256"],
                "dom": dom_name,
                "dom_source": state["dom"].relative_to(root).as_posix(),
                "dom_sha256": state["dom_sha256"],
            })
        validation = dataset_only_preflight(*staged)
        preflight_screenshot_task(staged[0])
        published = []
        try:
            for source, destination in zip(staged, destinations):
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.rename(destination)
                published.append(destination)
            receipt = {
                "task": task_alias,
                "source_recording": str(root),
                "source_status": final.get("status"),
                "source_run_status": final.get("run_status"),
                "actions": validation["actions"],
                "states": len(states),
                "screenshot_path": str(destinations[0]),
                "dom_path": str(destinations[1]),
                "alignment_warnings": validation["alignment"]["warnings"],
                "states_mapping": mappings,
            }
            write_json(receipt_path, receipt)
        except Exception:
            for directory in published:
                shutil.rmtree(directory)
            raise
    return {key: value for key, value in receipt.items() if key != "states_mapping"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--recording", type=Path, help="Prepare one recording directory")
    source.add_argument("--recordings-dir", type=Path, default=REPOSITORY_ROOT / "recordings", help="Prepare each recording under this directory (default: ./recordings)")
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY_ROOT / "dataset")
    naming = parser.add_mutually_exclusive_group()
    naming.add_argument("--task", help="Explicit task_N alias; requires --recording")
    naming.add_argument("--start-task", type=int, help="First task number; defaults to the next unused number")
    args = parser.parse_args(argv)
    if args.task and not args.recording:
        parser.error("--task requires --recording")
    if args.start_task is not None and args.start_task < 1:
        parser.error("--start-task must be positive")
    if args.task and TASK_RE.fullmatch(args.task) is None:
        parser.error("--task must have the form task_N")
    if args.recording:
        recordings = [args.recording]
    else:
        if not args.recordings_dir.is_dir():
            parser.error(f"Recordings directory does not exist: {args.recordings_dir}")
        recordings = sorted(path for path in args.recordings_dir.iterdir() if path.is_dir() and not path.name.startswith("."))
    if not recordings:
        parser.error("No recordings found")
    existing = [int(match.group(1)) for mode in ("data-ss", "data-dom") for path in (args.output_dir / mode).glob("task_*") if (match := TASK_RE.fullmatch(path.name))]
    number = args.start_task if args.start_task is not None else max(existing, default=0) + 1
    prepared, failed = [], []
    for recording in recordings:
        alias = args.task or f"task_{number:02d}"
        try:
            prepared.append(prepare_recording(recording, args.output_dir, alias))
            number += 1
        except (OSError, ValueError, RuntimeError) as error:
            failed.append({"source_recording": str(recording), "error": str(error)})
    print(json.dumps({"prepared": prepared, "failed": failed}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
