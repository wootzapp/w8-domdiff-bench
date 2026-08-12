"""Deterministic semantic compaction for ``dom_diff_summary`` evidence only.

The raw recorder summaries remain authoritative.  This module creates an
auditable, model-facing projection that removes volatile geometry, collapses
duplicate text, and enforces record-boundary token budgets without calling an
LLM.  It is intentionally independent from the raw DOM-diff and full-DOM
projectors.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Sequence


COMPACT_SUMMARY_SCHEMA = "dom-diff-summary-compact/v2"
SUPPORTED_SOURCE_SCHEMAS = {"1.0"}
SUPPORTED_SOURCE_METHODS = {"local_agent_observation_summary"}

SEMANTIC_CHANGE_FIELDS = {
    "accessibleName",
    "text",
    "href",
    "value",
    "checked",
    "selected",
    "expanded",
    "disabled",
    "pressed",
}
GEOMETRY_FIELDS = {"bounds", "centerX", "centerY", "x", "y", "width", "height"}
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d[\d,.'’]*)(?:\s?(?:%|[A-Za-z°²³]+))?")
_IMPORTANT_RE = re.compile(
    r"\b(error|failed|failure|warning|invalid|success|successful|confirmed|"
    r"complete|completed|submitted|saved|deleted|cancelled|canceled|blocked)\b",
    re.IGNORECASE,
)


def source_sha256(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def normalize_text(value: Any) -> str:
    """Normalize display text without changing case, punctuation, or units."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def matching_key(value: Any) -> str:
    return normalize_text(value).casefold()


def validate_source_summary(summary: dict[str, Any]) -> None:
    if not isinstance(summary, dict):
        raise ValueError("DOM diff summary must be a JSON object")
    schema = str(summary.get("schema_version") or "")
    if schema not in SUPPORTED_SOURCE_SCHEMAS:
        raise ValueError(f"Unsupported DOM diff summary schema_version: {schema!r}")
    method = str(summary.get("method") or "")
    if method not in SUPPORTED_SOURCE_METHODS:
        raise ValueError(f"Unsupported DOM diff summary method: {method!r}")
    for key in ("url", "title", "scroll", "stats"):
        if not isinstance(summary.get(key), dict):
            raise ValueError(f"DOM diff summary field {key!r} must be an object")
    for key in (
        "visible_text_added",
        "visible_text_removed",
        "interactive_added",
        "interactive_removed",
        "interactive_changed",
    ):
        if not isinstance(summary.get(key), list):
            raise ValueError(f"DOM diff summary field {key!r} must be a list")


@dataclass(frozen=True)
class CompactElementRecord:
    role: str = ""
    accessible_name: str = ""
    text: str = ""
    context: str = ""
    href: str = ""

    @property
    def identity(self) -> tuple[str, ...]:
        return tuple(
            matching_key(value)
            for value in (
                self.role,
                self.accessible_name,
                self.href,
                self.text,
            )
        )

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value not in ("", None)
        }


@dataclass(frozen=True)
class CompactElementChange:
    element: CompactElementRecord
    changes: tuple[tuple[str, str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element.to_dict(),
            "changes": {
                field_name: {"before": before, "after": after}
                for field_name, before, after in self.changes
            },
        }


@dataclass(frozen=True)
class CompactionReceipt:
    geometry_only_changes_removed: int = 0
    exact_duplicates_removed: int = 0
    contained_fragments_removed: int = 0
    element_duplicates_removed: int = 0
    records_truncated_by_char_limit: int = 0
    source_truncation_detected: bool = False


@dataclass(frozen=True)
class CompactDOMDiffSummaryFrame:
    action_ordinal: int
    action_id: str
    source_path: str
    source_sha256: str
    source_bytes: int
    source_schema_version: str
    page: dict[str, Any]
    counts: dict[str, int]
    text_added: tuple[str, ...]
    text_removed: tuple[str, ...]
    interactive_added: tuple[CompactElementRecord, ...]
    interactive_removed: tuple[CompactElementRecord, ...]
    interactive_changed: tuple[CompactElementChange, ...]
    receipt: CompactionReceipt
    schema_version: str = COMPACT_SUMMARY_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_schema_version": self.source_schema_version,
            "action_ordinal": self.action_ordinal,
            "action_id": self.action_id,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "source_bytes": self.source_bytes,
            "page": self.page,
            "counts": self.counts,
            "text_added": list(self.text_added),
            "text_removed": list(self.text_removed),
            "interactive_added": [value.to_dict() for value in self.interactive_added],
            "interactive_removed": [value.to_dict() for value in self.interactive_removed],
            "interactive_changed": [value.to_dict() for value in self.interactive_changed],
            "receipt": asdict(self.receipt),
        }

    @property
    def compact_bytes(self) -> int:
        return len(
            json.dumps(
                self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )


@dataclass(frozen=True)
class RenderedSummary:
    text: str
    estimated_tokens: int
    tokenizer: str
    records_total: int
    records_rendered: int
    records_omitted_by_budget: int


@dataclass(frozen=True)
class LedgerRecord:
    line: str
    steps: tuple[int, ...]
    priority: int
    hard_retained: bool = False


@dataclass(frozen=True)
class CompactTrajectoryLedger:
    frames: tuple[CompactDOMDiffSummaryFrame, ...]
    page_lines: tuple[str, ...]
    records: tuple[LedgerRecord, ...]


class TokenEstimator:
    """Local token estimator with an explicit conservative fallback."""

    def __init__(self, model: str = "gpt-5.2") -> None:
        self.model = model
        self._encoding = None
        self.name = "conservative-char-divisor-3"
        try:
            import tiktoken

            try:
                self._encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                self._encoding = tiktoken.get_encoding("o200k_base")
            self.name = getattr(self._encoding, "name", "tiktoken")
        except (ImportError, OSError, ValueError):
            self._encoding = None

    def count(self, text: str) -> int:
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        # Deliberately conservative for mixed JSON/DOM text.
        return max(1, (len(text) + 2) // 3)


def _clip(value: str, limit: int) -> tuple[str, bool]:
    if limit <= 0 or len(value) <= limit:
        return value, False
    if limit == 1:
        return "…", True
    return value[: limit - 1].rstrip() + "…", True


def _facts(value: str) -> frozenset[str]:
    return frozenset(match.group(0).casefold() for match in _NUMBER_RE.finditer(value))


def _dedupe_text(values: Sequence[Any], max_chars: int) -> tuple[tuple[str, ...], int, int, int]:
    normalized: list[str] = []
    seen: set[str] = set()
    exact_removed = truncated = 0
    for raw in values:
        value = normalize_text(raw)
        if not value:
            continue
        value, was_truncated = _clip(value, max_chars)
        truncated += int(was_truncated)
        key = value.casefold()
        if key in seen:
            exact_removed += 1
            continue
        seen.add(key)
        normalized.append(value)

    contained: set[int] = set()
    for index, value in enumerate(normalized):
        key = value.casefold()
        if len(key) < 8:
            continue
        for other_index, other in enumerate(normalized):
            if index == other_index or len(other) <= len(value):
                continue
            if key in other.casefold() and _facts(value).issubset(_facts(other)):
                contained.add(index)
                break
    output = tuple(value for index, value in enumerate(normalized) if index not in contained)
    return output, exact_removed, len(contained), truncated


def _compact_element(value: Any, max_chars: int) -> tuple[CompactElementRecord, int]:
    if not isinstance(value, dict):
        raise ValueError("Interactive DOM summary records must be objects")
    truncated = 0
    fields: dict[str, str] = {}
    for output_key, source_key in (
        ("role", "role"),
        ("accessible_name", "accessibleName"),
        ("text", "text"),
        ("context", "context"),
        ("href", "href"),
    ):
        normalized = normalize_text(value.get(source_key))
        normalized, was_truncated = _clip(normalized, max_chars)
        fields[output_key] = normalized
        truncated += int(was_truncated)
    return CompactElementRecord(**fields), truncated


def _dedupe_elements(
    values: Sequence[Any], max_chars: int
) -> tuple[tuple[CompactElementRecord, ...], int, int]:
    output: list[CompactElementRecord] = []
    seen: set[tuple[str, ...]] = set()
    duplicates = truncated = 0
    for raw in values:
        record, record_truncated = _compact_element(raw, max_chars)
        truncated += record_truncated
        if record.identity in seen:
            duplicates += 1
            continue
        seen.add(record.identity)
        output.append(record)
    return tuple(output), duplicates, truncated


def _compact_changes(
    values: Sequence[Any], max_chars: int
) -> tuple[tuple[CompactElementChange, ...], int, int]:
    output: list[CompactElementChange] = []
    geometry_only = truncated = 0
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            raise ValueError("interactive_changed entries must be objects")
        changes = raw.get("changes")
        if not isinstance(changes, dict):
            raise ValueError("interactive_changed.changes must be an object")
        semantic_fields = sorted(set(changes) & SEMANTIC_CHANGE_FIELDS)
        if not semantic_fields:
            geometry_only += 1
            continue
        element, element_truncated = _compact_element(raw.get("element") or {}, max_chars)
        truncated += element_truncated
        compact_changes: list[tuple[str, str, str]] = []
        for field_name in semantic_fields:
            change = changes[field_name]
            if not isinstance(change, dict):
                raise ValueError(f"Semantic change {field_name!r} must be an object")
            before, before_truncated = _clip(normalize_text(change.get("before")), max_chars)
            after, after_truncated = _clip(normalize_text(change.get("after")), max_chars)
            truncated += int(before_truncated) + int(after_truncated)
            compact_changes.append((field_name, before, after))
        record = CompactElementChange(element=element, changes=tuple(compact_changes))
        key = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        output.append(record)
    return tuple(output), geometry_only, truncated


def _source_truncated(summary: dict[str, Any]) -> bool:
    stats = summary.get("stats") or {}
    for state_name in ("before", "after"):
        state = stats.get(state_name) or {}
        for candidate_key, returned_key in (
            ("candidateInteractives", "returnedInteractives"),
            ("candidateContentBlocks", "returnedContentBlocks"),
        ):
            candidate = state.get(candidate_key)
            returned = state.get(returned_key)
            if isinstance(candidate, (int, float)) and isinstance(returned, (int, float)):
                if candidate > returned:
                    return True
    return any(
        len(summary.get(key) or []) >= 100
        for key in ("visible_text_added", "visible_text_removed", "interactive_added", "interactive_removed")
    )


def compact_summary_frame(
    summary: dict[str, Any],
    *,
    action_ordinal: int,
    action_id: str,
    source_path: str,
    source_hash: str,
    source_bytes: int,
    previous_url: str | None = None,
    previous_title: str | None = None,
    max_record_chars: int = 600,
) -> CompactDOMDiffSummaryFrame:
    validate_source_summary(summary)
    if action_ordinal <= 0:
        raise ValueError("action_ordinal must be positive")
    if max_record_chars <= 0:
        raise ValueError("max_record_chars must be positive")

    url = summary["url"]
    title = summary["title"]
    scroll = summary["scroll"]
    url_after = normalize_text(url.get("after"))
    title_after = normalize_text(title.get("after"))
    page = {
        "url_after": (
            url_after
            if previous_url is None or bool(url.get("changed")) or url_after != previous_url
            else None
        ),
        "title_after": (
            title_after
            if previous_title is None or bool(title.get("changed")) or title_after != previous_title
            else None
        ),
        "scroll_y_before": None,
        "scroll_y_after": None,
        "document_height_before": None,
        "document_height_after": None,
    }
    if bool(scroll.get("changed")):
        before_scroll = scroll.get("before") or {}
        after_scroll = scroll.get("after") or {}
        page.update(
            scroll_y_before=before_scroll.get("scrollY"),
            scroll_y_after=after_scroll.get("scrollY"),
            document_height_before=before_scroll.get("scrollHeight"),
            document_height_after=after_scroll.get("scrollHeight"),
        )

    text_added, exact_added, contained_added, text_added_truncated = _dedupe_text(
        summary["visible_text_added"], max_record_chars
    )
    text_removed, exact_removed, contained_removed, text_removed_truncated = _dedupe_text(
        summary["visible_text_removed"], max_record_chars
    )
    interactive_added, added_duplicates, added_truncated = _dedupe_elements(
        summary["interactive_added"], max_record_chars
    )
    interactive_removed, removed_duplicates, removed_truncated = _dedupe_elements(
        summary["interactive_removed"], max_record_chars
    )
    interactive_changed, geometry_only, changed_truncated = _compact_changes(
        summary["interactive_changed"], max_record_chars
    )

    stats = summary.get("stats") or {}
    counts = {
        "text_added": len(summary["visible_text_added"]),
        "text_removed": len(summary["visible_text_removed"]),
        "interactive_added": len(summary["interactive_added"]),
        "interactive_removed": len(summary["interactive_removed"]),
        "interactive_changed": len(summary["interactive_changed"]),
        "interactive_semantic_changed": len(interactive_changed),
        "elements_added": int(stats.get("elements_added") or 0),
        "elements_removed": int(stats.get("elements_removed") or 0),
        "elements_changed": int(stats.get("elements_changed") or 0),
    }
    receipt = CompactionReceipt(
        geometry_only_changes_removed=geometry_only,
        exact_duplicates_removed=exact_added + exact_removed,
        contained_fragments_removed=contained_added + contained_removed,
        element_duplicates_removed=added_duplicates + removed_duplicates,
        records_truncated_by_char_limit=(
            text_added_truncated
            + text_removed_truncated
            + added_truncated
            + removed_truncated
            + changed_truncated
        ),
        source_truncation_detected=_source_truncated(summary),
    )
    return CompactDOMDiffSummaryFrame(
        action_ordinal=action_ordinal,
        action_id=action_id,
        source_path=source_path,
        source_sha256=source_hash,
        source_bytes=source_bytes,
        source_schema_version=str(summary["schema_version"]),
        page=page,
        counts=counts,
        text_added=text_added,
        text_removed=text_removed,
        interactive_added=interactive_added,
        interactive_removed=interactive_removed,
        interactive_changed=interactive_changed,
        receipt=receipt,
    )


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _element_line(prefix: str, record: CompactElementRecord) -> str:
    fields = []
    for key, value in (
        ("role", record.role),
        ("name", record.accessible_name),
        ("text", record.text),
        ("context", record.context),
        ("href", record.href),
    ):
        if value:
            fields.append(f"{key}={_quote(value)}")
    return prefix + " " + " ".join(fields)


def compact_frame_record_lines(
    frame: CompactDOMDiffSummaryFrame,
) -> list[tuple[int, bool, str]]:
    """Return stable ``(priority, hard_retained, line)`` records."""
    rows: list[tuple[int, bool, str]] = []
    page = frame.page
    if page.get("url_after") is not None or page.get("title_after") is not None:
        fields = []
        if page.get("title_after") is not None:
            fields.append(f"title={_quote(str(page['title_after']))}")
        if page.get("url_after") is not None:
            fields.append(f"url={_quote(str(page['url_after']))}")
        rows.append((100, True, "PAGE " + " ".join(fields)))
    if page.get("scroll_y_before") is not None or page.get("scroll_y_after") is not None:
        rows.append(
            (
                35,
                False,
                "SCROLL "
                f"y={page.get('scroll_y_before')}->{page.get('scroll_y_after')} "
                f"document_height={page.get('document_height_before')}->{page.get('document_height_after')}",
            )
        )
    for direction, values in (("+TEXT", frame.text_added), ("-TEXT", frame.text_removed)):
        for value in values:
            hard = bool(_NUMBER_RE.search(value) or _IMPORTANT_RE.search(value))
            rows.append((90 if hard else 70, hard, f"{direction} {_quote(value)}"))
    for prefix, values in (
        ("+ELEMENT", frame.interactive_added),
        ("-ELEMENT", frame.interactive_removed),
    ):
        for value in values:
            rendered = _element_line(prefix, value)
            hard = bool(_NUMBER_RE.search(rendered) or _IMPORTANT_RE.search(rendered))
            rows.append((85 if hard else 55, hard, rendered))
    for change in frame.interactive_changed:
        fields = ", ".join(
            f"{field_name}:{_quote(before)}->{_quote(after)}"
            for field_name, before, after in change.changes
        )
        rendered = _element_line("~ELEMENT", change.element) + f" changes={fields}"
        rows.append((95, True, rendered))
    return rows


def _receipt_line(frame: CompactDOMDiffSummaryFrame, budget_omitted: int) -> str:
    receipt = frame.receipt
    return (
        "OMITTED "
        f"geometry_only={receipt.geometry_only_changes_removed} "
        f"exact_duplicate={receipt.exact_duplicates_removed} "
        f"contained_fragment={receipt.contained_fragments_removed} "
        f"element_duplicate={receipt.element_duplicates_removed} "
        f"char_limited={receipt.records_truncated_by_char_limit} "
        f"budget={budget_omitted} "
        f"source_truncated={str(receipt.source_truncation_detected).lower()}"
    )


def render_compact_frame(
    frame: CompactDOMDiffSummaryFrame,
    *,
    token_budget: int = 1500,
    model: str = "gpt-5.2",
) -> RenderedSummary:
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    estimator = TokenEstimator(model)
    header = [
        f"STEP {frame.action_ordinal} action_id={frame.action_id}",
        f"SCHEMA {frame.schema_version} source_sha256={frame.source_sha256}",
    ]
    records = compact_frame_record_lines(frame)
    selected: set[int] = set()
    # Reserve a receipt even when evidence must be omitted.
    for index in sorted(range(len(records)), key=lambda idx: (-records[idx][0], idx)):
        candidate_selected = selected | {index}
        ordered_lines = [records[idx][2] for idx in range(len(records)) if idx in candidate_selected]
        omitted = len(records) - len(candidate_selected)
        candidate = "\n".join(header + ordered_lines + [_receipt_line(frame, omitted)])
        if estimator.count(candidate) <= token_budget:
            selected = candidate_selected

    ordered_lines = [records[idx][2] for idx in range(len(records)) if idx in selected]
    omitted = len(records) - len(selected)
    text = "\n".join(header + ordered_lines + [_receipt_line(frame, omitted)])
    # Extremely small caller budgets still receive a complete, explicit receipt.
    if estimator.count(text) > token_budget:
        text = "\n".join([header[0], _receipt_line(frame, len(records))])
    return RenderedSummary(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        records_total=len(records),
        records_rendered=len(selected),
        records_omitted_by_budget=omitted,
    )


def build_trajectory_ledger(
    frames: Sequence[CompactDOMDiffSummaryFrame],
) -> CompactTrajectoryLedger:
    ordered = tuple(sorted(frames, key=lambda frame: (frame.action_ordinal, frame.action_id)))
    page_lines: list[str] = []
    grouped: dict[str, dict[str, Any]] = {}
    for frame in ordered:
        for priority, hard, line in compact_frame_record_lines(frame):
            if line.startswith("PAGE ") or line.startswith("SCROLL "):
                page_lines.append(f"step={frame.action_ordinal} {line}")
                continue
            entry = grouped.setdefault(
                line,
                {"steps": [], "priority": priority, "hard": hard},
            )
            entry["steps"].append(frame.action_ordinal)
            entry["priority"] = max(entry["priority"], priority)
            entry["hard"] = bool(entry["hard"] or hard)
    records = tuple(
        LedgerRecord(
            line=line,
            steps=tuple(entry["steps"]),
            priority=int(entry["priority"]),
            hard_retained=bool(entry["hard"]),
        )
        for line, entry in sorted(
            grouped.items(),
            key=lambda item: (min(item[1]["steps"]), item[0]),
        )
    )
    return CompactTrajectoryLedger(
        frames=ordered,
        page_lines=tuple(page_lines),
        records=records,
    )


def render_trajectory_ledger(
    ledger: CompactTrajectoryLedger,
    *,
    token_budget: int = 16000,
    model: str = "gpt-5.2",
) -> RenderedSummary:
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    estimator = TokenEstimator(model)
    header = [
        "COMPACT DOM-DIFF-SUMMARY TRAJECTORY",
        f"schema={COMPACT_SUMMARY_SCHEMA} frames={len(ledger.frames)}",
    ]
    candidates: list[tuple[int, bool, str]] = [
        (100, True, line) for line in ledger.page_lines
    ]
    candidates.extend(
        (
            record.priority,
            record.hard_retained,
            f"steps={list(record.steps)} {record.line}",
        )
        for record in ledger.records
    )
    selected: set[int] = set()
    for index in sorted(range(len(candidates)), key=lambda idx: (-candidates[idx][0], idx)):
        proposed = selected | {index}
        lines = [candidates[idx][2] for idx in range(len(candidates)) if idx in proposed]
        omitted = len(candidates) - len(proposed)
        receipt = f"OMITTED ledger_budget={omitted}"
        candidate = "\n".join(header + lines + [receipt])
        if estimator.count(candidate) <= token_budget:
            selected = proposed
    lines = [candidates[idx][2] for idx in range(len(candidates)) if idx in selected]
    omitted = len(candidates) - len(selected)
    text = "\n".join(header + lines + [f"OMITTED ledger_budget={omitted}"])
    return RenderedSummary(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        records_total=len(candidates),
        records_rendered=len(selected),
        records_omitted_by_budget=omitted,
    )


def aggregate_compaction_metrics(
    frames: Iterable[CompactDOMDiffSummaryFrame],
) -> dict[str, Any]:
    values = list(frames)
    source_bytes = sum(frame.source_bytes for frame in values)
    compact_bytes = sum(frame.compact_bytes for frame in values)
    return {
        "compact_schema_version": COMPACT_SUMMARY_SCHEMA,
        "source_frame_count": len(values),
        "source_bytes": source_bytes,
        "compact_bytes": compact_bytes,
        "compaction_ratio": (
            round(compact_bytes / source_bytes, 6) if source_bytes else None
        ),
        "geometry_only_changes_removed": sum(
            frame.receipt.geometry_only_changes_removed for frame in values
        ),
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
        "source_truncation_detected": any(
            frame.receipt.source_truncation_detected for frame in values
        ),
        "source_hashes": [frame.source_sha256 for frame in values],
    }

