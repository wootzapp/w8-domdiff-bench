from __future__ import annotations

from collections.abc import Mapping, Sequence

from .schemas import ActionRecord, SemanticState, TransitionFrame
from .semantic_diff import compare_states


def align_actions_to_states(
    actions: Sequence[ActionRecord],
    states: Mapping[int, SemanticState],
    initial_state: SemanticState,
) -> tuple[TransitionFrame, ...]:
    """Create one unambiguous before/after frame for every ordered action."""
    if not actions:
        raise ValueError("Cannot align an empty action sequence")
    expected = list(range(1, len(actions) + 1))
    actual = [action.ordinal for action in actions]
    if actual != expected:
        raise ValueError(f"Action ordinals must be contiguous: expected {expected}, got {actual}")
    missing = [ordinal for ordinal in expected if ordinal not in states]
    if missing:
        raise ValueError(f"Actions lack aligned after states: {missing}")
    frames: list[TransitionFrame] = []
    before = initial_state
    for action in actions:
        after = states[action.ordinal]
        frames.append(TransitionFrame(action, before, after, compare_states(before, after)))
        before = after
    return tuple(frames)

