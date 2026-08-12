"""Strict loading and bounded projection for DOM-diff-only evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from webeval.rubric_agent.dom_evidence import (
    SemanticDOMDiff,
    project_retrieved_diff,
)


CHROMIUMRL_DIFF_SCHEMA = "chromiumrl-dom-diff/v1"
_CHANGE_SECTIONS = (
    "textChanges",
    "insertions",
    "deletions",
    "attributeChanges",
    "moves",
    "typeChanges",
    "layoutChanges",
    "styleChanges",
)


@dataclass(frozen=True)
class DOMDiffEvidenceFrame:
    """One validated diff aligned to exactly one logged action."""

    action_ordinal: int
    action_id: str
    diff_path: str
    diff: SemanticDOMDiff | dict[str, Any]
    schema_version: str
    method: str
    reference: str
    current: str
    capture_status: str
    coverage_status: str = "diff_only"

    # Compatibility attributes used by the inherited task-aware term builder.
    verifier_action: None = None
    before_page_state: None = None
    after_page_state: None = None
    before_snapshot: None = None
    snapshot: None = None


def _load_json_object(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"DOM diff file not found: {resolved}")
    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"DOM diff must be a JSON object: {resolved}")
    return payload


def load_dom_diff(path: str | Path) -> SemanticDOMDiff | dict[str, Any]:
    """Validate a supported diff without following any snapshot references."""
    payload = _load_json_object(path)
    if payload.get("schema_version") == "semantic-dom-diff/v1":
        return SemanticDOMDiff.model_validate(payload)

    schema = str(payload.get("schema_version") or "")
    method = str(payload.get("method") or "")
    if schema not in {"1.0", CHROMIUMRL_DIFF_SCHEMA}:
        raise ValueError(f"Unsupported ChromiumRL DOM diff schema {schema!r}: {path}")
    if method != "ChromiumRL.compareDOMState":
        raise ValueError(f"Unsupported DOM diff method {method!r}: {path}")

    result = payload.get("chromiumrl_result")
    if result is None:
        result = payload.get("chromiumrl_response")
    if not isinstance(result, dict):
        raise ValueError(f"ChromiumRL DOM diff has no result object: {path}")
    for section in _CHANGE_SECTIONS:
        value = result.get(section, [])
        if not isinstance(value, list):
            raise ValueError(
                f"ChromiumRL DOM diff section {section!r} must be a list: {path}"
            )
    timing = payload.get("timing")
    if timing is not None and not isinstance(timing, dict):
        raise ValueError(f"ChromiumRL DOM diff timing must be an object: {path}")
    return payload


def _capture_status(diff: SemanticDOMDiff | dict[str, Any]) -> str:
    if isinstance(diff, SemanticDOMDiff):
        return "complete"
    timing = diff.get("timing") or {}
    if timing.get("ok") is False:
        return "failed"
    return "complete"


def load_dom_diff_frames(
    actions: Iterable[dict[str, Any]],
) -> list[DOMDiffEvidenceFrame]:
    """Load only the diff path from each already aligned action descriptor."""
    frames: list[DOMDiffEvidenceFrame] = []
    for position, action in enumerate(actions, start=1):
        ordinal = int(action.get("dom_action_ordinal") or action.get("id") or 0)
        if ordinal != position:
            raise ValueError(
                "DOM diff actions must be contiguous and ordered: "
                f"expected {position}, got {ordinal}"
            )
        diff_path = str(action.get("dom_diff_path") or "")
        if not diff_path:
            raise ValueError(f"Action {ordinal} has no DOM diff path")
        diff = load_dom_diff(diff_path)
        if isinstance(diff, SemanticDOMDiff):
            schema_version = diff.schema_version
            method = "semantic-dom-diff"
            reference = diff.from_snapshot_id
            current = diff.to_snapshot_id
        else:
            schema_version = CHROMIUMRL_DIFF_SCHEMA
            method = str(diff.get("method") or "")
            reference = str(diff.get("reference") or "")
            current = str(diff.get("current") or "")
        frames.append(
            DOMDiffEvidenceFrame(
                action_ordinal=ordinal,
                action_id=str(action.get("dom_action_id") or ordinal),
                diff_path=diff_path,
                diff=diff,
                schema_version=schema_version,
                method=method,
                reference=reference,
                current=current,
                capture_status=str(action.get("dom_capture_status") or _capture_status(diff)),
                coverage_status=str(action.get("dom_coverage_status") or "diff_only"),
            )
        )
    return frames


def summarize_diff(diff: SemanticDOMDiff | dict[str, Any]) -> dict[str, Any]:
    """Return small capture metadata without returning change payloads."""
    if isinstance(diff, SemanticDOMDiff):
        return {
            "added": len(diff.added),
            "removed": len(diff.removed),
            "updated": len(diff.updated),
            "unchanged_count": diff.unchanged_count,
        }
    result = diff.get("chromiumrl_result") or diff.get("chromiumrl_response") or {}
    summary = result.get("summary") if isinstance(result, dict) else None
    counts = {
        section: len(result.get(section) or [])
        for section in _CHANGE_SECTIONS
        if isinstance(result, dict)
    }
    return {"summary": summary if isinstance(summary, dict) else {}, "changes": counts}


def project_dom_diff_frame(
    frame: DOMDiffEvidenceFrame,
    *,
    terms: list[str],
    frame_char_budget: int = 16000,
) -> str:
    """Project explicit changes only, with explicit modality limitations."""
    header = (
        f"DOM DIFF FRAME {frame.action_ordinal} action_id={frame.action_id or 'N/A'}\n"
        f"schema={frame.schema_version}; method={frame.method}; "
        f"reference_id={frame.reference or 'unspecified'}; "
        f"current_id={frame.current or 'unspecified'}; "
        f"capture={frame.capture_status}; coverage={frame.coverage_status}\n"
        "DECLARED OMISSIONS: no before snapshot, no after snapshot, no page state, "
        "no screenshot, no URL/title/viewport/scroll evidence unless explicitly "
        "recorded as a change inside this diff.\n"
        "RETRIEVED EXPLICIT CHANGES:\n"
    )
    remaining = max(1, frame_char_budget - len(header))
    body = project_retrieved_diff(frame.diff, terms=terms, char_budget=remaining)
    return (header + body)[:frame_char_budget]

