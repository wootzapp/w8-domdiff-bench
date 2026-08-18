"""Verifier trajectory and Microsoft WebSurfer artifact export."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_browser import AgentBrowserClient
from recorder_support import RunnerError, write_json_lines
from dom_diff import clean_dom_text


TRAJECTORY_SCHEMA_VERSION = "1.0"
WEBSURFER_ACTION_MAP = {
    "navigate": "visit_url",
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


def generate_trajectory_artifacts(run_dir: Path) -> dict[str, Any]:
    """Generate trajectory.jsonl and web_surfer.log only after full validation."""
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
    step_dirs = sorted(
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
    for expected_step, step_dir in enumerate(step_dirs, start=1):
        try:
            recorded_step = step_directory_number(step_dir)
            if recorded_step != expected_step:
                raise RunnerError(
                    f"executed step sequence is not contiguous: expected "
                    f"step_{expected_step:03d}, found {step_dir.name}"
                )
            action_path = step_dir / "action.json"
            diff_path = step_dir / "dom_diff.json"
            diff_text_path = step_dir / "dom_diff.txt"
            for required in (action_path, diff_path, diff_text_path):
                if not required.exists():
                    raise RunnerError(
                        f"required executed-action artifact is missing: "
                        f"{required.relative_to(run_dir)}"
                    )
            action_record = json.loads(action_path.read_text(encoding="utf-8"))
            diff_record = json.loads(diff_path.read_text(encoding="utf-8"))
            if not isinstance(action_record, dict) or not isinstance(diff_record, dict):
                raise RunnerError("action or DOM-diff record is not a JSON object")
            raw_action = action_record.get("action")
            if not isinstance(raw_action, dict):
                raise RunnerError("action record has no structured executed action")
            source_action = clean_dom_text(raw_action.get("action"))
            before_endpoint = (
                diff_record.get("before")
                if isinstance(diff_record.get("before"), dict)
                else {}
            )
            after_endpoint = (
                diff_record.get("after")
                if isinstance(diff_record.get("after"), dict)
                else {}
            )
            before_url = str(before_endpoint.get("url", ""))
            after_url = str(after_endpoint.get("url", ""))
            if not after_url:
                raise RunnerError("DOM diff has no after-action URL")
            timestamp = str(action_record.get("started_at", ""))
            if not timestamp:
                raise RunnerError("executed action has no timestamp")
            if source_action == "request_human":
                skipped.append(
                    {
                        "step": step_dir.name,
                        "reason": (
                            "human intervention step is not an executed browser action"
                        ),
                    }
                )
                continue
            result = action_record.get("action_result")
            if (
                action_record.get("action_succeeded") is not True
                or action_record.get("action_error") not in (None, "")
                or not isinstance(result, dict)
                or result.get("success") is not True
            ):
                raise RunnerError(
                    "browser execution was not confirmed successful; verifier "
                    "dataset generation requires a rerun"
                )

            mapped_action, arguments, thought = websurfer_action(action_record)
            action_number = len(trajectory_rows) + 1

            trajectory_row = {
                "schema_version": TRAJECTORY_SCHEMA_VERSION,
                "task_id": task_id,
                "action_number": action_number,
                "step": recorded_step,
                "source_step": step_dir.name,
                "timestamp": timestamp,
                "thought": thought,
                "action": mapped_action,
                "arguments": arguments,
                "before_url": before_url,
                "after_url": after_url,
                "dom_diff": str(diff_path.relative_to(run_dir)),
                "dom_diff_text": str(diff_text_path.relative_to(run_dir)),
            }
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
                f"{json.dumps(message_arguments, ensure_ascii=False, separators=(',', ':'))}"
            )
            websurfer_rows.append(
                {
                    "timestamp": timestamp,
                    "type": "WebSurferEvent",
                    "source": "WebSurfer",
                    "message": message,
                    "action": mapped_action,
                    "arguments": arguments,
                    "url": after_url,
                }
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError, RunnerError) as error:
            errors.append(
                {
                    "step": step_dir.name,
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    report: dict[str, Any] = {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "status": "invalid" if errors else "complete",
        "executed_step_directories": len(step_dirs),
        "exported_actions": 0 if errors else len(trajectory_rows),
        "errors": errors,
        "skipped": skipped,
        "trajectory": None if errors else "trajectory.jsonl",
        "web_surfer_log": None if errors else "web_surfer.log",
        "self_contained_action_targets": True,
        "requires_action_json_after_export": False,
    }
    if errors:
        # Never leave a previously generated trajectory looking valid after the
        # source run has failed validation. These files are derived artifacts;
        # action.json and dom_diff.* remain the authoritative recording.
        for stale_path in (
            run_dir / "trajectory.jsonl",
            run_dir / "web_surfer.log",
        ):
            stale_path.unlink(missing_ok=True)
        return report
    write_json_lines(run_dir / "trajectory.jsonl", trajectory_rows)
    write_json_lines(run_dir / "web_surfer.log", websurfer_rows)
    return report

