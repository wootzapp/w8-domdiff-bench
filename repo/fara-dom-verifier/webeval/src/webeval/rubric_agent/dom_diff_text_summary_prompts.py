"""Summary-S3 prompts for dense projections of refined DOM-diff text."""

from string import Template


DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES = """
GROUNDING RULES FOR COMPACT REFINED DOM-DIFF TEXT EVIDENCE:
- Evidence is a deterministic, action-aligned projection of recorder-produced
  dom_diffN.txt files. Original text files remain authoritative and immutable.
- +DOC/-DOC mean document text added/removed. +VIEW/-VIEW mean text entering
  or exiting the viewport. These operations are distinct and never cancel.
- +ELEMENT/-ELEMENT mean semantic elements added/removed. ~ELEMENT means an
  explicit semantic field or state transition.
- FRAME is the zero-based citation identifier. STEP is the one-based action
  chronology. evidence_idx and evidence_indices must use FRAME values only.
- OMISSION receipts report deterministic deduplication, field clipping,
  source coverage warnings, and whole-record budget omission.
- Not observed is not proof of absence. If source or budget omissions prevent
  a safe conclusion, use unknown.
- Action history and final answer are context or claims, not page-state proof.
- Use contradicted only when retained evidence explicitly conflicts with a
  claim. Never infer unsupported facts from general knowledge.
""".strip()


TEXT_SUMMARY_BATCHED_RELEVANCE_PROMPT = Template(
    """
Rank every compact action-aligned refined DOM-diff text FRAME against every
rubric criterion.

Task:
$task_definition
$init_url_context

All compact text frames:
$text_summary_frames

Rubric criteria:
$rubric_criteria

$grounding_rules

Return JSON as {"frames": [...]}. Include exactly one object for every FRAME
in ascending order. Each object must contain evidence_idx equal to the
displayed zero-based FRAME value and one integer score from 0 to 10 for every
criterion using keys criterion_0, criterion_1, and so on. Never use STEP as
evidence_idx and do not omit low-relevance frames.
""".strip()
)


TEXT_SUMMARY_PACKED_ANALYSIS_PROMPT = Template(
    """
Analyze packed compact refined DOM-diff text evidence against every listed
rubric criterion. The evidence library is sent once. CRITERION EVIDENCE
ASSIGNMENTS identifies which FRAME values and chronological STEP values apply
to each criterion.

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
- evidence_text: concise non-empty description with applicable step numbers
- criterion_analysis: concise non-empty explanation
- discrepancies: non-empty string; use "None explicitly shown" when applicable
- environment_issues_confirmed: boolean
- evidence_indices: array containing only zero-based FRAME values assigned to
  that criterion; never return STEP values

For conditional criteria also include condition_verification as a boolean.
Do not turn not-observed evidence into proof of absence. Keep text fields brief.
""".strip()
)
