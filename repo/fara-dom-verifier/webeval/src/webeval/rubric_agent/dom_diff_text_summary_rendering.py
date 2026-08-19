"""Native summary-S3 rendering for dense refined-DOM-text frames.

There is deliberately no lexical retrieval, chunk selection, adaptive budget
expansion, or late cap in this module.  It mirrors the summary renderer:
whole semantic records are priority-packed per frame, and the complete stage
payload is constrained by a caller-supplied evidence budget.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Sequence

from webeval.rubric_agent.dom_diff_summary_compaction import (
    CompactElementRecord,
    RenderedSummary,
    TokenEstimator,
)
from webeval.rubric_agent.dom_diff_text_summary_projection import (
    CompactDOMDiffTextSummaryFrame,
)


_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d[\d,.'’]*)(?:\s?(?:%|[A-Za-z°²³]+))?")
_IMPORTANT_RE = re.compile(
    r"\b(error|failed|warning|invalid|success|confirmed|complete|completed|"
    r"submitted|saved|deleted|blocked)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PackedTextSummaryEvidence:
    text: str
    estimated_tokens: int
    tokenizer: str
    frame_indices: tuple[int, ...]
    records_omitted_by_budget: int
    starting_per_frame_allowance_tokens: int
    per_frame_allowance_tokens: int


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
    return (prefix + " " + " ".join(fields)).rstrip()


def _document_state_owners(
    frames: Sequence[CompactDOMDiffTextSummaryFrame],
    active_frame_indices: Sequence[int],
) -> dict[str, int]:
    """Choose one active owner for each shared state definition."""
    active = set(active_frame_indices)
    owners: dict[str, int] = {}
    for frame_index in active_frame_indices:
        for state in frames[frame_index].document_page_states:
            candidates = [
                occurrence.frame_index
                for occurrence in state.occurrences
                if occurrence.frame_index in active
            ]
            if candidates:
                owners[state.state_sha256] = min(candidates)
    return owners


def _document_state_rows(
    frame: CompactDOMDiffTextSummaryFrame,
    *,
    frame_index: int,
    active_frame_indices: Sequence[int],
    state_owners: dict[str, int],
) -> list[tuple[int, bool, str]]:
    active = set(active_frame_indices)
    rows: list[tuple[int, bool, str]] = []
    for state in frame.document_page_states:
        if state_owners.get(state.state_sha256) != frame_index:
            continue
        occurrences = tuple(
            occurrence
            for occurrence in state.occurrences
            if occurrence.frame_index in active
        )
        if not occurrences:
            continue
        transitions = "; ".join(
            f"{'+' if occurrence.direction == 'added' else '-'}"
            f"FRAME {occurrence.frame_index}/STEP {occurrence.action_ordinal} "
            f"url={_quote(occurrence.url)}"
            for occurrence in occurrences
        )
        rows.append(
            (
                100,
                True,
                f"PAGE_STATE {state.state_label} occurrences=[{transitions}]",
            )
        )
        for block in state.blocks:
            rendered = (
                f"{state.state_label} TEXT "
                + json.dumps(
                    block.values,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            hard = bool(_NUMBER_RE.search(rendered) or _IMPORTANT_RE.search(rendered))
            rows.append((90 if hard else 70, hard, rendered))
    return rows


def compact_text_summary_record_lines(
    frame: CompactDOMDiffTextSummaryFrame,
    *,
    frame_index: int | None = None,
    active_frame_indices: Sequence[int] | None = None,
    state_owners: dict[str, int] | None = None,
) -> list[tuple[int, bool, str]]:
    """Return summary-S3 ``(priority, hard, complete line)`` records."""
    resolved_index = (
        frame.action_ordinal - 1 if frame_index is None else frame_index
    )
    active = (
        tuple(
            dict.fromkeys(
                occurrence.frame_index
                for state in frame.document_page_states
                for occurrence in state.occurrences
            )
        )
        if active_frame_indices is None
        else tuple(active_frame_indices)
    )
    owners = state_owners or {
        state.state_sha256: min(
            occurrence.frame_index
            for occurrence in state.occurrences
            if occurrence.frame_index in set(active)
        )
        for state in frame.document_page_states
        if any(occurrence.frame_index in set(active) for occurrence in state.occurrences)
    }
    rows: list[tuple[int, bool, str]] = []
    if (
        frame.page.get("url_before") is not None
        or frame.page.get("url_after") is not None
    ):
        rows.append(
            (
                100,
                True,
                "PAGE "
                f"url={_quote(str(frame.page.get('url_before') or frame.before_url))}"
                " -> "
                f"{_quote(str(frame.page.get('url_after') or frame.after_url))} "
                f"document_replaced={str(bool(frame.page.get('document_replaced'))).lower()}",
            )
        )
    for prefix, values in (
        ("+DOC", frame.document_text_added),
        ("-DOC", frame.document_text_removed),
        ("+VIEW", frame.viewport_text_entered),
        ("-VIEW", frame.viewport_text_exited),
    ):
        for value in values:
            hard = bool(_NUMBER_RE.search(value) or _IMPORTANT_RE.search(value))
            rows.append((90 if hard else 70, hard, f"{prefix} {_quote(value)}"))
    rows.extend(
        _document_state_rows(
            frame,
            frame_index=resolved_index,
            active_frame_indices=active,
            state_owners=owners,
        )
    )
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
        rows.append(
            (95, True, _element_line("~ELEMENT", change.element) + f" changes={fields}")
        )
    return rows


def _receipt_line(frame: CompactDOMDiffTextSummaryFrame, budget_omitted: int) -> str:
    receipt = frame.receipt
    warnings = ",".join(receipt.coverage_warnings) or "none"
    return (
        "OMITTED "
        f"geometry_only={receipt.geometry_only_changes_removed} "
        f"exact_duplicate={receipt.exact_duplicates_removed} "
        f"contained_fragment={receipt.contained_fragments_removed} "
        f"element_duplicate={receipt.element_duplicates_removed} "
        f"char_limited={receipt.records_truncated_by_char_limit} "
        f"budget={budget_omitted} "
        f"source_truncated={str(receipt.source_truncation_detected).lower()} "
        f"coverage={warnings} "
        f"state_values={receipt.document_text_values_grouped} "
        f"state_blocks={receipt.document_text_blocks_created} "
        f"state_repeated={receipt.repeated_document_text_occurrences_factored}"
    )


def render_compact_text_summary_frame(
    frame: CompactDOMDiffTextSummaryFrame,
    *,
    frame_index: int,
    token_budget: int = 1500,
    model: str = "gpt-5.2",
    active_frame_indices: Sequence[int] | None = None,
    state_owners: dict[str, int] | None = None,
) -> RenderedSummary:
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    estimator = TokenEstimator(model)
    header = [
        f"FRAME {frame_index} | STEP {frame.action_ordinal} "
        f"action={frame.action_type} status={frame.status}"
    ]
    records = compact_text_summary_record_lines(
        frame,
        frame_index=frame_index,
        active_frame_indices=active_frame_indices,
        state_owners=state_owners,
    )
    selected: set[int] = set()
    for index in sorted(range(len(records)), key=lambda idx: (-records[idx][0], idx)):
        proposed = selected | {index}
        lines = [records[idx][2] for idx in range(len(records)) if idx in proposed]
        candidate = "\n".join(
            [*header, *lines, _receipt_line(frame, len(records) - len(proposed))]
        )
        if estimator.count(candidate) <= token_budget:
            selected = proposed
    lines = [records[idx][2] for idx in range(len(records)) if idx in selected]
    omitted = len(records) - len(selected)
    text = "\n".join([*header, *lines, _receipt_line(frame, omitted)])
    if estimator.count(text) > token_budget:
        text = "\n".join([header[0], _receipt_line(frame, len(records))])
        omitted = len(records)
    return RenderedSummary(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        records_total=len(records),
        records_rendered=len(records) - omitted,
        records_omitted_by_budget=omitted,
    )


def _starting_allowance(
    token_budget: int,
    frame_count: int,
    *,
    floor: int,
) -> int:
    return max(floor, token_budget // max(1, frame_count))


def render_batched_text_summary_relevance_evidence(
    frames: Sequence[CompactDOMDiffTextSummaryFrame],
    *,
    token_budget: int,
    model: str = "gpt-5.2",
) -> PackedTextSummaryEvidence:
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    estimator = TokenEstimator(model)
    starting_allowance = _starting_allowance(token_budget, len(frames), floor=120)
    allowance = starting_allowance
    header = "ALL ACTION-ALIGNED COMPACT REFINED DOM-DIFF TEXT FRAMES"
    active_indices = tuple(range(len(frames)))
    state_owners = _document_state_owners(frames, active_indices)

    def build(current: int) -> tuple[str, list[RenderedSummary]]:
        rendered = [
            render_compact_text_summary_frame(
                frame,
                frame_index=index,
                token_budget=current,
                model=model,
                active_frame_indices=active_indices,
                state_owners=state_owners,
            )
            for index, frame in enumerate(frames)
        ]
        return (
            header + "\n\n" + "\n\n---\n\n".join(item.text for item in rendered),
            rendered,
        )

    text, rendered = build(allowance)
    while estimator.count(text) > token_budget and allowance > 80:
        allowance = max(80, int(allowance * 0.8))
        text, rendered = build(allowance)
    if estimator.count(text) > token_budget:
        raise ValueError("Text-summary relevance evidence cannot fit configured budget")
    return PackedTextSummaryEvidence(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        frame_indices=tuple(range(len(frames))),
        records_omitted_by_budget=sum(
            item.records_omitted_by_budget for item in rendered
        ),
        starting_per_frame_allowance_tokens=starting_allowance,
        per_frame_allowance_tokens=allowance,
    )


def render_packed_text_summary_analysis_evidence(
    frames: Sequence[CompactDOMDiffTextSummaryFrame],
    grouped_frames: Dict[int, list[int]],
    *,
    token_budget: int,
    model: str = "gpt-5.2",
) -> PackedTextSummaryEvidence:
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    estimator = TokenEstimator(model)
    selected_indices = tuple(
        sorted(
            {frame_idx for indices in grouped_frames.values() for frame_idx in indices}
        )
    )
    starting_allowance = _starting_allowance(
        token_budget, len(selected_indices), floor=160
    )
    allowance = starting_allowance
    state_owners = _document_state_owners(frames, selected_indices)

    def build(current: int) -> tuple[str, list[RenderedSummary]]:
        rendered = [
            render_compact_text_summary_frame(
                frames[index],
                frame_index=index,
                token_budget=current,
                model=model,
                active_frame_indices=selected_indices,
                state_owners=state_owners,
            )
            for index in selected_indices
        ]
        library = "\n\n---\n\n".join(item.text for item in rendered)
        assignments = "\n".join(
            f"criterion_{criterion_idx}: frame_indices={indices}; "
            f"steps={[frames[index].action_ordinal for index in indices]}"
            for criterion_idx, indices in sorted(grouped_frames.items())
        )
        return (
            "SELECTED COMPACT REFINED DOM-DIFF TEXT EVIDENCE LIBRARY\n"
            + library
            + "\n\nCRITERION EVIDENCE ASSIGNMENTS\n"
            + assignments,
            rendered,
        )

    text, rendered = build(allowance)
    while estimator.count(text) > token_budget and allowance > 100:
        allowance = max(100, int(allowance * 0.8))
        text, rendered = build(allowance)
    if estimator.count(text) > token_budget:
        raise ValueError("Text-summary analysis evidence cannot fit configured budget")
    return PackedTextSummaryEvidence(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        frame_indices=selected_indices,
        records_omitted_by_budget=sum(
            item.records_omitted_by_budget for item in rendered
        ),
        starting_per_frame_allowance_tokens=starting_allowance,
        per_frame_allowance_tokens=allowance,
    )
