"""Shared-file frozen-rubric loading and canonical hash verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FrozenRubric:
    task_id: str
    precomputed_rubric: dict[str, Any]
    sha256: str
    path: Path


def canonical_rubric_bytes(rubric: object) -> bytes:
    return json.dumps(
        rubric, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def load_frozen_rubric(path: str | Path, *, expected_task_id: str) -> FrozenRubric:
    source = Path(path).resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Canonical rubric file must contain a JSON object")
    task_id = str(payload.get("task_id") or "")
    if task_id != expected_task_id:
        raise ValueError(
            f"Rubric task_id mismatch: expected {expected_task_id!r}, got {task_id!r}"
        )
    rubric = payload.get("precomputed_rubric")
    if not isinstance(rubric, dict) or not isinstance(rubric.get("items"), list):
        raise ValueError("precomputed_rubric must be an object with an items list")
    if not rubric["items"]:
        raise ValueError("Frozen rubric must contain at least one criterion")
    digest = hashlib.sha256(canonical_rubric_bytes(rubric)).hexdigest()
    return FrozenRubric(task_id, rubric, digest, source)


def require_matching_embedded_rubric(
    task_data: dict[str, Any], frozen: FrozenRubric
) -> dict[str, Any]:
    embedded = task_data.get("precomputed_rubric")
    if embedded is not None and canonical_rubric_bytes(embedded) != canonical_rubric_bytes(
        frozen.precomputed_rubric
    ):
        raise ValueError("Task data rubric differs from the canonical frozen rubric")
    merged = dict(task_data)
    merged["precomputed_rubric"] = frozen.precomputed_rubric
    return merged
