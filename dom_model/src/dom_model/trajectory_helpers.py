"""Read-only bridge to Microsoft's trajectory parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .trajectory import Trajectory


def load_trajectory(task_root: str | Path) -> Trajectory:
    root = Path(task_root).resolve(strict=True)
    trajectory = Trajectory.from_folder(root)
    if trajectory is None:
        raise ValueError(f"Microsoft trajectory parser could not load {root}")
    return trajectory


def action_events(trajectory: Trajectory) -> list[dict[str, Any]]:
    return [dict(event) for event in trajectory.events if event.get("action") is not None]

