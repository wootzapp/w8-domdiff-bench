"""Call and provider-token accounting matching Microsoft's standalone runner."""

from __future__ import annotations

from typing import Any


def instrument_client_calls(client: Any) -> None:
    if hasattr(client, "_benchmark_call_metrics"):
        return
    metrics = {"logical_calls": 0, "api_attempts": 0}
    original_create = client.create

    async def counted_logical_create(*args: Any, **kwargs: Any):
        metrics["logical_calls"] += 1
        return await original_create(*args, **kwargs)

    client.create = counted_logical_create
    for endpoint in getattr(client, "_clients", []):
        original_endpoint_create = endpoint.create

        async def counted_endpoint_create(
            *args: Any, _original=original_endpoint_create, **kwargs: Any
        ):
            metrics["api_attempts"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = counted_endpoint_create
    client._benchmark_call_metrics = metrics


def call_metrics(client: Any) -> dict[str, int]:
    metrics = getattr(client, "_benchmark_call_metrics", {})
    logical = int(metrics.get("logical_calls", 0))
    attempts = int(metrics.get("api_attempts", 0))
    return {
        "logical_calls": logical,
        "api_attempts": attempts,
        "retries": max(0, attempts - logical),
    }


def usage_dict(client: Any) -> dict[str, int]:
    prompt = completion = reasoning = 0
    for inner in getattr(client, "_clients", []):
        usage = inner.total_usage()
        prompt += int(getattr(usage, "prompt_tokens", 0))
        completion += int(getattr(usage, "completion_tokens", 0))
        reasoning += int(getattr(usage, "reasoning_tokens", 0))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "total_tokens": prompt + completion,
    }

