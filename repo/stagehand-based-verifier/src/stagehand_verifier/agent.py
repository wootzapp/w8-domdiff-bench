from __future__ import annotations

import copy
import json
import statistics
from dataclasses import asdict
from typing import Any

from .deterministic import evaluate_deterministic
from .failure_classification import normalize_failure
from .evidence_projection import (
    global_timeline,
    select_evidence,
    selected_links,
    terminal_projection,
)
from .llm import JsonJudge
from .prompts import (
    PROMPT_VERSION,
    action_analysis_prompt,
    criterion_evidence_prompt,
    dependency_prompt,
    failure_prompt,
    outcome_prompt,
    rubric_generation_prompt,
    side_effect_prompt,
    task_validity_prompt,
)
from .result_schema import (
    ADAPTER_VERSION,
    EVIDENCE_MODE,
    EVIDENCE_SCHEMA_VERSION,
    UPSTREAM_COMMIT,
    VERIFIER_SCHEMA_VERSION,
    cache_identity,
)
from .rubric import normalize_rubric, possible_points, rubric_hash, rubric_items
from .schemas import StagehandTrajectory, VerifierConfig
from .usage import UsageLedger
from .usage_delta import usage_delta


VALID_STATUSES = {"supported", "contradicted", "partial", "unknown"}


def _actions(trajectory: StagehandTrajectory) -> list[dict[str, Any]]:
    return [
        {
            "step": action.ordinal,
            "action_id": action.action_id,
            "name": action.name,
            "arguments": action.arguments,
            "url_after_action": action.url,
            "tool_ok": action.tool_result.get("ok"),
            "tool_error": action.tool_result.get("error"),
        }
        for action in trajectory.actions
    ]


def _bounded_points(value: Any, maximum: float) -> float:
    try:
        points = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(maximum, points))


def _condition_met(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None

def _strict_bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


class StagehandVerifier:
    """Standalone Universal-Verifier-style scorer for Stagehand semantic evidence."""

    def __init__(
        self,
        judge: JsonJudge,
        *,
        config: VerifierConfig | None = None,
        usage: UsageLedger | None = None,
    ) -> None:
        self.judge = judge
        self.config = config or VerifierConfig()
        self.usage = usage or getattr(judge, "ledger", UsageLedger())

    def _call(
        self,
        role: str,
        model: str,
        prompt: tuple[str, str],
    ) -> dict[str, Any]:
        return self.judge.complete_json(
            role=role,
            model=model,
            system=prompt[0],
            user=prompt[1],
        )

    def _rubric(self, trajectory: StagehandTrajectory) -> tuple[dict[str, Any], str]:
        if trajectory.task.precomputed_rubric is not None:
            return normalize_rubric(trajectory.task.precomputed_rubric), "frozen"
        generated = self._call(
            "main.rubric_generation",
            self.config.judge_model,
            rubric_generation_prompt(trajectory.task.instruction),
        )
        rubric = normalize_rubric(generated)
        dependent = self._call(
            "main.rubric_dependencies",
            self.config.judge_model,
            dependency_prompt(trajectory.task.instruction, rubric),
        )
        return normalize_rubric(dependent), "generated"

    def _semantic_consensus(
        self,
        trajectory: StagehandTrajectory,
        item: dict[str, Any],
        baseline: dict[str, Any],
        projections: list[str],
    ) -> dict[str, Any]:
        responses: list[dict[str, Any]] = []
        count = max(1, self.config.majority_vote_instances)
        for _ in range(count):
            response = self._call(
                "main.criterion_semantic",
                self.config.judge_model,
                criterion_evidence_prompt(
                    trajectory.task.instruction,
                    item,
                    trajectory.final_answer,
                    baseline,
                    projections,
                ),
            )
            responses.append(response)
        maximum = float(item["points"])
        points = [_bounded_points(response.get("earned_points"), maximum) for response in responses]
        winner_index = min(
            range(len(responses)),
            key=lambda index: abs(points[index] - statistics.median(points)),
        )
        selected = dict(responses[winner_index])
        selected["earned_points"] = points[winner_index]
        status = str(selected.get("status") or "unknown").casefold()
        selected["status"] = status if status in VALID_STATUSES else "unknown"
        selected["condition_met"] = _condition_met(selected.get("condition_met"))
        if count > 1:
            selected["majority_vote"] = {
                "instances": count,
                "earned_points": points,
                "selected_instance": winner_index,
            }
        return selected

    def verify(self, trajectory: StagehandTrajectory) -> dict[str, Any]:
        usage_before = self.usage.to_dict()
        rubric, rubric_source = self._rubric(trajectory)
        items = rubric_items(rubric)
        action_history = _actions(trajectory)
        criterion_results: list[dict[str, Any]] = []
        selected_by_criterion: dict[int, list[Any]] = {}

        for index, item in enumerate(items):
            decision = evaluate_deterministic(item, trajectory)
            if decision.applicable:
                result = {
                    **copy.deepcopy(item),
                    "evaluation_method": "deterministic",
                    "status": decision.status,
                    "condition_met": True,
                    "earned_points": decision.earned_points,
                    "explanation": decision.explanation,
                    "evidence_links": [asdict(link) for link in decision.links],
                    "action_only_analysis": None,
                }
                criterion_results.append(result)
                selected_by_criterion[index] = []
                continue

            selected = select_evidence(
                trajectory,
                index,
                item,
                top_k=self.config.max_evidence_per_criterion,
                min_score=self.config.min_relevance_score,
                frame_char_budget=self.config.frame_char_budget,
                context_char_budget=self.config.criterion_context_char_budget,
            )
            selected_by_criterion[index] = selected
            relevant_steps = {
                value.link.step for value in selected if value.link.step is not None
            }
            relevant_actions = [
                action for action in action_history if int(action["step"]) in relevant_steps
            ]
            baseline = self._call(
                "action_rubric.criterion_action",
                self.config.action_rubric_model,
                action_analysis_prompt(trajectory.task.instruction, item, relevant_actions),
            )
            semantic = self._semantic_consensus(
                trajectory, item, baseline, [value.projection for value in selected]
            )
            criterion_results.append(
                {
                    **copy.deepcopy(item),
                    "evaluation_method": "semantic_llm",
                    "status": semantic["status"],
                    "condition_met": semantic.get("condition_met"),
                    "earned_points": semantic["earned_points"],
                    "explanation": str(semantic.get("explanation") or ""),
                    "judge_citations": semantic.get("citations") or [],
                    "evidence_links": selected_links(selected),
                    "evidence_relevance": [
                        {
                            "frame_index": value.frame_index,
                            "step": value.link.step,
                            "state_ordinal": value.link.state_ordinal,
                            "evidence_kind": value.link.evidence_kind,
                            "score": value.relevance_score,
                        }
                        for value in selected
                    ],
                    "action_only_analysis": baseline,
                    **({"majority_vote": semantic["majority_vote"]} if "majority_vote" in semantic else {}),
                }
            )

        # Conditions and dependencies affect the denominator only when actually activated.
        by_id = {int(result["id"]): result for result in criterion_results}
        active_ids: set[int] = set()
        for result in criterion_results:
            condition = result.get("condition")
            condition_ok = result.get("condition_met") is True if condition else True
            depends_on = result.get("depends_on") or []
            if isinstance(depends_on, int):
                depends_on = [depends_on]
            dependencies_ok = all(
                dependency in by_id and by_id[dependency].get("status") == "supported"
                for dependency in depends_on
            )
            result["applicable"] = bool(condition_ok and dependencies_ok)
            if result["applicable"]:
                active_ids.add(int(result["id"]))
            else:
                result["earned_points"] = 0.0

        total_max = possible_points(criterion_results, active_ids)
        total_earned = sum(
            float(result["earned_points"])
            for result in criterion_results
            if int(result["id"]) in active_ids
        )
        process_score = total_earned / total_max if total_max else 0.0
        process_success = process_score >= self.config.rubric_threshold

        timeline = global_timeline(trajectory, self.config.global_timeline_char_budget)
        side_effect = self._call(
            "main.side_effects",
            self.config.judge_model,
            side_effect_prompt(trajectory.task.instruction, timeline),
        )
        penalty = max(0.0, float(side_effect.get("penalty") or 0))
        adjusted_earned = max(0.0, total_earned - penalty)
        adjusted_process_score = adjusted_earned / total_max if total_max else 0.0
        process_success = adjusted_process_score >= self.config.rubric_threshold

        unique_projections: list[str] = []
        seen: set[tuple[str, int]] = set()
        for selected in selected_by_criterion.values():
            for value in selected:
                identity = (value.link.evidence_kind, value.link.state_ordinal)
                if identity not in seen:
                    seen.add(identity)
                    unique_projections.append(value.projection)
                if len(unique_projections) >= 8:
                    break
            if len(unique_projections) >= 8:
                break
        terminal = terminal_projection(
            trajectory,
            {"criterion": trajectory.task.instruction},
            self.config.criterion_context_char_budget,
        )
        outcome = self._call(
            "main.outcome",
            self.config.judge_model,
            outcome_prompt(
                trajectory.task.instruction,
                trajectory.final_answer,
                [
                    {
                        "id": result["id"],
                        "status": result["status"],
                        "earned_points": result["earned_points"],
                        "points": result["points"],
                        "explanation": result["explanation"],
                    }
                    for result in criterion_results
                ],
                terminal,
                unique_projections,
            ),
        )
        outcome_success = _strict_bool(outcome.get("outcome_success"))

        validity_without = self._call(
            "action_rubric.task_validity_without_trajectory",
            self.config.action_rubric_model,
            task_validity_prompt(trajectory.task.instruction),
        )
        validity_with = self._call(
            "action_rubric.task_validity_with_trajectory",
            self.config.action_rubric_model,
            task_validity_prompt(trajectory.task.instruction, terminal),
        )
        if not _strict_bool(validity_without.get("valid"), True) and not _strict_bool(
            validity_with.get("valid"), True
        ):
            outcome_success = False

        errors = list(trajectory.manifest.get("deterministic_tool_errors") or [])
        if not outcome_success or side_effect.get("has_unintended_side_effect") or errors:
            failure = self._call(
                "main.first_failure",
                self.config.judge_model,
                failure_prompt(
                    trajectory.task.instruction,
                    outcome,
                    criterion_results,
                    timeline,
                    errors,
                ),
            )
        else:
            failure = {
                "first_failure_step": None,
                "error_code": None,
                "error_category": "none",
                "error_type": "none",
                "reasoning": "No evidence-grounded failure was found because outcome succeeded.",
                "evidence_steps": [],
            }

        failure = normalize_failure(failure, errors)

        if self.config.success_criterion == "process":
            top_success = process_success
        elif self.config.success_criterion == "both":
            top_success = process_success and outcome_success
        else:
            top_success = outcome_success
        identity = cache_identity(trajectory, rubric, self.config)
        return {
            "score": int(top_success),
            "requested_evidence_mode": EVIDENCE_MODE,
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "upstream_verifier_commit": UPSTREAM_COMMIT,
            "upstream_usage": "read-only behavioral reference; no runtime imports",
            "frozen_rubric_sha256": rubric_hash(rubric),
            "rubric_source": rubric_source,
            "model_roles": {
                "judge": self.config.judge_model,
                "action_rubric": self.config.action_rubric_model,
            },
            "action_count": len(trajectory.actions),
            "state_count": trajectory.manifest.get("state_count"),
            "alignment_complete": len(trajectory.frames) == len(trajectory.actions),
            "capture_coverage": trajectory.manifest.get("capture_coverage"),
            "synthetic_initial_state": trajectory.manifest.get("capture_coverage", {}).get(
                "synthetic_initial_state"
            ),
            "cache_identity": identity,
            "verifier_config": self.config.to_dict(),
            "result": {
                "top_score": int(top_success),
                "success_criterion": self.config.success_criterion,
                "rubric": {
                    "score": adjusted_process_score,
                    "is_success": process_success,
                    "total_max_points": total_max,
                    "total_earned_points": adjusted_earned,
                    "unadjusted_earned_points": total_earned,
                    "side_effect_penalty": penalty,
                    "items": criterion_results,
                },
                "process": {
                    "success": process_success,
                    "score": adjusted_process_score,
                },
                "outcome": {
                    "success": outcome_success,
                    "reasoning": str(outcome.get("reasoning") or ""),
                    "confidence": outcome.get("confidence"),
                    "unsupported_claims": outcome.get("unsupported_claims") or [],
                    "evidence_steps": outcome.get("evidence_steps") or [],
                },
                "side_effects": side_effect,
                "error_taxonomy": {
                    "first_point_of_failure": failure,
                    "task_verification": validity_without,
                    "task_verification_with_trajectory": validity_with,
                    "deterministic_tool_errors": errors,
                },
            },
            "llm_usage": usage_delta(usage_before, self.usage.to_dict()),
        }

