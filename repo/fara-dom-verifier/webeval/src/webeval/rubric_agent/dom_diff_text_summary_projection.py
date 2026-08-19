"""Dense summary-style projection for strict ``dom_diffN.txt`` evidence.

This module is intentionally independent of the existing DOM-text compactor
and retrieval stack.  Source files are parsed by ``dom_diff_text_evidence``;
the resulting semantic records are projected directly into one compact frame
per action for the summary-S3 call topology.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Sequence

from webeval.rubric_agent.dom_diff_summary_compaction import (
    CompactElementChange,
    CompactElementRecord,
    matching_key,
    normalize_text,
)
from webeval.rubric_agent.dom_diff_text_evidence import (
    DOMDiffTextEvidenceFrame,
    SemanticRecord,
    SourceSpan,
)


COMPACT_DOM_DIFF_TEXT_SUMMARY_SCHEMA = "compact-dom-diff-text-summary/v1"
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d[\d,.'’]*)(?:\s?(?:%|[A-Za-z°²³]+))?")
_IMPORTANT_RE = re.compile(
    r"\b(error|failed|warning|invalid|success|confirmed|complete|completed|"
    r"submitted|saved|deleted|blocked)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextSummaryProjectionReceipt:
    exact_duplicates_removed: int = 0
    contained_fragments_removed: int = 0
    element_duplicates_removed: int = 0
    records_truncated_by_char_limit: int = 0
    geometry_only_changes_removed: int = 0
    source_truncation_detected: bool = False
    coverage_warnings: tuple[str, ...] = ()
    document_text_values_grouped: int = 0
    document_text_blocks_created: int = 0
    repeated_document_text_occurrences_factored: int = 0

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["coverage_warnings"] = list(self.coverage_warnings)
        return value


@dataclass(frozen=True)
class DocumentStateOccurrence:
    """One direction-preserving occurrence of shared document text."""

    frame_index: int
    action_ordinal: int
    direction: str
    url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentTextValueProvenance:
    """Audit-only source spans for one exact model-facing text value."""

    value: str
    source_spans: tuple[SourceSpan, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source_spans": [span.to_dict() for span in self.source_spans],
        }


@dataclass(frozen=True)
class DocumentTextBlock:
    """Complete text values grouped without clipping value boundaries."""

    values: tuple[str, ...]
    provenance: tuple[DocumentTextValueProvenance, ...]

    def to_dict(self, *, include_audit: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {"values": list(self.values)}
        if include_audit:
            value["provenance"] = [item.to_dict() for item in self.provenance]
        return value


@dataclass(frozen=True)
class DocumentPageState:
    """Shared text whose exact occurrence history is identical across frames."""

    state_label: str
    state_sha256: str
    occurrences: tuple[DocumentStateOccurrence, ...]
    blocks: tuple[DocumentTextBlock, ...]

    def to_dict(self, *, include_audit: bool = True) -> dict[str, Any]:
        return {
            "state_label": self.state_label,
            "state_sha256": self.state_sha256,
            "occurrences": [item.to_dict() for item in self.occurrences],
            "blocks": [
                item.to_dict(include_audit=include_audit) for item in self.blocks
            ],
        }


@dataclass(frozen=True)
class CompactDOMDiffTextSummaryFrame:
    """One text diff projected into the dense record families used by S3."""

    action_ordinal: int
    action_id: str
    action_type: str
    status: str
    source_path: str
    source_sha256: str
    source_bytes: int
    audit_receipt_id: str
    before_url: str
    after_url: str
    page: dict[str, Any]
    counts: dict[str, int]
    document_text_added: tuple[str, ...]
    document_text_removed: tuple[str, ...]
    viewport_text_entered: tuple[str, ...]
    viewport_text_exited: tuple[str, ...]
    document_page_states: tuple[DocumentPageState, ...]
    interactive_added: tuple[CompactElementRecord, ...]
    interactive_removed: tuple[CompactElementRecord, ...]
    interactive_changed: tuple[CompactElementChange, ...]
    receipt: TextSummaryProjectionReceipt
    schema_version: str = COMPACT_DOM_DIFF_TEXT_SUMMARY_SCHEMA

    # Compatibility views used only by the unchanged summary selection-receipt
    # helper. Model-facing rendering keeps DOC and VIEW operations separate.
    @property
    def text_added(self) -> tuple[str, ...]:
        shared = tuple(
            value
            for state in self.document_page_states
            if any(
                occurrence.action_ordinal == self.action_ordinal
                and occurrence.direction == "added"
                for occurrence in state.occurrences
            )
            for block in state.blocks
            for value in block.values
        )
        return (*self.document_text_added, *shared, *self.viewport_text_entered)

    @property
    def text_removed(self) -> tuple[str, ...]:
        shared = tuple(
            value
            for state in self.document_page_states
            if any(
                occurrence.action_ordinal == self.action_ordinal
                and occurrence.direction == "removed"
                for occurrence in state.occurrences
            )
            for block in state.blocks
            for value in block.values
        )
        return (*self.document_text_removed, *shared, *self.viewport_text_exited)

    def to_dict(self, *, include_audit: bool = True) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "action_ordinal": self.action_ordinal,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "status": self.status,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "source_bytes": self.source_bytes,
            "audit_receipt_id": self.audit_receipt_id,
            "before_url": self.before_url,
            "after_url": self.after_url,
            "page": self.page,
            "counts": self.counts,
            "document_text_added": list(self.document_text_added),
            "document_text_removed": list(self.document_text_removed),
            "viewport_text_entered": list(self.viewport_text_entered),
            "viewport_text_exited": list(self.viewport_text_exited),
            "document_page_states": [
                item.to_dict(include_audit=include_audit)
                for item in self.document_page_states
            ],
            "interactive_added": [item.to_dict() for item in self.interactive_added],
            "interactive_removed": [
                item.to_dict() for item in self.interactive_removed
            ],
            "interactive_changed": [
                item.to_dict() for item in self.interactive_changed
            ],
            "receipt": self.receipt.to_dict(),
        }

    @property
    def compact_bytes(self) -> int:
        return len(
            json.dumps(
                self.to_dict(include_audit=False),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )


def _clip(value: Any, limit: int) -> tuple[str, bool]:
    normalized = normalize_text(value)
    if len(normalized) <= limit:
        return normalized, False
    if limit <= 1:
        return "…", True
    return normalized[: limit - 1].rstrip() + "…", True


def _facts(value: str) -> frozenset[str]:
    return frozenset(match.group(0).casefold() for match in _NUMBER_RE.finditer(value))


def _compact_text_values(
    records: Sequence[SemanticRecord], max_chars: int
) -> tuple[tuple[str, ...], int, int, int]:
    values: list[str] = []
    seen: set[str] = set()
    exact = truncated = 0
    for record in records:
        value, clipped = _clip(record.text or "", max_chars)
        truncated += int(clipped)
        if not value:
            continue
        key = matching_key(value)
        if key in seen:
            exact += 1
            continue
        seen.add(key)
        values.append(value)

    contained: set[int] = set()
    for index, value in enumerate(values):
        key = matching_key(value)
        if len(key) < 8:
            continue
        for other_index, other in enumerate(values):
            if index == other_index or len(other) <= len(value):
                continue
            if key in matching_key(other) and _facts(value).issubset(_facts(other)):
                contained.add(index)
                break
    return (
        tuple(value for index, value in enumerate(values) if index not in contained),
        exact,
        len(contained),
        truncated,
    )


def _pairs_text(values: Sequence[tuple[str, str]]) -> str:
    return ",".join(
        f"{normalize_text(name)}={normalize_text(value)}" for name, value in values
    )


def _element(
    record: SemanticRecord, max_chars: int
) -> tuple[CompactElementRecord, int]:
    truncated = 0

    def clipped(value: Any) -> str:
        nonlocal truncated
        output, was_clipped = _clip(value, max_chars)
        truncated += int(was_clipped)
        return output

    text = clipped(record.direct_text or record.visible_text or "")
    context_parts: list[str] = []
    if record.visible_text and normalize_text(record.visible_text) != normalize_text(
        text
    ):
        context_parts.append(f"visible={normalize_text(record.visible_text)}")
    if record.tag:
        context_parts.append(f"tag={normalize_text(record.tag)}")
    if record.scope:
        context_parts.append(f"scope={normalize_text(record.scope)}")
    if record.semantic_boundary:
        context_parts.append(f"boundary={normalize_text(record.semantic_boundary)}")
    if record.supported_actions:
        context_parts.append(
            "actions="
            + ",".join(normalize_text(item) for item in record.supported_actions)
        )
    if record.selected_attributes:
        context_parts.append("attributes=" + _pairs_text(record.selected_attributes))
    if record.states:
        context_parts.append("states=" + _pairs_text(record.states))
    if record.interactive_descendants:
        context_parts.append(
            "interactive="
            + " | ".join(
                normalize_text(item) for item in record.interactive_descendants
            )
        )
    if record.repeated_group_count is not None:
        context_parts.append(f"repeated_count={record.repeated_group_count}")
    if record.repeated_group_samples:
        context_parts.append(
            "samples="
            + " | ".join(normalize_text(item) for item in record.repeated_group_samples)
        )
    context = clipped("; ".join(part for part in context_parts if part))
    href = ""
    for name, value in record.selected_attributes:
        if matching_key(name) == "href":
            href = clipped(value)
            break
    return (
        CompactElementRecord(
            role=clipped(record.role or ""),
            accessible_name=clipped(record.accessible_name or ""),
            text=text,
            context=context,
            href=href,
        ),
        truncated,
    )


def _compact_elements(
    records: Sequence[SemanticRecord], max_chars: int
) -> tuple[tuple[CompactElementRecord, ...], int, int]:
    output: list[CompactElementRecord] = []
    seen: set[tuple[str, ...]] = set()
    duplicates = truncated = 0
    for record in records:
        element, count = _element(record, max_chars)
        truncated += count
        if element.identity in seen:
            duplicates += 1
            continue
        seen.add(element.identity)
        output.append(element)
    return tuple(output), duplicates, truncated


def _compact_changes(
    records: Sequence[SemanticRecord], max_chars: int
) -> tuple[tuple[CompactElementChange, ...], int]:
    grouped: dict[str, list[tuple[str, str, str]]] = {}
    order: list[str] = []
    truncated = 0
    for record in records:
        key = record.element_context_key or f"line:{len(order)}"
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        field_name, field_clipped = _clip(record.changed_field or "state", max_chars)
        before, before_clipped = _clip(
            json.dumps(record.before_value, ensure_ascii=False, sort_keys=True)
            if not isinstance(record.before_value, str)
            else record.before_value,
            max_chars,
        )
        after, after_clipped = _clip(
            json.dumps(record.after_value, ensure_ascii=False, sort_keys=True)
            if not isinstance(record.after_value, str)
            else record.after_value,
            max_chars,
        )
        truncated += int(field_clipped) + int(before_clipped) + int(after_clipped)
        grouped[key].append((field_name, before, after))
    return (
        tuple(
            CompactElementChange(
                element=CompactElementRecord(),
                changes=tuple(grouped[key]),
            )
            for key in order
        ),
        truncated,
    )


def _project_text_summary_frame_base(
    frame: DOMDiffTextEvidenceFrame,
    *,
    previous_url: str | None = None,
    max_record_chars: int = 600,
) -> CompactDOMDiffTextSummaryFrame:
    """Project one parsed text frame without using the legacy text compactor."""
    if max_record_chars <= 0:
        raise ValueError("max_record_chars must be positive")
    by_operation = {
        (operation, scope): [
            record
            for record in frame.records
            if record.operation == operation and record.scope == scope
        ]
        for operation, scope in (
            ("added", "document_text"),
            ("removed", "document_text"),
            ("viewport_entered", "viewport_text"),
            ("viewport_exited", "viewport_text"),
        )
    }
    text_results = {
        key: _compact_text_values(records, max_record_chars)
        for key, records in by_operation.items()
    }
    added_elements, added_duplicates, added_truncated = _compact_elements(
        [
            record
            for record in frame.records
            if record.record_kind == "element" and record.operation == "added"
        ],
        max_record_chars,
    )
    removed_elements, removed_duplicates, removed_truncated = _compact_elements(
        [
            record
            for record in frame.records
            if record.record_kind == "element" and record.operation == "removed"
        ],
        max_record_chars,
    )
    changes, changed_truncated = _compact_changes(
        [record for record in frame.records if record.operation == "changed"],
        max_record_chars,
    )
    warning_values: list[str] = []
    warning_truncated = 0
    for warning in frame.coverage_warnings:
        value, clipped = _clip(warning, max_record_chars)
        warning_values.append(value)
        warning_truncated += int(clipped)
    exact = sum(result[1] for result in text_results.values())
    contained = sum(result[2] for result in text_results.values())
    text_truncated = sum(result[3] for result in text_results.values())
    page_changed = previous_url is None or frame.before_url != frame.after_url
    page = {
        "url_before": frame.before_url if page_changed else None,
        "url_after": frame.after_url if page_changed else None,
        "document_replaced": frame.status == "document_replaced",
    }
    receipt = TextSummaryProjectionReceipt(
        exact_duplicates_removed=exact,
        contained_fragments_removed=contained,
        element_duplicates_removed=added_duplicates + removed_duplicates,
        records_truncated_by_char_limit=(
            text_truncated
            + added_truncated
            + removed_truncated
            + changed_truncated
            + warning_truncated
        ),
        geometry_only_changes_removed=int(
            frame.audit.parsed_record_counts.get("viewport_geometry", 0)
        ),
        source_truncation_detected=any(
            warning
            in {
                "source_entries_truncated",
                "source_entries_dropped",
                "source_candidates_not_fully_emitted",
            }
            for warning in frame.coverage_warnings
        ),
        coverage_warnings=tuple(dict.fromkeys(warning_values)),
    )
    return CompactDOMDiffTextSummaryFrame(
        action_ordinal=frame.action_ordinal,
        action_id=frame.action_id,
        action_type=frame.action_type,
        status=frame.status,
        source_path=frame.text_path,
        source_sha256=frame.source_sha256,
        source_bytes=frame.source_bytes,
        audit_receipt_id=frame.audit.audit_receipt_id,
        before_url=frame.before_url,
        after_url=frame.after_url,
        page=page,
        counts={
            "document_text_added": len(by_operation[("added", "document_text")]),
            "document_text_removed": len(by_operation[("removed", "document_text")]),
            "viewport_text_entered": len(
                by_operation[("viewport_entered", "viewport_text")]
            ),
            "viewport_text_exited": len(
                by_operation[("viewport_exited", "viewport_text")]
            ),
            "interactive_added": len(added_elements),
            "interactive_removed": len(removed_elements),
            "interactive_changed": len(changes),
        },
        document_text_added=text_results[("added", "document_text")][0],
        document_text_removed=text_results[("removed", "document_text")][0],
        viewport_text_entered=text_results[("viewport_entered", "viewport_text")][0],
        viewport_text_exited=text_results[("viewport_exited", "viewport_text")][0],
        document_page_states=(),
        interactive_added=added_elements,
        interactive_removed=removed_elements,
        interactive_changed=changes,
        receipt=receipt,
    )


def _spans_for_document_values(
    frame: DOMDiffTextEvidenceFrame,
    *,
    operation: str,
    max_record_chars: int,
) -> dict[str, tuple[SourceSpan, ...]]:
    output: dict[str, list[SourceSpan]] = {}
    for record in frame.records:
        if record.scope != "document_text" or record.operation != operation:
            continue
        value, _ = _clip(record.text or "", max_record_chars)
        if not value:
            continue
        spans = output.setdefault(value, [])
        for span in record.source_spans:
            if span not in spans:
                spans.append(span)
    return {value: tuple(spans) for value, spans in output.items()}


def _pack_document_text_blocks(
    values: Sequence[str],
    provenance: dict[str, tuple[SourceSpan, ...]],
    *,
    max_record_chars: int,
) -> tuple[DocumentTextBlock, ...]:
    """Group complete values into bounded blocks without cutting a value."""
    blocks: list[DocumentTextBlock] = []
    current: list[str] = []

    def emit() -> None:
        if not current:
            return
        blocks.append(
            DocumentTextBlock(
                values=tuple(current),
                provenance=tuple(
                    DocumentTextValueProvenance(
                        value=value,
                        source_spans=provenance.get(value, ()),
                    )
                    for value in current
                ),
            )
        )

    for value in values:
        candidate = [*current, value]
        encoded = json.dumps(
            candidate,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if current and len(encoded) > max_record_chars:
            emit()
            current = [value]
        else:
            current = candidate
    emit()
    return tuple(blocks)


def _factor_document_page_states(
    source_frames: Sequence[DOMDiffTextEvidenceFrame],
    compact_frames: Sequence[CompactDOMDiffTextSummaryFrame],
    *,
    max_record_chars: int,
) -> list[CompactDOMDiffTextSummaryFrame]:
    """Store each exact document-text value once with every signed occurrence."""
    if len(source_frames) != len(compact_frames):
        raise ValueError("Source/compact frame count mismatch")

    values_in_order: list[str] = []
    occurrences_by_value: dict[str, list[DocumentStateOccurrence]] = {}
    provenance_by_value: dict[str, list[SourceSpan]] = {}

    for frame_index, (source, compact) in enumerate(
        zip(source_frames, compact_frames, strict=True)
    ):
        if compact.status != "document_replaced":
            continue
        spans_by_direction = {
            "added": _spans_for_document_values(
                source,
                operation="added",
                max_record_chars=max_record_chars,
            ),
            "removed": _spans_for_document_values(
                source,
                operation="removed",
                max_record_chars=max_record_chars,
            ),
        }
        for direction, url, values in (
            ("added", compact.after_url, compact.document_text_added),
            ("removed", compact.before_url, compact.document_text_removed),
        ):
            for value in values:
                if value not in occurrences_by_value:
                    values_in_order.append(value)
                    occurrences_by_value[value] = []
                    provenance_by_value[value] = []
                occurrence = DocumentStateOccurrence(
                    frame_index=frame_index,
                    action_ordinal=compact.action_ordinal,
                    direction=direction,
                    url=url,
                )
                if occurrence not in occurrences_by_value[value]:
                    occurrences_by_value[value].append(occurrence)
                for span in spans_by_direction[direction].get(value, ()):
                    if span not in provenance_by_value[value]:
                        provenance_by_value[value].append(span)

    grouped_values: dict[
        tuple[tuple[DocumentStateOccurrence, ...], bool], list[str]
    ] = {}
    for value in values_in_order:
        occurrences = tuple(occurrences_by_value[value])
        has_priority_signal = bool(
            _NUMBER_RE.search(value) or _IMPORTANT_RE.search(value)
        )
        grouped_values.setdefault((occurrences, has_priority_signal), []).append(value)

    states: list[DocumentPageState] = []
    for state_index, (
        (occurrences, has_priority_signal),
        values,
    ) in enumerate(grouped_values.items()):
        signature = json.dumps(
            {
                "occurrences": [item.to_dict() for item in occurrences],
                "priority_signal": has_priority_signal,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        state_hash = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        states.append(
            DocumentPageState(
                state_label=f"P{state_index}",
                state_sha256=state_hash,
                occurrences=occurrences,
                blocks=_pack_document_text_blocks(
                    values,
                    {value: tuple(provenance_by_value[value]) for value in values},
                    max_record_chars=max_record_chars,
                ),
            )
        )

    states_by_frame: dict[int, list[DocumentPageState]] = {
        index: [] for index in range(len(compact_frames))
    }
    for state in states:
        for frame_index in dict.fromkeys(
            occurrence.frame_index for occurrence in state.occurrences
        ):
            states_by_frame[frame_index].append(state)

    output: list[CompactDOMDiffTextSummaryFrame] = []
    for frame_index, compact in enumerate(compact_frames):
        frame_states = tuple(states_by_frame[frame_index])
        grouped_value_count = len(compact.document_text_added) + len(
            compact.document_text_removed
        )
        repeated_occurrences = 0
        for state in frame_states:
            first = state.occurrences[0]
            value_count = sum(len(block.values) for block in state.blocks)
            for occurrence in state.occurrences:
                if occurrence.frame_index != frame_index:
                    continue
                if occurrence != first:
                    repeated_occurrences += value_count
        receipt = replace(
            compact.receipt,
            document_text_values_grouped=grouped_value_count,
            document_text_blocks_created=sum(
                len(state.blocks) for state in frame_states
            ),
            repeated_document_text_occurrences_factored=repeated_occurrences,
        )
        if compact.status == "document_replaced":
            output.append(
                replace(
                    compact,
                    document_text_added=(),
                    document_text_removed=(),
                    document_page_states=frame_states,
                    receipt=receipt,
                )
            )
        else:
            output.append(
                replace(
                    compact,
                    document_page_states=frame_states,
                    receipt=receipt,
                )
            )
    return output


def project_text_summary_frame(
    frame: DOMDiffTextEvidenceFrame,
    *,
    previous_url: str | None = None,
    max_record_chars: int = 600,
) -> CompactDOMDiffTextSummaryFrame:
    """Project one frame through the same page-state factoring used in a trajectory."""
    compact = _project_text_summary_frame_base(
        frame,
        previous_url=previous_url,
        max_record_chars=max_record_chars,
    )
    return _factor_document_page_states(
        [frame],
        [compact],
        max_record_chars=max_record_chars,
    )[0]


def project_text_summary_frames(
    frames: Iterable[DOMDiffTextEvidenceFrame],
    *,
    max_record_chars: int = 600,
) -> list[DOMDiffTextEvidenceFrame]:
    source_frames = list(frames)
    base_frames: list[CompactDOMDiffTextSummaryFrame] = []
    previous_url: str | None = None
    for frame in source_frames:
        base_frames.append(
            _project_text_summary_frame_base(
                frame,
                previous_url=previous_url,
                max_record_chars=max_record_chars,
            )
        )
        previous_url = frame.after_url
    compact_frames = _factor_document_page_states(
        source_frames,
        base_frames,
        max_record_chars=max_record_chars,
    )
    return [
        source.with_compact(compact)
        for source, compact in zip(source_frames, compact_frames, strict=True)
    ]


def aggregate_text_summary_projection_metrics(
    frames: Iterable[CompactDOMDiffTextSummaryFrame],
) -> dict[str, Any]:
    values = list(frames)
    source_bytes = sum(frame.source_bytes for frame in values)
    state_catalog: dict[str, DocumentPageState] = {}
    compact_frame_values: list[dict[str, Any]] = []
    for frame in values:
        compact_value = frame.to_dict(include_audit=False)
        compact_value.pop("document_page_states", None)
        compact_value["document_page_state_refs"] = [
            state.state_sha256 for state in frame.document_page_states
        ]
        compact_frame_values.append(compact_value)
        for state in frame.document_page_states:
            state_catalog.setdefault(state.state_sha256, state)
    compact_payload = {
        "frames": compact_frame_values,
        "document_page_state_catalog": [
            state.to_dict(include_audit=False) for state in state_catalog.values()
        ],
    }
    compact_bytes = len(
        json.dumps(
            compact_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return {
        "compact_schema_version": COMPACT_DOM_DIFF_TEXT_SUMMARY_SCHEMA,
        "source_frame_count": len(values),
        "source_bytes": source_bytes,
        "compact_bytes": compact_bytes,
        "compaction_ratio": round(compact_bytes / source_bytes, 6)
        if source_bytes
        else None,
        "exact_duplicates_removed": sum(
            frame.receipt.exact_duplicates_removed for frame in values
        ),
        "contained_fragments_removed": sum(
            frame.receipt.contained_fragments_removed for frame in values
        ),
        "element_duplicates_removed": sum(
            frame.receipt.element_duplicates_removed for frame in values
        ),
        "records_truncated_by_char_limit": sum(
            frame.receipt.records_truncated_by_char_limit for frame in values
        ),
        "geometry_only_changes_removed": sum(
            frame.receipt.geometry_only_changes_removed for frame in values
        ),
        "document_page_states": len(state_catalog),
        "document_text_blocks": sum(
            len(state.blocks) for state in state_catalog.values()
        ),
        "document_text_values": sum(
            len(block.values)
            for state in state_catalog.values()
            for block in state.blocks
        ),
        "repeated_document_text_occurrences_factored": sum(
            frame.receipt.repeated_document_text_occurrences_factored
            for frame in values
        ),
        "source_hashes": [frame.source_sha256 for frame in values],
    }
