"""DOM-model prompt binding and non-scoring evidence audit helpers."""

from __future__ import annotations

from typing import Any

from .schemas import DomModelState


LIMITATIONS = (
    "DOM-model evidence cannot prove pixel-only color, styling, geometry, overlap, clipping, "
    "z-order, or unrepresented image/canvas/video content. Treat absent content as unproven, "
    "not false; source-declared truncation further limits coverage."
)


def relevance_prompt(
    *, task: str, init_url_context: str, criteria_text: str, state: DomModelState,
    action_count: int, rendered_state: str | None = None,
) -> str:
    return f"""Evaluate how relevant this complete DOM-model browser state is to every rubric criterion.

Task:
{task}{init_url_context}

Rubric criteria:
{criteria_text}

Evidence rules:
- Score every criterion from 0 (irrelevant) through 10 (directly decisive).
- Return one JSON key criterion_0, criterion_1, and so on, with integer values only.
- This is a full ordered state, not a DOM diff.
- {LIMITATIONS}

DOM-model evidence:
{rendered_state if rendered_state is not None else state.model_text(action_count=action_count)}
"""


def criterion_prompt(
    *, task: str, init_url_context: str, action_history: str, predicted_output: str,
    criterion_info: str, conditional_check: str, conditional_output: str,
    state: DomModelState, action_count: int, rendered_state: str | None = None,
) -> str:
    return f"""Analyze the DOM-model state as evidence for exactly one rubric criterion.

Task: {task}{init_url_context}
Action history:
{action_history}
Agent predicted output:
{predicted_output}

{criterion_info}

Return JSON with nonempty string fields screenshot_evidence, criterion_analysis, discrepancies;
a boolean environment_issues_confirmed{conditional_output}.{conditional_check}
The compatibility name screenshot_evidence means DOM-model evidence in this run.
{LIMITATIONS}

DOM-model evidence:
{rendered_state if rendered_state is not None else state.model_text(action_count=action_count)}
"""


def batched_prompt(
    *, task: str, init_url_context: str, action_history: str, predicted_output: str,
    criteria_info: str, state: DomModelState, action_count: int,
    rendered_state: str | None = None,
) -> str:
    return f"""Analyze one DOM-model state against the listed rubric criteria in order.

Task: {task}{init_url_context}
Action history:
{action_history}
Agent predicted output:
{predicted_output}

Criteria:
{criteria_info}

Return JSON {{"analyses": [...]}} with exactly one ordered entry per criterion. Each entry must
contain criterion_idx, nonempty string fields screenshot_evidence, criterion_analysis, discrepancies,
and boolean environment_issues_confirmed. Conditional criteria also require boolean
condition_verification. The compatibility name screenshot_evidence means DOM-model evidence.
{LIMITATIONS}

DOM-model evidence:
{rendered_state if rendered_state is not None else state.model_text(action_count=action_count)}
"""


def base_audit(states: list[DomModelState]) -> dict[str, Any]:
    return {
        "evidence_mode": "dom_model",
        "complete_state_count": len(states),
        "final_state_index": states[-1].index if states else None,
        "states": [state.audit_dict() for state in states],
        "estimated_evidence_tokens": sum(state.estimated_tokens for state in states),
        "context_omissions": [],
        "coverage_limited": any(state.source_truncated for state in states),
        "limitations": [LIMITATIONS],
    }
