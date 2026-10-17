from w8bench.dom_model.dom_model_agent import DomModelRubricAgent
from w8bench.dom_model.rubric_agent import MMRubricAgent


EVIDENCE_HOOKS = {
    "_load_dom_states",
    "_score_dom_state_criterion_relevance",
    "_analyze_dom_evidence",
    "_analyze_dom_evidence_batched",
}


def test_only_evidence_hooks_override_screenshot_pipeline():
    overrides = {name for name in DomModelRubricAgent.__dict__ if name.startswith("_") and callable(DomModelRubricAgent.__dict__[name])}
    assert "_generate_reply" not in overrides
    assert EVIDENCE_HOOKS <= overrides
    for method in (
        "_disambiguate_conditional_criteria", "_rubric_reality_check",
        "_rescore_rubric_with_dom_evidence", "_detect_unsolicited_side_effects",
        "_outcome_verification", "_first_point_of_failure_analysis",
        "_classify_task_with_trajectory", "_classify_task", "_compute_final_scores",
    ):
        assert getattr(DomModelRubricAgent, method) is getattr(MMRubricAgent, method)
