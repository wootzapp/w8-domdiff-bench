from pathlib import Path

from dom_model.dom_model_agent import DomModelRubricAgent
from dom_model.rubric_agent import MMRubricAgent


EVIDENCE_HOOKS = {
    "_load_screenshots",
    "_score_screenshot_criterion_relevance",
    "_analyze_screenshot_evidence",
    "_analyze_screenshot_evidence_batched",
}


def test_only_evidence_hooks_override_microsoft_pipeline():
    overrides = {name for name in DomModelRubricAgent.__dict__ if name.startswith("_") and callable(DomModelRubricAgent.__dict__[name])}
    assert "_generate_reply" not in overrides
    assert EVIDENCE_HOOKS <= overrides
    for method in (
        "_disambiguate_conditional_criteria", "_rubric_reality_check",
        "_rescore_rubric_with_screenshots", "_detect_unsolicited_side_effects",
        "_outcome_verification", "_first_point_of_failure_analysis",
        "_classify_task_with_trajectory", "_classify_task", "_compute_final_scores",
    ):
        assert getattr(DomModelRubricAgent, method) is getattr(MMRubricAgent, method)


def test_no_dom_diff_runtime_imports():
    source_root = Path(__file__).resolve().parents[1] / "src"
    scripts_root = Path(__file__).resolve().parents[1] / "scripts"
    text = "\n".join(path.read_text(encoding="utf-8") for root in (source_root, scripts_root) for path in root.rglob("*.py"))
    assert "import dom_diff" not in text
    assert "from dom_diff" not in text

