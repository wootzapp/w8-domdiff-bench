"""Strict parser and immutable evidence model for refined ``dom_diffN.txt``.

This module reads only the declared recorder-produced text files.  It never
loads screenshots, raw DOM diffs, snapshots, page-state JSON, or verifier
actions.  Source bytes remain authoritative; normalized/compact projections
are attached later without modifying those bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DOM_DIFF_TEXT_SCHEMA = "runner-snapshot-diff-text/v1"
DOM_DIFF_TEXT_SOURCE = "runner_snapshot_diff"
DOM_DIFF_TEXT_INTERVAL = "before_snapshot_to_after_snapshot"

REQUIRED_HEADERS = (
    "source",
    "interval",
    "status",
    "action_type",
    "geometry_excluded",
    "covers_live_control_state",
    "before",
    "after",
    "change_count",
    "totals",
    "emitted_counts",
    "identity",
    "compression",
)
SUPPORTED_STATUSES = {
    "changes_present",
    "document_replaced",
    "viewport_content_changed",
}
SUPPORTED_ACTION_TYPES = {"click", "fill", "navigate", "scroll"}
JSON_HEADERS = {"before", "after", "totals", "emitted_counts", "identity", "compression"}
BOOLEAN_HEADERS = {"geometry_excluded", "covers_live_control_state"}
RECORD_FAMILIES = {
    "navigation",
    "added_node_count",
    "removed_node_count",
    "node_added",
    "node_removed",
    "node_changed",
    "text_added",
    "text_removed",
    "viewport_state",
    "viewport_geometry",
    "visible_text_entered",
    "visible_text_exited",
}
_RECORDS_BY_STATUS = {
    "document_replaced": {
        "navigation",
        "added_node_count",
        "removed_node_count",
        "text_added",
        "text_removed",
    },
    "changes_present": {
        "node_added",
        "node_removed",
        "node_changed",
        "viewport_state",
        "viewport_geometry",
        "visible_text_entered",
        "visible_text_exited",
    },
    "viewport_content_changed": {
        "viewport_state",
        "viewport_geometry",
        "visible_text_entered",
        "visible_text_exited",
    },
}
_NODE_PAYLOAD_KEYS = {
    "node": {"kind", "node", "path", "repeated_group_id", "repeated_item_index"},
    "subtree": {
        "kind",
        "node",
        "path",
        "visible_text",
        "subtree_node_count",
        "descendant_count",
        "document_percent",
        "interactive_descendants_total",
        "interactive_descendants",
    },
    "repeated_group": {
        "kind",
        "operation",
        "repeated_group_id",
        "count",
        "item_indices",
        "signature",
        "sample_paths",
        "sample_summaries",
    },
}
_NODE_KEYS = {
    "accessibleName",
    "actionTypes",
    "directText",
    "role",
    "selectedAttributes",
    "semanticBoundary",
    "states",
    "tag",
}
_SIGNATURE_KEYS = {"changed_fields", "kind", "role", "tag"}
_STATE_KEYS = {"snapshot_id", "document_revision", "url"}
_IDENTITY_KEYS = {"before", "after", "strategy"}
_IDENTITY_SIDE_KEYS = {
    "positional_nodes",
    "path_collisions",
    "duplicate_anchor_bases",
    "nodes",
    "duplicate_anchor_nodes",
    "anchored_nodes",
}
_COMPRESSION_KEYS = {
    "collapse_roots",
    "collapsed_descendants",
    "dropped_entries",
    "emitted_before_truncation",
    "entries_truncated",
    "entry_limit",
    "max_collapse_document_percent",
    "noise_nodes_skipped",
    "raw_added_before_relocation_match",
    "raw_removed_before_relocation_match",
    "relocated_nodes_suppressed",
    "relocation_matching",
    "repeated_group_members_condensed",
    "subtree_text_changes_ignored",
    "truncation_selection",
}
_COUNT_TRIPLE_KEYS = {"added", "changed", "removed"}
_VIEWPORT_STATE_KEYS = {
    "entered_nodes",
    "entered_text_total",
    "exited_nodes",
    "exited_text_total",
    "hit_testable_changed_nodes",
    "in_viewport_changed_nodes",
}
_VIEWPORT_GEOMETRY_KEYS = {
    "compared_nodes",
    "dimension_changed_nodes",
    "dominant_shift",
    "movement_clusters_total",
    "per_node_geometry_emitted",
    "shifted_nodes",
    "stationary_nodes",
}
_TEXT_RECORDS = {
    "text_added": ("added", "document_text"),
    "text_removed": ("removed", "document_text"),
    "visible_text_entered": ("viewport_entered", "viewport_text"),
    "visible_text_exited": ("viewport_exited", "viewport_text"),
}
_NODE_CHANGED_RE = re.compile(
    r'^path=(?P<path>"(?:\\.|[^"\\])*") '
    r'field=(?P<field>[^ ]+) change=(?P<change>\{.*\})$'
)
_DIFF_NAME_RE = re.compile(r"^dom_diff([1-9][0-9]*)\.txt$")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate_keys(
    value: Mapping[str, Any],
    *,
    label: str,
    allowed: set[str],
    required: set[str] | None = None,
) -> None:
    unknown = set(value) - allowed
    missing = (required or set()) - set(value)
    if unknown:
        raise ValueError(f"{label} has unsupported v1 keys: {sorted(unknown)}")
    if missing:
        raise ValueError(f"{label} is missing required v1 keys: {sorted(missing)}")


def _parse_json(value: str, *, path: Path, line_number: int, label: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Malformed JSON for {label} in {path} line {line_number}: {exc}"
        ) from exc


def _parse_bool(value: str, *, path: Path, line_number: int, label: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(
        f"{label} must be lowercase true or false in {path} line {line_number}"
    )


def _name_value_pairs(value: Any, *, label: str) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    output: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"name", "value"}:
            raise ValueError(f"{label} entries must contain name and value")
        raw_value = item["value"]
        rendered = raw_value if isinstance(raw_value, str) else _json_text(raw_value)
        output.append((str(item["name"]), rendered))
    return tuple(output)


def _semantic_descendant(value: Any) -> str:
    """Drop an audit-only path while preserving explicit action/label facts."""
    if not isinstance(value, str):
        raise ValueError("interactive_descendants entries must be strings")
    text = value
    parts = text.split(" | ")
    if len(parts) <= 1:
        raise ValueError("interactive_descendant has no path/semantic delimiter")
    return " | ".join(parts[1:])


def _semantic_sample(value: Any) -> str:
    """Drop a repeated-group sample path and retain its explicit summary."""
    if not isinstance(value, str):
        raise ValueError("sample_summaries entries must be strings")
    text = value
    marker = " visible_text="
    if marker in text:
        return "visible_text=" + text.split(marker, 1)[1]
    raise ValueError("sample_summary has no explicit visible_text field")


@dataclass(frozen=True)
class SourceSpan:
    task_id: str
    action_ordinal: int
    source_file: str
    source_line_start: int
    source_line_end: int
    source_line_sha256: str
    chunk_index: int | None = None
    chunk_count: int | None = None

    @property
    def compact_ref(self) -> str:
        if self.source_line_start == self.source_line_end:
            return f"s{self.action_ordinal}:L{self.source_line_start}"
        return (
            f"s{self.action_ordinal}:L{self.source_line_start}-"
            f"L{self.source_line_end}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "action_ordinal": self.action_ordinal,
            "source_file": self.source_file,
            "source_line_start": self.source_line_start,
            "source_line_end": self.source_line_end,
            "source_line_sha256": self.source_line_sha256,
            "chunk_index": self.chunk_index,
            "chunk_count": self.chunk_count,
            "compact_ref": self.compact_ref,
        }


@dataclass(frozen=True)
class SemanticRecord:
    record_id: str
    operation: str
    scope: str
    record_kind: str
    text: str | None = None
    role: str | None = None
    accessible_name: str | None = None
    direct_text: str | None = None
    visible_text: str | None = None
    supported_actions: tuple[str, ...] = ()
    tag: str | None = None
    semantic_boundary: str | None = None
    selected_attributes: tuple[tuple[str, str], ...] = ()
    states: tuple[tuple[str, str], ...] = ()
    changed_field: str | None = None
    before_value: Any = None
    after_value: Any = None
    navigation_from: str | None = None
    navigation_to: str | None = None
    interactive_descendants: tuple[str, ...] = ()
    repeated_group_samples: tuple[str, ...] = ()
    repeated_group_count: int | None = None
    element_context_key: str = ""
    source_spans: tuple[SourceSpan, ...] = ()

    def semantic_key(self) -> tuple[Any, ...]:
        """Exact normalized identity; provenance and record ID are excluded."""
        return (
            self.operation,
            self.scope,
            self.record_kind,
            self.text,
            self.role,
            self.accessible_name,
            self.direct_text,
            self.visible_text,
            self.supported_actions,
            self.tag,
            self.semantic_boundary,
            self.selected_attributes,
            self.states,
            self.changed_field,
            _json_text(self.before_value),
            _json_text(self.after_value),
            self.navigation_from,
            self.navigation_to,
            self.interactive_descendants,
            self.repeated_group_samples,
            self.repeated_group_count,
            self.element_context_key,
        )

    def to_model_dict(self) -> dict[str, Any]:
        """Return semantic fields only; provenance stays in the audit sidecar."""
        return {
            "record_id": self.record_id,
            "operation": self.operation,
            "scope": self.scope,
            "record_kind": self.record_kind,
            "text": self.text,
            "role": self.role,
            "accessible_name": self.accessible_name,
            "direct_text": self.direct_text,
            "visible_text": self.visible_text,
            "supported_actions": list(self.supported_actions),
            "tag": self.tag,
            "semantic_boundary": self.semantic_boundary,
            "selected_attributes": [list(item) for item in self.selected_attributes],
            "states": [list(item) for item in self.states],
            "changed_field": self.changed_field,
            "before_value": self.before_value,
            "after_value": self.after_value,
            "navigation_from": self.navigation_from,
            "navigation_to": self.navigation_to,
            "interactive_descendants": list(self.interactive_descendants),
            "repeated_group_samples": list(self.repeated_group_samples),
            "repeated_group_count": self.repeated_group_count,
        }

    def to_audit_dict(self) -> dict[str, Any]:
        value = self.to_model_dict()
        value["element_context_key"] = self.element_context_key
        value["source_spans"] = [span.to_dict() for span in self.source_spans]
        return value

    def to_dict(self, *, include_audit: bool = True) -> dict[str, Any]:
        if include_audit:
            return self.to_audit_dict()
        return self.to_model_dict()


@dataclass(frozen=True)
class DOMDiffTextAuditReceipt:
    task_id: str
    action_ordinal: int
    source_path: str
    source_bytes: int
    source_sha256: str
    source_line_count: int
    headers: Mapping[str, Any]
    raw_paths: tuple[str, ...]
    repeated_group_sample_paths: tuple[str, ...]
    raw_records: tuple[Mapping[str, Any], ...]
    parsed_record_counts: Mapping[str, int]
    coverage_warnings: tuple[str, ...]
    audit_receipt_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "action_ordinal": self.action_ordinal,
            "source_path": self.source_path,
            "source_bytes": self.source_bytes,
            "source_sha256": self.source_sha256,
            "source_line_count": self.source_line_count,
            "headers": dict(self.headers),
            "raw_paths": list(self.raw_paths),
            "repeated_group_sample_paths": list(self.repeated_group_sample_paths),
            "raw_records": [dict(item) for item in self.raw_records],
            "parsed_record_counts": dict(self.parsed_record_counts),
            "coverage_warnings": list(self.coverage_warnings),
            "audit_receipt_id": self.audit_receipt_id,
        }


@dataclass(frozen=True)
class DOMDiffTextEvidenceFrame:
    action_ordinal: int
    action_id: str
    task_id: str
    text_path: str
    action_type: str
    status: str
    before_url: str
    after_url: str
    before_identity: tuple[str, int]
    after_identity: tuple[str, int]
    navigation: tuple[str, str] | None
    records: tuple[SemanticRecord, ...]
    coverage_warnings: tuple[str, ...]
    audit: DOMDiffTextAuditReceipt
    compact: Any = None
    schema_version: str = DOM_DIFF_TEXT_SCHEMA
    capture_status: str = "complete"
    coverage_status: str = "text_diff_only"
    # Compatibility fields inspected by inherited DOM code.  They must remain
    # empty so text evidence cannot masquerade as raw/full-DOM evidence.
    diff: dict[str, Any] = field(default_factory=dict)
    verifier_action: None = None
    before_page_state: None = None
    after_page_state: None = None
    before_snapshot: None = None
    snapshot: None = None

    @property
    def source_sha256(self) -> str:
        return self.audit.source_sha256

    @property
    def source_bytes(self) -> int:
        return self.audit.source_bytes

    def with_compact(self, compact: Any) -> "DOMDiffTextEvidenceFrame":
        return replace(self, compact=compact)


def _source_span(
    *, task_id: str, action_ordinal: int, path: Path, line_number: int, raw_line: str
) -> SourceSpan:
    return SourceSpan(
        task_id=task_id,
        action_ordinal=action_ordinal,
        source_file=str(path.resolve(strict=False)),
        source_line_start=line_number,
        source_line_end=line_number,
        source_line_sha256=_sha256(raw_line.encode("utf-8")),
    )


def _node_record(
    *,
    payload: dict[str, Any],
    operation: str,
    record_id: str,
    span: SourceSpan,
) -> SemanticRecord:
    kind = str(payload.get("kind") or "")
    if kind not in {"node", "subtree", "repeated_group"}:
        raise ValueError(f"Unsupported node kind {kind!r}")
    _validate_keys(
        payload,
        label=f"{kind} payload",
        allowed=_NODE_PAYLOAD_KEYS[kind],
        required=(
            {"kind", "operation", "repeated_group_id", "count", "item_indices", "signature", "sample_paths", "sample_summaries"}
            if kind == "repeated_group"
            else {"kind", "node", "path"}
        ),
    )
    declared_operation = payload.get("operation")
    if declared_operation is not None and str(declared_operation) != operation:
        raise ValueError(
            f"Node record operation {declared_operation!r} conflicts with {operation!r}"
        )
    if kind == "repeated_group":
        signature = _require_object(payload.get("signature") or {}, label="signature")
        _validate_keys(
            signature,
            label="signature",
            allowed=_SIGNATURE_KEYS,
            required={"changed_fields", "kind", "role", "tag"},
        )
        if not isinstance(signature["changed_fields"], list) or any(
            not isinstance(item, str) for item in signature["changed_fields"]
        ):
            raise ValueError("signature.changed_fields must be an array of strings")
        sample_paths = payload["sample_paths"]
        sample_summaries = payload["sample_summaries"]
        item_indices = payload["item_indices"]
        if not isinstance(sample_paths, list) or any(
            not isinstance(item, str) for item in sample_paths
        ):
            raise ValueError("sample_paths must be an array of strings")
        if not isinstance(sample_summaries, list):
            raise ValueError("sample_summaries must be an array")
        if not isinstance(item_indices, list) or any(
            not isinstance(item, int) or isinstance(item, bool) for item in item_indices
        ):
            raise ValueError("item_indices must be an array of integers")
        if not isinstance(payload["count"], int) or isinstance(payload["count"], bool) or payload["count"] < 0:
            raise ValueError("repeated_group count must be a non-negative integer")
        samples = tuple(
            value
            for value in (_semantic_sample(item) for item in sample_summaries)
            if value
        )
        return SemanticRecord(
            record_id=record_id,
            operation=operation,
            scope="repeated_group",
            record_kind="element",
            role=str(signature.get("role")) if signature.get("role") is not None else None,
            tag=str(signature.get("tag")) if signature.get("tag") is not None else None,
            changed_field=(
                ",".join(str(item) for item in signature.get("changed_fields") or []) or None
            ),
            repeated_group_samples=samples,
            repeated_group_count=int(payload.get("count") or 0),
            element_context_key=str(payload.get("repeated_group_id") or ""),
            source_spans=(span,),
        )

    node = _require_object(payload.get("node") or {}, label="node")
    _validate_keys(node, label="node", allowed=_NODE_KEYS)
    if not isinstance(payload["path"], str) or not payload["path"]:
        raise ValueError(f"{kind} path must be a non-empty string")
    actions = node.get("actionTypes") or []
    if not isinstance(actions, list) or any(not isinstance(item, str) for item in actions):
        raise ValueError("node.actionTypes must be an array of strings")
    raw_descendants = payload.get("interactive_descendants") or []
    if not isinstance(raw_descendants, list):
        raise ValueError("interactive_descendants must be an array")
    descendants = tuple(
        value
        for value in (
            _semantic_descendant(item) for item in raw_descendants
        )
        if value
    )
    return SemanticRecord(
        record_id=record_id,
        operation=operation,
        scope=kind,
        record_kind="element",
        role=str(node.get("role")) if node.get("role") is not None else None,
        accessible_name=(
            str(node.get("accessibleName"))
            if node.get("accessibleName") is not None
            else None
        ),
        direct_text=str(node.get("directText")) if node.get("directText") is not None else None,
        visible_text=(
            str(payload.get("visible_text"))
            if payload.get("visible_text") is not None
            else None
        ),
        supported_actions=tuple(actions),
        tag=str(node.get("tag")) if node.get("tag") is not None else None,
        semantic_boundary=(
            str(node.get("semanticBoundary"))
            if node.get("semanticBoundary") is not None
            else None
        ),
        selected_attributes=_name_value_pairs(
            node.get("selectedAttributes"), label="node.selectedAttributes"
        ),
        states=_name_value_pairs(node.get("states"), label="node.states"),
        interactive_descendants=descendants,
        element_context_key=str(payload.get("path") or ""),
        source_spans=(span,),
    )


def _changed_record(
    *, value: str, record_id: str, span: SourceSpan, path: Path, line_number: int
) -> SemanticRecord:
    match = _NODE_CHANGED_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"Malformed node_changed in {path} line {line_number}")
    raw_path = _parse_json(
        match.group("path"), path=path, line_number=line_number, label="node_changed.path"
    )
    change = _require_object(
        _parse_json(
            match.group("change"),
            path=path,
            line_number=line_number,
            label="node_changed.change",
        ),
        label="node_changed.change",
    )
    if set(change) - {"before", "after"}:
        raise ValueError(
            f"node_changed.change has unsupported keys in {path} line {line_number}"
        )
    return SemanticRecord(
        record_id=record_id,
        operation="changed",
        scope="node",
        record_kind="element_change",
        changed_field=match.group("field"),
        before_value=change.get("before"),
        after_value=change.get("after"),
        element_context_key=str(raw_path),
        source_spans=(span,),
    )


def _validate_state_object(value: Any, *, label: str) -> dict[str, Any]:
    state = _require_object(value, label=label)
    _validate_keys(
        state, label=label, allowed=_STATE_KEYS, required=_STATE_KEYS
    )
    if not isinstance(state["snapshot_id"], str) or not state["snapshot_id"]:
        raise ValueError(f"{label}.snapshot_id must be a non-empty string")
    if not isinstance(state["document_revision"], int):
        raise ValueError(f"{label}.document_revision must be an integer")
    if not isinstance(state["url"], str):
        raise ValueError(f"{label}.url must be a string")
    return state


def _validate_header_arithmetic(
    *,
    path: Path,
    status: str,
    headers: Mapping[str, Any],
    counts: Mapping[str, int],
    records: Sequence[SemanticRecord],
) -> None:
    emitted = _require_object(headers["emitted_counts"], label="emitted_counts")
    totals = _require_object(headers["totals"], label="totals")
    change_count = headers["change_count"]
    if not isinstance(change_count, int) or change_count < 0:
        raise ValueError(f"change_count must be a non-negative integer: {path}")
    for label, values in (("totals", totals), ("emitted_counts", emitted)):
        if any(not isinstance(value, int) or value < 0 for value in values.values()):
            raise ValueError(f"{label} values must be non-negative integers: {path}")

    if status == "document_replaced":
        expected = {
            "added_text": counts.get("text_added", 0),
            "removed_text": counts.get("text_removed", 0),
        }
        for key, actual in expected.items():
            if emitted.get(key) != actual:
                raise ValueError(
                    f"{path}: emitted_counts.{key}={emitted.get(key)!r}, parsed={actual}"
                )
        if totals.get("added_nodes", 0) + totals.get("removed_nodes", 0) != change_count:
            raise ValueError(f"{path}: document-replacement change_count is inconsistent")
        return

    # ``emitted_counts.changed`` counts changed nodes, while the text format
    # emits one ``node_changed`` line per changed field.  Preserve every field
    # record but validate the recorder count against unique source elements.
    changed_elements = {
        record.element_context_key
        for record in records
        if record.operation == "changed" and record.element_context_key
    }
    expected = {
        "added": counts.get("node_added", 0),
        "removed": counts.get("node_removed", 0),
        "viewport_text_changed": counts.get("visible_text_entered", 0)
        + counts.get("visible_text_exited", 0),
    }
    for key, actual in expected.items():
        if emitted.get(key) != actual:
            raise ValueError(
                f"{path}: emitted_counts.{key}={emitted.get(key)!r}, parsed={actual}"
            )
    emitted_changed = emitted.get("changed")
    if not isinstance(emitted_changed, int) or emitted_changed < len(changed_elements):
        raise ValueError(
            f"{path}: emitted changed-node count {emitted_changed!r} is smaller "
            f"than {len(changed_elements)} explicit changed elements"
        )
    summed = (
        int(emitted.get("added") or 0)
        + emitted_changed
        + int(emitted.get("removed") or 0)
        + int(emitted.get("viewport_text_changed") or 0)
    )
    if emitted.get("changes") != summed or change_count != totals.get("changes"):
        raise ValueError(f"{path}: change-count arithmetic is inconsistent")


def parse_dom_diff_text(
    path: str | Path,
    *,
    task_id: str,
    action_ordinal: int,
    action_id: str | None = None,
) -> DOMDiffTextEvidenceFrame:
    """Parse one canonical refined text diff into explicit semantic records."""
    source_path = Path(path).resolve(strict=False)
    match = _DIFF_NAME_RE.fullmatch(source_path.name)
    if match is None or int(match.group(1)) != action_ordinal:
        raise ValueError(
            f"Text diff filename/action mismatch: {source_path.name}, action {action_ordinal}"
        )
    raw_bytes = source_path.read_bytes()
    try:
        source_text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Refined DOM diff is not strict UTF-8: {source_path}: {exc}") from exc

    headers: dict[str, Any] = {}
    records: list[SemanticRecord] = []
    raw_records: list[dict[str, Any]] = []
    raw_paths: list[str] = []
    repeated_paths: list[str] = []
    counts: dict[str, int] = {}
    seen_record = False
    lines = source_text.splitlines()
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line:
            raise ValueError(f"Blank evidence line is not allowed: {source_path} line {line_number}")
        if ": " not in raw_line:
            raise ValueError(f"Malformed evidence line: {source_path} line {line_number}")
        label, value = raw_line.split(": ", 1)
        if label in REQUIRED_HEADERS:
            if seen_record:
                raise ValueError(f"Header {label!r} appears after records: {source_path}")
            if label in headers:
                raise ValueError(f"Duplicate header {label!r}: {source_path}")
            if label in JSON_HEADERS:
                headers[label] = _parse_json(
                    value, path=source_path, line_number=line_number, label=label
                )
            elif label in BOOLEAN_HEADERS:
                headers[label] = _parse_bool(
                    value, path=source_path, line_number=line_number, label=label
                )
            elif label == "change_count":
                try:
                    headers[label] = int(value)
                except ValueError as exc:
                    raise ValueError(f"change_count must be an integer: {source_path}") from exc
            else:
                headers[label] = value
            continue
        seen_record = True
        if label not in RECORD_FAMILIES:
            raise ValueError(
                f"Unsupported refined DOM record {label!r}: {source_path} line {line_number}"
            )
        declared_status = headers.get("status")
        if declared_status in _RECORDS_BY_STATUS and label not in _RECORDS_BY_STATUS[declared_status]:
            raise ValueError(
                f"Record {label!r} is invalid for status {declared_status!r}: "
                f"{source_path} line {line_number}"
            )
        counts[label] = counts.get(label, 0) + 1
        span = _source_span(
            task_id=task_id,
            action_ordinal=action_ordinal,
            path=source_path,
            line_number=line_number,
            raw_line=raw_line,
        )
        record_id = f"s{action_ordinal}r{len(records) + 1}"
        if label in _TEXT_RECORDS:
            parsed = _parse_json(
                value, path=source_path, line_number=line_number, label=label
            )
            if not isinstance(parsed, str):
                raise ValueError(f"{label} must be a JSON string: {source_path} line {line_number}")
            operation, scope = _TEXT_RECORDS[label]
            records.append(
                SemanticRecord(
                    record_id=record_id,
                    operation=operation,
                    scope=scope,
                    record_kind="text",
                    text=parsed,
                    source_spans=(span,),
                )
            )
            parsed_value: Any = parsed
        elif label in {"node_added", "node_removed"}:
            payload = _require_object(
                _parse_json(value, path=source_path, line_number=line_number, label=label),
                label=label,
            )
            records.append(
                _node_record(
                    payload=payload,
                    operation="added" if label == "node_added" else "removed",
                    record_id=record_id,
                    span=span,
                )
            )
            if payload.get("path"):
                raw_paths.append(str(payload["path"]))
            for sample_path in payload.get("sample_paths") or []:
                repeated_paths.append(str(sample_path))
            parsed_value = payload
        elif label == "node_changed":
            record = _changed_record(
                value=value,
                record_id=record_id,
                span=span,
                path=source_path,
                line_number=line_number,
            )
            records.append(record)
            raw_paths.append(record.element_context_key)
            parsed_value = {
                "path": record.element_context_key,
                "field": record.changed_field,
                "before": record.before_value,
                "after": record.after_value,
            }
        elif label == "navigation":
            payload = _require_object(
                _parse_json(value, path=source_path, line_number=line_number, label=label),
                label=label,
            )
            if set(payload) != {"from", "to"} or not all(
                isinstance(payload[key], str) for key in ("from", "to")
            ):
                raise ValueError(f"navigation must contain exact string from/to fields: {source_path}")
            records.append(
                SemanticRecord(
                    record_id=record_id,
                    operation="navigation",
                    scope="page",
                    record_kind="navigation",
                    navigation_from=payload["from"],
                    navigation_to=payload["to"],
                    source_spans=(span,),
                )
            )
            parsed_value = payload
        elif label in {"added_node_count", "removed_node_count"}:
            try:
                parsed_value = int(value)
            except ValueError as exc:
                raise ValueError(f"{label} must be an integer: {source_path}") from exc
            if parsed_value < 0:
                raise ValueError(f"{label} must be non-negative: {source_path}")
        else:
            parsed_value = _parse_json(
                value, path=source_path, line_number=line_number, label=label
            )
            parsed_value = _require_object(parsed_value, label=label)
            allowed = (
                _VIEWPORT_STATE_KEYS
                if label == "viewport_state"
                else _VIEWPORT_GEOMETRY_KEYS
            )
            _validate_keys(
                parsed_value, label=label, allowed=allowed, required=allowed
            )
        raw_records.append(
            {"line": line_number, "family": label, "value": parsed_value, "span": span.to_dict()}
        )

    missing = [name for name in REQUIRED_HEADERS if name not in headers]
    if missing:
        raise ValueError(f"Missing required refined DOM headers {missing}: {source_path}")
    if headers["source"] != DOM_DIFF_TEXT_SOURCE:
        raise ValueError(f"Unsupported source {headers['source']!r}: {source_path}")
    if headers["interval"] != DOM_DIFF_TEXT_INTERVAL:
        raise ValueError(f"Unsupported interval {headers['interval']!r}: {source_path}")
    if headers["status"] not in SUPPORTED_STATUSES:
        raise ValueError(f"Unsupported status {headers['status']!r}: {source_path}")
    if headers["action_type"] not in SUPPORTED_ACTION_TYPES:
        raise ValueError(f"Unsupported action_type {headers['action_type']!r}: {source_path}")
    if headers["geometry_excluded"] is not True:
        raise ValueError(f"Version 1 requires geometry_excluded=true: {source_path}")
    before = _validate_state_object(headers["before"], label="before")
    after = _validate_state_object(headers["after"], label="after")
    identity = _require_object(headers["identity"], label="identity")
    _validate_keys(
        identity,
        label="identity",
        allowed=_IDENTITY_KEYS,
        required=_IDENTITY_KEYS,
    )
    for side in ("before", "after"):
        side_value = _require_object(identity[side], label=f"identity.{side}")
        _validate_keys(
            side_value,
            label=f"identity.{side}",
            allowed=_IDENTITY_SIDE_KEYS,
            required=_IDENTITY_SIDE_KEYS,
        )
    compression = _require_object(headers["compression"], label="compression")
    _validate_keys(compression, label="compression", allowed=_COMPRESSION_KEYS)
    for key in ("emitted_before_truncation", "entries_truncated"):
        if key in compression:
            values = _require_object(compression[key], label=f"compression.{key}")
            _validate_keys(
                values,
                label=f"compression.{key}",
                allowed=_COUNT_TRIPLE_KEYS,
                required=_COUNT_TRIPLE_KEYS,
            )
    totals = _require_object(headers["totals"], label="totals")
    emitted = _require_object(headers["emitted_counts"], label="emitted_counts")
    if headers["status"] == "document_replaced":
        total_keys = {"added_nodes", "added_text", "removed_nodes", "removed_text"}
        emitted_keys = total_keys
        cardinalities = {"navigation": 1, "added_node_count": 1, "removed_node_count": 1}
    else:
        total_keys = {"added", "changed", "changes", "removed", "semantic_changes", "viewport_text_changed"}
        emitted_keys = {"added", "changed", "changes", "removed", "viewport_text_changed"}
        cardinalities = (
            {"viewport_state": 1, "viewport_geometry": 1}
            if headers["status"] == "viewport_content_changed"
            else {}
        )
    _validate_keys(totals, label="totals", allowed=total_keys, required=total_keys)
    _validate_keys(
        emitted, label="emitted_counts", allowed=emitted_keys, required=emitted_keys
    )
    for family, expected_count in cardinalities.items():
        if counts.get(family, 0) != expected_count:
            raise ValueError(
                f"Status {headers['status']!r} requires exactly {expected_count} "
                f"{family} record(s): {source_path}"
            )
    if headers["status"] == "changes_present":
        viewport_counts = (
            counts.get("viewport_state", 0),
            counts.get("viewport_geometry", 0),
        )
        if viewport_counts not in {(0, 0), (1, 1)}:
            raise ValueError(
                f"changes_present viewport envelope must be absent or complete: {source_path}"
            )
    _validate_header_arithmetic(
        path=source_path,
        status=str(headers["status"]),
        headers=headers,
        counts=counts,
        records=records,
    )

    navigation_records = [record for record in records if record.record_kind == "navigation"]
    navigation: tuple[str, str] | None = None
    if headers["status"] == "document_replaced":
        if len(navigation_records) != 1:
            raise ValueError(f"Document replacement requires exactly one navigation record: {source_path}")
        navigation = (
            str(navigation_records[0].navigation_from),
            str(navigation_records[0].navigation_to),
        )
        if navigation != (before["url"], after["url"]):
            raise ValueError(f"Navigation URLs disagree with before/after URLs: {source_path}")
    elif navigation_records:
        raise ValueError(f"Only document replacement may contain navigation: {source_path}")

    warnings: list[str] = []
    if not headers["covers_live_control_state"]:
        warnings.append("live_control_state_not_covered")
    if headers["status"] == "document_replaced":
        warnings.extend(["document_replaced", "document_replacement_text_only"])
    truncated = compression.get("entries_truncated") or {}
    if isinstance(truncated, dict) and any(int(value or 0) for value in truncated.values()):
        warnings.append("source_entries_truncated")
    dropped = compression.get("dropped_entries") or []
    if dropped:
        warnings.append("source_entries_dropped")
    if compression.get("collapsed_descendants") or compression.get(
        "repeated_group_members_condensed"
    ):
        warnings.append("recorder_compacted_candidates")
    filtered_count_keys = (
        "noise_nodes_skipped",
        "relocated_nodes_suppressed",
        "subtree_text_changes_ignored",
    )
    if any(int(compression.get(key) or 0) for key in filtered_count_keys):
        warnings.append("recorder_filtered_candidates")
    if headers["status"] != "document_replaced" and any(
        int(totals.get(key) or 0) > int(emitted.get(key) or 0)
        for key in ("added", "changed", "removed", "viewport_text_changed")
    ):
        warnings.append("source_candidates_not_fully_emitted")

    source_hash = _sha256(raw_bytes)
    audit_id = f"text-{action_ordinal}-{source_hash[:16]}"
    audit = DOMDiffTextAuditReceipt(
        task_id=task_id,
        action_ordinal=action_ordinal,
        source_path=str(source_path),
        source_bytes=len(raw_bytes),
        source_sha256=source_hash,
        source_line_count=len(lines),
        headers=headers,
        raw_paths=tuple(raw_paths),
        repeated_group_sample_paths=tuple(repeated_paths),
        raw_records=tuple(raw_records),
        parsed_record_counts=dict(sorted(counts.items())),
        coverage_warnings=tuple(dict.fromkeys(warnings)),
        audit_receipt_id=audit_id,
    )
    return DOMDiffTextEvidenceFrame(
        action_ordinal=action_ordinal,
        action_id=str(action_id or action_ordinal),
        task_id=task_id,
        text_path=str(source_path),
        action_type=str(headers["action_type"]),
        status=str(headers["status"]),
        before_url=str(before["url"]),
        after_url=str(after["url"]),
        before_identity=(str(before["snapshot_id"]), int(before["document_revision"])),
        after_identity=(str(after["snapshot_id"]), int(after["document_revision"])),
        navigation=navigation,
        records=tuple(records),
        coverage_warnings=audit.coverage_warnings,
        audit=audit,
    )


def load_dom_diff_text_frames(
    actions: Iterable[dict[str, Any]],
) -> list[DOMDiffTextEvidenceFrame]:
    frames: list[DOMDiffTextEvidenceFrame] = []
    previous_after: tuple[str, int] | None = None
    for position, action in enumerate(actions, start=1):
        ordinal = int(action.get("dom_action_ordinal") or action.get("id") or 0)
        if ordinal != position:
            raise ValueError(
                f"DOM text actions must be contiguous: expected {position}, got {ordinal}"
            )
        path = str(action.get("dom_diff_text_path") or "")
        if not path:
            raise ValueError(f"Action {ordinal} has no dom_diff_text_path")
        frame = parse_dom_diff_text(
            path,
            task_id=str(action.get("dom_task_id") or "unknown-task"),
            action_ordinal=ordinal,
            action_id=str(action.get("dom_action_id") or ordinal),
        )
        if previous_after is not None and frame.before_identity != previous_after:
            raise ValueError(
                f"Snapshot/revision chain mismatch before action {ordinal}: "
                f"expected {previous_after}, got {frame.before_identity}"
            )
        previous_after = frame.after_identity
        frames.append(frame)
    return frames


def evidence_source_hashes(
    frames: Sequence[DOMDiffTextEvidenceFrame],
) -> tuple[str, ...]:
    return tuple(frame.source_sha256 for frame in frames)
