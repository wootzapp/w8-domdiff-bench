"""Minimal screenshot-free trajectory loading for refined DOM text evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def parse_text_based_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Parse legacy thought/action message events without browser dependencies."""
    message = str(event.get("message") or "")
    if "Thought #" not in message or "Action #" not in message:
        return None
    thought_match = re.search(
        r"Thought #\d+:\s*(.+?)(?=\nAction #)", message, re.DOTALL
    )
    action_match = re.search(r"with arguments\s+(\{.+\})", message, re.DOTALL)
    if action_match is None:
        return None
    try:
        arguments = json.loads(action_match.group(1))
    except json.JSONDecodeError:
        return None
    arguments["thoughts"] = thought_match.group(1).strip() if thought_match else ""
    return {
        "action": arguments.get("action", "unknown"),
        "arguments": arguments,
    }


@dataclass(frozen=True)
class DOMDiffTrajectory:
    path: Path
    events: list[dict[str, Any]]
    final_answer: str
    is_aborted: bool = False
    token_usage: dict[str, Any] = field(default_factory=dict)


def load_dom_diff_trajectory(path: str | Path) -> DOMDiffTrajectory:
    trajectory_dir = Path(path).resolve()
    logs = [
        candidate
        for candidate in (
            trajectory_dir / "web_surfer.log",
            trajectory_dir / "websurfer.log",
        )
        if candidate.is_file()
    ]
    if len(logs) != 1:
        raise ValueError(f"Expected exactly one web surfer log, found {len(logs)}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        logs[0].read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON on line {line_number}: {exc}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"Log event on line {line_number} must be an object")
        if event.get("action") is None:
            event = parse_text_based_event(event) or event
        events.append(event)
    answers = sorted(set(trajectory_dir.glob("*_answer.json")))
    if len(answers) != 1:
        raise ValueError(f"Expected exactly one *_answer.json, found {len(answers)}")
    answer = json.loads(answers[0].read_text(encoding="utf-8"))
    if not isinstance(answer, dict):
        raise ValueError(f"Final answer must be an object: {answers[0]}")
    final_answer = answer.get("final_answer", "")
    if not isinstance(final_answer, str):
        raise ValueError("final_answer must be a string")
    token_usage = answer.get("token_usage") or {}
    return DOMDiffTrajectory(
        path=trajectory_dir,
        events=events,
        final_answer=final_answer,
        is_aborted=bool(answer.get("is_aborted", False)),
        token_usage=token_usage if isinstance(token_usage, dict) else {},
    )


def ordered_action_events(candidate: DOMDiffTrajectory) -> list[dict[str, Any]]:
    actions = [event for event in candidate.events if event.get("action") is not None]
    if not actions:
        raise ValueError(f"Trajectory has no parsed actions: {candidate.path}")
    return actions
