"""Account for one actor recording and its evaluation attempts."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from w8bench.task_recorder.prepare_verifier_data import read_object
from w8bench.model_identity import match_model_id
from w8bench.usage import known_token_component, valid_token_component
from w8bench.settings import actual_browser_source_version

# USD per million tokens; estimates use published Standard model tariffs.
# Columns: input, output, cached input, 30-minute cache write, long-context threshold.
TOKEN_PRICES = {
    "gpt-6.1-sol": (2.0, 10.0, 0.1, 2.5, 272000),
    "gemini-3.8-flash": (0.75, 3.75, 0.075, 0.75, None),
    "gpt-5.2": (1.75, 14.0, 0.175, 1.75, None),
    "gemini-3.1-pro-preview": (2.0, 12.0, 0.2, 2.0, 200000),
}


def _object(value):
    return value if isinstance(value, dict) else {}


def _usage_values(value):
    raw = _object(value)
    inputs = _object(raw.get("input_tokens_details") or raw.get("prompt_tokens_details"))
    outputs = _object(raw.get("output_tokens_details") or raw.get("completion_tokens_details"))
    values = {
        "input_tokens": raw.get("input_tokens", raw.get("prompt_tokens")),
        "output_tokens": raw.get("output_tokens", raw.get("completion_tokens")),
        "total_tokens": raw.get("total_tokens"),
        "reasoning_tokens": raw.get("reasoning_tokens", outputs.get("reasoning_tokens")),
        "cached_input_tokens": raw.get("cached_input_tokens", inputs.get("cached_tokens")),
        "cache_write_input_tokens": raw.get("cache_write_input_tokens", raw.get("cache_creation_input_tokens", inputs.get("cache_write_tokens"))),
    }
    values = {key: known_token_component(item) for key, item in values.items()}
    if values["total_tokens"] is None and all(values[key] is not None for key in ("input_tokens", "output_tokens")):
        values["total_tokens"] = values["input_tokens"] + values["output_tokens"]
    return values


def _normalized_usage(value):
    raw = _object(value)
    if not raw:
        return None
    values = _usage_values(raw)
    normalized = {**raw, **values}
    for alias, component in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens"),
                             ("cache_creation_input_tokens", "cache_write_input_tokens")):
        if alias in normalized:
            normalized[alias] = values[component]
    for key, components in (
        ("input_tokens_details", {"cached_tokens": "cached_input_tokens", "cache_write_tokens": "cache_write_input_tokens"}),
        ("prompt_tokens_details", {"cached_tokens": "cached_input_tokens", "cache_write_tokens": "cache_write_input_tokens"}),
        ("output_tokens_details", {"reasoning_tokens": "reasoning_tokens"}),
        ("completion_tokens_details", {"reasoning_tokens": "reasoning_tokens"}),
    ):
        if key in normalized:
            details = _object(normalized[key])
            normalized[key] = {**details, **{name: values[component] for name, component in components.items() if name in details}}
            if "cache_write_tokens_details" in details:
                writes = _object(details["cache_write_tokens_details"])
                normalized[key]["cache_write_tokens_details"] = {
                    name: known_token_component(item) for name, item in writes.items()
                }
    return normalized


def _load_receipts(recording, source, task, manifest, partial):
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
    return evaluation_path, evaluation, grade, secondary, stages


def _actor_usage(decisions, source, partial):
    usage = dict.fromkeys(("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens"), 0)
    known = dict.fromkeys(usage, 0)
    models = set()
    missing = 0
    for row in decisions:
        components = _usage_values(row.get("usage"))
        missing += any(components[key] is None for key in ("input_tokens", "output_tokens"))
        for key in usage:
            value = components[key]
            if valid_token_component(value):
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
    tpt = {key: {"tokens": usage[key], "known_calls": known[key], "total_calls": len(decisions),
        "known_usage_mean": usage[key] / known[key] if known[key] else None,
        "mean": usage[key] / len(decisions) if decisions and known[key] == len(decisions) and not partial else None,
        "coverage": "complete" if known[key] == len(decisions) and not partial else "partial" if known[key] else "none"}
        for key in ("input_tokens", "output_tokens")}
    return usage, known, models, missing, tpt


def _completion_streams(grade, secondary):
    streams = {}
    for name, item in (("paired_completion", grade), ("actor_native_completion", secondary)):
        if item is not None:
            calls = item.get("judge_calls", 0)
            normalized = _normalized_usage(item.get("usage"))
            streams[name] = {"model": item.get("judge_model"), "calls": calls, "usage": normalized,
                "call_records": [{"model": item.get("judge_model"),
                    "returned_model": item.get("returned_judge_model"), "usage": normalized}] if calls == 1 else [],
                "usage_coverage": "complete" if not calls or all((normalized or {}).get(key) is not None for key in ("input_tokens", "output_tokens")) else "unknown"}
    return streams


def _verifier_streams(streams, stages, evaluation_path):
    for name in ("dom_model", "screenshot_verifier"):
        stage = stages.get(name)
        if stage is None:
            continue
        stage_usage = stage.get("usage") or {}
        provider_metrics = stage.get("provider_call_metrics") or {}
        metrics_file = evaluation_path.parent / name / "run_metrics.json"
        metrics_hash = (stage.get("normalized_metrics_sha256") if "normalized_metrics_sha256" in stage
            else (stage.get("artifacts_sha256") or {}).get("run_metrics.json"))
        if not provider_metrics and metrics_hash and metrics_file.is_file():
            if hashlib.sha256(metrics_file.read_bytes()).hexdigest() != metrics_hash:
                raise ValueError("normalized verifier accounting artifact changed")
            provider_metrics = read_object(metrics_file).get("provider_call_metrics") or {}
        for model, raw in stage_usage.items():
            if model == "combined":
                continue
            principal_known = all(_usage_values(raw)[component] is not None for component in ("input_tokens", "output_tokens"))
            declared_coverage = stage.get("usage_coverage")
            if not principal_known and (stage.get("calls") or {}).get(model) != 0:
                declared_coverage = "unknown"
            streams[f"{name}:{model}"] = {"model": model, "calls": (stage.get("calls") or {}).get(model),
                "call_records": [call for value in provider_metrics.values() for call in value.get("calls", []) if call.get("configured_model") == model],
                "usage": _normalized_usage(raw), "usage_coverage": declared_coverage or (
                    "complete" if stage.get("status") == "complete" and isinstance(raw, dict)
                    and all(_usage_values(raw)[component] is not None for component in ("input_tokens", "output_tokens"))
                    and (not raw.get("usage_known_calls") or all(raw["usage_known_calls"].get(component)
                        == (stage.get("calls") or {}).get(model) for component in ("input_tokens", "output_tokens")))
                    and not raw.get("calls_without_reported_usage", 0) else "unknown")}
        if not stage_usage:
            streams[name] = {"model": stage.get("configured_models"), "calls": stage.get("calls"),
                "call_records": [call for value in provider_metrics.values() for call in value.get("calls", [])],
                "usage": None, "usage_coverage": stage.get("usage_coverage", "unknown")}


def _audit_streams(streams, stages):
    audit = stages.get("audit") or {}
    for stage_name in ("inventory", "adjudication"):
        audit_attempts = [*audit.get("attempt_history", []), audit] if audit else []
        calls = [call for attempt in audit_attempts for call in attempt.get("calls", []) if call.get("stage") == stage_name]
        if not calls and not audit:
            continue
        stream_usage = dict.fromkeys(("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens"), None)
        coverage = dict.fromkeys(stream_usage, 0)
        for call in calls:
            values = _usage_values(call.get("usage"))
            for key in stream_usage:
                value = values[key]
                if valid_token_component(value):
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
    return audit


def _append_attempt_history(streams, stages, evaluation_path):
    # Resume histories represent distinct attempted calls. Reused completed stages
    # are only present as the current receipt and are therefore counted once.
    for name in ("paired_completion", "dom_model", "screenshot_verifier"):
        for prior in stages.get(name, {}).get("attempt_history", []):
            prior_usage = prior.get("usage") or {}
            if name == "paired_completion":
                member = streams.setdefault(name, {"model": "gpt-6.1-sol", "calls": 0,
                    "usage": None, "usage_coverage": "complete", "_history_only": True})
                member.setdefault("history_attempts", []).append({"usage": prior_usage or None,
                    "calls": prior.get("calls"), "usage_coverage": prior.get("usage_coverage", "unknown"),
                    "status": prior.get("status"),
                    "call_records": [{"model": "gpt-6.1-sol",
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
                historical_models = [model for model in prior_usage if model != "combined"]
                for model in historical_models or [None]:
                    key = f"{name}:{model}" if model else name
                    member = streams.setdefault(key, {"model": model or prior.get("configured_models"),
                        "calls": 0, "usage": None, "usage_coverage": "complete", "_history_only": True})
                    member.setdefault("history_attempts", []).append({"usage": prior_usage.get(model) if model else None,
                        "calls": (prior.get("calls") or {}).get(model) if isinstance(prior.get("calls"), dict) else prior.get("calls"),
                        "usage_coverage": prior.get("usage_coverage", "unknown"), "status": prior.get("status"),
                        "call_records": [call for value in provider_metrics.values() for call in value.get("calls", []) if model is None or call.get("configured_model") == model]})


def _combine_attempt_usage(streams):
    for member in streams.values():
        histories = member.get("history_attempts", [])
        if not histories:
            continue
        current = {key: member.get(key) for key in ("usage", "calls", "usage_coverage", "call_records")}
        attempts = list(histories) if member.pop("_history_only", False) else [*histories, current]
        totals = dict.fromkeys(("input_tokens", "output_tokens", "total_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens"), None)
        reported = dict.fromkeys(totals, 0)
        for attempt in attempts:
            values = _usage_values(attempt.get("usage"))
            for key, value in values.items():
                if valid_token_component(value):
                    totals[key] = (totals[key] or 0) + value
                    reported[key] += 1
        unknown_attempts = sum(attempt.get("usage_coverage") != "complete" or
            any(_usage_values(attempt.get("usage"))[key] is None for key in ("input_tokens", "output_tokens"))
            and attempt.get("calls") != 0 for attempt in attempts)
        member.update(current_attempt=current, attempts=attempts, attempt_count=len(attempts), usage=totals,
            call_records=[call for attempt in attempts for call in attempt.get("call_records") or []],
            usage_known_attempts=reported, known_calls=sum(attempt.get("calls", 0) or 0 for attempt in attempts if isinstance(attempt.get("calls"), int)),
            calls=sum(attempt["calls"] for attempt in attempts) if all(isinstance(attempt.get("calls"), int) for attempt in attempts) else None,
            unknown_attempts=unknown_attempts, usage_coverage="complete" if not unknown_attempts else "partial" if any(reported.values()) else "unknown")


def _evaluation_streams(stages, evaluation, evaluation_path, grade, secondary):
    streams = _completion_streams(grade, secondary)
    _verifier_streams(streams, stages, evaluation_path)
    audit = _audit_streams(streams, stages)
    _append_attempt_history(streams, stages, evaluation_path)
    _combine_attempt_usage(streams)
    if evaluation is not None:
        import_path = evaluation_path.parent / "rubric_import.json"
        declaration = read_object(import_path) if import_path.is_file() else None
        if declaration is not None and declaration.get("model_calls") == 0:
            streams["rubric_import"] = {"calls": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "usage_coverage": "complete", "preparation_receipt": declaration,
                "scope": "Frozen-rubric import only; external rubric preparation is not charged per trial."}
    return streams, audit


def _price_call(call, stream, assumptions, price_sources):
    model = (call.get("returned_model") or call.get("response_model") or call.get("returned_judge_model")
        or call.get("configured_model") or call.get("requested_model") or call.get("model") or stream.get("model"))
    selected = next((key for key in TOKEN_PRICES if match_model_id(key, model)["matched"]), None)
    raw = call.get("usage") if isinstance(call.get("usage"), dict) else call
    input_tokens = raw.get("input_tokens", raw.get("prompt_tokens"))
    output_tokens = raw.get("output_tokens", raw.get("completion_tokens"))
    if (not selected or call.get("usage_reported") is False or
            any(not valid_token_component(value) for value in (input_tokens, output_tokens))):
        return None
    details = _object(raw.get("input_tokens_details") or raw.get("prompt_tokens_details"))
    cached = raw.get("cached_input_tokens", details.get("cached_tokens"))
    written = raw.get("cache_write_input_tokens", raw.get("cache_creation_input_tokens", details.get("cache_write_tokens")))
    if cached is None:
        cached = 0
        assumptions.add("unreported_cached_input_priced_as_ordinary_input")
    if written is None:
        written = 0
        assumptions.add("unreported_cache_writes_priced_as_ordinary_input")
    if (any(not valid_token_component(value) for value in (cached, written))
            or cached + written > input_tokens):
        return None
    price_sources.add("https://ai.google.dev/gemini-api/docs/pricing" if selected.startswith("gemini-")
        else "https://developers.openai.com/api/docs/pricing")
    if selected == "gemini-3.8-flash":
        assumptions.add("gemini_3_8_flash_introductory_rates_through_2026_12_31")
    pin, pout, pcache, pwrite, threshold = TOKEN_PRICES[selected]
    if threshold is not None and input_tokens > threshold:
        pin, pout, pcache, pwrite = pin * 2, pout * 1.5, pcache * 2, pwrite * 2
    write_details = _object(details.get("cache_write_tokens_details"))
    written_12h = write_details.get("ttl_12h_tokens", 0)
    if written and not write_details:
        assumptions.add("cache_write_lifetime_assumed_30_minutes")
    if not valid_token_component(written_12h) or written_12h > written:
        return None
    return ((input_tokens - cached - written) * pin + cached * pcache
        + written * pwrite + written_12h * pwrite + output_tokens * pout) / 1000000


def _price_stream(stream):
    estimate, priced, assumptions, price_sources = 0.0, 0, set(), set()
    records = stream.get("call_records", [])
    for call in records:
        amount = _price_call(call, stream, assumptions, price_sources)
        if amount is not None:
            estimate += amount
            priced += 1
    calls = stream.get("calls")
    complete = (type(calls) is int and calls == priced and not stream.get("unknown_attempts")
        and stream.get("usage_coverage") == "complete")
    stream["cost"] = {"currency": "USD", "kind": "estimated_from_list_prices", "price_date": "2026-11-16",
        "sources": sorted(price_sources),
        "source": next(iter(price_sources)) if len(price_sources) == 1 else None,
        "estimated_usd": round(estimate, 8) if complete else None,
        "known_usage_estimate_usd": round(estimate, 8) if priced or calls == 0 and complete else None,
        "priced_calls": priced, "unpriced_calls": max(0, calls - priced) if type(calls) is int else None,
        "unknown_attempts": stream.get("unknown_attempts", 0), "coverage": "complete" if complete else "partial" if priced else "unknown",
        "assumptions": sorted(assumptions), "reason": None if complete else "missing_per_call_usage_or_attempt_coverage"}


def _actor_statistics(recording, manifest, decisions, partial, cap):
    return {"run_status": recording["final"]["run_status"], "actor_reported_status": recording["final"].get("status"),
        "stall_advisory_matches": sum(bool(row.get("stall_advisory")) for row in decisions),
        "stall_advisory_match_counts": dict(Counter(row["stall_advisory"] for row in decisions if row.get("stall_advisory"))),
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
        "action_seconds": round(sum(step.get("duration_seconds", 0) for step in manifest.get("steps", [])), 6)}


def _native_model_mismatches(streams, task, recording):
    mismatches = []
    for stream_name, stream in streams.items():
        verifier = stream_name.split(":", 1)[0]
        if verifier not in {"dom_model", "screenshot_verifier"}:
            continue
        for index, call in enumerate(stream.get("call_records") or [], 1):
            match = match_model_id(call.get("configured_model", stream.get("model")), call.get("returned_model"))
            if not match["matched"]:
                mismatches.append({"recording_sha256": recording.get("recording_sha256"),
                    "task_id": task["source_task_id"], "actor_arm": task["observation_mode"],
                    "trial_id": str(task.get("run_name") or recording["manifest"].get("run_name")),
                    "verifier": verifier, "stage": call.get("stage", "unattributed"),
                    "stage_call_path": call.get("stage_call_path"), "stream": stream_name,
                    "call_index": index, **match})
    return mismatches


def _citation_diagnostics(stages):
    diagnostics = {}
    for verifier in ("dom_model", "screenshot_verifier"):
        stage = stages.get(verifier) or {}
        value = stage.get("citation_checks")
        diagnostics[verifier] = value if isinstance(value, dict) else None
    return diagnostics


def summarize(recording: dict[str, Any]) -> dict[str, Any]:
    manifest, decisions, task = recording["manifest"], recording["decisions"], recording["task"]
    source = Path(recording["source"])
    partial = recording.get("partial_recording", False)
    evaluation_path, evaluation, grade, secondary, stages = _load_receipts(recording, source, task, manifest, partial)
    transport_receipts = []
    for path in sorted((source / "turns").glob("*/transport_attempts.jsonl")):
        transport_receipts.extend(json.loads(line) for line in path.read_text().splitlines() if line)
    for pending in sorted((source / "turns").glob("*/transport_pending.json")):
        item = read_object(pending)
        if item.get("status") == "started":
            transport_receipts.append({**item, "usage": None, "response_received": False, "model": task.get("model")})
    failed_transport = [row for row in transport_receipts if row.get("response_received") is not True]
    transport_unknown = sum(not all(_usage_values(row.get("usage"))[key] is not None
        for key in ("input_tokens", "output_tokens")) for row in failed_transport)
    known_zero_calls = not decisions and not transport_receipts and (not partial or recording.get("actor_calls_known_zero") is True)
    usage, known, models, missing, tpt = _actor_usage(decisions, source, partial and not known_zero_calls)
    if known_zero_calls:
        usage.update(input_tokens=0, output_tokens=0, total_tokens=0)
    streams, audit = _evaluation_streams(stages, evaluation, evaluation_path, grade, secondary)
    primary_streams = [value for key, value in streams.items() if key in {"paired_completion", "actor_native_completion"}]
    judge_usage = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        values = [value for stream in primary_streams
                  if valid_token_component(value := (stream.get("usage") or {}).get(key))]
        judge_usage[key] = sum(values) if values else 0 if not primary_streams or all(stream.get("calls") == 0 for stream in primary_streams) else None
    if grade is not None and grade.get("verdict") not in {"success", "failure", "uncertain", "ungraded"}:
        raise ValueError("invalid completion verdict")
    cost_streams = {"actor": {"model": task.get("model"), "calls": len(decisions) + len(failed_transport), "usage": usage,
        "call_records": [*decisions, *failed_transport], "usage_known_calls": known,
        "unknown_attempts": max(int(partial and not known_zero_calls), transport_unknown),
        "response_calls": len(decisions), "failed_transport_attempts": len(failed_transport),
        "usage_coverage": "partial" if partial and not known_zero_calls or missing or transport_unknown else "complete"}, **streams}
    for stream in cost_streams.values():
        _price_stream(stream)
    response_cost = {"model": task.get("model"), "calls": len(decisions), "call_records": decisions,
        "usage_coverage": "partial" if missing else "complete"}
    transport_cost = {"model": task.get("model"), "calls": len(failed_transport), "call_records": failed_transport,
        "unknown_attempts": transport_unknown, "usage_coverage": "partial" if transport_unknown else "complete"}
    _price_stream(response_cost)
    _price_stream(transport_cost)
    cost_streams["actor"]["cost_breakdown"] = {"responses": response_cost["cost"], "failed_transport": transport_cost["cost"]}
    cap = manifest.get("controls", {}).get("max_turns")
    return {"run": str(source), "recording_available": not partial, "partial_recording": partial,
        "turns_complete": not partial or known_zero_calls,
        "cost_coverage": "partial" if partial and not known_zero_calls or missing else "complete",
        "category": task.get("category"), "difficulty": task.get("difficulty"), "catalog_sha256": task.get("catalog_sha256"),
        "secondary_completion": secondary, "judge_usage": judge_usage, "judge_usage_streams": streams,
        "native_model_mismatches": _native_model_mismatches(streams, task, recording),
        "citation_checks": _citation_diagnostics(stages),
        "actor_effective_settings": manifest.get("effective_settings"),
        "evaluation_effective_settings": (evaluation or {}).get("effective_settings"),
        "scheduled_effective_settings": recording.get("scheduled_effective_settings"),
        "actual_browser_source_version": actual_browser_source_version(manifest),
        "completion_grade_available": grade is not None,
        "cost_streams": cost_streams,
        "judge_calls": sum(stream.get("calls") if isinstance(stream.get("calls"), int) else stream.get("known_calls", 0) for stream in primary_streams),
        "judge_calls_missing_usage": sum(max(1, stream.get("unknown_attempts", 0)) for stream in primary_streams if stream["usage_coverage"] != "complete"),
        "recording_sha256": recording.get("recording_sha256"),
        "evaluation": evaluation, "evaluation_path": str(evaluation_path) if evaluation else None,
        "evaluation_coverage": (evaluation or {}).get("coverage"),
        "evidence_audit": audit.get("metrics") if audit.get("status") == "complete" else None,
        "evidence_audit_status": audit.get("status", "not_available"),
        "auxiliary_verifiers": {name: stages[name] for name in ("dom_model", "screenshot_verifier") if name in stages},
        **_actor_statistics(recording, manifest, decisions, partial, cap),
        "actor_transport_attempts": len(transport_receipts) if transport_receipts or manifest.get("turn_policy") == "actor-response-turn/v2" else None,
        "failed_transport_attempts": sum(item.get("status") != "started" for item in failed_transport),
        "pending_transport_attempts": sum(item.get("status") == "started" for item in failed_transport), "failed_transport_attempts_missing_usage": transport_unknown,
        "failed_transport_usage": [row.get("usage") for row in failed_transport],
        "token_usage": usage, "token_usage_known_calls": known, "tokens_per_turn": tpt,
        "turns_missing_usage": missing, "returned_actor_models": sorted(models),
        "completion": grade or {"method": "ungraded", "verdict": "ungraded"}}
