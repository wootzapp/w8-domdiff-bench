from __future__ import annotations

from typing import Any


STAGEHAND_ACTION_DEFINITIONS: dict[str, set[str]] = {
    "goto": {"url"},
    "act": {"action"},
    "keys": {"method", "value"},
    "fillForm": {"fields"},
    "scroll": {"direction"},
    "navback": set(),
    "wait": {"timeMs"},
    "extract": {"instruction"},
    "ariaTree": set(),
    "screenshot": set(),
    "think": set(),
}


def sanitize_action_arguments(action: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ValueError(f"Arguments for {action!r} must be a JSON object")
    # Reasoning is not action evidence and must not enter judge context.
    return {
        key: value
        for key, value in arguments.items()
        if key not in {"reasoning", "thoughts", "chain_of_thought"}
    }


def validate_action(action: str, arguments: dict[str, Any]) -> list[dict[str, str]]:
    if action not in STAGEHAND_ACTION_DEFINITIONS:
        return [
            {
                "error_code": "6.2",
                "error_category": "Tool Interaction",
                "error_type": "Hallucinated action",
                "message": f"Unknown Stagehand action {action!r}",
            }
        ]
    missing = sorted(STAGEHAND_ACTION_DEFINITIONS[action] - arguments.keys())
    if not missing:
        return []
    return [
        {
            "error_code": "6.1",
            "error_category": "Tool Interaction",
            "error_type": "Invalid invocation",
            "message": f"Action {action!r} is missing required arguments: {missing}",
        }
    ]

