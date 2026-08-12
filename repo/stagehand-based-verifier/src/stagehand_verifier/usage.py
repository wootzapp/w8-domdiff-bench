from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .schemas import UsageRecord


@dataclass
class UsageLedger:
    records: dict[str, UsageRecord] = field(default_factory=lambda: defaultdict(UsageRecord))

    def add(self, role: str, usage: dict[str, Any] | None) -> None:
        record = self.records[role]
        record.calls += 1
        if not usage:
            return
        record.prompt_tokens += int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        record.completion_tokens += int(
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
        details = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
        if isinstance(details, dict):
            record.reasoning_tokens += int(details.get("reasoning_tokens") or 0)

    def to_dict(self) -> dict[str, Any]:
        roles = {role: record.to_dict() for role, record in sorted(self.records.items())}
        return {
            "by_role": roles,
            "total": {
                "calls": sum(record.calls for record in self.records.values()),
                "prompt_tokens": sum(record.prompt_tokens for record in self.records.values()),
                "completion_tokens": sum(
                    record.completion_tokens for record in self.records.values()
                ),
                "reasoning_tokens": sum(record.reasoning_tokens for record in self.records.values()),
                "total_tokens": sum(record.total_tokens for record in self.records.values()),
            },
        }

