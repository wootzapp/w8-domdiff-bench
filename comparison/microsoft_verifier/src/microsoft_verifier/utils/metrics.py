"""Run-receipt helpers shared by the standalone Microsoft runner."""

from __future__ import annotations

from typing import Any


def rubric_receipt(*, path: str, sha256: str, rubric: dict[str, Any]) -> dict[str, Any]:
    return {
        "rubric_path": path,
        "rubric_sha256": sha256,
        "criterion_denominator": sum(
            int(item.get("max_points", 0)) for item in rubric.get("items", [])
        ),
    }
