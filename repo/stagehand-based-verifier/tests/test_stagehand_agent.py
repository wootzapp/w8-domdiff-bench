from __future__ import annotations

from pathlib import Path
from typing import Any

from stagehand_verifier.agent import StagehandVerifier
from stagehand_verifier.loader import load_stagehand_trajectory
from stagehand_verifier.schemas import VerifierConfig
from stagehand_verifier.usage import UsageLedger


class FakeJudge:
    def __init__(self) -> None:
        self.ledger = UsageLedger()
        self.calls: list[tuple[str, str]] = []

    def complete_json(
        self, *, role: str, model: str, system: str, user: str, temperature: float = 0
    ) -> dict[str, Any]:
        self.ledger.add(role, {"prompt_tokens": 10, "completion_tokens": 4})
        self.calls.append((role, user))
        if role.endswith("criterion_action"):
            return {"assessment": "consistent", "reasoning": "attempted", "relevant_steps": [2]}
        if role.endswith("criterion_semantic"):
            return {"status": "supported", "earned_points": 2, "condition_met": True,
                    "explanation": "Terminal ARIA confirms Alpha checked.",
                    "citations": [{"step": 2, "node_identifiers": ["node"]}]}
        if role.endswith("side_effects"):
            return {"has_unintended_side_effect": False, "penalty": 0, "reasoning": "none"}
        if role.endswith("outcome"):
            return {"outcome_success": True, "confidence": 1, "reasoning": "supported",
                    "unsupported_claims": [], "evidence_steps": [2]}
        if "task_validity" in role:
            return {"valid": True, "reasoning": "valid", "blocked_by_environment": False}
        raise AssertionError(role)


def test_end_to_end_uses_llm_only_for_semantic_criterion(stagehand_task: Path) -> None:
    rubric = {"items": [
        {"id": 0, "criterion": "End on settings", "points": 1,
         "deterministic_check": {"final_url_contains": "/settings"}},
        {"id": 1, "criterion": "Alpha is enabled", "points": 2},
    ]}
    override = {"id": "sample-task", "question": "Enable Alpha", "init_url": "about:blank",
                "precomputed_rubric": rubric}
    trajectory, _ = load_stagehand_trajectory(stagehand_task, task_data=override)
    judge = FakeJudge()
    result = StagehandVerifier(judge, config=VerifierConfig(max_evidence_per_criterion=1)).verify(trajectory)
    roles = [role for role, _ in judge.calls]
    assert roles.count("action_rubric.criterion_action") == 1
    assert roles.count("main.criterion_semantic") == 1
    assert result["result"]["rubric"]["total_earned_points"] == 3
    assert result["score"] == 1
    action_prompt = next(prompt for role, prompt in judge.calls if role.endswith("criterion_action"))
    assert action_prompt.count("\"step\":") <= 1
    prompts = "\n".join(prompt for _, prompt in judge.calls)
    assert "[Buffer" not in prompts
    assert "cdp_url" not in prompts
    assert result["llm_usage"]["total"]["calls"] == len(judge.calls)
