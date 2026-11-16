"""Build screenshot data points and normalize screenshot aliases."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from .models import (
    ComputerObservation,
    DataPoint,
    SolverLog,
    Task,
    Trajectory,
)
from ..models import (
    Action,
    DataPointMetadata,
    Outcome,
    SolverStatus,
)


def _screenshot_sort_key(s) -> int:
    """Trailing numeric index from a screenshot filename.

    Handles ``screenshot_1.png``, ``screenshot0.png``,
    ``screenshot_post_3.png`` etc.
    """
    stem = Path(s).stem if not isinstance(s, Path) else s.stem
    match = re.search(r"(\d+)$", stem)
    return int(match.group(1)) if match else 0


def _normalize_screenshots(candidate_path: Path, sorted_screenshots: list) -> list:
    """Ensure screenshots follow ``screenshot_{N}.png`` 1-based naming.

    Creates symlinks when originals use a different convention and returns
    the list of normalized filenames relative to ``candidate_path``.
    """
    normalized: list[str] = []
    for i, screenshot in enumerate(sorted_screenshots):
        canonical_name = f"screenshot_{i + 1}.png"
        canonical_path = candidate_path / canonical_name
        original = Path(screenshot)

        if original.name == canonical_name:
            normalized.append(canonical_name)
            continue

        if canonical_path.exists() or canonical_path.is_symlink():
            normalized.append(canonical_name)
            continue

        try:
            canonical_path.symlink_to(original.name)
        except OSError:
            rel = (
                str(original.relative_to(candidate_path))
                if original.is_absolute()
                else str(original)
            )
            normalized.append(rel)
            continue

        normalized.append(canonical_name)
    return normalized


def normalize_all_screenshot_evidence(candidate: Trajectory) -> list[str]:
    """Return every declared screenshot in chronological, canonical order."""
    sorted_screenshots = sorted(
        candidate.answer.screenshots, key=_screenshot_sort_key
    )
    task_path = candidate.path / "task_data.json"
    if task_path.is_file():
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task = task[0] if isinstance(task, list) else task
        if task.get("evaluation_context"):
            return [Path(path).name for path in sorted_screenshots]
    return _normalize_screenshots(candidate.path, sorted_screenshots)


def create_datapoint(task_data: Dict[str, Any], candidate: Trajectory) -> DataPoint:
    """Convert *task_data* + *candidate* Trajectory into a :class:`DataPoint`.

    Parameters
    ----------
    task_data : dict
        Must contain ``"question"`` at minimum; ``"init_url"`` is
        optional (defaults to empty string).
    candidate : Trajectory
        Loaded screenshot baseline trajectory with ``events`` and ``answer.screenshots``.
    """
    action_events = [evt for evt in candidate.events if evt.get("action")]

    all_screenshot_evidence = normalize_all_screenshot_evidence(candidate)
    context = task_data.get("evaluation_context") or {}
    if not context and len(all_screenshot_evidence) != len(action_events) + 1:
        raise ValueError("Expected exactly N+1 screenshot states for N actions")
    # Step summaries retain one post-action state per real action.
    if context:
        indexed_screenshots = {_screenshot_sort_key(path): path for path in all_screenshot_evidence}
        normalized_screenshots = [indexed_screenshots.get(context["expected_state_ids"][index + 1], "") for index in range(len(action_events))]
    else:
        normalized_screenshots = all_screenshot_evidence[1:]

    # precomputed rubric (optional) — may live on task_data or on disk next
    # to the trajectory.
    precomputed_rubric = task_data.get("precomputed_rubric")
    if precomputed_rubric is None:
        task_data_path = candidate.path / "task_data.json"
        if task_data_path.exists():
            try:
                with open(task_data_path, "r") as f:
                    loaded = json.load(f)
                precomputed_rubric = loaded.get("precomputed_rubric")
            except Exception:
                pass

    task_metadata: Dict[str, Any] = {}
    if precomputed_rubric is not None:
        task_metadata["precomputed_rubric"] = precomputed_rubric

    if task_data.get("evaluation_context") is not None:
        task_metadata["evaluation_context"] = task_data["evaluation_context"]
    task = Task(
        task_id=task_data.get("id", candidate.path.name),
        instruction=task_data.get("question", ""),
        environment_config={"init_url": task_data.get("init_url", "")},
        metadata=task_metadata,
    )

    events: list = []
    for i, evt in enumerate(action_events):
        args = evt.get("arguments") or {}
        action_name = args.get("action", evt.get("action", ""))
        if action_name in ("stop_and_answer_question", "stop_execution"):
            action_name = "terminate"
        action_args = {k: v for k, v in args.items() if k != "action"}
        action_id = str(i + 1)

        events.append(ComputerObservation(url=evt.get("url", "")))

        events.append(
            Action(
                id=action_id,
                action_name=action_name,
                content={"action": action_name, "arguments": action_args},
                action_nl_description=args.get("thoughts", "")
                or f"{args.get('state_description', '')} {args.get('reasoning', '')}".strip(),
            )
        )

        screenshot_path = (
            normalized_screenshots[i] if i < len(normalized_screenshots) else ""
        )
        events.append(
            ComputerObservation(
                screenshot_path=screenshot_path, action_id=action_id
            )
        )

    solver_log = SolverLog(
        events=events,
        status=SolverStatus.COMPLETE,
        outcome=Outcome(answer=candidate.answer.final_answer),
    )

    return DataPoint(
        task=task,
        solver_log=solver_log,
        metadata=DataPointMetadata(run_id=candidate.path.name),
    )
