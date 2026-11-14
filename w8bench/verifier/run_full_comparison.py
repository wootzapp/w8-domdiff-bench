#!/usr/bin/env python3
"""Aggregate actor efficiency, completion and within-run evaluation receipts."""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics
from typing import Any

from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.task_recorder.recorder_support import write_json
from .compare_results import compare, summarize


def aggregate(pairs: list[dict[str, Any]], *, pass_k: list[int] | None = None) -> dict[str, Any]:
    """Aggregate any number of matched trials, retaining task/criterion identity."""
    if not pairs:
        raise ValueError("no matched task pairs")
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    identities = set()
    for pair in pairs:
        identity = (pair.get("trial_id", "run_1"), pair["task_id"])
        if identity in identities:
            raise ValueError(f"duplicate trial/task attempt: {identity}")
        identities.add(identity)
        by_task[pair["task_id"]].append(pair)
    catalog_hashes = {pair.get("catalog_sha256", pair["dom"].get("catalog_sha256")) for pair in pairs}
    if len(catalog_hashes) != 1:
        raise ValueError("selected catalog hashes differ across arms, tasks or trials")
    controls = {json.dumps(pair["shared_controls"], sort_keys=True) for pair in pairs}
    if len(controls) != 1:
        raise ValueError("shared actor controls differ across trials/tasks")
    models = {model for pair in pairs for mode in ("dom", "screenshot")
              for model in pair[mode]["returned_actor_models"]}
    if len(models) > 1:
        raise ValueError("returned actor model versions differ across trials")
    trial_counts = {task_id: len(attempts) for task_id, attempts in sorted(by_task.items())}
    ks = sorted(set(pass_k)) if pass_k is not None else list(range(1, min(trial_counts.values()) + 1))
    if not ks or any(type(k) is not int or k <= 0 for k in ks):
        raise ValueError("pass@k values must be positive integers")
    if any(n < max(ks) for n in trial_counts.values()):
        raise ValueError("requested pass@k needs at least k attempts for every retained task")
    result = {"paired_tasks": len(by_task), "paired_attempts": len(pairs),
        "trial_ids": sorted({str(identity[0]) for identity in identities}),
        "trials_per_task": trial_counts, "balanced_trial_counts": len(set(trial_counts.values())) == 1,
        "evaluated_k": ks, "catalog_sha256": next(iter(catalog_hashes)), "modes": {}, "per_task": {}}
    for task_id, attempts in sorted(by_task.items()):
        result["per_task"][task_id] = {}
        evaluation_hashes = {pair[mode]["evaluation"]["rubric_sha256"] for pair in attempts
            for mode in ("dom", "screenshot") if pair[mode].get("evaluation")}
        if len(evaluation_hashes) > 1:
            raise ValueError(f"frozen evaluation rubric differs across trials for {task_id}")
        task_grades = [pair[mode]["completion"] for pair in attempts for mode in ("dom", "screenshot")
            if pair[mode]["completion"].get("method") != "ungraded"]
        signatures = {json.dumps({key: grade.get(key) for key in (
            "rubric_sha256", "evidence_policy", "method", "judge_model", "returned_judge_model",
            "judge_prompt_sha256", "judge_base_url", "max_output_tokens", "judge_schema_sha256")},
            sort_keys=True) for grade in task_grades}
        task_criterion_sets = {tuple(c["id"] for c in grade.get("criteria", [])) for grade in task_grades}
        if len(signatures) > 1 or len(task_criterion_sets) > 1:
            raise ValueError(f"frozen rubric or grading controls differ across trials for {task_id}")
        for mode in ("dom", "screenshot"):
            grades = [pair[mode]["completion"] for pair in attempts]
            graded = [grade for grade in grades if grade.get("method") != "ungraded"]
            if graded:
                signatures = {json.dumps({key: grade.get(key) for key in (
                    "rubric_sha256", "evidence_policy", "method", "judge_model", "returned_judge_model",
                    "judge_prompt_sha256", "judge_base_url", "max_output_tokens", "judge_schema_sha256")},
                    sort_keys=True) for grade in graded}
                criterion_sets = {tuple(c["id"] for c in grade.get("criteria", [])) for grade in graded}
                if len(signatures) > 1 or len(criterion_sets) > 1:
                    raise ValueError(f"frozen rubric or grading controls differ across trials for {task_id}")
            verdicts = Counter(grade["verdict"] for grade in grades)
            n, c = len(grades), verdicts["success"]
            u = verdicts["uncertain"] + verdicts["ungraded"]
            estimates = {}
            for k in ks:
                lower = 1 - (math.comb(n-c, k) / math.comb(n, k) if n-c >= k else 0)
                upper = 1 - (math.comb(n-c-u, k) / math.comb(n, k) if n-c-u >= k else 0)
                estimates[str(k)] = {"estimate": lower if lower == upper else None,
                    "confirmed_lower": lower, "possible_upper": upper}
            criteria = {}
            criterion_ids = [item["id"] for item in graded[0].get("criteria", [])] if graded else []
            for criterion_id in criterion_ids:
                outcomes = Counter(next((item["verdict"] for item in grade.get("criteria", [])
                    if item["id"] == criterion_id), "ungraded") for grade in grades)
                criterion_c = outcomes["success"]
                criterion_u = outcomes["uncertain"] + outcomes["ungraded"]
                criterion_estimates = {}
                for k in ks:
                    lower = 1 - (math.comb(n-criterion_c, k) / math.comb(n, k) if n-criterion_c >= k else 0)
                    upper = 1 - (math.comb(n-criterion_c-criterion_u, k) / math.comb(n, k)
                        if n-criterion_c-criterion_u >= k else 0)
                    criterion_estimates[str(k)] = {"estimate": lower if lower == upper else None,
                        "confirmed_lower": lower, "possible_upper": upper}
                criteria[criterion_id] = {"verdict_counts": dict(outcomes),
                    "confirmed_success_rate": criterion_c/n, "definitively_graded": n-criterion_u,
                    "pass_at_k": criterion_estimates}
            result["per_task"][task_id][mode] = {"attempts": n, "completion_counts": dict(verdicts),
                "definitively_graded": n-u, "pass_at_k": estimates,
                "all_trials_success_confirmed": c == n, "all_trials_success_possible": c+u == n,
                "criteria": criteria,
                "all_trials_tokens": sum((pair[mode]["token_usage"]["total_tokens"] or 0) for pair in attempts)
                    if any(pair[mode]["token_usage"]["total_tokens"] is not None for pair in attempts) else None,
                "token_usage_coverage": dict(Counter(pair[mode].get("cost_coverage", "unknown") for pair in attempts)),
                "all_trials_turns": sum(pair[mode]["model_turns"] for pair in attempts)}
    for mode in ("dom", "screenshot"):
        rows = [pair[mode] for pair in pairs]
        verdicts = Counter(row["completion"]["verdict"] for row in rows)
        successes = [row for row in rows if row["completion"]["verdict"] == "success"]
        definitive = verdicts["success"] + verdicts["failure"]
        turns_complete = all(row.get("turns_complete", True) for row in rows)
        tokens_complete = all(row.get("cost_coverage", "complete") == "complete" and not row["turns_missing_usage"] for row in rows)
        result["modes"][mode] = {
            "attempted_tasks": len(by_task), "attempted_runs": len(rows), "completion_counts": dict(verdicts),
            "confirmed_success_rate_all_attempts": verdicts["success"] / len(rows),
            "success_rate_definitively_graded": verdicts["success"] / definitive if definitive else None,
            "definitively_graded_tasks": definitive,
            "definitively_graded_runs": definitive,
            "turns_complete": turns_complete, "tokens_complete": tokens_complete,
            "cost_coverage": dict(Counter(row.get("cost_coverage","complete") for row in rows)),
            "mean_turns_all_attempts": statistics.mean(row["model_turns"] for row in rows) if turns_complete else None,
            "mean_turns_all_attempts_lower_bound": statistics.mean(row["model_turns"] for row in rows),
            "median_turns_all_attempts": statistics.median(row["model_turns"] for row in rows) if turns_complete else None,
            "mean_turns_successful_tasks": statistics.mean(row["model_turns"] for row in successes) if successes else None,
            "actor_turns": sum(row["model_turns"] for row in rows),
            "output_limit_hits": sum(row.get("output_limit_hits",0) for row in rows),
            "token_usage_known_calls": {key: sum(row.get("token_usage_known_calls", {}).get(key, 0) for row in rows) for key in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens")},
            "action_attempts": sum(row["action_attempts"] for row in rows),
            "rejected_turns": sum(row["rejected_turns"] for row in rows),
            "actor_seconds": sum(row["actor_latency_seconds"] for row in rows),
            "tokens": sum((row["token_usage"]["total_tokens"] or 0) for row in rows) if any(row["token_usage"]["total_tokens"] is not None for row in rows) else None,
            "token_usage": {key: sum((row["token_usage"].get(key, 0) or 0) for row in rows) if any(row["token_usage"].get(key) is not None for row in rows) else None
                for key in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens")},
            "mean_tokens_all_attempts": statistics.mean((row["token_usage"]["total_tokens"] or 0) for row in rows) if tokens_complete else None,
            "mean_tokens_all_attempts_lower_bound": statistics.mean((row["token_usage"]["total_tokens"] or 0) for row in rows) if any(row["token_usage"]["total_tokens"] is not None for row in rows) else None,
            "median_tokens_all_attempts": statistics.median((row["token_usage"]["total_tokens"] or 0) for row in rows) if tokens_complete else None,
            "mean_tokens_successful_attempts": statistics.mean((row["token_usage"]["total_tokens"] or 0) for row in successes) if successes and all(row.get("cost_coverage") == "complete" for row in successes) else None,
            "action_errors": sum(row["action_errors"] for row in rows),
            "model_error_turns": sum(row["model_error_turns"] for row in rows),
            "parse_error_turns": sum(row["parse_error_turns"] for row in rows),
            "run_status_counts": dict(Counter(row["run_status"] for row in rows)),
            "judge_usage": {key: sum(row.get("judge_usage", row["completion"].get("usage") or {}).get(key, 0) for row in rows)
                for key in ("input_tokens", "output_tokens", "total_tokens")},
            "judge_calls": sum(row.get("judge_calls", row["completion"].get("judge_calls", 0)) for row in rows),
            "judge_calls_missing_usage": sum(row.get("judge_calls_missing_usage",
                int(row["completion"].get("judge_calls", 0) > 0 and "input_tokens" not in (row["completion"].get("usage") or {}))) for row in rows),
            "turns_missing_usage": sum(row["turns_missing_usage"] for row in rows),
        }
        task_rows = [result["per_task"][task_id][mode] for task_id in by_task]
        result["modes"][mode]["pass_at_k"] = {str(k): {
            "estimate": statistics.mean(row["pass_at_k"][str(k)]["estimate"] for row in task_rows)
                if all(row["pass_at_k"][str(k)]["estimate"] is not None for row in task_rows) else None,
            "confirmed_lower": statistics.mean(row["pass_at_k"][str(k)]["confirmed_lower"] for row in task_rows),
            "possible_upper": statistics.mean(row["pass_at_k"][str(k)]["possible_upper"] for row in task_rows),
            "tasks": len(task_rows)} for k in ks}
        result["modes"][mode]["all_trials_success_rate_confirmed"] = sum(row["all_trials_success_confirmed"] for row in task_rows)/len(task_rows)
        result["modes"][mode]["all_trials_success_rate_possible"] = sum(row["all_trials_success_possible"] for row in task_rows)/len(task_rows)
    result["task_metadata"] = {}
    result["categories"] = {}
    result["audit_by_task_trial"] = []
    for pair in pairs:
        labels = {key: pair.get(key, pair["dom"].get(key)) for key in ("category", "difficulty")}
        if pair["task_id"] in result["task_metadata"] and result["task_metadata"][pair["task_id"]] != labels:
            raise ValueError("task category or difficulty differs across trials")
        result["task_metadata"][pair["task_id"]] = labels
        result["audit_by_task_trial"].append({"task_id": pair["task_id"], "trial_id": pair.get("trial_id"),
            **labels, **{mode: {"status": pair[mode].get("evidence_audit_status", "not_available"),
                "metrics": pair[mode].get("evidence_audit"), "coverage": pair[mode].get("evaluation_coverage")}
                for mode in ("dom", "screenshot")}})
    groups = {"all": pairs}
    for category in ("medium", "hard", "complex", "unknown"):
        selected = [pair for pair in pairs if str(pair.get("difficulty") or pair.get("category") or "unknown").lower() == category
            or category == "unknown" and str(pair.get("difficulty") or pair.get("category") or "unknown").lower() not in {"medium", "hard", "complex"}]
        if selected:
            groups[category] = selected
    for category, selected in groups.items():
        target = result["modes"] if category == "all" else result["categories"].setdefault(category, {})
        for mode in ("dom", "screenshot"):
            rows = [pair[mode] for pair in selected]
            metrics = target.setdefault(mode, {})
            distributions = {}
            for key in ("model_turns", "input_tokens", "output_tokens", "total_tokens", "input_tokens_per_turn", "output_tokens_per_turn"):
                if key == "model_turns":
                    values = [row[key] for row in rows if row.get("turns_complete", True)]
                elif key.endswith("_per_turn"):
                    component = key.removesuffix("_per_turn")
                    values = [row.get("tokens_per_turn", {}).get(component, {}).get("known_usage_mean") for row in rows]
                else:
                    values = [row["token_usage"].get(key) for row in rows]
                values = [value for value in values if value is not None]
                distributions[key] = {"known_runs": len(values), "attempted_runs": len(rows),
                    "mean": statistics.mean(values) if values else None, "median": statistics.median(values) if values else None,
                    "min": min(values) if values else None, "max": max(values) if values else None, "values": values,
                    "usage_coverage": dict(Counter(row.get("cost_coverage", "unknown") for row in rows))}
            tpt = {}
            for component in ("input_tokens", "output_tokens"):
                observed = [row.get("tokens_per_turn", {}).get(component, {}) for row in rows]
                known_calls = sum(value.get("known_calls", 0) for value in observed)
                known_tokens = sum(value.get("tokens", 0) or 0 for value in observed)
                complete = all(value.get("coverage") == "complete" for value in observed) and all(row.get("turns_complete", True) for row in rows)
                tpt[component] = {"known_tokens": known_tokens if known_calls else None,
                    "known_calls": known_calls, "recorded_calls": sum(row["model_turns"] for row in rows),
                    "known_usage_mean": known_tokens / known_calls if known_calls else None,
                    "mean": known_tokens / known_calls if known_calls and complete else None,
                    "coverage": "complete" if complete else "partial" if known_calls else "none"}
            streams = {}
            for name in sorted({name for row in rows for name in row.get("judge_usage_streams", {})}):
                members = [row["judge_usage_streams"][name] for row in rows if name in row.get("judge_usage_streams", {})]
                totals, known_runs = {}, {}
                for component in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens"):
                    alternate = {"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens"}.get(component, component)
                    values = [(member.get("usage") or {}).get(component, (member.get("usage") or {}).get(alternate)) for member in members]
                    values = [value for value in values if isinstance(value, (int, float))]
                    totals[component] = sum(values) if values else None
                    known_runs[component] = len(values)
                streams[name] = {"usage": totals, "usage_known_runs": known_runs, "present_runs": len(members),
                    "attempted_runs": len(rows),
                    "calls": sum(member["calls"] for member in members) if all(isinstance(member.get("calls"), int) for member in members) else None,
                    "known_calls": sum(member.get("calls", 0) or 0 for member in members if isinstance(member.get("calls"), int)),
                    "usage_coverage": dict(Counter(member["usage_coverage"] for member in members))}
            directional = {}
            audited = [row for row in rows if row.get("evidence_audit") is not None]
            for key in ("screenshot_evidence_loss", "dom_model_evidence_loss", "screenshot_verifier_misses", "dom_model_verifier_misses"):
                values = [row["evidence_audit"][key] for row in audited if key in row["evidence_audit"]]
                denominator = sum(value["denominator"] for value in values)
                count = sum(value["count"] for value in values)
                directional[key] = {"count": count if values else None, "denominator": denominator if values else None,
                    "rate": count / denominator if denominator else None, "audited_runs": len(values), "attempted_runs": len(rows)}
            verdicts = Counter(row["completion"]["verdict"] for row in rows)
            definitive = verdicts["success"] + verdicts["failure"]
            auxiliary = {}
            for verifier in ("dom_model", "screenshot_verifier"):
                members = [row.get("auxiliary_verifiers", {}).get(verifier) for row in rows]
                completed = [member for member in members if member and member.get("status") == "complete"]
                signals = {}
                for key in {key for member in completed for key in member.get("signals", {})}:
                    values = [member.get("signals", {}).get(key) for member in completed]
                    values = [value for value in values if isinstance(value, (int, float))]
                    signals[key] = {"mean": statistics.mean(values) if values else None,
                        "median": statistics.median(values) if values else None, "known_runs": len(values)}
                fallback_keys = {key for member in members if member for key in member.get("fallback_counts", {})}
                auxiliary[verifier] = {"completed_runs": len(completed), "attempted_runs": len(rows),
                    "signals": signals,
                    "fallback_counts": {key: sum(member.get("fallback_counts", {}).get(key, 0) for member in members if member) for key in sorted(fallback_keys)},
                    "judgment_quality_counts": dict(Counter(member.get("judgment_quality", "unknown") if member else "not_available" for member in members)),
                    "validation_repair_events": sum(member.get("validation_repair_events", 0) for member in members if member),
                    "status_counts": dict(Counter(member.get("status") if member else "not_available" for member in members))}
            metrics.setdefault("token_usage", {key: sum(row["token_usage"].get(key) or 0 for row in rows)
                if any(row["token_usage"].get(key) is not None for row in rows) else None
                for key in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens")})
            metrics.setdefault("token_usage_known_calls", {key: sum(row.get("token_usage_known_calls", {}).get(key, 0) for row in rows)
                for key in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens")})
            metrics.update(attempted_runs=len(rows), completion_counts=dict(verdicts),
                confirmed_success_rate_all_attempts=verdicts["success"] / len(rows),
                success_rate_definitively_graded=verdicts["success"] / definitive if definitive else None,
                definitively_graded_runs=definitive, auxiliary_verifiers=auxiliary,
                distributions=distributions, tokens_per_turn=tpt,
                judge_usage_streams=streams,
                cost_streams={"actor": {"usage": metrics.get("token_usage"),
                    "usage_known_calls": metrics.get("token_usage_known_calls"),
                    "calls": sum(row["model_turns"] for row in rows),
                    "usage_coverage": dict(Counter(row.get("cost_coverage", "unknown") for row in rows))}, **streams},
                evidence_audit=directional,
                audit_status_counts=dict(Counter(row.get("evidence_audit_status", "not_available") for row in rows)),
                step_cap_hits=sum(row.get("step_cap_hit", False) for row in rows),
                step_cap_rate=sum(row.get("step_cap_hit", False) for row in rows) / len(rows),
                step_cap_known_runs=sum(row.get("step_cap_known", row.get("turns_complete", True)) for row in rows),
                step_cap_unknown_runs=sum(not row.get("step_cap_known", row.get("turns_complete", True)) for row in rows),
                step_cap_rate_known=(sum(row.get("step_cap_hit", False) for row in rows)
                    / sum(row.get("step_cap_known", row.get("turns_complete", True)) for row in rows))
                    if any(row.get("step_cap_known", row.get("turns_complete", True)) for row in rows) else None,
                hard_cap_200_hits=sum(row.get("step_cap_hit", False) and row.get("turn_budget") == 200 for row in rows),
                hard_cap_200_rate=sum(row.get("step_cap_hit", False) and row.get("turn_budget") == 200 for row in rows) / len(rows),
                output_limit_hit_rate=sum(row.get("output_limit_hits", 0) for row in rows) / sum(row["model_turns"] for row in rows)
                    if sum(row["model_turns"] for row in rows) and all(row.get("turns_complete", True) for row in rows) else None,
                output_limit_known_calls=sum(row.get("output_limit_known_calls", row["model_turns"]) for row in rows),
                output_limit_unknown_calls=sum(row.get("output_limit_unknown_calls", 0) for row in rows),
                output_limit_hit_rate_known=(sum(row.get("output_limit_hits", 0) for row in rows)
                    / sum(row.get("output_limit_known_calls", row["model_turns"]) for row in rows))
                    if any(row.get("output_limit_known_calls", row["model_turns"]) for row in rows) else None)
            for name in sorted({name for row in rows for name in row.get("cost_streams", {})}):
                members = [row.get("cost_streams", {}).get(name, {}).get("cost") for row in rows]
                known_estimates = [member["estimated_usd"] for member in members if member and member.get("estimated_usd") is not None]
                known_usage = [member["known_usage_estimate_usd"] for member in members if member and member.get("known_usage_estimate_usd") is not None]
                metrics["cost_streams"].setdefault(name, {})["cost"] = {
                    "currency": "USD", "kind": "estimated_from_list_prices", "price_date": "2026-11-13",
                    "estimated_usd": round(sum(known_estimates), 8) if len(known_estimates) == len(rows) else None,
                    "known_usage_estimate_usd": round(sum(known_usage), 8) if known_usage else None,
                    "complete_runs": len(known_estimates), "attempted_runs": len(rows),
                    "coverage": dict(Counter(member.get("coverage", "unknown") if member else "not_available" for member in members)),
                    "run_estimates": known_estimates,
                    "mean_complete_run_estimate_usd": statistics.mean(known_estimates) if known_estimates else None,
                    "median_complete_run_estimate_usd": statistics.median(known_estimates) if known_estimates else None}
    common = [pair for pair in pairs if pair["both_successful"]]
    result["both_successful_tasks"] = len({pair["task_id"] for pair in common})
    result["both_successful_pairs"] = len(common)
    result["mean_successful_pair_turn_delta"] = statistics.mean(
        pair["successful_pair_turn_delta"] for pair in common) if common else None
    result["mean_successful_pair_token_delta"] = statistics.mean(
        (pair["screenshot"]["token_usage"]["total_tokens"] or 0) - (pair["dom"]["token_usage"]["total_tokens"] or 0)
        for pair in common) if common and all(pair[mode].get("cost_coverage") == "complete" for pair in common for mode in ("dom", "screenshot")) else None
    result["denominator_notes"] = [
        "Every scheduled ledger row, including startup failure or missing recording, is in the denominator.",
        "Missing/incomplete recordings retain known usage as lower bounds; exact cost means are null when coverage is incomplete.",
        "Input/output TPT each use their own known-usage call denominator; all call types qualify, including rejected, failed and termination calls.",
        "Unknown usage is null, never an observed zero; reasoning and cached reads/writes are reported as subsets with their own coverage.",
        "judge_usage covers completion graders; judge_usage_streams separates completion policies, auxiliary verifier models and audit stages.",
        "Audit metrics compare paired evidence within each recording; the four directions are reported independently for both actor arms.",
        "Ungraded and uncertain outcomes are not classified as definitive failures; coverage is reported separately.",
        "The confirmed-success fraction is a lower bound when grading is incomplete.",
        "pass@k is task-macro averaged over the same retained tasks; lower/upper bounds preserve unknown grades.",
        "Only k supported by every retained task is computed; no trial or task is silently omitted to increase k.",
        "All-trials-success reliability differs from pass@k, which requires at least one successful selected attempt.",
        "Success-conditioned means may use different task sets; the paired delta uses only tasks both modes complete.",
        "Positive screenshot-minus-DOM deltas mean more screenshot actor turns.",
        "This benchmark includes target grounding differences between refs and coordinates; it does not isolate visual perception alone.",
        "Public web states can differ between independent runs; alternate run order and repeat trials before drawing conclusions."]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True, help="batch schedule and attempt outcomes")
    parser.add_argument("--pass-k", type=int, nargs="+", help="k values; default is all scheduled trial counts")
    parser.add_argument("--output", type=Path, required=True, help="new report directory")
    args = parser.parse_args(argv)
    ledger = [json.loads(line) for line in args.ledger.read_text().splitlines() if line.strip()]
    if not ledger:
        raise ValueError("empty attempt ledger")
    identities = [(row["task_id"], row["trial"], row["arm"]) for row in ledger]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate ledger task/arm/trial")
    trial_counts = {row["trials"] for row in ledger}
    if len(trial_counts) != 1 or next(iter(trial_counts)) <= 0:
        raise ValueError("invalid configured trial count")
    n = next(iter(trial_counts))
    paths = [str(Path(row["recording"]).resolve()) for row in ledger]
    if len(set(paths)) != len(paths):
        raise ValueError("a recording path is reused across scheduled attempts")
    task_ids = {row["task_id"] for row in ledger}
    if set(identities) != {(task, trial, arm) for task in task_ids for trial in range(1,n+1) for arm in ("dom","screenshot")}:
        raise ValueError("ledger omits a scheduled task/arm/trial")
    indexed = [{}, {}]
    records = {}
    protocols, builds, models, grading_policies, configurations = {}, set(), set(), set(), set()
    environments, capture_policies = set(), set()
    for row in ledger:
        configurations.add(json.dumps(row["configuration"], sort_keys=True))
        source = Path(row["recording"])
        key = (row["run_name"], row["task_id"])
        if row["technical_outcome"] in {"not_started", "running"}:
            continue
        if not (source / "final.json").is_file():
            continue
        recording = inspect_recording(source)
        mode, task, manifest = row["arm"], recording["task"], recording["manifest"]
        if (task["source_task_id"] != row["task_id"] or task["observation_mode"] != mode
                or task["instruction"] != row["task"]["instruction"] or task["start_url"] != row["task"]["start_url"]
                or task["run_name"] != row["run_name"] or manifest["run_name"] != row["run_name"]
                or any(task.get(key) != row["task"].get(key) for key in ("category", "difficulty"))):
            raise ValueError("recording differs from its scheduled task, arm or run name")
        if (task.get("catalog_sha256") != manifest.get("catalog_sha256")
                or task.get("catalog_sha256") != row.get("catalog_sha256")
                or task.get("catalog_sha256") != row["task"].get("catalog_sha256")):
            raise ValueError("recording selected catalog hash differs from its schedule")
        if manifest["status"] != row["technical_outcome"]:
            raise ValueError("ledger technical outcome disagrees with recording")
        indexed[0 if mode == "dom" else 1][key] = recording
        records[(row["task_id"],row["trial"],mode)] = recording
        configuration = row["configuration"]
        for key in ("model", "max_turns", "max_output_tokens", "viewport", "reasoning_effort", "base_url",
                    "browser_lang", "browser_accept_language", "recorder_code_sha256"):
            if key in configuration and manifest["controls"].get(key) != configuration[key]:
                raise ValueError(f"recording control differs from schedule: {key}")
        summary = summarize(recording)
        if row.get("evaluation_path") and summary.get("evaluation_path") and Path(row["evaluation_path"]).resolve() != Path(summary["evaluation_path"]).resolve():
            raise ValueError("evaluation receipt path differs from its scheduled attempt")
        if row.get("evaluation_outcome") in {"complete", "incomplete"} and (
                summary.get("evaluation") is None or row["evaluation_outcome"] != summary["evaluation"].get("status")):
            raise ValueError("evaluation outcome differs from its scheduled receipt")
        models.update(summary["returned_actor_models"])
        grade = summary["completion"]
        if (grade.get("method") != "ungraded" or summary.get("evaluation")) and row.get("rubric"):
            frozen = json.loads(Path(row["rubric"]).read_text())
            rubric_hash = hashlib.sha256(json.dumps(frozen.get("precomputed_rubric", frozen),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            rubric_hashes = {rubric_hash}
            if "criteria" in frozen and "precomputed_rubric" not in frozen:
                canonical = {"items": [{"criterion": item["id"], "description": item["description"],
                    "max_points": 1, "earned_points": None, "justification": None} for item in frozen["criteria"]]}
                rubric_hashes.add(hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest())
            if (hashlib.sha256(Path(row["rubric"]).read_bytes()).hexdigest() != row["rubric_sha256"]
                    or grade.get("rubric_sha256") not in rubric_hashes
                    or summary.get("evaluation") is not None and summary["evaluation"].get("rubric_sha256") not in rubric_hashes
                    or grade.get("judge_model") != row["judge_model"] or grade.get("evidence_policy") != "paired"):
                raise ValueError("grade differs from scheduled rubric, judge or primary evidence policy")
        if grade.get("evidence_policy") is not None:
            grading_policies.add(grade["evidence_policy"])
        profile = manifest.get("browser_profile_provenance") or {}
        if profile.get("profile_fresh_at_run_start") is not True:
            raise ValueError("browser profile freshness is unverified")
        build = (profile.get("browser_build") or {}).get("image_id")
        environment = profile.get("browser_environment")
        if not build or not isinstance(environment,dict) or not environment:
            raise ValueError("browser build or runtime environment is unverified")
        builds.add(build)
        environments.add(json.dumps(environment,sort_keys=True))
        capture_policies.add(json.dumps({key: manifest.get(key) for key in
            ("dom_capture_parameters","renderer_versions")},sort_keys=True))
        protocol = json.dumps({"controls": manifest["controls"],
            "dom_capture": manifest.get("dom_capture_parameters"), "renderers": manifest.get("renderer_versions"),
            "action_driver": manifest.get("action_driver"), "action_driver_version": manifest.get("action_driver_version")}, sort_keys=True)
        if mode in protocols and protocols[mode] != protocol:
            raise ValueError(f"{mode} observation/action policy differs across trials")
        protocols[mode] = protocol
    if (len(configurations)>1 or len(builds)>1 or len(models)>1 or len(grading_policies)>1
            or len(environments)>1 or len(capture_policies)>1):
        raise ValueError("scheduled controls, browser builds/environments, capture policies, actor models or judge policies differ")
    pairs, reports, unmatched = [], [], []
    for task_id in sorted(task_ids):
        for trial in range(1,n+1):
            rows = {row["arm"]: row for row in ledger if row["task_id"]==task_id and row["trial"]==trial}
            available = {arm: records.get((task_id,trial,arm)) for arm in ("dom","screenshot")}
            if all(available.values()):
                receipt, markdown = compare(available["dom"], available["screenshot"])
                reports.append(f"Trial: {trial}\n\n{markdown}")
            else:
                receipt = {"task_id": task_id, "shared_controls": {}, "both_successful": False,
                    "successful_pair_turn_delta": None}
                for arm in ("dom", "screenshot"):
                    if available[arm]:
                        receipt[arm] = summarize(available[arm])
                    else:
                        unmatched.append({"task_id": task_id, "trial": trial, "arm": arm,
                            "technical_outcome": rows[arm]["technical_outcome"]})
                        source = Path(rows[arm]["recording"])
                        decisions = []
                        partial = source / "decisions.jsonl"
                        if partial.is_file():
                            for line in partial.read_text().splitlines():
                                try:
                                    decision = json.loads(line)
                                except json.JSONDecodeError:
                                    continue
                                if isinstance(decision, dict):
                                    decisions.append(decision)
                        task = {**rows[arm]["task"], "source_task_id": task_id, "observation_mode": arm,
                            "run_name": rows[arm]["run_name"]}
                        partial_manifest = {"steps": [], "states": [], "controls": rows[arm]["configuration"]}
                        if (source / "manifest.json").is_file():
                            partial_manifest = json.loads((source / "manifest.json").read_text())
                        receipt[arm] = summarize({"source": str(source), "task": task,
                            "manifest": partial_manifest, "decisions": decisions, "recording_sha256": None,
                            "partial_recording": True, "final": {"run_status": rows[arm]["technical_outcome"]}})
                        no_calls = rows[arm]["technical_outcome"] in {"not_started", "startup_failure"} and not decisions
                        receipt[arm].update(recording_available=False, partial_recording=source.exists(),
                            turns_complete=no_calls, cost_coverage="complete" if no_calls else "partial")
                        if not no_calls and not decisions:
                            receipt[arm]["turns_missing_usage"] = 1
                        if no_calls:
                            receipt[arm]["token_usage"].update(input_tokens=0, output_tokens=0, total_tokens=0)


            receipt["category"] = rows["dom"]["task"].get("category")
            receipt["difficulty"] = rows["dom"]["task"].get("difficulty")
            receipt["catalog_sha256"] = rows["dom"].get("catalog_sha256")
            if rows["dom"].get("catalog_sha256") != rows["screenshot"].get("catalog_sha256"):
                raise ValueError("scheduled arms use different selected catalog hashes")
            receipt["trial_id"] = str(trial)
            receipt["recordings_paired"] = all(available.values())
            pairs.append(receipt)
    # Shared controls are checked across every recorded attempt, including unmatched ones.
    shared = {json.dumps({k:v for k,v in r["manifest"]["controls"].items() if k!="prompt_sha256"},sort_keys=True)
        for r in records.values()}
    if len(shared)>1:
        raise ValueError("shared actor controls differ across recorded attempts")
    for pair in pairs:
        pair["shared_controls"] = json.loads(next(iter(shared))) if shared else next(iter(ledger))["configuration"]
    summary = aggregate(pairs, pass_k=args.pass_k)
    summary.update(scheduled_attempts=len(ledger), scheduled_pairs=len(pairs),
        paired_tasks=len({pair["task_id"] for pair in pairs if pair["recordings_paired"]}),
        paired_attempts=sum(pair["recordings_paired"] for pair in pairs),
        scheduled_tasks=len(task_ids), unmatched_arms=unmatched,
        ledger=str(args.ledger.resolve()), ledger_sha256=hashlib.sha256(args.ledger.read_bytes()).hexdigest(),
        technical_outcomes=dict(Counter(row["technical_outcome"] for row in ledger)),
        evaluation_outcomes=dict(Counter(row.get("evaluation_outcome", "not_available") for row in ledger)),
        full_evaluation_completed_attempts=sum(row.get("evaluation_outcome") == "complete" for row in ledger),
        full_evaluation_completion_rate=sum(row.get("evaluation_outcome") == "complete" for row in ledger) / len(ledger),
        judge_processes_without_usage=sum(bool(row.get("judge_started_at")) and not (Path(row["recording"])/"completion.json").is_file() for row in ledger))
    # Prevent reports from being mixed into immutable source recordings.
    output = args.output.resolve()
    if any(output.is_relative_to(Path(r["source"])) for catalog in indexed for r in catalog.values()):
        raise ValueError("reports must be outside recording folders")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "summary.json", summary)
    write_json(output / "pairs.json", pairs)
    write_json(output / "per_task.json", summary["per_task"])
    lines = ["# DOM versus screenshot actor turns", "",
        f"Scheduled tasks: {summary['scheduled_tasks']}; recorded pairs: {summary['paired_attempts']}; scheduled pairs: {len(pairs)}. No model calls were performed.", "",
        "| Mode | Confirmed successes / attempts | Definitively graded | Mean actor turns (all attempts) | Rejected turns |",
        "|---|---:|---:|---:|---:|"]
    for mode, row in summary["modes"].items():
        lines.append(f"| {mode} | {row['completion_counts'].get('success', 0)} / {row['attempted_runs']} | {row['definitively_graded_tasks']} | {row['mean_turns_all_attempts']} | {row['rejected_turns']} |")
    lines += ["", "| Mode | k | pass@k confirmed lower | Possible upper |", "|---|---:|---:|---:|"]
    for mode in ("dom", "screenshot"):
        for k, estimate in summary["modes"][mode]["pass_at_k"].items():
            lines.append(f"| {mode} | {k} | {estimate['confirmed_lower']:.4f} | {estimate['possible_upper']:.4f} |")
    lines += ["", "pass@k requires at least one success among k attempts; all-trials reliability is reported separately.",
        "Per-task criterion results and pass@k are in per_task.json; actor/judge usage and error coverage are in summary.json.",
        "", f"Both-successful matched trial/task pairs: {summary['both_successful_pairs']}.", "", *summary["denominator_notes"], "", *reports]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output / "report.md"), "paired_tasks": summary["paired_tasks"],
        "paired_attempts": summary["paired_attempts"], "scheduled_pairs": summary["scheduled_pairs"],
        "scheduled_tasks": summary["scheduled_tasks"], "evaluated_k": summary["evaluated_k"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
