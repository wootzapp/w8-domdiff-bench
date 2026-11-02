"""Summarize independent recorded runs using paired hierarchical intervals."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import random
from statistics import mean, quantiles

from .combine_audit_passes import _flags, _protocol
from .common import canonical_sha256, write_json
from .evidence_audit import calculate_metrics


LOSS_FLAGS = ("screenshot_evidence_loss", "dom_model_evidence_loss")


def hierarchical_intervals(clusters: list[list[tuple[int, int, int]]], *,
                           resamples: int = 20000, seed: int = 0) -> dict:
    """Keep all criteria and both sides together; draw tasks, then runs."""
    if not clusters or resamples < 2 or any(not values for values in clusters):
        raise ValueError("Intervals require nonempty task clusters and at least two resamples")
    rng = random.Random(seed)
    distributions = [[], [], [], []]
    undefined = 0
    for _ in range(resamples):
        counts = [0, 0, 0]
        for task in rng.choices(clusters, k=len(clusters)):
            for run in rng.choices(task, k=len(task)):
                for index, value in enumerate(run):
                    counts[index] += value
        n, s, d = counts
        distributions[0].append(s / n)
        distributions[1].append(d / n)
        distributions[2].append((s - d) / n)
        if s:
            distributions[3].append((s - d) / s)
        else:
            undefined += 1
    result = {"method": "paired_task_then_run_percentile_bootstrap", "confidence": 0.95,
              "resamples": resamples, "seed": seed, "tasks": len(clusters),
              "runs": len(clusters[0]), "undefined_relative_reduction_resamples": undefined,
              "interpretation": "Sampling uncertainty with audit labels held fixed; not annotation error."}
    for key, values in zip((*LOSS_FLAGS, "rate_difference", "relative_reduction"), distributions):
        cutpoints = quantiles(values, n=40, method="inclusive") if len(values) >= 2 else None
        result[key] = [cutpoints[0], cutpoints[-1]] if cutpoints else None
    return result


def aggregate_runs(roots: list[Path], *, expected_tasks: int = 100,
                   resamples: int = 20000, seed: int = 0) -> tuple[dict, list[dict]]:
    if not roots or len({Path(root).resolve() for root in roots}) != len(roots):
        raise ValueError("Provide distinct, complete run directories")
    runs, reference_protocol, reference = [], None, None
    for root in roots:
        root = Path(root).resolve(strict=True)
        tasks = {}
        for path in sorted(root.glob("task_*/**/evidence_audit.json")):
            value = json.loads(path.read_text())
            alias = value.get("task_alias")
            if not isinstance(alias, str) or alias in tasks:
                raise ValueError(f"Missing or duplicate task alias in {root.name}")
            protocol = _protocol(value)
            if reference_protocol is None:
                reference_protocol = protocol
            if protocol != reference_protocol:
                raise ValueError(f"Audit protocol mismatch: {root.name}/{alias}")
            rows = value.get("criteria", [])
            indices = [row["criterion_index"] for row in rows]
            if not rows or sorted(indices) != list(range(len(rows))):
                raise ValueError(f"Invalid criterion indices: {alias}")
            for row in rows:
                _flags(row)
            rubric_hash = value.get("frozen_rubric_sha256")
            if not isinstance(rubric_hash, str) or len(rubric_hash) != 64:
                raise ValueError(f"Missing frozen rubric hash: {alias}")
            signature = (rubric_hash, sorted((row["criterion_index"], row["criterion"],
                                             row.get("description"), row.get("max_points")) for row in rows))
            tasks[alias] = {"audit": value, "signature": signature, "path": path}
        if len(tasks) != expected_tasks:
            raise ValueError(f"Expected {expected_tasks} tasks in {root.name}; found {len(tasks)}")
        if set(tasks) != {f"task_{number:02d}" for number in range(1, expected_tasks + 1)}:
            raise ValueError("Run task sets differ from the expected catalog aliases")
        signatures = {alias: value["signature"] for alias, value in tasks.items()}
        if reference is None:
            reference = signatures
        if set(signatures) != set(reference):
            raise ValueError("Run task sets differ")
        if signatures != reference:
            raise ValueError("Frozen rubric hashes or criteria differ between runs")
        runs.append((root, tasks))
    aliases = sorted(reference)
    clusters = [[(len(tasks[alias]["audit"]["criteria"]),
                  sum(row[LOSS_FLAGS[0]] for row in tasks[alias]["audit"]["criteria"]),
                  sum(row[LOSS_FLAGS[1]] for row in tasks[alias]["audit"]["criteria"]))
                 for _, tasks in runs] for alias in aliases]
    per_run, categories = [], []
    returned = {stage: set() for stage in ("inventory", "adjudication")}
    for run_index, (root, tasks) in enumerate(runs):
        rows = [row for alias in aliases for row in tasks[alias]["audit"]["criteria"]]
        metrics = calculate_metrics(rows)
        per_run.append({"run_name": root.name, "tasks": len(tasks), **metrics,
                        "confidence_intervals": hierarchical_intervals(
                            [[task[run_index]] for task in clusters], resamples=resamples, seed=seed)})
        for alias, entry in tasks.items():
            audit = entry["audit"]
            for call in audit.get("calls", []):
                if call.get("stage") in returned and call.get("response_model"):
                    returned[call["stage"]].add(call["response_model"])
            for row in audit["criteria"]:
                for side in ("screenshot", "dom_model"):
                    if not row[side + "_evidence_loss"]:
                        continue
                    finding = row["adjudication"][side + "_evidence_loss"]
                    categories.append({"run_name": root.name, "task": alias,
                                       "criterion_index": row["criterion_index"], "representation": side,
                                       "category": row.get("loss_categories", {}).get(side, "Unclassified"),
                                       "rationale": finding["explanation"],
                                       "finding_sha256": canonical_sha256({"criterion": row["criterion"], "finding": finding}),
                                       "source": entry["path"].as_posix()})
    means = {flag: {"count": mean(run[flag]["count"] for run in per_run),
                    "rate": mean(run[flag]["rate"] for run in per_run)} for flag in LOSS_FLAGS}
    s, d = (means[key]["count"] for key in LOSS_FLAGS)
    return {"schema_version": "recorded-run-comparison/v1", "created_at": datetime.now(timezone.utc).isoformat(),
            "aggregation": "mean_across_independent_recorded_runs", "protocol": reference_protocol,
            "run_names": [root.name for root, _ in runs], "k": len(runs), "tasks_per_run": len(aliases),
            "criteria_per_run": sum(len(values[1]) for values in reference.values()),
            "per_run": per_run, "mean": means,
            "mean_verifier_misses": {key: {"count": mean(run[key]["count"] for run in per_run),
                                            "rate": mean(run[key]["rate"] for run in per_run)}
                                      for key in ("screenshot_verifier_misses", "dom_model_verifier_misses")},
            "relative_reduction": (s - d) / s if s else None,
            "confidence_intervals": hierarchical_intervals(clusters, resamples=resamples, seed=seed),
            "response_models": {key: sorted(values) for key, values in returned.items()},
            "response_model_drift": any(len(values) > 1 for values in returned.values()),
            "frozen_rubrics": {alias: value[0] for alias, value in reference.items()}}, categories


def render_table(summary: dict) -> str:
    lines = ["| Run | Criteria | Screenshot losses | DOM losses | Screenshot misses | DOM misses |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for run in summary["per_run"]:
        counts = [run[key]["count"] for key in (*LOSS_FLAGS, "screenshot_verifier_misses", "dom_model_verifier_misses")]
        lines.append(f"| {run['run_name']} | {run['total_criteria']} | " + " | ".join(map(str, counts)) + " |")
    s, d = (summary["mean"][flag] for flag in LOSS_FLAGS)
    sm, dm = (summary["mean_verifier_misses"][key]["count"] for key in ("screenshot_verifier_misses", "dom_model_verifier_misses"))
    lines.extend([f"| Mean | {summary['criteria_per_run']} | {s['count']:.2f} ({s['rate']:.2%}) | {d['count']:.2f} ({d['rate']:.2%}) | {sm:.2f} | {dm:.2f} |", "",
                  "| Measure | Estimate | 95% interval |", "| --- | ---: | ---: |"])
    for key, label, estimate in ((LOSS_FLAGS[0], "Screenshot loss rate", s["rate"]),
                                 (LOSS_FLAGS[1], "DOM loss rate", d["rate"]),
                                 ("rate_difference", "Screenshot minus DOM rate", s["rate"] - d["rate"]),
                                 ("relative_reduction", "Relative reduction", summary["relative_reduction"])):
        interval = summary["confidence_intervals"][key]
        estimate_text = f"{estimate:.2%}" if estimate is not None else "undefined"
        interval_text = f"{interval[0]:.2%} to {interval[1]:.2%}" if interval is not None else "undefined"
        lines.append(f"| {label} | {estimate_text} | {interval_text} |")
    lines.extend(["", "Intervals resample tasks, then recorded runs within each task, keeping both representations together."])
    return "\n".join(lines) + "\n"


def write_figure(path: Path, title: str, rows: list[tuple[str, float, float]], *, unit: str) -> None:
    """Small vector chart; orange and dark red distinguish the two sides."""
    peak = max((max(s, d) for _, s, d in rows), default=1) or 1
    width, height = 880, 120 + 58 * len(rows)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
             f'<title>{escape(title)}</title>', '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="20" y="28" font-family="sans-serif" font-size="18">{escape(title)}</text>',
             '<text x="220" y="55" fill="#e77b18" font-family="sans-serif">Screenshots</text>',
             '<text x="380" y="55" fill="#8b2332" font-family="sans-serif">DOM</text>']
    for index, (label, s, d) in enumerate(rows):
        y = 83 + index * 58
        parts.append(f'<text x="20" y="{y + 12}" font-family="sans-serif" font-size="13">{escape(label)}</text>')
        for offset, value, color in ((0, s, '#e77b18'), (21, d, '#8b2332')):
            size = 500 * value / peak
            parts.extend([f'<rect x="230" y="{y + offset}" width="{size:.2f}" height="16" fill="{color}"/>',
                          f'<text x="{740}" y="{y + offset + 13}" font-family="sans-serif" font-size="13">{value:.2f} {unit}</text>'])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(parts + ['</svg>']) + '\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--expected-tasks", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--readme", type=Path)
    parser.add_argument("--figures-dir", type=Path)
    parser.add_argument("--recordings-root", type=Path, default=Path("recordings"))
    parser.add_argument("--categories", type=Path, help="Reviewed annotations keyed by run, task, criterion and finding hash")
    parser.add_argument("--resamples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    readme_text = args.readme.read_text(encoding="utf-8") if args.readme else None
    start, end = "<!-- recorded-runs:start -->", "<!-- recorded-runs:end -->"
    if readme_text is not None and (readme_text.count(start) != 1 or readme_text.count(end) != 1
                                    or readme_text.index(start) > readme_text.index(end)):
        raise ValueError("README must contain one ordered recorded-runs marker pair")
    summary, categories = aggregate_runs(args.runs, expected_tasks=args.expected_tasks,
                                         resamples=args.resamples, seed=args.seed)
    if args.categories:
        with args.categories.open(newline="", encoding="utf-8") as stream:
            annotations = {(row.get("run_name", "run_1"), row["task"], str(row["criterion_index"]),
                            row["representation"], row["finding_sha256"]): row for row in csv.DictReader(stream, delimiter="\t")}
        for row in categories:
            key = (row["run_name"], row["task"], str(row["criterion_index"]), row["representation"], row["finding_sha256"])
            if key in annotations:
                row.update(category=annotations[key]["category"], rationale=annotations[key]["rationale"])
    root = Path(__file__).resolve().parents[2]
    for row in categories:
        row["source"] = os.path.relpath(row["source"], root)
    names = sorted({row["category"] for row in categories})
    summary["mean_category_counts"] = {
        name: {side: sum(row["category"] == name and row["representation"] == side for row in categories) / summary["k"]
               for side in ("screenshot", "dom_model")} for name in names}
    summary["unclassified_losses"] = sum(row["category"] == "Unclassified" for row in categories)
    population = {}
    for run_name in summary["run_names"]:
        folder = args.recordings_root / run_name
        if not folder.is_dir():
            continue
        states = sorted(folder.glob("task_*/steps/step_*"))
        formats = {}
        for name in ("screenshot.png", "dom_model.txt", "dom_full.txt", "dom.json"):
            paths = [state / name for state in states]
            if not paths or any(not path.is_file() for path in paths):
                raise ValueError(f"Incomplete captured-state size population: {run_name}/{name}")
            formats[name] = {"files": len(paths), "bytes": sum(path.stat().st_size for path in paths)}
            formats[name]["mean_kib"] = formats[name]["bytes"] / len(paths) / 1024
        population[run_name] = {"tasks": len(list(folder.glob("task_*/task.json"))), "formats": formats}
    summary["recorded_file_sizes"] = {"unit": "KiB", "bytes_per_kib": 1024,
                                       "population": "All captured states in the listed recorded runs", "per_run": population}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "summary.json", summary)
    with (args.output_dir / "evidence_categories.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["run_name", "task", "criterion_index", "representation", "category", "rationale", "finding_sha256", "source"], delimiter="\t")
        writer.writeheader()
        writer.writerows(categories)
    table = render_table(summary)
    (args.output_dir / "comparison.md").write_text(table, encoding="utf-8")
    if args.figures_dir:
        write_figure(args.figures_dir / "evidence-loss-rates.svg", "Source-evidence loss rates",
                     [(run["run_name"], run[LOSS_FLAGS[0]]["rate"] * 100, run[LOSS_FLAGS[1]]["rate"] * 100)
                      for run in summary["per_run"]] + [("Mean", summary["mean"][LOSS_FLAGS[0]]["rate"] * 100,
                                                       summary["mean"][LOSS_FLAGS[1]]["rate"] * 100)], unit="%")
        write_figure(args.figures_dir / "evidence-loss-categories.svg", "Mean losses by category",
                     [(name, values["screenshot"], values["dom_model"])
                      for name, values in summary["mean_category_counts"].items()], unit="criteria")
        if population:
            formats = ("dom_model.txt", "dom_full.txt", "dom.json", "screenshot.png")
            sizes = [(name, sum(value["formats"][name]["bytes"] for value in population.values()) /
                      sum(value["formats"][name]["files"] for value in population.values()) / 1024) for name in formats]
            peak = max(value for _, value in sizes) or 1
            parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 260" role="img">',
                     '<title>Mean captured-state file sizes</title><rect width="100%" height="100%" fill="white"/>',
                     '<text x="20" y="30" font-family="sans-serif" font-size="18">Mean captured-state file sizes (KiB)</text>']
            for index, (name, size) in enumerate(sizes):
                y = 62 + index * 44
                color = ('#8b2332', '#e77b18', '#c4a67d', '#3c536d')[index]
                parts.extend([f'<text x="20" y="{y + 17}" font-family="sans-serif">{escape(name)}</text>',
                              f'<rect x="200" y="{y}" width="{500 * size / peak:.2f}" height="24" fill="{color}"/>',
                              f'<text x="720" y="{y + 17}" font-family="sans-serif">{size:.2f} KiB</text>'])
            (args.figures_dir / "recorded-file-sizes.svg").write_text('\n'.join(parts + ['</svg>']) + '\n', encoding='utf-8')
    if args.readme:
        if args.readme.read_text(encoding="utf-8") != readme_text:
            raise ValueError("README changed during aggregation")
        before, rest = readme_text.split(start)
        _, after = rest.split(end)
        args.readme.write_text(before + start + "\n\n" + table + "\n" + end + after, encoding="utf-8")
    print(json.dumps({"runs": summary["k"], "tasks_per_run": summary["tasks_per_run"], "output": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
