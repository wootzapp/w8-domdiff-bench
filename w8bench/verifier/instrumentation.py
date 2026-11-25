"""Logical calls, provider attempts, stages and token usage."""
from __future__ import annotations

import inspect
from typing import Any

from w8bench.usage import known_token_component


def _stage_path() -> list[str]:
    stack = []
    frame = inspect.currentframe()
    try:
        while frame is not None:
            stack.append((frame.f_globals, frame.f_code.co_name, type(frame.f_locals.get("self"))))
            frame = frame.f_back
    finally:
        del frame
    stage_path = []
    evidence_mode = None
    for namespace, name, owner in reversed(stack):
        module = namespace.get("__name__", "")
        for cls in owner.__mro__:
            for kind in ("dom_model", "screenshot_verifier"):
                if cls.__module__.startswith(f"w8bench.verifier.{kind}."):
                    evidence_mode = kind
                    break
            else:
                continue
            break
        stages = namespace.get("_LOGICAL_STAGE_NAMES", {})
        label = stages.get(evidence_mode, {}).get(name)
        if name == "_call_llm" or name in namespace.get("_LOGICAL_STAGE_EXCLUDES", ()):
            continue
        if label is not None:
            stage_path.append(label)
        elif (module.endswith(".rubric_agent") or module.endswith(".dom_model_agent")) and module != "w8bench.verifier.rubric_agent":
            stage_path.append(f"{module}.{name}")
    return list(reversed(stage_path))


def instrument_client_calls(client: Any, *, receipt: bool = False) -> dict[str, Any] | None:
    if not receipt and hasattr(client, "_benchmark_call_metrics"):
        return None
    metrics = {"logical_calls": 0, "endpoint_calls": 0}
    if receipt:
        metrics.update(api_attempts=0, http_attempts=0, http_attempts_complete=False, calls=[])
    original_create = client.create

    async def counted_logical_create(*args: Any, **kwargs: Any):
        metrics["logical_calls"] += 1
        stage_path = _stage_path()
        stage_tokens = [(endpoint, endpoint._logical_stage.set(tuple(stage_path)))
            for endpoint in getattr(client, "_clients", []) if hasattr(endpoint, "_logical_stage")]
        try:
            return await original_create(*args, **kwargs)
        finally:
            for endpoint, token in stage_tokens:
                endpoint._logical_stage.reset(token)
            if receipt:
                details = call_metrics(client, counters=metrics)
                metrics.update((key, details[key]) for key in (
                    "api_attempts", "http_attempts", "http_attempts_complete", "calls",
                    "configured_models", "returned_models", "endpoint_retries", "sdk_http_retries"))

    client.create = counted_logical_create
    for endpoint in getattr(client, "_clients", []):
        original_endpoint_create = endpoint.create

        async def counted_endpoint_create(*args: Any, _original=original_endpoint_create, **kwargs: Any):
            metrics["endpoint_calls"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = counted_endpoint_create
    if receipt:
        return metrics
    client._benchmark_call_metrics = metrics


def call_metrics(client: Any, *, counters: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = getattr(client, "_benchmark_call_metrics", {}) if counters is None else counters
    logical = int(metrics.get("logical_calls", 0))
    endpoint_calls = int(metrics.get("endpoint_calls", 0))
    endpoints = list(getattr(client, "_clients", []))
    attempts = sum(int(getattr(endpoint, "_http_attempts", 0)) for endpoint in endpoints)
    complete = bool(endpoints) and all(getattr(endpoint, "_http_attempts_observed", False) for endpoint in endpoints)
    records = [dict(record) for endpoint in endpoints for record in getattr(endpoint, "_call_records", [])]
    return {
        "logical_calls": logical, "endpoint_calls": endpoint_calls,
        "api_attempts": attempts, "http_attempts": attempts,
        "http_attempts_complete": complete,
        "retries": max(0, attempts - logical) if complete else None,
        "endpoint_retries": max(0, endpoint_calls - logical),
        "sdk_http_retries": max(0, attempts - endpoint_calls) if complete else None,
        "configured_models": sorted({record["configured_model"] for record in records}),
        "returned_models": sorted({record["returned_model"] for record in records if record.get("returned_model")}),
        "calls": records,
    }


def usage_dict(client: Any) -> dict[str, Any]:
    prompt = completion = 0
    records = []
    for inner in getattr(client, "_clients", []):
        usage = inner.total_usage()
        prompt += int(getattr(usage, "prompt_tokens", 0))
        completion += int(getattr(usage, "completion_tokens", 0))
        records.extend(getattr(inner, "_call_records", []))
    if records:
        inputs = [value for record in records if (value := known_token_component(record.get("input_tokens"))) is not None]
        outputs = [value for record in records if (value := known_token_component(record.get("output_tokens"))) is not None]
        prompt = sum(inputs) if inputs else None
        completion = sum(outputs) if outputs else None
    totals = []
    residuals = []
    reconciled = []
    for record in records:
        inputs, outputs, total = (known_token_component(record.get(key))
            for key in ("input_tokens", "output_tokens", "total_tokens"))
        invalid_total = record.get("total_tokens") is not None and total is None
        if record.get("total_tokens") is None and inputs is not None and outputs is not None:
            total = inputs + outputs
        if total is not None:
            totals.append(total)
        difference = total - inputs - outputs if all(value is not None for value in (inputs, outputs, total)) else None
        reconciled.append(False if invalid_total else difference == 0 if difference is not None else None)
        if difference is not None and difference >= 0:
            residuals.append(difference)
    writes = [value for record in records if (value := known_token_component(record.get("cache_write_input_tokens"))) is not None]
    reads = [value for record in records if (value := known_token_component(record.get("cached_input_tokens"))) is not None]
    thinking = [value for record in records if (value := known_token_component(record.get("reasoning_tokens"))) is not None]
    return {
        "prompt_tokens": prompt, "input_tokens": prompt,
        "completion_tokens": completion, "output_tokens": completion,
        "cached_input_tokens": sum(reads) if reads else None,
        "cache_write_input_tokens": sum(writes) if writes else None,
        "reasoning_tokens": sum(thinking) if thinking else None,
        "total_tokens": sum(totals) if totals else None if records else prompt + completion,
        "unattributed_tokens": sum(residuals) if residuals else None if records else 0,
        "token_components_reconcile": (False if False in reconciled else None if None in reconciled
            else True),
        "usage_known_calls": {key: sum(bool(record.get("usage_fields_reported", {}).get(key, False))
            and known_token_component(record.get(key)) is not None for record in records)
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens")}
            | {"total_tokens": len(totals), "unattributed_tokens": len(residuals)},
        "cached_input_usage_reported_calls": len(reads), "reasoning_usage_reported_calls": len(thinking),
        "calls_without_reported_usage": sum(not record.get("usage_reported", False) for record in records),
        "cache_write_usage_reported_calls": len(writes),
    }
