from w8bench.verifier.dom_model.evidence import DomModelRubricAgent
from w8bench.verifier.dom_model.rubric_agent import MMRubricAgent


EVIDENCE_HOOKS = {
    "_load_evidence",
    "_score_evidence_relevance",
    "_analyze_evidence",
    "_analyze_evidence_batched",
}


def test_only_evidence_hooks_override_screenshot_pipeline():
    overrides = {name for name in DomModelRubricAgent.__dict__ if name.startswith("_") and callable(DomModelRubricAgent.__dict__[name])}
    assert "_generate_reply" not in overrides
    assert EVIDENCE_HOOKS <= overrides
    for method in (
        "_disambiguate_conditional_criteria", "_rubric_reality_check",
        "_rescore_rubric", "_detect_unsolicited_side_effects",
        "_outcome_verification", "_first_point_of_failure_analysis",
        "_classify_task_with_trajectory", "_classify_task", "_run_steps_6_7_single_instance",
    ):
        assert getattr(DomModelRubricAgent, method) is getattr(MMRubricAgent, method)
