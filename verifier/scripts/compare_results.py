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
        "criterion_denominator": screenshot_result["total_max_points"],
        "screenshot": {
            "process_score": screenshot_result["process_score"],
            "earned_points": screenshot_result["total_earned_points"],
            "maximum_points": screenshot_result["total_max_points"],
            "outcome_success": screenshot_result["outcome_success"],
        },
        "dom_model": {
            "process_score": dom_result["process_score"],
            "earned_points": dom_result["total_earned_points"],
            "maximum_points": dom_result["total_max_points"],
            "outcome_success": dom_result["outcome_success"],
        },
        "criteria": criteria,
    }
    lines = [
        f"# {screenshot['task_id']} verifier comparison", "",
        "| Mode | Score | Outcome |",
        "|---|---:|:---:|",
    ]
    for label, run in (("Microsoft screenshots", screenshot), ("DOM-model", dom_model)):
        result = run["result"]
        lines.append(
            f"| {label} | {_fmt(result['total_earned_points'])}/{_fmt(result['total_max_points'])} ({result['process_score']:.3f}) | "
            f"{result['outcome_success']} |"
        )
    lines.extend([
        "", "## Criterion scores", "",
        "| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for item in criteria:
        lines.append(
            f"| {item['criterion']} | {_fmt(item['max_points'])} | {_fmt(item['screenshot_action_only'])} | "
            f"{_fmt(item['dom_model_action_only'])} | {_fmt(item['screenshot_final'])} | {_fmt(item['dom_model_final'])} |"
        )
    lines.append("")
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
