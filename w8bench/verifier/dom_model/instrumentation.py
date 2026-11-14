"""Call and provider-token accounting for the standalone DOM-model runner."""

from __future__ import annotations

import inspect

from typing import Any


def instrument_client_calls(client: Any) -> None:
    if hasattr(client, "_benchmark_call_metrics"):
        return
    metrics = {"logical_calls": 0, "endpoint_calls": 0}
    original_create = client.create

    async def counted_logical_create(*args: Any, **kwargs: Any):
        metrics["logical_calls"] += 1
        stage_path = []
        frame = inspect.currentframe()
        try:
            while frame is not None:
                module = frame.f_globals.get("__name__", "")
                if (module.endswith(".rubric_agent") or module.endswith(".dom_model_agent")) and frame.f_code.co_name != "_call_llm":
                    stage_path.append(f"{module}.{frame.f_code.co_name}")
                frame = frame.f_back
        finally:
            del frame
        stage_tokens = [(endpoint, endpoint._logical_stage.set(tuple(stage_path)))
            for endpoint in getattr(client, "_clients", []) if hasattr(endpoint, "_logical_stage")]
        try:
            return await original_create(*args, **kwargs)
        finally:
            for endpoint, token in stage_tokens:
                endpoint._logical_stage.reset(token)

    client.create = counted_logical_create
    for endpoint in getattr(client, "_clients", []):
        original_endpoint_create = endpoint.create

        async def counted_endpoint_create(
            *args: Any, _original=original_endpoint_create, **kwargs: Any
        ):
            metrics["endpoint_calls"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = counted_endpoint_create
    client._benchmark_call_metrics = metrics


def call_metrics(client: Any) -> dict[str, Any]:
    metrics = getattr(client, "_benchmark_call_metrics", {})
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
        inputs = [record["input_tokens"] for record in records if record.get("input_tokens") is not None]
        outputs = [record["output_tokens"] for record in records if record.get("output_tokens") is not None]
        prompt = sum(inputs) if inputs else None
        completion = sum(outputs) if outputs else None
    writes = [record["cache_write_input_tokens"] for record in records if record.get("cache_write_input_tokens") is not None]
    reads = [record["cached_input_tokens"] for record in records if record.get("cached_input_tokens") is not None]
    thinking = [record["reasoning_tokens"] for record in records if record.get("reasoning_tokens") is not None]
    return {
        "prompt_tokens": prompt, "input_tokens": prompt,
        "completion_tokens": completion, "output_tokens": completion,
        "cached_input_tokens": sum(reads) if reads else None,
        "cache_write_input_tokens": sum(writes) if writes else None,
        "reasoning_tokens": sum(thinking) if thinking else None,
        "total_tokens": (prompt or 0) + (completion or 0) if prompt is not None or completion is not None else None,
        "usage_known_calls": {key: sum(record.get("usage_fields_reported", {}).get(key, False) for record in records)
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens")},
        "cached_input_usage_reported_calls": len(reads), "reasoning_usage_reported_calls": len(thinking),
        "calls_without_reported_usage": sum(not record.get("usage_reported", False) for record in records),
        "cache_write_usage_reported_calls": len(writes),
    }
