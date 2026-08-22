from __future__ import annotations

import json
from pathlib import Path

from scripts.common import write_json
from scripts.results import normalize_dom_text, normalize_screenshot


def _rubric() -> dict:
    return {
        "task_id": "task-internal",
        "precomputed_rubric": {
            "items": [
                {
                    "criterion": "Find the value",
                    "description": "Report the explicit value.",
                    "max_points": 2,
                    "justification": "",
                    "earned_points": "",
                }
            ]
        },
    }


def test_normalize_screenshot_preserves_criteria_calls_and_tokens(tmp_path: Path) -> None:
    rubric = write_json(tmp_path / "rubric.json", _rubric())
    result = {
        "task_id": "task-internal",
        "rubric_score": 0.5,
        "rubric_total_max_points": 2,
        "rubric_total_earned_points": 1,
        "rubric_is_success": False,
        "outcome": {"output_success": False},
        "preflight": {"actions": 1, "screenshots": 2},
        "token_usage": {
            "judge": {
                "prompt_tokens": 50,
                "completion_tokens": 5,
                "reasoning_tokens": 0,
                "total_tokens": 55,
            },
            "action_judge": {
                "prompt_tokens": 20,
                "completion_tokens": 3,
                "reasoning_tokens": 1,
                "total_tokens": 23,
            },
        },
        "call_metrics": {
            "judge": {"logical_calls": 2, "api_attempts": 2, "retries": 0},
            "action_judge": {"logical_calls": 1, "api_attempts": 1, "retries": 0},
        },
        "intermediate_mm_rubric_steps": {
            "step6_rescoring_summary": [
                {
                    "criterion": "Find the value",
                    "earned_points": 0,
                    "post_image_earned_points": 1,
                    "max_points": 2,
                }
            ],
            "step9_first_point_of_failure": {
                "has_failure": True,
                "first_failure_step": 1,
            },
            "step10_task_verification": {"is_invalid": False},
        },
        "duration_sec": 1.5,
    }
    result_path = write_json(tmp_path / "screenshot-result.json", result)
    metrics = normalize_screenshot(
        result_path,
        input_task=tmp_path,
        rubric_file=rubric,
        run_log=tmp_path / "run.log",
    )
    assert metrics["token_usage"]["combined"]["total_tokens"] == 78
    assert metrics["llm_calls"]["total"] == 3
    assert metrics["criteria"][0]["final_points"] == 1


def test_normalize_dom_preserves_evidence_receipts(tmp_path: Path) -> None:
    rubric = write_json(tmp_path / "rubric.json", _rubric())
    write_json(
        tmp_path / "task_data.json",
        {"task_id": "task-internal", "confirmed_task": "Find the value"},
    )
    from scripts.common import load_canonical_rubric

    digest = load_canonical_rubric(rubric).sha256
    score = {
        "frozen_rubric_sha256": digest,
        "capture_coverage": {"actions": 1, "text_frames": 1},
        "token_usage": {
            "judge": {
                "prompt_tokens": 40,
                "completion_tokens": 4,
                "reasoning_tokens": 0,
                "total_tokens": 44,
            },
            "action_rubric": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "reasoning_tokens": 1,
                "total_tokens": 12,
            },
            "total": {
                "prompt_tokens": 50,
                "completion_tokens": 6,
                "reasoning_tokens": 1,
                "total_tokens": 56,
            },
        },
        "call_metrics": {
            "judge": {"logical_calls": 2, "api_attempts": 2, "retries": 0},
            "action_rubric": {"logical_calls": 1, "api_attempts": 1, "retries": 0},
            "total": {"logical_calls": 3, "api_attempts": 3, "retries": 0},
        },
        "text_runtime_metrics": {"compact_estimated_tokens": 25},
        "verifier_config": {
            "text_frame_starting_tokens": 1500,
            "text_trajectory_starting_tokens": 16000,
            "text_analysis_starting_tokens": 24000,
            "text_allow_budget_expansion": True,
        },
        "result": {
            "rubric": {
                "score": 0.5,
                "is_success": False,
                "total_max_points": 2,
                "total_earned_points": 1,
                "items": [
                    {
                        "criterion": "Find the value",
                        "earned_points": 0,
                        "post_evidence_earned_points": 1,
                        "max_points": 2,
                    }
                ],
            },
            "outcome": {"success": False},
            "error_taxonomy": {
                "first_point_of_failure": {
                    "has_failure": True,
                    "first_failure_step": 1,
                },
                "task_verification": {"is_invalid": False},
            },
        },
    }
    score_path = write_json(tmp_path / "dom-score.json", score)
    report = tmp_path / "report.jsonl"
    report.write_text(
        json.dumps(
            {
                "task_id": "task-folder-alias",
                "status": "ok",
                "score_path": str(score_path),
                "duration_sec": 2.5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metrics = normalize_dom_text(
        report,
        input_task=tmp_path,
        rubric_file=rubric,
        run_log=tmp_path / "run.log",
    )
    assert metrics["token_usage"]["combined"]["total_tokens"] == 56
    assert metrics["criteria"][0]["final_points"] == 1
    assert metrics["evidence_metrics"]["compact_estimated_tokens"] == 25
    assert metrics["task_id"] == "task-internal"
