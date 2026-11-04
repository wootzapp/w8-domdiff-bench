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
import re
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
    for _ in range(resamples if len(clusters) > 1 else 0):
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
              "performed_resamples": len(distributions[0]), "statuses": {},
              "interpretation": "Sampling uncertainty with audit labels held fixed; not annotation error."}
    for key, values in zip((*LOSS_FLAGS, "rate_difference", "relative_reduction"), distributions):
        cutpoints = quantiles(values, n=40, method="inclusive") if len(values) >= 2 else None
        result[key] = [cutpoints[0], cutpoints[-1]] if cutpoints else None
        result["statuses"][key] = (
            "insufficient_tasks" if len(clusters) < 2 else
            "all_resamples_undefined" if not values else
            "insufficient_defined_resamples" if cutpoints is None else
            "degenerate" if min(values) == max(values) else "estimated"
        )
    return result


def aggregate_runs(roots: list[Path], *, expected_tasks: int = 100,
                   resamples: int = 20000, seed: int = 0,
                   excluded_tasks: tuple[str, ...] = ()) -> tuple[dict, list[dict]]:
    if not roots or len({Path(root).resolve() for root in roots}) != len(roots):
        raise ValueError("Provide distinct, complete run directories")
    if len({Path(root).name for root in roots}) != len(roots):
        raise ValueError("Provide distinct run names")
    runs, reference_protocol, reference = [], None, {}
    recording_sources, recording_identities, evidence_identities = {}, {}, {}
    catalog = {f"task_{number:02d}" for number in range(1, expected_tasks + 1)}
    if not set(excluded_tasks) <= catalog:
        raise ValueError("Exploratory exclusions contain unknown catalog tasks")
    reference_hashes, unscored = None, {}
    for root in roots:
        root = Path(root).resolve(strict=True)
        project_root = root.parent.parent
        manifest_path = project_root / "manifests" / f"{root.name}.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else None
        selected = {}
        if manifest is not None:
            for entry in manifest.get("entries", []):
                if entry.get("audit") is not None:
                    path = Path(entry["audit"])
                    path = (project_root / path).resolve(strict=True) if not path.is_absolute() else path.resolve(strict=True)
                    if not path.is_relative_to(root) or path in selected:
                        raise ValueError(f"Invalid or duplicate selected audit path: {root.name}")
                    selected[path] = entry["task_alias"]
        paths = sorted(selected) if manifest is not None else sorted(root.glob("task_*/**/evidence_audit.json"))
        tasks = {}
        for path in paths:
            value = json.loads(path.read_text())
            alias = value.get("task_alias")
            if not isinstance(alias, str) or alias in tasks:
                raise ValueError(f"Missing or duplicate task alias in {root.name}")
            if selected and selected[path] != alias:
                raise ValueError(f"Selected audit task differs from manifest: {root.name}/{alias}")
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
        if manifest is not None:
            entries = manifest.get("entries", [])
            indexed = {entry["task_alias"]: entry for entry in entries}
            if (manifest.get("run_name") != root.name or len(entries) != expected_tasks
                    or len(indexed) != len(entries) or set(indexed) != catalog):
                raise ValueError(f"Run manifest task set differs: {root.name}")
            hashes = {alias: entry.get("frozen_rubric_sha256") for alias, entry in indexed.items()}
            if any(not isinstance(value, str) or len(value) != 64 for value in hashes.values()):
                raise ValueError(f"Missing frozen rubric hash in manifest: {root.name}")
            unscored[root.name] = {}
            for alias, entry in indexed.items():
                if alias not in tasks:
                    if (entry.get("evaluation_status") != "not_scored"
                            or entry.get("captured_states") != 0 or entry.get("audit") is not None
                            or entry.get("unscored_reason") != "no_captured_state"):
                        raise ValueError(f"Unexplained missing audit: {root.name}/{alias}")
                    unscored[root.name][alias] = entry["unscored_reason"]
                elif (entry.get("evaluation_status", "complete") != "complete"
                        or hashes[alias] != tasks[alias]["signature"][0]):
                    raise ValueError(f"Audit and run manifest differ: {root.name}/{alias}")
        else:
            if len(tasks) != expected_tasks:
                raise ValueError(f"Expected {expected_tasks} tasks in {root.name}; found {len(tasks)}")
            hashes = {alias: entry["signature"][0] for alias, entry in tasks.items()}
            unscored[root.name] = {}
            indexed = {}
        if not set(tasks) <= catalog:
            raise ValueError("Run task sets differ from the expected catalog aliases")
        for alias, entry in tasks.items():
            source = Path(indexed.get(alias, {}).get("recording") or f"recordings/{root.name}/{alias}")
            source = (project_root / source).resolve() if not source.is_absolute() else source.resolve()
            if not source.is_relative_to(project_root):
                raise ValueError(f"Recording source escapes the run workspace: {alias}")
            source_manifest = source / "manifest.json"
            identity = None
            if source_manifest.is_file():
                if source in recording_sources and recording_sources[source] != root.name:
                    raise ValueError(f"Recording source reused across runs: {alias}")
                recording_sources[source] = root.name
                recorded = json.loads(source_manifest.read_text())
                started = recorded.get("started_at") or recorded.get("created_at")
                recorded_id = recorded.get("task_id")
                if started and recorded_id:
                    identity = (alias, recorded_id, started)
                    if identity in recording_identities and recording_identities[identity] != root.name:
                        raise ValueError(f"Recording identity reused across runs: {alias}")
                    recording_identities[identity] = root.name
            fingerprints = entry["audit"].get("input_fingerprints", {})
            if (not isinstance(fingerprints, dict) or any(
                    not isinstance(fingerprints.get(key), dict) or not fingerprints[key]
                    for key in ("screenshot_sources", "dom_sources"))):
                raise ValueError(f"Source fingerprints missing from audit: {alias}")
            digests = [fingerprints.get("frozen_rubric"), fingerprints.get("shared_trajectory"),
                       *fingerprints["screenshot_sources"].values(), *fingerprints["dom_sources"].values()]
            if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in digests):
                raise ValueError(f"Invalid source fingerprint: {alias}")
            if (fingerprints["frozen_rubric"] != entry["signature"][0]
                    or fingerprints["shared_trajectory"] != canonical_sha256(entry["audit"].get("shared_trajectory"))):
                raise ValueError(f"Shared trajectory or rubric fingerprint differs: {alias}")
            evidence_key = (alias, canonical_sha256({key: fingerprints[key] for key in
                            ("shared_trajectory", "screenshot_sources", "dom_sources")}))
            if evidence_key in evidence_identities:
                previous_identity = evidence_identities[evidence_key]
                if identity is None or previous_identity is None or identity == previous_identity:
                    raise ValueError(f"Repeated evidence requires distinct recording provenance: {alias}")
            evidence_identities[evidence_key] = identity
        if reference_hashes is None:
            reference_hashes = hashes
        elif hashes != reference_hashes:
            raise ValueError("Frozen rubric hashes differ between run catalogs")
        signatures = {alias: value["signature"] for alias, value in tasks.items()}
        for alias, signature in signatures.items():
            if alias in reference and signature != reference[alias]:
                raise ValueError("Frozen rubric hashes or criteria differ between runs")
            reference[alias] = signature
        runs.append((root, tasks))
    common = set.intersection(*(set(tasks) for _, tasks in runs))
    aliases = sorted(common - set(excluded_tasks))
    if not aliases:
        raise ValueError("No tasks have a validated audit in every run")
    clusters = [[(len(tasks[alias]["audit"]["criteria"]),
                  sum(row[LOSS_FLAGS[0]] for row in tasks[alias]["audit"]["criteria"]),
                  sum(row[LOSS_FLAGS[1]] for row in tasks[alias]["audit"]["criteria"]))
                 for _, tasks in runs] for alias in aliases]
    per_run, categories = [], []
    returned = {stage: set() for stage in ("inventory", "adjudication")}
    for run_index, (root, tasks) in enumerate(runs):
        rows = [row for alias in aliases for row in tasks[alias]["audit"]["criteria"]]
        metrics = calculate_metrics(rows)
        available_rows = [row for entry in tasks.values() for row in entry["audit"]["criteria"]]
        per_run.append({"run_name": root.name, "tasks": len(aliases), **metrics,
                        "available_tasks": len(tasks),
                        "available_metrics": calculate_metrics(available_rows),
                        "affected_tasks": sum(any(row[LOSS_FLAGS[0]] or row[LOSS_FLAGS[1]]
                                                  for row in tasks[alias]["audit"]["criteria"]) for alias in aliases),
                        "paired_outcomes": {
                            label: sum(row[LOSS_FLAGS[0]] == s and row[LOSS_FLAGS[1]] == d for row in rows)
                            for label, s, d in (("screenshot_only", True, False), ("dom_only", False, True),
                                                ("both", True, True), ("neither", False, False))},
                        "confidence_intervals": hierarchical_intervals(
                            [[task[run_index]] for task in clusters], resamples=resamples, seed=seed)})
        for alias, entry in tasks.items():
            audit = entry["audit"]
            if any(not any(call.get("stage") == stage and call.get("response_model")
                           for call in audit.get("calls", [])) for stage in returned):
                raise ValueError(f"Audit lacks returned-model provenance: {alias}")
            for call in audit.get("calls", []):
                if call.get("stage") in returned and call.get("response_model"):
                    returned[call["stage"]].add(call["response_model"])
            if alias not in aliases:
                continue
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
    if any(len(values) > 1 for values in returned.values()):
        raise ValueError("Returned model versions differ across the selected audits")
    return {"schema_version": "recorded-run-comparison/v1", "created_at": datetime.now(timezone.utc).isoformat(),
            "aggregation": "mean_across_independent_recorded_runs", "protocol": reference_protocol,
            "run_names": [root.name for root, _ in runs], "k": len(runs), "tasks_per_run": len(aliases),
            "catalog_tasks": expected_tasks,
            "coverage": {"compared_tasks": aliases, "unscored_tasks": unscored,
                         "outside_common_panel": sorted(catalog - common),
                         "analysis_excluded_tasks": sorted(set(excluded_tasks)),
                         "policy": "Use identical audited tasks across runs; never treat missing audits as zero loss."},
            "criteria_per_run": sum(len(reference[alias][1]) for alias in aliases),
            "per_run": per_run, "mean": means,
            "mean_paired_outcomes": {label: mean(run["paired_outcomes"][label] for run in per_run)
                                      for label in ("screenshot_only", "dom_only", "both", "neither")},
            "mean_verifier_misses": {key: {"count": mean(run[key]["count"] for run in per_run),
                                            "rate": mean(run[key]["rate"] for run in per_run)}
                                      for key in ("screenshot_verifier_misses", "dom_model_verifier_misses")},
            "relative_reduction": (s - d) / s if s else None,
            "confidence_intervals": hierarchical_intervals(clusters, resamples=resamples, seed=seed),
            "response_models": {key: sorted(values) for key, values in returned.items()},
            "response_model_drift": any(len(values) > 1 for values in returned.values()),
            "frozen_rubrics": reference_hashes}, categories


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
        if key == "rate_difference":
            estimate_text = f"{estimate * 100:.2f} pp" if estimate is not None else "undefined"
            interval_text = f"{interval[0] * 100:.2f} to {interval[1] * 100:.2f} pp" if interval is not None else "undefined"
        else:
            estimate_text = f"{estimate:.2%}" if estimate is not None else "undefined"
            interval_text = f"{interval[0]:.2%} to {interval[1]:.2%}" if interval is not None else "undefined"
        lines.append(f"| {label} | {estimate_text} | {interval_text} |")
    lines.extend(["", f"The matched comparison uses {summary['tasks_per_run']} of {summary['catalog_tasks']} catalog tasks in every run.",
                  "Intervals resample tasks, then recorded runs within each task, keeping both representations together."])
    if summary["coverage"]["outside_common_panel"]:
        lines.extend(["", "Recordings without captured states remain recorded execution errors, not zero-loss audits.",
                      "Tasks outside the common panel: " + ", ".join(summary["coverage"]["outside_common_panel"]) + ".",
                      "", "| Run | Available audited tasks | Available criteria | Screenshot losses | DOM losses |",
                      "| --- | ---: | ---: | ---: | ---: |"])
        for run in summary["per_run"]:
            metrics = run["available_metrics"]
            lines.append(f"| {run['run_name']} | {run['available_tasks']} | {metrics['total_criteria']} | "
                         f"{metrics[LOSS_FLAGS[0]]['count']} | {metrics[LOSS_FLAGS[1]]['count']} |")
    return "\n".join(lines) + "\n"


def write_figure(path: Path, title: str, rows: list[tuple[str, float, float]], *, unit: str,
                 series: tuple[str, str] = ("Screenshots", "DOM"), intervals: list | None = None) -> None:
    """Write matching vector and raster charts from the same drawing."""
    from cairosvg import svg2png
    peak = max((max(s, d) for _, s, d in rows), default=1) or 1
    if intervals:
        if len(intervals) != len(rows):
            raise ValueError("Figure interval rows must match the plotted rows")
        peak = max(peak, max((bound for pair in intervals for interval in pair
                              if interval is not None for bound in interval), default=peak))
    width, height = 880, 120 + 58 * len(rows)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
             f'<title>{escape(title)}</title>', '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="20" y="28" font-family="sans-serif" font-size="18">{escape(title)}</text>',
             f'<text x="220" y="55" fill="#e77b18" font-family="sans-serif">{escape(series[0])}</text>',
             f'<text x="380" y="55" fill="#8b2332" font-family="sans-serif">{escape(series[1])}</text>']
    for index, (label, s, d) in enumerate(rows):
        y = 83 + index * 58
        parts.append(f'<text x="20" y="{y + 12}" font-family="sans-serif" font-size="13">{escape(label)}</text>')
        for side, (offset, value, color) in enumerate(((0, s, '#e77b18'), (21, d, '#8b2332'))):
            size = 500 * value / peak
            parts.extend([f'<rect x="230" y="{y + offset}" width="{size:.2f}" height="16" fill="{color}"/>',
                          f'<text x="{740}" y="{y + offset + 13}" font-family="sans-serif" font-size="13">{value:.2f} {unit}</text>'])
            if intervals and intervals[index][side] is not None:
                low, high = (230 + 500 * bound / peak for bound in intervals[index][side])
                middle = y + offset + 8
                parts.extend([f'<path d="M {low:.2f} {middle} H {high:.2f} '
                              f'M {low:.2f} {middle - 4} V {middle + 4} '
                              f'M {high:.2f} {middle - 4} V {middle + 4}" stroke="#222" stroke-width="1.5"/>'])
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = '\n'.join(parts + ['</svg>']) + '\n'
    raster = svg2png(bytestring=svg.encode('utf-8'), scale=2)
    path.write_text(svg, encoding='utf-8')
    path.with_suffix('.png').write_bytes(raster)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--expected-tasks", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--readme", type=Path)
    parser.add_argument("--figures-dir", type=Path)
    parser.add_argument("--recordings-root", type=Path, default=Path("recordings"))
    parser.add_argument("--categories", type=Path, help="Reviewed annotations keyed by run, task, criterion and finding hash")
    parser.add_argument("--exploratory-exclusions", default="",
                        help="Comma-separated catalog task aliases for a labelled exploratory view")
    parser.add_argument("--resamples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    if args.figures_dir:
        try:
            from cairosvg import svg2png
        except (ImportError, OSError) as error:
            raise ValueError("Figure rendering requires the figures extra and the Cairo system library") from error
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
    if args.exploratory_exclusions:
        excluded = tuple(value.strip() for value in args.exploratory_exclusions.split(",") if value.strip())
        subset, _ = aggregate_runs(args.runs, expected_tasks=args.expected_tasks,
                                   resamples=args.resamples, seed=args.seed, excluded_tasks=excluded)
        summary["exploratory_subset"] = {
            "excluded_task_ids": sorted(set(excluded)), "pre_specified": False,
            **{key: subset[key] for key in ("tasks_per_run", "criteria_per_run", "mean", "per_run",
                                            "mean_paired_outcomes", "mean_verifier_misses",
                                            "relative_reduction", "confidence_intervals")},
            "mean_category_counts": {
                name: {side: sum(row["task"] not in excluded and row["category"] == name
                                 and row["representation"] == side for row in categories) / summary["k"]
                       for side in ("screenshot", "dom_model")} for name in names}}
    population, outcomes = {}, {}
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
        manifests = list(folder.glob("task_*/manifest.json"))
        if manifests:
            if len(manifests) != population[run_name]["tasks"]:
                raise ValueError(f"Incomplete recording status population: {run_name}")
            outcomes[run_name] = dict(Counter(json.loads(path.read_text())["status"] for path in manifests))
    if population and len(population) != len(summary["run_names"]):
        raise ValueError("Recorded file-size population is missing a selected run")
    pooled = {}
    for name in ("screenshot.png", "dom_model.txt", "dom_full.txt", "dom.json"):
        count = sum(run["formats"][name]["files"] for run in population.values())
        size = sum(run["formats"][name]["bytes"] for run in population.values())
        if count:
            pooled[name] = {"files": count, "bytes": size, "mean_kib": size / count / 1024,
                            "mean_kb": size / count / 1000}
    summary["recorded_file_sizes"] = {"unit": "KiB", "bytes_per_kib": 1024,
                                       "population": "All captured states in the listed recorded runs",
                                       "recordings": sum(run["tasks"] for run in population.values()),
                                       "per_run": population, "pooled": pooled}
    summary["recorded_outcomes"] = outcomes
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "summary.json", summary)
    with (args.output_dir / "evidence_categories.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["run_name", "task", "criterion_index", "representation", "category", "rationale", "finding_sha256", "source"], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(categories)
    table = render_table(summary)
    (args.output_dir / "comparison.md").write_text(table, encoding="utf-8")
    if args.figures_dir:
        rate_rows = [(run["run_name"], run[LOSS_FLAGS[0]]["rate"] * 100,
                      run[LOSS_FLAGS[1]]["rate"] * 100) for run in summary["per_run"]]
        rate_rows.append(("Mean", summary["mean"][LOSS_FLAGS[0]]["rate"] * 100,
                          summary["mean"][LOSS_FLAGS[1]]["rate"] * 100))
        rate_intervals = [tuple([value * 100 for value in run["confidence_intervals"][flag]]
                                if run["confidence_intervals"][flag] is not None else None
                                for flag in LOSS_FLAGS) for run in summary["per_run"]]
        rate_intervals.append(tuple([value * 100 for value in summary["confidence_intervals"][flag]]
                                     if summary["confidence_intervals"][flag] is not None else None
                                     for flag in LOSS_FLAGS))
        if summary.get("exploratory_subset"):
            subset = summary["exploratory_subset"]
            rate_rows.append(("Listed IDs excluded", subset["mean"][LOSS_FLAGS[0]]["rate"] * 100,
                              subset["mean"][LOSS_FLAGS[1]]["rate"] * 100))
            rate_intervals.append(tuple([value * 100 for value in subset["confidence_intervals"][flag]]
                                         if subset["confidence_intervals"][flag] is not None else None
                                         for flag in LOSS_FLAGS))
        write_figure(args.figures_dir / "evidence-loss-rates.svg", "Source-evidence loss rates",
                     rate_rows, unit="%", intervals=rate_intervals)
        category_rows = [(name, values["screenshot"], values["dom_model"])
                         for name, values in summary["mean_category_counts"].items()]
        if summary.get("exploratory_subset"):
            category_rows.extend(("Subset: " + name, values["screenshot"], values["dom_model"])
                                 for name, values in subset["mean_category_counts"].items())
            write_figure(args.figures_dir / "exclusion-waterfall.svg", "Mean loss counts by analysis",
                         [("Matched panel", summary["mean"][LOSS_FLAGS[0]]["count"],
                           summary["mean"][LOSS_FLAGS[1]]["count"]),
                          ("Listed IDs excluded", subset["mean"][LOSS_FLAGS[0]]["count"],
                           subset["mean"][LOSS_FLAGS[1]]["count"])], unit="criteria")
        write_figure(args.figures_dir / "evidence-loss-categories.svg", "Mean losses by category",
                     category_rows, unit="criteria")
        paired = summary["mean_paired_outcomes"]
        write_figure(args.figures_dir / "paired-outcomes.svg", "Mean paired outcomes",
                     [("Exclusive loss", paired["screenshot_only"], paired["dom_only"]),
                      ("Both lose", paired["both"], paired["both"]),
                      ("Neither loses", paired["neither"], paired["neither"])], unit="criteria")
        write_figure(args.figures_dir / "task-coverage.svg", "Recorded and audited task counts",
                     [(run["run_name"], summary["catalog_tasks"], run["available_tasks"])
                      for run in summary["per_run"]], unit="tasks", series=("Recordings", "Audited tasks"))
        write_figure(args.figures_dir / "verifier-miss-rates.svg", "Verifier interpretation-miss rates",
                     [(run["run_name"], run["screenshot_verifier_misses"]["rate"] * 100,
                       run["dom_model_verifier_misses"]["rate"] * 100) for run in summary["per_run"]]
                     + [("Mean", summary["mean_verifier_misses"]["screenshot_verifier_misses"]["rate"] * 100,
                         summary["mean_verifier_misses"]["dom_model_verifier_misses"]["rate"] * 100)], unit="%")
        if population:
            formats = ("dom_model.txt", "dom_full.txt", "dom.json")
            sizes = [(name, sum(value["formats"][name]["bytes"] for value in population.values()) /
                      sum(value["formats"][name]["files"] for value in population.values()) / 1024) for name in formats]
            peak = max(value for _, value in sizes) or 1
            parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 260" role="img">',
                     '<title>Mean captured-state file sizes</title><rect width="100%" height="100%" fill="white"/>',
                     '<text x="20" y="30" font-family="sans-serif" font-size="18">Mean captured-state file sizes (KiB)</text>']
            for index, (name, size) in enumerate(sizes):
                y = 62 + index * 44
                color = ('#8b2332', '#e77b18', '#c4a67d')[index]
                parts.extend([f'<text x="20" y="{y + 17}" font-family="sans-serif">{escape(name)}</text>',
                              f'<rect x="200" y="{y}" width="{500 * size / peak:.2f}" height="24" fill="{color}"/>',
                              f'<text x="720" y="{y + 17}" font-family="sans-serif">{size:.2f} KiB</text>'])
            svg = '\n'.join(parts + ['</svg>']) + '\n'
            raster = svg2png(bytestring=svg.encode('utf-8'), scale=2)
            (args.figures_dir / "representation-sizes.svg").write_text(svg, encoding='utf-8')
            (args.figures_dir / "representation-sizes.png").write_bytes(raster)
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
