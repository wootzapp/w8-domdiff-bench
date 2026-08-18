"""Default-off dom_diff_summary S3-style hard caps for DOM-text evidence.

The current DOM-text parser, compactor, retrieval, and context packer run first.
This module only clips fields and packs the already-selected model records.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, Mapping, Sequence

from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_compaction import (
    CompactDOMDiffTextFrame,
    coverage_line,
    page_line,
    step_header,
)
from webeval.rubric_agent.dom_diff_text_retrieval import (
    ModelEvidenceRecord,
    OmissionReceipt,
    PackedTextEvidence,
    render_criterion_assignment_tag,
)


S3_FIELD_CHAR_LIMIT = 600
S3_PROMPT_RESERVE_TOKENS = 64
S3_PRIORITY_BY_CLASS = {
    "navigation": 100,
    "semantic_state_change": 95,
    "signal_text": 90,
    "signal_interactive": 85,
    "ordinary_text": 70,
    "ordinary_interactive": 55,
    "scroll_transition": 35,
}
_SIGNAL_RE = re.compile(
    r"(?:"
    r"(?<!\w)[+-]?\d[\d,.'’]*(?:\s?(?:%|[A-Za-z°²³]+))?"
    r"|\b(?:error|failed|failure|warning|invalid|success|successful|confirmed|"
    r"confirmation|complete|completed|submitted|saved|deleted|cancelled|"
    r"canceled|blocked)\b"
    r")",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(
    r"(?<!\w)[+-]?\d[\d,.'’]*(?:\s?(?:%|[A-Za-z°²³]+))?",
    re.IGNORECASE,
)
_STATE_RE = re.compile(
    r"\b(?:checked|selected|expanded|disabled|pressed|value|state|true|false)\b",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=")
_RECORD_PREFIX_RE = re.compile(
    r"^(?P<prefix>(?:@\d+(?:,\d+)*\s+)?\[[^\]]+\]\s+\S+)(?:\s+(?P<body>.*))?$"
)
_CHUNK_SUFFIX_RE = re.compile(r"(?:\s+chunk=\d+/\d+)$")


@dataclass(frozen=True)
class _ClippedRecord:
    source: ModelEvidenceRecord
    text: str
    semantic_class: str
    priority: int
    fields_clipped: int
    removed_suffixes: tuple[str, ...]
    stage_order: int
    owner_frame_idx: int
    exact_signal: bool
    numeric_signal: bool
    state_signal: bool
    navigation_signal: bool


@dataclass(frozen=True)
class _FramePack:
    frame_idx: int
    selected: tuple[_ClippedRecord, ...]
    omitted: tuple[_ClippedRecord, ...]
    allowance_tokens: int
    used_tokens: int


def _clip_string(value: str, limit: int) -> tuple[str, str | None]:
    if len(value) <= limit:
        return value, None
    clipped = value[: limit - 1].rstrip() + "…"
    return clipped, value[len(clipped.rstrip("…")) :]


def _clip_json_value(value: Any, limit: int) -> tuple[Any, int, tuple[str, ...]]:
    if isinstance(value, str):
        clipped, removed = _clip_string(value, limit)
        return clipped, int(removed is not None), ((removed,) if removed else ())
    if isinstance(value, list):
        output: list[Any] = []
        count = 0
        removed: list[str] = []
        for item in value:
            transformed, item_count, item_removed = _clip_json_value(item, limit)
            output.append(transformed)
            count += item_count
            removed.extend(item_removed)
        return output, count, tuple(removed)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        count = 0
        removed: list[str] = []
        for key, item in value.items():
            transformed, item_count, item_removed = _clip_json_value(item, limit)
            output[key] = transformed
            count += item_count
            removed.extend(item_removed)
        return output, count, tuple(removed)
    return value, 0, ()


def _clip_body_fields(body: str, limit: int) -> tuple[str, int, tuple[str, ...]]:
    suffix = ""
    suffix_match = _CHUNK_SUFFIX_RE.search(body)
    if suffix_match:
        suffix = suffix_match.group(0)
        body = body[: suffix_match.start()]

    decoder = json.JSONDecoder()
    stripped = body.lstrip()
    leading = body[: len(body) - len(stripped)]
    if stripped.startswith('"'):
        try:
            value, end = decoder.raw_decode(stripped)
        except json.JSONDecodeError:
            value = None
        else:
            transformed, count, removed = _clip_json_value(value, limit)
            tail = stripped[end:]
            return (
                leading + json.dumps(transformed, ensure_ascii=False) + tail + suffix,
                count,
                removed,
            )

    output: list[str] = []
    position = 0
    clipped_count = 0
    removed_suffixes: list[str] = []
    while position < len(body):
        whitespace_start = position
        while position < len(body) and body[position].isspace():
            position += 1
        output.append(body[whitespace_start:position])
        match = _FIELD_RE.match(body, position)
        if match is None:
            remainder = body[position:]
            clipped, removed = _clip_string(remainder, limit)
            output.append(clipped)
            if removed is not None:
                clipped_count += 1
                removed_suffixes.append(removed)
            position = len(body)
            break
        output.append(match.group(0))
        position = match.end()
        if match.group(1) == "chunk":
            output.append(body[position:])
            position = len(body)
            break
        try:
            value, length = decoder.raw_decode(body[position:])
        except json.JSONDecodeError:
            next_match = re.search(r"\s+[A-Za-z_][A-Za-z0-9_]*=", body[position:])
            end = position + next_match.start() if next_match else len(body)
            clipped, removed = _clip_string(body[position:end], limit)
            output.append(clipped)
            if removed is not None:
                clipped_count += 1
                removed_suffixes.append(removed)
            position = end
            continue
        transformed, count, removed = _clip_json_value(value, limit)
        output.append(
            json.dumps(
                transformed,
                ensure_ascii=False,
                sort_keys=isinstance(transformed, dict),
                separators=(",", ":") if isinstance(transformed, (dict, list)) else None,
            )
        )
        clipped_count += count
        removed_suffixes.extend(removed)
        position += length
    return "".join(output) + suffix, clipped_count, tuple(removed_suffixes)


def clip_model_facing_fields(
    text: str, *, max_chars: int = S3_FIELD_CHAR_LIMIT
) -> tuple[str, int, tuple[str, ...]]:
    """Clip each selected model-facing field, never the packed record itself."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    match = _RECORD_PREFIX_RE.match(text)
    if match is None:
        clipped, removed = _clip_string(text, max_chars)
        return clipped, int(removed is not None), ((removed,) if removed else ())
    body = match.group("body") or ""
    if not body:
        return text, 0, ()
    transformed, count, removed = _clip_body_fields(body, max_chars)
    return f"{match.group('prefix')} {transformed}".rstrip(), count, removed


def _semantic_class(record: ModelEvidenceRecord) -> str:
    chunk = record.chunk
    combined = chunk.search_text
    if chunk.operation == "navigation":
        return "navigation"
    if chunk.operation == "changed" or "states=" in record.text or " field=" in record.text:
        return "semantic_state_change"
    if chunk.operation == "scroll" or chunk.record_kind == "scroll_transition":
        return "scroll_transition"
    has_signal = bool(_SIGNAL_RE.search(combined))
    if chunk.record_kind == "text":
        return "signal_text" if has_signal else "ordinary_text"
    return "signal_interactive" if has_signal else "ordinary_interactive"


def _to_clipped(
    records: Sequence[ModelEvidenceRecord],
    applicable_frames: Sequence[int],
    frame_index_by_step: Mapping[int, int],
) -> tuple[_ClippedRecord, ...]:
    fallback_frame = min(applicable_frames) if applicable_frames else 0
    output: list[_ClippedRecord] = []
    for stage_order, record in enumerate(records):
        semantic_class = _semantic_class(record)
        text, clipped_count, removed = clip_model_facing_fields(record.text)
        frames = tuple(index for index in record.frame_indices if index in applicable_frames)
        owner = frame_index_by_step.get(
            record.chunk.action_ordinal,
            min(frames) if frames else fallback_frame,
        )
        combined = record.chunk.search_text
        output.append(
            _ClippedRecord(
                source=record,
                text=text,
                semantic_class=semantic_class,
                priority=S3_PRIORITY_BY_CLASS[semantic_class],
                fields_clipped=clipped_count,
                removed_suffixes=removed,
                stage_order=stage_order,
                owner_frame_idx=owner,
                exact_signal=any(
                    reason in {"exact_phrase", "exact_number_date_or_unit"}
                    for reason in record.reasons
                ),
                numeric_signal=bool(_NUMBER_RE.search(combined)),
                state_signal=(
                    record.chunk.operation == "changed"
                    or "states=" in record.text
                    or " field=" in record.text
                ),
                navigation_signal=record.chunk.operation == "navigation",
            )
        )
    return tuple(output)


def _frame_header(frame_idx: int, frame: CompactDOMDiffTextFrame) -> str:
    return f"FRAME {frame_idx} | {step_header(frame)}"


def _record_line(stage: str, record: _ClippedRecord) -> str:
    if stage == "analysis":
        return (
            f"{render_criterion_assignment_tag(record.source.criterion_indices)} "
            f"{record.text}"
        )
    return record.text


def _receipt_line(
    omitted: Sequence[_ClippedRecord],
    clipped: Sequence[_ClippedRecord],
) -> str:
    by_class = Counter(item.semantic_class for item in omitted)
    class_text = (
        ",".join(f"{key}:{by_class[key]}" for key in S3_PRIORITY_BY_CLASS if by_class[key])
        or "none"
    )
    return (
        "OMITTED "
        f"s3_cap_budget={len(omitted)} "
        f"s3_fields_clipped={sum(item.fields_clipped for item in clipped)} "
        f"s3_classes={class_text}"
    )


def _frame_text(
    stage: str,
    frame_idx: int,
    frame: CompactDOMDiffTextFrame,
    selected: Sequence[_ClippedRecord],
    omitted: Sequence[_ClippedRecord],
    all_owned: Sequence[_ClippedRecord],
) -> str:
    ordered = sorted(selected, key=lambda item: item.source.stable_order)
    return "\n".join(
        [
            _frame_header(frame_idx, frame),
            page_line(frame),
            coverage_line(frame),
            *(_record_line(stage, item) for item in ordered),
            _receipt_line(omitted, all_owned),
        ]
    )


def _pack_frame(
    *,
    stage: str,
    frame_idx: int,
    frame: CompactDOMDiffTextFrame,
    candidates: Sequence[_ClippedRecord],
    allowance_tokens: int,
    estimator: TokenEstimator,
) -> _FramePack:
    ordered_for_packing = sorted(
        candidates,
        key=lambda item: (-item.priority, item.source.stable_order),
    )
    selected: list[_ClippedRecord] = []
    for candidate in ordered_for_packing:
        proposed = [*selected, candidate]
        proposed_ids = {item.source.item_id for item in proposed}
        omitted = [
            item for item in candidates if item.source.item_id not in proposed_ids
        ]
        text = _frame_text(
            stage, frame_idx, frame, proposed, omitted, candidates
        )
        if estimator.count(text) <= allowance_tokens:
            selected = proposed
    selected_ids = {item.source.item_id for item in selected}
    omitted = tuple(
        item for item in candidates if item.source.item_id not in selected_ids
    )
    text = _frame_text(stage, frame_idx, frame, selected, omitted, candidates)
    used = estimator.count(text)
    if used > allowance_tokens:
        raise ValueError(
            f"{stage} FRAME {frame_idx} mandatory header/coverage/receipt "
            f"requires {used} tokens but allowance is {allowance_tokens}"
        )
    return _FramePack(
        frame_idx=frame_idx,
        selected=tuple(selected),
        omitted=omitted,
        allowance_tokens=allowance_tokens,
        used_tokens=used,
    )


def _assignments(
    selected: Sequence[_ClippedRecord],
    criterion_indices: Iterable[int],
    source_chunk_assignments: Mapping[int, Sequence[str]] | None = None,
) -> tuple[dict[int, tuple[str, ...]], dict[int, tuple[int, ...]]]:
    selected_by_criterion = {
        criterion_idx: {
            item.source.item_id
            for item in selected
            if criterion_idx in item.source.criterion_indices
        }
        for criterion_idx in criterion_indices
    }
    if source_chunk_assignments is None:
        chunk_assignments = {
            criterion_idx: tuple(
                item.source.item_id
                for item in selected
                if criterion_idx in item.source.criterion_indices
            )
            for criterion_idx in criterion_indices
        }
    else:
        chunk_assignments = {}
        for criterion_idx in criterion_indices:
            original = tuple(source_chunk_assignments.get(criterion_idx, ()))
            selected_ids = selected_by_criterion[criterion_idx]
            unknown = selected_ids.difference(original)
            if unknown:
                raise RuntimeError(
                    "S3 analysis selected records missing from source assignments: "
                    f"criterion {criterion_idx}, records {sorted(unknown)}"
                )
            # Preserve the retrieval stage criterion-specific ranking while
            # projecting it through the one final post-cap selected set.
            chunk_assignments[criterion_idx] = tuple(
                item_id for item_id in original if item_id in selected_ids
            )
    frame_assignments = {
        criterion_idx: tuple(
            sorted(
                {
                    frame_idx
                    for item in selected
                    if criterion_idx in item.source.criterion_indices
                    for frame_idx in item.source.frame_indices
                }
            )
        )
        for criterion_idx in criterion_indices
    }
    return chunk_assignments, frame_assignments


def _allowed_lines(assignments: Mapping[int, Sequence[int]]) -> list[str]:
    return [
        "ALLOWED FRAMES",
        *[
            f"C{criterion_idx}=[{','.join(str(index) for index in indices)}]"
            for criterion_idx, indices in sorted(assignments.items())
        ],
    ]


def _render_stage(
    *,
    stage: str,
    frames: Sequence[CompactDOMDiffTextFrame],
    frame_indices: Sequence[int],
    frame_packs: Sequence[_FramePack],
    criterion_indices: Sequence[int],
    had_prior_context_omissions: bool,
    source_chunk_assignments: Mapping[int, Sequence[str]] | None = None,
) -> tuple[
    str,
    tuple[_ClippedRecord, ...],
    dict[int, tuple[str, ...]],
    dict[int, tuple[int, ...]],
]:
    selected = tuple(
        sorted(
            (item for pack in frame_packs for item in pack.selected),
            key=lambda item: item.stage_order,
        )
    )
    chunk_assignments, frame_assignments = _assignments(
        selected,
        criterion_indices,
        source_chunk_assignments,
    )
    if stage == "relevance":
        heading = ["ALL ACTION-ALIGNED REFINED DOM-DIFF TEXT FRAMES"]
    else:
        heading = [
            "SELECTED REFINED DOM-DIFF TEXT EVIDENCE LIBRARY",
            "ASSIGNMENT: C[criterion indexes] on each evidence line is complete.",
        ]
    frame_headers = [
        line
        for frame_idx in frame_indices
        for line in (
            _frame_header(frame_idx, frames[frame_idx]),
            page_line(frames[frame_idx]),
            coverage_line(frames[frame_idx]),
        )
    ]
    allowed = _allowed_lines(frame_assignments) if stage == "analysis" else []
    records = [_record_line(stage, item) for item in selected]
    receipts = [
        (
            f"OMITTED FRAME {pack.frame_idx} "
            + _receipt_line(
                pack.omitted,
                tuple([*pack.selected, *pack.omitted]),
            ).removeprefix("OMITTED ")
        )
        for pack in frame_packs
    ]
    lines = [*heading, *frame_headers, *allowed, *records, *receipts]
    if had_prior_context_omissions:
        lines.append(
            "COVERAGE context_limit_omitted_relevant_records; consult audit receipt; "
            "use unknown when omitted evidence prevents a safe conclusion"
        )
    return "\n".join(lines), selected, chunk_assignments, frame_assignments


def _loss_counts(
    omitted: Sequence[_ClippedRecord],
    selected: Sequence[_ClippedRecord],
) -> dict[str, Any]:
    flags = {
        "exact_match": "exact_signal",
        "numeric": "numeric_signal",
        "state": "state_signal",
        "navigation": "navigation_signal",
    }
    omitted_loss = {
        key: sum(bool(getattr(item, attr)) for item in omitted)
        for key, attr in flags.items()
    }
    clipped_suffix_loss = {
        "exact_match": 0,
        "numeric": sum(
            any(_NUMBER_RE.search(suffix) for suffix in item.removed_suffixes)
            for item in selected
        ),
        "state": sum(
            item.state_signal
            and any(_STATE_RE.search(suffix) for suffix in item.removed_suffixes)
            for item in selected
        ),
        "navigation": sum(
            item.navigation_signal
            and any(suffix.strip() for suffix in item.removed_suffixes)
            for item in selected
        ),
    }
    return {
        "potential_exact_match_records_affected_by_clipping": sum(
            item.exact_signal and bool(item.removed_suffixes)
            for item in selected
        ),
        "omitted_records": omitted_loss,
        "clipped_suffixes": clipped_suffix_loss,
        "total": {
            key: omitted_loss[key] + clipped_suffix_loss[key] for key in flags
        },
    }


def apply_s3_prompt_cap(
    packed: PackedTextEvidence,
    frames: Sequence[CompactDOMDiffTextFrame],
    *,
    stage: str,
    total_prompt_cap_tokens: int,
    empty_prompt_tokens: int,
    render_prompt: Callable[[str], str],
    model: str = "gpt-5.2",
    reserve_tokens: int = S3_PROMPT_RESERVE_TOKENS,
) -> PackedTextEvidence:
    """Apply S3 clipping and equal-per-frame hard packing to current evidence."""
    if stage not in {"relevance", "analysis"}:
        raise ValueError("stage must be relevance or analysis")
    if total_prompt_cap_tokens <= 0 or empty_prompt_tokens < 0 or reserve_tokens < 0:
        raise ValueError("prompt cap and token accounting values must be valid")
    estimator = TokenEstimator(model)
    actual_empty_tokens = estimator.count(render_prompt(""))
    if actual_empty_tokens != empty_prompt_tokens:
        raise ValueError(
            "Empty prompt token accounting drifted before S3 cap "
            f"({empty_prompt_tokens} != {actual_empty_tokens})"
        )
    evidence_budget = total_prompt_cap_tokens - empty_prompt_tokens - reserve_tokens
    minimum_evidence = 120 if stage == "relevance" else 160
    minimum_frame = 80 if stage == "relevance" else 100
    if evidence_budget < minimum_evidence:
        raise ValueError(
            f"{stage} total prompt cap leaves only {evidence_budget} evidence tokens"
        )

    frame_indices = tuple(packed.frame_indices)
    if not frame_indices:
        raise ValueError(f"{stage} has no applicable frames to cap")
    frame_index_by_step = {
        frames[index].action_ordinal: index for index in frame_indices
    }
    clipped = _to_clipped(
        packed.model_records, frame_indices, frame_index_by_step
    )
    by_owner = {
        frame_idx: tuple(item for item in clipped if item.owner_frame_idx == frame_idx)
        for frame_idx in frame_indices
    }
    allowance = max(minimum_evidence, evidence_budget // len(frame_indices))
    iterations: list[int] = []
    final: tuple[
        str,
        tuple[_ClippedRecord, ...],
        dict[int, tuple[str, ...]],
        dict[int, tuple[int, ...]],
    ] | None = None
    final_packs: list[_FramePack] = []
    while True:
        iterations.append(allowance)
        frame_packs = [
            _pack_frame(
                stage=stage,
                frame_idx=frame_idx,
                frame=frames[frame_idx],
                candidates=by_owner[frame_idx],
                allowance_tokens=allowance,
                estimator=estimator,
            )
            for frame_idx in frame_indices
        ]
        criterion_indices = (
            sorted((packed.criterion_chunk_assignments or {}).keys())
            if stage == "analysis"
            else []
        )
        rendered = _render_stage(
            stage=stage,
            frames=frames,
            frame_indices=frame_indices,
            frame_packs=frame_packs,
            criterion_indices=criterion_indices,
            had_prior_context_omissions=bool(packed.omission_receipts),
            source_chunk_assignments=(
                packed.criterion_chunk_assignments if stage == "analysis" else None
            ),
        )
        evidence_tokens = estimator.count(rendered[0])
        prompt_tokens = estimator.count(render_prompt(rendered[0]))
        if evidence_tokens <= evidence_budget and prompt_tokens <= total_prompt_cap_tokens:
            final = rendered
            final_packs = frame_packs
            break
        if allowance <= minimum_frame:
            raise ValueError(
                f"{stage} S3 prompt remains {prompt_tokens} tokens at the "
                f"{minimum_frame}-token per-frame floor; cap is "
                f"{total_prompt_cap_tokens}"
            )
        reduced = max(minimum_frame, int(allowance * 0.8))
        if reduced >= allowance:
            raise ValueError(f"{stage} S3 allowance cannot be reduced further")
        allowance = reduced

    assert final is not None
    text, selected, chunk_assignments, frame_assignments = final
    selected_ids = {item.source.item_id for item in selected}
    omitted = tuple(
        item for item in clipped if item.source.item_id not in selected_ids
    )
    omission_receipts = tuple(
        OmissionReceipt(
            stage=f"text_{stage}_s3_cap",
            reason="s3_prompt_cap",
            item_id=item.source.item_id,
            action_ordinal=item.source.chunk.action_ordinal,
            criterion_indices=item.source.criterion_indices,
            relevance_rank=index,
            estimated_tokens=estimator.count(item.text),
            source_refs=item.source.chunk.source_refs,
        )
        for index, item in enumerate(
            sorted(clipped, key=lambda value: (-value.priority, value.source.stable_order)),
            start=1,
        )
        if item.source.item_id not in selected_ids
    )

    all_by_class = Counter(item.semantic_class for item in clipped)
    omitted_by_class = Counter(item.semantic_class for item in omitted)
    post_clip_full_packs = [
        _FramePack(
            frame_idx=frame_idx,
            selected=by_owner[frame_idx],
            omitted=(),
            allowance_tokens=10**9,
            used_tokens=0,
        )
        for frame_idx in frame_indices
    ]
    criterion_indices = (
        sorted((packed.criterion_chunk_assignments or {}).keys())
        if stage == "analysis"
        else []
    )
    post_clip_text = _render_stage(
        stage=stage,
        frames=frames,
        frame_indices=frame_indices,
        frame_packs=post_clip_full_packs,
        criterion_indices=criterion_indices,
        had_prior_context_omissions=bool(packed.omission_receipts),
        source_chunk_assignments=(
            packed.criterion_chunk_assignments if stage == "analysis" else None
        ),
    )[0]
    clipped_in_current_layout = packed.text
    for item in clipped:
        if item.text != item.source.text:
            clipped_in_current_layout = clipped_in_current_layout.replace(
                item.source.text, item.text, 1
            )
    prompt_tokens = estimator.count(render_prompt(text))
    receipt = {
        "enabled": True,
        "policy": "dom_diff_summary_s3",
        "stage": stage,
        "total_prompt_cap_tokens": total_prompt_cap_tokens,
        "empty_prompt_tokens": empty_prompt_tokens,
        "reserve_tokens": reserve_tokens,
        "available_evidence_budget_tokens": evidence_budget,
        "evidence_tokens_before_s3": packed.estimated_tokens,
        "evidence_tokens_after_600_char_clipping": estimator.count(clipped_in_current_layout),
        "s3_envelope_tokens_after_600_char_clipping": estimator.count(post_clip_text),
        "final_packed_evidence_tokens": estimator.count(text),
        "final_prompt_tokens": prompt_tokens,
        "records_before": len(clipped),
        "records_retained": len(selected),
        "records_omitted": len(omitted),
        "fields_clipped": sum(item.fields_clipped for item in clipped),
        "records_by_semantic_class": dict(sorted(all_by_class.items())),
        "omission_counts_by_semantic_class": dict(sorted(omitted_by_class.items())),
        "per_frame_budget_allocation": [
            {
                "frame_idx": pack.frame_idx,
                "step": frames[pack.frame_idx].action_ordinal,
                "allowance_tokens": pack.allowance_tokens,
                "used_tokens": pack.used_tokens,
                "unused_tokens": pack.allowance_tokens - pack.used_tokens,
                "records_before": len(by_owner[pack.frame_idx]),
                "records_retained": len(pack.selected),
                "records_omitted": len(pack.omitted),
            }
            for pack in final_packs
        ],
        "per_frame_allowance_iterations": iterations,
        "unused_evidence_budget_tokens": evidence_budget - estimator.count(text),
        "unused_total_prompt_budget_tokens": total_prompt_cap_tokens - prompt_tokens,
        "evidence_loss": _loss_counts(omitted, selected),
    }
    if stage == "analysis":
        # One final selected set feeds rendering and validator assignments.
        original_ids = {
            key: tuple(value)
            for key, value in (packed.criterion_chunk_assignments or {}).items()
        }
        if not omitted and chunk_assignments != original_ids:
            raise RuntimeError("S3 no-omission analysis assignments drifted")
    return replace(
        packed,
        text=text,
        estimated_tokens=estimator.count(text),
        records_omitted_by_budget=(
            packed.records_omitted_by_budget + len(omission_receipts)
        ),
        omission_receipts=(*packed.omission_receipts, *omission_receipts),
        criterion_chunk_assignments=(
            chunk_assignments if stage == "analysis" else packed.criterion_chunk_assignments
        ),
        criterion_frame_assignments=(
            frame_assignments if stage == "analysis" else packed.criterion_frame_assignments
        ),
        model_records=tuple(item.source for item in selected),
        experimental_s3_cap_receipt=receipt,
    )
