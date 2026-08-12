from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from .usage import UsageLedger


class JsonJudge(Protocol):
    def complete_json(
        self,
        *,
        role: str,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.0,
    ) -> dict[str, Any]: ...


def _extract_json(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Judge did not return a JSON object")
        parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Judge response must be a JSON object")
    return parsed


@dataclass
class OpenAIJsonJudge:
    client: Any
    ledger: UsageLedger
    max_retries: int = 5
    timeout_seconds: float = 180.0

    @classmethod
    def from_config(
        cls,
        endpoint_config: dict[str, Any],
        ledger: UsageLedger,
        *,
        max_retries: int,
        timeout_seconds: float,
    ) -> "OpenAIJsonJudge":
        from openai import OpenAI

        api_key_env = str(endpoint_config.get("api_key_env") or "OPENAI_API_KEY")
        import os

        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Required environment variable is not set: {api_key_env}")
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout_seconds}
        if endpoint_config.get("base_url"):
            kwargs["base_url"] = endpoint_config["base_url"]
        return cls(OpenAI(**kwargs), ledger, max_retries, timeout_seconds)

    def complete_json(
        self,
        *,
        role: str,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                )
                usage = response.usage
                usage_dict = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage or {})
                self.ledger.add(role, usage_dict)
                content = response.choices[0].message.content or ""
                return _extract_json(content)
            except Exception as exc:  # provider errors have several SDK-specific types
                last_error = exc
                if attempt + 1 >= self.max_retries:
                    break
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Judge call failed after {self.max_retries} attempts: {last_error}")

