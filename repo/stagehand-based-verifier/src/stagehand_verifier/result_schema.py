from __future__ import annotations

import hashlib
import json
from typing import Any

from .prompts import PROMPT_VERSION
from .rubric import rubric_hash
from .schemas import StagehandTrajectory, VerifierConfig


EVIDENCE_MODE = "stagehand_semantic"
EVIDENCE_SCHEMA_VERSION = "stagehand-semantic-trajectory/v2"
VERIFIER_SCHEMA_VERSION = "stagehand-mmrubric-result/v1"
ADAPTER_VERSION = "stagehand-adapter/v2"
UPSTREAM_COMMIT = "9f14b6e34094fe469a54a821e81e013a0739520d"


def cache_identity(
    trajectory: StagehandTrajectory,
    rubric: dict[str, Any],
    config: VerifierConfig,
) -> str:
    payload = {
        "task_id": trajectory.task.task_id,
        "evidence_mode": EVIDENCE_MODE,
        "evidence_schema": EVIDENCE_SCHEMA_VERSION,
        "adapter": ADAPTER_VERSION,
        "upstream_behavioral_reference": UPSTREAM_COMMIT,
        "prompt_version": PROMPT_VERSION,
        "rubric_sha256": rubric_hash(rubric),
        "config": config.to_dict(),
        "manifest": {
            "action_count": len(trajectory.actions),
            "state_count": trajectory.manifest.get("state_count"),
            "terminal_state_ordinal": trajectory.manifest.get("terminal_state_ordinal"),
        },
    }
    frozen = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(frozen.encode("utf-8")).hexdigest()[:16]

