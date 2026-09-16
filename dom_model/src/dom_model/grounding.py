"""General evidence-grounding contracts for DOM-model evaluation prompts."""

GROUNDING_POLICY_VERSION = "dom_model_evidence_grounding_v1"
EVIDENCE_STATUSES = frozenset({"SUPPORTED", "PARTIAL", "CONTRADICTED", "UNKNOWN"})


RELEVANCE_GROUNDING_POLICY = """
DOM relevance rule: judge only explicit state content. Do not infer relevance from the answer,
actions, outside knowledge, or plausibility. Absent, omitted, truncated, and pixel-only facts are
unproven.
""".strip()


EVIDENCE_ANALYSIS_GROUNDING_POLICY = """
DOM evidence rule:
- Start criterion_analysis with exactly one status:
  EVIDENCE_STATUS: SUPPORTED
  EVIDENCE_STATUS: PARTIAL
  EVIDENCE_STATUS: CONTRADICTED
  EVIDENCE_STATUS: UNKNOWN
- SUPPORTED means all material browser facts are explicit; PARTIAL means some are; CONTRADICTED means
  the state conflicts; UNKNOWN means relevant coverage is absent, omitted, truncated, or pixel-only.
- Cite DOM_MODEL_STATE_INDEX and exact text, labels, values, controls, URL, dialogs, or errors.
- Actions prove actions and the final answer proves delivery; neither proves browser facts. The answer
  need not appear in the DOM, but its browser-derived claims require DOM support.
- Never fill gaps with outside knowledge or plausibility: not contradicted is not supported. Absence
  proves nonexistence only when the relevant scope is represented and was explored.
""".strip()


REALITY_CHECK_GROUNDING_POLICY = """
DOM rule: use only explicit state evidence. PARTIAL or UNKNOWN cannot establish facts, limitations,
or nonexistence. Never replace missing support with plausibility or outside knowledge.
""".strip()


RESCORING_GROUNDING_POLICY = """
DOM rule: browser facts require explicit DOM support for full credit. Actions prove actions; answers
prove delivery; neither proves browser state. SUPPORTED can justify credit; PARTIAL supports only
its represented portion; UNKNOWN gives no confirmation; CONTRADICTED warrants a proportional
deduction. Do not fill gaps with outside knowledge,
plausibility, or "not contradicted." Missing or pixel-only evidence is unproven, not automatically
false. Do not penalize an answer merely because its text is not rendered.
""".strip()


def validate_grounded_analysis(analysis: dict) -> str:
    """Validate the DOM-only additions to Microsoft's evidence-analysis schema."""
    first_line = analysis["criterion_analysis"].splitlines()[0].strip()
    prefix = "EVIDENCE_STATUS: "
    if not first_line.startswith(prefix):
        raise ValueError("criterion_analysis must start with EVIDENCE_STATUS")
    status = first_line.removeprefix(prefix)
    if status not in EVIDENCE_STATUSES:
        raise ValueError(f"Invalid DOM evidence status: {status!r}")
    if "DOM_MODEL_STATE_INDEX" not in analysis["dom_model_evidence"]:
        raise ValueError("DOM-model evidence must cite DOM_MODEL_STATE_INDEX")
    return status
