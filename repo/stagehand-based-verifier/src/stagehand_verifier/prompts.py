from __future__ import annotations

import json
from typing import Any
from .taxonomy import TAXONOMY_PROMPT


PROMPT_VERSION = "stagehand-semantic-v2"

GROUNDING_RULES = """
Evidence is a Stagehand ARIA semantic tree, bounded page state, action metadata,
and bounded tool results—not pixels or raw HTML. Apply these rules strictly:
1. ARIA/page evidence proves only what it explicitly contains.
2. Actions record intent or attempts, never successful outcome by themselves.
3. tool_result.ok means the tool returned, not that the user task succeeded.
4. The final answer is a claim to verify, not browser-state evidence.
5. A persistent terminal state is stronger than a transient change.
6. Absence from ARIA does not prove visual absence.
7. ARIA membership does not prove viewport visibility without geometry.
8. Color, styling, exact layout, overlap, image pixels, canvas, charts, maps,
   and videos are unsupported unless semantic text explicitly establishes them.
9. Missing or modality-incompatible evidence must be UNKNOWN, never inferred.
10. Cite only supplied state ordinal, URL, and node identifiers; cite step and action_id only when present.
""".strip()


def rubric_generation_prompt(task: str) -> tuple[str, str]:
    system = """You design concise, independent evaluation rubrics for computer-use tasks.
Return JSON only. Do not inspect or anticipate trajectory evidence. Split the requested
task into observable criteria. Include conditional criteria only when genuinely needed."""
    user = f"""Task: {task}

Return:
{{"items":[{{"id":0,"criterion":"...","description":"...","points":1,
"condition":"optional condition","depends_on":[],"deterministic_check":null}}]}}
Use positive point weights. Do not include scores, evidence, or task-specific answers not
already stated in the instruction. Set deterministic_check only for an exact non-semantic
assertion, using one of: final_url_equals, final_url_contains, final_domain_equals,
terminal_contains_all, terminal_contains_any, terminal_not_contains, action_present,
all_tools_ok. Otherwise omit it or use null."""
    return system, user


def dependency_prompt(task: str, rubric: dict[str, Any]) -> tuple[str, str]:
    system = "You validate rubric dependencies and conditions. Return JSON only."
    user = f"""Task: {task}
Rubric: {json.dumps(rubric, ensure_ascii=False)}
Return the same rubric schema, changing only depends_on and condition where necessary.
Never score the rubric."""
    return system, user


def action_analysis_prompt(task: str, criterion: dict[str, Any], actions: list[dict[str, Any]]) -> tuple[str, str]:
    system = """You assess whether an ordered computer-use action history is consistent with
a rubric criterion. Actions prove attempts, not outcomes. Return JSON only."""
    user = f"""Task: {task}
Criterion: {json.dumps(criterion, ensure_ascii=False)}
Ordered actions: {json.dumps(actions, ensure_ascii=False)}
Return {{"assessment":"consistent|inconsistent|insufficient","reasoning":"...",
"relevant_steps":[1]}}. Do not award points and do not infer state changes."""
    return system, user


def criterion_evidence_prompt(
    task: str,
    criterion: dict[str, Any],
    final_answer: str,
    action_baseline: dict[str, Any],
    evidence: list[str],
) -> tuple[str, str]:
    system = f"""You are an evidence-grounded criterion judge.
{GROUNDING_RULES}
Return JSON only."""
    user = f"""Task: {task}
Criterion: {json.dumps(criterion, ensure_ascii=False)}
Final answer claim: {final_answer}
Action-only baseline: {json.dumps(action_baseline, ensure_ascii=False)}

Selected criterion-relevant evidence items (transitions or an actionless terminal state; not the complete trajectory):
{chr(10).join(evidence) if evidence else '[no frame passed retrieval threshold]'}

Return {{"status":"supported|contradicted|partial|unknown","earned_points":0,
"condition_met":true,"explanation":"...","citations":[{{"state_ordinal":2,"step":1,"action_id":"stagehand-0001","node_identifiers":["..."]}}]}}.
earned_points must be between 0 and criterion.points. If visual-only or missing evidence is
needed, status must be unknown and earned_points must be 0."""
    return system, user


def outcome_prompt(
    task: str,
    final_answer: str,
    criterion_results: list[dict[str, Any]],
    terminal: str,
    relevant_transitions: list[str],
) -> tuple[str, str]:
    system = f"""You evaluate final task outcome from persistent semantic evidence.
{GROUNDING_RULES}
Return JSON only."""
    user = f"""Task: {task}
Final answer: {final_answer}
Criterion decisions: {json.dumps(criterion_results, ensure_ascii=False)}
Terminal state: {terminal}
Selected relevant transitions: {chr(10).join(relevant_transitions)}
Return {{"outcome_success":true,"confidence":0.0,"reasoning":"...",
"unsupported_claims":[],"evidence_steps":[]}}. A plausible final answer without
supporting terminal/transition evidence is not success."""
    return system, user


def side_effect_prompt(task: str, timeline: str) -> tuple[str, str]:
    system = f"""You detect unintended side effects and cascading failures in a compact
ordered transition timeline. {GROUNDING_RULES} Return JSON only."""
    user = f"""Task: {task}
Timeline: {timeline}
Return {{"has_unintended_side_effect":false,"penalty":0,"reasoning":"...",
"first_problem_step":null,"error_code":null}}. If a side effect exists, use 5.1 or 5.2;
use 4.1-4.3 only for a transactional permission boundary. Penalize only evidence-grounded effects;
do not treat ordinary exploration as a side effect."""
    return system, user


def task_validity_prompt(task: str, terminal: str | None = None) -> tuple[str, str]:
    system = "You classify whether a computer-use task is valid and feasible. Return JSON only."
    context = f"\nTerminal semantic evidence: {terminal}" if terminal else ""
    user = f"""Task: {task}{context}
Return {{"valid":true,"reasoning":"...","blocked_by_environment":false}}.
Do not call a task invalid merely because the agent failed."""
    return system, user


def failure_prompt(
    task: str,
    outcome: dict[str, Any],
    criteria: list[dict[str, Any]],
    timeline: str,
    deterministic_errors: list[dict[str, Any]],
) -> tuple[str, str]:
    system = f"""You identify the earliest evidence-grounded failure in a computer-use
trajectory using the Universal Verifier error categories. {GROUNDING_RULES} Return JSON only."""
    user = f"""Task: {task}
Outcome: {json.dumps(outcome, ensure_ascii=False)}
Criterion results: {json.dumps(criteria, ensure_ascii=False)}
Deterministic tool errors: {json.dumps(deterministic_errors, ensure_ascii=False)}
Compact timeline: {timeline}
Allowed taxonomy codes and labels:
{TAXONOMY_PROMPT}
Return {{"first_failure_step":null,"error_code":null,"error_category":"none|planning|reasoning|action|tool_interaction|environment|outcome|unknown",
"error_type":"...","reasoning":"...","evidence_steps":[]}}.
If no failure is established, use null code and category none. If evidence is insufficient,
use category unknown rather than inventing a cause."""
    return system, user

