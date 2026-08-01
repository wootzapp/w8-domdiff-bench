"""Reusable exact call and token instrumentation for Universal Verifier clients."""

from __future__ import annotations

from typing import Any


MODEL_CLIENTS = {
    "gpt-5.2": "_gpt5_client",
    "o4-mini": "_o4mini_client",
}


def client_usage(client: Any) -> dict[str, int]:
    prompt = completion = reasoning = 0
    for endpoint in getattr(client, "_clients", [client]):
        getter = getattr(endpoint, "total_usage", None)
        if not callable(getter):
            continue
        usage = getter()
        prompt += int(getattr(usage, "prompt_tokens", 0) or 0)
        completion += int(getattr(usage, "completion_tokens", 0) or 0)
        reasoning += int(getattr(usage, "reasoning_tokens", 0) or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "total_tokens": prompt + completion,
    }


class VerifierInstrumentation:
    def __init__(self) -> None:
        self.logical_calls = {model: 0 for model in MODEL_CLIENTS}
        self.api_attempts = {model: 0 for model in MODEL_CLIENTS}

    def install(self, agent: Any) -> None:
        for model, attribute in MODEL_CLIENTS.items():
            client = getattr(agent, attribute)
            original_logical = client.create

            async def counted_logical(
                *args: Any,
                _model: str = model,
                _original: Any = original_logical,
                **kwargs: Any,
            ) -> Any:
                self.logical_calls[_model] += 1
                return await _original(*args, **kwargs)

            client.create = counted_logical
            for endpoint in getattr(client, "_clients", []):
                original_attempt = endpoint.create

                async def counted_attempt(
                    *args: Any,
                    _model: str = model,
                    _original: Any = original_attempt,
                    **kwargs: Any,
                ) -> Any:
                    self.api_attempts[_model] += 1
                    return await _original(*args, **kwargs)

                endpoint.create = counted_attempt

    def snapshot(self, agent: Any) -> dict[str, Any]:
        usage = {
            model: client_usage(getattr(agent, attribute))
            for model, attribute in MODEL_CLIENTS.items()
        }
        usage["combined"] = {
            key: sum(usage[model][key] for model in MODEL_CLIENTS)
            for key in usage["gpt-5.2"]
        }
        logical_total = sum(self.logical_calls.values())
        attempt_total = sum(self.api_attempts.values())
        return {
            "logical_llm_calls": {
                **self.logical_calls,
                "total": logical_total,
            },
            "api_attempts": {
                **self.api_attempts,
                "total": attempt_total,
            },
            "retries": attempt_total - logical_total,
            "token_usage": usage,
            "token_accounting_note": (
                "Reasoning tokens are included in completion_tokens and are not "
                "added again to total_tokens."
            ),
        }


def instrument_agent(agent: Any) -> VerifierInstrumentation:
    instrumentation = VerifierInstrumentation()
    instrumentation.install(agent)
    return instrumentation
