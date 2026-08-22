"""Normalize standalone verifier artifacts into one comparison schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    CANONICAL_ACTION_MODEL,
    CANONICAL_JUDGE_MODEL,
    CANONICAL_SETTINGS,
    load_canonical_rubric,
    load_json,
    load_one_task,
    sum_call_metrics,
    sum_usage,
    task_id,
)


def _criteria(items: list[dict[str, Any]], *, mode: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if mode == "screenshot":
            final_points = item.get("post_image_earned_points", item.get("earned_points", 0))
        else:
            final_points = item.get(
                "post_evidence_earned_points",
                item.get("post_image_earned_points", item.get("earned_points", 0)),
            )
        rows.append(
            {
                "criterion": item.get("criterion", ""),
                "action_only_points": item.get("earned_points", 0),
                "final_points": final_points,
                "max_points": item.get("max_points", 0),
                "final_justification": item.get(
                    "post_evidence_justification",
                    item.get("post_image_justification", item.get("justification", "")),
                ),
            }
        )
    return rows


def normalize_screenshot(
    result_path: str | Path,
    *,
    input_task: str | Path,
    rubric_file: str | Path,
    run_log: str | Path,
) -> dict[str, Any]:
    source = Path(result_path).resolve(strict=True)
    raw = load_json(source)
    if not isinstance(raw, dict):
        raise ValueError(f"Microsoft result must be an object: {source}")
    task = raw.get("task_id")
    frozen = load_canonical_rubric(rubric_file, expected_task_id=str(task))
    usage_judge = raw.get("token_usage", {}).get("judge", {})
    usage_action = raw.get("token_usage", {}).get("action_judge", {})
    calls_judge = raw.get("call_metrics", {}).get("judge", {})
    calls_action = raw.get("call_metrics", {}).get("action_judge", {})
    combined_usage = sum_usage(usage_judge, usage_action)
    combined_calls = sum_call_metrics(calls_judge, calls_action)
    intermediate = raw.get("intermediate_mm_rubric_steps") or {}
    criterion_rows = intermediate.get("step6_rescoring_summary") or []
    if not isinstance(criterion_rows, list) or len(criterion_rows) != len(frozen.rubric["items"]):
        raise ValueError("Microsoft result lacks complete criterion rescoring details")
    outcome = raw.get("outcome") or {}
    failure = intermediate.get("step9_first_point_of_failure") or {}
    process_score = float(raw.get("rubric_score", 0))
    total_max = float(raw.get("rubric_total_max_points", 0))
    total_earned = float(raw.get("rubric_total_earned_points", 0))
    return {
        "task_id": task,
        "evidence_mode": "screenshot",
        "input_task": str(Path(input_task).resolve()),
        "frozen_rubric_path": str(frozen.path),
        "frozen_rubric_sha256": frozen.sha256,
        "judge_models": {
            "judge": CANONICAL_JUDGE_MODEL,
            "action_and_validity_judge": CANONICAL_ACTION_MODEL,
        },
        "pipeline_settings": dict(CANONICAL_SETTINGS),
        "trajectory": raw.get("preflight", {}),
        "result": {
            "process_score": process_score,
            "total_earned_points": total_earned,
            "total_max_points": total_max,
            "rubric_is_success": bool(raw.get("rubric_is_success")),
            "outcome_success": outcome.get("output_success"),
            "has_failure": failure.get("has_failure"),
            "first_failure_step": failure.get("first_failure_step"),
            "is_ambiguous": failure.get("is_ambiguous", False),
            "ambiguity_codes": failure.get("ambiguity_codes", []),
            "is_invalid": (
                intermediate.get("step10_task_verification", {}).get("is_invalid", False)
            ),
            "duration_seconds": raw.get("duration_sec", 0),
        },
        "criteria": _criteria(criterion_rows, mode="screenshot"),
        "llm_calls": {
            CANONICAL_JUDGE_MODEL: int(calls_judge.get("logical_calls", 0)),
            CANONICAL_ACTION_MODEL: int(calls_action.get("logical_calls", 0)),
            "total": combined_calls["logical_calls"],
            "api_attempts": combined_calls["api_attempts"],
            "retries": combined_calls["retries"],
            "rubric_generation_calls": 0,
        },
        "token_usage": {
            CANONICAL_JUDGE_MODEL: usage_judge,
            CANONICAL_ACTION_MODEL: usage_action,
            "combined": combined_usage,
        },
        "score_artifact": str(source),
        "raw_instrumentation": str(source),
        "run_log": str(Path(run_log).resolve()),
    }


def _one_report_row(path: Path) -> dict[str, Any]:
    rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one DOM report row in {path}, got {len(rows)}")
    import json

    value = json.loads(rows[0])
    if not isinstance(value, dict) or value.get("status") not in {"ok", "cached"}:
        raise ValueError(f"DOM report does not contain a successful run: {value}")
    return value


def normalize_dom_text(
    report_path: str | Path,
    *,
    input_task: str | Path,
    rubric_file: str | Path,
    run_log: str | Path,
) -> dict[str, Any]:
    report = Path(report_path).resolve(strict=True)
    row = _one_report_row(report)
    source = Path(row["score_path"]).resolve(strict=True)
    raw = load_json(source)
    if not isinstance(raw, dict):
        raise ValueError(f"DOM score must be an object: {source}")
    input_root = Path(input_task).resolve(strict=True)
    task = task_id(load_one_task(input_root / "task_data.json"))
    if not task:
        raise ValueError(f"DOM task data has no internal task ID: {input_root}")
    frozen = load_canonical_rubric(rubric_file, expected_task_id=task)
    if raw.get("frozen_rubric_sha256") != frozen.sha256:
        raise ValueError("DOM score rubric hash differs from the canonical rubric")
    result = raw.get("result") or {}
    rubric_result = result.get("rubric") or {}
    items = rubric_result.get("items") or []
    if not isinstance(items, list) or len(items) != len(frozen.rubric["items"]):
        raise ValueError("DOM result lacks complete criterion rescoring details")
    usage_judge = raw.get("token_usage", {}).get("judge", {})
    usage_action = raw.get("token_usage", {}).get("action_rubric", {})
    combined_usage = raw.get("token_usage", {}).get("total") or sum_usage(usage_judge, usage_action)
    calls_judge = raw.get("call_metrics", {}).get("judge", {})
    calls_action = raw.get("call_metrics", {}).get("action_rubric", {})
    combined_calls = raw.get("call_metrics", {}).get("total") or sum_call_metrics(
        calls_judge, calls_action
    )
    failure = result.get("error_taxonomy", {}).get("first_point_of_failure") or {}
    validity = result.get("error_taxonomy", {}).get("task_verification") or {}
    verifier_config = raw.get("verifier_config") or {}
    settings = dict(CANONICAL_SETTINGS)
    settings.update(
        {
            "text_frame_starting_tokens": verifier_config.get("text_frame_starting_tokens"),
            "text_trajectory_starting_tokens": verifier_config.get(
                "text_trajectory_starting_tokens"
            ),
            "text_analysis_starting_tokens": verifier_config.get("text_analysis_starting_tokens"),
            "text_allow_budget_expansion": verifier_config.get("text_allow_budget_expansion"),
        }
    )
    return {
        "task_id": task,
        "evidence_mode": "dom_diff_text",
        "input_task": str(input_root),
        "frozen_rubric_path": str(frozen.path),
        "frozen_rubric_sha256": frozen.sha256,
        "judge_models": {
            "judge": CANONICAL_JUDGE_MODEL,
            "action_and_validity_judge": CANONICAL_ACTION_MODEL,
        },
        "pipeline_settings": settings,
        "trajectory": raw.get("capture_coverage", {}),
        "result": {
            "process_score": float(rubric_result.get("score", 0)),
            "total_earned_points": float(rubric_result.get("total_earned_points", 0)),
            "total_max_points": float(rubric_result.get("total_max_points", 0)),
            "rubric_is_success": bool(rubric_result.get("is_success")),
            "outcome_success": result.get("outcome", {}).get("success"),
            "has_failure": failure.get("has_failure"),
            "first_failure_step": failure.get("first_failure_step"),
            "is_ambiguous": failure.get("is_ambiguous", False),
            "ambiguity_codes": failure.get("ambiguity_codes", []),
            "is_invalid": validity.get("is_invalid", False),
            "duration_seconds": row.get("duration_sec", 0),
        },
        "criteria": _criteria(items, mode="dom"),
        "llm_calls": {
            CANONICAL_JUDGE_MODEL: int(calls_judge.get("logical_calls", 0)),
            CANONICAL_ACTION_MODEL: int(calls_action.get("logical_calls", 0)),
            "total": int(combined_calls.get("logical_calls", 0)),
            "api_attempts": int(combined_calls.get("api_attempts", 0)),
            "retries": int(combined_calls.get("retries", 0)),
            "rubric_generation_calls": 0,
        },
        "token_usage": {
            CANONICAL_JUDGE_MODEL: usage_judge,
            CANONICAL_ACTION_MODEL: usage_action,
            "combined": combined_usage,
        },
        "evidence_metrics": raw.get("text_runtime_metrics", {}),
        "score_artifact": str(source),
        "raw_instrumentation": str(source),
        "run_log": str(Path(run_log).resolve()),
    }
