"""Strict input adapter for the DOM-diff-summary verifier only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from webeval.rubric_agent.dom_diff_adapter import (
    DOMDiffTrajectory,
    build_dom_diff_input,
    discover_dom_diff_paths,
    ordered_action_events,
)


def build_dom_diff_summary_input(
    task_data: dict[str, Any],
    candidate: DOMDiffTrajectory,
    *,
    redo_eval: bool = False,
) -> dict[str, Any]:
    """Build inherited agent input with summary paths as the sole state evidence.

    The shared datapoint extractor knows ``dom_diff_path`` but not the newer
    ``dom_diff_summary_path`` field.  The raw adapter therefore transports the
    summary path through that legacy field.  This summary-only boundary restores
    the explicit field and clears the legacy one before evidence loading.
    """
    value = build_dom_diff_input(
        task_data,
        candidate,
        redo_eval=redo_eval,
        evidence_source="dom_diff_summary",
    )
    actions = ordered_action_events(candidate)
    paths = discover_dom_diff_paths(
        candidate.path, len(actions), evidence_source="dom_diff_summary"
    )
    dom_actions = value.get("dom_actions") or []
    if len(dom_actions) != len(paths):
        raise ValueError(
            f"Action/summary mismatch: {len(actions)} actions, {len(dom_actions)} action records, "
            f"{len(paths)} summaries"
        )
    for ordinal, (action, path) in enumerate(zip(dom_actions, paths), start=1):
        resolved = str(Path(path).resolve(strict=False))
        if Path(resolved).name != "dom_diff_summary.json":
            raise ValueError(f"Forbidden non-summary evidence path: {resolved}")
        action["id"] = ordinal
        action["dom_action_ordinal"] = ordinal
        action["dom_diff_summary_path"] = resolved
        action["dom_diff_path"] = ""
        action["dom_before_snapshot_path"] = ""
        action["dom_after_snapshot_path"] = ""
        action["dom_before_page_state_path"] = ""
        action["dom_after_page_state_path"] = ""
        action["dom_verifier_action_path"] = ""
        action["dom_coverage_status"] = "summary_only"
    value["requested_evidence_mode"] = "dom_diff_summary"
    value["declared_evidence_paths"] = [str(path) for path in paths]
    return value


def validate_summary_input_paths(input_dict: dict[str, Any], action_count: int) -> None:
    actions = input_dict.get("dom_actions") or []
    if len(actions) != action_count:
        raise ValueError(
            f"Action/summary mismatch: {action_count} actions, {len(actions)} summaries"
        )
    declared: list[str] = []
    for ordinal, action in enumerate(actions, start=1):
        if int(action.get("dom_action_ordinal") or 0) != ordinal:
            raise ValueError(
                f"Summary actions must be contiguous: expected {ordinal}, "
                f"got {action.get('dom_action_ordinal')}"
            )
        path = str(action.get("dom_diff_summary_path") or "")
        if not path or Path(path).name != "dom_diff_summary.json":
            raise ValueError(f"Action {ordinal} has no valid summary-only path")
        forbidden = {
            key: action.get(key)
            for key in (
                "dom_diff_path",
                "dom_before_snapshot_path",
                "dom_after_snapshot_path",
                "dom_before_page_state_path",
                "dom_after_page_state_path",
                "dom_verifier_action_path",
            )
            if action.get(key)
        }
        if forbidden:
            raise ValueError(
                f"Action {ordinal} exposes forbidden summary-mode evidence: {forbidden}"
            )
        declared.append(str(Path(path).resolve(strict=False)))
    expected = [
        str(Path(path).resolve(strict=False))
        for path in input_dict.get("declared_evidence_paths") or []
    ]
    if declared != expected:
        raise ValueError(
            "Declared summary evidence paths do not match action-aligned summary paths"
        )

