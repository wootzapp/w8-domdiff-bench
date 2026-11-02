"""Combine complete evidence-audit passes without contacting any model."""

from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path
import random
import re
import shutil
from statistics import quantiles

from .common import canonical_sha256
from .evidence_audit import SCHEMA_VERSION


FLAGS = (
    "screenshot_evidence_loss", "dom_model_evidence_loss",
    "screenshot_verifier_miss", "dom_model_verifier_miss",
)
PROTOCOL_FIELDS = ("schema_version", "prompt_version", "audit_model", "adjudicator_model")


def _protocol(audit: dict) -> dict:
    if not isinstance(audit, dict):
        raise ValueError("Audit file must contain an object")
    if any(not isinstance(audit.get(key), str) or not audit[key] for key in PROTOCOL_FIELDS):
        raise ValueError("Every audit must record schema, prompt and both models")
    if audit["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"Unsupported audit schema: {audit['schema_version']}")
    settings = audit.get("generation_settings", {})
    if not isinstance(settings, dict):
        raise ValueError("Generation settings must be an object")
    stages = {}
    for stage, model_key in (("inventory", "audit_model"), ("adjudication", "adjudicator_model")):
        setting = settings.get(stage, {})
        if not isinstance(setting, dict):
            raise ValueError(f"Generation settings must be an object for {stage}")
        requested, actual = setting.get("requested"), setting.get("actual")
        provider = setting.get("provider")
        if provider not in {"google", "openai"} or "api_version" not in setting:
            raise ValueError(f"Missing or inconsistent provider/API version for {stage}")
        if not isinstance(requested, dict) or not requested or not isinstance(actual, list) or not actual:
            raise ValueError(f"Actual generation settings are required for {stage}")
        if any(value != requested for value in actual):
            raise ValueError(f"Generation settings changed within {stage}")
        stages[stage] = {"provider": provider, "api_version": setting["api_version"], "settings": requested}
    return {**{key: audit[key] for key in PROTOCOL_FIELDS}, "generation_settings": stages}


def _flags(row: dict) -> dict:
    flags = {key: row.get(key) for key in FLAGS[:2]}
    for side in ("screenshot", "dom_model"):
        modality = row.get(side)
        caught = modality.get("verifier_caught") if isinstance(modality, dict) else None
        if type(caught) is not bool:
            raise ValueError("Every criterion must record boolean verifier_caught flags")
        flags[side + "_verifier_miss"] = not caught
    if any(type(value) is not bool for value in flags.values()):
        raise ValueError("Every criterion must record boolean loss flags")
    adjudication = row.get("adjudication")
    if not isinstance(adjudication, dict) or any(
        not isinstance(adjudication.get(key), dict)
        or adjudication[key].get("confirmed") is not value for key, value in flags.items()
    ):
        raise ValueError("Final flags and adjudication must agree")
    return flags


def _loss_totals(tasks: list[dict]) -> dict:
    """Bootstrap paired tasks, retaining all criteria in each selected task."""
    rows = [row for task in tasks for row in task["criteria"]]
    ties = sum(row["votes"][key]["majority"] is None for row in rows for key in FLAGS[:2])
    base = {"total_criteria": len(rows), "unresolved_loss_labels": ties,
            "confidence_method": "paired_task_cluster_percentile_bootstrap",
            "confidence_level": 0.95, "resampling_unit": "task", "seed": 0,
            "requested_resamples": 20000, "clusters": len(tasks)}
    if ties:
        return {**base, "status": "unresolved_ties", "screenshot_evidence_loss": None,
                "dom_model_evidence_loss": None, "relative_reduction": None}
    clusters = [(len(task["criteria"]),
                 sum(row["votes"][FLAGS[0]]["majority"] for row in task["criteria"]),
                 sum(row["votes"][FLAGS[1]]["majority"] for row in task["criteria"]))
                for task in tasks]
    n = sum(value[0] for value in clusters)
    s, d = (sum(value[index] for value in clusters) for index in (1, 2))
    distributions = [[], [], [], []]
    undefined = 0
    if len(clusters) >= 2:
        rng = random.Random(0)
        for _ in range(20000):
            sample = rng.choices(clusters, k=len(clusters))
            count, screen, dom = (sum(value[index] for value in sample) for index in range(3))
            distributions[0].append(screen / count)
            distributions[1].append(dom / count)
            distributions[2].append((screen - dom) / count)
            if screen:
                distributions[3].append((screen - dom) / screen)
            else:
                undefined += 1
    results = {}
    for name, estimate, values in zip(
        (*FLAGS[:2], "screenshot_minus_dom_loss_rate", "relative_reduction"),
        (s / n, d / n, (s - d) / n, (s - d) / s if s else None), distributions,
    ):
        ci = quantiles(values, n=40, method="inclusive") if len(values) >= 2 else None
        results[name] = {"estimate": estimate, "ci95": [ci[0], ci[-1]] if ci else None,
                         "status": ("degenerate" if min(values) == max(values) else "estimated")
                         if ci else "all_resamples_undefined" if len(clusters) >= 2 else "insufficient_tasks"}
    for key, count in zip(FLAGS[:2], (s, d)):
        results[key].update(count=count, denominator=n, rate=count / n)
    results["relative_reduction"].update(
        defined_resamples=len(distributions[3]), undefined_resamples=undefined,
        performed_resamples=len(distributions[3]) + undefined,
        conditional_on="resampled screenshot loss count > 0",
    )
    return {**base, "status": "complete", **results,
            "interpretation": "Intervals hold majority labels fixed and do not measure annotation error."}


def combine_passes(pass_roots: list[Path], *, sample_seed: int = 0,
                   review_order_seed: int = 1,
                   expected_tasks: int | None = None) -> tuple[dict, list[dict], list[dict]]:
    roots = [Path(root).resolve(strict=True) for root in pass_roots]
    if not roots or len(set(roots)) != len(roots):
        raise ValueError("Provide distinct nonempty audit-set directories")
    if any(not root.is_dir() for root in roots):
        raise ValueError("Each audit set must be a directory")
    if any(a.is_relative_to(b) or b.is_relative_to(a) for a, b in combinations(roots, 2)):
        raise ValueError("Audit-set directories must not overlap")
    passes, source_files, protocol = [], [], None
    for root in roots:
        tasks, files = {}, {}
        for path in sorted(root.rglob("evidence_audit.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            current = _protocol(value)
            task_id = value.get("task_id")
            if not isinstance(task_id, str) or not task_id or task_id in tasks:
                raise ValueError("Missing or duplicate task identity within a pass")
            if protocol is None:
                protocol = current
            if current != protocol:
                raise ValueError("Audit protocol mismatch across passes/tasks")
            rows = value.get("criteria")
            if not isinstance(rows, list) or not rows:
                raise ValueError("Every task must contain a complete nonempty criterion list")
            if any(not isinstance(row, dict) for row in rows):
                raise ValueError("Every criterion must be an object")
            indices = [row.get("criterion_index") for row in rows]
            if any(type(index) is not int for index in indices) or sorted(indices) != list(range(len(rows))):
                raise ValueError("Incomplete or duplicate criterion indices")
            rows.sort(key=lambda row: row["criterion_index"])
            for row in rows:
                if not isinstance(row.get("criterion"), str) or not row["criterion"]:
                    raise ValueError("Missing criterion text")
                _flags(row)
            rubric = value.get("frozen_rubric_sha256")
            fingerprints = value.get("input_fingerprints")
            if not isinstance(rubric, str) or not re.fullmatch("[0-9a-f]{64}", rubric):
                raise ValueError("Every audit must identify its frozen rubric hash")
            fingerprint_keys = {"frozen_rubric", "shared_trajectory", "screenshot_verifier_result",
                                "dom_verifier_result", "screenshot_sources", "dom_sources"}
            if not isinstance(fingerprints, dict) or set(fingerprints) != fingerprint_keys:
                raise ValueError("Complete input fingerprints are required")
            if fingerprints["frozen_rubric"] != rubric:
                raise ValueError("Input fingerprints disagree with frozen rubric")
            hashes = [fingerprints[key] for key in fingerprint_keys - {"screenshot_sources", "dom_sources"}]
            for key in ("screenshot_sources", "dom_sources"):
                if not isinstance(fingerprints[key], dict):
                    raise ValueError("Source fingerprints must be filename-to-hash mappings")
                hashes.extend(fingerprints[key].values())
            if any(not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value) for value in hashes):
                raise ValueError("Invalid input fingerprint")
            if not isinstance(value.get("shared_trajectory"), dict) or (
                fingerprints["shared_trajectory"] != canonical_sha256(value["shared_trajectory"])
            ):
                raise ValueError("Shared trajectory fingerprint mismatch")
            evidence = value.get("evidence_paths")
            if not isinstance(evidence, dict) or set(evidence) != {"screenshots", "dom_states", "action_history"}:
                raise ValueError("Evidence paths are required for blind review")
            for key in ("screenshots", "dom_states"):
                if not isinstance(evidence[key], list) or any(not isinstance(path, str) or not path for path in evidence[key]):
                    raise ValueError("Evidence paths must contain lists of paths")
            history = evidence["action_history"]
            if (not isinstance(history, dict) or set(history) != {"screenshot", "dom_model"}
                    or any(not isinstance(path, str) or not path for path in history.values())):
                raise ValueError("Both action-history paths are required")
            tasks[task_id], files[task_id] = value, path.relative_to(root).as_posix()
        if not tasks or (expected_tasks is not None and len(tasks) != expected_tasks):
            raise ValueError("Incomplete audit set or unexpected task count")
        if passes and tasks.keys() != passes[0].keys():
            raise ValueError("Every pass must contain the identical complete task set")
        passes.append(tasks)
        source_files.append(files)
    k = len(passes)
    combined, rows_for_agreement = [], []
    for task_id in sorted(passes[0]):
        task_passes = [items[task_id] for items in passes]
        reference = task_passes[0]
        identity = lambda value: {
            "rubric": value["frozen_rubric_sha256"], "inputs": value["input_fingerprints"],
            "shared_trajectory": value.get("shared_trajectory"),
            "criteria": [{key: row.get(key) for key in ("criterion_index", "criterion", "description", "max_points")}
                         for row in value["criteria"]],
        }
        if any(identity(value) != identity(reference) for value in task_passes[1:]):
            raise ValueError(f"Frozen inputs or criteria differ for {task_id}")
        merged = []
        for index, row in enumerate(reference["criteria"]):
            votes = {}
            for key in FLAGS:
                values = [_flags(value["criteria"][index])[key] for value in task_passes]
                count = sum(values)
                votes[key] = {"flagged_passes": count, "passes": k, "pass_flags": values,
                              "majority": None if count * 2 == k else count * 2 > k,
                              "tie": count * 2 == k}
            result = {"task_id": task_id, "task_alias": reference.get("task_alias"),
                      "criterion_index": index, "criterion": row["criterion"], "votes": votes,
                      "audit_files": [files[task_id] for files in source_files],
                      "flagged_in_any_pass": any(v["flagged_passes"] for v in votes.values())}
            merged.append(result)
            rows_for_agreement.append(result)
        combined.append({"task_id": task_id, "task_alias": reference.get("task_alias"), "criteria": merged})
    agreement = {}
    for key in FLAGS:
        pairs = []
        for a, b in combinations(range(k), 2):
            labels = [row["votes"][key]["pass_flags"] for row in rows_for_agreement]
            same = sum(values[a] == values[b] for values in labels)
            both = sum(values[a] and values[b] for values in labels)
            positives = sum(values[a] + values[b] for values in labels)
            pairs.append({"passes": [a + 1, b + 1], "agreements": same,
                          "comparisons": len(labels), "rate": same / len(labels),
                          "positive_agreement": 2 * both / positives if positives else None})
        comparisons = sum(pair["comparisons"] for pair in pairs)
        same = sum(pair["agreements"] for pair in pairs)
        agreement[key] = {"agreements": same, "comparisons": comparisons,
                          "rate": same / comparisons if comparisons else None,
                          "unanimous_criteria": sum(len(set(row["votes"][key]["pass_flags"])) == 1
                                                    for row in rows_for_agreement), "pairs": pairs}
    flagged = [row for row in rows_for_agreement if row["flagged_in_any_pass"]]
    unflagged = [row for row in rows_for_agreement if not row["flagged_in_any_pass"]]
    sample = random.Random(sample_seed).sample(unflagged, min(75, len(unflagged)))
    selected = flagged + sample
    random.Random(review_order_seed).shuffle(selected)
    blind, review_key = [], []
    for row in selected:
        identity = {"task_id": row["task_id"], "task_alias": row["task_alias"],
                    "criterion_index": row["criterion_index"], "criterion": row["criterion"]}
        evidence = passes[0][row["task_id"]]["evidence_paths"]
        blind.append({**identity, "screenshots": json.dumps(evidence["screenshots"]),
                      "dom_states": json.dumps(evidence["dom_states"]),
                      "action_history": json.dumps(evidence["action_history"]),
                      "review_screenshot_loss": "", "review_dom_loss": "",
                      "review_screenshot_miss": "", "review_dom_miss": "", "review_notes": ""})
        review_key.append({**identity,
                           "selection": "flagged_in_any_pass" if row["flagged_in_any_pass"] else "seeded_unflagged_sample",
                           **{key + "_passes": row["votes"][key]["flagged_passes"] for key in FLAGS},
                           **{key + "_majority": row["votes"][key]["majority"] for key in FLAGS},
                           "audit_files": json.dumps(row["audit_files"])})
    returned_models = {
        stage: sorted({call["response_model"] for items in passes for value in items.values()
                       for call in value.get("calls", []) if call.get("stage") == stage
                       and isinstance(call.get("response_model"), str) and call["response_model"]})
        for stage in ("inventory", "adjudication")
    }
    result = {"schema_version": "evidence-audit-k-pass/v1", "protocol": deepcopy(protocol),
              "created_at": datetime.now(timezone.utc).isoformat(), "k": k,
              "task_count": len(combined), "expected_tasks": expected_tasks,
              "input_sets": [str(root) for root in roots], "tasks": combined,
              "pass_to_pass_agreement": agreement, "majority_vote_totals": _loss_totals(combined),
              "response_models": returned_models,
              "response_model_drift": any(len(models) > 1 for models in returned_models.values()),
              "human_review": {"flagged_criteria": len(flagged), "unflagged_pool": len(unflagged),
                               "source_loss_flagged_rows": sum(any(row["votes"][key]["flagged_passes"]
                                                                   for key in FLAGS[:2]) for row in flagged),
                               "verifier_miss_only_rows": sum(not any(row["votes"][key]["flagged_passes"]
                                                                      for key in FLAGS[:2]) for row in flagged),
                               "requested_sample": 75, "sampled_unflagged": len(sample),
                               "sampled_unflagged_rows": len(sample),
                               "sample_shortfall": max(0, 75 - len(sample)), "sample_seed": sample_seed,
                               "review_order_seed": review_order_seed,
                               "total_rows": len(blind), "review_completed": False},
              "limitations": ["Pass independence cannot be established from audit files alone.",
                              "Task completeness is relative to the supplied sets unless expected_tasks is given.",
                              "Ties remain unresolved; no loss totals are reported if a loss label ties."]}
    return result, blind, review_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("passes", type=Path, nargs="+", help="One complete audit directory per pass")
    parser.add_argument("--output-dir", type=Path, required=True, help="A new output directory")
    parser.add_argument("--sample-seed", type=int, default=0)
    parser.add_argument("--review-order-seed", type=int, default=1)
    parser.add_argument("--review-bundle", action="store_true", help="Copy reviewed evidence into the output directory")
    parser.add_argument("--expected-tasks", type=int)
    args = parser.parse_args(argv)
    if args.expected_tasks is not None and args.expected_tasks < 1:
        parser.error("--expected-tasks must be positive")
    output = args.output_dir.resolve()
    if output.exists():
        parser.error("Output directory already exists; inputs and outputs will not be overwritten")
    if any(output.is_relative_to(root.resolve()) for root in args.passes):
        parser.error("Output directory must be separate from all input passes")
    result, blind, review_key = combine_passes(args.passes, sample_seed=args.sample_seed,
                                              review_order_seed=args.review_order_seed,
                                              expected_tasks=args.expected_tasks)
    output.mkdir(parents=True)
    if args.review_bundle:
        copied = {}
        for row in blind:
            task_id = row["task_id"]
            if Path(task_id).name != task_id or task_id in {".", ".."} or "\\" in task_id:
                raise ValueError("Unsafe task ID for review bundle")
            if task_id not in copied:
                task_root = Path("review_bundle") / task_id
                paths = {}
                for field in ("screenshots", "dom_states"):
                    targets = []
                    for source in json.loads(row[field]):
                        source = Path(source)
                        source = (source if source.is_absolute() else Path(__file__).resolve().parents[2] / source).resolve(strict=True)
                        target = task_root / field / source.name
                        (output / target.parent).mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, output / target)
                        targets.append(target.as_posix())
                    paths[field] = json.dumps(targets)
                histories = {}
                for side, source in json.loads(row["action_history"]).items():
                    target = task_root / "action_history" / (side + ".log")
                    (output / target.parent).mkdir(parents=True, exist_ok=True)
                    source = Path(source)
                    source = (source if source.is_absolute() else Path(__file__).resolve().parents[2] / source).resolve(strict=True)
                    shutil.copy2(source, output / target)
                    histories[side] = target.as_posix()
                paths["action_history"] = json.dumps(histories)
                copied[task_id] = paths
            row.update(copied[task_id])
        result["review_bundle"] = {"enabled": True, "tasks": len(copied), "paths_relative_to": "output_directory"}
    (output / "combined_audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, rows in (("review_blind.csv", blind), ("review_key.csv", review_key)):
        with (output / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({"output": str(output), "k": result["k"], "tasks": result["task_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
