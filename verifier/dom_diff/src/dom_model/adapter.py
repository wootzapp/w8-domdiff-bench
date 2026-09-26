"""Build package-local data points for DOM-model verification."""

from __future__ import annotations

from typing import Any

from .models import (
    Action,
    ComputerObservation,
    DataPoint,
    DataPointMetadata,
    Outcome,
    SolverLog,
    SolverStatus,
    Task,
)
from .trajectory import Trajectory


def create_datapoint(task_data: dict[str, Any], trajectory: Trajectory) -> DataPoint:
    events: list[Any] = []
    action_events = [event for event in trajectory.events if event.get("action") is not None]
    for ordinal, event in enumerate(action_events, start=1):
        arguments = event.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError(f"Action {ordinal} arguments must be an object")
        action_name = str(arguments.get("action") or event.get("action") or "")
        if action_name in {"stop_and_answer_question", "stop_execution"}:
            action_name = "terminate"
        action_args = {key: value for key, value in arguments.items() if key != "action"}
        action_id = str(ordinal)
        events.append(ComputerObservation(url=str(event.get("url") or "")))
        events.append(
            Action(
                id=action_id,
                action_name=action_name,
                content={
                    "action": action_name,
                    "arguments": action_args,
                    "other_state": event.get("other_state") or {},
                },
                action_nl_description=str(arguments.get("thoughts") or ""),
            )
        )
        events.append(ComputerObservation(action_id=action_id, evidence_path=""))

    rubric = task_data.get("precomputed_rubric")
    metadata = {"precomputed_rubric": rubric} if rubric is not None else {}
    task = Task(
        task_id=str(task_data.get("id") or task_data.get("task_id") or trajectory.path.name),
        instruction=str(task_data.get("question") or task_data.get("confirmed_task") or ""),
        environment_config={
            "init_url": str(task_data.get("init_url") or task_data.get("website") or "")
        },
        metadata=metadata,
    )
    solver_log = SolverLog(
        events=events,
        status=SolverStatus.ABORTED if trajectory.answer.is_aborted else SolverStatus.COMPLETE,
        outcome=Outcome(answer=trajectory.answer.final_answer),
    )
    return DataPoint(
        task=task,
        solver_log=solver_log,
        metadata=DataPointMetadata(run_id=trajectory.path.name),
    )

