"""Provider-neutral tool-call transcript helpers for the grep verifier."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class NormalizedToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str


def _value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(exclude_none=True)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_") and item is not None
        }
    raise TypeError(f"Cannot serialize tool transcript item {type(value).__name__}")


def _arguments(raw: Any) -> tuple[dict[str, Any], str]:
    if isinstance(raw, dict):
        return dict(raw), json.dumps(raw, ensure_ascii=False, sort_keys=True)
    text = str(raw or "")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must decode to a JSON object")
    return parsed, text


def response_family(result: Any) -> str:
    message = getattr(result, "message", None)
    if message is not None and _value(message, "output", None) is not None:
        return "responses"
    return "chat"


def normalize_tool_calls(result: Any) -> list[NormalizedToolCall]:
    calls: list[Any] = list(getattr(result, "tool_calls", None) or [])
    if not calls:
        message = getattr(result, "message", None)
        for item in list(_value(message, "output", None) or []):
            if str(_value(item, "type", "")) in {"function_call", "custom_tool_call"}:
                calls.append(item)
    normalized: list[NormalizedToolCall] = []
    for call in calls:
        function = _value(call, "function", None)
        if function is not None:
            name = str(_value(function, "name", ""))
            raw_arguments = _value(function, "arguments", "")
            call_id = str(_value(call, "id", "") or _value(call, "call_id", ""))
        else:
            name = str(_value(call, "name", ""))
            raw_arguments = _value(call, "arguments", "")
            call_id = str(_value(call, "call_id", "") or _value(call, "id", ""))
        if not call_id or not name:
            raise ValueError("Tool call is missing call_id or name")
        arguments, raw_text = _arguments(raw_arguments)
        normalized.append(
            NormalizedToolCall(
                call_id=call_id,
                name=name,
                arguments=arguments,
                raw_arguments=raw_text,
            )
        )
    return normalized


def append_assistant_tool_calls(
    messages: list[dict[str, Any]], result: Any, calls: Sequence[NormalizedToolCall]
) -> str:
    family = response_family(result)
    if family == "responses":
        response = getattr(result, "message", None)
        for item in list(_value(response, "output", None) or []):
            messages.append(_as_dict(item))
        return family
    raw_calls = [
        {
            "id": call.call_id,
            "type": "function",
            "function": {"name": call.name, "arguments": call.raw_arguments},
        }
        for call in calls
    ]
    messages.append(
        {
            "role": "assistant",
            "content": getattr(result, "content", "") or None,
            "tool_calls": raw_calls,
        }
    )
    return family


def append_tool_output(
    messages: list[dict[str, Any]],
    *,
    family: str,
    call_id: str,
    output: str,
) -> None:
    if family == "responses":
        messages.append(
            {"type": "function_call_output", "call_id": call_id, "output": output}
        )
    else:
        messages.append(
            {"role": "tool", "tool_call_id": call_id, "content": output}
        )


def count_request_tokens(client: Any, messages: Sequence[Any], tools: Sequence[Any]) -> int:
    counter = getattr(client, "count_tokens", None)
    if callable(counter):
        try:
            return int(counter(messages=messages, tools=tools))
        except TypeError:
            return int(counter(messages=messages))
    getter = getattr(client, "next_client", None)
    if callable(getter):
        child = getter(no_increment=True)
        return int(child.count_tokens(messages=messages, tools=tools))
    text = json.dumps(
        {"messages": messages, "tools": tools},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return max(1, len(text) // 4)


def context_limit(client: Any) -> int:
    value = getattr(client, "max_tokens", None)
    if value is None:
        value = getattr(client, "_max_tokens", None)
    if value is None:
        getter = getattr(client, "next_client", None)
        if callable(getter):
            child = getter(no_increment=True)
            value = getattr(child, "_max_tokens", None)
    return int(value or 115000)
