"""Prompts used only by the refined DOM-diff text verifier."""

from string import Template


DOM_DIFF_TEXT_GROUNDING_RULES = """
GROUNDING RULES FOR REFINED DOM-DIFF TEXT EVIDENCE:
- The evidence is a deterministic compact projection of recorder-produced,
  action-aligned dom_diffN.txt files.
- Added, removed, changed, viewport-entered, and viewport-exited records are
  distinct operations. Never cancel or equate their directions.
- Operation markers are compact but exact: +DOC/-DOC are document text
  additions/removals; +VIEW/-VIEW are viewport entry/exit; +EL/-EL are element
  additions/removals; ~EL is a state/attribute change; NAV is navigation.
- Document additions/removals are not equivalent to viewport entry/exit.
- State transitions mean only their explicit before and after values.
- [record-or-chunk-id] is a stable audit join key and adds no semantic fact.
- On multi-step evidence, @1,3 means observed at steps 1 and 3 only; it does
  not prove continuous presence between those steps. A one-step evidence line
  inherits the sole STEP header and therefore omits redundant @step notation.
- In analysis evidence, C[0,2] is the complete criterion assignment for that
  line. A criterion may use only lines whose C[...] tag contains its index.
- Source refs, hashes, paths, occurrence details, and merge mappings remain in
  audit receipts and are intentionally absent from model-facing lines.
- COVERAGE warnings describe recorder limits or true model-context omissions.
  If missing coverage prevents a safe conclusion, use unknown.
- "Not observed" is not proof that a fact is absent from the website or page.
- Action history and the agent final answer are claims/context, not browser-state
  evidence.
- Use contradicted only when an explicit retained record conflicts with a claim.
- Do not infer structured relationships or unsupported facts that the source did
  not explicitly represent. The judge, not the parser, performs interpretation.
""".strip()


TEXT_BATCHED_RELEVANCE_PROMPT = Template(
    """
Rank every action-aligned refined DOM-diff text frame against every rubric
criterion.

Task:
$task_definition
$init_url_context

Retrieved compact text evidence across all steps:
$text_frames

Rubric criteria:
$rubric_criteria

$grounding_rules

Return JSON as {"frames": [...]}. Include exactly one object for every STEP in
ascending order. Each object must contain evidence_idx (zero-based STEP order)
and one integer score from 0 to 10 for every criterion using keys criterion_0,
criterion_1, and so on. Do not omit low-relevance steps. Relevance means an
explicit retained record at that step could support or contradict a criterion.
""".strip()
)


TEXT_PACKED_ANALYSIS_PROMPT = Template(
    """
Analyze packed refined DOM-diff text evidence against every listed rubric
criterion. The evidence library is sent once. Every evidence line begins with
a C[...] tag identifying exactly which criteria may use that line.

Task:
$task_definition
$init_url_context

Action history (context only; not browser-state evidence):
$action_history

Agent final answer (claim to verify; not evidence):
$agent_predicted_output

Packed refined DOM-diff text evidence:
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

For conditional criteria also include condition_verification as a boolean. Use
only evidence lines assigned to the criterion's index and cite only assigned
frame indices. Do not turn not-observed evidence into proof of absence. Keep
text fields brief.
""".strip()
)
