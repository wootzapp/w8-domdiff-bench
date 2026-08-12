from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .loader import load_stagehand_trajectory
from .preparation import prepare_stagehand_trajectory
from .result_schema import EVIDENCE_MODE, EVIDENCE_SCHEMA_VERSION
from .schemas import PreflightResult, StagehandTrajectory


@dataclass(frozen=True)
class StagehandAdapter:
    """Public adapter for loading or preparing Stagehand semantic trajectories."""

    evidence_identity: str = EVIDENCE_MODE
    evidence_schema_version: str = EVIDENCE_SCHEMA_VERSION

    def load(
        self, path: str | Path, task_data: dict[str, Any] | None = None
    ) -> tuple[StagehandTrajectory, PreflightResult]:
        return load_stagehand_trajectory(path, task_data=task_data)

    def prepare(self, source: str | Path, destination: str | Path) -> Path:
        return prepare_stagehand_trajectory(source, destination)
