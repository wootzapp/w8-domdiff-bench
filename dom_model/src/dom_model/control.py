"""Package-local frozen-rubric and JSON controls for the DOM-model runner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CANONICAL_JUDGE_MODEL = "gpt-5.2"
CANONICAL_ACTION_MODEL = "o4-mini"


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_one_task(path: str | Path) -> dict[str, Any]:
    payload = load_json(path)
    rows = payload if isinstance(payload, list) else [payload]
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError(f"Expected exactly one task object in {path}")
    return dict(rows[0])


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_generation_metrics(path: str | Path, frozen: Any) -> dict[str, Any]:
    value = load_json(Path(path).resolve(strict=True))
    if not isinstance(value, dict):
        raise ValueError("Rubric generation metrics must be an object")
    expected = {
        "task_id": frozen.task_id,
        "frozen_rubric_sha256": frozen.sha256,
        "criterion_count": len(frozen.rubric["items"]),
        "criterion_denominator": frozen.denominator,
        "criteria": [item["criterion"] for item in frozen.rubric["items"]],
        "maximum_points": [float(item["max_points"]) for item in frozen.rubric["items"]],
    }
    for key, wanted in expected.items():
        actual = value.get(key)
        if key == "criterion_denominator":
            actual = float(actual)
        if key == "maximum_points" and isinstance(actual, list):
            actual = [float(point) for point in actual]
        if actual != wanted:
            raise ValueError(f"Generation metrics drift for {key}: {actual!r} != {wanted!r}")
    if int(value.get("rubric_generation_calls", 0)) <= 0 and value.get("origin") != "validated_import":
        raise ValueError("Phase A receipt has no generation calls or validated import origin")
    return value


def write_json(path: str | Path, value: object) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return destination
