from pathlib import Path

import pytest

from dom_model.evidence_backend import base_audit, batched_prompt, criterion_prompt, relevance_prompt
from dom_model.grounding import (
    EVIDENCE_ANALYSIS_GROUNDING_POLICY,
    GROUNDING_POLICY_VERSION,
    REALITY_CHECK_GROUNDING_POLICY,
    RELEVANCE_GROUNDING_POLICY,
    RESCORING_GROUNDING_POLICY,
    validate_grounded_analysis,
)
from dom_model.prompts import (
    MM_CRITERION_RESCORING_PROMPT,
    MM_RUBRIC_RESCORING_PROMPT,
    RUBRIC_REALITY_CHECK_PROMPT,
)
from dom_model.schemas import DomModelState


def _state() -> DomModelState:
    return DomModelState(
        index=1,
        path=Path("dom_model1.txt"),
        raw_text="URL: https://example.test\nLabel: Account\nValue: Active\n",
        sha256="0" * 64,
        byte_count=58,
        line_count=3,
        estimated_tokens=15,
        url="https://example.test",
        title="Example",
    )


def test_analysis_prompts_require_status_and_state_provenance():
    state = _state()
    single = criterion_prompt(
        task="Report the account value",
        init_url_context="",
        action_history="navigate",
        predicted_output="Active",
        criterion_info="Criterion 0",
        conditional_check="",
        conditional_output="",
        state=state,
        action_count=1,
    )
    batched = batched_prompt(
        task="Report the account value",
        init_url_context="",
        action_history="navigate",
        predicted_output="Active",
        criteria_info="Criterion 0",
        state=state,
        action_count=1,
    )
    for prompt in (single, batched):
        for status in ("SUPPORTED", "PARTIAL", "CONTRADICTED", "UNKNOWN"):
            assert f"EVIDENCE_STATUS: {status}" in prompt
        assert "DOM_MODEL_STATE_INDEX" in prompt
        assert "outside knowledge" in prompt
        assert "not contradicted is not supported" in prompt
        assert "browser-derived claims require DOM support" in prompt


def test_relevance_cannot_be_invented_from_answer_or_outside_knowledge():
    prompt = relevance_prompt(
        task="Report the account value",
        init_url_context="",
        criteria_text="0. Account value",
        state=_state(),
        action_count=1,
    )
    assert "judge only explicit state content" in prompt
    assert "outside knowledge" in prompt
    assert "Absent, omitted, truncated, and pixel-only facts" in prompt


def test_downstream_dom_prompts_preserve_unknown_as_unproven():
    for prompt in (MM_CRITERION_RESCORING_PROMPT, MM_RUBRIC_RESCORING_PROMPT):
        assert "full credit for required browser facts needs explicit DOM support" in prompt
        assert "UNKNOWN gives no confirmation" in prompt
        assert "Actions prove actions" in prompt
        assert "neither proves page facts or resulting state" in prompt
        assert "outside knowledge" in prompt
        assert "text is not rendered" in prompt
    assert "PARTIAL or UNKNOWN cannot establish facts" in RUBRIC_REALITY_CHECK_PROMPT
    assert "Never replace missing support" in RUBRIC_REALITY_CHECK_PROMPT


def test_policy_is_general_and_audited():
    all_policy_text = "\n".join(
        (
            RELEVANCE_GROUNDING_POLICY,
            EVIDENCE_ANALYSIS_GROUNDING_POLICY,
            REALITY_CHECK_GROUNDING_POLICY,
            RESCORING_GROUNDING_POLICY,
        )
    ).lower()
    for task_specific_term in ("task36", "typescript", "pick<", "omit<", "exclude<", "extract<"):
        assert task_specific_term not in all_policy_text
    audit = base_audit([_state()])
    assert audit["grounding_policy_version"] == GROUNDING_POLICY_VERSION
    assert audit["evidence_mode"] == "dom_model"


def test_dom_prompt_overhead_stays_close_to_fixed_microsoft_prompts():
    microsoft_words = {
        "criterion_rescore": 4047,
        "rubric_rescore": 5198,
        "reality_check": 543,
    }
    assert len(MM_CRITERION_RESCORING_PROMPT.split()) <= microsoft_words["criterion_rescore"] * 1.02
    assert len(MM_RUBRIC_RESCORING_PROMPT.split()) <= microsoft_words["rubric_rescore"] * 1.02
    assert len(RUBRIC_REALITY_CHECK_PROMPT.split()) <= microsoft_words["reality_check"] * 1.05
    assert len(EVIDENCE_ANALYSIS_GROUNDING_POLICY.split()) <= 120
    assert len(RESCORING_GROUNDING_POLICY.split()) <= 80
    assert len(REALITY_CHECK_GROUNDING_POLICY.split()) <= 25


@pytest.mark.parametrize("status", ("SUPPORTED", "PARTIAL", "CONTRADICTED", "UNKNOWN"))
def test_all_grounding_statuses_validate(status):
    analysis = {
        "criterion_analysis": f"EVIDENCE_STATUS: {status}\nGrounded explanation.",
        "screenshot_evidence": "DOM_MODEL_STATE_INDEX: 1; Value: Active",
    }
    assert validate_grounded_analysis(analysis) == status


@pytest.mark.parametrize(
    ("criterion_analysis", "screenshot_evidence"),
    (
        ("No status", "DOM_MODEL_STATE_INDEX: 1"),
        ("EVIDENCE_STATUS: PLAUSIBLE", "DOM_MODEL_STATE_INDEX: 1"),
        ("EVIDENCE_STATUS: SUPPORTED", "No state citation"),
    ),
)
def test_malformed_grounding_is_rejected(criterion_analysis, screenshot_evidence):
    with pytest.raises(ValueError):
        validate_grounded_analysis(
            {
                "criterion_analysis": criterion_analysis,
                "screenshot_evidence": screenshot_evidence,
            }
        )
