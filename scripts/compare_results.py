#!/usr/bin/env python3
"""Validate and compare one Microsoft screenshot run with one DOM-model run."""

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
    if int(calls.get("api_attempts", 0)) != int(calls.get("total", 0)) + int(calls.get("retries", 0)):
        errors.append(f"{mode} call accounting is inconsistent")
    usage = (run.get("token_usage") or {}).get("combined", {})
    if int(usage.get("total_tokens", 0)) != int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0)):
        errors.append(f"{mode} token accounting is inconsistent")
    denominator = float((run.get("result") or {}).get("total_max_points", 0))
    effective_maximum = sum(
        float(item.get("max_points", 0))
        for item in run.get("criteria", [])
        if item.get("is_applicable", True)
    )
    if denominator != effective_maximum:
        errors.append(f"{mode} denominator differs from applicable criterion maxima")
    return errors


def compare(screenshot: dict[str, Any], dom_model: dict[str, Any]) -> tuple[dict[str, Any], str]:
    errors = _validate_metrics(screenshot) + _validate_metrics(dom_model)
    for field in ("task_id", "frozen_rubric_sha256", "judge_models", "phase_a_generation_metrics"):
        if screenshot.get(field) != dom_model.get(field):
            errors.append(f"Cross-modal mismatch for {field}")
    for setting, expected in CANONICAL_SETTINGS.items():
        if screenshot.get("pipeline_settings", {}).get(setting) != expected or dom_model.get("pipeline_settings", {}).get(setting) != expected:
            errors.append(f"Controlled setting {setting} drifted from {expected!r}")
    screenshot_items = screenshot.get("criteria", [])
    dom_items = dom_model.get("criteria", [])
    if [item.get("criterion") for item in screenshot_items] != [item.get("criterion") for item in dom_items]:
        errors.append("Criterion names/order differ")
    elif [item.get("max_points") for item in screenshot_items] != [item.get("max_points") for item in dom_items]:
        errors.append("Criterion maximum points differ")
    screenshot_result = screenshot.get("result") or {}
    dom_result = dom_model.get("result") or {}
    if screenshot_result.get("total_max_points") != dom_result.get("total_max_points"):
        errors.append("Cross-modal denominators differ")
    if errors:
        raise ValueError("Comparison validation failed:\n- " + "\n- ".join(errors))

    screenshot_usage = screenshot["token_usage"]["combined"]
    dom_usage = dom_model["token_usage"]["combined"]
    token_delta = int(dom_usage["total_tokens"]) - int(screenshot_usage["total_tokens"])
    percent = token_delta / int(screenshot_usage["total_tokens"]) * 100 if int(screenshot_usage["total_tokens"]) else None
    criteria: list[dict[str, Any]] = []
    for left, right in zip(screenshot_items, dom_items):
        criteria.append(
            {
                "criterion": left["criterion"],
                "max_points": left["max_points"],
                "screenshot_action_only": left["action_only_points"],
                "dom_model_action_only": right["action_only_points"],
                "screenshot_final": left["final_points"],
                "dom_model_final": right["final_points"],
            }
        )
    receipt = {
        "status": "pass",
        "task_id": screenshot["task_id"],
        "frozen_rubric_sha256": screenshot["frozen_rubric_sha256"],
        "criterion_denominator": screenshot_result["total_max_points"],
        "models": screenshot["judge_models"],
        "pipeline_settings": CANONICAL_SETTINGS,
        "rubric_generation_calls_during_scoring": {"screenshot": 0, "dom_model": 0},
        "phase_a_generation_metrics": screenshot["phase_a_generation_metrics"],
        "screenshot": {
            "process_score": screenshot_result["process_score"],
            "earned_points": screenshot_result["total_earned_points"],
            "outcome_success": screenshot_result["outcome_success"],
            "logical_calls": screenshot["llm_calls"]["total"],
            "api_attempts": screenshot["llm_calls"]["api_attempts"],
            "retries": screenshot["llm_calls"]["retries"],
            "token_usage": screenshot_usage,
        },
        "dom_model": {
            "process_score": dom_result["process_score"],
            "earned_points": dom_result["total_earned_points"],
            "outcome_success": dom_result["outcome_success"],
            "logical_calls": dom_model["llm_calls"]["total"],
            "api_attempts": dom_model["llm_calls"]["api_attempts"],
            "retries": dom_model["llm_calls"]["retries"],
            "token_usage": dom_usage,
            "evidence_metrics": dom_model.get("evidence_metrics", {}),
        },
        "token_delta_dom_model_minus_screenshot": token_delta,
        "token_change_percent": percent,
        "criteria": criteria,
        "source_metrics": {
            "screenshot": screenshot.get("score_artifact"),
            "dom_model": dom_model.get("score_artifact"),
        },
    }
    lines = [
        f"# {screenshot['task_id']} verifier comparison", "",
        f"Frozen rubric SHA-256: `{screenshot['frozen_rubric_sha256']}`  ",
        f"Denominator: `{_fmt(screenshot_result['total_max_points'])}`  ",
        "Rubric generation calls during scoring: `0` for both modes", "",
        "| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |",
        "|---|---:|:---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, run in (("Microsoft screenshots", screenshot), ("DOM-model", dom_model)):
        result = run["result"]
        calls = run["llm_calls"]
        usage = run["token_usage"]["combined"]
        lines.append(
            f"| {label} | {_fmt(result['total_earned_points'])}/{_fmt(result['total_max_points'])} ({result['process_score']:.3f}) | "
            f"{result['outcome_success']} | {_fmt(calls['total'])} | {_fmt(calls['api_attempts'])} | {_fmt(calls['retries'])} | "
            f"{_fmt(usage['prompt_tokens'])} | {_fmt(usage['completion_tokens'])} | {_fmt(usage['total_tokens'])} |"
        )
    change = "undefined" if percent is None else f"{percent:+.2f}%"
    lines.extend([
        "", f"DOM-model minus screenshot tokens: **{token_delta:+,} ({change})**.", "",
        "## Criterion attribution", "",
        "| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for item in criteria:
        lines.append(
            f"| {item['criterion']} | {_fmt(item['max_points'])} | {_fmt(item['screenshot_action_only'])} | "
            f"{_fmt(item['dom_model_action_only'])} | {_fmt(item['screenshot_final'])} | {_fmt(item['dom_model_final'])} |"
        )
    lines.extend([
        "", "## Interpretation checks", "",
        "- Equal scores are not treated as proof that the two modalities contain equivalent evidence.",
        "- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.",
        "- Phase A generation usage is reported separately from both scoring totals.",
        "- Reasoning tokens are included in completion tokens and are not added twice.", "",
    ])
    return receipt, "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", required=True)
    parser.add_argument("--dom-model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    screenshot = load_json(args.screenshot)
    dom_model = load_json(args.dom_model)
    receipt, markdown = compare(screenshot, dom_model)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    receipt_path = Path(args.receipt) if args.receipt else output.with_suffix(".json")
    write_json(receipt_path, receipt)
    print(json.dumps({"report": str(output), "receipt": str(receipt_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
