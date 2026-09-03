"""Shared offline controls with no DOM-diff runtime dependencies."""

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
    # MMRubricAgent's evidence-analysis gate is separate from the reported
    # Microsoft keypoint threshold. Microsoft's screenshot runner leaves this
    # gate disabled, so the DOM runner must do the same.
    "min_relevance_threshold": 0,
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
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_one_task(path: str | Path) -> dict[str, Any]:
    payload = load_json(path)
    rows = payload if isinstance(payload, list) else [payload]
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError(f"Expected exactly one task object in {path}")
    return dict(rows[0])


def task_id(task: dict[str, Any]) -> str:
    return str(task.get("task_id") or task.get("id") or "")


def task_instruction(task: dict[str, Any]) -> str:
    return str(task.get("confirmed_task") or task.get("question") or "")


def task_init_url(task: dict[str, Any]) -> str:
    return str(task.get("website") or task.get("init_url") or "")


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_rubric(rubric: object) -> float:
    if not isinstance(rubric, dict) or not isinstance(rubric.get("items"), list) or not rubric["items"]:
        raise ValueError("Frozen rubric must contain a non-empty items list")
    seen: set[str] = set()
    denominator = 0.0
    for index, item in enumerate(rubric["items"]):
        if not isinstance(item, dict):
            raise ValueError(f"Rubric item {index} must be an object")
        for field in ("criterion", "description", "max_points", "justification", "earned_points"):
            if field not in item:
                raise ValueError(f"Rubric item {index} is missing {field}")
        criterion = item["criterion"]
        if not isinstance(criterion, str) or not criterion.strip() or criterion in seen:
            raise ValueError(f"Rubric item {index} criterion is empty or duplicated")
        seen.add(criterion)
        if not isinstance(item["description"], str) or not item["description"].strip():
            raise ValueError(f"Rubric item {index} has an empty description")
        points = item["max_points"]
        if isinstance(points, bool) or not isinstance(points, (int, float)) or not math.isfinite(float(points)) or float(points) <= 0:
            raise ValueError(f"Rubric item {index} max_points must be positive and finite")
        denominator += float(points)
        for scored in ("justification", "earned_points", "post_image_earned_points", "post_evidence_earned_points"):
            if item.get(scored) not in (None, ""):
                raise ValueError(f"Frozen rubric item {index} is already scored: {scored}")
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("Frozen rubric denominator must be positive and finite")
    return denominator


def load_canonical_rubric(path: str | Path, *, expected_task_id: str | None = None) -> CanonicalRubric:
    source = Path(path).resolve(strict=True)
    payload = load_json(source)
    if not isinstance(payload, dict):
        raise ValueError("Canonical rubric file must be an object")
    rubric_task = str(payload.get("task_id") or "")
    if not rubric_task:
        raise ValueError("Canonical rubric file is missing task_id")
    if expected_task_id is not None and rubric_task != expected_task_id:
        raise ValueError(f"Rubric task_id mismatch: expected {expected_task_id!r}, got {rubric_task!r}")
    rubric = payload.get("precomputed_rubric")
    denominator = validate_rubric(rubric)
    return CanonicalRubric(
        task_id=rubric_task,
        rubric=rubric,
        sha256=canonical_sha256(rubric),
        denominator=denominator,
        path=source,
    )


def validate_generation_metrics(path: str | Path, frozen: CanonicalRubric) -> dict[str, Any]:
    source = Path(path).resolve(strict=True)
    value = load_json(source)
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
    for key, expected_value in expected.items():
        actual = value.get(key)
        if key in {"criterion_denominator"}:
            actual = float(actual)
        if key == "maximum_points" and isinstance(actual, list):
            actual = [float(point) for point in actual]
        if actual != expected_value:
            raise ValueError(f"Rubric generation metrics drift for {key}: {actual!r} != {expected_value!r}")
    if int(value.get("rubric_generation_calls", 0)) <= 0 and value.get("origin") != "validated_import":
        raise ValueError("Phase A receipt has neither generation calls nor validated_import origin")
    return value


def validate_endpoint_configs(path: str | Path) -> dict[str, Any]:
    root = Path(path).resolve(strict=True)
    files = sorted(root.glob("*.json")) if root.is_dir() else [root]
    if not files:
        raise ValueError(f"No endpoint JSON files found under {root}")
    models: set[str] = set()
    receipts: list[dict[str, str]] = []
    for source in files:
        payload = load_json(source)
        if not isinstance(payload, dict):
            raise ValueError(f"Endpoint config must be an object: {source}")
        if str(payload.get("CHAT_COMPLETION_PROVIDER") or "").casefold() != "openai":
            raise ValueError(f"Only OpenAI endpoint configs are allowed: {source}")
        keys = " ".join(_walk_keys(payload)).casefold()
        if any(fragment in keys for fragment in ("api_key", "token", "secret", "password")):
            raise ValueError(f"Endpoint config appears to contain credentials: {source}")
        kwargs = payload.get("CHAT_COMPLETION_KWARGS_JSON")
        if not isinstance(kwargs, dict) or not isinstance(kwargs.get("model"), str):
            raise ValueError(f"Endpoint config has no model: {source}")
        models.add(kwargs["model"])
        receipts.append({"path": str(source), "model": kwargs["model"]})
    required = {CANONICAL_JUDGE_MODEL, CANONICAL_ACTION_MODEL}
    if models != required:
        raise ValueError(f"Endpoint models must be exactly {sorted(required)}, got {sorted(models)}")
    return {"models": sorted(models), "files": receipts}


def _walk_keys(value: object) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def ensure_under(path: str | Path, root: str | Path, *, label: str) -> Path:
    target = Path(path).resolve()
    boundary = Path(root).resolve(strict=True)
    try:
        target.relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"{label} must be under isolated root {boundary}: {target}") from exc
    return target


def load_env_file(path: str | Path) -> None:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Environment file does not exist: {source}")
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ValueError(f"Malformed environment entry at {source}:{line_number}")
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value


def require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is not set or is empty")


def write_json(path: str | Path, value: object) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return destination


def sum_usage(*rows: dict[str, Any]) -> dict[str, int]:
    keys = ("prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens")
    return {key: sum(int(row.get(key, 0) or 0) for row in rows) for key in keys}


def sum_call_metrics(*rows: dict[str, Any]) -> dict[str, int]:
    logical = sum(int(row.get("logical_calls", 0) or 0) for row in rows)
    attempts = sum(int(row.get("api_attempts", 0) or 0) for row in rows)
    return {"logical_calls": logical, "api_attempts": attempts, "retries": max(0, attempts - logical)}
