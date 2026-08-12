from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agent import StagehandVerifier
from .loader import load_stagehand_trajectory
from .result_schema import cache_identity
from .rubric import normalize_rubric
from .schemas import PreflightResult, StagehandTrajectory, VerifierConfig


@dataclass(frozen=True)
class PreparedRun:
    trajectory: StagehandTrajectory
    preflight: PreflightResult


def discover_tasks(path: str | Path) -> list[Path]:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    if (root / "task.json").is_file() or (root / "task_data.json").is_file():
        return [root]
    tasks = [
        child
        for child in sorted(root.iterdir())
        if child.is_dir()
        and ((child / "task.json").is_file() or (child / "task_data.json").is_file())
    ]
    if not tasks:
        raise ValueError(f"No Stagehand task directories found under {root}")
    return tasks


def load_task_data(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("tasks"), list):
        rows = payload["tasks"]
    elif isinstance(payload, dict):
        rows = [payload]
    else:
        raise ValueError("--task-data must contain an object, list, or {tasks:[...]} object")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Every task-data row must be an object")
        task_id = str(row.get("id") or row.get("task_id") or "")
        if not task_id:
            raise ValueError("Every task-data row requires id or task_id")
        if task_id in result:
            raise ValueError(f"Duplicate task-data id: {task_id}")
        if row.get("precomputed_rubric") is not None:
            normalize_rubric(row["precomputed_rubric"])
        result[task_id] = row
    return result


def preflight_tasks(
    input_path: str | Path,
    task_data_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[PreparedRun]:
    overrides = task_data_by_id or {}
    prepared: list[PreparedRun] = []
    for root in discover_tasks(input_path):
        raw_task_id = root.name
        if (root / "task.json").is_file():
            raw = json.loads((root / "task.json").read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw_task_id = str(raw.get("task_id") or raw_task_id)
        elif (root / "task_data.json").is_file():
            raw = json.loads((root / "task_data.json").read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw_task_id = str(raw.get("id") or raw.get("task_id") or raw_task_id)
        override = overrides.get(raw_task_id)
        if overrides and override is None:
            raise ValueError(f"No --task-data row found for discovered task {raw_task_id}")
        trajectory, preflight = load_stagehand_trajectory(root, task_data=override)
        if trajectory.task.task_id != raw_task_id:
            raise ValueError(
                f"Task identifier mismatch: directory metadata={raw_task_id!r}, "
                f"task data={trajectory.task.task_id!r}"
            )
        prepared.append(PreparedRun(trajectory, preflight))
    unused = set(overrides) - {item.trajectory.task.task_id for item in prepared}
    if unused:
        raise ValueError(f"Task-data rows did not match discovered tasks: {sorted(unused)}")
    return prepared


def result_path(
    trajectory: StagehandTrajectory,
    rubric: dict[str, Any],
    config: VerifierConfig,
    output_root: Path | None,
) -> Path:
    identity = cache_identity(trajectory, rubric, config)
    filename = (
        f"mmrubric_{config.rubric_threshold:g}-{config.max_evidence_per_criterion}"
        f"-stagehand-{identity}.json"
    )
    if output_root is None:
        return trajectory.path / "scores" / filename
    return output_root / trajectory.task.task_id / "scores" / filename


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def run_prepared(
    prepared: list[PreparedRun],
    verifier: StagehandVerifier,
    *,
    output_root: Path | None,
    report_path: Path,
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as report_handle:
        for item in prepared:
            rubric = item.trajectory.task.precomputed_rubric
            cached_path = None
            if rubric is not None:
                cached_path = result_path(item.trajectory, rubric, verifier.config, output_root)
            if cached_path and cached_path.is_file() and not verifier.config.redo_eval:
                result = json.loads(cached_path.read_text(encoding="utf-8"))
                status = "cached"
                path = cached_path
            else:
                result = verifier.verify(item.trajectory)
                final_rubric = {
                    "items": [
                        {
                            key: value
                            for key, value in rubric_item.items()
                            if key
                            not in {
                                "evaluation_method",
                                "status",
                                "condition_met",
                                "earned_points",
                                "explanation",
                                "judge_citations",
                                "evidence_links",
                                "evidence_relevance",
                                "action_only_analysis",
                                "majority_vote",
                                "applicable",
                            }
                        }
                        for rubric_item in result["result"]["rubric"]["items"]
                    ]
                }
                path = result_path(item.trajectory, final_rubric, verifier.config, output_root)
                write_json_atomic(path, result)
                status = "evaluated"
            report = {
                "task_id": item.trajectory.task.task_id,
                "status": status,
                "score": result.get("score"),
                "result_path": str(path),
                "cache_identity": result.get("cache_identity"),
                "preflight": item.preflight.to_dict(),
                "llm_usage": result.get("llm_usage"),
            }
            report_handle.write(json.dumps(report, ensure_ascii=False) + "\n")
            report_handle.flush()
            reports.append(report)
    return reports

