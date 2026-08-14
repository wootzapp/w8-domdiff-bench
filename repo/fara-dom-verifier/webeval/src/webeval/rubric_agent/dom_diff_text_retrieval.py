"""Deterministic criterion retrieval and adaptive packing for text DOM diffs."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_compaction import (
    CompactChunk,
    CompactDOMDiffTextFrame,
    build_trajectory_ledger,
    coverage_line,
    page_line,
    step_header,
)


_TOKEN_RE = re.compile(r"[\w°%$€£¥]+(?:[-./'][\w°%$€£¥]+)*", re.UNICODE)
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d[\d,.'’]*)(?:[ \t]?(?:%|[A-Za-z°²³]+))?")
_QUOTED_RE = re.compile(r'["“”]([^"“”]{2,160})["“”]')
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

# Measured against the refined-text fixtures and task5: one shared lexical
# token is too permissive, while two retains focused records without weakening
# exact phrase/number/state/error matches. The fallback is deliberately smaller
# than the inherited eight-record floor and deterministic.
LEXICAL_ONLY_MIN_SCORE = 2
DETERMINISTIC_FALLBACK_RECORDS = 3
_CRITERION_TAG_RE = re.compile(r"^C\[(?P<indices>\d+(?:,\d+)*)\]$")


def _matching(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _tokens(value: str) -> list[str]:
    output: list[str] = []
    for match in _TOKEN_RE.finditer(_matching(value)):
        token = match.group(0)
        if len(token) >= 3 and token not in _STOP_WORDS:
            output.append(token)
    return output


def _terms_from_text(value: str) -> list[str]:
    normalized = _matching(value)
    tokens = _tokens(normalized)
    terms = list(tokens)
    terms.extend(
        match.group(1).strip().casefold() for match in _QUOTED_RE.finditer(value)
    )
    terms.extend(
        match.group(0).strip().casefold() for match in _NUMBER_RE.finditer(value)
    )
    terms.extend(
        f"{tokens[index]} {tokens[index + 1]}" for index in range(len(tokens) - 1)
    )
    return terms


@dataclass(frozen=True)
class CriterionQuery:
    criterion_idx: int
    terms: tuple[str, ...]
    lexical_terms: frozenset[str]
    phrases: tuple[str, ...]
    exact_numbers: frozenset[str]


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
class OmissionReceipt:
    stage: str
    reason: str
    item_id: str
    action_ordinal: int
    criterion_indices: tuple[int, ...]
    relevance_rank: int
    estimated_tokens: int
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "reason": self.reason,
            "item_id": self.item_id,
            "action_ordinal": self.action_ordinal,
            "criterion_indices": list(self.criterion_indices),
            "relevance_rank": self.relevance_rank,
            "estimated_tokens": self.estimated_tokens,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class AdaptiveBudgetReceipt:
    stage: str
    starting_target_tokens: int
    model_context_window_tokens: int
    completion_reserve_tokens: int
    prompt_headroom_tokens: int
    fixed_prompt_tokens: int
    safe_prompt_limit_tokens: int
    max_evidence_tokens: int
    effective_evidence_tokens: int
    expansion_tokens: int
    expansion_reason: str | None
    included_estimated_tokens: int
    omitted_estimated_tokens: int
    overflow: bool
    tokenizer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "starting_target_tokens": self.starting_target_tokens,
            "model_context_window_tokens": self.model_context_window_tokens,
            "completion_reserve_tokens": self.completion_reserve_tokens,
            "prompt_headroom_tokens": self.prompt_headroom_tokens,
            "fixed_prompt_tokens": self.fixed_prompt_tokens,
            "safe_prompt_limit_tokens": self.safe_prompt_limit_tokens,
            "max_evidence_tokens": self.max_evidence_tokens,
            "effective_evidence_tokens": self.effective_evidence_tokens,
            "expansion_tokens": self.expansion_tokens,
            "expansion_reason": self.expansion_reason,
            "included_estimated_tokens": self.included_estimated_tokens,
            "omitted_estimated_tokens": self.omitted_estimated_tokens,
            "overflow": self.overflow,
            "tokenizer": self.tokenizer,
        }


@dataclass(frozen=True)
class PackedTextEvidence:
    text: str
    estimated_tokens: int
    tokenizer: str
    frame_indices: tuple[int, ...]
    records_omitted_by_budget: int
    budget_receipt: AdaptiveBudgetReceipt
    omission_receipts: tuple[OmissionReceipt, ...]
    retrieval_omissions: tuple[OmissionReceipt, ...] = ()
    criterion_chunk_assignments: Mapping[int, tuple[str, ...]] | None = None
    criterion_frame_assignments: Mapping[int, tuple[int, ...]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "estimated_tokens": self.estimated_tokens,
            "tokenizer": self.tokenizer,
            "frame_indices": list(self.frame_indices),
            "records_omitted_by_budget": self.records_omitted_by_budget,
            "budget_receipt": self.budget_receipt.to_dict(),
            "omission_receipts": [item.to_dict() for item in self.omission_receipts],
            "retrieval_omissions": [
                item.to_dict() for item in self.retrieval_omissions
            ],
            "criterion_chunk_assignments": {
                str(key): list(value)
                for key, value in sorted(
                    (self.criterion_chunk_assignments or {}).items()
                )
            },
            "criterion_frame_assignments": {
                str(key): list(value)
                for key, value in sorted(
                    (self.criterion_frame_assignments or {}).items()
                )
            },
        }


@dataclass(frozen=True)
class _Candidate:
    item_id: str
    text: str
    chunk: CompactChunk
    score: int
    reasons: tuple[str, ...]
    criterion_indices: tuple[int, ...]
    stable_order: tuple[Any, ...]


def _criterion_frame_assignments(
    selected: Sequence[_Candidate],
    criterion_indices: Iterable[int],
    candidate_frame_indices: Mapping[str, set[int]],
) -> dict[int, tuple[int, ...]]:
    """Project one final selected chunk set into criterion citation allowlists."""
    return {
        criterion_idx: tuple(
            sorted(
                {
                    frame_idx
                    for item in selected
                    if criterion_idx in item.criterion_indices
                    for frame_idx in candidate_frame_indices.get(item.item_id, ())
                }
            )
        )
        for criterion_idx in criterion_indices
    }


def _allowed_frames_lines(
    assignments: Mapping[int, Sequence[int]],
) -> tuple[str, ...]:
    """Render only criterion IDs and their zero-based FRAME citation IDs."""
    return (
        "ALLOWED FRAMES",
        *(
            f"C{criterion_idx}=[{','.join(str(index) for index in indices)}]"
            for criterion_idx, indices in sorted(assignments.items())
        ),
    )


def build_text_retrieval_terms(
    *,
    task: str,
    rubric_items: Iterable[dict[str, Any]],
    predicted_output: str = "",
    limit: int | None = None,
) -> list[str]:
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
                if limit is not None and len(output) >= limit:
                    return output
    return output


def build_criterion_query(
    criterion_idx: int,
    item: Mapping[str, Any],
    predicted_output: str,
    *,
    task: str = "",
) -> CriterionQuery:
    criterion_text = "\n".join(
        str(item.get(key) or "") for key in ("criterion", "description", "condition")
    )
    query_context = "\n".join(value for value in (task, criterion_text) if value)
    criterion_tokens = set(_tokens(query_context))
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
    answer_parts: list[str] = []
    for part in re.split(r"[\n;]+", predicted_output):
        part = part.strip()
        part_tokens = set(_tokens(part))
        if not part:
            continue
        if criterion_tokens.intersection(part_tokens) or (
            _NUMBER_RE.search(part)
            and len(part_tokens) <= 2
            and criterion_tokens.intersection(value_cues)
        ):
            answer_parts.append(part)
    source = "\n".join([query_context, *answer_parts])
    terms = tuple(dict.fromkeys(_terms_from_text(source)))
    return CriterionQuery(
        criterion_idx=criterion_idx,
        terms=terms,
        lexical_terms=frozenset(term for term in terms if " " not in term),
        phrases=tuple(term for term in terms if " " in term),
        exact_numbers=frozenset(
            match.group(0).strip().casefold() for match in _NUMBER_RE.finditer(source)
        ),
    )


def _frame_search_text(frame: CompactDOMDiffTextFrame) -> str:
    return "\n".join(
        [
            frame.before_url,
            frame.after_url,
            frame.status,
            *(chunk.search_text for chunk in frame.chunks),
        ]
    )


def _frame_step_header(frame_idx: int, frame: CompactDOMDiffTextFrame) -> str:
    """Render the validator citation ID separately from chronology."""
    return f"FRAME {frame_idx} | {step_header(frame)}"


def _score_text(search_text: str, query: CriterionQuery) -> tuple[int, tuple[str, ...]]:
    folded = _matching(search_text)
    text_tokens = set(_tokens(folded))
    overlap = len(text_tokens.intersection(query.lexical_terms))
    phrase_hits = sum(1 for phrase in query.phrases if phrase in folded)
    number_hits = sum(1 for number in query.exact_numbers if number in folded)
    reasons: list[str] = []
    if number_hits:
        reasons.append("exact_number_date_or_unit")
    if phrase_hits:
        reasons.append("exact_phrase")
    if overlap:
        reasons.append("lexical_overlap")
    if _IMPORTANT_RE.search(search_text):
        reasons.append("error_or_confirmation")
    score = min(
        10,
        overlap
        + min(4, phrase_hits * 2)
        + min(5, number_hits * 3)
        + (2 if "error_or_confirmation" in reasons else 0),
    )
    return int(score), tuple(reasons)


def _passes_relevance_threshold(score: int, reasons: Sequence[str]) -> bool:
    unique = set(reasons)
    if not unique:
        return False
    if unique == {"lexical_overlap"}:
        return score >= LEXICAL_ONLY_MIN_SCORE
    return True


def render_criterion_assignment_tag(indices: Sequence[int]) -> str:
    values = tuple(sorted(set(int(index) for index in indices)))
    if not values or any(index < 0 for index in values):
        raise ValueError("Criterion assignment tags require non-negative indices")
    return "C[" + ",".join(str(index) for index in values) + "]"


def parse_criterion_assignment_tag(value: str) -> tuple[int, ...]:
    match = _CRITERION_TAG_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid criterion assignment tag: {value!r}")
    values = tuple(int(item) for item in match.group("indices").split(","))
    if values != tuple(sorted(set(values))):
        raise ValueError("Criterion assignment indices must be unique and sorted")
    return values


def local_relevance_scores(
    frames: Sequence[CompactDOMDiffTextFrame],
    rubric: dict[str, Any],
    *,
    task: str,
    predicted_output: str = "",
) -> Dict[int, Dict[Any, int]]:
    queries = [
        build_criterion_query(index, item, predicted_output, task=task)
        for index, item in enumerate(rubric.get("items") or [])
    ]
    result: Dict[int, Dict[Any, int]] = {}
    for frame_idx, frame in enumerate(frames):
        search = _frame_search_text(frame)
        row: Dict[Any, int] = {}
        for query in queries:
            score, _ = _score_text(search, query)
            if frame.status == "document_replaced":
                score = min(10, score + 2)
            if any(record.record.operation == "changed" for record in frame.records):
                score = min(10, score + 1)
            if score == 0 and frame_idx == len(frames) - 1:
                score = 1
            row[query.criterion_idx] = score
        row.update(screenshot_idx=frame_idx, evidence_idx=frame_idx)
        result[frame_idx] = row
    return result


def build_selection_receipts(
    frames: Sequence[CompactDOMDiffTextFrame],
    grouped_frames: Dict[int, list[int]],
    relevance_scores: Dict[int, Dict[Any, int]],
    rubric: dict[str, Any],
    *,
    predicted_output: str = "",
    task: str = "",
) -> list[SelectionReceipt]:
    receipts: list[SelectionReceipt] = []
    for criterion_idx, selected in sorted(grouped_frames.items()):
        query = build_criterion_query(
            criterion_idx,
            rubric["items"][criterion_idx],
            predicted_output,
            task=task,
        )
        reasons: list[str] = []
        for frame_idx in selected:
            frame = frames[frame_idx]
            _, frame_reasons = _score_text(_frame_search_text(frame), query)
            if frame.status == "document_replaced":
                frame_reasons = (*frame_reasons, "document_replaced")
            if any(record.record.operation == "changed" for record in frame.records):
                frame_reasons = (*frame_reasons, "semantic_state_change")
            reasons.extend(
                f"step_{frame.action_ordinal}:{reason}" for reason in frame_reasons
            )
        receipts.append(
            SelectionReceipt(
                criterion_idx=criterion_idx,
                selected_steps=tuple(
                    frames[index].action_ordinal for index in selected
                ),
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


def _safe_evidence_budget(
    *,
    model_context_window_tokens: int,
    completion_reserve_tokens: int,
    prompt_headroom_tokens: int,
    fixed_prompt_tokens: int,
) -> tuple[int, int]:
    values = (
        model_context_window_tokens,
        completion_reserve_tokens,
        prompt_headroom_tokens,
        fixed_prompt_tokens,
    )
    if any(value < 0 for value in values) or model_context_window_tokens <= 0:
        raise ValueError("Context and reserve token values must be non-negative")
    safe_prompt = (
        model_context_window_tokens - completion_reserve_tokens - prompt_headroom_tokens
    )
    evidence = safe_prompt - fixed_prompt_tokens
    if safe_prompt <= 0 or evidence <= 0:
        raise ValueError("Fixed prompt/reserves leave no safe evidence capacity")
    return safe_prompt, evidence


def _adaptive_pack(
    *,
    stage: str,
    mandatory_lines: Sequence[str],
    candidates: Sequence[_Candidate],
    render: Callable[[Sequence[_Candidate], bool], str],
    starting_target_tokens: int,
    model_context_window_tokens: int,
    completion_reserve_tokens: int,
    prompt_headroom_tokens: int,
    fixed_prompt_tokens: int,
    allow_budget_expansion: bool,
    model: str,
) -> tuple[
    str, tuple[_Candidate, ...], tuple[OmissionReceipt, ...], AdaptiveBudgetReceipt
]:
    if starting_target_tokens <= 0:
        raise ValueError("starting_target_tokens must be positive")
    estimator = TokenEstimator(model)
    safe_prompt, max_evidence = _safe_evidence_budget(
        model_context_window_tokens=model_context_window_tokens,
        completion_reserve_tokens=completion_reserve_tokens,
        prompt_headroom_tokens=prompt_headroom_tokens,
        fixed_prompt_tokens=fixed_prompt_tokens,
    )
    mandatory_text = render([], False)
    mandatory_tokens = estimator.count(mandatory_text)
    if mandatory_tokens > max_evidence:
        raise ValueError(
            f"{stage} mandatory step/page/coverage envelope exceeds safe model context"
        )

    ordered = sorted(candidates, key=lambda item: (-item.score, item.stable_order))
    full_text = render(ordered, False)
    full_tokens = estimator.count(full_text)
    if not allow_budget_expansion and full_tokens > starting_target_tokens:
        raise ValueError(
            f"{stage} evidence exceeds the starting target while expansion is disabled; "
            "refusing to omit semantic evidence for an artificial cap"
        )
    if full_tokens <= max_evidence:
        selected = list(ordered)
        text = full_text
        omitted: list[_Candidate] = []
    else:
        selected = []
        # Add complete chunks by deterministic relevance.  Token estimates are
        # only a fast precheck; the exact rendered prompt is validated below.
        running = mandatory_tokens
        for candidate in ordered:
            estimate = estimator.count(candidate.text + "\n")
            if running + estimate <= max_evidence:
                selected.append(candidate)
                running += estimate
        selected_ids = {item.item_id for item in selected}
        omitted = [item for item in ordered if item.item_id not in selected_ids]
        text = render(selected, bool(omitted))
        while estimator.count(text) > max_evidence and selected:
            removed = selected.pop()
            omitted.append(removed)
            text = render(selected, True)
        if estimator.count(text) > max_evidence:
            raise ValueError(
                f"{stage} mandatory context-limit warning cannot fit safely"
            )

    selected_ids = {item.item_id for item in selected}
    ranked = {item.item_id: index for index, item in enumerate(ordered, start=1)}
    omission_receipts = tuple(
        OmissionReceipt(
            stage=stage,
            reason="context_limit",
            item_id=item.item_id,
            action_ordinal=item.chunk.action_ordinal,
            criterion_indices=item.criterion_indices,
            relevance_rank=ranked[item.item_id],
            estimated_tokens=estimator.count(item.text),
            source_refs=item.chunk.source_refs,
        )
        for item in ordered
        if item.item_id not in selected_ids
    )
    included_tokens = estimator.count(text)
    omitted_tokens = sum(item.estimated_tokens for item in omission_receipts)
    expansion = max(0, included_tokens - starting_target_tokens)
    receipt = AdaptiveBudgetReceipt(
        stage=stage,
        starting_target_tokens=starting_target_tokens,
        model_context_window_tokens=model_context_window_tokens,
        completion_reserve_tokens=completion_reserve_tokens,
        prompt_headroom_tokens=prompt_headroom_tokens,
        fixed_prompt_tokens=fixed_prompt_tokens,
        safe_prompt_limit_tokens=safe_prompt,
        max_evidence_tokens=max_evidence,
        effective_evidence_tokens=included_tokens,
        expansion_tokens=expansion,
        expansion_reason=(
            "semantic_evidence_exceeded_starting_target" if expansion else None
        ),
        included_estimated_tokens=included_tokens,
        omitted_estimated_tokens=omitted_tokens,
        overflow=bool(omission_receipts),
        tokenizer=estimator.name,
    )
    return text, tuple(selected), omission_receipts, receipt


def _global_queries(
    *, task: str, rubric: dict[str, Any], predicted_output: str
) -> list[CriterionQuery]:
    items = rubric.get("items") or []
    queries = [
        build_criterion_query(index, item, predicted_output, task=task)
        for index, item in enumerate(items)
    ]
    task_terms = tuple(dict.fromkeys(_terms_from_text(task)))
    if task_terms:
        queries.append(
            CriterionQuery(
                criterion_idx=-1,
                terms=task_terms,
                lexical_terms=frozenset(term for term in task_terms if " " not in term),
                phrases=tuple(term for term in task_terms if " " in term),
                exact_numbers=frozenset(
                    match.group(0).casefold() for match in _NUMBER_RE.finditer(task)
                ),
            )
        )
    return queries


def render_batched_relevance_evidence(
    frames: Sequence[CompactDOMDiffTextFrame],
    rubric: dict[str, Any],
    *,
    task: str,
    predicted_output: str,
    starting_target_tokens: int,
    model_context_window_tokens: int,
    completion_reserve_tokens: int,
    prompt_headroom_tokens: int,
    fixed_prompt_tokens: int,
    allow_budget_expansion: bool = True,
    model: str = "gpt-5.2",
) -> PackedTextEvidence:
    ledger = build_trajectory_ledger(frames)
    mandatory = [
        "ALL ACTION-ALIGNED REFINED DOM-DIFF TEXT FRAMES",
        *(
            line
            for frame_idx, frame in enumerate(frames)
            for line in (
                _frame_step_header(frame_idx, frame),
                page_line(frame),
                coverage_line(frame),
            )
        ),
    ]
    queries = _global_queries(
        task=task, rubric=rubric, predicted_output=predicted_output
    )
    first_records: dict[tuple[Any, ...], tuple[CompactChunk, ...]] = {}
    for frame in frames:
        for compact_record in frame.records:
            first_records.setdefault(
                compact_record.record.semantic_key(), compact_record.chunks
            )
    candidates: list[_Candidate] = []
    for ledger_record in ledger.records:
        steps = ",".join(str(step) for step in ledger_record.occurs_at_steps)
        ledger_refs = tuple(
            dict.fromkeys(
                ref
                for occurrence in ledger_record.occurrences
                for ref in occurrence.source_refs
            )
        )
        chunks = first_records[ledger_record.record.semantic_key()]
        for chunk in chunks:
            ledger_chunk = replace(chunk, source_refs=ledger_refs)
            scores = [_score_text(chunk.search_text, query) for query in queries]
            score = max((value[0] for value in scores), default=0)
            reasons = tuple(
                dict.fromkeys(reason for _, found in scores for reason in found)
            )
            if chunk.operation in {"navigation", "changed"}:
                score = max(score, chunk.priority)
                reasons = (*reasons, "semantic_hard_retention")
            # A single frame already has an unambiguous STEP header. For
            # multi-frame ledgers, @1,3 means observed at those discrete steps,
            # never continuously present between them.
            occurrence = f"@{steps} " if len(frames) > 1 else ""
            text = occurrence + chunk.text
            criterion_indices = tuple(
                query.criterion_idx
                for query, value in zip(queries, scores)
                if query.criterion_idx >= 0
                and _passes_relevance_threshold(value[0], value[1])
            )
            candidates.append(
                _Candidate(
                    item_id=chunk.chunk_id,
                    text=text,
                    chunk=ledger_chunk,
                    score=score,
                    reasons=tuple(dict.fromkeys(reasons)),
                    criterion_indices=criterion_indices,
                    stable_order=(
                        chunk.action_ordinal,
                        chunk.first_source_line,
                        chunk.chunk_id,
                    ),
                )
            )

    ranked_all = sorted(candidates, key=lambda item: (-item.score, item.stable_order))
    retained_candidates = [
        item
        for item in ranked_all
        if "semantic_hard_retention" in item.reasons
        or _passes_relevance_threshold(item.score, item.reasons)
    ]
    fallback_ids: set[str] = set()
    if not retained_candidates:
        retained_candidates = ranked_all[:DETERMINISTIC_FALLBACK_RECORDS]
        fallback_ids = {item.item_id for item in retained_candidates}
    retained_ids = {item.item_id for item in retained_candidates}
    estimator = TokenEstimator(model)
    ranks = {item.item_id: rank for rank, item in enumerate(ranked_all, start=1)}
    retrieval_omissions = tuple(
        OmissionReceipt(
            stage="text_relevance_retrieval",
            reason=(
                "below_relevance_threshold"
                if item.score > 0
                else "trajectory_not_retrieved"
            ),
            item_id=item.item_id,
            action_ordinal=item.chunk.action_ordinal,
            criterion_indices=item.criterion_indices,
            relevance_rank=ranks[item.item_id],
            estimated_tokens=estimator.count(item.text),
            source_refs=item.chunk.source_refs,
        )
        for item in ranked_all
        if item.item_id not in retained_ids
    )
    if fallback_ids:
        # Fallback selection is fully represented by the retained IDs and its
        # fixed deterministic rule; it does not masquerade as lexical support.
        retained_candidates = [
            replace(
                item,
                reasons=tuple(dict.fromkeys((*item.reasons, "deterministic_fallback"))),
            )
            for item in retained_candidates
        ]

    def render(selected: Sequence[_Candidate], overflow: bool) -> str:
        lines = [*mandatory, *(item.text for item in selected)]
        if overflow:
            lines.append(
                "COVERAGE context_limit_omitted_relevant_records; consult audit receipt; "
                "use unknown when omitted evidence prevents a safe conclusion"
            )
        return "\n".join(lines)

    text, selected, omissions, budget = _adaptive_pack(
        stage="text_relevance_batched",
        mandatory_lines=mandatory,
        candidates=retained_candidates,
        render=render,
        starting_target_tokens=starting_target_tokens,
        model_context_window_tokens=model_context_window_tokens,
        completion_reserve_tokens=completion_reserve_tokens,
        prompt_headroom_tokens=prompt_headroom_tokens,
        fixed_prompt_tokens=fixed_prompt_tokens,
        allow_budget_expansion=allow_budget_expansion,
        model=model,
    )
    return PackedTextEvidence(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        frame_indices=tuple(range(len(frames))),
        records_omitted_by_budget=len(omissions),
        budget_receipt=budget,
        omission_receipts=omissions,
        retrieval_omissions=retrieval_omissions,
    )


def render_packed_analysis_evidence(
    frames: Sequence[CompactDOMDiffTextFrame],
    grouped_frames: Dict[int, list[int]],
    rubric: dict[str, Any],
    *,
    predicted_output: str,
    task: str = "",
    starting_target_tokens: int,
    model_context_window_tokens: int,
    completion_reserve_tokens: int,
    prompt_headroom_tokens: int,
    fixed_prompt_tokens: int,
    allow_budget_expansion: bool = True,
    model: str = "gpt-5.2",
) -> PackedTextEvidence:
    selected_indices = tuple(
        sorted(
            {frame_idx for indices in grouped_frames.values() for frame_idx in indices}
        )
    )
    mandatory = [
        "SELECTED REFINED DOM-DIFF TEXT EVIDENCE LIBRARY",
        "ASSIGNMENT: C[criterion indexes] on each evidence line is complete.",
        *(
            line
            for index in selected_indices
            for line in (
                _frame_step_header(index, frames[index]),
                page_line(frames[index]),
                coverage_line(frames[index]),
            )
        ),
    ]
    queries = {
        criterion_idx: build_criterion_query(
            criterion_idx,
            rubric["items"][criterion_idx],
            predicted_output,
            task=task,
        )
        for criterion_idx in sorted(grouped_frames)
    }
    candidate_by_id: dict[str, _Candidate] = {}
    candidate_frame_indices: dict[str, set[int]] = {}
    retrieval_omissions: list[OmissionReceipt] = []
    criterion_candidates: dict[int, list[str]] = {index: [] for index in grouped_frames}
    estimator = TokenEstimator(model)
    for criterion_idx, frame_indices in sorted(grouped_frames.items()):
        query = queries[criterion_idx]
        ranked: list[tuple[int, CompactChunk, tuple[str, ...]]] = []
        for frame_idx in frame_indices:
            for chunk in frames[frame_idx].chunks:
                score, reasons = _score_text(chunk.search_text, query)
                if chunk.operation in {"navigation", "changed"}:
                    score = max(score, chunk.priority)
                    reasons = (*reasons, "mandatory_semantic_transition")
                ranked.append((score, chunk, tuple(dict.fromkeys(reasons))))
        ranked.sort(
            key=lambda item: (
                -item[0],
                item[1].action_ordinal,
                item[1].first_source_line,
                item[1].chunk_id,
            )
        )
        qualified = [
            item
            for item in ranked
            if "mandatory_semantic_transition" in item[2]
            or _passes_relevance_threshold(item[0], item[2])
        ]
        # A measured three-record deterministic floor prevents empty criterion
        # context without reviving the old eight-record over-selection.
        retained = qualified if qualified else ranked[:DETERMINISTIC_FALLBACK_RECORDS]
        retained_ids = {chunk.chunk_id for _, chunk, _ in retained}
        for rank, (score, chunk, reasons) in enumerate(ranked, start=1):
            if chunk.chunk_id not in retained_ids:
                retrieval_omissions.append(
                    OmissionReceipt(
                        stage="text_analysis_retrieval",
                        reason=(
                            "below_relevance_threshold"
                            if score > 0
                            else "criterion_not_retrieved"
                        ),
                        item_id=chunk.chunk_id,
                        action_ordinal=chunk.action_ordinal,
                        criterion_indices=(criterion_idx,),
                        relevance_rank=rank,
                        estimated_tokens=estimator.count(chunk.text),
                        source_refs=chunk.source_refs,
                    )
                )
                continue
            criterion_candidates[criterion_idx].append(chunk.chunk_id)
            candidate_frame_indices.setdefault(chunk.chunk_id, set()).add(frame_idx)
            existing = candidate_by_id.get(chunk.chunk_id)
            if existing is None:
                candidate_by_id[chunk.chunk_id] = _Candidate(
                    item_id=chunk.chunk_id,
                    text=chunk.text,
                    chunk=chunk,
                    score=score,
                    reasons=reasons,
                    criterion_indices=(criterion_idx,),
                    stable_order=(
                        chunk.action_ordinal,
                        chunk.first_source_line,
                        chunk.chunk_id,
                    ),
                )
            else:
                candidate_by_id[chunk.chunk_id] = _Candidate(
                    item_id=existing.item_id,
                    text=existing.text,
                    chunk=existing.chunk,
                    score=max(existing.score, score),
                    reasons=tuple(dict.fromkeys((*existing.reasons, *reasons))),
                    criterion_indices=tuple(
                        sorted({*existing.criterion_indices, criterion_idx})
                    ),
                    stable_order=existing.stable_order,
                )

    def render(
        selected: Sequence[_Candidate],
        overflow: bool,
        *,
        frame_assignments: Mapping[int, Sequence[int]] | None = None,
    ) -> str:
        visible_assignments = (
            frame_assignments
            if frame_assignments is not None
            else _criterion_frame_assignments(
                selected,
                criterion_candidates,
                candidate_frame_indices,
            )
        )
        lines = [
            *mandatory,
            *_allowed_frames_lines(visible_assignments),
            *(
                f"{render_criterion_assignment_tag(item.criterion_indices)} {item.text}"
                for item in selected
            ),
        ]
        if overflow:
            lines.append(
                "COVERAGE context_limit_omitted_relevant_records; consult audit receipt; "
                "use unknown when omitted evidence prevents a safe conclusion"
            )
        return "\n".join(lines)

    text, selected, omissions, budget = _adaptive_pack(
        stage="text_analysis_packed",
        mandatory_lines=mandatory,
        candidates=list(candidate_by_id.values()),
        render=render,
        starting_target_tokens=starting_target_tokens,
        model_context_window_tokens=model_context_window_tokens,
        completion_reserve_tokens=completion_reserve_tokens,
        prompt_headroom_tokens=prompt_headroom_tokens,
        fixed_prompt_tokens=fixed_prompt_tokens,
        allow_budget_expansion=allow_budget_expansion,
        model=model,
    )
    selected_ids = {item.item_id for item in selected}
    assignments = {
        criterion_idx: tuple(
            chunk_id for chunk_id in chunk_ids if chunk_id in selected_ids
        )
        for criterion_idx, chunk_ids in criterion_candidates.items()
    }
    # Compute the final mapping exactly once from the post-pack selected set.
    # This same object feeds both the model-visible block and the validator.
    frame_assignments = _criterion_frame_assignments(
        selected,
        criterion_candidates,
        candidate_frame_indices,
    )
    text = render(
        selected,
        bool(omissions),
        frame_assignments=frame_assignments,
    )
    if estimator.count(text) != budget.included_estimated_tokens:
        raise RuntimeError("Final ALLOWED FRAMES rendering drifted from adaptive packing")
    return PackedTextEvidence(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        frame_indices=selected_indices,
        records_omitted_by_budget=len(omissions),
        budget_receipt=budget,
        omission_receipts=omissions,
        retrieval_omissions=tuple(retrieval_omissions),
        criterion_chunk_assignments=assignments,
        criterion_frame_assignments=frame_assignments,
    )
