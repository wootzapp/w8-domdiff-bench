#!/usr/bin/env python3
"""Supported integration contract for task-recorder ``dom_diff.json``.

``ARTIFACT_VERSION`` must be bumped whenever a field is added, removed, or
changes meaning in the DOM-diff artifact. Consumers should import this module
instead of branching on the raw same-document and cross-document shapes.

This module is intentionally standalone: it imports no recorder code and can be
vendored by verifier pipelines.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


ARTIFACT_VERSION = "1.0"
ARTIFACT_NAME = "local_slim_dom_semantic_diff"

FIELD_ARTIFACT_VERSION = "artifact_version"
FIELD_SCHEMA_VERSION = "schema_version"  # legacy alias accepted by validate()
FIELD_METHOD = "method"
FIELD_CROSS_DOCUMENT = "cross_document"
FIELD_NAVIGATION = "navigation"
FIELD_TEXT_DELTA = "text_delta"
FIELD_TOP_ACTIONS = "top_actions"
FIELD_DOCUMENT = "document"
FIELD_STATS = "stats"
FIELD_FRAMES = "frames"
FIELD_ENRICHMENT = "enrichment"
FIELD_PATHS = "paths"
FIELD_ADDED = "added"
FIELD_REMOVED = "removed"
FIELD_CHANGED = "changed"
FIELD_FLAGGED_CHANGES = "flagged_changes"

SHARED_FIELDS = {
    FIELD_ARTIFACT_VERSION,
    FIELD_SCHEMA_VERSION,
    FIELD_METHOD,
    "captured_at",
    FIELD_CROSS_DOCUMENT,
    FIELD_NAVIGATION,
    "source",
    FIELD_FRAMES,
    FIELD_ENRICHMENT,
    "key_population",
    FIELD_STATS,
    "format",
    FIELD_PATHS,
}

SAME_DOCUMENT_FIELDS = {
    FIELD_ADDED,
    FIELD_REMOVED,
    FIELD_CHANGED,
    FIELD_FLAGGED_CHANGES,
}

CROSS_DOCUMENT_FIELDS = {
    FIELD_TEXT_DELTA,
    FIELD_DOCUMENT,
    FIELD_TOP_ACTIONS,
}

CHANGE_KIND_PREFIXES = (
    "text",
    "visibility",
    "moved",
    "attr:",
    "style:",
)

EVIDENCE_KINDS = {
    "text_added",
    "text_removed",
    "element_added",
    "element_removed",
    "element_changed",
    "collapse_root",
    "document_text",
}


def _version(diff: dict[str, Any]) -> str | None:
    version = diff.get(FIELD_ARTIFACT_VERSION, diff.get(FIELD_SCHEMA_VERSION))
    return str(version) if version is not None else None


def validate(diff: dict[str, Any]) -> None:
    """Validate a ``dom_diff.json`` object.

    Raises ``ValueError`` with a specific message. Accepts both same-document
    and cross-document shapes. Older artifacts that only carry
    ``schema_version`` are accepted as the same version.
    """

    if not isinstance(diff, dict):
        raise ValueError("dom_diff must be a JSON object")
    version = _version(diff)
    if version != ARTIFACT_VERSION:
        raise ValueError(f"unknown artifact_version: {version!r}")
    if diff.get(FIELD_METHOD) != ARTIFACT_NAME:
        raise ValueError(f"wrong artifact name: expected {ARTIFACT_NAME!r}, got {diff.get(FIELD_METHOD)!r}")
    if not isinstance(diff.get(FIELD_STATS), dict):
        raise ValueError("missing stats block")
    if not isinstance(diff.get(FIELD_FRAMES), dict):
        raise ValueError("missing frames block")
    if FIELD_CROSS_DOCUMENT not in diff:
        raise ValueError("missing cross_document flag")

    if is_cross_document(diff):
        for key in (FIELD_NAVIGATION, FIELD_TEXT_DELTA):
            if not isinstance(diff.get(key), dict):
                raise ValueError(f"cross_document diff missing {key}")
        has_compact_payload = isinstance(diff.get(FIELD_DOCUMENT), dict) and isinstance(diff.get(FIELD_TOP_ACTIONS), list)
        has_full_payload = isinstance(diff.get("document_added"), dict) and isinstance(diff.get("document_removed"), dict)
        if not (has_compact_payload or has_full_payload):
            raise ValueError("cross_document diff missing document/top_actions or document_added/document_removed")
    else:
        for key in (FIELD_ADDED, FIELD_REMOVED, FIELD_CHANGED, FIELD_FLAGGED_CHANGES):
            if not isinstance(diff.get(key), list):
                raise ValueError(f"same_document diff missing {key}")


def is_cross_document(diff: dict[str, Any]) -> bool:
    return bool(diff.get(FIELD_CROSS_DOCUMENT))


def _entry_text(entry: dict[str, Any]) -> str:
    if not isinstance(entry, dict):
        return ""
    text = entry.get("text") or entry.get("visible_text") or entry.get("context") or ""
    if not text and isinstance(entry.get("changes"), dict):
        change = entry["changes"].get("text")
        if isinstance(change, dict):
            text = change.get("after") or change.get("before") or ""
    return " ".join(str(text).split())


def _yield_collapse(entry: dict[str, Any], *, source: str, descendant_kind: str) -> Iterator[dict[str, Any]]:
    yield {"kind": "collapse_root", "text": _entry_text(entry), "element": entry, "source": source}
    descendants = entry.get("interactive_descendants")
    if isinstance(descendants, list):
        for child in descendants:
            if isinstance(child, dict):
                yield {"kind": descendant_kind, "text": _entry_text(child), "element": child, "source": source + ".interactive_descendants"}


def iter_evidence_entries(diff: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield a normalized evidence stream from either diff shape.

    Each yielded dict has ``kind``, ``text``, ``element``, and ``source``.
    ``kind`` is one of ``EVIDENCE_KINDS``.
    """

    validate(diff)
    if is_cross_document(diff):
        text_delta = diff.get(FIELD_TEXT_DELTA) or {}
        for text in text_delta.get("added", []) if isinstance(text_delta.get("added"), list) else []:
            yield {"kind": "text_added", "text": str(text), "element": None, "source": "text_delta.added"}
        for text in text_delta.get("removed", []) if isinstance(text_delta.get("removed"), list) else []:
            yield {"kind": "text_removed", "text": str(text), "element": None, "source": "text_delta.removed"}
        for key in ("document_added", "document_removed"):
            document = diff.get(key)
            if isinstance(document, dict):
                yield {"kind": "document_text", "text": _entry_text(document), "element": document, "source": key}
        for action in diff.get(FIELD_TOP_ACTIONS, []) if isinstance(diff.get(FIELD_TOP_ACTIONS), list) else []:
            if isinstance(action, dict):
                yield {"kind": "element_added", "text": _entry_text(action), "element": action, "source": FIELD_TOP_ACTIONS}
        for action in diff.get("interactive_added", []) if isinstance(diff.get("interactive_added"), list) else []:
            if isinstance(action, dict):
                yield {"kind": "element_added", "text": _entry_text(action), "element": action, "source": "interactive_added"}
        return

    for section, kind, descendant_kind in (
        (FIELD_ADDED, "element_added", "element_added"),
        (FIELD_REMOVED, "element_removed", "element_removed"),
    ):
        for entry in diff.get(section, []):
            if not isinstance(entry, dict):
                continue
            if entry.get("kind") == "group" or entry.get("descendant_count") or entry.get("visible_text"):
                yield from _yield_collapse(entry, source=section, descendant_kind=descendant_kind)
            else:
                yield {"kind": kind, "text": _entry_text(entry), "element": entry, "source": section}
    for section in (FIELD_CHANGED, FIELD_FLAGGED_CHANGES):
        for entry in diff.get(section, []):
            if isinstance(entry, dict):
                yield {"kind": "element_changed", "text": _entry_text(entry), "element": entry, "source": section}
