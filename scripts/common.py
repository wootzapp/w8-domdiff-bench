"""Shared benchmark-control helpers with no verifier-runtime dependencies."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CANONICAL_JUDGE_MODEL = "gpt-5.2"
CANONICAL_ACTION_MODEL = "o4-mini"
CANONICAL_SETTINGS = {
    "rubric_threshold": 0.8,
    "max_evidence_items_per_criterion": 5,
    "mm_keypoint_score_threshold": 3,
    "majority_vote_instances": 1,
    "success_criterion": "outcome",
}


@dataclass(frozen=True)
class CanonicalRubric:
    task_id: str
    rubric: dict[str, Any]
    sha256: str
    denominator: float
    path: Path


def load_json(path: str | Path) -> Any:
    source = Path(path)
    return json.loads(source.read_text(encoding="utf-8"))


def load_one_task(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    payload = load_json(source)
    rows = payload if isinstance(payload, list) else [payload]
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError(f"Expected exactly one task object in {source}")
    return dict(rows[0])


def task_id(task: dict[str, Any]) -> str:
    return str(task.get("task_id") or task.get("id") or "")


def task_instruction(task: dict[str, Any]) -> str:
    return str(task.get("confirmed_task") or task.get("question") or "")


def task_init_url(task: dict[str, Any]) -> str:
    return str(task.get("website") or task.get("init_url") or "")


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_rubric(rubric: object) -> float:
    if not isinstance(rubric, dict):
        raise ValueError("Frozen rubric must be a JSON object")
    items = rubric.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Frozen rubric must contain a non-empty items list")
    criteria: set[str] = set()
    denominator = 0.0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Rubric item {index} must be an object")
        for field in (
            "criterion",
            "description",
            "max_points",
            "justification",
            "earned_points",
        ):
            if field not in item:
                raise ValueError(f"Rubric item {index} is missing {field}")
        criterion = item["criterion"]
        if not isinstance(criterion, str) or not criterion.strip():
            raise ValueError(f"Rubric item {index} has an empty criterion")
        if criterion in criteria:
            raise ValueError(f"Duplicate rubric criterion: {criterion}")
        criteria.add(criterion)
        description = item["description"]
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"Rubric item {index} has an empty description")
        points = item["max_points"]
        if (
            not isinstance(points, (int, float))
            or isinstance(points, bool)
            or not math.isfinite(float(points))
            or float(points) <= 0
        ):
            raise ValueError(f"Rubric item {index} max_points must be positive")
        denominator += float(points)
        for scored_field in (
            "justification",
            "earned_points",
            "post_image_earned_points",
            "post_evidence_earned_points",
        ):
            if item.get(scored_field) not in (None, ""):
                raise ValueError(f"Frozen rubric item {index} is already scored: {scored_field}")
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("Frozen rubric denominator must be positive and finite")
    return denominator


def load_canonical_rubric(
    path: str | Path, *, expected_task_id: str | None = None
) -> CanonicalRubric:
    source = Path(path).resolve(strict=True)
    payload = load_json(source)
    if not isinstance(payload, dict):
        raise ValueError("Canonical rubric file must contain a JSON object")
    rubric_task_id = str(payload.get("task_id") or "")
    if not rubric_task_id:
        raise ValueError("Canonical rubric file is missing task_id")
    if expected_task_id is not None and rubric_task_id != expected_task_id:
        raise ValueError(
            f"Rubric task_id mismatch: expected {expected_task_id!r}, got {rubric_task_id!r}"
        )
    rubric = payload.get("precomputed_rubric")
    denominator = validate_rubric(rubric)
    return CanonicalRubric(
        task_id=rubric_task_id,
        rubric=rubric,
        sha256=canonical_sha256(rubric),
        denominator=denominator,
        path=source,
    )


def load_env_file(path: str | Path) -> None:
    """Load simple KEY=VALUE entries without logging their values."""

    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Environment file does not exist: {source}")
    for line_number, raw_line in enumerate(
        source.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ValueError(f"Malformed environment entry at {source}:{line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is not set or is empty")


def validate_endpoint_configs(path: str | Path) -> dict[str, Any]:
    root = Path(path).resolve(strict=True)
    files = sorted(root.glob("*.json")) if root.is_dir() else [root]
    if not files:
        raise ValueError(f"No endpoint JSON files found under {root}")
    models: set[str] = set()
    receipts: list[dict[str, str]] = []
    forbidden_key_fragments = ("api_key", "token", "secret", "password")
    for source in files:
        payload = load_json(source)
        if not isinstance(payload, dict):
            raise ValueError(f"Endpoint config must be an object: {source}")
        provider = str(payload.get("CHAT_COMPLETION_PROVIDER") or "").lower()
        if provider != "openai":
            raise ValueError(f"Only OpenAI endpoint configs are allowed: {source}")
        encoded_keys = " ".join(_walk_keys(payload)).casefold()
        if any(fragment in encoded_keys for fragment in forbidden_key_fragments):
            raise ValueError(f"Endpoint config appears to contain credentials: {source}")
        kwargs = payload.get("CHAT_COMPLETION_KWARGS_JSON")
        if not isinstance(kwargs, dict) or not isinstance(kwargs.get("model"), str):
            raise ValueError(f"Endpoint config has no model: {source}")
        model = kwargs["model"]
        models.add(model)
        receipts.append({"path": str(source), "model": model})
    required = {CANONICAL_JUDGE_MODEL, CANONICAL_ACTION_MODEL}
    if models != required:
        raise ValueError(
            f"Endpoint models must be exactly {sorted(required)}, got {sorted(models)}"
        )
    return {"models": sorted(models), "files": receipts}


def _walk_keys(value: object) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def sum_usage(*usage_rows: dict[str, Any]) -> dict[str, int]:
    keys = ("prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens")
    return {key: sum(int(row.get(key, 0) or 0) for row in usage_rows) for key in keys}


def sum_call_metrics(*rows: dict[str, Any]) -> dict[str, int]:
    logical = sum(int(row.get("logical_calls", 0) or 0) for row in rows)
    attempts = sum(int(row.get("api_attempts", 0) or 0) for row in rows)
    return {
        "logical_calls": logical,
        "api_attempts": attempts,
        "retries": attempts - logical,
    }


def write_json(path: str | Path, value: object) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return destination
