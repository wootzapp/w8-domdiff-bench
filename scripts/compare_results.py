#!/usr/bin/env python3
"""Validate and compare one screenshot run with one DOM-text run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .common import CANONICAL_SETTINGS, load_json, write_json


def _fmt(value: Any) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:g}"
    if isinstance(value, (int, float)):
        return f"{value:,.0f}"
    return str(value)


def _validate_metrics(run: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    mode = run.get("evidence_mode")
    calls = run.get("llm_calls") or {}
    if calls.get("rubric_generation_calls") != 0:
        errors.append(f"{mode} scoring generated a rubric")
    if int(calls.get("api_attempts", 0)) != int(calls.get("total", 0)) + int(
        calls.get("retries", 0)
    ):
        errors.append(f"{mode} call/attempt/retry accounting is inconsistent")
    usage = run.get("token_usage", {}).get("combined", {})
    if int(usage.get("total_tokens", 0)) != int(usage.get("prompt_tokens", 0)) + int(
        usage.get("completion_tokens", 0)
    ):
        errors.append(f"{mode} token accounting is inconsistent")
    result = run.get("result") or {}
    max_points = float(result.get("total_max_points", 0))
    points_from_criteria = sum(float(item.get("max_points", 0)) for item in run.get("criteria", []))
    if max_points != points_from_criteria:
        errors.append(f"{mode} criterion denominator differs from result denominator")
    return errors


def compare(screenshot: dict[str, Any], dom: dict[str, Any]) -> tuple[dict[str, Any], str]:
    errors = _validate_metrics(screenshot) + _validate_metrics(dom)
    for field in ("task_id", "frozen_rubric_sha256", "judge_models"):
        if screenshot.get(field) != dom.get(field):
            errors.append(f"Cross-modal mismatch for {field}")
    screenshot_result = screenshot.get("result") or {}
    dom_result = dom.get("result") or {}
    if screenshot_result.get("total_max_points") != dom_result.get("total_max_points"):
        errors.append("Cross-modal rubric denominators differ")
    for setting, expected in CANONICAL_SETTINGS.items():
        screenshot_value = screenshot.get("pipeline_settings", {}).get(setting)
        dom_value = dom.get("pipeline_settings", {}).get(setting)
        if screenshot_value != expected or dom_value != expected:
            errors.append(
                f"Controlled setting {setting} must be {expected!r}; "
                f"got screenshot={screenshot_value!r}, DOM={dom_value!r}"
            )
    screenshot_criteria = {item["criterion"]: item for item in screenshot.get("criteria", [])}
    dom_criteria = {item["criterion"]: item for item in dom.get("criteria", [])}
    if list(screenshot_criteria) != list(dom_criteria):
        errors.append("Criterion names/order differ between modalities")
    else:
        for criterion in screenshot_criteria:
            if screenshot_criteria[criterion].get("max_points") != dom_criteria[criterion].get(
                "max_points"
            ):
                errors.append(f"Criterion max_points differs: {criterion}")
    if errors:
        raise ValueError("Comparison validation failed:\n- " + "\n- ".join(errors))

    screenshot_usage = screenshot["token_usage"]["combined"]
    dom_usage = dom["token_usage"]["combined"]
    screenshot_total = int(screenshot_usage["total_tokens"])
    dom_total = int(dom_usage["total_tokens"])
    token_delta = dom_total - screenshot_total
    token_change_percent = (token_delta / screenshot_total * 100.0) if screenshot_total else None
    criteria = []
    action_variance = False
    final_variance = False
    for criterion, screenshot_item in screenshot_criteria.items():
        dom_item = dom_criteria[criterion]
        action_differs = screenshot_item.get("action_only_points") != dom_item.get(
            "action_only_points"
        )
        final_differs = screenshot_item.get("final_points") != dom_item.get("final_points")
        action_variance = action_variance or action_differs
        final_variance = final_variance or final_differs
        criteria.append(
            {
                "criterion": criterion,
                "max_points": screenshot_item.get("max_points"),
                "screenshot_action_only": screenshot_item.get("action_only_points"),
                "dom_action_only": dom_item.get("action_only_points"),
                "screenshot_final": screenshot_item.get("final_points"),
                "dom_final": dom_item.get("final_points"),
            }
        )
    receipt = {
        "status": "pass",
        "task_id": screenshot["task_id"],
        "frozen_rubric_sha256": screenshot["frozen_rubric_sha256"],
        "criterion_denominator": screenshot_result["total_max_points"],
        "models": screenshot["judge_models"],
        "pipeline_settings": CANONICAL_SETTINGS,
        "screenshot": {
            "process_score": screenshot_result["process_score"],
            "earned_points": screenshot_result["total_earned_points"],
            "outcome_success": screenshot_result["outcome_success"],
            "logical_calls": screenshot["llm_calls"]["total"],
            "api_attempts": screenshot["llm_calls"]["api_attempts"],
            "retries": screenshot["llm_calls"]["retries"],
            "token_usage": screenshot_usage,
        },
        "dom_diff_text": {
            "process_score": dom_result["process_score"],
            "earned_points": dom_result["total_earned_points"],
            "outcome_success": dom_result["outcome_success"],
            "logical_calls": dom["llm_calls"]["total"],
            "api_attempts": dom["llm_calls"]["api_attempts"],
            "retries": dom["llm_calls"]["retries"],
            "token_usage": dom_usage,
        },
        "token_delta_dom_minus_screenshot": token_delta,
        "token_change_percent": token_change_percent,
        "action_only_variance": action_variance,
        "criterion_allocation_differs": final_variance,
        "criteria": criteria,
        "source_metrics": {
            "screenshot": screenshot.get("score_artifact"),
            "dom_diff_text": dom.get("score_artifact"),
        },
    }

    lines = [
        f"# {screenshot['task_id']} verifier comparison",
        "",
        f"Frozen rubric SHA-256: `{screenshot['frozen_rubric_sha256']}`  ",
        f"Denominator: `{_fmt(screenshot_result['total_max_points'])}`  ",
        "Rubric generation calls during scoring: `0`",
        "",
        "| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |",
        "|---|---:|:---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, run in (("Microsoft screenshots", screenshot), ("DOM-diff text", dom)):
        result = run["result"]
        calls = run["llm_calls"]
        usage = run["token_usage"]["combined"]
        lines.append(
            f"| {label} | {_fmt(result['total_earned_points'])}/{_fmt(result['total_max_points'])} "
            f"({result['process_score']:.3f}) | {result['outcome_success']} | "
            f"{_fmt(calls['total'])} | {_fmt(calls['api_attempts'])} | "
            f"{_fmt(calls['retries'])} | {_fmt(usage['prompt_tokens'])} | "
            f"{_fmt(usage['completion_tokens'])} | {_fmt(usage['total_tokens'])} |"
        )
    change_text = "undefined" if token_change_percent is None else f"{token_change_percent:+.2f}%"
    lines.extend(
        [
            "",
            f"DOM minus screenshot tokens: **{token_delta:+,} ({change_text})**.",
            "",
            "## Criterion attribution",
            "",
            "| Criterion | Max | Screenshot action | DOM action | Screenshot final | DOM final |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in criteria:
        lines.append(
            f"| {item['criterion']} | {_fmt(item['max_points'])} | "
            f"{_fmt(item['screenshot_action_only'])} | {_fmt(item['dom_action_only'])} | "
            f"{_fmt(item['screenshot_final'])} | {_fmt(item['dom_final'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation checks",
            "",
            f"- Independent action-only scores differ: **{action_variance}**.",
            f"- Final criterion allocation differs: **{final_variance}**.",
            "- Matching totals are not treated as evidence agreement when criterion allocation differs.",
            "- Reasoning tokens are included in completion tokens and are not added twice.",
            "",
        ]
    )
    return receipt, "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", required=True)
    parser.add_argument("--dom-diff-text", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    screenshot = load_json(args.screenshot)
    dom = load_json(args.dom_diff_text)
    if not isinstance(screenshot, dict) or not isinstance(dom, dict):
        raise ValueError("Metrics inputs must be JSON objects")
    receipt, markdown = compare(screenshot, dom)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    receipt_path = Path(args.receipt) if args.receipt else output.with_suffix(".json")
    write_json(receipt_path, receipt)
    print(json.dumps({"report": str(output), "receipt": str(receipt_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
