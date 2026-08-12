from __future__ import annotations

from typing import Any


FIELDS = ("calls", "prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens")


def usage_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Return per-task usage when a runner reuses one client across tasks."""
    before_roles = before.get("by_role") if isinstance(before.get("by_role"), dict) else {}
    after_roles = after.get("by_role") if isinstance(after.get("by_role"), dict) else {}
    roles: dict[str, dict[str, int]] = {}
    for role in sorted(set(before_roles) | set(after_roles)):
        previous = before_roles.get(role) or {}
        current = after_roles.get(role) or {}
        delta = {field: int(current.get(field, 0)) - int(previous.get(field, 0)) for field in FIELDS}
        if any(delta.values()):
            roles[role] = delta
    return {
        "by_role": roles,
        "total": {field: sum(record[field] for record in roles.values()) for field in FIELDS},
    }
