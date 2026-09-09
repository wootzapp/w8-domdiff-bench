"""Normalize Microsoft screenshot and DOM-model result artifacts identically."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    CANONICAL_ACTION_MODEL,
    CANONICAL_JUDGE_MODEL,
    CANONICAL_SETTINGS,
    load_canonical_rubric,
    load_json,
    sum_call_metrics,
    sum_usage,
)


def _criteria(items: list[dict[str, Any]], frozen_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(items) != len(frozen_items):
        raise ValueError("Result lacks complete criterion rescoring details")
    rows: list[dict[str, Any]] = []
    for index, (item, frozen) in enumerate(zip(items, frozen_items)):
        if item.get("criterion") != frozen["criterion"]:
            raise ValueError(f"Criterion order/name drift at index {index}")
        if float(item.get("max_points", 0)) != float(frozen["max_points"]):
            raise ValueError(f"Criterion maximum-point drift at index {index}")
        rows.append(
            {
                "criterion": item["criterion"],
                "action_only_points": float(item.get("earned_points", 0) or 0),
                "final_points": float(item.get("post_image_earned_points", item.get("earned_points", 0)) or 0),
                "max_points": float(item["max_points"]),
                "condition": item.get("condition"),
                "is_condition_met": item.get("is_condition_met"),
                "is_applicable": item.get("is_condition_met") is not False,
                "final_justification": item.get("post_image_justification", item.get("justification", "")),
                "penalty": bool(item.get("penalty", False)),
            }
        )
    return rows


def _normalize(
    result_path: str | Path,
    *,
    mode: str,
    input_task: str | Path,
    rubric_file: str | Path,
    generation_metrics: str | Path,
    run_log: str | Path,
) -> dict[str, Any]:
    source = Path(result_path).resolve(strict=True)
    raw = load_json(source)
    if not isinstance(raw, dict):
        raise ValueError(f"Verifier result must be an object: {source}")
    task = str(raw.get("task_id") or "")
    frozen = load_canonical_rubric(rubric_file, expected_task_id=task)
    raw_hash = raw.get("rubric_sha256") or raw.get("frozen_rubric_sha256")
    if raw_hash != frozen.sha256:
        raise ValueError(f"{mode} result rubric hash differs from canonical rubric")
    if int(raw.get("rubric_generation_calls", 0) or 0) != 0:
        raise ValueError(f"{mode} scoring artifact reports rubric generation")
    intermediate = raw.get("intermediate_mm_rubric_steps") or {}
    criterion_rows = intermediate.get("step6_rescoring_summary") or []
    criteria = _criteria(criterion_rows, frozen.rubric["items"])
    frozen_denominator = sum(item["max_points"] for item in criteria)
    effective_denominator = sum(
        item["max_points"] for item in criteria if item["is_applicable"]
    )
    result_denominator = float(raw.get("rubric_total_max_points", 0))
    declared_frozen_denominator = float(
        raw.get("criterion_denominator", frozen.denominator)
    )
    if (
        frozen_denominator != frozen.denominator
        or declared_frozen_denominator != frozen.denominator
        or result_denominator != effective_denominator
    ):
        raise ValueError(f"{mode} criterion denominator drift")
    usage_judge = raw.get("token_usage", {}).get("judge", {})
    usage_action = raw.get("token_usage", {}).get("action_judge", {})
    calls_judge = raw.get("call_metrics", {}).get("judge", {})
    calls_action = raw.get("call_metrics", {}).get("action_judge", {})
    combined_usage = sum_usage(usage_judge, usage_action)
    combined_calls = sum_call_metrics(calls_judge, calls_action)
    outcome = raw.get("outcome") or {}
    failure = intermediate.get("step9_first_point_of_failure") or {}
    return {
        "task_id": task,
        "evidence_mode": mode,
        "input_task": str(Path(input_task).resolve()),
        "frozen_rubric_path": str(frozen.path),
        "frozen_rubric_sha256": frozen.sha256,
        "phase_a_generation_metrics": str(Path(generation_metrics).resolve(strict=True)),
        "judge_models": {
            "judge": CANONICAL_JUDGE_MODEL,
            "action_and_validity_judge": CANONICAL_ACTION_MODEL,
        },
        "pipeline_settings": dict(CANONICAL_SETTINGS),
        "trajectory": raw.get("preflight", {}),
        "result": {
            "process_score": float(raw.get("rubric_score", 0)),
            "total_earned_points": float(raw.get("rubric_total_earned_points", 0)),
            "total_max_points": result_denominator,
            "rubric_is_success": bool(raw.get("rubric_is_success")),
            "outcome_success": outcome.get("output_success"),
            "has_failure": failure.get("has_failure"),
            "first_failure_step": failure.get("first_failure_step"),
            "is_ambiguous": failure.get("is_ambiguous", False),
            "ambiguity_codes": failure.get("ambiguity_codes", []),
            "is_invalid": (intermediate.get("step10_task_verification") or {}).get("is_invalid", False),
            "duration_seconds": raw.get("duration_sec", 0),
        },
        "criteria": criteria,
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
        "evidence_metrics": raw.get("evidence_audit", {}) if mode == "dom_model" else {},
        "score_artifact": str(source),
        "raw_instrumentation": str(source),
        "run_log": str(Path(run_log).resolve()),
    }


def normalize_screenshot(result_path: str | Path, **kwargs: Any) -> dict[str, Any]:
    return _normalize(result_path, mode="screenshot", **kwargs)


def normalize_dom_model(result_path: str | Path, **kwargs: Any) -> dict[str, Any]:
    return _normalize(result_path, mode="dom_model", **kwargs)

