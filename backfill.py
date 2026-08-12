"""Stored-run DOM-diff regeneration and metadata synchronization."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from artifacts import utc_now, write_json
from capture import preserve_original_renders, render_stored_snapshot, renderer_versions
from dom_diff import (
    DOM_DIFF_FIELDS,
    DOM_DIFF_SOURCE,
    MAX_DOM_DIFF_JSON_BYTES,
    clean_dom_text,
    write_dom_diff_files,
)
from recorder_errors import RunnerError

def previous_dom_diff_state(path: Path) -> str:
    """Classify broken/missing evidence separately from valid semantic zero."""
    if not path.exists():
        return "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "invalid_json"
    if value in (None, [], {}):
        return "empty_payload"
    if not isinstance(value, dict):
        return "legacy_non_object"
    if value.get("native_diff_available") is False:
        return "missing_native_diff"
    if value.get("diff") in (None, [], {}):
        return "empty_diff_payload"
    try:
        change_count = int(value.get("change_count", 0) or 0)
    except (TypeError, ValueError):
        return "invalid_change_count"
    return "semantic_zero" if change_count == 0 else "changes_present"


def diff_report_summary(record: dict[str, Any]) -> dict[str, Any]:
    """Return compact backfill diagnostics without replacing the full artifact."""
    diff = record.get("diff") if isinstance(record.get("diff"), dict) else {}
    summary: dict[str, Any] = {
        "status": record.get("status"),
        "change_count": record.get("change_count", 0),
        "totals": record.get("totals", {}),
    }
    if record.get("status") == "document_replaced":
        summary["navigation"] = diff.get("navigation")
        text_delta = diff.get("text_delta") if isinstance(diff.get("text_delta"), dict) else {}
        summary["sample_removed_text"] = (text_delta.get("removed") or [])[:3]
        summary["sample_added_text"] = (text_delta.get("added") or [])[:3]
    else:
        summary["sample_added_paths"] = [item.get("path") for item in (diff.get("added") or [])[:3]]
        summary["sample_removed_paths"] = [item.get("path") for item in (diff.get("removed") or [])[:3]]
        summary["sample_changed_paths"] = [item.get("path") for item in (diff.get("changed") or [])[:3]]
    return summary


def apply_diff_metadata(manifest: dict[str, Any]) -> None:
    """Record the local snapshot-diff contract and explicitly excluded fields."""
    manifest["dom_diff_source"] = DOM_DIFF_SOURCE
    manifest["dom_diff_format"] = "snapshot_path_diff_v2"
    manifest["dom_diff_identity"] = (
        "tag plus normalized own directText or semantic-node accessibility anchor with occurrence index; "
        "tag sibling-position fallback for broad nodes and nodes without own content anchors"
    )
    manifest["dom_diff_compared_fields"] = list(DOM_DIFF_FIELDS)
    manifest["dom_diff_geometry_excluded"] = True
    manifest["dom_diff_covers_live_control_state"] = False
    manifest["dom_diff_max_json_bytes"] = MAX_DOM_DIFF_JSON_BYTES
    manifest.pop("dom_diff_max_json_lines", None)
    manifest["dom_diff_excluded_fields"] = [
        "bounds",
        "clippedBounds",
        "sourceOrder",
        "index",
        "confidence",
        "ref",
        "nodeId",
        "backendNodeId",
    ]
    manifest.pop("dom_diff_capture_parameters", None)


def update_step_diff_metadata(step_record: dict[str, Any], step_dir: Path, run_dir: Path, record: dict[str, Any]) -> None:
    """Synchronize one action/manifest step with its regenerated diff metrics."""
    step_record["dom_diff"] = str((step_dir / "dom_diff.json").relative_to(run_dir))
    step_record["dom_diff_text"] = str((step_dir / "dom_diff.txt").relative_to(run_dir))
    step_record["dom_diff_status"] = record["status"]
    step_record["dom_diff_change_count"] = record["change_count"]
    artifact = record.get("artifact") if isinstance(record.get("artifact"), dict) else {}
    step_record["dom_diff_json_lines"] = int(artifact.get("json_lines") or 0)
    step_record["dom_diff_json_bytes"] = int(artifact.get("json_bytes") or 0)
    step_record["dom_diff_over_size_limit"] = bool(artifact.get("over_size_limit"))
    step_record.pop("dom_diff_over_line_limit", None)


def backfill_run(run_dir: Path, *, rerender: bool = False) -> dict[str, Any]:
    """Recompute stored diffs without a browser; rerendering is opt-in.

    Existing model/full renders are preserved before an explicit rerender so the
    evidence originally consumed by the action model is never silently replaced.
    """
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise RunnerError(f"backfill run directory does not exist: {run_dir}")
    manifest_path = run_dir / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(loaded_manifest, dict):
            raise RunnerError(f"manifest is not a JSON object: {manifest_path}")
        manifest = loaded_manifest
    apply_diff_metadata(manifest)
    current_renderer_versions = renderer_versions()
    manifest.setdefault("model_input_renderer", {"status": "unknown_legacy"})

    manifest_steps = {
        int(item.get("step")): item
        for item in manifest.get("steps", []) or []
        if isinstance(item, dict) and isinstance(item.get("step"), int)
    }
    complete = 0
    unsafe = 0
    status_counts: Counter[str] = Counter()
    rerendered_snapshots = 0
    preserved_original_renders: list[str] = []
    incomplete: list[str] = []
    previous_diff_state_counts: Counter[str] = Counter()
    previously_broken_repaired: list[dict[str, Any]] = []
    semantic_zero_recomputed: list[str] = []
    oversized_diffs: list[dict[str, Any]] = []
    if rerender:
        for snapshot_path in sorted(run_dir.rglob("dom.json")):
            preserved = preserve_original_renders(snapshot_path)
            preserved_original_renders.extend(
                str(Path(path).relative_to(run_dir)) for path in preserved
            )
            render_stored_snapshot(snapshot_path)
            rerendered_snapshots += 1
    steps_root = run_dir / "steps"
    step_dirs = sorted(path for path in steps_root.glob("step_*") if path.is_dir()) if steps_root.exists() else []
    for step_dir in step_dirs:
        before_path = step_dir / "before" / "dom.json"
        after_path = step_dir / "after" / "dom.json"
        if not before_path.exists() or not after_path.exists():
            incomplete.append(str(step_dir.relative_to(run_dir)))
            continue
        diff_path = step_dir / "dom_diff.json"
        previous_state = previous_dom_diff_state(diff_path)
        previous_diff_state_counts[previous_state] += 1
        action_path = step_dir / "action.json"
        action_record: dict[str, Any] | None = None
        action_type: str | None = None
        if action_path.exists():
            loaded_action = json.loads(action_path.read_text(encoding="utf-8"))
            if isinstance(loaded_action, dict):
                action_record = loaded_action
                action_value = action_record.get("action")
                if isinstance(action_value, dict):
                    action_type = clean_dom_text(action_value.get("action")) or None
                elif isinstance(action_value, str):
                    action_type = clean_dom_text(action_value) or None
                if action_type is None:
                    action_type = clean_dom_text(action_record.get("action_type")) or None
        record = write_dom_diff_files(
            before_path, after_path, diff_path, action_type=action_type
        )
        complete += 1
        status_counts[str(record["status"])] += 1
        if record["status"] == "unsafe_node_identity":
            unsafe += 1
        artifact = record.get("artifact") if isinstance(record.get("artifact"), dict) else {}
        if artifact.get("over_size_limit"):
            oversized_diffs.append(
                {
                    "step": step_dir.name,
                    "json_lines": int(artifact.get("json_lines") or 0),
                    "json_bytes": int(artifact.get("json_bytes") or 0),
                    "max_json_bytes": MAX_DOM_DIFF_JSON_BYTES,
                }
            )
        try:
            step_number = int(step_dir.name.removeprefix("step_"))
        except ValueError:
            step_number = -1
        if previous_state in {
            "missing",
            "invalid_json",
            "empty_payload",
            "missing_native_diff",
            "empty_diff_payload",
            "invalid_change_count",
        } and record["change_count"]:
            previously_broken_repaired.append(
                {"step": step_dir.name, **diff_report_summary(record)}
            )
        if previous_state == "semantic_zero":
            semantic_zero_recomputed.append(step_dir.name)
        if action_record is not None:
            action_record.setdefault("model_input_renderer", {"status": "unknown_legacy"})
            if rerender:
                action_record["backfill_renderer"] = current_renderer_versions
            update_step_diff_metadata(action_record, step_dir, run_dir, record)
            write_json(action_path, action_record)
        if step_number in manifest_steps:
            manifest_steps[step_number].setdefault(
                "model_input_renderer", {"status": "unknown_legacy"}
            )
            if rerender:
                manifest_steps[step_number]["backfill_renderer"] = current_renderer_versions
            update_step_diff_metadata(manifest_steps[step_number], step_dir, run_dir, record)

    manifest["dom_diff_backfill"] = {
        "completed_at": utc_now(),
        "complete_steps": complete,
        "unsafe_identity_steps": unsafe,
        "status_counts": dict(status_counts),
        "rerender_requested": rerender,
        "rerendered_snapshots": rerendered_snapshots,
        "backfill_renderer": current_renderer_versions if rerender else None,
        "preserved_original_renders": preserved_original_renders,
        "previous_diff_state_counts": dict(previous_diff_state_counts),
        "incomplete_step_directories": incomplete,
        "oversized_diffs": oversized_diffs,
    }
    if manifest_path.exists() or manifest:
        write_json(manifest_path, manifest)
    return {
        "run_directory": str(run_dir),
        "complete_steps_backfilled": complete,
        "unsafe_identity_steps": unsafe,
        "status_counts": dict(status_counts),
        "rerender_requested": rerender,
        "rerendered_snapshots": rerendered_snapshots,
        "preserved_original_renders": preserved_original_renders,
        "previous_diff_state_counts": dict(previous_diff_state_counts),
        "incomplete_step_directories": incomplete,
        "previously_broken_repaired": previously_broken_repaired,
        "semantic_zero_recomputed": semantic_zero_recomputed,
        "oversized_diffs": oversized_diffs,
    }


