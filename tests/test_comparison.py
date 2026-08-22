from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.common import CANONICAL_SETTINGS
from scripts.compare_results import compare


def _metrics(mode: str, *, tokens: int = 100) -> dict:
    prompt = tokens - 10
    return {
        "task_id": "task-internal",
        "evidence_mode": mode,
        "frozen_rubric_sha256": "abc123",
        "judge_models": {
            "judge": "gpt-5.2",
            "action_and_validity_judge": "o4-mini",
        },
        "pipeline_settings": dict(CANONICAL_SETTINGS),
        "result": {
            "process_score": 0.5,
            "total_earned_points": 1,
            "total_max_points": 2,
            "rubric_is_success": False,
            "outcome_success": False,
        },
        "criteria": [
            {
                "criterion": "Find the value",
                "action_only_points": 0,
                "final_points": 1,
                "max_points": 2,
            }
        ],
        "llm_calls": {
            "gpt-5.2": 1,
            "o4-mini": 1,
            "total": 2,
            "api_attempts": 2,
            "retries": 0,
            "rubric_generation_calls": 0,
        },
        "token_usage": {
            "combined": {
                "prompt_tokens": prompt,
                "completion_tokens": 10,
                "reasoning_tokens": 4,
                "total_tokens": tokens,
            }
        },
        "score_artifact": f"/{mode}/result.json",
    }


def test_comparison_reports_token_delta_and_control_parity() -> None:
    screenshot = _metrics("screenshot", tokens=100)
    dom = _metrics("dom_diff_text", tokens=70)
    receipt, markdown = compare(screenshot, dom)
    assert receipt["token_delta_dom_minus_screenshot"] == -30
    assert receipt["token_change_percent"] == -30
    assert "-30 (-30.00%)" in markdown
    assert receipt["criterion_denominator"] == 2


def test_comparison_rejects_rubric_hash_drift() -> None:
    screenshot = _metrics("screenshot")
    dom = _metrics("dom_diff_text")
    dom["frozen_rubric_sha256"] = "different"
    with pytest.raises(ValueError, match="frozen_rubric_sha256"):
        compare(screenshot, dom)


def test_comparison_rejects_scoring_time_rubric_generation() -> None:
    screenshot = _metrics("screenshot")
    dom = _metrics("dom_diff_text")
    dom["llm_calls"]["rubric_generation_calls"] = 1
    with pytest.raises(ValueError, match="generated a rubric"):
        compare(screenshot, dom)


def test_comparison_reports_action_variance_separately() -> None:
    screenshot = _metrics("screenshot")
    dom = deepcopy(_metrics("dom_diff_text"))
    dom["criteria"][0]["action_only_points"] = 1
    receipt, _ = compare(screenshot, dom)
    assert receipt["action_only_variance"] is True
    assert receipt["criterion_allocation_differs"] is False
