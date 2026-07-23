"""Freeze E0 operational artifacts and per-task process/outcome results."""

import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from e0_common import (
    BATCH_REPORT_ROOT,
    CORPUS_MANIFEST_PATH,
    OUTPUT_ROOT,
    PROJECT_ROOT,
    RAW_SCORE_ROOT,
    VALIDATION_PATH,
    ensure_output_dirs,
    read_jsonl,
    write_jsonl,
)

FRESH_STAGES = ("preflight", "batch_10", "remainder")
INFRASTRUCTURE_MARKERS = (
    "timeout",
    "rate limit",
    "ratelimit",
    "apiconnection",
    "connection error",
    "network error",
    "internalserver",
    "service unavailable",
    "temporarily unavailable",
    "interrupted",
)


def report_rows(stage: str) -> list[dict[str, Any]]:
    path = BATCH_REPORT_ROOT / f"{stage}.jsonl"
    if not path.exists():
        raise RuntimeError(f"Missing required fresh report: {path}")
    rows = read_jsonl(path)
    for row in rows:
        row["execution_stage"] = stage
        row["report_source"] = str(path.relative_to(PROJECT_ROOT))
    return rows


def canonical_score_path(task_id: str) -> Path:
    return (
        PROJECT_ROOT
        / "data/materialized/day2/E0_full_uv/traj"
        / task_id
        / "scores/mmrubric_0.8-5-3.json"
    )


def score_details(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    response = json.loads(payload["gpt_response_text"])
    return {
        "top_level_score": payload.get("score"),
        "top_level_success": payload.get("score") == 1,
        "score_process_rubric_is_success": response.get("rubric_is_success"),
        "score_outcome_success": response.get("outcome_success"),
        "success_criterion": response.get("success_criterion"),
    }


def is_infrastructure_failure(row: dict[str, Any]) -> bool:
    text = f"{row.get('error', '')}\n{row.get('traceback', '')}".lower()
    return any(marker in text for marker in INFRASTRUCTURE_MARKERS)


def main() -> None:
    ensure_output_dirs()
    manifest = read_jsonl(CORPUS_MANIFEST_PATH)
    validation = {row["task_id"]: row for row in read_jsonl(VALIDATION_PATH)}
    if len(manifest) != 106 or len(validation) != 106:
        raise RuntimeError("E0 finalization requires exactly 106 manifest and validation rows")

    fresh_rows = [row for stage in FRESH_STAGES for row in report_rows(stage)]
    by_task: dict[str, dict[str, Any]] = {}
    for row in fresh_rows:
        task_id = row["task_id"]
        if task_id in by_task:
            raise RuntimeError(f"Duplicate fresh report task: {task_id}")
        by_task[task_id] = row

    expected_valid = {
        row["task_id"] for row in manifest if row["input_validation_status"] == "valid"
    }
    if set(by_task) != expected_valid:
        missing = sorted(expected_valid - set(by_task))
        extra = sorted(set(by_task) - expected_valid)
        raise RuntimeError(f"Fresh reports do not account for valid corpus; missing={missing}, extra={extra}")

    predictions: list[dict[str, Any]] = []
    successful: list[dict[str, Any]] = []
    infrastructure_failures: list[dict[str, Any]] = []
    input_failures: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for item in manifest:
        task_id = item["task_id"]
        checked = validation[task_id]
        row = by_task.get(task_id)
        if checked["status"] != "valid":
            prediction = {
                "task_id": task_id,
                "status": checked["status"],
                "failure_category": "input",
                "error": checked.get("reason"),
                "rubric_score": None,
                "rubric_is_success": None,
                "outcome_success": None,
                "top_level_success": None,
                "first_failure_step": None,
                "is_ambiguous": None,
                "is_invalid": None,
                "action_count": item["action_count"],
                "screenshot_count": item["screenshot_count"],
                "duration_sec": None,
                "score_path": None,
            }
            predictions.append(prediction)
            input_failures.append(prediction)
            unresolved.append(prediction)
            continue

        if row is None:
            raise RuntimeError(f"Valid task silently disappeared: {task_id}")
        status = row.get("status")
        score_path = canonical_score_path(task_id)
        details: dict[str, Any] = {}
        if status == "ok":
            if not score_path.is_file():
                raise RuntimeError(f"Successful row lacks canonical score file: {task_id}")
            details = score_details(score_path)
            if details["success_criterion"] != "outcome":
                raise RuntimeError(f"Unexpected success criterion for {task_id}: {details['success_criterion']}")
            if bool(row.get("rubric_is_success")) != bool(details["score_process_rubric_is_success"]):
                raise RuntimeError(f"Process-result mismatch between report and score: {task_id}")
            if row.get("outcome_success") is not details["score_outcome_success"]:
                raise RuntimeError(f"Outcome-result mismatch between report and score: {task_id}")

        failure_category = None
        if status != "ok":
            failure_category = "infrastructure" if is_infrastructure_failure(row) else "verifier_terminal"
        prediction = {
            "task_id": task_id,
            "status": status,
            "failure_category": failure_category,
            "rubric_score": row.get("rubric_score"),
            "rubric_total_max_points": row.get("rubric_total_max_points"),
            "rubric_total_earned_points": row.get("rubric_total_earned_points"),
            "rubric_is_success": row.get("rubric_is_success"),
            "outcome_success": row.get("outcome_success"),
            "top_level_success": details.get("top_level_success"),
            "top_level_score": details.get("top_level_score"),
            "success_criterion": details.get("success_criterion"),
            "has_failure": row.get("has_failure"),
            "first_failure_step": row.get("first_failure_step"),
            "is_ambiguous": row.get("is_ambiguous"),
            "ambiguity_codes": row.get("ambiguity_codes"),
            "is_invalid": row.get("is_invalid"),
            "invalid_task_codes": row.get("invalid_task_codes"),
            "action_count": item["action_count"],
            "screenshot_count": item["screenshot_count"],
            "duration_sec": row.get("duration_sec"),
            "score_path": str(score_path.relative_to(PROJECT_ROOT)) if score_path.exists() else None,
            "execution_stage": row.get("execution_stage"),
            "error": row.get("error"),
        }
        predictions.append(prediction)
        if status == "ok":
            successful.append(prediction)
            destination = RAW_SCORE_ROOT / task_id / score_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(score_path, destination)
        else:
            unresolved.append(prediction)
            if failure_category == "infrastructure":
                infrastructure_failures.append(prediction)

    cached_path = BATCH_REPORT_ROOT / "preflight_cache_check.jsonl"
    cached = read_jsonl(cached_path) if cached_path.exists() else []
    retry_path = BATCH_REPORT_ROOT / "retry.jsonl"
    retry_rows = read_jsonl(retry_path) if retry_path.exists() else []

    write_jsonl(OUTPUT_ROOT / "full_report.jsonl", fresh_rows)
    write_jsonl(OUTPUT_ROOT / "full_predictions.jsonl", predictions)
    write_jsonl(
        OUTPUT_ROOT / "process_outcome_results.jsonl",
        [
            {
                "task_id": row["task_id"],
                "status": row["status"],
                "rubric_score": row["rubric_score"],
                "rubric_is_success": row["rubric_is_success"],
                "outcome_success": row["outcome_success"],
                "top_level_success": row["top_level_success"],
                "success_criterion": row.get("success_criterion"),
                "score_path": row["score_path"],
            }
            for row in predictions
        ],
    )
    write_jsonl(OUTPUT_ROOT / "successful_runs.jsonl", successful)
    write_jsonl(OUTPUT_ROOT / "infrastructure_failures.jsonl", infrastructure_failures)
    write_jsonl(OUTPUT_ROOT / "input_failures.jsonl", input_failures)
    write_jsonl(OUTPUT_ROOT / "cached_runs.jsonl", cached)
    write_jsonl(OUTPUT_ROOT / "retry_manifest.jsonl", retry_rows)
    write_jsonl(OUTPUT_ROOT / "unresolved_failures.jsonl", unresolved)

    statuses = Counter(row["status"] for row in predictions)
    coverage = len(successful) / len(predictions) * 100
    summary = f"""# E0 Execution Summary

- Frozen at (UTC): {datetime.now(timezone.utc).isoformat()}
- Total dataset rows: {len(predictions)}
- Valid inputs: {len(expected_valid)}
- Successfully scored: {len(successful)}
- Infrastructure failures: {len(infrastructure_failures)}
- Input failures: {len(input_failures)}
- Cached preflight checks: {len(cached)}
- Retry report rows: {len(retry_rows)}
- Unresolved failures: {len(unresolved)}
- Operational coverage: {coverage:.2f}%
- Status counts: {json.dumps(dict(statuses), sort_keys=True)}
- Judge models: `gpt-5.2` (multimodal) + `o4-mini` (action/rubric)
- Success criterion: outcome
- Per-task process and outcome results: `process_outcome_results.jsonl`
- Human annotations included: no
- Later experiments started: no

This summary reports execution coverage only. It does not calculate benchmark
accuracy, human agreement, or process/outcome aggregate statistics.
"""
    (OUTPUT_ROOT / "E0_execution_summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps({
        "total": len(predictions),
        "successful": len(successful),
        "infrastructure_failures": len(infrastructure_failures),
        "input_failures": len(input_failures),
        "unresolved": len(unresolved),
        "coverage_percent": round(coverage, 2),
    }))


if __name__ == "__main__":
    main()
