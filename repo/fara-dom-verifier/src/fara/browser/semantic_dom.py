"""Versioned semantic-DOM evidence models and deterministic processing.

The browser capture intentionally emits a small, renderer-derived intermediate
representation.  This module owns the security and determinism boundary:
captured values are redacted, normalized, assigned stable keys, sorted, hashed,
diffed, and persisted without relying on browser-specific object identities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SNAPSHOT_SCHEMA_VERSION = "semantic-dom-snapshot/v1"
DIFF_SCHEMA_VERSION = "semantic-dom-diff/v1"
EVIDENCE_FRAME_SCHEMA_VERSION = "dom-evidence-frame/v1"
TRAJECTORY_SCHEMA_VERSION = "dom-trajectory-manifest/v2"
CANONICALIZER_VERSION = "semantic-dom-canonicalizer/v1"
REDACTION_MARKER = "<redacted>"

_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "client_secret",
}
_SENSITIVE_QUERY_KEYS = _SENSITIVE_KEYS | {
    "auth",
    "code",
    "key",
    "session",
    "session_id",
    "signature",
    "sig",
}
_SENSITIVE_INPUT_TYPES = {"password"}
_SENSITIVE_AUTOCOMPLETE = {
    "cc-csc",
    "cc-number",
    "current-password",
    "new-password",
    "one-time-code",
}
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(bearer\s+)[a-z0-9._~+/=-]{8,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|(?:access[_-]?)?token|client[_-]?secret|"
        r"password|authorization|cookie)"
        r"(\s*[:=]\s*)[^\s,;]+"
    ),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
)


@dataclass(frozen=True)
class DOMCoverage:
    status: str = "complete"
    rendered_dom: bool = True
    nodes_seen: int = 0
    nodes_captured: int = 0
    node_limit: int = 5000
    text_limit: int = 1000
    truncated: bool = False
    same_origin_frames: int = 1
    open_shadow_roots: int = 0
    cross_origin_frames: tuple[str, ...] = ()
    canvas_count: int = 0
    image_without_alt_count: int = 0
    unsupported: tuple[str, ...] = (
        "closed-shadow-roots",
        "canvas-pixels",
        "image-pixels",
        "visual-style-and-layout",
    )
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticDOMNode:
    key: str
    parent_key: str | None
    frame_path: str
    role: str
    name: str = ""
    text: str = ""
    value: str = ""
    tag: str = ""
    states: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticDOMSnapshot:
    schema_version: str
    canonicalizer_version: str
    snapshot_id: str
    ordinal: int
    url: str
    title: str
    captured_at: str
    hash: str
    nodes: tuple[SemanticDOMNode, ...]
    coverage: DOMCoverage

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticDOMDiff:
    schema_version: str
    canonicalizer_version: str
    diff_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    from_hash: str
    to_hash: str
    added: tuple[Mapping[str, Any], ...]
    removed: tuple[Mapping[str, Any], ...]
    updated: tuple[Mapping[str, Any], ...]
    unchanged_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DOMEvidenceFrame:
    schema_version: str
    action_ordinal: int
    action_id: str
    before_snapshot: str | None
    after_snapshot: str | None
    diff: str | None
    capture_status: str
    coverage_status: str


@dataclass
class DOMTrajectoryManifest:
    schema_version: str = TRAJECTORY_SCHEMA_VERSION
    evidence_format: str = "semantic-dom"
    canonicalizer_version: str = CANONICALIZER_VERSION
    created_at: str = field(default_factory=lambda: _utc_now())
    browser: dict[str, Any] = field(default_factory=dict)
    initial_snapshot: str | None = None
    frames: list[DOMEvidenceFrame] = field(default_factory=list)
    capture_errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_text(value: Any, *, limit: int | None = None) -> str:
    """Normalize Unicode and whitespace without changing semantic case."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = " ".join(normalized.split())
    if limit is not None and len(normalized) > limit:
        return normalized[:limit]
    return normalized


def redact_text(value: Any) -> str:
    """Redact common credential, payment-card, and identity secret patterns."""
    text = normalize_text(value)
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 1:
            text = pattern.sub(r"\1" + REDACTION_MARKER, text)
        elif pattern.groups >= 2:
            text = pattern.sub(r"\1\2" + REDACTION_MARKER, text)
        else:
            text = pattern.sub(REDACTION_MARKER, text)
    return text


def redact_url(url: Any) -> str:
    """Redact sensitive query values while retaining evidence-bearing location."""
    value = normalize_text(url)
    try:
        parts = urlsplit(value)
        netloc = parts.netloc
        if parts.username is not None:
            host = parts.hostname or ""
            if parts.port is not None:
                host = f"{host}:{parts.port}"
            netloc = f"{REDACTION_MARKER}@{host}"
        query = [
            (
                key,
                REDACTION_MARKER
                if key.lower() in _SENSITIVE_QUERY_KEYS
                else redact_text(val),
            )
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
        ]
        fragment = parts.fragment
        if "=" in fragment:
            fragment = urlencode(
                [
                    (
                        key,
                        REDACTION_MARKER
                        if key.lower() in _SENSITIVE_QUERY_KEYS
                        else redact_text(val),
                    )
                    for key, val in parse_qsl(fragment, keep_blank_values=True)
                ]
            )
        else:
            fragment = redact_text(fragment)
        return urlunsplit(
            (
                parts.scheme,
                netloc,
                redact_text(parts.path),
                urlencode(query),
                fragment,
            )
        )
    except ValueError:
        return redact_text(value)


def redact_secrets(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact secrets from JSON-like data."""
    if key and key.lower() in _SENSITIVE_KEYS:
        return REDACTION_MARKER if value not in (None, "") else value
    if isinstance(value, Mapping):
        return {
            str(k): redact_secrets(v, key=str(k))
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def stable_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_node_key(
    *,
    parent_key: str | None,
    frame_path: str,
    role: str,
    name: str,
    tag: str,
    semantic_id: str = "",
    occurrence: int = 0,
) -> str:
    """Create a deterministic identity independent of browser node handles."""
    identity = {
        "parent": parent_key or "",
        "frame": frame_path,
        "role": normalize_text(role).lower(),
        "name": normalize_text(name),
        "tag": normalize_text(tag).lower(),
        "semantic_id": normalize_text(semantic_id),
        "occurrence": occurrence,
    }
    return "node:" + stable_hash(identity).split(":", 1)[1][:24]


def _canonical_states(raw: Mapping[str, Any]) -> dict[str, Any]:
    states: dict[str, Any] = {}
    for key, value in sorted(raw.items()):
        if value is None or value == "":
            continue
        if isinstance(value, str):
            states[normalize_text(key)] = redact_text(value)
        elif isinstance(value, (bool, int, float)):
            states[normalize_text(key)] = value
    return states


def _coverage_from_raw(raw: Mapping[str, Any], node_count: int) -> DOMCoverage:
    errors = tuple(sorted(redact_text(item) for item in raw.get("errors", [])))
    cross_origin = tuple(
        sorted(redact_url(item) for item in raw.get("cross_origin_frames", []))
    )
    truncated = bool(raw.get("truncated", False))
    status = "partial" if errors or cross_origin else "complete"
    if truncated:
        status = "truncated"
    return DOMCoverage(
        status=status,
        rendered_dom=bool(raw.get("rendered_dom", True)),
        nodes_seen=int(raw.get("nodes_seen", node_count)),
        nodes_captured=node_count,
        node_limit=int(raw.get("node_limit", 5000)),
        text_limit=int(raw.get("text_limit", 1000)),
        truncated=truncated,
        same_origin_frames=int(raw.get("same_origin_frames", 1)),
        open_shadow_roots=int(raw.get("open_shadow_roots", 0)),
        cross_origin_frames=cross_origin,
        canvas_count=int(raw.get("canvas_count", 0)),
        image_without_alt_count=int(raw.get("image_without_alt_count", 0)),
        errors=errors,
    )


def canonicalize_snapshot(
    raw: Mapping[str, Any],
    *,
    ordinal: int,
    captured_at: str | None = None,
) -> SemanticDOMSnapshot:
    """Canonicalize a raw renderer capture into a versioned snapshot."""
    raw_nodes = list(raw.get("nodes", []))
    keys_by_source_index: dict[int, str] = {}
    duplicate_counts: dict[tuple[str, str, str, str, str, str], int] = {}
    canonical_nodes: list[SemanticDOMNode] = []

    for source_index, raw_node in enumerate(raw_nodes):
        parent_index = raw_node.get("parent_index")
        parent_key = (
            keys_by_source_index.get(int(parent_index))
            if isinstance(parent_index, int) or str(parent_index).isdigit()
            else None
        )
        frame_path = normalize_text(raw_node.get("frame_path", "main")) or "main"
        role = normalize_text(raw_node.get("role", "generic")).lower() or "generic"
        tag = normalize_text(raw_node.get("tag", "")).lower()
        name = redact_text(raw_node.get("name", ""))
        text = redact_text(raw_node.get("text", ""))
        input_type = normalize_text(raw_node.get("input_type", "")).lower()
        autocomplete = normalize_text(raw_node.get("autocomplete", "")).lower()
        sensitive = bool(raw_node.get("sensitive")) or input_type in _SENSITIVE_INPUT_TYPES
        sensitive = sensitive or autocomplete in _SENSITIVE_AUTOCOMPLETE
        value = (
            REDACTION_MARKER
            if sensitive and raw_node.get("value") not in (None, "")
            else redact_text(raw_node.get("value", ""))
        )
        semantic_id = normalize_text(raw_node.get("semantic_id", ""))
        identity = (parent_key or "", frame_path, role, name, tag, semantic_id)
        occurrence = duplicate_counts.get(identity, 0)
        duplicate_counts[identity] = occurrence + 1
        key = stable_node_key(
            parent_key=parent_key,
            frame_path=frame_path,
            role=role,
            name=name,
            tag=tag,
            semantic_id=semantic_id,
            occurrence=occurrence,
        )
        keys_by_source_index[source_index] = key
        canonical_nodes.append(
            SemanticDOMNode(
                key=key,
                parent_key=parent_key,
                frame_path=frame_path,
                role=role,
                name=name,
                text=text,
                value=value,
                tag=tag,
                states=_canonical_states(raw_node.get("states", {})),
            )
        )

    canonical_nodes.sort(key=lambda node: node.key)
    coverage = _coverage_from_raw(raw.get("coverage", {}), len(canonical_nodes))
    payload = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "canonicalizer_version": CANONICALIZER_VERSION,
        "url": redact_url(raw.get("url", "")),
        "title": redact_text(raw.get("title", "")),
        "nodes": [asdict(node) for node in canonical_nodes],
        "coverage": asdict(coverage),
    }
    digest = stable_hash(payload)
    return SemanticDOMSnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        canonicalizer_version=CANONICALIZER_VERSION,
        snapshot_id=f"snapshot-{ordinal:04d}",
        ordinal=ordinal,
        url=payload["url"],
        title=payload["title"],
        captured_at=captured_at or _utc_now(),
        hash=digest,
        nodes=tuple(canonical_nodes),
        coverage=coverage,
    )


def _node_payload(node: SemanticDOMNode) -> dict[str, Any]:
    return asdict(node)


def diff_snapshots(
    before: SemanticDOMSnapshot, after: SemanticDOMSnapshot
) -> SemanticDOMDiff:
    """Return a deterministic key-based semantic diff."""
    before_nodes = {node.key: node for node in before.nodes}
    after_nodes = {node.key: node for node in after.nodes}
    added = tuple(
        _node_payload(after_nodes[key]) for key in sorted(after_nodes.keys() - before_nodes)
    )
    removed = tuple(
        _node_payload(before_nodes[key])
        for key in sorted(before_nodes.keys() - after_nodes)
    )
    updated: list[dict[str, Any]] = []
    unchanged_count = 0
    for key in sorted(before_nodes.keys() & after_nodes):
        old = _node_payload(before_nodes[key])
        new = _node_payload(after_nodes[key])
        changes = {
            field_name: {"before": old[field_name], "after": new[field_name]}
            for field_name in sorted(old)
            if field_name != "key" and old[field_name] != new[field_name]
        }
        if changes:
            updated.append({"key": key, "changes": changes})
        else:
            unchanged_count += 1
    return SemanticDOMDiff(
        schema_version=DIFF_SCHEMA_VERSION,
        canonicalizer_version=CANONICALIZER_VERSION,
        diff_id=f"diff-{after.ordinal:04d}",
        from_snapshot_id=before.snapshot_id,
        to_snapshot_id=after.snapshot_id,
        from_hash=before.hash,
        to_hash=after.hash,
        added=added,
        removed=removed,
        updated=tuple(updated),
        unchanged_count=unchanged_count,
    )


def write_json_atomic(path: str | Path, value: Any) -> Path:
    """Persist canonical JSON atomically and return the destination path."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return destination


def persist_snapshot(
    evidence_root: str | Path, snapshot: SemanticDOMSnapshot
) -> Path:
    return write_json_atomic(
        Path(evidence_root)
        / f"step_{snapshot.ordinal:04d}"
        / "semantic_dom.json",
        snapshot,
    )


def persist_diff(evidence_root: str | Path, diff: SemanticDOMDiff) -> Path:
    ordinal = int(diff.to_snapshot_id.rsplit("-", 1)[-1])
    return write_json_atomic(
        Path(evidence_root) / f"step_{ordinal:04d}" / "dom_diff.json", diff
    )


def relative_reference(path: str | Path, root: str | Path) -> str:
    return Path(path).relative_to(Path(root)).as_posix()


def persist_manifest(
    trajectory_root: str | Path, manifest: DOMTrajectoryManifest
) -> Path:
    return write_json_atomic(
        Path(trajectory_root) / "trajectory_manifest.json", manifest
    )


def validate_diff_chain(
    snapshots: Iterable[SemanticDOMSnapshot], diffs: Iterable[SemanticDOMDiff]
) -> bool:
    """Validate hash linkage for a snapshot/diff sequence."""
    ordered_snapshots = sorted(snapshots, key=lambda item: item.ordinal)
    ordered_diffs = sorted(diffs, key=lambda item: item.to_snapshot_id)
    if len(ordered_diffs) != max(0, len(ordered_snapshots) - 1):
        return False
    return all(
        diff.from_hash == before.hash
        and diff.to_hash == after.hash
        and diff.from_snapshot_id == before.snapshot_id
        and diff.to_snapshot_id == after.snapshot_id
        for before, after, diff in zip(
            ordered_snapshots, ordered_snapshots[1:], ordered_diffs
        )
    )
