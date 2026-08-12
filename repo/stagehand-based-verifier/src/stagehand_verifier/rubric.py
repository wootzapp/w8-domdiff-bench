from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Iterable


TEXT_FIELDS = ("rubric", "criterion", "description", "condition")


def normalize_rubric(value: dict[str, Any]) -> dict[str, Any]:
    """Validate and return an unscored rubric without changing its wording."""
    if not isinstance(value, dict):
        raise ValueError("Rubric must be a JSON object")
    items = value.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Rubric.items must be a non-empty list")
    normalized = copy.deepcopy(value)
    seen: set[int] = set()
    for index, item in enumerate(normalized["items"]):
        if not isinstance(item, dict):
            raise ValueError(f"Rubric item {index} must be an object")
        rubric_id = item.get("id", index)
        if not isinstance(rubric_id, int):
            raise ValueError(f"Rubric item {index} id must be an integer")
        if rubric_id in seen:
            raise ValueError(f"Duplicate rubric item id: {rubric_id}")
        seen.add(rubric_id)
        item["id"] = rubric_id
        text = criterion_text(item)
        if not text:
            raise ValueError(f"Rubric item {rubric_id} has no criterion text")
        points = item.get("points", item.get("max_points", 1))
        if not isinstance(points, (int, float)) or points <= 0:
            raise ValueError(f"Rubric item {rubric_id} points must be positive")
        item["points"] = float(points)
        item.pop("score", None)
        item.pop("earned_points", None)
        item.pop("evidence", None)
        item.pop("explanation", None)
        if "depends_on" in item and not isinstance(item["depends_on"], (list, int)):
            raise ValueError(f"Rubric item {rubric_id} depends_on has invalid type")
    return normalized


def criterion_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in TEXT_FIELDS:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "\n".join(parts)


def rubric_items(rubric: dict[str, Any]) -> list[dict[str, Any]]:
    return list(rubric.get("items") or [])


def rubric_hash(rubric: dict[str, Any]) -> str:
    frozen = normalize_rubric(rubric)
    payload = json.dumps(frozen, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def possible_points(items: Iterable[dict[str, Any]], active_ids: set[int] | None = None) -> float:
    return sum(
        float(item["points"])
        for item in items
        if active_ids is None or int(item["id"]) in active_ids
    )

