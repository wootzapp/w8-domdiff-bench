from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from .rubric import criterion_text
from .schemas import (
    AriaNode,
    EvidenceLink,
    SelectedEvidence,
    SemanticState,
    StagehandTrajectory,
    TransitionFrame,
)


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.:/-]{1,}", re.I)
STOP_WORDS = {
    "about", "after", "against", "also", "and", "are", "been", "before", "being",
    "both", "can", "does", "each", "for", "from", "has", "have", "into", "its",
    "must", "not", "only", "should", "that", "the", "their", "then", "this", "through",
    "to", "was", "were", "when", "where", "which", "will", "with", "without", "would",
    "task", "user", "agent", "criterion", "complete", "successfully",
}


def tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token.casefold()
        for token in TOKEN_RE.findall(text)
        if len(token) > 2 and token.casefold() not in STOP_WORDS
    )


def retrieval_concepts(
    task_instruction: str,
    criterion: dict[str, Any],
    final_answer: str,
) -> tuple[str, ...]:
    """Derive concepts at inference time; there are no task-family keyword lists."""
    weighted = Counter(tokens(criterion_text(criterion)))
    weighted.update({term: 0.55 for term in tokens(task_instruction)})
    weighted.update({term: 0.25 for term in tokens(final_answer)})
    return tuple(term for term, _ in weighted.most_common(80))


def _node_text(node: AriaNode) -> str:
    states = f" states={','.join(node.states)}" if node.states else ""
    parents = " > ".join(node.parent_context[-3:])
    parent = f" parent={parents}" if parents else ""
    return (
        f"node={node.semantic_key} ref={node.raw_reference} role={node.role} "
        f"name={node.accessible_name}{states}{parent}"
    ).strip()


def _frame_search_text(frame: TransitionFrame) -> str:
    changed = " ".join(f"{change.before} {change.after}" for change in frame.diff.node_changes)
    arguments = json.dumps(frame.action.arguments, ensure_ascii=False, sort_keys=True)
    tool = json.dumps(frame.action.tool_result, ensure_ascii=False, sort_keys=True)
    return " ".join(
        (
            frame.action.name,
            arguments,
            tool,
            frame.before.page.url,
            frame.before.page.title,
            frame.after.page.url,
            frame.after.page.title,
            frame.before.page.body_text_preview,
            frame.after.page.body_text_preview,
            changed,
        )
    )


def frame_relevance(frame: TransitionFrame, concepts: Iterable[str], final_ordinal: int) -> float:
    haystack = _frame_search_text(frame).casefold()
    concept_list = tuple(dict.fromkeys(concepts))
    overlap = sum(1.0 + min(len(term), 18) / 18 for term in concept_list if term in haystack)
    action_bonus = 0.8 if any(term in json.dumps(frame.action.arguments).casefold() for term in concept_list) else 0
    change_bonus = min(len(frame.diff.node_changes), 8) * 0.12
    nav_bonus = 0.7 if frame.diff.url_before != frame.diff.url_after else 0
    error_bonus = 1.0 if frame.action.tool_result.get("ok") is False else 0
    terminal_bonus = 0.45 if frame.after.ordinal == final_ordinal else 0
    return round(min(10.0, overlap + action_bonus + change_bonus + nav_bonus + error_bonus + terminal_bonus), 3)


def terminal_relevance(state: SemanticState, concepts: Iterable[str]) -> float:
    """Score the persistent terminal state as evidence, without inventing an action."""
    haystack = " ".join(
        (
            state.page.url,
            state.page.title,
            state.page.body_text_preview,
            *(node.searchable_text() for node in state.nodes),
        )
    ).casefold()
    concept_list = tuple(dict.fromkeys(concepts))
    overlap = sum(1.0 + min(len(term), 18) / 18 for term in concept_list if term in haystack)
    persistent_state_bonus = 0.45
    return round(min(10.0, overlap + persistent_state_bonus), 3)


def _rank_nodes(nodes: tuple[AriaNode, ...], concepts: tuple[str, ...], limit: int) -> list[AriaNode]:
    ranked: list[tuple[float, int, AriaNode]] = []
    for index, node in enumerate(nodes):
        text = node.searchable_text().casefold()
        score = sum(1.0 + min(len(term), 16) / 16 for term in concepts if term in text)
        if score:
            ranked.append((score, -index, node))
    ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [node for _, _, node in ranked[:limit]]


def _changed_nodes(frame: TransitionFrame, concepts: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
    values: list[tuple[float, dict[str, Any]]] = []
    for change in frame.diff.node_changes:
        text = f"{change.before} {change.after}".casefold()
        score = sum(1 for term in concepts if term in text)
        values.append(
            (
                score,
                {
                    "kind": change.kind,
                    "semantic_node_id": change.semantic_key,
                    "raw_reference_before": change.raw_reference_before,
                    "raw_reference_after": change.raw_reference_after,
                    "before": change.before,
                    "after": change.after,
                },
            )
        )
    values.sort(key=lambda item: item[0], reverse=True)
    return [value for _, value in values[:limit]]


def evidence_link(frame: TransitionFrame, node_ids: Iterable[str]) -> EvidenceLink:
    source = Path(frame.action.source_path)
    step_dir = source.parent
    return EvidenceLink(
        evidence_kind="transition",
        state_ordinal=frame.after.ordinal,
        step=frame.action.ordinal,
        action_id=frame.action.action_id,
        action_name=frame.action.name,
        before_url=frame.before.page.url,
        after_url=frame.after.page.url,
        node_identifiers=tuple(dict.fromkeys(node_ids)),
        source_paths=(
            str(source),
            str(step_dir / "tool_result.json"),
            str(step_dir / "aria.txt"),
            str(step_dir / "page_state.json"),
        ),
    )


def terminal_evidence_link(
    trajectory: StagehandTrajectory, node_ids: Iterable[str]
) -> EvidenceLink:
    state = trajectory.terminal_state
    step_dir = trajectory.path / f"step_{state.ordinal:03d}"
    return EvidenceLink(
        evidence_kind="terminal_state",
        state_ordinal=state.ordinal,
        step=None,
        action_id=None,
        action_name=None,
        before_url=None,
        after_url=state.page.url,
        node_identifiers=tuple(dict.fromkeys(node_ids)),
        source_paths=(
            str(step_dir / "aria.txt"),
            str(step_dir / "page_state.json"),
        ),
    )



def project_frame(frame: TransitionFrame, concepts: tuple[str, ...], char_budget: int) -> tuple[str, EvidenceLink]:
    before_nodes = _rank_nodes(frame.before.nodes, concepts, 18)
    after_nodes = _rank_nodes(frame.after.nodes, concepts, 24)
    changes = _changed_nodes(frame, concepts, 30)
    node_ids = [node.semantic_key for node in (*before_nodes, *after_nodes)]
    node_ids.extend(change["semantic_node_id"] for change in changes)
    payload = {
        "evidence_type": "stagehand_semantic_transition",
        "step": frame.action.ordinal,
        "action": {
            "action_id": frame.action.action_id,
            "name": frame.action.name,
            "arguments": frame.action.arguments,
            "tool_result": frame.action.tool_result,
        },
        "before": {
            "state_ordinal": frame.before.ordinal,
            "url": frame.before.page.url,
            "title": frame.before.page.title,
            "scroll": [frame.before.page.scroll_x, frame.before.page.scroll_y],
            "capture_status": frame.before.capture_status,
            "synthetic": frame.before.synthetic,
            "relevant_nodes": [_node_text(node) for node in before_nodes],
        },
        "after": {
            "state_ordinal": frame.after.ordinal,
            "url": frame.after.page.url,
            "title": frame.after.page.title,
            "scroll": [frame.after.page.scroll_x, frame.after.page.scroll_y],
            "capture_status": frame.after.capture_status,
            "relevant_nodes": [_node_text(node) for node in after_nodes],
        },
        "semantic_changes": changes,
        "coverage": {
            "modality": "Stagehand ARIA semantic tree plus page state",
            "pixel_evidence": False,
            "geometry_available": False,
        },
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) > char_budget:
        text = text[: char_budget - 70] + '\n{"truncated": true, "reason": "frame_char_budget"}\n'
    return text, evidence_link(frame, node_ids)


def project_terminal_state(
    trajectory: StagehandTrajectory,
    concepts: tuple[str, ...],
    char_budget: int,
) -> tuple[str, EvidenceLink]:
    state = trajectory.terminal_state
    nodes = _rank_nodes(state.nodes, concepts, 60)
    payload = {
        "evidence_type": "stagehand_terminal_state",
        "state_ordinal": state.ordinal,
        "action": None,
        "url": state.page.url,
        "title": state.page.title,
        "ready_state": state.page.ready_state,
        "scroll": [state.page.scroll_x, state.page.scroll_y],
        "capture_status": state.capture_status,
        "relevant_nodes": [_node_text(node) for node in nodes],
        "bounded_body_text_fallback": state.page.body_text_preview,
        "limitations": [
            "No pixels, color, exact geometry, overlap, canvas, chart, or image-content evidence.",
            "ARIA inclusion does not prove viewport visibility without geometry.",
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) > char_budget:
        text = text[: char_budget - 40] + '\n{"truncated": true}\n'
    return text, terminal_evidence_link(
        trajectory, (node.semantic_key for node in nodes)
    )


def select_evidence(
    trajectory: StagehandTrajectory,
    criterion_index: int,
    criterion: dict[str, Any],
    *,
    top_k: int,
    min_score: float,
    frame_char_budget: int,
    context_char_budget: int,
) -> list[SelectedEvidence]:
    concepts = retrieval_concepts(
        trajectory.task.instruction, criterion, trajectory.final_answer
    )
    ranked: list[tuple[float, int, str, int | None, TransitionFrame | None]] = [
        (
            frame_relevance(frame, concepts, trajectory.terminal_state.ordinal),
            index,
            "transition",
            index,
            frame,
        )
        for index, frame in enumerate(trajectory.frames)
    ]
    # A terminal state can be captured after the final action. It competes inside
    # the same criterion top-k budget and remains explicitly actionless.
    ranked.append(
        (
            terminal_relevance(trajectory.terminal_state, concepts),
            len(trajectory.frames),
            "terminal_state",
            None,
            None,
        )
    )
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    candidates = [item for item in ranked if item[0] >= min_score][:top_k]
    selected: list[SelectedEvidence] = []
    used = 0
    for score, _, evidence_kind, frame_index, frame in candidates:
        if evidence_kind == "terminal_state":
            projection, link = project_terminal_state(
                trajectory, concepts, frame_char_budget
            )
        else:
            assert frame is not None
            projection, link = project_frame(frame, concepts, frame_char_budget)
        remaining = context_char_budget - used
        if remaining <= 0:
            break
        if len(projection) > remaining:
            projection = projection[: max(0, remaining - 40)] + '\n{"context_truncated": true}\n'
        if not projection:
            break
        selected.append(SelectedEvidence(criterion_index, frame_index, score, projection, link))
        used += len(projection)
    return selected

def terminal_projection(trajectory: StagehandTrajectory, criterion: dict[str, Any] | None, budget: int) -> str:
    concepts = retrieval_concepts(
        trajectory.task.instruction,
        criterion or {"criterion": trajectory.task.instruction},
        trajectory.final_answer,
    )
    text, _ = project_terminal_state(trajectory, concepts, budget)
    return text


def global_timeline(trajectory: StagehandTrajectory, budget: int) -> str:
    """Compact non-raw context for side effects and cascading failures."""
    rows: list[dict[str, Any]] = []
    for frame in trajectory.frames:
        important_changes = [
            {
                "kind": change.kind,
                "node": change.semantic_key,
                "before": change.before[:200],
                "after": change.after[:200],
            }
            for change in frame.diff.node_changes[:12]
        ]
        rows.append(
            {
                "step": frame.action.ordinal,
                "action_id": frame.action.action_id,
                "action": frame.action.name,
                "arguments": frame.action.arguments,
                "tool_ok": frame.action.tool_result.get("ok"),
                "before_url": frame.before.page.url,
                "after_url": frame.after.page.url,
                "scroll_before": frame.diff.scroll_before,
                "scroll_after": frame.diff.scroll_after,
                "changes": important_changes,
            }
        )
    payload = {
        "evidence_type": "stagehand_compact_global_transition_timeline",
        "transitions": rows,
        "terminal_url": trajectory.terminal_state.page.url,
        "terminal_title": trajectory.terminal_state.page.title,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return text if len(text) <= budget else text[: budget - 40] + '\n{"truncated": true}\n'


def selected_links(values: Iterable[SelectedEvidence]) -> list[dict[str, Any]]:
    return [asdict(value.link) for value in values]

