"""Deterministic retrieval and packing for compact DOM-diff summaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Sequence

from webeval.rubric_agent.dom_diff_summary_compaction import (
    CompactDOMDiffSummaryFrame,
    RenderedSummary,
    TokenEstimator,
    matching_key,
    render_compact_frame,
)


_TOKEN_RE = re.compile(r"[\w°%$€£¥]+(?:[-./'][\w°%$€£¥]+)*", re.UNICODE)
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d[\d,.'’]*)(?:\s?(?:%|[A-Za-z°²³]+))?")
_QUOTED_RE = re.compile(r'["“”]([^"“”]{2,120})["“”]')
_IMPORTANT_RE = re.compile(
    r"\b(error|failed|warning|invalid|success|confirmed|complete|completed|"
    r"submitted|saved|deleted|blocked)\b",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


@dataclass(frozen=True)
class SelectionReceipt:
    criterion_idx: int
    selected_steps: tuple[int, ...]
    selected_frame_indices: tuple[int, ...]
    scores: tuple[int, ...]
    hard_retention_reasons: tuple[str, ...]
    dropped_candidate_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_idx": self.criterion_idx,
            "selected_steps": list(self.selected_steps),
            "selected_frame_indices": list(self.selected_frame_indices),
            "scores": list(self.scores),
            "hard_retention_reasons": list(self.hard_retention_reasons),
            "dropped_candidate_count": self.dropped_candidate_count,
        }


@dataclass(frozen=True)
class PackedEvidence:
    text: str
    estimated_tokens: int
    tokenizer: str
    frame_indices: tuple[int, ...]
    records_omitted_by_budget: int


def _tokens(value: str) -> list[str]:
    output: list[str] = []
    for match in _TOKEN_RE.finditer(matching_key(value)):
        token = match.group(0)
        if len(token) >= 3 and token not in _STOP_WORDS:
            output.append(token)
    return output


def _terms_from_text(value: str) -> list[str]:
    normalized = matching_key(value)
    terms = _tokens(normalized)
    terms.extend(match.group(1).strip().casefold() for match in _QUOTED_RE.finditer(value))
    terms.extend(match.group(0).strip().casefold() for match in _NUMBER_RE.finditer(value))
    token_list = _tokens(normalized)
    terms.extend(
        f"{token_list[index]} {token_list[index + 1]}"
        for index in range(len(token_list) - 1)
    )
    return terms


def build_summary_retrieval_terms(
    *,
    task: str,
    rubric_items: Iterable[dict[str, Any]],
    predicted_output: str = "",
    limit: int = 240,
) -> list[str]:
    """Build stable task/rubric/answer terms without an inference call."""
    values = [task, predicted_output]
    for item in rubric_items:
        values.extend(
            str(item.get(key) or "")
            for key in ("criterion", "description", "condition")
        )
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        for term in _terms_from_text(value):
            if term and term not in seen:
                seen.add(term)
                output.append(term)
                if len(output) >= limit:
                    return output
    return output


def _frame_search_text(frame: CompactDOMDiffSummaryFrame) -> str:
    parts = [
        str(frame.page.get("url_after") or ""),
        str(frame.page.get("title_after") or ""),
        *frame.text_added,
        *frame.text_removed,
    ]
    for record in (*frame.interactive_added, *frame.interactive_removed):
        parts.extend(
            [record.role, record.accessible_name, record.text, record.context, record.href]
        )
    for change in frame.interactive_changed:
        parts.extend(
            [
                change.element.role,
                change.element.accessible_name,
                change.element.text,
                change.element.context,
                change.element.href,
            ]
        )
        for field_name, before, after in change.changes:
            parts.extend([field_name, before, after])
    return "\n".join(part for part in parts if part)


def _criterion_terms(item: dict[str, Any], predicted_output: str) -> tuple[set[str], set[str]]:
    criterion_text = "\n".join(
        [
            str(item.get("criterion") or ""),
            str(item.get("description") or ""),
            str(item.get("condition") or ""),
        ]
    )
    criterion_tokens = set(_tokens(criterion_text))
    relevant_answer_parts: list[str] = []
    value_cues = {
        "amount",
        "count",
        "date",
        "height",
        "length",
        "number",
        "price",
        "quantity",
        "size",
        "time",
        "unit",
        "units",
        "weight",
        "width",
        "year",
    }
    for part in re.split(r"[\n;]+", predicted_output):
        part = part.strip()
        part_tokens = set(_tokens(part))
        labeled_match = bool(criterion_tokens.intersection(part_tokens))
        unlabeled_value_match = bool(
            _NUMBER_RE.search(part)
            and len(part_tokens) <= 3
            and criterion_tokens.intersection(value_cues)
        )
        if part and (labeled_match or unlabeled_value_match):
            relevant_answer_parts.append(part)
    value = "\n".join([criterion_text, *relevant_answer_parts])
    return set(_terms_from_text(value)), {
        match.group(0).casefold() for match in _NUMBER_RE.finditer(value)
    }


def _hard_reasons(
    frame: CompactDOMDiffSummaryFrame,
    *,
    frame_idx: int,
    frame_count: int,
    query_numbers: set[str],
    search_text: str,
) -> list[str]:
    reasons: list[str] = []
    if frame_idx == 0:
        reasons.append("first_frame")
    if frame_idx == frame_count - 1:
        reasons.append("final_frame")
    if frame.page.get("url_after") is not None or frame.page.get("title_after") is not None:
        reasons.append("page_transition")
    if frame.interactive_changed:
        reasons.append("semantic_state_change")
    if frame.receipt.source_truncation_detected:
        reasons.append("source_truncation_receipt")
    folded = search_text.casefold()
    if _IMPORTANT_RE.search(search_text):
        reasons.append("error_or_confirmation")
    if any(number in folded for number in query_numbers):
        reasons.append("exact_number_or_unit")
    return reasons


def local_relevance_scores(
    frames: Sequence[CompactDOMDiffSummaryFrame],
    rubric: dict[str, Any],
    *,
    task: str,
    predicted_output: str = "",
) -> Dict[int, Dict[Any, int]]:
    """Return the relevance matrix expected by the inherited grouping stage."""
    result: Dict[int, Dict[Any, int]] = {}
    frame_texts = [_frame_search_text(frame) for frame in frames]
    frame_token_sets = [set(_tokens(text)) for text in frame_texts]
    for frame_idx, (frame, text, frame_tokens) in enumerate(
        zip(frames, frame_texts, frame_token_sets)
    ):
        row: Dict[Any, int] = {}
        for criterion_idx, item in enumerate(rubric.get("items") or []):
            query_terms, query_numbers = _criterion_terms(item, predicted_output)
            lexical_terms = {term for term in query_terms if " " not in term}
            overlap = len(frame_tokens & lexical_terms)
            phrase_hits = sum(1 for term in query_terms if " " in term and term in text.casefold())
            number_hits = sum(1 for number in query_numbers if number in text.casefold())
            reasons = _hard_reasons(
                frame,
                frame_idx=frame_idx,
                frame_count=len(frames),
                query_numbers=query_numbers,
                search_text=text,
            )
            score = min(
                10,
                overlap
                + min(3, phrase_hits * 2)
                + min(4, number_hits * 3)
                + (2 if "page_transition" in reasons else 0)
                + (2 if "semantic_state_change" in reasons else 0)
                + (2 if "error_or_confirmation" in reasons else 0),
            )
            # Keep a small chronological signal without making every frame high relevance.
            if score == 0 and frame_idx == len(frames) - 1:
                score = 1
            row[criterion_idx] = int(score)
        row["screenshot_idx"] = frame_idx
        row["evidence_idx"] = frame_idx
        result[frame_idx] = row
    return result


def build_selection_receipts(
    frames: Sequence[CompactDOMDiffSummaryFrame],
    grouped_frames: Dict[int, list[int]],
    relevance_scores: Dict[int, Dict[Any, int]],
    rubric: dict[str, Any],
    *,
    predicted_output: str = "",
) -> list[SelectionReceipt]:
    receipts: list[SelectionReceipt] = []
    for criterion_idx, selected in sorted(grouped_frames.items()):
        item = (rubric.get("items") or [])[criterion_idx]
        _, query_numbers = _criterion_terms(item, predicted_output)
        reasons: list[str] = []
        for frame_idx in selected:
            reasons.extend(
                f"step_{frames[frame_idx].action_ordinal}:{reason}"
                for reason in _hard_reasons(
                    frames[frame_idx],
                    frame_idx=frame_idx,
                    frame_count=len(frames),
                    query_numbers=query_numbers,
                    search_text=_frame_search_text(frames[frame_idx]),
                )
            )
        receipts.append(
            SelectionReceipt(
                criterion_idx=criterion_idx,
                selected_steps=tuple(frames[index].action_ordinal for index in selected),
                selected_frame_indices=tuple(selected),
                scores=tuple(
                    int(relevance_scores.get(index, {}).get(criterion_idx, 0))
                    for index in selected
                ),
                hard_retention_reasons=tuple(dict.fromkeys(reasons)),
                dropped_candidate_count=max(0, len(frames) - len(selected)),
            )
        )
    return receipts


def render_batched_relevance_evidence(
    frames: Sequence[CompactDOMDiffSummaryFrame],
    *,
    token_budget: int,
    model: str = "gpt-5.2",
) -> PackedEvidence:
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    estimator = TokenEstimator(model)
    frame_budget = max(120, token_budget // max(1, len(frames)))
    rendered = [
        render_compact_frame(frame, token_budget=frame_budget, model=model)
        for frame in frames
    ]
    header = "ALL ACTION-ALIGNED COMPACT SUMMARY FRAMES"
    blocks = [value.text for value in rendered]
    text = header + "\n\n" + "\n\n---\n\n".join(blocks)
    # Reduce all frames evenly until the complete matrix input fits. Every frame
    # remains represented by a header and omission receipt.
    while estimator.count(text) > token_budget and frame_budget > 80:
        frame_budget = max(80, int(frame_budget * 0.8))
        rendered = [
            render_compact_frame(frame, token_budget=frame_budget, model=model)
            for frame in frames
        ]
        blocks = [value.text for value in rendered]
        text = header + "\n\n" + "\n\n---\n\n".join(blocks)
    return PackedEvidence(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        frame_indices=tuple(range(len(frames))),
        records_omitted_by_budget=sum(
            value.records_omitted_by_budget for value in rendered
        ),
    )


def render_packed_analysis_evidence(
    frames: Sequence[CompactDOMDiffSummaryFrame],
    grouped_frames: Dict[int, list[int]],
    *,
    token_budget: int,
    model: str = "gpt-5.2",
) -> PackedEvidence:
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    estimator = TokenEstimator(model)
    selected_indices = tuple(
        sorted({frame_idx for values in grouped_frames.values() for frame_idx in values})
    )
    frame_budget = max(160, token_budget // max(1, len(selected_indices)))

    def build(current_frame_budget: int) -> tuple[str, list[RenderedSummary]]:
        rendered = [
            render_compact_frame(
                frames[index], token_budget=current_frame_budget, model=model
            )
            for index in selected_indices
        ]
        library = "\n\n---\n\n".join(value.text for value in rendered)
        assignments = "\n".join(
            f"criterion_{criterion_idx}: frame_indices={indices}; "
            f"steps={[frames[index].action_ordinal for index in indices]}"
            for criterion_idx, indices in sorted(grouped_frames.items())
        )
        return (
            "SELECTED COMPACT EVIDENCE LIBRARY\n"
            + library
            + "\n\nCRITERION EVIDENCE ASSIGNMENTS\n"
            + assignments,
            rendered,
        )

    text, rendered = build(frame_budget)
    while estimator.count(text) > token_budget and frame_budget > 100:
        frame_budget = max(100, int(frame_budget * 0.8))
        text, rendered = build(frame_budget)
    return PackedEvidence(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        frame_indices=selected_indices,
        records_omitted_by_budget=sum(
            value.records_omitted_by_budget for value in rendered
        ),
    )
