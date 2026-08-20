"""Prompts for raw DOM-diff evidence accessed only through grep/read tools."""

from string import Template


RAW_DOM_DIFF_TOOL_GROUNDING_RULES = """
GROUNDING RULES FOR RAW DOM-DIFF TOOL EVIDENCE:
- Raw dom_diffN.txt files are the only page-observation evidence.
- The initial prompt contains file handles, not file contents. Use
  grep_evidence and read_file before judging.
- Added, removed, changed, viewport-entered, and viewport-exited evidence have
  different direction/scope and never cancel one another.
- A grep miss is not proof that a fact is absent. Search relevant synonyms,
  exact phrases, numbers, dates, units, labels, semantic states, navigation,
  status, and coverage/truncation warnings.
- If available evidence or source coverage is insufficient, use unknown.
- Action history and the final answer are context/claims, not page-state proof.
- FRAME is the zero-based citation identifier. STEP is one-based chronology.
  Never return STEP values as evidence_idx/evidence_indices.
- Cite only evidence returned by a successful tool call. Never infer facts from
  general knowledge.
""".strip()


RAW_GREP_RELEVANCE_PROMPT = Template(
    """
Rank every raw action-aligned DOM-diff FRAME against every rubric criterion.

Task:
$task_definition
$init_url_context

Evidence file manifest (metadata only; no DOM content):
$file_manifest

Rubric criteria:
$rubric_criteria

$grounding_rules

Use the tools to inspect evidence. Search all criteria efficiently and inspect
context around relevant matches. You must make at least one successful evidence
tool call before returning the matrix.

Return JSON as {"frames": [...]}. Include exactly one object for every FRAME in
ascending order. Each object must contain evidence_idx equal to the displayed
zero-based FRAME value and one integer score from 0 to 10 for every criterion
using keys criterion_0, criterion_1, and so on. Do not omit low-relevance
frames and never use STEP as evidence_idx.
""".strip()
)


RAW_GREP_ANALYSIS_PROMPT = Template(
    """
Analyze raw DOM-diff evidence against every listed rubric criterion. The files
are not pasted here; retrieve only needed source ranges using the tools.

Task:
$task_definition
$init_url_context

Action history (context only; not browser-state evidence):
$action_history

Agent final answer (claim to verify; not evidence):
$agent_predicted_output

Selected evidence file manifest (metadata only):
$file_manifest

ALLOWED FRAMES
$allowed_frames

Criteria:
$criteria_info_block

$grounding_rules

For each criterion, evidence_indices must be a subset of that criterion's
displayed ALLOWED FRAMES and must use FRAME values only, never STEP values.
Cite only FRAME values whose source text was returned by a successful tool call
in this analysis session.

Return JSON as {"analyses": [...]}, with exactly one entry for every criterion
in ascending criterion_idx order. Every entry must contain:
- criterion_idx: integer
- evidence_status: one of "supported", "contradicted", "partial", "unknown"
- evidence_text: concise non-empty description with FRAME and source line ranges
- criterion_analysis: concise non-empty explanation
- discrepancies: non-empty string; use "None explicitly shown" when applicable
- environment_issues_confirmed: boolean
- evidence_indices: array containing only allowed zero-based FRAME values

For conditional criteria also include condition_verification as a boolean.
Do not turn not-observed evidence into proof of absence.
""".strip()
)
