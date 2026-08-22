"""Narrow transition compatibility layer for refined text frames.

The downstream rubric workflow still requests a global chronological DOM
transition string for failure and penalty analysis. Refined text frames do not
contain raw snapshots or raw diff objects, so the historical renderer produced
only the frame/action coverage envelope shown here. Keeping that exact envelope
preserves behavior without shipping the unused raw-DOM loader/projector.
"""

from __future__ import annotations

from typing import Any, Iterable


DOMEvidenceFrame = Any


def _unsupported(*args: Any, **kwargs: Any) -> Any:
    del args, kwargs
    raise RuntimeError(
        "Raw/full DOM projection is unavailable in the refined dom_diff_text verifier"
    )


build_dom_retrieval_terms = _unsupported
load_dom_frames = _unsupported
project_frame = _unsupported
project_frame_retrieved = _unsupported


def _frame_transition(frame: Any) -> str:
    ordinal = int(getattr(frame, "action_ordinal", 0))
    action_id = str(getattr(frame, "action_id", "") or "N/A")
    capture = str(getattr(frame, "capture_status", "") or "unknown")
    coverage = str(getattr(frame, "coverage_status", "") or "unknown")
    return (
        f"FRAME {ordinal} action_id={action_id} capture={capture} coverage={coverage}\n"
        "action=\n"
        "before_page=unavailable\n"
        "after_page=unavailable\n"
        "UNFILTERED EXPLICIT CHANGES:\n"
        "counts={}\n\n"
        "AFTER STATE unavailable"
    )


def project_dom_transition_timeline(
    frames: Iterable[Any],
    *,
    context_char_budget: int = 24000,
    frame_char_budget: int = 6000,
) -> str:
    """Render the exact legacy transition envelope for refined text frames."""
    ordered = sorted(
        frames,
        key=lambda frame: (
            int(getattr(frame, "action_ordinal", 0)),
            str(getattr(frame, "action_id", "")),
        ),
    )
    output = (
        "GLOBAL DOM TRANSITION EVIDENCE (chronological, not task/rubric filtered)\n"
        f"frames={len(ordered)}\n"
        "CROSS-FRAME SEMANTIC STATE CHANGES "
        "(N actions -> N+1 states; no task-term filtering):\n"
        "none represented\n"
        "---\n"
    )
    for frame in ordered:
        projected = _frame_transition(frame)[:frame_char_budget]
        output += "\n---\n" + projected
        if len(output) >= context_char_budget:
            break
    return output[:context_char_budget]
