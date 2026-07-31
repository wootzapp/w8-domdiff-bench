"""Prompts for the isolated DOM-diff-only verifier ablation."""

from string import Template


DOM_DIFF_GROUNDING_RULES = """
GROUNDING RULES FOR DOM-DIFF-ONLY EVIDENCE:
- The evidence proves only changes explicitly recorded in this diff.
- Absence from the diff does not prove absence from the page.
- Unchanged text, controls, and attributes are unknown.
- The initial state and persistent final state are unknown unless an explicit
  change record contains the relevant before/after value.
- URL, title, viewport, scroll position, visual layout, color, image pixels,
  canvas, charts, and cross-origin content are unknown unless explicitly
  represented in the diff itself.
- Never infer a before-state or after-state from filenames, references, action
  history, the agent's answer, or the fact that an action was attempted.
- Treat unsupported evidence as unknown, not as failure. Use contradicted only
  when an explicit change is incompatible with the criterion.
""".strip()


DOM_DIFF_CRITERION_RELEVANCE_PROMPT = Template(
    """
You are ranking one action-aligned DOM diff for rubric evaluation.

Task:
$task_definition
$init_url_context

DOM diff evidence:
$dom_diff_frame

Rubric criteria:
$rubric_criteria

$grounding_rules

Return a JSON object with exactly one integer score from 0 to 10 for every
criterion, using keys criterion_0, criterion_1, and so on. Relevance means the
explicit change records could support or contradict that criterion. A diff is
not relevant merely because the action history or final answer mentions it.
""".strip()
)

DOM_DIFF_BATCHED_EVIDENCE_ANALYSIS_PROMPT = Template(
    """
Analyze a single action-aligned DOM diff against each listed rubric criterion.

Task:
$task_definition
$init_url_context

Action history (context only; it is not browser-state evidence):
$action_history

Agent final answer (a claim to verify, not evidence):
$agent_predicted_output

DOM diff evidence:
$dom_diff_frame

Criteria:
$criteria_info_block

$grounding_rules

Return JSON as {"analyses": [...]}, with exactly one entry per criterion in
the same order. Every entry must contain:
- criterion_idx: integer
- evidence_status: one of "supported", "contradicted", "partial", "unknown"
- screenshot_evidence: non-empty string describing only explicit diff records
- criterion_analysis: non-empty string explaining the decision
- discrepancies: non-empty string (use "None explicitly shown" when applicable)
- environment_issues_confirmed: boolean

For conditional criteria also include condition_verification as a boolean.
If the diff cannot establish the criterion, choose unknown. Do not convert
unknown into failure and do not claim that an unchanged final state was seen.
""".strip()
)
