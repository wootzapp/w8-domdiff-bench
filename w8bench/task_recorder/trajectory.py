"""Export each independent run without borrowing observations from another mode."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .recorder_support import RunnerError, write_json_lines

TRAJECTORY_SCHEMA_VERSION = "3.0"
WEBSURFER_ACTION_MAP = {"navigate": "visit_url", "back": "history_back", "click": "left_click",
    "type": "type", "press": "key", "scroll": "scroll", "wait": "wait"}


def websurfer_action(record: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    action = record["action"]
    name = WEBSURFER_ACTION_MAP.get(action.get("action"))
    if name is None:
        raise RunnerError("unsupported recorded action")
    arguments = {**action, "action": name, "thoughts": record["thought"]}
    coordinates = record.get("executed_coordinates") or (record.get("action_result") or {}).get("executed_coordinates")
    if coordinates is not None:
        if coordinates.get("units") != "css_pixels":
            raise RunnerError("recorded execution coordinates must use CSS pixels")
        arguments.update(x=coordinates["x"], y=coordinates["y"])
    if "target" in record:
        arguments["target"] = record["target"]
    return name, arguments, record["thought"]


def _trajectory_action(run_dir: Path, mode: str, states: list, index: int, record: dict) -> dict[str, Any]:
    if index >= len(states):
        raise RunnerError("action has no captured after-state")
    before, after = states[index - 1], states[index]
    if before["state"] != index or after["state"] != index + 1:
        raise RunnerError("state numbering is not contiguous")
    for state in (before, after):
        path = (run_dir / state["observation"]).resolve()
        if not path.is_relative_to(run_dir) or not path.is_file():
            raise RunnerError("state observation is missing or escapes its run")
    name, arguments, thought = websurfer_action(record)
    if mode == "screenshot" and (arguments.get("id") is not None or "target" in arguments):
        raise RunnerError("screenshot action contains DOM target information")
    row = {"schema_version": TRAJECTORY_SCHEMA_VERSION, "observation_mode": mode,
        "action_number": index, "model_turn": record["model_turn"],
        "source_step": before["directory"], "next_step": after["directory"],
        "before_observation": before["observation"], "after_observation": after["observation"],
        "before_artifacts": before["artifacts"], "after_artifacts": after["artifacts"],
        "before_capture": before["capture"], "after_capture": after["capture"],
        "action": name, "arguments": arguments, "thought": thought,
        "execution_status": "success" if record["action_succeeded"] else "failure",
        "execution_error": record.get("action_error")}
    return row


def generate_trajectory_artifacts(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    mode = manifest.get("observation_mode")
    if mode not in {"dom", "screenshot"}:
        raise RunnerError("legacy paired recordings are not independent actor runs")
    states, steps = manifest.get("states", []), manifest.get("steps", [])
    rows, events, errors = [], [], []
    if len(states) != len(steps) + 1:
        errors.append({"error": "N action attempts require N+1 captured states", "actions": len(steps), "states": len(states)})
    for index, record in enumerate(steps, 1):
        try:
            row = _trajectory_action(run_dir, mode, states, index, record)
            rows.append(row)
            events.append({"source": "WebSurfer", "action": row["action"], "arguments": row["arguments"],
                "model_turn": record["model_turn"], "execution_status": row["execution_status"]})
        except (KeyError, OSError, ValueError, RunnerError) as error:
            errors.append({"action_number": index, "error": str(error)})
    write_json_lines(run_dir / "trajectory.jsonl", rows)
    write_json_lines(run_dir / "web_surfer.log", events)
    return {"schema_version": TRAJECTORY_SCHEMA_VERSION, "status": "complete" if not errors else "incomplete",
        "observation_mode": mode, "captured_states": len(states), "action_attempts": len(steps),
        "exported_actions": len(rows), "errors": errors}
