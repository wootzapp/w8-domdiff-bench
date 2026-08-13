"""Conservative deterministic compaction for refined DOM-diff text.

No source record is character-clipped.  The full normalized IR remains
available even when model-facing evidence is split into semantic chunks.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Sequence

from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_evidence import (
    DOMDiffTextEvidenceFrame,
    SemanticRecord,
    SourceSpan,
)


COMPACT_DOM_DIFF_TEXT_SCHEMA = "dom-diff-text-compact/v2"
_ZERO_WIDTH_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)")
_TOKEN_RE = re.compile(r"\S+\s*")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = _ZERO_WIDTH_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _normalize_json(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_json(value[key]) for key in sorted(value)}
    return value


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _tail_context(path: str) -> str:
    if not path:
        return ""
    parts = path.split("/")
    return "/".join(parts[-2:])


@dataclass(frozen=True)
class CompactChunk:
    chunk_id: str
    record_id: str
    action_ordinal: int
    operation: str
    scope: str
    record_kind: str
    text: str
    search_text: str
    # Lightweight stable joins used by retrieval/audit receipts. Complete
    # SourceSpan objects live once on CompactRecord.record and in the source
    # audit sidecar; they are not repeated on every semantic chunk.
    source_refs: tuple[str, ...]
    first_source_line: int
    chunk_index: int
    chunk_count: int
    priority: int
    hard_retained: bool

    def to_model_dict(self) -> dict[str, Any]:
        return {"chunk_id": self.chunk_id, "text": self.text}

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "record_id": self.record_id,
            "action_ordinal": self.action_ordinal,
            "operation": self.operation,
            "scope": self.scope,
            "record_kind": self.record_kind,
            "text": self.text,
            "search_text": self.search_text,
            "source_refs": list(self.source_refs),
            "first_source_line": self.first_source_line,
            "chunk_index": self.chunk_index,
            "chunk_count": self.chunk_count,
            "priority": self.priority,
            "hard_retained": self.hard_retained,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return the audit form for backward-compatible artifact readers."""
        return self.to_audit_dict()


@dataclass(frozen=True)
class CompactRecord:
    record: SemanticRecord
    chunks: tuple[CompactChunk, ...]

    @property
    def record_id(self) -> str:
        return self.record.record_id

    def to_model_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "chunks": [chunk.to_model_dict() for chunk in self.chunks],
        }

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(include_audit=True),
            "chunks": [chunk.to_audit_dict() for chunk in self.chunks],
        }

    def to_dict(self) -> dict[str, Any]:
        return self.to_audit_dict()


@dataclass(frozen=True)
class TextCompactionReceipt:
    source_records: int
    compact_records: int
    compact_chunks: int
    source_text_chars: int
    compact_text_chars: int
    exact_duplicates_removed: int
    element_field_duplicates_removed: int
    contained_fragments_removed: int
    geometry_only_changes_removed: int
    records_truncated_by_char_limit: int
    duplicate_merges: tuple[Mapping[str, Any], ...]
    element_field_merges: tuple[Mapping[str, Any], ...]
    containment_merges: tuple[Mapping[str, Any], ...]
    source_to_compact: Mapping[str, tuple[str, ...]]
    model_path_exceptions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_records": self.source_records,
            "compact_records": self.compact_records,
            "compact_chunks": self.compact_chunks,
            "source_text_chars": self.source_text_chars,
            "compact_text_chars": self.compact_text_chars,
            "exact_duplicates_removed": self.exact_duplicates_removed,
            "element_field_duplicates_removed": self.element_field_duplicates_removed,
            "contained_fragments_removed": self.contained_fragments_removed,
            "geometry_only_changes_removed": self.geometry_only_changes_removed,
            "records_truncated_by_char_limit": self.records_truncated_by_char_limit,
            "duplicate_merges": [dict(item) for item in self.duplicate_merges],
            "element_field_merges": [dict(item) for item in self.element_field_merges],
            "containment_merges": [dict(item) for item in self.containment_merges],
            "source_to_compact": {
                key: list(value) for key, value in sorted(self.source_to_compact.items())
            },
            "model_path_exceptions": list(self.model_path_exceptions),
        }


@dataclass(frozen=True)
class CompactDOMDiffTextFrame:
    action_ordinal: int
    action_id: str
    task_id: str
    status: str
    action_type: str
    before_url: str
    after_url: str
    navigation: tuple[str, str] | None
    coverage_warnings: tuple[str, ...]
    records: tuple[CompactRecord, ...]
    receipt: TextCompactionReceipt
    source_path: str
    source_sha256: str
    source_bytes: int
    audit_receipt_id: str
    schema_version: str = COMPACT_DOM_DIFF_TEXT_SCHEMA

    @property
    def chunks(self) -> tuple[CompactChunk, ...]:
        return tuple(chunk for record in self.records for chunk in record.chunks)

    @property
    def compact_bytes(self) -> int:
        """Size of the lightweight model representation, not the audit sidecar."""
        return self.model_bytes

    @property
    def model_bytes(self) -> int:
        return len(
            json.dumps(
                self.to_model_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )

    @property
    def audit_bytes(self) -> int:
        return len(
            json.dumps(
                self.to_audit_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )

    def to_model_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "action_ordinal": self.action_ordinal,
            "status": self.status,
            "action_type": self.action_type,
            "before_url": self.before_url,
            "after_url": self.after_url,
            "coverage_warnings": list(self.coverage_warnings),
            "records": [record.to_model_dict() for record in self.records],
        }

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "action_ordinal": self.action_ordinal,
            "action_id": self.action_id,
            "task_id": self.task_id,
            "status": self.status,
            "action_type": self.action_type,
            "before_url": self.before_url,
            "after_url": self.after_url,
            "navigation": list(self.navigation) if self.navigation else None,
            "coverage_warnings": list(self.coverage_warnings),
            "records": [record.to_audit_dict() for record in self.records],
            "receipt": self.receipt.to_dict(),
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "source_bytes": self.source_bytes,
            "audit_receipt_id": self.audit_receipt_id,
        }

    def to_dict(self) -> dict[str, Any]:
        """Keep the full form explicitly audit-only."""
        return self.to_audit_dict()


@dataclass(frozen=True)
class RecordOccurrence:
    action_ordinal: int
    frame_record_id: str
    source_spans: tuple[SourceSpan, ...]
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_ordinal": self.action_ordinal,
            "frame_record_id": self.frame_record_id,
            "source_spans": [span.to_dict() for span in self.source_spans],
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class LedgerRecord:
    ledger_record_id: str
    record: SemanticRecord
    occurrences: tuple[RecordOccurrence, ...]

    @property
    def occurs_at_steps(self) -> tuple[int, ...]:
        return tuple(occurrence.action_ordinal for occurrence in self.occurrences)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_record_id": self.ledger_record_id,
            "record": self.record.to_dict(include_audit=True),
            "occurrences": [item.to_dict() for item in self.occurrences],
        }


@dataclass(frozen=True)
class CompactDOMDiffTextTrajectoryLedger:
    frames: tuple[CompactDOMDiffTextFrame, ...]
    ordered_step_headers: tuple[str, ...]
    records: tuple[LedgerRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": COMPACT_DOM_DIFF_TEXT_SCHEMA,
            "ordered_step_headers": list(self.ordered_step_headers),
            "records": [record.to_dict() for record in self.records],
        }


def _normalize_record(record: SemanticRecord) -> tuple[SemanticRecord, list[dict[str, Any]]]:
    field_merges: list[dict[str, Any]] = []
    direct_text = normalize_text(record.direct_text) or None
    visible_text = normalize_text(record.visible_text) or None
    # These two fields describe the same source element and direction.  Exact
    # equality is the only automatic element/text merge performed.
    if direct_text and visible_text and direct_text == visible_text:
        visible_text = None
        field_merges.append(
            {
                "record_id": record.record_id,
                "removed_field": "visible_text",
                "retained_field": "direct_text",
                "reason": "exact_same_element_text",
            }
        )
    return (
        replace(
            record,
            text=normalize_text(record.text) or None,
            role=normalize_text(record.role) or None,
            accessible_name=normalize_text(record.accessible_name) or None,
            direct_text=direct_text,
            visible_text=visible_text,
            supported_actions=tuple(normalize_text(item) for item in record.supported_actions),
            tag=normalize_text(record.tag) or None,
            semantic_boundary=normalize_text(record.semantic_boundary) or None,
            selected_attributes=tuple(
                (normalize_text(name), normalize_text(value))
                for name, value in record.selected_attributes
            ),
            states=tuple(
                (normalize_text(name), normalize_text(value)) for name, value in record.states
            ),
            changed_field=normalize_text(record.changed_field) or None,
            before_value=_normalize_json(record.before_value),
            after_value=_normalize_json(record.after_value),
            navigation_from=normalize_text(record.navigation_from) or None,
            navigation_to=normalize_text(record.navigation_to) or None,
            interactive_descendants=tuple(
                normalize_text(item) for item in record.interactive_descendants if normalize_text(item)
            ),
            repeated_group_samples=tuple(
                normalize_text(item) for item in record.repeated_group_samples if normalize_text(item)
            ),
        ),
        field_merges,
    )


def _merge_spans(left: Sequence[SourceSpan], right: Sequence[SourceSpan]) -> tuple[SourceSpan, ...]:
    seen: set[tuple[Any, ...]] = set()
    output: list[SourceSpan] = []
    for span in (*left, *right):
        key = (
            span.source_file,
            span.source_line_start,
            span.source_line_end,
            span.source_line_sha256,
        )
        if key not in seen:
            seen.add(key)
            output.append(span)
    return tuple(output)


def _prefix(record: SemanticRecord) -> str:
    if record.operation == "added" and record.record_kind == "text":
        return "+DOC"
    if record.operation == "removed" and record.record_kind == "text":
        return "-DOC"
    if record.operation == "viewport_entered":
        return "+VIEW"
    if record.operation == "viewport_exited":
        return "-VIEW"
    if record.operation == "added":
        return f"+EL[{record.scope}]"
    if record.operation == "removed":
        return f"-EL[{record.scope}]"
    if record.operation == "changed":
        return "~EL"
    return "NAV"


def _priority(record: SemanticRecord) -> tuple[int, bool]:
    if record.operation == "navigation":
        return 100, True
    if record.operation == "changed":
        return 96, True
    text = " ".join(
        value
        for value in (
            record.text,
            record.accessible_name,
            record.direct_text,
            record.visible_text,
            record.navigation_from,
            record.navigation_to,
        )
        if value
    )
    important = bool(
        re.search(
            r"(?:\d|\b(?:error|failed|warning|success|confirmed|submitted|saved|deleted|blocked)\b)",
            text,
            re.IGNORECASE,
        )
    )
    if record.operation in {"viewport_entered", "viewport_exited"}:
        return (90 if important else 76), important
    return (88 if important else 68), important


def _record_fields(record: SemanticRecord) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for name, value in (
        ("text", record.text),
        ("role", record.role),
        ("name", record.accessible_name),
        ("direct_text", record.direct_text),
        ("visible_text", record.visible_text),
        ("tag", record.tag),
        ("boundary", record.semantic_boundary),
    ):
        if value is not None:
            fields.append((name, _quote(value)))
    if record.supported_actions:
        fields.append(("actions", _value(list(record.supported_actions))))
    if record.selected_attributes:
        fields.append(
            (
                "attributes",
                _value(
                    [
                        {"name": name, "value": value}
                        for name, value in record.selected_attributes
                    ]
                ),
            )
        )
    if record.states:
        fields.append(
            (
                "states",
                _value(
                    [{"name": name, "value": value} for name, value in record.states]
                ),
            )
        )
    if record.changed_field:
        fields.append(("field", _quote(record.changed_field)))
        fields.append(("before", _value(record.before_value)))
        fields.append(("after", _value(record.after_value)))
    if record.navigation_from is not None:
        fields.append(("from", _quote(record.navigation_from)))
    if record.navigation_to is not None:
        fields.append(("to", _quote(record.navigation_to)))
    if record.repeated_group_count is not None:
        fields.append(("count", str(record.repeated_group_count)))
    for index, value in enumerate(record.interactive_descendants, start=1):
        fields.append((f"interactive_{index}", _quote(value)))
    for index, value in enumerate(record.repeated_group_samples, start=1):
        fields.append((f"sample_{index}", _quote(value)))
    semantic_identity = any(
        (
            record.text,
            record.role,
            record.accessible_name,
            record.direct_text,
            record.visible_text,
            record.tag,
            record.changed_field,
        )
    )
    if record.element_context_key and not semantic_identity:
        fields.append(("context_path_tail", _quote(_tail_context(record.element_context_key))))
    return fields


def render_record(record: SemanticRecord) -> str:
    prefix = f"[{record.record_id}] {_prefix(record)}"
    fields = _record_fields(record)
    # Text records have one semantic payload. Omitting the constant field name
    # avoids repeating `text=` hundreds of times while direction remains
    # explicit in +DOC/-DOC/+VIEW/-VIEW.
    if record.record_kind == "text" and len(fields) == 1 and fields[0][0] == "text":
        return f"{prefix} {fields[0][1]}"
    rendered = " ".join(f"{name}={value}" for name, value in fields)
    return f"{prefix} {rendered}".rstrip()


def record_search_text(record: SemanticRecord) -> str:
    values: list[str] = [record.operation, record.scope, record.record_kind]
    for value in (
        record.text,
        record.role,
        record.accessible_name,
        record.direct_text,
        record.visible_text,
        record.tag,
        record.semantic_boundary,
        record.changed_field,
        record.navigation_from,
        record.navigation_to,
    ):
        if value:
            values.append(value)
    values.extend(record.supported_actions)
    values.extend(name for name, _ in record.selected_attributes)
    values.extend(value for _, value in record.selected_attributes)
    values.extend(name for name, _ in record.states)
    values.extend(value for _, value in record.states)
    values.extend(record.interactive_descendants)
    values.extend(record.repeated_group_samples)
    if record.before_value is not None:
        values.append(_value(record.before_value))
    if record.after_value is not None:
        values.append(_value(record.after_value))
    return "\n".join(values)


def _pack_units(units: Sequence[str], *, prefix: str, target: int, estimator: TokenEstimator) -> list[str]:
    output: list[str] = []
    current = ""
    for unit in units:
        candidate = current + unit
        if current and estimator.count(prefix + candidate) > target:
            output.append(current.rstrip())
            current = unit
        else:
            current = candidate
    if current:
        output.append(current.rstrip())
    return output


def _split_semantic_text(
    value: str, *, prefix: str, target: int, estimator: TokenEstimator
) -> list[str]:
    if estimator.count(prefix + value) <= target:
        return [value]
    sentences = [match.group(0) for match in _SENTENCE_RE.finditer(value) if match.group(0)]
    if len(sentences) > 1:
        packed = _pack_units(sentences, prefix=prefix, target=target, estimator=estimator)
        if all(estimator.count(prefix + part) <= target for part in packed):
            return packed
    words = _TOKEN_RE.findall(value)
    if len(words) > 1:
        return _pack_units(words, prefix=prefix, target=target, estimator=estimator)
    # A single indivisible token (typically a URL) remains complete even when
    # it exceeds the soft chunk target.
    return [value]


def _chunk_record(
    record: SemanticRecord,
    *,
    action_ordinal: int,
    source_refs: tuple[str, ...],
    max_chunk_tokens: int,
    model: str,
) -> tuple[CompactChunk, ...]:
    estimator = TokenEstimator(model)
    priority, hard = _priority(record)
    full = render_record(record)
    if estimator.count(full) <= max_chunk_tokens:
        payloads = [full]
    else:
        base = f"[{record.record_id}] {_prefix(record)}"
        payloads: list[str] = []
        for field_name, rendered_value in _record_fields(record):
            field_prefix = (
                f"{base} "
                if record.record_kind == "text" and field_name == "text"
                else f"{base} {field_name}="
            )
            pieces = _split_semantic_text(
                rendered_value,
                prefix=field_prefix,
                target=max_chunk_tokens,
                estimator=estimator,
            )
            payloads.extend(field_prefix + piece for piece in pieces)
        if not payloads:
            payloads = [base]
    chunk_count = len(payloads)
    chunks: list[CompactChunk] = []
    first_source_line = min(
        span.source_line_start for span in record.source_spans
    )
    for index, text in enumerate(payloads, start=1):
        chunk_id = (
            record.record_id
            if chunk_count == 1
            else f"{record.record_id}c{index}"
        )
        display_text = text
        if chunk_count > 1:
            display_text = display_text.replace(
                f"[{record.record_id}]", f"[{chunk_id}]", 1
            )
            display_text += f" chunk={index}/{chunk_count}"
        chunks.append(
            CompactChunk(
                chunk_id=chunk_id,
                record_id=record.record_id,
                action_ordinal=action_ordinal,
                operation=record.operation,
                scope=record.scope,
                record_kind=record.record_kind,
                text=display_text,
                search_text=record_search_text(record),
                source_refs=source_refs,
                first_source_line=first_source_line,
                chunk_index=index,
                chunk_count=chunk_count,
                priority=priority,
                hard_retained=hard,
            )
        )
    return tuple(chunks)


def _is_containment_candidate(record: SemanticRecord) -> bool:
    """Return whether strict text containment can preserve the full record.

    Only standalone text observations participate. Element, navigation and
    changed-state records carry structure beyond their text and therefore can
    never be removed by this rule.
    """
    return bool(
        record.record_kind == "text"
        and record.text
        and record.operation
        in {"added", "removed", "viewport_entered", "viewport_exited"}
    )


def _containment_compact(
    records: Sequence[SemanticRecord],
) -> tuple[
    list[SemanticRecord],
    list[dict[str, Any]],
    dict[str, tuple[str, ...]],
]:
    """Retain maximal normalized spans within one direction and scope.

    The caller supplies records from exactly one action frame, so action
    ordinal is already fixed. A removed leaf maps to every compatible maximal
    superstring, avoiding an invented parent/child relationship when the text
    format does not expose one. Parse-time record IDs are never renumbered.
    """
    positions = {record.record_id: index for index, record in enumerate(records)}
    groups: dict[tuple[str, str], list[SemanticRecord]] = {}
    for record in records:
        if _is_containment_candidate(record):
            groups.setdefault((record.operation, record.scope), []).append(record)

    removed_targets: dict[str, tuple[str, ...]] = {}
    merges: list[dict[str, Any]] = []
    for (operation, scope), group in sorted(groups.items()):
        ordered = sorted(
            group,
            key=lambda record: (
                -len(record.text or ""),
                positions[record.record_id],
                record.record_id,
            ),
        )
        maximal: list[SemanticRecord] = []
        for record in ordered:
            text = record.text or ""
            containers = tuple(
                candidate
                for candidate in maximal
                if len(candidate.text or "") > len(text)
                and text in (candidate.text or "")
            )
            if not containers:
                maximal.append(record)
                continue
            target_ids = tuple(candidate.record_id for candidate in containers)
            removed_targets[record.record_id] = target_ids
            merges.append(
                {
                    "merged_record_id": record.record_id,
                    "retained_record_ids": list(target_ids),
                    "source_refs": [
                        span.compact_ref for span in record.source_spans
                    ],
                    "operation": operation,
                    "scope": scope,
                    "reason": "strict_normalized_text_containment",
                }
            )

    retained = [
        record for record in records if record.record_id not in removed_targets
    ]
    provenance: dict[str, list[str]] = {
        record.record_id: [span.compact_ref for span in record.source_spans]
        for record in retained
    }
    by_id = {record.record_id: record for record in records}
    for removed_id, target_ids in removed_targets.items():
        removed_refs = [
            span.compact_ref for span in by_id[removed_id].source_spans
        ]
        for target_id in target_ids:
            provenance[target_id].extend(removed_refs)
    return (
        retained,
        merges,
        {
            record_id: tuple(dict.fromkeys(refs))
            for record_id, refs in provenance.items()
        },
    )


def compact_text_frame(
    frame: DOMDiffTextEvidenceFrame,
    *,
    max_chunk_tokens: int = 256,
    model: str = "gpt-5.2",
) -> CompactDOMDiffTextFrame:
    if max_chunk_tokens <= 0:
        raise ValueError("max_chunk_tokens must be positive")
    normalized: list[SemanticRecord] = []
    duplicate_merges: list[dict[str, Any]] = []
    field_merges: list[dict[str, Any]] = []
    by_key: dict[tuple[Any, ...], int] = {}
    for source_record in frame.records:
        record, record_field_merges = _normalize_record(source_record)
        field_merges.extend(record_field_merges)
        key = record.semantic_key()
        existing_index = by_key.get(key)
        if existing_index is None:
            by_key[key] = len(normalized)
            normalized.append(record)
            continue
        retained = normalized[existing_index]
        normalized[existing_index] = replace(
            retained,
            source_spans=_merge_spans(retained.source_spans, record.source_spans),
        )
        duplicate_merges.append(
            {
                "retained_record_id": retained.record_id,
                "merged_record_id": record.record_id,
                "source_refs": [span.compact_ref for span in record.source_spans],
                "reason": "exact_semantic_duplicate",
            }
        )

    contained, containment_merges, provenance_refs = _containment_compact(normalized)

    compact_records: list[CompactRecord] = []
    source_to_compact: dict[str, tuple[str, ...]] = {}
    model_path_exceptions: list[str] = []
    for record in contained:
        chunks = _chunk_record(
            record,
            action_ordinal=frame.action_ordinal,
            source_refs=provenance_refs[record.record_id],
            max_chunk_tokens=max_chunk_tokens,
            model=model,
        )
        compact_records.append(CompactRecord(record=record, chunks=chunks))
        chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
        for source_ref in provenance_refs[record.record_id]:
            prior = source_to_compact.get(source_ref, ())
            source_to_compact[source_ref] = tuple(
                dict.fromkeys((*prior, *chunk_ids))
            )
        if record.element_context_key and not any(
            (
                record.text,
                record.role,
                record.accessible_name,
                record.direct_text,
                record.visible_text,
                record.tag,
                record.changed_field,
            )
        ):
            model_path_exceptions.append(record.record_id)

    receipt = TextCompactionReceipt(
        source_records=len(frame.records),
        compact_records=len(compact_records),
        compact_chunks=sum(len(record.chunks) for record in compact_records),
        source_text_chars=sum(
            len(record.text or "")
            for record in normalized
            if record.record_kind == "text"
        ),
        compact_text_chars=sum(
            len(record.record.text or "")
            for record in compact_records
            if record.record.record_kind == "text"
        ),
        exact_duplicates_removed=len(duplicate_merges),
        element_field_duplicates_removed=len(field_merges),
        contained_fragments_removed=len(containment_merges),
        geometry_only_changes_removed=frame.audit.parsed_record_counts.get(
            "viewport_geometry", 0
        ),
        records_truncated_by_char_limit=0,
        duplicate_merges=tuple(duplicate_merges),
        element_field_merges=tuple(field_merges),
        containment_merges=tuple(containment_merges),
        source_to_compact=source_to_compact,
        model_path_exceptions=tuple(model_path_exceptions),
    )
    return CompactDOMDiffTextFrame(
        action_ordinal=frame.action_ordinal,
        action_id=frame.action_id,
        task_id=frame.task_id,
        status=frame.status,
        action_type=frame.action_type,
        before_url=frame.before_url,
        after_url=frame.after_url,
        navigation=frame.navigation,
        coverage_warnings=frame.coverage_warnings,
        records=tuple(compact_records),
        receipt=receipt,
        source_path=frame.text_path,
        source_sha256=frame.source_sha256,
        source_bytes=frame.source_bytes,
        audit_receipt_id=frame.audit.audit_receipt_id,
    )


def compact_text_frames(
    frames: Iterable[DOMDiffTextEvidenceFrame],
    *,
    max_chunk_tokens: int = 256,
    model: str = "gpt-5.2",
) -> list[DOMDiffTextEvidenceFrame]:
    return [
        frame.with_compact(
            compact_text_frame(
                frame, max_chunk_tokens=max_chunk_tokens, model=model
            )
        )
        for frame in frames
    ]


def step_header(frame: CompactDOMDiffTextFrame) -> str:
    return (
        f"STEP {frame.action_ordinal} action={frame.action_type} "
        f"status={frame.status}"
    )


def page_line(frame: CompactDOMDiffTextFrame) -> str:
    return f"PAGE url={_quote(frame.before_url)} -> {_quote(frame.after_url)}"


def coverage_line(frame: CompactDOMDiffTextFrame) -> str:
    values = list(frame.coverage_warnings)
    return "COVERAGE " + ("; ".join(values) if values else "complete_for_declared_source")


def render_full_compact_frame(frame: CompactDOMDiffTextFrame) -> str:
    return "\n".join(
        [
            step_header(frame),
            page_line(frame),
            coverage_line(frame),
            *(chunk.text for chunk in frame.chunks),
        ]
    )


def build_trajectory_ledger(
    frames: Sequence[CompactDOMDiffTextFrame],
) -> CompactDOMDiffTextTrajectoryLedger:
    ordered = tuple(sorted(frames, key=lambda frame: frame.action_ordinal))
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for frame in ordered:
        for compact_record in frame.records:
            record = compact_record.record
            key = record.semantic_key()
            entry = grouped.setdefault(key, {"record": record, "occurrences": []})
            entry["occurrences"].append(
                RecordOccurrence(
                    action_ordinal=frame.action_ordinal,
                    frame_record_id=record.record_id,
                    source_spans=record.source_spans,
                    source_refs=tuple(
                        dict.fromkeys(
                            ref
                            for chunk in compact_record.chunks
                            for ref in chunk.source_refs
                        )
                    ),
                )
            )
    ledger_records = tuple(
        LedgerRecord(
            ledger_record_id=f"R{index}",
            record=value["record"],
            occurrences=tuple(value["occurrences"]),
        )
        for index, value in enumerate(grouped.values(), start=1)
    )
    return CompactDOMDiffTextTrajectoryLedger(
        frames=ordered,
        ordered_step_headers=tuple(step_header(frame) for frame in ordered),
        records=ledger_records,
    )


def render_ledger_record(record: LedgerRecord) -> str:
    steps = ",".join(str(step) for step in record.occurs_at_steps)
    rendered = render_record(record.record)
    return f"@{steps} {rendered}"


def aggregate_text_compaction_metrics(
    frames: Iterable[CompactDOMDiffTextFrame],
) -> dict[str, Any]:
    values = list(frames)
    source_bytes = sum(frame.source_bytes for frame in values)
    model_compact_bytes = sum(frame.model_bytes for frame in values)
    audit_bytes = sum(frame.audit_bytes for frame in values)
    return {
        "compact_schema_version": COMPACT_DOM_DIFF_TEXT_SCHEMA,
        "source_frame_count": len(values),
        "source_bytes": source_bytes,
        # Keep the historical keys, but define them as model-facing compact
        # size. Audit serialization is reported independently.
        "compact_bytes": model_compact_bytes,
        "compaction_ratio": (
            round(model_compact_bytes / source_bytes, 6) if source_bytes else None
        ),
        "model_compact_bytes": model_compact_bytes,
        "model_compaction_ratio": (
            round(model_compact_bytes / source_bytes, 6) if source_bytes else None
        ),
        "audit_bytes": audit_bytes,
        "source_records": sum(frame.receipt.source_records for frame in values),
        "compact_records": sum(frame.receipt.compact_records for frame in values),
        "compact_chunks": sum(frame.receipt.compact_chunks for frame in values),
        "source_text_chars": sum(
            frame.receipt.source_text_chars for frame in values
        ),
        "compact_text_chars": sum(
            frame.receipt.compact_text_chars for frame in values
        ),
        "exact_duplicates_removed": sum(
            frame.receipt.exact_duplicates_removed for frame in values
        ),
        "element_field_duplicates_removed": sum(
            frame.receipt.element_field_duplicates_removed for frame in values
        ),
        "contained_fragments_removed": sum(
            frame.receipt.contained_fragments_removed for frame in values
        ),
        "geometry_only_changes_removed": sum(
            frame.receipt.geometry_only_changes_removed for frame in values
        ),
        "records_truncated_by_char_limit": 0,
        "source_hashes": [frame.source_sha256 for frame in values],
    }
