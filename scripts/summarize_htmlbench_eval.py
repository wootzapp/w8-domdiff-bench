#!/usr/bin/env python3
"""Summarize repeated HTMLBench profile runs from recorder artifacts."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


NUMERIC_METRICS = (
    "input_tokens", "output_tokens", "total_tokens", "cached_input_tokens",
    "model_calls", "recorded_steps", "run_duration_seconds", "dom_model_bytes",
    "dom_model_chars", "dom_json_bytes", "dom_diff_json_bytes",
    "captured_nodes", "raw_nodes", "truncated_snapshots", "diff_changes",
    "stored_run_bytes",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def usage_totals(path: Path) -> dict[str, int]:
    totals = {
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
        "cached_input_tokens": 0, "model_calls": 0,
    }
    if not path.exists():
        return totals
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        row = json.loads(raw)
        response = row.get("model_response")
        usage = response.get("usage") if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            continue
        totals["model_calls"] += 1
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                totals[key] += value
        details = usage.get("input_tokens_details")
        cached = details.get("cached_tokens") if isinstance(details, dict) else None
        if isinstance(cached, int):
            totals["cached_input_tokens"] += cached
    return totals


def snapshot_payload(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        return {}
    result = value.get("result")
    snapshot = result.get("snapshot") if isinstance(result, dict) else None
    return snapshot if isinstance(snapshot, dict) else {}


def unique_state_directories(run_dir: Path) -> list[Path]:
    directories = []
    initial = run_dir / "initial"
    if initial.is_dir():
        directories.append(initial)
    directories.extend(sorted(run_dir.glob("steps/step_*/after")))
    return directories


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def collect_run(manifest_path: Path, *, historical: bool = False) -> dict[str, Any]:
    run_dir = manifest_path.parent
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path} is not a JSON object")
    profile_data = manifest.get("htmlbench_eval")
    profile = (
        str(profile_data.get("profile"))
        if isinstance(profile_data, dict) and profile_data.get("profile")
        else "historical" if historical else "unlabeled"
    )
    started = parse_time(manifest.get("created_at"))
    completed = parse_time(manifest.get("completed_at"))
    duration = (
        max(0.0, (completed - started).total_seconds())
        if started is not None and completed is not None else 0.0
    )
    values: dict[str, Any] = {
        "run_dir": str(run_dir),
        "task_id": str(manifest.get("source_task_id") or manifest.get("task_id") or ""),
        "task_name": str(manifest.get("task_name") or manifest.get("source_task_id") or "unknown"),
        "profile": profile,
        "status": str(manifest.get("status") or "unknown"),
        "success": 1 if manifest.get("status") == "success" else 0,
        "recorded_steps": len(manifest.get("steps") or []),
        "run_duration_seconds": round(duration, 3),
        **usage_totals(run_dir / "decisions.jsonl"),
        "dom_model_bytes": 0,
        "dom_model_chars": 0,
        "dom_json_bytes": 0,
        "dom_diff_json_bytes": 0,
        "captured_nodes": 0,
        "raw_nodes": 0,
        "truncated_snapshots": 0,
        "diff_changes": 0,
        "stored_run_bytes": 0,
    }
    for state_dir in unique_state_directories(run_dir):
        model_path = state_dir / "dom_model.txt"
        dom_path = state_dir / "dom.json"
        values["dom_model_bytes"] += file_size(model_path)
        if model_path.exists():
            values["dom_model_chars"] += len(
                model_path.read_text(encoding="utf-8", errors="replace")
            )
        values["dom_json_bytes"] += file_size(dom_path)
        if dom_path.exists():
            snapshot = snapshot_payload(dom_path)
            nodes = snapshot.get("nodes")
            if isinstance(nodes, list):
                values["captured_nodes"] += len(nodes)
            stats = snapshot.get("stats")
            if isinstance(stats, dict):
                raw_nodes = stats.get("rawNodes")
                if isinstance(raw_nodes, int):
                    values["raw_nodes"] += raw_nodes
                values["truncated_snapshots"] += int(stats.get("truncated") is True)
    for diff_path in sorted(run_dir.glob("steps/step_*/dom_diff.json")):
        values["dom_diff_json_bytes"] += file_size(diff_path)
        diff = read_json(diff_path)
        if isinstance(diff, dict) and isinstance(diff.get("change_count"), int):
            values["diff_changes"] += diff["change_count"]
    values["stored_run_bytes"] = sum(
        file_size(path) for path in run_dir.rglob("*") if path.is_file()
    )
    return values


def metric_stats(values: Iterable[float]) -> dict[str, float]:
    samples = [float(value) for value in values]
    if not samples:
        return {"n": 0, "mean": 0.0, "median": 0.0, "stdev": 0.0, "min": 0.0, "max": 0.0}
    return {
        "n": len(samples),
        "mean": round(statistics.mean(samples), 3),
        "median": round(statistics.median(samples), 3),
        "stdev": round(statistics.stdev(samples), 3) if len(samples) > 1 else 0.0,
        "min": round(min(samples), 3),
        "max": round(max(samples), 3),
    }


def grouped_summary(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[(run["task_name"], run["profile"])].append(run)
    summaries = []
    for (task_name, profile), members in sorted(grouped.items()):
        summaries.append({
            "task_name": task_name,
            "profile": profile,
            "runs": len(members),
            "success_rate": round(
                sum(member["success"] for member in members) / len(members), 3
            ),
            "metrics": {
                metric: metric_stats(member[metric] for member in members)
                for metric in NUMERIC_METRICS
            },
        })
    return summaries


def comparisons(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(group["task_name"], group["profile"]): group for group in groups}
    output = []
    tasks = sorted({group["task_name"] for group in groups})
    profiles = sorted({
        group["profile"] for group in groups
        if group["profile"] not in {"baseline", "historical", "unlabeled"}
    })
    for task_name in tasks:
        baseline = indexed.get((task_name, "baseline"))
        if baseline is None:
            continue
        for profile in profiles:
            treatment = indexed.get((task_name, profile))
            if treatment is None:
                continue
            deltas: dict[str, Any] = {}
            for metric in NUMERIC_METRICS:
                before = baseline["metrics"][metric]["median"]
                after = treatment["metrics"][metric]["median"]
                deltas[metric] = {
                    "baseline_median": before,
                    "treatment_median": after,
                    "percent_change": (
                        round((after - before) * 100.0 / before, 3)
                        if before else None
                    ),
                }
            output.append({
                "task_name": task_name,
                "profile": profile,
                "baseline_runs": baseline["runs"],
                "treatment_runs": treatment["runs"],
                "baseline_success_rate": baseline["success_rate"],
                "treatment_success_rate": treatment["success_rate"],
                "deltas": deltas,
            })
    return output


def markdown_report(report: dict[str, Any]) -> str:
    comparisons = report["comparisons"]
    task_labels = {
        "CPython workflow inspection evidence rerun": "GitHub/CPython",
        "arxiv paper metadata": "arXiv",
        "hugging face dataset inspection": "Hugging Face SQuAD",
        "openstreetmap-cycling-route": "OpenStreetMap cycling",
    }

    def percent(value: float | None) -> str:
        if value is None:
            return "n/a"
        if value == 0:
            return "0%"
        precision = 3 if abs(value) < 0.01 else 2
        return f"{value:+.{precision}f}%"

    def comparison(item: dict[str, Any], metric: str, unit: str = "") -> str:
        values = item["deltas"][metric]
        before = values["baseline_median"]
        after = values["treatment_median"]
        suffix = f" {unit}" if unit else ""
        return (
            f"{before:,.0f} → {after:,.0f}{suffix} "
            f"({percent(values['percent_change'])})"
        )

    first = comparisons[0] if comparisons else None
    baseline_runs = first["baseline_runs"] if first else 0
    treatment_runs = first["treatment_runs"] if first else 0
    lines = [
        "# HTMLBench run results",
        "",
        f"{len(comparisons)} tasks were run {baseline_runs} times with `baseline` and "
        f"{treatment_runs} times with `htmlbench-full`. This produced "
        f"{report['run_count']} fresh runs. The table uses medians.",
        "",
        "The tasks cover a document page, a dense repository page, an SPA, and an interactive map. Both profiles used the same browser image, viewport, task settings, and DOM capture limits.",
        "",
        "Total tokens include every model response. DOM sizes count the initial state and each after-action state once.",
        "",
        "| Task | Total tokens: baseline → HTMLBench | `dom_model`: baseline → HTMLBench | `dom_diff`: baseline → HTMLBench |",
        "|---|---:|---:|---:|",
    ]
    for item in comparisons:
        label = task_labels.get(item["task_name"], item["task_name"])
        lines.append(
            f"| {label} | {comparison(item, 'total_tokens')} | "
            f"{comparison(item, 'dom_model_bytes', 'bytes')} | "
            f"{comparison(item, 'dom_diff_json_bytes', 'bytes')} |"
        )

    near_unchanged = sum(
        abs(item["deltas"]["dom_model_bytes"]["percent_change"] or 0) < 1
        and abs(item["deltas"]["dom_diff_json_bytes"]["percent_change"] or 0) < 1
        for item in comparisons
    )
    largest_step_increase = max(
        comparisons,
        key=lambda item: item["deltas"]["recorded_steps"]["percent_change"] or 0,
        default=None,
    )
    lines.extend([
        "",
        "- There was no consistent reduction in token usage or DOM file size.",
        f"- {near_unchanged} of {len(comparisons)} tasks had less than 1% DOM-size change.",
        "- GitHub/CPython used fewer median tokens, but its DOM sizes stayed the same, so this was not DOM compression.",
        (
            f"- {task_labels.get(largest_step_increase['task_name'], largest_step_increase['task_name'])} "
            f"recorded {largest_step_increase['deltas']['recorded_steps']['baseline_median']:.0f} → "
            f"{largest_step_increase['deltas']['recorded_steps']['treatment_median']:.0f} actions, "
            "which also increased the number of stored page states."
            if largest_step_increase else ""
        ),
        "- The browser flags and page scripts changed runtime behavior, but not how ChromiumRL snapshots, `dom_model`, or `dom_diff` are created.",
    ])
    return "\n".join(lines) + "\n"


def discover(root: Path) -> list[Path]:
    if root.name == "manifest.json" and root.is_file():
        return [root]
    return sorted(root.rglob("manifest.json"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", type=Path, action="append", default=[])
    parser.add_argument("--historical-root", type=Path, action="append", default=[])
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.runs_root and not args.historical_root:
        raise SystemExit("provide --runs-root and/or --historical-root")
    seen: set[Path] = set()
    runs: list[dict[str, Any]] = []
    for root, historical in [
        *((path, False) for path in args.runs_root),
        *((path, True) for path in args.historical_root),
    ]:
        for manifest_path in discover(root.resolve()):
            if manifest_path in seen:
                continue
            seen.add(manifest_path)
            runs.append(collect_run(manifest_path, historical=historical))
    groups = grouped_summary(runs)
    report = {
        "run_count": len(runs),
        "runs": runs,
        "groups": groups,
        "comparisons": comparisons(groups),
    }
    rendered_json = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    rendered_markdown = markdown_report(report)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered_json, encoding="utf-8")
    else:
        print(rendered_json, end="")
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(rendered_markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
