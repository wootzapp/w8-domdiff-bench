"""Input adapter for the isolated DOM-diff-only verifier."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from webeval.rubric_agent.data_point import (
    Action,
    ComputerObservation,
    DataPoint,
    DataPointMetadata,
    Outcome,
    SolverLog,
    SolverStatus,
    Task,
)
from webeval.rubric_agent.dom_diff_evidence import (
    CHROMIUMRL_DIFF_SCHEMA,
    load_dom_diff,
)
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgent
from webeval.trajectory import parse_text_based_event


_STEP_RE = re.compile(r"^step_(\d+)$")


@dataclass(frozen=True)
class DOMDiffTrajectory:
    """Minimal trajectory object containing no screenshot or snapshot state."""

    path: Path
    events: list[dict[str, Any]]
    final_answer: str
    is_aborted: bool = False
    token_usage: dict[str, Any] = field(default_factory=dict)


def _read_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def load_dom_diff_trajectory(path: str | Path) -> DOMDiffTrajectory:
    """Load only actions and final answer from a trajectory folder."""
    trajectory_dir = Path(path).resolve()
    log_candidates = [
        candidate
        for candidate in (
            trajectory_dir / "web_surfer.log",
            trajectory_dir / "websurfer.log",
        )
        if candidate.is_file()
    ]
    if len(log_candidates) != 1:
        raise ValueError(
            f"Expected exactly one web surfer log in {trajectory_dir}, "
            f"found {len(log_candidates)}"
        )
    events: list[dict[str, Any]] = []
    with log_candidates[0].open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed JSON on {log_candidates[0]} line {line_number}: {exc}"
                ) from exc
            if not isinstance(event, dict):
                raise ValueError(
                    f"Log event on line {line_number} must be an object"
                )
            if event.get("action") is None:
                event = parse_text_based_event(event) or event
            events.append(event)

    answer_candidates = sorted(set(trajectory_dir.glob("*_answer.json")))
    if len(answer_candidates) != 1:
        raise ValueError(
            f"Expected exactly one *_answer.json in {trajectory_dir}, "
            f"found {len(answer_candidates)}"
        )
    answer = _read_json_object(answer_candidates[0])
    final_answer = answer.get("final_answer", "")
    if not isinstance(final_answer, str):
        raise ValueError(f"final_answer must be a string: {answer_candidates[0]}")
    token_usage = answer.get("token_usage") or {}
    if not isinstance(token_usage, dict):
        token_usage = {}
    return DOMDiffTrajectory(
        path=trajectory_dir,
        events=events,
        final_answer=final_answer,
        is_aborted=bool(answer.get("is_aborted", False)),
        token_usage=token_usage,
    )


def ordered_action_events(candidate: DOMDiffTrajectory) -> list[dict[str, Any]]:
    actions = [event for event in candidate.events if event.get("action") is not None]
    if not actions:
        raise ValueError(f"Trajectory has no parsed actions: {candidate.path}")
    return actions


def discover_dom_diff_paths(
    candidate_path: str | Path, action_count: int
) -> list[Path]:
    """Require exactly step_001..step_NNN, each with one valid diff."""
    root = Path(candidate_path)
    by_ordinal: dict[int, list[Path]] = {}
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = _STEP_RE.fullmatch(child.name)
        if match is None:
            continue
        ordinal = int(match.group(1))
        # A recorder may emit a trailing capture-only state folder after the
        # last action. It is not evidence in this ablation unless it contains a
        # dom_diff.json. Expected action ordinals are always retained so a
        # missing action diff still fails below.
        if ordinal <= action_count or (child / "dom_diff.json").is_file():
            by_ordinal.setdefault(ordinal, []).append(child)

    duplicates = {
        ordinal: paths for ordinal, paths in by_ordinal.items() if len(paths) != 1
    }
    if duplicates:
        labels = ", ".join(
            f"{ordinal}: {[path.name for path in paths]}"
            for ordinal, paths in sorted(duplicates.items())
        )
        raise ValueError(f"Duplicate DOM diff step ordinals: {labels}")

    expected = list(range(1, action_count + 1))
    actual = sorted(by_ordinal)
    if actual != expected:
        raise ValueError(
            "DOM diff steps must be contiguous and action-aligned: "
            f"expected {expected}, got {actual}"
        )

    paths: list[Path] = []
    for ordinal in expected:
        diff_path = by_ordinal[ordinal][0] / "dom_diff.json"
        if not diff_path.is_file():
            raise ValueError(f"Missing DOM diff for action {ordinal}: {diff_path}")
        load_dom_diff(diff_path)
        paths.append(diff_path.resolve(strict=False))
    return paths


def create_dom_diff_datapoint(
    task_data: dict[str, Any], candidate: DOMDiffTrajectory
) -> DataPoint:
    """Build a DataPoint whose only browser-state path is ``dom_diff_path``."""
    action_events = ordered_action_events(candidate)
    diff_paths = discover_dom_diff_paths(candidate.path, len(action_events))

    metadata: dict[str, Any] = {
        # The inherited pipeline dispatches its text-evidence route as "dom".
        # External artifacts identify this isolated modality as "dom_diff".
        "evidence_mode": "dom",
        "requested_evidence_mode": "dom_diff",
    }
    rubric = task_data.get("precomputed_rubric")
    if rubric is not None:
        metadata["precomputed_rubric"] = rubric

    task = Task(
        task_id=str(task_data.get("id") or candidate.path.name),
        instruction=str(task_data.get("question") or ""),
        environment_config={"init_url": str(task_data.get("init_url") or "")},
        metadata=metadata,
    )

    events: list[Any] = []
    for index, event in enumerate(action_events, start=1):
        arguments = event.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError(f"Action {index} arguments must be an object")
        action_name = str(arguments.get("action") or event.get("action") or "")
        if action_name in {"stop_execution", "stop_and_answer_question"}:
            action_name = "terminate"
        action_args = {key: value for key, value in arguments.items() if key != "action"}
        action_id = str(index)

        events.append(ComputerObservation(url=str(event.get("url") or "")))
        events.append(
            Action(
                id=action_id,
                action_name=action_name,
                content={"action": action_name, "arguments": action_args},
                action_nl_description=str(arguments.get("thoughts") or ""),
            )
        )
        events.append(
            ComputerObservation(
                evidence_mode="dom",
                screenshot_path="",
                dom_evidence_schema_version=CHROMIUMRL_DIFF_SCHEMA,
                dom_action_ordinal=index,
                dom_action_id=action_id,
                dom_before_snapshot_path="",
                dom_after_snapshot_path="",
                dom_diff_path=str(diff_paths[index - 1]),
                dom_before_page_state_path="",
                dom_after_page_state_path="",
                dom_verifier_action_path="",
                dom_capture_status="complete",
                dom_coverage_status="diff_only",
                action_id=action_id,
            )
        )

    return DataPoint(
        task=task,
        solver_log=SolverLog(
            events=events,
            status=(SolverStatus.ABORTED if candidate.is_aborted else SolverStatus.COMPLETE),
            outcome=Outcome(answer=candidate.final_answer),
        ),
        metadata=DataPointMetadata(run_id=candidate.path.name),
    )


def build_dom_diff_input(
    task_data: dict[str, Any],
    candidate: DOMDiffTrajectory,
    *,
    redo_eval: bool = False,
) -> dict[str, Any]:
    """Return the inherited agent input while preserving diff-only identity."""
    datapoint = create_dom_diff_datapoint(task_data, candidate)
    value = MMRubricAgent._extract_input_from_datapoint(
        datapoint, screenshots_dir=None, redo_eval=redo_eval
    )
    value["evidence_mode"] = "dom"
    value["requested_evidence_mode"] = "dom_diff"
    value["screenshots_dir"] = None
    return value
