"""Prompts used only by the compact DOM-diff-summary verifier."""

from string import Template


DOM_DIFF_SUMMARY_GROUNDING_RULES = """
GROUNDING RULES FOR DOM-DIFF-SUMMARY EVIDENCE:
- The evidence is a deterministic compact projection of recorder-produced
  action-aligned DOM-diff summaries.
- Added, removed, and changed records are distinct. Preserve their direction.
- Repeated step numbers mean the same explicit record was observed in multiple
  summaries; they do not prove continuous visibility between those steps.
- OMISSION receipts describe geometry removal, deduplication, source capture
  limits, and token-budget omissions. Geometry-only changes are not semantic
  browser-state evidence.
- "not observed" is not proof that a fact is absent from the website or page.
- If source_truncated=true or relevant records were omitted by budget, use
  unknown when coverage prevents a safe conclusion.
- Action history and the agent final answer are claims/context, not browser-state
  evidence.
- Use contradicted only when an explicit retained record conflicts with a claim.
- Never infer unsupported facts from general knowledge.
""".strip()


SUMMARY_FRAME_RELEVANCE_PROMPT = Template(
    """
Rank one compact action-aligned DOM-diff-summary frame for rubric evaluation.

Task:
$task_definition
$init_url_context

Compact summary evidence:
$summary_frame

Rubric criteria:
$rubric_criteria

$grounding_rules

Return a JSON object with exactly one integer score from 0 to 10 for every
criterion, using keys criterion_0, criterion_1, and so on. Relevance means an
explicit retained record could support or contradict that criterion.
""".strip()
)


SUMMARY_BATCHED_RELEVANCE_PROMPT = Template(
    """
Rank every compact action-aligned DOM-diff-summary frame against every rubric
criterion.

Task:
$task_definition
$init_url_context

All compact summary frames:
$summary_frames

Rubric criteria:
$rubric_criteria

$grounding_rules

Return JSON as {"frames": [...]}. Include exactly one object for every frame in
the evidence, in ascending order. Each object must contain evidence_idx and one
integer score from 0 to 10 for every criterion using keys criterion_0,
criterion_1, and so on. Do not omit low-relevance frames.
""".strip()
)


SUMMARY_FRAME_ANALYSIS_PROMPT = Template(
    """
Analyze one compact action-aligned DOM-diff-summary frame against each listed
rubric criterion.

Task:
$task_definition
$init_url_context

Action history (context only; not browser-state evidence):
$action_history

Agent final answer (claim to verify; not evidence):
$agent_predicted_output

Compact summary evidence:
$summary_frame

Criteria:
$criteria_info_block

$grounding_rules

Return JSON as {"analyses": [...]}, with exactly one entry per criterion in the
same order. Every entry must contain:
- criterion_idx: integer
- evidence_status: one of "supported", "contradicted", "partial", "unknown"
- evidence_text: concise, non-empty description of explicit retained records
- criterion_analysis: concise, non-empty explanation
- discrepancies: non-empty string; use "None explicitly shown" when applicable
- environment_issues_confirmed: boolean

For conditional criteria also include condition_verification as a boolean. If
coverage cannot establish the criterion, choose unknown. Keep each text field
brief and do not repeat the full evidence block.
""".strip()
)


SUMMARY_PACKED_ANALYSIS_PROMPT = Template(
    """
Analyze packed compact DOM-diff-summary evidence against every listed rubric
criterion. The evidence library is sent once. The assignment section identifies
which frame indices and steps apply to each criterion.

Task:
$task_definition
$init_url_context

Action history (context only; not browser-state evidence):
$action_history

Agent final answer (claim to verify; not evidence):
$agent_predicted_output

Packed compact evidence:
$packed_evidence

Criteria:
$criteria_info_block

$grounding_rules

Return JSON as {"analyses": [...]}, with exactly one entry for every criterion
in ascending criterion_idx order. Every entry must contain:
- criterion_idx: integer
- evidence_status: one of "supported", "contradicted", "partial", "unknown"
- evidence_text: concise, non-empty description with applicable step numbers
- criterion_analysis: concise, non-empty explanation
- discrepancies: non-empty string; use "None explicitly shown" when applicable
- environment_issues_confirmed: boolean
- evidence_indices: array of applicable zero-based frame indices

For conditional criteria also include condition_verification as a boolean. Do
not turn not-observed evidence into proof of absence. Keep text fields brief.
""".strip()
)

