"""Run-receipt helpers shared by the standalone screenshot runner."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def rubric_receipt(*, path: str, sha256: str, rubric: dict[str, Any]) -> dict[str, Any]:
    return {
        "rubric_path": os.path.relpath(Path(path).resolve(), Path(__file__).resolve().parents[3]),
        "rubric_sha256": sha256,
        "criterion_denominator": sum(
            int(item.get("max_points", 0)) for item in rubric.get("items", [])
        ),
    }
