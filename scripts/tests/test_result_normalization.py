from copy import deepcopy

import pytest

from scripts.compare_results import compare
from scripts.common import CANONICAL_SETTINGS


def _run(mode):
    return {
        "task_id": "task",
        "evidence_mode": mode,
        "frozen_rubric_sha256": "abc",
        "phase_a_generation_metrics": "/same/metrics.json",
        "judge_models": {"judge": "gpt-5.2", "action_and_validity_judge": "o4-mini"},
        "pipeline_settings": dict(CANONICAL_SETTINGS),
        "result": {"process_score": 1.0, "total_earned_points": 10.0, "total_max_points": 10.0, "outcome_success": True},
        "criteria": [
            {"criterion": "a", "action_only_points": 5.0, "final_points": 7.0, "max_points": 7.0},
            {"criterion": "b", "action_only_points": 2.0, "final_points": 3.0, "max_points": 3.0},
        ],
        "llm_calls": {"total": 2, "api_attempts": 3, "retries": 1, "rubric_generation_calls": 0},
        "token_usage": {"combined": {"prompt_tokens": 10, "completion_tokens": 5, "reasoning_tokens": 2, "total_tokens": 15}},
    }


def test_comparison_accepts_controlled_matching_receipts():
    receipt, markdown = compare(_run("screenshot"), _run("dom_model"))
    assert receipt["status"] == "pass"
    assert receipt["rubric_generation_calls_during_scoring"] == {"screenshot": 0, "dom_model": 0}
    assert "DOM-model" in markdown


@pytest.mark.parametrize("drift", ["hash", "order", "maximum", "generation"])
def test_comparison_rejects_frozen_contract_drift(drift):
    screenshot = _run("screenshot")
    dom = deepcopy(_run("dom_model"))
    if drift == "hash":
        dom["frozen_rubric_sha256"] = "different"
    elif drift == "order":
        dom["criteria"].reverse()
    elif drift == "maximum":
        dom["criteria"][0]["max_points"] = 6.0
        dom["criteria"][1]["max_points"] = 4.0
    else:
        dom["llm_calls"]["rubric_generation_calls"] = 1
    with pytest.raises(ValueError):
        compare(screenshot, dom)

