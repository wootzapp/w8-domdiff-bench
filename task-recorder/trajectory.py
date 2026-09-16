"""Verifier trajectory and Microsoft WebSurfer artifact export."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_browser import AgentBrowserClient
from recorder_support import RunnerError, clean_dom_text, write_json_lines


TRAJECTORY_SCHEMA_VERSION = "1.0"
WEBSURFER_ACTION_MAP = {
    "navigate": "visit_url",
    # WebSurfer has no dedicated history action. Represent the browser's
    # back navigation with its standard keyboard form.
    "back": "key",
    "click": "left_click",
    "fill": "type",
    "type": "type",
    # Preserve exact executed actions that have no legacy renaming rule.
    "select": "select",
    "press": "key",
    "scroll": "scroll",
    "wait": "wait",
}

def websurfer_action(
    action_record: dict[str, Any],
) -> tuple[str, dict[str, Any], str]:
    """Map one confirmed execution to a self-contained WebSurfer action.

    Ref-based arguments carry both the exact executed ref and the semantic
    role/name returned for that ref by the same pre-action agent-browser
    snapshot. No ChromiumRL identifier is inferred or joined here.
    """
    raw_action = action_record.get("action")
    if not isinstance(raw_action, dict):
        raise RunnerError("action record has no structured executed action")
    source_action = clean_dom_text(raw_action.get("action"))
    mapped_action = WEBSURFER_ACTION_MAP.get(source_action)
    if mapped_action is None:
        raise RunnerError(
            f"executed action {source_action!r} has no confirmed WebSurfer mapping"
        )
    thought = action_record.get("thought")
    if not isinstance(thought, str) or not thought.strip():
        raise RunnerError("executed action has no verbatim accepted thought")

    arguments: dict[str, Any] = {"action": mapped_action}
    if source_action == "navigate":
        url = str(raw_action.get("url", "")).strip()
        if not url.startswith(("http://", "https://")):
            raise RunnerError("executed navigate action has no valid URL")
        arguments["url"] = url
    elif source_action == "back":
        arguments["key"] = "ALT+LEFT"
    elif source_action in {"click", "fill", "type", "select", "scroll"}:
        ref = AgentBrowserClient.action_ref(raw_action.get("id"))
        if ref:
            target = action_record.get("target")
            if not isinstance(target, dict):
                raise RunnerError(f"ref-based action {ref!r} has no semantic target")
            exact_target = {
                "ref": str(target.get("ref", "")),
                "role": str(target.get("role", "")),
                "name": str(target.get("name", "")),
            }
            if exact_target["ref"] != ref:
                raise RunnerError(
                    f"executed ref {ref!r} does not match target ref "
                    f"{exact_target['ref']!r}"
                )
            if not exact_target["role"].strip() or not exact_target["name"].strip():
                raise RunnerError(
                    f"ref-based action {ref!r} lacks its DOM-derived role/name"
                )
            arguments["ref"] = ref
            arguments["target"] = exact_target
            coordinate_capture = action_record.get("coordinate_capture")
            coordinate = (
                coordinate_capture.get("coordinate")
                if isinstance(coordinate_capture, dict)
                else None
            )
            if (
                isinstance(coordinate, list)
                and len(coordinate) == 2
                and all(isinstance(value, (int, float)) for value in coordinate)
            ):
                arguments["coordinate"] = coordinate
        elif source_action in {"click", "fill", "select"}:
            raise RunnerError(f"executed {source_action} action has no ref")
        if source_action in {"fill", "type", "select"}:
            arguments["text"] = "" if raw_action.get("text") is None else str(
                raw_action.get("text")
            )
        if source_action == "scroll":
            result = action_record.get("action_result")
            normalized = (
                result.get("normalized_parameters")
                if isinstance(result, dict)
                and isinstance(result.get("normalized_parameters"), dict)
                else {}
            )
            arguments["pixels"] = (
                normalized["pixels"]
                if isinstance(normalized.get("pixels"), (int, float))
                else (
                    800.0
                    if raw_action.get("pixels") is None
                    else float(raw_action.get("pixels"))
                )
            )
    elif source_action == "press":
        key = "" if raw_action.get("key") is None else str(raw_action.get("key"))
        if not key:
            raise RunnerError("executed press action has no key")
        arguments["key"] = key
    elif source_action == "wait":
        result = action_record.get("action_result")
        normalized = (
            result.get("normalized_parameters")
            if isinstance(result, dict)
            and isinstance(result.get("normalized_parameters"), dict)
            else {}
        )
        seconds = normalized.get("seconds")
        if not isinstance(seconds, (int, float)):
            seconds = (
                1.0
                if raw_action.get("seconds") is None
                else float(raw_action.get("seconds"))
            )
        arguments["seconds"] = seconds

    arguments["thoughts"] = thought
    return mapped_action, arguments, thought


def step_directory_number(path: Path) -> int:
    """Parse and validate the numeric suffix used for chronological step order."""
    match = re.fullmatch(r"step_(\d+)", path.name)
    if not match:
        raise RunnerError(f"invalid recorded step directory name: {path.name}")
    return int(match.group(1))


def snapshot_url(snapshot_path: Path) -> str:
    """Read one captured state URL from its stored structured snapshot."""
    loaded = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RunnerError("state snapshot is not a JSON object")
    result = loaded.get("result")
    snapshot = result.get("snapshot") if isinstance(result, dict) else None
    if not isinstance(snapshot, dict):
        raise RunnerError("state snapshot has no ChromiumRL snapshot object")
    url = snapshot.get("url")
    if not isinstance(url, str) or not url:
        raise RunnerError("state snapshot has no document URL")
    return url


def generate_trajectory_artifacts(run_dir: Path) -> dict[str, Any]:
    """Generate trajectory.jsonl and web_surfer.log from recorded states."""
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise RunnerError(f"run directory does not exist: {run_dir}")
    manifest_path = run_dir / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            manifest = loaded
    task_id = str(manifest.get("task_id") or run_dir.name)
    steps_root = run_dir / "steps"
    child_directories = (
        [path for path in steps_root.iterdir() if path.is_dir()]
        if steps_root.is_dir()
        else []
    )
    state_dirs = sorted(
        (
            path
            for path in child_directories
            if re.fullmatch(r"step_\d+", path.name)
        ),
        key=step_directory_number,
    )

    trajectory_rows: list[dict[str, Any]] = []
    websurfer_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, Any]] = [
        {
            "step": path.name,
            "error": "RunnerError: unrecognized directory under steps/",
        }
        for path in child_directories
        if not re.fullmatch(r"step_\d+", path.name)
    ]
    for expected_state, state_dir in enumerate(state_dirs, start=1):
        try:
            state_number = step_directory_number(state_dir)
            if state_number != expected_state:
                raise RunnerError(
                    f"captured state sequence is not contiguous: expected "
                    f"step_{expected_state:03d}, found {state_dir.name}"
                )
            snapshot_path = state_dir / "dom.json"
            if not snapshot_path.exists():
                raise RunnerError(
                    f"required state artifact is missing: "
                    f"{snapshot_path.relative_to(run_dir)}"
                )
            action_path = state_dir / "action.json"
            if not action_path.exists():
                continue
            next_state_dir = steps_root / f"step_{state_number + 1:03d}"
            next_snapshot_path = next_state_dir / "dom.json"
            if not next_snapshot_path.exists():
                raise RunnerError(
                    f"action state has no following captured state: "
                    f"{next_snapshot_path.relative_to(run_dir)}"
                )
            action_record = json.loads(action_path.read_text(encoding="utf-8"))
            if not isinstance(action_record, dict):
                raise RunnerError("action record is not a JSON object")
            raw_action = action_record.get("action")
            if not isinstance(raw_action, dict):
                raise RunnerError("action record has no structured executed action")
            source_action = clean_dom_text(raw_action.get("action"))
            source_url = snapshot_url(snapshot_path)
            next_url = snapshot_url(next_snapshot_path)
            timestamp = str(action_record.get("started_at", ""))
            if not timestamp:
                raise RunnerError("executed action has no timestamp")
            if source_action == "request_human":
                skipped.append(
                    {
                        "step": state_dir.name,
                        "reason": "human intervention is not an executed browser action",
                    }
                )
                continue
            mapped_action, arguments, thought = websurfer_action(action_record)
            action_number = len(trajectory_rows) + 1
            result = action_record.get("action_result")
            execution_succeeded = (
                action_record.get("action_succeeded") is True
                and action_record.get("action_error") in (None, "")
                and isinstance(result, dict)
                and result.get("success") is True
            )
            execution_status = "success" if execution_succeeded else "failure"
            execution_error = action_record.get("action_error")
            if not execution_succeeded and not execution_error:
                execution_error = "browser execution was not confirmed successful"

            trajectory_row = {
                "schema_version": TRAJECTORY_SCHEMA_VERSION,
                "task_id": task_id,
                "action_number": action_number,
                "step": state_number,
                "source_step": state_dir.name,
                "next_step": next_state_dir.name,
                "timestamp": timestamp,
                "thought": thought,
                "action": mapped_action,
                "arguments": arguments,
                "state_url": source_url,
                "next_state_url": next_url,
                "execution_status": execution_status,
            }
            if execution_error:
                trajectory_row["execution_error"] = str(execution_error)
            coordinate_capture = action_record.get("coordinate_capture")
            if (
                source_action == "click"
                and isinstance(coordinate_capture, dict)
                and coordinate_capture.get("status") != "resolved"
            ):
                trajectory_row["coordinate_status"] = str(
                    coordinate_capture.get("status") or "not_found"
                )
            trajectory_rows.append(trajectory_row)
            message_arguments = {
                key: value for key, value in arguments.items() if key != "thoughts"
            }
            message = (
                f"\nThought #{action_number}: {thought}"
                f"\nAction #{action_number}: executing tool {mapped_action!r} "
                f"with arguments "
                f"{json.dumps(message_arguments, ensure_ascii=False, separators=(",", ":"))}"
            )
            websurfer_row = {
                "timestamp": timestamp,
                "type": "WebSurferEvent",
                "source": "WebSurfer",
                "message": message,
                "action": mapped_action,
                "arguments": arguments,
                "url": next_url,
                "execution_status": execution_status,
            }
            if execution_error:
                websurfer_row["execution_error"] = str(execution_error)
            websurfer_rows.append(websurfer_row)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, RunnerError) as error:
            errors.append(
                {
                    "step": state_dir.name,
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    report: dict[str, Any] = {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "status": "invalid" if errors else "complete",
        "captured_states": len(state_dirs),
        "exported_actions": 0 if errors else len(trajectory_rows),
        "errors": errors,
        "skipped": skipped,
        "trajectory": None if errors else "trajectory.jsonl",
        "web_surfer_log": None if errors else "web_surfer.log",
        "self_contained_action_targets": True,
        "requires_action_json_after_export": False,
    }
    if errors:
        for stale_path in (
            run_dir / "trajectory.jsonl",
            run_dir / "web_surfer.log",
        ):
            stale_path.unlink(missing_ok=True)
        return report
    write_json_lines(run_dir / "trajectory.jsonl", trajectory_rows)
    write_json_lines(run_dir / "web_surfer.log", websurfer_rows)
    return report
