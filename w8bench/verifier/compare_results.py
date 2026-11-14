"""Compare acting-model turns and completion across independent modality runs."""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter
import json
import re
from pathlib import Path
from typing import Any

from w8bench.task_recorder.prepare_verifier_data import inspect_recording, read_object
from w8bench.task_recorder.recorder_support import write_json

# USD per million tokens; estimates use Standard pricing checked on this date.
# Columns: input, output, cached input, 30-minute cache write, long-context threshold.
TOKEN_PRICES = {
    "gpt-6.1-terra": (1.0, 5.0, 0.05, 1.25, 272000),
    "gpt-5.6-sol": (4.0, 20.0, 0.4, 5.0, 272000),
    "gpt-5.6-terra": (2.0, 12.0, 0.2, 2.5, 272000),
    "gpt-5.2": (1.75, 14.0, 0.175, 1.75, None),
    "gemini-3.1-pro-preview": (2.0, 12.0, 0.2, 2.0, 200000),
}


def summarize(recording: dict[str, Any]) -> dict[str, Any]:
    manifest, decisions, task = recording["manifest"], recording["decisions"], recording["task"]
    source = Path(recording["source"])
    partial = recording.get("partial_recording", False)
    evaluation_path = (source.parent.parent / "evaluations" / str(task.get("run_name") or manifest.get("run_name"))
        / task["observation_mode"] / task["source_task_id"] / str(recording.get("recording_sha256")) / "evaluation.json")
    evaluation = read_object(evaluation_path) if evaluation_path.is_file() and not partial else None
    if evaluation is not None and any(evaluation.get(key) != expected for key, expected in (
            ("recording_sha256", recording["recording_sha256"]), ("task_id", task["source_task_id"]),
            ("actor_arm", task["observation_mode"]), ("trial_id", str(task.get("run_name") or manifest.get("run_name"))))):
        raise ValueError("evaluation receipt belongs to a different task, arm, trial or recording")
    grade_path = source / "completion.json"
    grade = read_object(grade_path) if grade_path.is_file() and not partial else None
    stages = (evaluation or {}).get("stages", {})
    if grade is None and stages.get("paired_completion", {}).get("result"):
        result = Path(stages["paired_completion"]["result"])
        if not result.resolve().is_relative_to(evaluation_path.parent.resolve()):
            raise ValueError("primary completion result is outside its evaluation folder")
        grade = read_object(result)
    if grade is not None and (grade.get("recording_sha256") != recording["recording_sha256"] or
            grade.get("observation_mode") != task["observation_mode"] or grade.get("task_id") != task["source_task_id"]):
        raise ValueError("completion grade is stale or belongs to a different run")
    if grade is not None and evaluation is not None and grade.get("rubric_sha256") != evaluation.get("rubric_sha256"):
        raise ValueError("completion and evaluation frozen rubric hashes differ")
    secondary_path = source / "completion_actor_native.json"
    secondary = read_object(secondary_path) if secondary_path.is_file() and not partial else None
    if secondary and (secondary.get("recording_sha256") != recording["recording_sha256"]
            or secondary.get("evidence_policy") != "actor_native"
            or secondary.get("task_id") != task["source_task_id"]
            or secondary.get("observation_mode") != task["observation_mode"]):
        raise ValueError("secondary completion grade is stale or has the wrong policy")
    usage = dict.fromkeys(("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens"), 0)
    known = dict.fromkeys(usage, 0)
    models = set()
    for row in decisions:
        raw = row.get("usage") or {}
        components = {"input_tokens": raw.get("input_tokens"), "output_tokens": raw.get("output_tokens"),
            "reasoning_tokens": (raw.get("output_tokens_details") or {}).get("reasoning_tokens"),
            "cached_input_tokens": (raw.get("input_tokens_details") or {}).get("cached_tokens"),
            "cache_write_input_tokens": raw.get("cache_creation_input_tokens", (raw.get("input_tokens_details") or {}).get("cache_write_tokens"))}
        for key, value in components.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                usage[key] += value
                known[key] += 1
        if row.get("returned_model"):
            models.add(row["returned_model"])
        if row.get("response") and (source / row["response"]).is_file():
            response = read_object(source / row["response"])
            if response.get("model"):
                models.add(response["model"])
    for key in usage:
        if not known[key]:
            usage[key] = None
    usage["total_tokens"] = (usage["input_tokens"] or 0) + (usage["output_tokens"] or 0) if known["input_tokens"] or known["output_tokens"] else None
    missing = sum(not isinstance((row.get("usage") or {}).get("input_tokens"), (int, float)) or
                  not isinstance((row.get("usage") or {}).get("output_tokens"), (int, float)) for row in decisions)
    tpt = {key: {"tokens": usage[key], "known_calls": known[key], "total_calls": len(decisions),
        "known_usage_mean": usage[key] / known[key] if known[key] else None,
        "mean": usage[key] / len(decisions) if decisions and known[key] == len(decisions) and not partial else None,
        "coverage": "complete" if known[key] == len(decisions) and not partial else "partial" if known[key] else "none"}
        for key in ("input_tokens", "output_tokens")}
    streams = {}
    for name, item in (("paired_completion", grade), ("actor_native_completion", secondary)):
        if item is not None:
            calls = item.get("judge_calls", 0)
            raw = item.get("usage") or {}
            normalized = {**raw,
                "cached_input_tokens": raw.get("cached_input_tokens", (raw.get("input_tokens_details") or {}).get("cached_tokens")),
                "reasoning_tokens": raw.get("reasoning_tokens", (raw.get("output_tokens_details") or {}).get("reasoning_tokens")),
                "cache_write_input_tokens": raw.get("cache_write_input_tokens", raw.get("cache_creation_input_tokens",
                    (raw.get("input_tokens_details") or {}).get("cache_write_tokens")))} if raw else None
            if normalized is not None and normalized.get("total_tokens") is None and all(raw.get(key) is not None for key in ("input_tokens", "output_tokens")):
                normalized["total_tokens"] = raw["input_tokens"] + raw["output_tokens"]
            streams[name] = {"model": item.get("judge_model"), "calls": calls, "usage": normalized,
                "call_records": [{"model": item.get("judge_model"),
                    "returned_model": item.get("returned_judge_model"), "usage": normalized}] if calls == 1 else [],
                "usage_coverage": "complete" if not calls or all(raw.get(key) is not None for key in ("input_tokens", "output_tokens")) else "unknown"}
    for name in ("dom_model", "screenshot_verifier"):
        stage = stages.get(name)
        if stage is None:
            continue
        stage_usage = stage.get("usage") or {}
        provider_metrics = stage.get("provider_call_metrics") or {}
        metrics_file = evaluation_path.parent / name / "run_metrics.json"
        metrics_hash = stage.get("normalized_metrics_sha256")
        if not provider_metrics and metrics_hash and metrics_file.is_file():
            if hashlib.sha256(metrics_file.read_bytes()).hexdigest() != metrics_hash:
                raise ValueError("normalized verifier accounting artifact changed")
            provider_metrics = read_object(metrics_file).get("provider_call_metrics") or {}
        for model, raw in stage_usage.items():
            if model == "combined":
                continue
            streams[f"{name}:{model}"] = {"model": model, "calls": (stage.get("calls") or {}).get(model),
                "call_records": [call for value in provider_metrics.values() for call in value.get("calls", []) if call.get("configured_model") == model],
                "usage": raw or None, "usage_coverage": stage.get("usage_coverage") or (
                    "complete" if stage.get("status") == "complete" and isinstance(raw, dict)
                    and raw.get("input_tokens", raw.get("prompt_tokens")) is not None
                    and raw.get("output_tokens", raw.get("completion_tokens")) is not None
                    and (not raw.get("usage_known_calls") or all(raw["usage_known_calls"].get(component)
                        == (stage.get("calls") or {}).get(model) for component in ("input_tokens", "output_tokens")))
                    and not raw.get("calls_without_reported_usage", 0) else "unknown")}
        if not stage_usage:
            streams[name] = {"model": stage.get("configured_models"), "calls": stage.get("calls"),
                "usage": None, "usage_coverage": stage.get("usage_coverage", "unknown")}
    audit = stages.get("audit") or {}
    for stage_name in ("inventory", "adjudication"):
        audit_attempts = [*audit.get("attempt_history", []), audit] if audit else []
        calls = [call for attempt in audit_attempts for call in attempt.get("calls", []) if call.get("stage") == stage_name]
        if not calls and not audit:
            continue
        stream_usage = dict.fromkeys(("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens"), None)
        coverage = dict.fromkeys(stream_usage, 0)
        for call in calls:
            raw = call.get("usage") or {}
            values = {"input_tokens": raw.get("input_tokens", raw.get("prompt_tokens")),
                "output_tokens": raw.get("output_tokens", raw.get("completion_tokens")),
                "reasoning_tokens": raw.get("reasoning_tokens", (raw.get("completion_tokens_details") or {}).get("reasoning_tokens")),
                "cached_input_tokens": raw.get("cached_input_tokens", (raw.get("prompt_tokens_details") or {}).get("cached_tokens")),
                "cache_write_input_tokens": raw.get("cache_write_input_tokens", raw.get("cache_creation_input_tokens"))}
            for key, value in values.items():
                if value is not None:
                    stream_usage[key] = (stream_usage[key] or 0) + value
                    coverage[key] += 1
        stream_usage["total_tokens"] = ((stream_usage["input_tokens"] or 0) + (stream_usage["output_tokens"] or 0)
            if coverage["input_tokens"] or coverage["output_tokens"] else None)
        unknown_attempts = sum(attempt.get("usage_coverage") in {"unknown", "none"} and
            attempt.get("status") not in {"blocked", "not_eligible", "not_available"} for attempt in audit_attempts)
        streams[f"audit:{stage_name}"] = {"unknown_attempts": unknown_attempts, "attempt_count": len(audit_attempts), "models": sorted({call.get("requested_model", call.get("model")) for call in calls}),
            "calls": len(calls), "call_records": calls, "usage": stream_usage, "usage_known_calls": coverage,
            "usage_coverage": "complete" if calls and not unknown_attempts and coverage["input_tokens"] == coverage["output_tokens"] == len(calls)
                else "complete" if audit.get("status") == "not_eligible" and not unknown_attempts else "partial" if calls else "unknown"}
    # Resume histories represent distinct attempted calls. Reused completed stages
    # are only present as the current receipt and are therefore counted once.
    for name in ("paired_completion", "dom_model", "screenshot_verifier"):
        for prior in stages.get(name, {}).get("attempt_history", []):
            prior_usage = prior.get("usage") or {}
            if name == "paired_completion":
                member = streams.setdefault(name, {"model": "gpt-5.6-sol", "calls": 0,
                    "usage": None, "usage_coverage": "complete", "_history_only": True})
                member.setdefault("history_attempts", []).append({"usage": prior_usage or None,
                    "calls": prior.get("calls"), "usage_coverage": prior.get("usage_coverage", "unknown"),
                    "status": prior.get("status"),
                    "call_records": [{"model": "gpt-5.6-sol",
                        "returned_model": (prior.get("model_settings") or {}).get("returned_model"),
                        "usage": prior_usage}] if prior.get("calls") == 1 else []})
            else:
                provider_metrics = prior.get("provider_call_metrics") or {}
                snapshot = prior.get("artifact_snapshots", {}).get("run_metrics.json")
                if not provider_metrics and snapshot:
                    metrics_file = Path(snapshot["path"])
                    if not metrics_file.resolve().is_relative_to(evaluation_path.parent.resolve()) or hashlib.sha256(metrics_file.read_bytes()).hexdigest() != snapshot["sha256"]:
                        raise ValueError("historical verifier accounting artifact changed")
                    provider_metrics = read_object(metrics_file).get("provider_call_metrics") or {}
                models = [model for model in prior_usage if model != "combined"]
                for model in models or [None]:
                    key = f"{name}:{model}" if model else name
                    member = streams.setdefault(key, {"model": model or prior.get("configured_models"),
                        "calls": 0, "usage": None, "usage_coverage": "complete", "_history_only": True})
                    member.setdefault("history_attempts", []).append({"usage": prior_usage.get(model) if model else None,
                        "calls": (prior.get("calls") or {}).get(model) if isinstance(prior.get("calls"), dict) else prior.get("calls"),
                        "usage_coverage": prior.get("usage_coverage", "unknown"), "status": prior.get("status"),
                        "call_records": [call for value in provider_metrics.values() for call in value.get("calls", []) if model and call.get("configured_model") == model]})
    for member in streams.values():
        histories = member.get("history_attempts", [])
        if not histories:
            continue
        current = {key: member.get(key) for key in ("usage", "calls", "usage_coverage", "call_records")}
        attempts = list(histories) if member.pop("_history_only", False) else [*histories, current]
        totals = dict.fromkeys(("input_tokens", "output_tokens", "total_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens"), None)
        reported = dict.fromkeys(totals, 0)
        for attempt in attempts:
            raw = attempt.get("usage") or {}
            values = {"input_tokens": raw.get("input_tokens", raw.get("prompt_tokens")),
                "output_tokens": raw.get("output_tokens", raw.get("completion_tokens")),
                "total_tokens": raw.get("total_tokens"),
                "reasoning_tokens": raw.get("reasoning_tokens", (raw.get("output_tokens_details") or raw.get("completion_tokens_details") or {}).get("reasoning_tokens")),
                "cached_input_tokens": raw.get("cached_input_tokens", (raw.get("input_tokens_details") or raw.get("prompt_tokens_details") or {}).get("cached_tokens")),
                "cache_write_input_tokens": raw.get("cache_write_input_tokens", raw.get("cache_creation_input_tokens"))}
            if values["total_tokens"] is None and values["input_tokens"] is not None and values["output_tokens"] is not None:
                values["total_tokens"] = values["input_tokens"] + values["output_tokens"]
            for key, value in values.items():
                if isinstance(value, (int, float)):
                    totals[key] = (totals[key] or 0) + value
                    reported[key] += 1
        missing = sum(attempt.get("usage_coverage") != "complete" for attempt in attempts)
        member.update(current_attempt=current, attempts=attempts, attempt_count=len(attempts), usage=totals,
            call_records=[call for attempt in attempts for call in attempt.get("call_records") or []],
            usage_known_attempts=reported, known_calls=sum(attempt.get("calls", 0) or 0 for attempt in attempts if isinstance(attempt.get("calls"), int)),
            calls=sum(attempt["calls"] for attempt in attempts) if all(isinstance(attempt.get("calls"), int) for attempt in attempts) else None,
            unknown_attempts=missing, usage_coverage="complete" if not missing else "partial" if any(reported.values()) else "unknown")
    if evaluation is not None:
        import_path = evaluation_path.parent / "rubric_import.json"
        declaration = read_object(import_path) if import_path.is_file() else None
        if declaration is not None and declaration.get("model_calls") == 0:
            streams["rubric_import"] = {"calls": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "usage_coverage": "complete", "preparation_receipt": declaration,
                "scope": "Frozen-rubric import only; external rubric preparation is not charged per trial."}
    primary_streams = [value for key, value in streams.items() if key in {"paired_completion", "actor_native_completion"}]
    judge_usage = {key: sum((stream.get("usage") or {}).get(key, 0) or 0 for stream in primary_streams)
        for key in ("input_tokens", "output_tokens", "total_tokens")}
    if grade is not None and grade.get("verdict") not in {"success", "failure", "uncertain", "ungraded"}:
        raise ValueError("invalid completion verdict")
    cost_streams = {"actor": {"model": task.get("model"), "calls": len(decisions), "usage": usage,
        "call_records": decisions, "usage_known_calls": known,
        "usage_coverage": "partial" if partial or missing else "complete"}, **streams}
    for name, stream in cost_streams.items():
        estimate, priced, assumptions = 0.0, 0, set()
        records = stream.get("call_records", [])
        for call in records:
            model = (call.get("returned_model") or call.get("response_model") or call.get("returned_judge_model")
                or call.get("configured_model") or call.get("requested_model") or call.get("model") or stream.get("model"))
            selected = next((key for key in TOKEN_PRICES if isinstance(model, str)
                and re.fullmatch(re.escape(key) + r"(?:-\d{4}-\d{2}-\d{2})?", model)), None)
            raw = call.get("usage") if isinstance(call.get("usage"), dict) else call
            input_tokens = raw.get("input_tokens", raw.get("prompt_tokens"))
            output_tokens = raw.get("output_tokens", raw.get("completion_tokens"))
            if (not selected or call.get("usage_reported") is False or
                    any(not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
                        for value in (input_tokens, output_tokens))):
                continue
            details = raw.get("input_tokens_details") or raw.get("prompt_tokens_details") or {}
            cached = raw.get("cached_input_tokens", details.get("cached_tokens"))
            written = raw.get("cache_write_input_tokens", raw.get("cache_creation_input_tokens", details.get("cache_write_tokens")))
            if cached is None:
                cached = 0
                assumptions.add("unreported_cached_input_priced_as_ordinary_input")
            if written is None:
                written = 0
                assumptions.add("unreported_cache_writes_priced_as_ordinary_input")
            if (any(not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 for value in (cached, written))
                    or cached + written > input_tokens):
                continue
            pin, pout, pcache, pwrite, threshold = TOKEN_PRICES[selected]
            if threshold is not None and input_tokens > threshold:
                pin, pout, pcache, pwrite = pin * 2, pout * 1.5, pcache * 2, pwrite * 2
            write_details = details.get("cache_write_tokens_details") or {}
            written_12h = write_details.get("ttl_12h_tokens", 0) or 0
            if written and not write_details:
                assumptions.add("cache_write_lifetime_assumed_30_minutes")
            if written_12h > written:
                continue
            estimate += ((input_tokens - cached - written) * pin + cached * pcache
                + written * pwrite + written_12h * pwrite + output_tokens * pout) / 1000000
            priced += 1
        calls = stream.get("calls")
        complete = (type(calls) is int and calls == priced and not stream.get("unknown_attempts")
            and stream.get("usage_coverage") == "complete")
        stream["cost"] = {"currency": "USD", "kind": "estimated_from_list_prices", "price_date": "2026-11-13",
            "source": "https://developers.openai.com/api/docs/pricing" if not name.startswith("audit:adjudication")
                else "https://ai.google.dev/gemini-api/docs/pricing",
            "estimated_usd": round(estimate, 8) if complete else None,
            "known_usage_estimate_usd": round(estimate, 8) if priced or calls == 0 else None,
            "priced_calls": priced, "unpriced_calls": max(0, calls - priced) if type(calls) is int else None,
            "unknown_attempts": stream.get("unknown_attempts", 0), "coverage": "complete" if complete else "partial" if priced else "unknown",
            "assumptions": sorted(assumptions), "reason": None if complete else "missing_per_call_usage_or_attempt_coverage"}
    cap = manifest.get("controls", {}).get("max_turns")
    return {"run": str(source), "recording_available": not partial, "partial_recording": partial,
        "turns_complete": not partial, "cost_coverage": "partial" if partial or missing else "complete",
        "category": task.get("category"), "difficulty": task.get("difficulty"), "catalog_sha256": task.get("catalog_sha256"),
        "secondary_completion": secondary, "judge_usage": judge_usage, "judge_usage_streams": streams,
        "cost_streams": cost_streams,
        "judge_calls": sum(stream.get("calls") if isinstance(stream.get("calls"), int) else stream.get("known_calls", 0) for stream in primary_streams),
        "judge_calls_missing_usage": sum(max(1, stream.get("unknown_attempts", 0)) for stream in primary_streams if stream["usage_coverage"] != "complete"),
        "recording_sha256": recording.get("recording_sha256"),
        "evaluation": evaluation, "evaluation_path": str(evaluation_path) if evaluation else None,
        "evaluation_coverage": (evaluation or {}).get("coverage"),
        "evidence_audit": audit.get("metrics") if audit.get("status") == "complete" else None,
        "evidence_audit_status": audit.get("status", "not_available"),
        "auxiliary_verifiers": {name: stages[name] for name in ("dom_model", "screenshot_verifier") if name in stages},
        "run_status": recording["final"]["run_status"], "actor_reported_status": recording["final"].get("status"),
        "model_turns": len(decisions), "rejected_turns": sum(not row.get("accepted") for row in decisions),
        "parse_error_turns": sum(bool(row.get("error")) and bool(row.get("response")) for row in decisions),
        "model_error_turns": sum(bool(row.get("error")) and not row.get("response") for row in decisions),
        "termination_turns": sum(bool(row.get("accepted")) and (row.get("decision") or {}).get("action") == "terminate" for row in decisions),
        "action_attempts": len(manifest.get("steps", [])),
        "action_errors": sum(not step["action_succeeded"] for step in manifest.get("steps", [])),
        "actions_by_type": dict(Counter(step["action"]["action"] for step in manifest.get("steps", []))),
        "captured_states": len(manifest.get("states", [])), "turn_budget": cap,
        "step_cap_hit": bool(cap and len(decisions) >= cap and recording["final"]["run_status"] == "turn_limit"),
        "step_cap_known": not partial and isinstance(cap, int),
        "output_limit_hits": sum(row.get("output_limit_hit") is True for row in decisions),
        "output_limit_known_calls": sum(isinstance(row.get("output_limit_hit"), bool) for row in decisions),
        "output_limit_unknown_calls": sum(not isinstance(row.get("output_limit_hit"), bool) for row in decisions),
        "actor_latency_seconds": round(sum(row.get("latency_seconds", 0) for row in decisions), 6),
        "action_seconds": round(sum(step.get("duration_seconds", 0) for step in manifest.get("steps", [])), 6),
        "token_usage": usage, "token_usage_known_calls": known, "tokens_per_turn": tpt,
        "turns_missing_usage": missing, "returned_actor_models": sorted(models),
        "completion": grade or {"method": "ungraded", "verdict": "ungraded"}}


def compare(dom: dict[str, Any], screenshot: dict[str, Any]) -> tuple[dict[str, Any], str]:
    for recording, mode in ((dom, "dom"), (screenshot, "screenshot")):
        if recording["task"]["observation_mode"] != mode:
            raise ValueError(f"expected a {mode} recording")
        if recording["task"].get("catalog_sha256") != recording["manifest"].get("catalog_sha256"):
            raise ValueError("task and manifest selected catalog hashes differ")
    for key in ("source_task_id", "instruction", "start_url"):
        if dom["task"][key] != screenshot["task"][key]:
            raise ValueError(f"tasks differ for {key}")
    left, right = dom["manifest"]["controls"], screenshot["manifest"]["controls"]
    # Policies necessarily describe different observations. All other actor
    # controls must match; histories, final answers and state counts may differ.
    if {k: v for k, v in left.items() if k != "prompt_sha256"} != {k: v for k, v in right.items() if k != "prompt_sha256"}:
        raise ValueError("actor model, budget, viewport, action schema or other shared controls differ")
    for key in ("dom_capture_parameters","renderer_versions"):
        if not dom["manifest"].get(key) or dom["manifest"][key] != screenshot["manifest"].get(key):
            raise ValueError(f"shared capture policies differ for {key}")
    if any(dom["task"].get(key) != screenshot["task"].get(key) for key in ("category", "difficulty", "catalog_sha256")):
        raise ValueError("task category, difficulty or catalog hash differs between arms")
    summaries = {"dom": summarize(dom), "screenshot": summarize(screenshot)}
    evaluation_hashes = {row["evaluation"]["rubric_sha256"] for row in summaries.values() if row.get("evaluation")}
    if len(evaluation_hashes) > 1:
        raise ValueError("frozen evaluation rubric differs between arms")
    grades = [summaries[m]["completion"] for m in ("dom", "screenshot")]
    policies = {g["evidence_policy"] for g in grades if g.get("evidence_policy") is not None}
    if len(policies) > 1:
        raise ValueError("completion controls differ for evidence_policy")
    if all(g.get("method") != "ungraded" for g in grades):
        for key in ("rubric_sha256", "evidence_policy", "method", "judge_model", "returned_judge_model", "judge_prompt_sha256", "judge_base_url", "max_output_tokens", "judge_schema_sha256"):
            if grades[0].get(key) != grades[1].get(key):
                raise ValueError(f"completion controls differ for {key}")
    actual_models = [summaries[m]["returned_actor_models"] for m in ("dom", "screenshot")]
    if actual_models[0] and actual_models[1] and actual_models[0] != actual_models[1]:
        raise ValueError("returned actor model versions differ")
    notes = []
    builds, environments = [], []
    for recording in (dom, screenshot):
        profile = recording["manifest"].get("browser_profile_provenance") or {}
        if profile.get("profile_fresh_at_run_start") is not True:
            raise ValueError("browser profile freshness is unverified; use the controlled task launcher")
        builds.append((profile.get("browser_build") or {}).get("image_id"))
        environments.append(profile.get("browser_environment"))
    if not all(isinstance(environment,dict) and environment for environment in environments):
        raise ValueError("browser runtime environments are unverified")
    if environments[0] != environments[1]:
        raise ValueError("browser runtime environments differ")
    if all(builds) and builds[0] != builds[1]:
        raise ValueError("browser image IDs differ")
    if not all(builds):
        raise ValueError("browser builds are unverified")
    both_success = all(g.get("verdict") == "success" for g in grades)
    receipt = {"schema_version": "2.0", "task_id": dom["task"]["source_task_id"],
        "shared_controls": {k: v for k, v in left.items() if k != "prompt_sha256"},
        "actor_policy_sha256": {"dom": left.get("prompt_sha256"), "screenshot": right.get("prompt_sha256")},
        "environment_notes": notes, "category": dom["task"].get("category"),
        "difficulty": dom["task"].get("difficulty"), "catalog_sha256": dom["task"].get("catalog_sha256"), **summaries,
        "screenshot_minus_dom_turns": summaries["screenshot"]["model_turns"] - summaries["dom"]["model_turns"],
        "both_successful": both_success,
        "successful_pair_turn_delta": summaries["screenshot"]["model_turns"] - summaries["dom"]["model_turns"] if both_success else None}
    lines = [f"# {receipt['task_id']}: independent actor runs", "",
        "| Mode | Completion | Actor turns | Rejected | Actions | Actor seconds | Tokens |",
        "|---|---|---:|---:|---:|---:|---:|"]
    for mode, row in summaries.items():
        tokens = str(row["token_usage"]["total_tokens"]) + (" (incomplete)" if row["turns_missing_usage"] else "")
        lines.append(f"| {mode} | {row['completion']['verdict']} | {row['model_turns']} | {row['rejected_turns']} | {row['action_attempts']} | {row['actor_latency_seconds']:.3f} | {tokens} |")
    lines += ["", "Turns include rejected proposals, malformed responses and termination. Judge calls are excluded.",
        "Cached input and reasoning tokens are subsets of input/output usage; they are not added again.",
        "A successful-pair efficiency comparison is available only when both independently graded runs succeed."]
    if notes:
        lines += ["", *notes]
    return receipt, "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dom-run", type=Path, required=True)
    parser.add_argument("--screenshot-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt, markdown = compare(inspect_recording(args.dom_run), inspect_recording(args.screenshot_run))
    if args.output.suffix != ".md":
        raise ValueError("--output must name a Markdown (.md) report")
    if any(args.output.resolve().is_relative_to(path.resolve()) for path in (args.dom_run, args.screenshot_run)):
        raise ValueError("reports must be outside recording folders")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    write_json(args.output.with_suffix(".json"), receipt)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
