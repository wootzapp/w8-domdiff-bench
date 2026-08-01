#!/usr/bin/env python3
"""Validate and summarize screenshot, DOM, and DOM-diff run metrics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Metrics must be an object: {path}")
    return value


def mode_name(value: dict[str, Any]) -> str:
    return {"screenshot": "Screenshot", "dom": "Full DOM", "dom_diff": "DOM-diff only"}.get(value.get("evidence_mode"), str(value.get("evidence_mode")))


def fmt_number(value: Any) -> str:
    return f"{int(value):,}" if isinstance(value, (int, float)) else str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--dom", type=Path, required=True)
    parser.add_argument("--dom-diff", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    runs = [load(args.screenshot), load(args.dom), load(args.dom_diff)]
    errors: list[str] = []
    for field in ("task_id", "frozen_rubric_sha256"):
        values = {run.get(field) for run in runs}
        if len(values) != 1:
            errors.append(f"Mismatched {field}: {sorted(map(str, values))}")
    max_points = {run.get("result", {}).get("total_max_points") for run in runs}
    if len(max_points) != 1:
        errors.append(f"Mismatched rubric denominators: {sorted(map(str, max_points))}")
    for run in runs:
        calls = run.get("llm_calls", {})
        if calls.get("rubric_generation_calls") != 0:
            errors.append(f"{mode_name(run)} scoring run generated a rubric")
        if calls.get("api_attempts") != calls.get("total", 0) + calls.get("retries", 0):
            errors.append(f"{mode_name(run)} has inconsistent call/attempt/retry counts")
        usage = run.get("token_usage", {}).get("combined", {})
        if usage.get("total_tokens") != usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0):
            errors.append(f"{mode_name(run)} total token accounting is inconsistent")
    if errors:
        print("\n".join(f"ERROR: {value}" for value in errors), file=sys.stderr)
        return 1

    lines = [
        f"# {runs[0]['task_id']} Verifier Comparison",
        "",
        f"Frozen rubric SHA-256: `{runs[0]['frozen_rubric_sha256']}`",
        "",
        "| Evidence mode | Process score | Outcome | Calls | API attempts | Retries | Total tokens |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for run in runs:
        result = run["result"]
        calls = run["llm_calls"]
        total = run["token_usage"]["combined"]["total_tokens"]
        lines.append(
            f"| {mode_name(run)} | {fmt_number(result['total_earned_points'])}/{fmt_number(result['total_max_points'])} ({result['process_score']:.2f}) | {result['outcome_success']} | {fmt_number(calls['total'])} | {fmt_number(calls['api_attempts'])} | {fmt_number(calls['retries'])} | {fmt_number(total)} |"
        )

    criteria: list[str] = []
    by_mode: list[dict[str, dict[str, Any]]] = []
    for run in runs:
        mapping = {item["criterion"]: item for item in run.get("criteria", [])}
        by_mode.append(mapping)
        for criterion in mapping:
            if criterion not in criteria:
                criteria.append(criterion)
    lines += ["", "## Criterion attribution", "", "| Criterion | Screenshot | Full DOM | DOM-diff only |", "|---|---:|---:|---:|"]
    for criterion in criteria:
        cells = []
        for mapping in by_mode:
            item = mapping.get(criterion)
            cells.append("—" if item is None else f"{fmt_number(item['final_points'])}/{fmt_number(item['max_points'])}")
        lines.append(f"| {criterion} | {cells[0]} | {cells[1]} | {cells[2]} |")

    action_variance = any(
        len({mapping.get(criterion, {}).get("action_only_points") for mapping in by_mode}) > 1
        for criterion in criteria
    )
    lines += ["", "## Interpretation checks", "", f"- Action-only scores differ across modes: **{action_variance}**."]
    if action_variance:
        lines.append("- Separate action-judge variance from evidence-stage changes; the frozen rubric does not freeze independent scoring calls.")
    final_vectors = [tuple(mapping.get(c, {}).get("final_points") for c in criteria) for mapping in by_mode]
    lines.append(f"- Criterion allocation differs across modes: **{len(set(final_vectors)) > 1}**.")
    lines.append("- Matching totals must not be reported as evidence agreement when criterion allocation differs.")

    output = "\n".join(lines) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(args.output)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
