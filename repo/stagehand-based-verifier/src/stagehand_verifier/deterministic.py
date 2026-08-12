from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from .evidence_projection import evidence_link
from .schemas import DeterministicDecision, StagehandTrajectory


SUPPORTED_CHECKS = {
    "final_url_equals",
    "final_url_contains",
    "final_domain_equals",
    "terminal_contains_all",
    "terminal_contains_any",
    "terminal_not_contains",
    "action_present",
    "all_tools_ok",
}


def _terminal_text(trajectory: StagehandTrajectory) -> str:
    state = trajectory.terminal_state
    return " ".join(
        [state.page.url, state.page.title, state.page.body_text_preview]
        + [node.searchable_text() for node in state.nodes]
    ).casefold()


def _values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError("Deterministic check value must be a string or list of strings")


def evaluate_deterministic(
    criterion: dict[str, Any], trajectory: StagehandTrajectory
) -> DeterministicDecision:
    """Evaluate only explicit, auditable checks; semantic criteria stay with the LLM."""
    spec = criterion.get("deterministic_check")
    if spec is None:
        return DeterministicDecision(False)
    if not isinstance(spec, dict) or len(spec) != 1:
        raise ValueError("deterministic_check must contain exactly one supported operator")
    operator, expected = next(iter(spec.items()))
    if operator not in SUPPORTED_CHECKS:
        raise ValueError(f"Unsupported deterministic operator: {operator}")

    terminal = trajectory.terminal_state
    text = _terminal_text(trajectory)
    observed: Any
    passed: bool
    links = ()
    if operator == "final_url_equals":
        observed = terminal.page.url
        passed = observed == str(expected)
    elif operator == "final_url_contains":
        observed = terminal.page.url
        passed = str(expected).casefold() in observed.casefold()
    elif operator == "final_domain_equals":
        observed = urlparse(terminal.page.url).netloc.casefold()
        passed = observed == str(expected).casefold()
    elif operator == "terminal_contains_all":
        values = [value.casefold() for value in _values(expected)]
        observed = values
        passed = all(value in text for value in values)
    elif operator == "terminal_contains_any":
        values = [value.casefold() for value in _values(expected)]
        observed = values
        passed = any(value in text for value in values)
    elif operator == "terminal_not_contains":
        values = [value.casefold() for value in _values(expected)]
        observed = values
        passed = all(value not in text for value in values)
    elif operator == "action_present":
        observed = [action.name for action in trajectory.actions]
        passed = str(expected) in observed
        matched = [frame for frame in trajectory.frames if frame.action.name == str(expected)]
        links = tuple(evidence_link(frame, ()) for frame in matched[:3])
    else:
        observed = [frame.action.tool_result.get("ok") for frame in trajectory.frames]
        passed = all(value is not False for value in observed)

    max_points = float(criterion.get("points", 1))
    return DeterministicDecision(
        applicable=True,
        status="supported" if passed else "contradicted",
        earned_points=max_points if passed else 0.0,
        explanation=(
            f"Deterministic check {operator} {'passed' if passed else 'failed'}; "
            f"observed={json.dumps(observed, ensure_ascii=False)}."
        ),
        links=links,
    )

