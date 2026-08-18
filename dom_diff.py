"""Runtime rendering and prompt projections for browser-produced DOM diffs.

ChromiumRL.captureSnapshotDiff computes every live diff. This module never
compares two snapshots and never creates evidence after a task step; it only
normalizes shared text, renders the browser result, and builds bounded prompt
views from the already-persisted result.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

# Persisted diffs are not cut at this size: it is an audit warning threshold.
MAX_DOM_DIFF_JSON_BYTES = 500 * 1024
# These caps affect only valid JSON summaries sent to the model/reviewer.
# dom_diff.json and dom_diff.txt retain every compared entry.
MAX_MODEL_DOM_DIFF_ENTRIES = 32
MAX_TERMINATION_REVIEW_DIFF_ENTRIES_PER_STEP = 8


def clean_dom_text(value: Any) -> str:
    """Normalize whitespace for matching while preserving visible characters."""
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()

def entry_text_fragment(entry: dict[str, Any], *, limit: int = 180) -> str:
    """Recoverable semantic summary for ranked selection and dropped evidence."""
    candidates: list[str] = []
    for key in ("visible_text", "sample_summaries"):
        value = entry.get(key)
        if isinstance(value, list):
            candidates.extend(clean_dom_text(item) for item in value)
        else:
            candidates.append(clean_dom_text(value))
    node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
    for key in ("directText", "accessibleName"):
        candidates.append(clean_dom_text(node.get(key)))
    fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else {}
    for key in ("directText", "accessibleName", "selectedAttributes", "states", "actionTypes"):
        change = fields.get(key)
        if not isinstance(change, dict):
            continue
        for side in ("after", "before"):
            value = change.get(side)
            if value not in (None, "", [], {}):
                candidates.append(clean_dom_text(json.dumps(value, ensure_ascii=False)))
    fragment = next((value for value in candidates if value), "")
    return fragment if len(fragment) <= limit else fragment[: limit - 1].rstrip() + "…"

def entry_priority(entry: dict[str, Any]) -> tuple[int, int, int, int, str]:
    """Semantic facts outrank wrapper/path-only entries before truncation."""
    fragment = entry_text_fragment(entry)
    fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else {}
    node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
    has_action = bool(node.get("actionTypes") or "actionTypes" in fields)
    has_state = bool(node.get("states") or "states" in fields)
    has_numeric = bool(re.search(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?(?!\w)", fragment))
    has_text = bool(fragment)
    score = (8 if has_action else 0) + (6 if has_state else 0) + (4 if has_numeric else 0) + (2 if has_text else 0)
    return (-score, -int(has_text), -int(has_numeric), -int(has_state or has_action), str(entry.get("path", "")))

def model_diff_entry_summary(operation: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Compact one diff entry without cutting its JSON representation."""
    summary: dict[str, Any] = {
        "operation": operation,
        "kind": entry.get("kind", "node"),
    }
    for key in ("path", "path_before", "path_after"):
        value = clean_dom_text(entry.get(key))
        if value:
            summary[key] = value[:400]
    sample_paths = entry.get("sample_paths")
    if isinstance(sample_paths, list) and sample_paths:
        summary["sample_paths"] = [clean_dom_text(path)[:400] for path in sample_paths[:3]]
    fragment = entry_text_fragment(entry, limit=320)
    if fragment:
        summary["text_fragment"] = fragment
    fields = entry.get("fields")
    if isinstance(fields, dict) and fields:
        summary["changed_fields"] = sorted(str(name) for name in fields)
    node = entry.get("node")
    if isinstance(node, dict):
        facts: dict[str, Any] = {}
        for key in ("tag", "role", "semanticBoundary"):
            value = clean_dom_text(node.get(key))
            if value:
                facts[key] = value
        for key in ("actionTypes", "states"):
            value = node.get(key)
            if value not in (None, [], {}):
                facts[key] = value
        if facts:
            summary["node"] = facts
    for key in ("count", "descendant_count", "document_percent", "signature"):
        if entry.get(key) not in (None, ""):
            summary[key] = entry[key]
    return summary

def bounded_dom_diff_for_model(
    record: dict[str, Any] | None,
    *,
    max_entries: int = MAX_MODEL_DOM_DIFF_ENTRIES,
) -> dict[str, Any]:
    """Build valid, bounded JSON evidence from a potentially large DOM diff."""
    if not isinstance(record, dict) or not record:
        return {}

    compression = record.get("compression") if isinstance(record.get("compression"), dict) else {}
    diff = record.get("diff") if isinstance(record.get("diff"), dict) else {}
    text_delta = diff.get("text_delta") if isinstance(diff.get("text_delta"), dict) else {}
    summary: dict[str, Any] = {
        "status": record.get("status"),
        "action_type": record.get("action_type"),
        "totals": record.get("totals", {}),
        "emitted_counts": record.get("emitted_counts", {}),
        "entries_truncated": compression.get(
            "entries_truncated", text_delta.get("truncated", {})
        ),
    }

    viewport = diff.get("viewport_delta") if isinstance(diff.get("viewport_delta"), dict) else {}
    if viewport:
        summary["viewport_delta"] = {
            "aggregation": viewport.get("aggregation"),
            "viewport_state": viewport.get("viewport_state", {}),
            "geometry": viewport.get("geometry", {}),
        }

    operations: dict[str, list[dict[str, Any]]] = {}
    for operation in ("added", "removed", "changed"):
        rows = diff.get(operation)
        if isinstance(rows, list):
            operations[operation] = [row for row in rows if isinstance(row, dict)]
    for operation, key in (("added_text", "added"), ("removed_text", "removed")):
        rows = text_delta.get(key)
        if isinstance(rows, list):
            operations[operation] = [
                {
                    "kind": "text",
                    "path": f"{operation}[{position}]",
                    "node": {"directText": clean_dom_text(value)},
                }
                for position, value in enumerate(rows, start=1)
                if clean_dom_text(value)
            ]
    for operation, key in (
        ("viewport_entered", "visible_text_entered"),
        ("viewport_exited", "visible_text_exited"),
    ):
        rows = viewport.get(key)
        if isinstance(rows, list):
            operations[operation] = [
                {
                    "kind": "viewport_text",
                    "path": f"{operation}[{position}]",
                    "node": {"directText": clean_dom_text(value)},
                }
                for position, value in enumerate(rows, start=1)
                if clean_dom_text(value)
            ]

    ranked = {
        operation: sorted(rows, key=entry_priority)
        for operation, rows in operations.items()
        if rows
    }
    available = {operation: len(rows) for operation, rows in ranked.items()}
    selected: dict[str, list[dict[str, Any]]] = {operation: [] for operation in ranked}
    selected_keys: set[tuple[str, int]] = set()
    nonempty = list(ranked)
    limit = max(0, int(max_entries))
    if limit and sum(available.values()) <= limit:
        selected = {operation: list(rows) for operation, rows in ranked.items()}
    elif limit and nonempty:
        guaranteed_share = max(1, limit // (2 * len(nonempty)))
        for operation in nonempty:
            for position, entry in enumerate(ranked[operation][:guaranteed_share]):
                selected[operation].append(entry)
                selected_keys.add((operation, position))
        remaining = max(0, limit - sum(len(rows) for rows in selected.values()))
        candidates = sorted(
            (
                entry_priority(entry),
                operation,
                position,
                entry,
            )
            for operation, rows in ranked.items()
            for position, entry in enumerate(rows)
            if (operation, position) not in selected_keys
        )
        for _priority, operation, _position, entry in candidates[:remaining]:
            selected[operation].append(entry)

    included = {operation: len(rows) for operation, rows in selected.items()}
    summary["model_evidence"] = {
        "entry_limit": limit,
        "available_counts": available,
        "included_counts": included,
        "entries_truncated": {
            operation: available[operation] - included.get(operation, 0)
            for operation in available
        },
        "selection": "balanced_operation_share_then_entry_priority",
        "entries": [
            model_diff_entry_summary(operation, entry)
            for operation, rows in selected.items()
            for entry in sorted(rows, key=entry_priority)
        ],
    }
    return summary

def bounded_dom_diff_history_for_review(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep evidence from every executed step in valid, bounded JSON.

    The artifact itself is never truncated. Only the separate reviewer prompt is
    bounded per step, so an early source page remains available in cross-site
    tasks without allowing one large navigation diff to consume the whole input.
    """
    history: list[dict[str, Any]] = []
    for step, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        history.append(
            {
                "step": step,
                "before": record.get("before", {}),
                "after": record.get("after", {}),
                "evidence": bounded_dom_diff_for_model(
                    record,
                    max_entries=MAX_TERMINATION_REVIEW_DIFF_ENTRIES_PER_STEP,
                ),
            }
        )
    return history

def same_document_except_fragment(before_url: str, after_url: str) -> bool:
    """Return whether only the URL fragment may differ."""
    before = urlsplit(before_url)
    after = urlsplit(after_url)
    return (
        before.scheme.lower(),
        before.netloc.lower(),
        before.path,
        before.query,
    ) == (
        after.scheme.lower(),
        after.netloc.lower(),
        after.path,
        after.query,
    )

def dom_diff_text(record: dict[str, Any]) -> str:
    """Render the JSON diff as one verifier-friendly fact per line."""
    def encoded(value: Any) -> str:
        """Serialize nested facts deterministically on a single line."""
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    lines = [
        f"source: {record.get('source')}",
        f"interval: {record.get('interval')}",
        f"status: {record.get('status')}",
        f"action_type: {record.get('action_type')}",
        f"geometry_excluded: {str(bool(record.get('geometry_excluded'))).lower()}",
        f"covers_live_control_state: {str(bool(record.get('covers_live_control_state'))).lower()}",
        f"before: {encoded(record.get('before'))}",
        f"after: {encoded(record.get('after'))}",
        f"change_count: {record.get('change_count', 0)}",
        f"totals: {encoded(record.get('totals', {}))}",
        f"emitted_counts: {encoded(record.get('emitted_counts', {}))}",
        f"identity: {encoded(record.get('identity', {}))}",
        f"compression: {encoded(record.get('compression', {}))}",
    ]
    diff = record.get("diff") if isinstance(record.get("diff"), dict) else {}
    if record.get("status") == "document_replaced":
        lines.append(f"navigation: {encoded(diff.get('navigation'))}")
        lines.append(f"removed_node_count: {diff.get('removed_node_count', 0)}")
        lines.append(f"added_node_count: {diff.get('added_node_count', 0)}")
        text_delta = diff.get("text_delta") if isinstance(diff.get("text_delta"), dict) else {}
        lines.extend(f"text_removed: {encoded(text)}" for text in text_delta.get("removed", []) or [])
        lines.extend(f"text_added: {encoded(text)}" for text in text_delta.get("added", []) or [])
    elif record.get("status") == "unsafe_node_identity":
        lines.extend(f"identity_error: {encoded(error)}" for error in diff.get("errors", []) or [])
    else:
        lines.extend(f"node_added: {encoded(item)}" for item in diff.get("added", []) or [])
        lines.extend(f"node_removed: {encoded(item)}" for item in diff.get("removed", []) or [])
        for item in diff.get("changed", []) or []:
            path = item.get("path")
            semantic = str(item.get("semantic") is True).lower()
            fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
            for field, change in fields.items():
                lines.append(
                    f"node_changed: semantic={semantic} path={encoded(path)} "
                    f"field={field} change={encoded(change)}"
                )
        indexes = diff.get("indexes") if isinstance(diff.get("indexes"), dict) else {}
        lines.extend(
            f"subtree_index: {encoded(item)}"
            for item in indexes.get("subtrees", []) or []
        )
        lines.extend(
            f"repeated_group_index: {encoded(item)}"
            for item in indexes.get("repeated_groups", []) or []
        )
        viewport = diff.get("viewport_delta") if isinstance(diff.get("viewport_delta"), dict) else {}
        if viewport:
            lines.append(f"viewport_state: {encoded(viewport.get('viewport_state', {}))}")
            lines.append(f"viewport_geometry: {encoded(viewport.get('geometry', {}))}")
            lines.extend(
                f"visible_text_entered: {encoded(text)}"
                for text in viewport.get("visible_text_entered", []) or []
            )
            lines.extend(
                f"visible_text_exited: {encoded(text)}"
                for text in viewport.get("visible_text_exited", []) or []
            )
    return "\n".join(lines).rstrip() + "\n"
