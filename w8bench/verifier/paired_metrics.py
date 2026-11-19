"""Aggregate matched actor trials while retaining task and criterion identity."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
import statistics
from typing import Any

from w8bench.usage import valid_token_component
from w8bench.settings import comparison_settings, normalized_settings, require_same_settings


def validate_settings_contracts(entries, *, label):
    """Compare shared policy globally and full task bindings within each task."""
    entries = list(entries)
    present = [value for _, value in entries if value is not None]
    if not present:
        return
    reference = comparison_settings(present[0])
    tasks = {}
    for task_id, value in entries:
        require_same_settings(reference, comparison_settings(value), label=label)
        if task_id in tasks:
            require_same_settings(tasks[task_id], value, label=f"{label} task {task_id}")
        else:
            tasks[task_id] = value


def validate_recorded_settings(entries):
    entries = [(task_id, row) for task_id, row in entries if row.get("recording_available", True)]
    validate_settings_contracts(((task_id, row.get("actor_effective_settings")) for task_id, row in entries), label="recorded actor")
    evaluations = [(task_id, row) for task_id, row in entries if row.get("evaluation") is not None]
    validate_settings_contracts(((task_id, row.get("evaluation_effective_settings")) for task_id, row in evaluations), label="recorded evaluation")
    for _, row in entries:
        actor, evaluation = row.get("actor_effective_settings"), row.get("evaluation_effective_settings")
        if actor is not None and evaluation is not None:
            require_same_settings(actor, evaluation.get("actor"), label="evaluation actor")
        if actor is not None:
            actual = row.get("actual_browser_source_version") or {}
            pinned = actor.get("browser_source") or {}
            shared = set(actual) & set(pinned)
            require_same_settings({key: pinned[key] for key in shared}, {key: actual[key] for key in shared},
                                  label="actual browser source against recorded pin")
    if entries:
        source = entries[0][1].get("actual_browser_source_version") or {}
        for _, row in entries[1:]:
            require_same_settings(source, row.get("actual_browser_source_version") or {}, label="actual browser source")


def validate_completion_policy_versions(rows):
    signatures = set()
    for row in rows:
        grade = row.get("completion") or {}
        if not row.get("completion_grade_available") and set(grade) <= {"method", "verdict"}:
            continue
        signatures.add(tuple(grade.get(key) for key in ("completion_policy_version", "acceptance_policy_version")))
    if len(signatures) > 1:
        raise ValueError("completion policy versions differ across saved grade receipts")

def _pass_at_k_bounds(n: int, confirmed: int, unknown: int, ks: list[int]) -> dict[str, dict[str, Any]]:
    estimates = {}
    for k in ks:
        lower = 1 - (math.comb(n-confirmed, k) / math.comb(n, k) if n-confirmed >= k else 0)
        upper = 1 - (math.comb(n-confirmed-unknown, k) / math.comb(n, k)
            if n-confirmed-unknown >= k else 0)
        estimates[str(k)] = {"estimate": lower if lower == upper else None,
            "confirmed_lower": lower, "possible_upper": upper}
    return estimates


def _index_pairs(pairs, pass_k):
    if not pairs:
        raise ValueError("no matched task pairs")
    validate_completion_policy_versions([pair[mode] for pair in pairs for mode in ("dom", "screenshot")])
    validate_recorded_settings([(pair["task_id"], pair[mode]) for pair in pairs for mode in ("dom", "screenshot")])
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
    controls = {json.dumps(normalized_settings(pair["shared_controls"]), sort_keys=True) for pair in pairs}
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
    return by_task, identities, catalog_hashes, trial_counts, ks


def _validate_task_grades(task_id, attempts):
    evaluation_hashes = {pair[mode]["evaluation"]["rubric_sha256"] for pair in attempts
        for mode in ("dom", "screenshot") if pair[mode].get("evaluation")}
    if len(evaluation_hashes) > 1:
        raise ValueError(f"frozen evaluation rubric differs across trials for {task_id}")
    task_grades = [pair[mode]["completion"] for pair in attempts for mode in ("dom", "screenshot")
        if pair[mode]["completion"].get("method") != "ungraded"]
    signatures = {json.dumps(normalized_settings({key: grade.get(key) for key in (
        "rubric_sha256", "evidence_policy", "method", "judge_model", "returned_judge_model",
        "judge_prompt_sha256", "judge_base_url", "max_output_tokens", "judge_schema_sha256",
        "completion_policy_version", "acceptance_policy_version")}),
        sort_keys=True) for grade in task_grades}
    task_criterion_sets = {tuple(c["id"] for c in grade.get("criteria", [])) for grade in task_grades}
    if len(signatures) > 1 or len(task_criterion_sets) > 1:
        raise ValueError(f"frozen rubric or grading controls differ across trials for {task_id}")


def _task_mode_metrics(attempts, mode, ks):
    grades = [pair[mode]["completion"] for pair in attempts]
    graded = [grade for grade in grades if grade.get("method") != "ungraded"]
    verdicts = Counter(grade["verdict"] for grade in grades)
    n, c = len(grades), verdicts["success"]
    u = verdicts["uncertain"] + verdicts["ungraded"]
    estimates = _pass_at_k_bounds(n, c, u, ks)
    criteria = {}
    criterion_ids = [item["id"] for item in graded[0].get("criteria", [])] if graded else []
    for criterion_id in criterion_ids:
        outcomes = Counter(next((item["verdict"] for item in grade.get("criteria", [])
            if item["id"] == criterion_id), "ungraded") for grade in grades)
        criterion_c = outcomes["success"]
        criterion_u = outcomes["uncertain"] + outcomes["ungraded"]
        criterion_estimates = _pass_at_k_bounds(n, criterion_c, criterion_u, ks)
        criteria[criterion_id] = {"verdict_counts": dict(outcomes),
            "confirmed_success_rate": criterion_c/n, "definitively_graded": n-criterion_u,
            "pass_at_k": criterion_estimates}
    return {"attempts": n, "completion_counts": dict(verdicts),
        "definitively_graded": n-u, "pass_at_k": estimates,
        "all_trials_success_confirmed": c == n, "all_trials_success_possible": c+u == n,
        "criteria": criteria,
        "all_trials_tokens": sum((pair[mode]["token_usage"]["total_tokens"] or 0) for pair in attempts)
            if any(pair[mode]["token_usage"]["total_tokens"] is not None for pair in attempts) else None,
        "token_usage_coverage": dict(Counter(pair[mode].get("cost_coverage", "unknown") for pair in attempts)),
        "all_trials_turns": sum(pair[mode]["model_turns"] for pair in attempts)}


def _mode_accounting(rows, successes, tokens_complete):
    return {"tokens": sum((row["token_usage"]["total_tokens"] or 0) for row in rows) if any(row["token_usage"]["total_tokens"] is not None for row in rows) else None,
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
        "judge_usage": {key: sum(values) if (values := [value for row in rows
            if valid_token_component(value := row.get("judge_usage", row["completion"].get("usage") or {}).get(key))]) else None
            for key in ("input_tokens", "output_tokens", "total_tokens")},
        "judge_calls": sum(row.get("judge_calls", row["completion"].get("judge_calls", 0)) for row in rows),
        "judge_calls_missing_usage": sum(row.get("judge_calls_missing_usage",
            int(row["completion"].get("judge_calls", 0) > 0 and "input_tokens" not in (row["completion"].get("usage") or {}))) for row in rows),
        "turns_missing_usage": sum(row["turns_missing_usage"] for row in rows)}


def _mode_metrics(rows, task_count):
    verdicts = Counter(row["completion"]["verdict"] for row in rows)
    successes = [row for row in rows if row["completion"]["verdict"] == "success"]
    definitive = verdicts["success"] + verdicts["failure"]
    turns_complete = all(row.get("turns_complete", True) for row in rows)
    tokens_complete = all(row.get("cost_coverage", "complete") == "complete" and not row["turns_missing_usage"] for row in rows)
    return {
        "technical_failures": sum(row.get("technical_failure", False) for row in rows),
        "technical_failure_classes": dict(Counter(row.get("technical_failure_class") or "unknown"
            for row in rows if row.get("technical_failure"))),
        "agent_eligible_runs": sum(not row.get("technical_failure", False) for row in rows),
        "agent_failure_runs": sum(not row.get("technical_failure", False) and row["completion"]["verdict"] == "failure" for row in rows),
        "confirmed_success_rate_agent_eligible": verdicts["success"] / eligible
            if (eligible := sum(not row.get("technical_failure", False) for row in rows)) else None,
        "attempted_tasks": task_count, "attempted_runs": len(rows), "completion_counts": dict(verdicts),
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
        "stall_advisory_matches": sum(row.get("stall_advisory_matches", 0) for row in rows),
        "actor_transport_attempts": sum(row["actor_transport_attempts"] for row in rows)
            if all(type(row.get("actor_transport_attempts")) is int for row in rows) else None,
        "actor_transport_attempts_known_lower_bound": sum(row.get("actor_transport_attempts") or 0 for row in rows),
        "runs_missing_transport_counts": sum(row.get("actor_transport_attempts") is None for row in rows),
        "failed_transport_attempts": sum(row.get("failed_transport_attempts", 0) for row in rows),
        "pending_transport_attempts": sum(row.get("pending_transport_attempts", 0) for row in rows),
        "output_limit_hits": sum(row.get("output_limit_hits",0) for row in rows),
        "token_usage_known_calls": {key: sum(row.get("token_usage_known_calls", {}).get(key, 0) for row in rows) for key in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens")},
        "action_attempts": sum(row["action_attempts"] for row in rows),
        "rejected_turns": sum(row["rejected_turns"] for row in rows),
        "actor_seconds": sum(row["actor_latency_seconds"] for row in rows),
        **_mode_accounting(rows, successes, tokens_complete)}


def _task_macro_metrics(metrics, task_rows, ks):
    metrics["pass_at_k"] = {str(k): {
        "estimate": statistics.mean(row["pass_at_k"][str(k)]["estimate"] for row in task_rows)
            if all(row["pass_at_k"][str(k)]["estimate"] is not None for row in task_rows) else None,
        "confirmed_lower": statistics.mean(row["pass_at_k"][str(k)]["confirmed_lower"] for row in task_rows),
        "possible_upper": statistics.mean(row["pass_at_k"][str(k)]["possible_upper"] for row in task_rows),
        "tasks": len(task_rows)} for k in ks}
    metrics["all_trials_success_rate_confirmed"] = sum(row["all_trials_success_confirmed"] for row in task_rows)/len(task_rows)
    metrics["all_trials_success_rate_possible"] = sum(row["all_trials_success_possible"] for row in task_rows)/len(task_rows)


def _category_groups(result, pairs):
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
    return groups


def _distributions(rows):
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
    return distributions


def _tokens_per_turn(rows):
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
    return tpt


def _judge_streams(rows):
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
    return streams


def _audit_directions(rows):
    directional = {}
    audited = [row for row in rows if row.get("evidence_audit") is not None]
    for key in ("screenshot_evidence_loss", "dom_model_evidence_loss", "screenshot_verifier_misses", "dom_model_verifier_misses"):
        values = [row["evidence_audit"][key] for row in audited if key in row["evidence_audit"]]
        denominator = sum(value["denominator"] for value in values)
        count = sum(value["count"] for value in values)
        directional[key] = {"count": count if values else None, "denominator": denominator if values else None,
            "rate": count / denominator if denominator else None, "audited_runs": len(values), "attempted_runs": len(rows)}
    return directional


def _auxiliary_signals(rows):
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
    return auxiliary


def _citation_metrics(rows):
    diagnostics = {}
    for verifier in ("dom_model", "screenshot_verifier"):
        per_run = [{"run": row.get("run"), "recording_sha256": row.get("recording_sha256"),
                    "citation_checks": row.get("citation_checks", {}).get(verifier)} for row in rows]
        available = [entry["citation_checks"] for entry in per_run if isinstance(entry["citation_checks"], dict)
            and all(type(entry["citation_checks"].get(key)) is int and entry["citation_checks"][key] >= 0
                    for key in ("checked_citations", "valid_citations", "invalid_citations"))
            and entry["citation_checks"]["valid_citations"] + entry["citation_checks"]["invalid_citations"] == entry["citation_checks"]["checked_citations"]]
        counts = {key: sum(value[key] for value in available) if available else None
                  for key in ("checked_citations", "valid_citations", "invalid_citations")}
        quote_checks = [value for value in available if all(type(value.get(key)) is int and value[key] >= 0
                        for key in ("quote_checked_citations", "quote_unavailable_citations"))]
        quote_counts = {key: sum(value[key] for value in quote_checks) if quote_checks else None
                        for key in ("quote_checked_citations", "quote_unavailable_citations")}
        diagnostics[verifier] = {**counts,
            **quote_counts, "quote_check_known_runs": len(quote_checks),
            "invalid_citation_rate": counts["invalid_citations"] / counts["checked_citations"] if counts["checked_citations"] else None,
            "checked_runs": len(available), "attempted_runs": len(rows), "per_run": per_run}
    return diagnostics


def _coverage_rates(rows):
    return dict(step_cap_hits=sum(row.get("step_cap_hit", False) for row in rows),
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


def _cost_estimates(metrics, rows):
    for name in sorted({name for row in rows for name in row.get("cost_streams", {})}):
        members = [row.get("cost_streams", {}).get(name, {}).get("cost") for row in rows]
        known_estimates = [member["estimated_usd"] for member in members if member and member.get("estimated_usd") is not None]
        known_usage = [member["known_usage_estimate_usd"] for member in members if member and member.get("known_usage_estimate_usd") is not None]
        metrics["cost_streams"].setdefault(name, {})["cost"] = {
            "currency": "USD", "kind": "estimated_from_list_prices", "price_date": "2026-11-16",
            "estimated_usd": round(sum(known_estimates), 8) if len(known_estimates) == len(rows) else None,
            "known_usage_estimate_usd": round(sum(known_usage), 8) if known_usage else None,
            "complete_runs": len(known_estimates), "attempted_runs": len(rows),
            "coverage": dict(Counter(member.get("coverage", "unknown") if member else "not_available" for member in members)),
            "run_estimates": known_estimates,
            "mean_complete_run_estimate_usd": statistics.mean(known_estimates) if known_estimates else None,
            "median_complete_run_estimate_usd": statistics.median(known_estimates) if known_estimates else None}


def _group_metrics(target, mode, selected):
    rows = [pair[mode] for pair in selected]
    metrics = target.setdefault(mode, {})
    distributions = _distributions(rows)
    tpt = _tokens_per_turn(rows)
    streams = _judge_streams(rows)
    directional = _audit_directions(rows)
    verdicts = Counter(row["completion"]["verdict"] for row in rows)
    definitive = verdicts["success"] + verdicts["failure"]
    auxiliary = _auxiliary_signals(rows)
    metrics.setdefault("token_usage", {key: sum(row["token_usage"].get(key) or 0 for row in rows)
        if any(row["token_usage"].get(key) is not None for row in rows) else None
        for key in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens")})
    metrics.setdefault("token_usage_known_calls", {key: sum(row.get("token_usage_known_calls", {}).get(key, 0) for row in rows)
        for key in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens")})
    metrics.update(attempted_runs=len(rows), completion_counts=dict(verdicts),
        stall_advisory_matches=sum(row.get("stall_advisory_matches", 0) for row in rows),
        stall_advisory_matches_per_run=[{"run": row.get("run"), "matches": row.get("stall_advisory_matches", 0)} for row in rows],
        stall_advisory_match_counts=dict(sum((Counter(row.get("stall_advisory_match_counts", {})) for row in rows), Counter())),
        technical_failures=sum(row.get("technical_failure", False) for row in rows),
        technical_failure_classes=dict(Counter(row.get("technical_failure_class") or "unknown"
            for row in rows if row.get("technical_failure"))),
        agent_eligible_runs=sum(not row.get("technical_failure", False) for row in rows),
        agent_failure_runs=sum(not row.get("technical_failure", False) and row["completion"]["verdict"] == "failure" for row in rows),
        confirmed_success_rate_agent_eligible=verdicts["success"] / eligible
            if (eligible := sum(not row.get("technical_failure", False) for row in rows)) else None,
        confirmed_success_rate_all_attempts=verdicts["success"] / len(rows),
        success_rate_definitively_graded=verdicts["success"] / definitive if definitive else None,
        definitively_graded_runs=definitive, auxiliary_verifiers=auxiliary,
        distributions=distributions, tokens_per_turn=tpt,
        judge_usage_streams=streams,
        native_model_mismatches=[finding for row in rows for finding in row.get("native_model_mismatches", [])],
        citation_checks=_citation_metrics(rows),
        cost_streams={"actor": {"usage": metrics.get("token_usage"),
            "usage_known_calls": metrics.get("token_usage_known_calls"),
            "calls": sum(row["model_turns"] for row in rows),
            "usage_coverage": dict(Counter(row.get("cost_coverage", "unknown") for row in rows))}, **streams},
        evidence_audit=directional,
        audit_status_counts=dict(Counter(row.get("evidence_audit_status", "not_available") for row in rows)),
        **_coverage_rates(rows))
    _cost_estimates(metrics, rows)
    technical_streams = [row.get("cost_streams", {}).get("technical_attempts:actor") for row in rows]
    technical_streams = [stream for stream in technical_streams if stream is not None]
    if technical_streams:
        metrics["cost_streams"].setdefault("technical_attempts:actor", {}).update(
            attempt_count=sum(stream.get("attempt_count", 0) for stream in technical_streams),
            calls=sum(stream.get("calls", 0) for stream in technical_streams) if all(type(stream.get("calls")) is int for stream in technical_streams) else None,
            usage={key: sum(values) if (values := [(stream.get("usage") or {})[key] for stream in technical_streams
                if (stream.get("usage") or {}).get(key) is not None]) else None
                for key in ("input_tokens", "output_tokens", "total_tokens")},
            usage_coverage=dict(Counter(stream.get("usage_coverage", "unknown") for stream in technical_streams)))


def _paired_outcomes(result, pairs):
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
        "Technical failures are ungraded and never agent failures; agent-eligible success excludes them while the scheduled lower bound retains all rows.",
        "Actor efficiency uses the final attempt only; prior technical-attempt usage and costs are reported separately.",
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


def aggregate(pairs: list[dict[str, Any]], *, pass_k: list[int] | None = None) -> dict[str, Any]:
    """Aggregate any number of matched trials, retaining task/criterion identity."""
    pairs = [{**pair, "both_successful": pair["both_successful"] and not any(pair[mode].get("technical_failure") for mode in ("dom", "screenshot")),
        "successful_pair_turn_delta": None if any(pair[mode].get("technical_failure") for mode in ("dom", "screenshot")) else pair.get("successful_pair_turn_delta"),
        **{mode: {**pair[mode],
        "technical_completion_diagnostic": pair[mode]["completion"],
        "completion": {"method": "ungraded", "verdict": "ungraded", "reason": "technical_failure"}}
        for mode in ("dom", "screenshot") if pair[mode].get("technical_failure")}} for pair in pairs]
    profile_policies = {pair.get("browser_profile_policy", {}).get("allow_nonfresh", False) for pair in pairs}
    if len(profile_policies) > 1:
        raise ValueError("browser profile comparison policies differ")
    by_task, identities, catalog_hashes, trial_counts, ks = _index_pairs(pairs, pass_k)
    result = {"browser_profile_policy": {"allow_nonfresh": next(iter(profile_policies), False),
        "override_used": any(pair.get("browser_profile_policy", {}).get("override_used") for pair in pairs)},"paired_tasks": len(by_task), "paired_attempts": len(pairs),
        "trial_ids": sorted({str(identity[0]) for identity in identities}),
        "trials_per_task": trial_counts, "balanced_trial_counts": len(set(trial_counts.values())) == 1,
        "evaluated_k": ks, "catalog_sha256": next(iter(catalog_hashes)), "modes": {}, "per_task": {}}
    for task_id, attempts in sorted(by_task.items()):
        result["per_task"][task_id] = {}
        _validate_task_grades(task_id, attempts)
        for mode in ("dom", "screenshot"):
            result["per_task"][task_id][mode] = _task_mode_metrics(attempts, mode, ks)
    for mode in ("dom", "screenshot"):
        rows = [pair[mode] for pair in pairs]
        result["modes"][mode] = _mode_metrics(rows, len(by_task))
        task_rows = [result["per_task"][task_id][mode] for task_id in by_task]
        _task_macro_metrics(result["modes"][mode], task_rows, ks)
    groups = _category_groups(result, pairs)
    for category, selected in groups.items():
        target = result["modes"] if category == "all" else result["categories"].setdefault(category, {})
        for mode in ("dom", "screenshot"):
            _group_metrics(target, mode, selected)
    result["native_model_mismatches"] = [finding for pair in pairs for mode in ("dom", "screenshot")
                                          for finding in pair[mode].get("native_model_mismatches", [])]
    _paired_outcomes(result, pairs)
    return result
