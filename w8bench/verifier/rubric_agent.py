"""Rubric execution for recorded screenshot and DOM evidence."""

from __future__ import annotations
import asyncio
import copy
import json
import re
import traceback
from pathlib import Path
from string import Template
from typing import Any
from .models import (
    VerifierAgent,
    AgentConfig,
    RunContext,
    VerificationResult,
    MMRubricResult,
    MMRubricOutcomeResult,
    MajorityVoteMetadata,
    UserMessageType,
)
from . import rubric_scoring as scoring
from . import validity
from .clients.providers import ChatCompletionClient

_LOGICAL_STAGE_NAMES = {
    "screenshot_verifier": {
        "__init__": "w8bench.verifier.screenshot_verifier.rubric_agent.__init__",
        "_get_config_class": "w8bench.verifier.screenshot_verifier.rubric_agent._get_config_class",
        "_action_client": "w8bench.verifier.screenshot_verifier.rubric_agent._action_client",
        "_judge_client": "w8bench.verifier.screenshot_verifier.rubric_agent._judge_client",
        "initialize": "w8bench.verifier.screenshot_verifier.rubric_agent.initialize",
        "run": "w8bench.verifier.screenshot_verifier.rubric_agent.run",
        "_format_action_history": "w8bench.verifier.screenshot_verifier.rubric_agent._format_action_history",
        "_extract_input_from_datapoint": "w8bench.verifier.screenshot_verifier.rubric_agent._extract_input_from_datapoint",
        "_wrap_result": "w8bench.verifier.screenshot_verifier.rubric_agent._wrap_result",
        "_call_llm": "w8bench.verifier.screenshot_verifier.rubric_agent._call_llm",
        "_generate_rubric": "w8bench.verifier.screenshot_verifier.rubric_agent._generate_rubric",
        "_check_rubric_dependencies": "w8bench.verifier.screenshot_verifier.rubric_agent._check_rubric_dependencies",
        "_group_evidence_by_criterion": "w8bench.verifier.screenshot_verifier.rubric_agent._group_screenshots_by_criterion",
        "_invert_grouped_evidence": "w8bench.verifier.screenshot_verifier.rubric_agent._invert_grouped_screenshots",
        "_filter_irrelevant_evidence": "w8bench.verifier.screenshot_verifier.rubric_agent._filter_irrelevant_screenshots",
        "_disambiguate_conditional_criteria": "w8bench.verifier.screenshot_verifier.rubric_agent._disambiguate_conditional_criteria",
        "_rubric_reality_check": "w8bench.verifier.screenshot_verifier.rubric_agent._rubric_reality_check",
        "_rescore_criterion": "w8bench.verifier.screenshot_verifier.rubric_agent._rescore_criterion_with_screenshots",
        "_rescore_rubric": "w8bench.verifier.screenshot_verifier.rubric_agent._rescore_rubric_with_screenshots",
        "_detect_unsolicited_side_effects": "w8bench.verifier.screenshot_verifier.rubric_agent._detect_unsolicited_side_effects",
        "_outcome_verification": "w8bench.verifier.screenshot_verifier.rubric_agent._outcome_verification",
        "_first_point_of_failure_analysis": "w8bench.verifier.screenshot_verifier.rubric_agent._first_point_of_failure_analysis",
        "_compute_first_failure": "w8bench.verifier.screenshot_verifier.rubric_agent._compute_first_failure",
        "_classify_task_with_trajectory": "w8bench.verifier.screenshot_verifier.rubric_agent._classify_task_with_trajectory",
        "_classify_task": "w8bench.verifier.screenshot_verifier.rubric_agent._classify_task",
        "_run_steps_6_7_single_instance": "w8bench.verifier.screenshot_verifier.rubric_agent._run_steps_6_7_single_instance",
        "_build_full_rubric_context": "w8bench.verifier.screenshot_verifier.rubric_agent._build_full_rubric_context",
        "_build_full_rubric_with_baselines": "w8bench.verifier.screenshot_verifier.rubric_agent._build_full_rubric_with_baselines",
        "_build_scored_rubric_summary": "w8bench.verifier.screenshot_verifier.rubric_agent._build_scored_rubric_summary",
        "run_failure_points_only": "w8bench.verifier.screenshot_verifier.rubric_agent.run_failure_points_only",
        "_generate_reply": "w8bench.verifier.screenshot_verifier.rubric_agent._generate_reply",
    },
    "dom_model": {
        "__init__": "w8bench.verifier.dom_model.rubric_agent.__init__",
        "_get_config_class": "w8bench.verifier.dom_model.rubric_agent._get_config_class",
        "_action_client": "w8bench.verifier.dom_model.rubric_agent._action_client",
        "_judge_client": "w8bench.verifier.dom_model.rubric_agent._judge_client",
        "initialize": "w8bench.verifier.dom_model.rubric_agent.initialize",
        "run": "w8bench.verifier.dom_model.rubric_agent.run",
        "_format_action_history": "w8bench.verifier.dom_model.rubric_agent._format_action_history",
        "_extract_input_from_datapoint": "w8bench.verifier.dom_model.rubric_agent._extract_input_from_datapoint",
        "_wrap_result": "w8bench.verifier.dom_model.rubric_agent._wrap_result",
        "_call_llm": "w8bench.verifier.dom_model.rubric_agent._call_llm",
        "_generate_rubric": "w8bench.verifier.dom_model.rubric_agent._generate_rubric",
        "_check_rubric_dependencies": "w8bench.verifier.dom_model.rubric_agent._check_rubric_dependencies",
        "_group_evidence_by_criterion": "w8bench.verifier.dom_model.rubric_agent._group_dom_states_by_criterion",
        "_invert_grouped_evidence": "w8bench.verifier.dom_model.rubric_agent._invert_grouped_dom_states",
        "_filter_irrelevant_evidence": "w8bench.verifier.dom_model.rubric_agent._filter_irrelevant_dom_states",
        "_disambiguate_conditional_criteria": "w8bench.verifier.dom_model.rubric_agent._disambiguate_conditional_criteria",
        "_rubric_reality_check": "w8bench.verifier.dom_model.rubric_agent._rubric_reality_check",
        "_rescore_criterion": "w8bench.verifier.dom_model.rubric_agent._rescore_criterion_with_dom_evidence",
        "_rescore_rubric": "w8bench.verifier.dom_model.rubric_agent._rescore_rubric_with_dom_evidence",
        "_detect_unsolicited_side_effects": "w8bench.verifier.dom_model.rubric_agent._detect_unsolicited_side_effects",
        "_outcome_verification": "w8bench.verifier.dom_model.rubric_agent._outcome_verification",
        "_first_point_of_failure_analysis": "w8bench.verifier.dom_model.rubric_agent._first_point_of_failure_analysis",
        "_compute_first_failure": "w8bench.verifier.dom_model.rubric_agent._compute_first_failure",
        "_classify_task_with_trajectory": "w8bench.verifier.dom_model.rubric_agent._classify_task_with_trajectory",
        "_classify_task": "w8bench.verifier.dom_model.rubric_agent._classify_task",
        "_run_steps_6_7_single_instance": "w8bench.verifier.dom_model.rubric_agent._run_steps_6_7_single_instance",
        "_build_full_rubric_context": "w8bench.verifier.dom_model.rubric_agent._build_full_rubric_context",
        "_build_full_rubric_with_baselines": "w8bench.verifier.dom_model.rubric_agent._build_full_rubric_with_baselines",
        "_build_scored_rubric_summary": "w8bench.verifier.dom_model.rubric_agent._build_scored_rubric_summary",
        "run_failure_points_only": "w8bench.verifier.dom_model.rubric_agent.run_failure_points_only",
        "_generate_reply": "w8bench.verifier.dom_model.rubric_agent._generate_reply",
    },
}


def resolve_tools(names):
    """Resolve tool-group names through an unavailable registry.

    This package requires explicit action_definitions for failure analysis.
    Tool-group lookup raises RuntimeError.
    """
    raise RuntimeError(
        "resolve_tools is a stub. Supply MMRubricAgentConfig.action_definitions directly (or leave both tools and action_definitions unset to skip schema-level failure validation)."
    )


def tools_to_action_definitions(tools):
    raise RuntimeError("tools_to_action_definitions is a stub.")


def _build_client_from_endpoint_config(cfg: Any, *, evidence_mode, logger) -> Any:
    from w8bench.verifier.clients.retry import GracefulRetryClient
    from w8bench.verifier.clients.factory import create_client_from_config

    if isinstance(cfg, (str, Path)):
        p = Path(cfg).expanduser()
        if p.is_dir() or (p.is_file() and p.suffix == ".json"):
            return GracefulRetryClient.from_path(
                p, logger=logger, eval_model="*", evidence_mode=evidence_mode
            )
        raise FileNotFoundError(f"Endpoint config not found: {p}")
    if isinstance(cfg, list):
        clients = [
            create_client_from_config(c, evidence_mode=evidence_mode) for c in cfg
        ]
        return GracefulRetryClient(
            clients=clients, logger=logger, evidence_mode=evidence_mode
        )
    if isinstance(cfg, dict):
        return create_client_from_config(cfg, evidence_mode=evidence_mode)
    raise TypeError(
        f"Unsupported endpoint config type {type(cfg).__name__}; expected dict, list[dict], or str path."
    )


class RubricAgent(VerifierAgent):
    _STEP_NUMBERS_RE = re.compile("^\\d+(-\\d+)?(,\\d+)*$")

    def __init__(
        self, config: AgentConfig | dict[str, Any] | None = None, **kwargs: Any,
    ):
        super().__init__(config, **kwargs)
        if self.config.action_client is None and self.config.action_client_config:
            self.config.action_client = _build_client_from_endpoint_config(
                self.config.action_client_config,
                evidence_mode=self.evidence_mode,
                logger=self.logger,
            )
        if self.config.judge_client is None and self.config.judge_client_config:
            self.config.judge_client = _build_client_from_endpoint_config(
                self.config.judge_client_config,
                evidence_mode=self.evidence_mode,
                logger=self.logger,
            )
        assert self.config.action_client is not None, (
            "action_client or action_client_config must be provided"
        )
        assert self.config.judge_client is not None, (
            "judge_client or judge_client_config must be provided"
        )
        assert (
            self.config.majority_vote_instances >= 1
            and self.config.majority_vote_instances % 2 == 1
        ), (
            f"majority_vote_instances must be a positive odd number, got {self.config.majority_vote_instances}"
        )

    @classmethod
    def _get_config_class(cls):
        return cls.config_type

    @property
    def _action_client(self) -> ChatCompletionClient:
        return self.config.action_client

    @property
    def _judge_client(self) -> ChatCompletionClient:
        return self.config.judge_client

    async def initialize(self, run_context):
        await super().initialize(run_context)
        if not getattr(self.config, self.evidence_dir_key):
            setattr(self.config, self.evidence_dir_key, str(run_context.output_dir))

    async def run(
        self, run_context: RunContext, input: Any = None,
    ) -> list[VerificationResult]:
        dp = run_context.data_point
        input_dict = self._extract_input_from_datapoint(
            dp, evidence_dir=getattr(self.config, self.evidence_dir_key),
            redo_eval=self.config.redo_eval,
        )
        result = await self._generate_reply(input_dict)
        return self._wrap_result(result)

    @staticmethod
    def _format_action_history(
        summaries: list[Any], max_url_chars: int = 150,
        evaluation_context: dict[str, Any] | None = None,
    ) -> str:
        lines: list[str] = []
        lines.extend(RubricAgent._action_history_context(evaluation_context))
        for s in summaries:
            lines.extend(RubricAgent._action_history_step(s, max_url_chars))
        return "\n".join(lines)

    def _wrap_result(self, result: dict) -> list[VerificationResult]:
        total_max = result.get("total_max_points", 1)
        total_earned = result.get("total_earned_points", 0)
        rubric_score = total_earned / total_max if total_max > 0 else 0.0
        outcome_verification = result.get("outcome_verification", {})
        output_success = outcome_verification.get("output_success")
        mv_raw = result.get("majority_vote_metadata", {})
        rubric_vr = self._rubric_result(
            result, total_max, total_earned, rubric_score, mv_raw
        )
        outcome_vr = self._outcome_result(outcome_verification, output_success)
        return [rubric_vr, outcome_vr]

    async def _call_llm(
        self, messages: list[dict], client: Any, json_output: bool = False,
    ) -> str:
        return await validity._call_llm(messages, client, json_output=json_output)

    async def _generate_rubric(self, task: str, init_url_context: str) -> dict:
        if self.record_generation_trace:
            self.rubric_generation_trace = []
        prompt = Template(self.prompts.RUBRIC_GENERATION_PROMPT_TEMPLATE).substitute(
            task_id=task, init_url_context=init_url_context
        )
        messages = [{"role": "user", "content": prompt}]
        max_iters = self.config.max_iters
        attempt = 0
        errors = []
        while max_iters > 0:
            attempt += 1
            receipt = self._rubric_attempt_receipt(
                "rubric_generation", attempt, messages
            )
            try:
                response_text = await self._call_llm(
                    messages, self._judge_client, json_output=True
                )
                if receipt is not None:
                    receipt["response_text"] = response_text
                rubric_dict = json.loads(response_text)
                if receipt is not None:
                    receipt["response"] = rubric_dict
                scoring.verify_generated_rubric(rubric_dict)
                self.logger.info(f"Successfully generated rubric: {rubric_dict}")
                rubric_dict = await self._check_rubric_dependencies(
                    rubric_dict, task, init_url_context
                )
                scoring.verify_generated_rubric(rubric_dict)
                if receipt is not None:
                    receipt["accepted"] = True
                return rubric_dict
            except Exception as e:
                if receipt is not None:
                    receipt["error"] = f"{type(e).__name__}: {e}"
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                self._generation_error(
                    messages, errors, e, attempt, response_text if 'response_text' in dir() else None,
                )
                max_iters -= 1
        error_summary = "\n".join(errors)
        raise RuntimeError(
            f"Failed to generate a valid rubric after {self.config.max_iters} attempts:\n{error_summary}"
        )

    async def _check_rubric_dependencies(
        self, rubric_dict: dict, task: str, init_url_context: str,
    ) -> dict:
        if self.record_generation_trace and (
            not hasattr(self, "rubric_generation_trace")
        ):
            if self.record_generation_trace:
                self.rubric_generation_trace = []
        prompt = Template(self.prompts.RUBRIC_DEPENDENCY_CHECKING_PROMPT).substitute(
            task_id=task,
            rubric=json.dumps(rubric_dict, indent=2),
            init_url_context=init_url_context,
        )
        messages = [{"role": "user", "content": prompt}]
        max_iters = self.config.max_iters
        attempt = 0
        errors = []
        while max_iters > 0:
            attempt += 1
            receipt = self._rubric_attempt_receipt(
                "dependency_check", attempt, messages
            )
            try:
                response_text = await self._call_llm(
                    messages, self._judge_client, json_output=True
                )
                if receipt is not None:
                    receipt["response_text"] = response_text
                result = json.loads(response_text)
                if receipt is not None:
                    receipt["response"] = result
                rubric_dict = self._dependency_rubric(result, rubric_dict)
                if receipt is not None:
                    receipt["accepted"] = True
                return rubric_dict
            except Exception as e:
                if receipt is not None:
                    receipt["error"] = f"{type(e).__name__}: {e}"
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                self._dependency_error(
                    messages, errors, e, attempt, response_text if 'response_text' in dir() else None,
                )
                max_iters -= 1
        error_summary = "\n".join(errors)
        raise RuntimeError(
            f"Failed to check rubric dependencies after {self.config.max_iters} attempts:\n{error_summary}"
        )

    def _group_evidence_by_criterion(
        self, relevance_scores: dict[int, dict], num_criteria: int,
    ) -> dict[int, list[int]]:
        grouped = {c: [] for c in range(num_criteria)}
        for screenshot_idx, scores_dict in relevance_scores.items():
            for key, score in scores_dict.items():
                if key == self.state_index_field:
                    continue
                grouped[key].append((screenshot_idx, score))
        max_k = getattr(self.config, self.evidence_limit_key)
        for c in grouped:
            grouped[c].sort(key=lambda x: (x[1], x[0]), reverse=True)
            grouped[c] = [s for s, _ in grouped[c][:max_k]]
        return grouped

    @staticmethod
    def _invert_grouped_evidence(grouped: dict[int, list[int]]) -> dict[int, list[int]]:
        inverted: dict[int, list[int]] = {}
        for c_idx, s_indices in grouped.items():
            for s_idx in s_indices:
                inverted.setdefault(s_idx, []).append(c_idx)
        for s_idx in inverted:
            inverted[s_idx].sort()
        return inverted

    def _filter_irrelevant_evidence(
        self, grouped: dict[int, list[int]], relevance_scores: dict[int, dict],
    ) -> dict[int, list[int]]:
        filtered: dict[int, list[int]] = {}
        total_removed = 0
        for c_idx, s_indices in grouped.items():
            scored = [(s, relevance_scores.get(s, {}).get(c_idx, 0)) for s in s_indices]
            high_scores = [s for _, s in scored if s >= 6]
            if not high_scores:
                filtered[c_idx] = s_indices
                continue
            min_high = min(high_scores)
            kept = [
                s for s, score in scored if not (score < 5 and min_high - score > 2)
            ]
            if not kept:
                kept = s_indices
            total_removed += len(s_indices) - len(kept)
            filtered[c_idx] = kept
        if total_removed > 0:
            self.logger.info(
                f"[MM Pipeline] Filtered {total_removed}{self.filtered_pairs_suffix}"
            )
        return filtered

    async def _disambiguate_conditional_criteria(
        self, rubric: dict, evidence_by_criterion: dict[int, list[dict]], task: str,
        init_url_context: str,
    ) -> dict:
        messages, conditional_indices = self._condition_messages(
            rubric, evidence_by_criterion, task, init_url_context
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                return await self._condition_attempt(
                    messages, rubric, conditional_indices
                )
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self.logger.error(
                    f"Error in conditional criteria disambiguation (attempt {self.config.max_iters + 1 - max_iters}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {e}. Please ensure your output follows the exact format specified.",
                    }
                )
                max_iters -= 1
        self.logger.warning(
            f"Failed conditional criteria disambiguation after {self.config.max_iters} attempts. Last error: {last_error}. Falling back to per-criterion OR semantics."
        )
        for c_idx in conditional_indices:
            verifications = [
                a["condition_verification"]
                for a in evidence_by_criterion.get(c_idx, [])
                if "condition_verification" in a
            ]
            if verifications:
                rubric["items"][c_idx]["is_condition_met"] = any(verifications)
        return rubric

    async def _rubric_reality_check(
        self, rubric: dict, evidence_by_criterion: dict[int, list[dict]], task: str,
        init_url_context: str,
    ) -> dict:
        messages, num_criteria = self._reality_messages(
            rubric, evidence_by_criterion, task, init_url_context
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                return await self._reality_attempt(messages, rubric, num_criteria)
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self.logger.error(
                    f"Error in rubric reality check (attempt {self.config.max_iters + 1 - max_iters}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {e}. Please ensure your output follows the exact format specified.",
                    }
                )
                max_iters -= 1
        self.logger.warning(
            f"Failed rubric reality check after {self.config.max_iters} attempts. Last error: {last_error}. Proceeding without reality notes."
        )
        for item in rubric["items"]:
            item["reality_notes"] = ""
        return rubric

    async def _rescore_criterion(
        self, rubric: dict, evidence_by_criterion: dict[int, list[dict]], task: str,
        init_url_context: str, action_history: str, predicted_output: str, total_states: int = 0,
    ) -> dict:
        for c_idx in range(len(rubric["items"])):
            criterion = rubric["items"][c_idx]
            if "condition" in criterion and (
                not criterion.get("is_condition_met", False)
            ):
                criterion["applicable_evidence"] = (
                    "N/A — condition not met, criterion skipped."
                )
                criterion[self.justification_field] = (
                    "Condition not met; criterion does not apply and was not rescored."
                )
                criterion[self.score_field] = 0.0
                continue
            messages = self._criterion_rescore_messages(
                rubric, evidence_by_criterion, c_idx, criterion, task, init_url_context, action_history,
                predicted_output, total_states,
            )
            await self._rescore_one_criterion(messages, criterion, c_idx)
        return rubric

    async def _rescore_rubric(
        self, rubric: dict, evidence_by_criterion: dict[int, list[dict]], task: str,
        init_url_context: str, action_history: str, predicted_output: str, total_states: int = 0,
    ) -> dict:
        num_criteria = len(rubric["items"])
        skipped = self._skipped_criteria(rubric)
        messages = self._rubric_rescore_messages(
            rubric, evidence_by_criterion, task, init_url_context, action_history, predicted_output,
            total_states, num_criteria,
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                return await self._rubric_rescore_attempt(
                    messages, rubric, num_criteria, skipped
                )
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self.logger.error(
                    f"Error rescoring rubric (attempt {self.config.max_iters + 1 - max_iters}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {e}. Please ensure your output includes all {num_criteria} criteria in the correct format.",
                    }
                )
                max_iters -= 1
        self.logger.warning(
            f"Failed to rescore rubric after {self.config.max_iters} attempts. Last error: {last_error}"
        )
        raise scoring.UngradedVerifierError("rubric_rescore", str(last_error))

    async def _detect_unsolicited_side_effects(
        self, rubric: dict, evidence_by_criterion: dict[int, list[dict]], task: str,
        init_url_context: str, action_history: str,
    ) -> dict:
        messages = self._side_effect_messages(
            rubric, evidence_by_criterion, task, init_url_context, action_history
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                return await self._side_effect_attempt(messages)
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self.logger.error(
                    f"Error detecting side effects (attempt {self.config.max_iters + 1 - max_iters}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {e}. Please ensure your output follows the exact format specified with all required fields.",
                    }
                )
                max_iters -= 1
        self.logger.warning(
            f"Failed to detect side effects after {self.config.max_iters} attempts. Last error: {last_error}"
        )
        raise scoring.UngradedVerifierError("side_effect_scoring", str(last_error))

    async def _outcome_verification(
        self, rubric: dict, evidence_by_criterion: dict[int, list[dict]], task: str,
        init_url_context: str, action_history: str, predicted_output: str, total_states: int = 0,
    ) -> dict:
        messages = self._outcome_messages(
            rubric, evidence_by_criterion, task, init_url_context, action_history, predicted_output,
            total_states,
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                return await self._outcome_attempt(messages)
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self.logger.error(
                    f"Error in outcome verification (attempt {self.config.max_iters + 1 - max_iters}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {e}. Please ensure your output follows the exact JSON format specified with all required fields.",
                    }
                )
                max_iters -= 1
        self.logger.warning(
            f"Failed outcome verification after {self.config.max_iters} attempts. Last error: {last_error}"
        )
        return {
            "primary_intent": f"Failed after {self.config.max_iters} attempts. Last error: {last_error}",
            "reasoning": f"Outcome verification failed after {self.config.max_iters} attempts. Last error: {last_error}",
            "output_success": None,
        }

    async def _first_point_of_failure_analysis(
        self, rubric: dict, evidence_by_criterion: dict[int, list[dict]], task: str,
        init_url_context: str, action_history: str, predicted_output: str, outcome_result: dict,
        total_states: int = 0, action_definitions: dict[str, set[str]] | None = None,
        step_actions: list[dict[str, Any]] | None = None,
    ) -> dict:
        if action_definitions is None:
            action_definitions = self.config.action_definitions
        messages = self._failure_messages(
            rubric, evidence_by_criterion, task, init_url_context, action_history, predicted_output,
            outcome_result, total_states, action_definitions,
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                return await self._failure_attempt(
                    messages, step_actions, action_definitions
                )
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self.logger.error(
                    f"Error in points of failure analysis (attempt {self.config.max_iters + 1 - max_iters}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {e}. Please ensure your output follows the exact JSON format specified with all required fields.",
                    }
                )
                max_iters -= 1
        self.logger.warning(
            f"Failed points of failure analysis after {self.config.max_iters} attempts. Last error: {last_error}"
        )
        return {
            "reasoning": f"Failed after {self.config.max_iters} attempts. Last error: {last_error}",
            "has_failure": False,
            "failure_points": [],
            "first_failure_step": None,
            "first_failure_summary": "",
        }

    @staticmethod
    def _compute_first_failure(failure_points: list[dict]) -> tuple[int | None, str]:
        if not failure_points:
            return (None, "")

        def sort_key(fp: dict) -> int:
            return scoring.parse_first_step_number(fp.get("step_numbers", ""))

        sorted_fps = sorted(failure_points, key=sort_key)
        fp = sorted_fps[0]
        step = scoring.parse_first_step_number(fp.get("step_numbers", ""))
        summary = f"[{fp.get('error_code', '')}] {fp.get('error_type', '')}: {fp.get('what_happened', '')}"
        return (step if step != 999999 else None, summary)

    async def _classify_task_with_trajectory(
        self, rubric: dict, evidence_by_criterion: dict[int, list[dict]], task: str,
        init_url_context: str, action_history: str, predicted_output: str, outcome_result: dict,
        total_states: int = 0, apps: str = 'N/A',
    ) -> dict:
        messages = self._trajectory_messages(
            rubric, evidence_by_criterion, task, init_url_context, action_history, predicted_output,
            outcome_result, total_states, apps,
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                return await self._trajectory_attempt(messages)
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                attempt = self.config.max_iters + 1 - max_iters
                self.logger.error(
                    f"Error in trajectory-informed task verification (attempt {attempt}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {e}. Please ensure your output follows the exact JSON format specified with all required fields.",
                    }
                )
                max_iters -= 1
        self.logger.warning(
            "Failed trajectory-informed task verification after %d attempts. Last error: %s",
            self.config.max_iters,
            last_error,
        )
        return {
            "reasoning_is_ambiguous": f"Failed after {self.config.max_iters} attempts. Last error: {last_error}",
            "is_ambiguous": None,
            "ambiguity_codes": [],
            "reasoning_is_invalid": f"Failed after {self.config.max_iters} attempts. Last error: {last_error}",
            "is_invalid": None,
            "invalid_task_codes": [],
        }

    async def _classify_task(
        self, task: str, url: str, apps: list[str] | None = None,
    ) -> dict:
        result = await validity.classify_task(
            task, url, self._action_client, apps=apps, date=self.config.validity_date,
            system_messages=self.DEFAULT_SYSTEM_MESSAGES,
            prompt_template=self.prompts.CHECK_VALID_TASK_PROMPT,
            logger=self.task_verification_logger,
        )
        return result.model_dump()

    async def _run_steps_6_7_single_instance(
        self, rubric_dict: dict, evidence_by_criterion: dict, evidence: list | dict[int, Any],
        task: str, init_url_context: str, action_history: str, predicted_output: str, instance_idx: int,
    ) -> tuple[dict, float, dict]:
        rubric_copy = copy.deepcopy(rubric_dict)
        instance_steps = {}
        rubric_copy = await self._rescore_instance(
            rubric_copy, evidence_by_criterion, evidence, task, init_url_context, action_history,
            predicted_output,
        )
        instance_steps["step6_rescoring_summary"] = [
            self._rescoring_summary_item(item) for item in rubric_copy["items"]
        ]
        side_effect_result = await self._detect_unsolicited_side_effects(
            rubric_copy, evidence_by_criterion, task, init_url_context, action_history
        )
        instance_steps["step7_penalty_criteria"] = side_effect_result.get(
            "penalty_criteria", []
        )
        instance_steps["step7_reasoning"] = side_effect_result.get("reasoning", "")
        instance_steps["step7_requires_penalty"] = side_effect_result.get(
            "requires_penalty", False
        )
        if side_effect_result.get("penalty_criteria"):
            rubric_copy["items"].extend(side_effect_result["penalty_criteria"])
        final_scores = scoring.compute_final_scores(rubric_copy, self.score_field)
        rubric_copy["total_max_points"] = final_scores["total_max_points"]
        rubric_copy["total_earned_points"] = final_scores["total_earned_points"]
        score = (
            final_scores["total_earned_points"] / final_scores["total_max_points"]
            if final_scores["total_max_points"] > 0
            else 0.0
        )
        self.logger.info(f"[Majority Vote] Instance {instance_idx}: Score={score:.4f}")
        return (rubric_copy, score, instance_steps)

    @classmethod
    def _build_full_rubric_context(cls, rubric: dict, target_criterion_idx: int) -> str:
        lines = []
        for j, criterion in enumerate(rubric["items"]):
            name = criterion.get("criterion", f"Criterion {j}")
            description = criterion.get("description", "")
            max_points = criterion.get("max_points", 0)
            baseline_earned = criterion.get("earned_points", 0)
            baseline_justification = criterion.get("justification", "")
            condition = criterion.get("condition")
            reality_notes = criterion.get("reality_notes", "")
            if j < target_criterion_idx:
                rescored_earned = criterion.get(cls.score_field, baseline_earned)
                rescored_justification = criterion.get(
                    cls.justification_field, baseline_justification
                )
                lines.append(f'--- Criterion {j}: "{name}" [ALREADY RESCORED] ---')
                include_condition_result = True
            elif j == target_criterion_idx:
                lines.append(
                    f'>>> Criterion {j}: "{name}" <<< SCORE THIS CRITERION <<<'
                )
                include_condition_result = True
            else:
                lines.append(f'--- Criterion {j}: "{name}" [NOT YET SCORED] ---')
                include_condition_result = False
            lines.append(f"Description: {description}")
            if reality_notes:
                lines.append(f"Reality Notes: {reality_notes}")
            if condition:
                lines.append(f"Condition: {condition}")
                if include_condition_result:
                    lines.append(
                        f"Condition Met: {criterion.get('is_condition_met', 'unknown')}"
                    )
            lines.append(f"Max Points: {max_points}")
            lines.append(
                f'Baseline: {baseline_earned}/{max_points} — "{baseline_justification}"'
            )
            if j < target_criterion_idx:
                lines.append(
                    f'Rescored: {rescored_earned}/{max_points} — "{rescored_justification}"'
                )
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _build_full_rubric_with_baselines(rubric: dict) -> str:
        lines = []
        for j, criterion in enumerate(rubric["items"]):
            lines.append(
                f'--- Criterion {j}: "{criterion.get("criterion", f"Criterion {j}")}" ---'
            )
            lines.append(f"Description: {criterion.get('description', '')}")
            if criterion.get("reality_notes"):
                lines.append(f"Reality Notes: {criterion['reality_notes']}")
            if criterion.get("condition"):
                lines.append(f"Condition: {criterion['condition']}")
                lines.append(
                    f"Condition Met (from action-only scoring): {criterion.get('is_condition_met', 'unknown')}"
                )
            lines.append(f"Max Points: {criterion.get('max_points', 0)}")
            lines.append(
                f"Baseline Score: {criterion.get('earned_points', 0)}/{criterion.get('max_points', 0)}"
            )
            lines.append(
                f'Baseline Justification: "{criterion.get("justification", "")}"'
            )
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def _build_scored_rubric_summary(cls, rubric: dict) -> str:
        lines = []
        for j, item in enumerate(rubric["items"]):
            lines.append(
                f'--- Criterion {j}: "{item.get("criterion", f"Criterion {j}")}" ---'
            )
            lines.append(f"Description: {item.get('description', '')}")
            if item.get("reality_notes"):
                lines.append(f"Reality Notes: {item['reality_notes']}")
            if item.get("condition"):
                lines.append(f"Condition: {item['condition']}")
                lines.append(
                    f"Condition Met: {item.get('is_condition_met', 'unknown')}"
                )
            lines.append(f"Max Points: {item.get('max_points', 0)}")
            lines.append(
                f"Baseline Score (action-only): {item.get('earned_points', 'N/A')}/{item.get('max_points', 0)}"
            )
            lines.append(
                f"{cls.final_score_prefix}{item.get(cls.score_field, 'N/A')}/{item.get('max_points', 0)}"
            )
            lines.append(
                f'Final Justification: "{item.get(cls.justification_field, "N/A")}"'
            )
            if item.get("penalty"):
                lines.append("[PENALTY CRITERION]")
            lines.append("")
        lines.append(
            f"Total: {rubric.get('total_earned_points', 'N/A')}/{rubric.get('total_max_points', 'N/A')}"
        )
        return "\n".join(lines)

    async def run_failure_points_only(self, input: dict) -> dict:
        context = self._failure_only_input(input)
        rubric_dict = self._failure_only_rubric(input)
        intermediate = self._failure_only_intermediate(input, context["evidence_dir"])
        (
            evidence_by_criterion,
            outcome_result,
            total_states,
            step_actions,
            action_definitions,
        ) = self._failure_only_evidence(input, rubric_dict, intermediate)
        step9_result = await self._failure_only_failure(
            context, rubric_dict, intermediate, evidence_by_criterion, outcome_result, total_states,
            step_actions, action_definitions,
        )
        await self._failure_only_trajectory(
            context, rubric_dict, intermediate, evidence_by_criterion, outcome_result, total_states,
        )
        await self._failure_only_task(context, rubric_dict, intermediate)
        rubric_dict["intermediate_mm_rubric_steps"] = intermediate
        self.logger.info(
            f"[failure_analysis_only] Done. has_failure={step9_result.get('has_failure')}, first_failure_step={step9_result.get('first_failure_step')}"
        )
        return rubric_dict

    async def _generate_reply(self, input: dict) -> dict:
        context = self._evaluation_input(input)
        rubric_dict, complete = await self._prepare_rubric(context)
        if complete:
            return rubric_dict
        rubric_dict, complete = await self._score_action_history(context, rubric_dict)
        if complete:
            return rubric_dict
        if context["evidence_dir"] is None:
            raise RuntimeError(self.missing_evidence_message)
        return await self._evaluate_evidence(context, rubric_dict)

    @classmethod
    def _extract_input_from_datapoint(cls, dp, evidence_dir, redo_eval):
        summaries = dp.solver_log.get_step_summaries()
        actions_list = cls._action_records(summaries)
        step_actions = [
            {
                "step_number": s.index,
                "action_name": s.action_name,
                "action_args_keys": list(s.action_args.keys()),
            }
            for s in summaries
            if s.action_name
        ]
        env_cfg = dp.task.environment_config or {}
        apps = env_cfg.get("apps", [])
        init_url = (
            env_cfg.get("init_url")
            or env_cfg.get("start_page")
            or env_cfg.get("start_url", "")
        )
        return {
            "task": dp.task.instruction,
            "action_history": cls._format_action_history(
                summaries, evaluation_context=dp.task.metadata.get("evaluation_context")
            ),
            "predicted_output": dp.solver_log.outcome.answer
            if dp.solver_log.outcome
            else "",
            cls.evidence_dir_key: evidence_dir,
            "actions_list": actions_list,
            "step_actions": step_actions,
            "precomputed_rubric": dp.task.metadata.get("precomputed_rubric"),
            "init_url": init_url,
            "apps": apps,
            "redo_eval": redo_eval,
        }

    def _evaluation_input(self, input):
        task: str = input["task"]
        action_history: str = input["action_history"]
        predicted_output: str = input.get("predicted_output", "")
        evidence_dir: str = input.get(self.evidence_dir_key) or getattr(
            self.config, self.evidence_dir_key
        )
        actions_list: list = input["actions_list"]
        step_actions: list[dict[str, Any]] | None = input.get("step_actions")
        precomputed_rubric = input.get("precomputed_rubric")
        init_url: str = input.get("init_url", "")
        apps: list = input.get("apps", [])
        redo_eval: bool = input.get("redo_eval", self.config.redo_eval)
        init_url_context = scoring.get_init_url_context(init_url)
        apps_str = ", ".join(apps) if apps else "N/A"
        return {
            "task": task,
            "action_history": action_history,
            "predicted_output": predicted_output,
            "evidence_dir": evidence_dir,
            "actions_list": actions_list,
            "step_actions": step_actions,
            "precomputed_rubric": precomputed_rubric,
            "init_url": init_url,
            "apps": apps,
            "redo_eval": redo_eval,
            "init_url_context": init_url_context,
            "apps_str": apps_str,
            "_input": input,
        }

    async def _prepare_rubric(self, context):
        rubric_dict = None
        if (
            isinstance(context["precomputed_rubric"], list)
            and len(context["precomputed_rubric"]) > 0
        ):
            context["precomputed_rubric"] = context["precomputed_rubric"][0]
        if context["precomputed_rubric"] and isinstance(
            context["precomputed_rubric"], dict
        ):
            rubric_dict = context["precomputed_rubric"]
            is_scored = False
            try:
                scoring.verify_rubric(rubric_dict, evidence_mode=self.evidence_mode)
                is_scored = True
            except Exception:
                pass
            if self.config.failure_analysis_only and is_scored:
                self.logger.info(
                    "[failure_analysis_only] Scored rubric found, skipping to steps 9-10."
                )
                return (await self.run_failure_points_only(context["_input"]), True)
            elif context["redo_eval"] and is_scored:
                rubric_dict = scoring.clear_rubric_scores(
                    rubric_dict, evidence_mode=self.evidence_mode
                )
                try:
                    scoring.verify_generated_rubric(rubric_dict)
                except Exception:
                    rubric_dict = None
            elif is_scored and (not context["redo_eval"]):
                return (rubric_dict, True)
            elif not is_scored:
                try:
                    scoring.verify_generated_rubric(rubric_dict)
                except Exception:
                    rubric_dict = None
        if rubric_dict is None:
            rubric_dict = await self._generate_rubric(
                context["task"], context["init_url_context"]
            )
        return (rubric_dict, False)

    async def _score_action_history(self, context, rubric_dict):
        messages = self._action_scoring_messages(context, rubric_dict)
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                response_text = await self._call_llm(
                    messages, self._action_client, json_output=True
                )
                response_dict = json.loads(response_text)
                response_dict = scoring.graft_scores_onto_rubric(
                    rubric_dict, response_dict
                )
                scoring.verify_rubric(response_dict, evidence_mode=self.evidence_mode)
                action_only_scores = scoring.compute_final_scores(
                    response_dict, "earned_points"
                )
                response_dict["total_max_points"] = action_only_scores[
                    "total_max_points"
                ]
                response_dict["total_earned_points"] = action_only_scores[
                    "total_earned_points"
                ]
                rubric_dict = response_dict
                break
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self.logger.warning(f"Action-only scoring attempt failed: {e}")
                messages.append({"role": "user", "content": f"Error: {e}"})
                max_iters -= 1
        if max_iters == 0:
            raise scoring.UngradedVerifierError("action_scoring", str(last_error))
        return (rubric_dict, False)

    async def _load_and_score_evidence(self, context, rubric_dict, intermediate):
        self.logger.info(self.loading_evidence_log)
        evidence = self._load_evidence(context["evidence_dir"], context["actions_list"])
        self.logger.info(
            f"[Step 1/9] Loaded {len(evidence)}{self.evidence_count_suffix}"
        )
        intermediate[self.state_count_key] = len(evidence)
        if self.evidence_mode == "screenshot_verifier" and isinstance(evidence, dict):
            intermediate["step1_source_state_ids"] = list(evidence)
        self.logger.info(
            f"[Step 2/9] Scoring relevance ({len(evidence)}{self.relevance_count_suffix}"
        )
        relevance_scores = await self._score_evidence_relevance(
            evidence, rubric_dict, context["task"], context["init_url_context"]
        )
        num_criteria = len(rubric_dict["items"])
        for sid, scores in relevance_scores.items():
            criterion_keys = {k for k in scores if k != self.state_index_field}
            assert len(criterion_keys) == num_criteria, (
                f"{self.relevance_error_prefix}{sid} has {len(criterion_keys)} criterion scores but expected {num_criteria}. Got keys: {sorted(criterion_keys)}, expected: {list(range(num_criteria))}"
            )
            assert scores[self.state_index_field] == sid, (
                f"{self.index_error_prefix}{sid} but stored {self.state_index_field} is {scores[self.state_index_field]}"
            )
        intermediate["step2_relevance_scores"] = {
            f"{self.relevance_key_prefix}{sid}": {str(k): v for k, v in scores.items()}
            for sid, scores in relevance_scores.items()
        }
        return (evidence, relevance_scores)

    async def _collect_evidence(self, context, rubric_dict, intermediate):
        evidence, relevance_scores = await self._load_and_score_evidence(
            context, rubric_dict, intermediate
        )
        self.logger.info(self.grouping_evidence_log)
        grouped_evidence = self._group_evidence_by_criterion(
            relevance_scores, len(rubric_dict["items"])
        )
        intermediate[self.grouped_states_key] = {
            str(k): v for k, v in grouped_evidence.items()
        }
        if getattr(self.config, self.filter_config_key):
            grouped_evidence = self._filter_irrelevant_evidence(
                grouped_evidence, relevance_scores
            )
        self.logger.info(self.analyzing_evidence_log)
        if getattr(self.config, self.batch_config_key):
            evidence_by_criterion = await self._analyze_evidence_batched(
                evidence, rubric_dict, grouped_evidence, context['task'], context['init_url_context'],
                context['action_history'], context['predicted_output'],
                relevance_scores=relevance_scores,
                min_relevance_threshold=self.config.min_relevance_threshold,
            )
        else:
            evidence_by_criterion = await self._analyze_evidence(
                evidence, rubric_dict, grouped_evidence, context['task'], context['init_url_context'],
                context['action_history'], context['predicted_output'],
            )
        intermediate["step4_evidence_by_criterion"] = {
            str(k): v for k, v in evidence_by_criterion.items()
        }
        return (evidence, evidence_by_criterion)

    async def _conditions_and_reality(
        self, context, rubric_dict, evidence_by_criterion, intermediate,
    ):
        rubric_dict = await self._condition_statuses(
            context, rubric_dict, evidence_by_criterion, intermediate
        )
        self.logger.info("[Step 5/9] Running rubric reality check...")
        rubric_dict = await self._rubric_reality_check(
            rubric_dict, evidence_by_criterion, context['task'], context['init_url_context'],
        )
        intermediate["step5_reality_check"] = {
            str(i): item.get("reality_notes", "")
            for i, item in enumerate(rubric_dict["items"])
        }
        return rubric_dict

    async def _score_instances(
        self, context, rubric_dict, evidence_by_criterion, evidence, intermediate,
    ):
        N = self.config.majority_vote_instances
        self.logger.info(f"[Steps 6-7/9] Running {N} majority vote instance(s)...")
        step67_tasks = [
            self._run_steps_6_7_single_instance(
                rubric_dict, evidence_by_criterion, evidence, context['task'],
                context['init_url_context'], context['action_history'], context['predicted_output'],
                instance_idx=i,
            )
            for i in range(N)
        ]
        step67_results = await asyncio.gather(*step67_tasks)
        median_idx, rubric_dict, score, median_steps = scoring.select_median_instance(
            step67_results
        )
        all_scores = [r[1] for r in step67_results]
        self.logger.info(f"[Steps 6-7/9] Scores: {all_scores}, median_idx={median_idx}")
        intermediate["step6_rescoring_summary"] = median_steps[
            "step6_rescoring_summary"
        ]
        intermediate["step7_penalty_criteria"] = median_steps["step7_penalty_criteria"]
        intermediate["step7_reasoning"] = median_steps["step7_reasoning"]
        intermediate["step7_requires_penalty"] = median_steps["step7_requires_penalty"]
        intermediate["majority_vote_steps67"] = {
            "all_scores": all_scores,
            "median_instance_idx": median_idx,
            "all_instances": [
                self._instance_summary(i, r) for i, r in enumerate(step67_results)
            ],
        }
        return (rubric_dict, step67_results, median_idx, score, N)

    async def _outcome_votes(
        self, context, rubric_dict, evidence_by_criterion, evidence, intermediate, N,
    ):
        self.logger.info(f"[Step 8/9] Running {N} outcome verification(s)...")
        step8_tasks = [
            self._outcome_verification(
                rubric_dict, evidence_by_criterion, context['task'], context['init_url_context'],
                context['action_history'], context['predicted_output'], total_states=len(evidence),
            )
            for _ in range(N)
        ]
        step8_results = await asyncio.gather(*step8_tasks)
        success_votes = [r.get("output_success") for r in step8_results]
        non_none_votes = [v for v in success_votes if v is not None]
        if len(non_none_votes) >= N // 2 + 1:
            majority_output_success = sum(non_none_votes) > len(non_none_votes) / 2
        else:
            majority_output_success = None
        majority_outcome_result = None
        for r in step8_results:
            if r.get("output_success") == majority_output_success:
                majority_outcome_result = r
                break
        if majority_outcome_result is None:
            majority_outcome_result = step8_results[0]
        majority_outcome_result = copy.deepcopy(majority_outcome_result)
        majority_outcome_result["output_success"] = majority_output_success
        intermediate["step8_outcome_verification"] = majority_outcome_result
        intermediate["majority_vote_step8"] = {
            "all_votes": success_votes,
            "majority_output_success": majority_output_success,
            "all_results": step8_results,
        }
        rubric_dict["outcome_verification"] = majority_outcome_result
        return (majority_outcome_result, success_votes, majority_output_success)

    async def _verify_failure(
        self, context, rubric_dict, evidence_by_criterion, evidence, intermediate,
        majority_outcome_result,
    ):
        cached_step9 = (
            context["precomputed_rubric"].get("first_point_of_failure")
            if isinstance(context["precomputed_rubric"], dict)
            else None
        )
        if cached_step9 and (not context["redo_eval"]):
            self.logger.info("[Step 9a/9] Reusing cached points of failure analysis.")
            step9_result = cached_step9
        else:
            self.logger.info("[Step 9a/9] Running points of failure analysis...")
            step9_result = await self._first_point_of_failure_analysis(
                rubric_dict, evidence_by_criterion, context['task'], context['init_url_context'],
                context['action_history'], context['predicted_output'],
                outcome_result=majority_outcome_result, total_states=len(evidence),
                action_definitions=self.config.action_definitions, step_actions=context['step_actions'],
            )
        intermediate["step9_first_point_of_failure"] = step9_result
        rubric_dict["first_point_of_failure"] = step9_result

    async def _verify_trajectory(
        self, context, rubric_dict, evidence_by_criterion, evidence, intermediate,
        majority_outcome_result,
    ):
        cached_step9b = (
            context["precomputed_rubric"].get("task_verification_with_trajectory")
            if isinstance(context["precomputed_rubric"], dict)
            else None
        )
        if cached_step9b and (not context["redo_eval"]):
            self.logger.info(
                "[Step 9b] Reusing cached trajectory-informed task verification."
            )
            step9b_result = cached_step9b
        else:
            self.logger.info(
                "[Step 9b] Running trajectory-informed task verification..."
            )
            step9b_result = await self._classify_task_with_trajectory(
                rubric_dict, evidence_by_criterion, context['task'], context['init_url_context'],
                context['action_history'], context['predicted_output'],
                outcome_result=majority_outcome_result, total_states=len(evidence),
                apps=context['apps_str'],
            )
        intermediate["step9b_task_verification_with_trajectory"] = step9b_result
        rubric_dict["task_verification_with_trajectory"] = step9b_result

    async def _verify_task(self, context, rubric_dict, intermediate):
        cached_step10 = (
            context["precomputed_rubric"].get("task_verification")
            if isinstance(context["precomputed_rubric"], dict)
            else None
        )
        if cached_step10 and (not context["redo_eval"]):
            self.logger.info("[Step 10] Reusing cached task verification.")
            step10_result = cached_step10
        else:
            self.logger.info("[Step 10] Running task verification...")
            step10_result = await self._classify_task(
                context["task"], context["init_url"], apps=context["apps"]
            )
        intermediate["step10_task_verification"] = step10_result
        rubric_dict["task_verification"] = step10_result

    @staticmethod
    def _evaluation_result(
        rubric_dict, intermediate, step67_results, N, median_idx, score, all_scores, success_votes,
        majority_output_success,
    ):
        all_rubric_dicts = [copy.deepcopy(r[0]) for r in step67_results]
        all_scores_list = [r[1] for r in step67_results]
        rubric_dict["intermediate_mm_rubric_steps"] = copy.deepcopy(intermediate)
        rubric_dict["majority_vote_metadata"] = {
            "n_instances": N,
            "median_instance_idx": median_idx,
            "all_scores": all_scores,
            "median_score": score,
            "outcome_votes": success_votes,
            "majority_output_success": majority_output_success,
        }
        rubric_dict["all_rubric_dicts"] = all_rubric_dicts
        rubric_dict["all_scores_list"] = all_scores_list
        return rubric_dict

    async def _evaluate_evidence(self, context, rubric_dict):
        intermediate = {}
        try:
            evidence, evidence_by_criterion = await self._collect_evidence(
                context, rubric_dict, intermediate
            )
            rubric_dict = await self._conditions_and_reality(
                context, rubric_dict, evidence_by_criterion, intermediate
            )
            (
                rubric_dict,
                step67_results,
                median_idx,
                score,
                N,
            ) = await self._score_instances(
                context, rubric_dict, evidence_by_criterion, evidence, intermediate
            )
            (
                majority_outcome_result,
                success_votes,
                majority_output_success,
            ) = await self._outcome_votes(
                context, rubric_dict, evidence_by_criterion, evidence, intermediate, N
            )
            await self._verify_failure(
                context, rubric_dict, evidence_by_criterion, evidence, intermediate,
                majority_outcome_result,
            )
            await self._verify_trajectory(
                context, rubric_dict, evidence_by_criterion, evidence, intermediate,
                majority_outcome_result,
            )
            await self._verify_task(context, rubric_dict, intermediate)
            return self._evaluation_result(
                rubric_dict, intermediate, step67_results, N, median_idx, score,
                intermediate['majority_vote_steps67']['all_scores'], success_votes,
                majority_output_success,
            )
        except Exception as e:
            if isinstance(e, scoring.UngradedVerifierError):
                raise
            tb_str = traceback.format_exc()
            self.logger.error(f"[MM Pipeline] Pipeline failed: {e}\n{tb_str}")
            raise

    @staticmethod
    def _validate_condition_entry(entry, i, rubric, conditional_indices):
        expected_idx = conditional_indices[i]
        if "criterion_idx" not in entry:
            raise ValueError(f"Entry {i} missing 'criterion_idx'")
        if entry["criterion_idx"] != expected_idx:
            raise ValueError(
                f"Entry {i} has criterion_idx={entry['criterion_idx']}, expected {expected_idx}"
            )
        if "condition" not in entry:
            raise ValueError(f"Entry {i} missing 'condition'")
        expected_condition = rubric["items"][expected_idx]["condition"]
        if entry["condition"] != expected_condition:
            raise ValueError(
                f"Entry {i}: condition text mismatch. Expected verbatim: {expected_condition!r}, got: {entry['condition']!r}"
            )
        if "reasoning" not in entry:
            raise ValueError(f"Entry {i} missing 'reasoning'")
        if not isinstance(entry["reasoning"], str):
            raise ValueError(f"Entry {i}: 'reasoning' must be a string")
        if "is_condition_met" not in entry:
            raise ValueError(f"Entry {i} missing 'is_condition_met'")
        if not isinstance(entry["is_condition_met"], bool):
            raise ValueError(f"Entry {i}: 'is_condition_met' must be a boolean")

    def _condition_messages(
        self, rubric, evidence_by_criterion, task, init_url_context,
    ):
        conditional_indices = [
            i for i, item in enumerate(rubric["items"]) if "condition" in item
        ]
        conditional_criteria_with_evidence = self._conditional_evidence_text(
            rubric, evidence_by_criterion, conditional_indices
        )
        prompt = Template(
            self.prompts.CONDITIONAL_CRITERIA_DISAMBIGUATION_PROMPT
        ).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            num_conditional=len(conditional_indices),
            conditional_criteria_with_evidence=conditional_criteria_with_evidence,
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        return (messages, conditional_indices)

    def _reality_messages(self, rubric, evidence_by_criterion, task, init_url_context):
        criteria_with_evidence = self._reality_evidence_text(
            rubric, evidence_by_criterion
        )
        num_criteria = len(rubric["items"])
        prompt = Template(self.prompts.RUBRIC_REALITY_CHECK_PROMPT).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            num_criteria=num_criteria,
            last_criterion_idx=num_criteria - 1,
            criteria_with_evidence=criteria_with_evidence,
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        return (messages, num_criteria)

    def _rubric_rescore_messages(
        self, rubric, evidence_by_criterion, task, init_url_context, action_history, predicted_output,
        total_states, num_criteria,
    ):
        full_rubric = self._build_full_rubric_with_baselines(rubric)
        all_evidence = self._build_all_evidence_text(
            rubric, evidence_by_criterion, total_states
        )
        prompt = Template(self.prompts.MM_RUBRIC_RESCORING_PROMPT).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            full_rubric_with_baselines=full_rubric,
            **{self.all_evidence_placeholder: all_evidence},
            num_criteria=num_criteria,
            num_criteria_minus_1=num_criteria - 1,
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        return messages

    def _criterion_rescore_messages(
        self, rubric, evidence_by_criterion, c_idx, criterion, task, init_url_context, action_history,
        predicted_output, total_states,
    ):
        concatenated = self._criterion_analyses_text(
            evidence_by_criterion, c_idx, total_states
        )
        full_rubric_context = self._build_full_rubric_context(rubric, c_idx)
        prompt = Template(self.prompts.MM_CRITERION_RESCORING_PROMPT).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            full_rubric_context=full_rubric_context,
            max_points=criterion["max_points"],
            **{self.criterion_evidence_placeholder: concatenated},
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        return messages

    def _validate_penalty(self, penalty, i):
        required_penalty_fields = [
            "criterion",
            "description",
            "max_points",
            self.justification_field,
            self.score_field,
        ]
        missing_fields = [f for f in required_penalty_fields if f not in penalty]
        if missing_fields:
            raise ValueError(
                f"Penalty criterion {i} missing fields: {', '.join(missing_fields)}"
            )
        if not isinstance(penalty["criterion"], str) or not penalty["criterion"]:
            raise ValueError(
                f"Penalty criterion {i}: 'criterion' must be a non-empty string"
            )
        if not isinstance(penalty["description"], str) or not penalty["description"]:
            raise ValueError(
                f"Penalty criterion {i}: 'description' must be a non-empty string"
            )
        scoring.validate_points(penalty[self.score_field], penalty["max_points"], field=self.score_field)
        if penalty[self.score_field] != 0:
            raise ValueError(
                f"Penalty criterion {i}: '{self.score_field}' must be 0 for penalties"
            )
        penalty["earned_points"] = penalty[self.score_field]
        penalty["justification"] = penalty[self.justification_field]

    def _side_effect_messages(
        self, rubric, evidence_by_criterion, task, init_url_context, action_history,
    ):
        all_evidence_text = ""
        for c_idx, analyses in evidence_by_criterion.items():
            criterion = rubric["items"][c_idx]
            all_evidence_text += f"\n\n## Criterion {c_idx}: {criterion['criterion']}\n"
            for analysis in analyses:
                all_evidence_text += (
                    f"- **Evidence:** {analysis.get(self.evidence_field, 'N/A')}\n"
                )
                all_evidence_text += (
                    f"- **Analysis:** {analysis.get('criterion_analysis', 'N/A')}\n"
                )
                all_evidence_text += (
                    f"- **Discrepancies:** {analysis.get('discrepancies', 'N/A')}\n"
                )
        scored_summary = self._build_scored_rubric_summary(rubric)
        prompt = Template(
            self.prompts.PENALIZE_UNSOLICITED_SIDE_EFFECTS_PROMPT
        ).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            scored_rubric_summary=scored_summary,
            all_concatenated_evidence=all_evidence_text,
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        return messages

    def _outcome_messages(
        self, rubric, evidence_by_criterion, task, init_url_context, action_history, predicted_output,
        total_states,
    ):
        rubric_summary = self._build_scored_rubric_summary(rubric)
        evidence_summary = self._build_all_evidence_text(
            rubric, evidence_by_criterion, total_states
        )
        prompt = Template(self.prompts.OUTCOME_VERIFICATION_PROMPT).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            rubric_summary=rubric_summary,
            evidence_summary=evidence_summary,
            action_history=action_history,
            predicted_output=predicted_output or "N/A",
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        return messages

    def _validate_failure_point(self, fp, i):
        required_fields = [
            "step_numbers",
            "error_code",
            "error_category",
            "error_type",
            "what_happened",
            "agent_reasoning",
            "evidence",
            "impact",
        ]
        missing = [f for f in required_fields if f not in fp]
        if missing:
            raise ValueError(
                f"failure_points[{i}] missing fields: {', '.join(missing)}"
            )
        sn = str(fp["step_numbers"]).replace(" ", "")
        if not self._STEP_NUMBERS_RE.match(sn):
            raise ValueError(
                f'failure_points[{i}].step_numbers must be "INT", "INT-INT", or "INT,INT,..." (e.g. "5", "5-7", or "5,8,12"), got "{fp["step_numbers"]}". Never use N/A or descriptive text.'
            )
        fp["step_numbers"] = sn

    @staticmethod
    def _merge_tool_failures(result, step_actions, action_definitions):
        if step_actions is not None and action_definitions:
            prog_fps = scoring.detect_tool_interaction_errors(
                step_actions, action_definitions
            )
            if prog_fps:
                existing = {
                    (fp.get("step_numbers"), fp.get("error_code"))
                    for fp in result["failure_points"]
                }
                for pfp in prog_fps:
                    key = (pfp["step_numbers"], pfp["error_code"])
                    if key not in existing:
                        result["failure_points"].append(pfp)
                result["failure_points"].sort(
                    key=lambda fp: scoring.parse_first_step_number(
                        fp.get("step_numbers", "")
                    )
                )
                if result["failure_points"]:
                    result["has_failure"] = True

    def _failure_messages(
        self, rubric, evidence_by_criterion, task, init_url_context, action_history, predicted_output,
        outcome_result, total_states, action_definitions,
    ):
        rubric_summary = self._build_scored_rubric_summary(rubric)
        evidence_summary = self._build_all_evidence_text(
            rubric, evidence_by_criterion, total_states
        )
        outcome_text = self._outcome_text(outcome_result)
        action_space_str, action_definitions_text = self._action_definitions_text(
            action_definitions
        )
        prompt = Template(self.prompts.FIRST_POINT_OF_FAILURE_PROMPT).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            predicted_output=predicted_output or "N/A",
            rubric_summary=rubric_summary,
            evidence_summary=evidence_summary,
            outcome_verification=outcome_text,
            action_space=action_space_str,
            action_definitions_text=action_definitions_text,
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        return messages

    def _trajectory_messages(
        self, rubric, evidence_by_criterion, task, init_url_context, action_history, predicted_output,
        outcome_result, total_states, apps,
    ):
        from datetime import datetime, timezone

        rubric_summary = self._build_scored_rubric_summary(rubric)
        evidence_summary = self._build_all_evidence_text(
            rubric, evidence_by_criterion, total_states
        )
        outcome_text = self._outcome_text(outcome_result)
        date = self.config.validity_date or datetime.now(timezone.utc).strftime(
            "%Y-%m-%d"
        )
        prompt = Template(
            self.prompts.CHECK_VALID_TASK_WITH_TRAJECTORY_PROMPT
        ).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            apps=apps,
            date=date,
            action_history=action_history,
            predicted_output=predicted_output or "N/A",
            rubric_summary=rubric_summary,
            evidence_summary=evidence_summary,
            outcome_verification=outcome_text,
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        return messages

    def _rubric_result(self, result, total_max, total_earned, rubric_score, mv_raw):
        rubric_vr = MMRubricResult(
            score=rubric_score,
            reasoning=json.dumps(
                {
                    "items": result.get("items", []),
                    "total_max_points": total_max,
                    "total_earned_points": total_earned,
                },
                indent=2,
            ),
            verifier_name="mm_rubric",
            total_max_points=total_max,
            total_earned_points=total_earned,
            rubric_is_success=rubric_score >= self.config.rubric_score_threshold,
            intermediate_mm_rubric_steps=result.get("intermediate_mm_rubric_steps", {}),
            majority_vote_metadata=MajorityVoteMetadata(
                n_instances=mv_raw.get("n_instances", 0),
                median_instance_idx=mv_raw.get("median_instance_idx", 0),
                all_scores=mv_raw.get("all_scores", []),
                median_score=mv_raw.get("median_score", 0.0),
                outcome_votes=mv_raw.get("outcome_votes", []),
                majority_output_success=mv_raw.get("majority_output_success"),
            ),
            all_rubric_dicts=result.get("all_rubric_dicts", []),
            all_scores_list=result.get("all_scores_list", []),
        )
        return rubric_vr

    @staticmethod
    def _outcome_result(outcome_verification, output_success):
        outcome_vr = MMRubricOutcomeResult(
            score=1.0 if output_success else 0.0,
            reasoning=outcome_verification.get("reasoning", ""),
            verifier_name="mm_rubric_outcome",
            output_success=output_success,
            primary_intent=outcome_verification.get("primary_intent", ""),
        )
        return outcome_vr

    def _rescoring_summary_item(self, item):
        return {
            "criterion": item.get("criterion", ""),
            "earned_points": item.get("earned_points"),
            self.score_field: item.get(self.score_field),
            "max_points": item.get("max_points"),
            "justification": item.get("justification", ""),
            "applicable_evidence": item.get("applicable_evidence", ""),
            self.justification_field: item.get(self.justification_field, ""),
            "reality_notes": item.get("reality_notes", ""),
            **({"condition": item["condition"]} if "condition" in item else {}),
            **(
                {"is_condition_met": item["is_condition_met"]}
                if "is_condition_met" in item
                else {}
            ),
        }

    @staticmethod
    def _instance_summary(i, r):
        return {
            "instance_idx": i,
            "score": r[1],
            "total_earned_points": r[0].get("total_earned_points"),
            "total_max_points": r[0].get("total_max_points"),
            "step6_rescoring_summary": r[2].get("step6_rescoring_summary"),
            "step7_requires_penalty": r[2].get("step7_requires_penalty", False),
            "step7_reasoning": r[2].get("step7_reasoning", ""),
            "step7_penalty_criteria": r[2].get("step7_penalty_criteria", []),
        }

    def _failure_only_rubric(self, input):
        precomputed_rubric = input.get("precomputed_rubric")
        if isinstance(precomputed_rubric, list) and len(precomputed_rubric) > 0:
            precomputed_rubric = precomputed_rubric[0]
        if not precomputed_rubric or not isinstance(precomputed_rubric, dict):
            raise ValueError(
                "failure_analysis_only requires a precomputed scored rubric but none was found."
            )
        rubric_dict = precomputed_rubric
        try:
            scoring.verify_rubric(rubric_dict, evidence_mode=self.evidence_mode)
        except Exception as e:
            if isinstance(e, scoring.UngradedVerifierError):
                raise
            raise ValueError(
                f"failure_analysis_only requires a fully scored rubric, but validation failed: {e}"
            ) from e
        return rubric_dict

    @staticmethod
    def _failure_only_intermediate(input, evidence_dir):
        intermediate = input.get("intermediate_mm_rubric_steps")
        if intermediate is None and evidence_dir:
            td_path = Path(evidence_dir) / "task_data.json"
            if td_path.exists():
                with open(td_path, "r", encoding="utf-8") as f:
                    td = json.load(f)
                intermediate = td.get("intermediate_mm_rubric_steps")
        if not intermediate or not isinstance(intermediate, dict):
            raise ValueError(
                "failure_analysis_only requires intermediate_mm_rubric_steps (from a previous full evaluation) but none was found."
            )
        return intermediate

    def _rubric_attempt_receipt(self, stage, attempt, messages):
        if not self.record_generation_trace:
            return None
        receipt = {
            "stage": stage,
            "attempt": attempt,
            "messages": json.loads(json.dumps(messages)),
            "accepted": False,
        }
        self.rubric_generation_trace.append(receipt)
        return receipt

    def _generation_error(self, messages, errors, e, attempt, response_text):
        error_type = type(e).__name__
        response_preview = response_text[:200] + "..." if response_text else "N/A"
        errors.append(f"  Attempt {attempt}: [{error_type}] {e}")
        self.logger.warning(
            f"Rubric generation attempt {attempt}/5 failed: [{error_type}] {e} | Response preview: {response_preview}"
        )
        messages.append(
            {
                "role": "user",
                "content": f"Error: {e}. Please ensure the rubric follows the exact format specified with 'items' list containing objects with 'criterion', 'description', 'max_points', 'justification' (empty string), and 'earned_points' (empty string) fields.",
            }
        )

    def _dependency_error(self, messages, errors, e, attempt, response_text):
        error_type = type(e).__name__
        response_preview = response_text[:200] + "..." if response_text else "N/A"
        errors.append(f"  Attempt {attempt}: [{error_type}] {e}")
        self.logger.warning(
            f"Rubric dependency check attempt {attempt}/5 failed: [{error_type}] {e} | Response preview: {response_preview}"
        )
        messages.append(
            {
                "role": "user",
                "content": f"Error: {e}. Please ensure the output follows the exact format specified with 'reasoning', 'needs_reformulation', and 'reformulated_rubric' fields.",
            }
        )

    @staticmethod
    def _dependency_rubric(result, rubric_dict):
        if result.get("needs_reformulation", False):
            reformulated = result.get("reformulated_rubric", {})
            if reformulated:
                scoring.verify_generated_rubric(reformulated)
                return reformulated
            raise ValueError(
                "needs_reformulation is True but reformulated_rubric is empty"
            )
        return rubric_dict

    @staticmethod
    def _outcome_text(outcome_result):
        outcome_success = outcome_result.get("output_success")
        if outcome_success is True:
            outcome_label = "SUCCESS"
        elif outcome_success is False:
            outcome_label = "FAILURE"
        else:
            outcome_label = "UNKNOWN"
        outcome_text = f"Task outcome: {outcome_label}\nPrimary intent: {outcome_result.get('primary_intent', 'N/A')}\nReasoning: {outcome_result.get('reasoning', 'N/A')}"
        return outcome_text

    @staticmethod
    def _action_definitions_text(action_definitions):
        action_space_str = ", ".join((f"`{a}`" for a in action_definitions))
        action_defs_lines = []
        for act_name in sorted(action_definitions):
            args_str = ", ".join(sorted(action_definitions[act_name]))
            action_defs_lines.append(f"  - `{act_name}({args_str})`")
        action_definitions_text = "\n".join(action_defs_lines)
        action_definitions_text += (
            "\nRecorder annotations ("
            + ", ".join(sorted(scoring.ACTION_METADATA_KEYS))
            + ") may accompany actions in the history. They are not tool parameters; their presence alone is not an invalid invocation."
        )
        return (action_space_str, action_definitions_text)

    def _skipped_criteria(self, rubric):
        skipped = set()
        for c_idx, criterion in enumerate(rubric["items"]):
            if "condition" in criterion and (
                not criterion.get("is_condition_met", False)
            ):
                criterion["applicable_evidence"] = (
                    "N/A — condition not met, criterion skipped."
                )
                criterion[self.justification_field] = (
                    "Condition not met; criterion does not apply and was not rescored."
                )
                criterion[self.score_field] = 0.0
                skipped.add(c_idx)
        return skipped

    async def _rescore_one_criterion(self, messages, criterion, c_idx):
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                await self._criterion_rescore_attempt(messages, criterion)
                break
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self.logger.error(
                    f"Error rescoring criterion {c_idx} (attempt {self.config.max_iters + 1 - max_iters}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {e}. Please ensure your output includes all required fields in the correct format.",
                    }
                )
                max_iters -= 1
        else:
            self.logger.warning(
                f"Failed to rescore criterion {c_idx} after {self.config.max_iters} attempts. Last error: {last_error}"
            )
            raise scoring.UngradedVerifierError(f"criterion_rescore:{c_idx}", str(last_error))

    async def _rescore_instance(
        self, rubric_copy, evidence_by_criterion, evidence, task, init_url_context, action_history,
        predicted_output,
    ):
        if self.config.rescore_whole_mm_rubric:
            rubric_copy = await self._rescore_rubric(
                rubric_copy, evidence_by_criterion, task, init_url_context, action_history,
                predicted_output, total_states=len(evidence),
            )
        else:
            rubric_copy = await self._rescore_criterion(
                rubric_copy, evidence_by_criterion, task, init_url_context, action_history,
                predicted_output, total_states=len(evidence),
            )
        return rubric_copy

    @staticmethod
    def _action_history_step(s, max_url_chars):
        lines = []
        for msg_type, msg_content in s.user_messages_before:
            if msg_type == UserMessageType.CRITICAL_POINT_RESPONSE:
                lines.append(f"[User Response] {msg_content}")
            elif msg_type == UserMessageType.FOLLOWUP_TASK:
                lines.append(f"[Follow-up Task] {msg_content}")
        url_shortened = s.url.split("?")[0].split("#")[0]
        if len(url_shortened) > max_url_chars:
            url_shortened = url_shortened[:max_url_chars] + "..."
        state_str = f"{url_shortened}, state_description: {s.state_description}"
        action_str = f"{s.action_name}({json.dumps(s.action_args, indent=4)})"
        idx = s.index
        entry = f"State {idx}: {state_str}\nAction {idx}: {action_str}"
        if s.previous_error:
            entry += f"\nError! The above Action {idx} encountered an Error: {s.previous_error}"
        lines.append(entry)
        return lines

    @staticmethod
    def _action_history_context(evaluation_context):
        lines = []
        if evaluation_context:
            lines.append(
                "Observed document URL timeline (capture observations, not navigation intent):"
            )
            for observed in evaluation_context.get("observed_url_timeline", []):
                value = (
                    observed.get("url")
                    if observed.get("verified") is True
                    else "unavailable (not verified)"
                )
                lines.append(f"State {observed['state']}: {value}")
            gaps = evaluation_context.get("format_gaps", {})
            if any(gaps.values()):
                lines.append(
                    "Unavailable recorded evidence states: "
                    + json.dumps(gaps, sort_keys=True)
                )
            navigation = evaluation_context.get("navigation_states", [])
            if navigation:
                lines.append(
                    "Navigation occurred within capture intervals at states: "
                    + json.dumps(navigation)
                )
            lines.append("")
        return lines

    def _action_scoring_messages(self, context, rubric_dict):
        prompt = Template(self.prompts.ACTION_ONLY_RUBRIC_SCORER_PROMPT).substitute(
            task_definition=context["task"],
            rubric=rubric_dict,
            action_history=context["action_history"],
            predicted_target=context["predicted_output"],
            init_url_context=context["init_url_context"],
        )
        messages = [{"role": "user", "content": prompt}]
        return messages

    async def _condition_statuses(
        self, context, rubric_dict, evidence_by_criterion, intermediate,
    ):
        conditional_indices = [
            i for i, c in enumerate(rubric_dict["items"]) if "condition" in c
        ]
        if len(conditional_indices) >= 2:
            self.logger.info(
                f"[Step 4.5/9] Disambiguating {len(conditional_indices)} conditional criteria..."
            )
            rubric_dict = await self._disambiguate_conditional_criteria(
                rubric_dict, evidence_by_criterion, context['task'], context['init_url_context'],
            )
            intermediate["step4_5_disambiguation"] = {
                str(i): {
                    "is_condition_met": rubric_dict["items"][i].get("is_condition_met"),
                    "reasoning": rubric_dict["items"][i].get(
                        "condition_disambiguation_reasoning", ""
                    ),
                }
                for i in conditional_indices
            }
        elif len(conditional_indices) == 1:
            c_idx = conditional_indices[0]
            verifications = [
                a["condition_verification"]
                for a in evidence_by_criterion.get(c_idx, [])
                if "condition_verification" in a
            ]
            if verifications:
                rubric_dict["items"][c_idx]["is_condition_met"] = any(verifications)
        return rubric_dict

    def _failure_only_input(self, input):
        task: str = input["task"]
        action_history: str = input["action_history"]
        predicted_output: str = input.get("predicted_output", "")
        evidence_dir: str = input.get(self.evidence_dir_key) or getattr(
            self.config, self.evidence_dir_key
        )
        init_url: str = input.get("init_url", "")
        apps_list: list = input.get("apps", [])
        init_url_context = scoring.get_init_url_context(init_url)
        apps_str = ", ".join(apps_list) if apps_list else "N/A"
        return {
            "task": task,
            "action_history": action_history,
            "predicted_output": predicted_output,
            "evidence_dir": evidence_dir,
            "init_url": init_url,
            "apps_list": apps_list,
            "init_url_context": init_url_context,
            "apps_str": apps_str,
        }

    def _failure_only_evidence(self, input, rubric_dict, intermediate):
        raw_evidence = intermediate.get("step4_evidence_by_criterion", {})
        evidence_by_criterion: dict[int, list[dict]] = {
            int(k): v for k, v in raw_evidence.items()
        }
        outcome_result = intermediate.get(
            "step8_outcome_verification", rubric_dict.get("outcome_verification", {})
        )
        total_states = intermediate.get(self.state_count_key, 0)
        step_actions: list[dict[str, Any]] | None = input.get("step_actions")
        action_definitions = (
            input.get("action_definitions") or self.config.action_definitions
        )
        return (
            evidence_by_criterion,
            outcome_result,
            total_states,
            step_actions,
            action_definitions,
        )

    async def _failure_only_failure(
        self, context, rubric_dict, intermediate, evidence_by_criterion, outcome_result, total_states,
        step_actions, action_definitions,
    ):
        self.logger.info(
            "[failure_analysis_only] Running step 9a (points of failure)..."
        )
        step9_result = await self._first_point_of_failure_analysis(
            rubric_dict, evidence_by_criterion, context['task'], context['init_url_context'],
            context['action_history'], context['predicted_output'], outcome_result=outcome_result,
            total_states=total_states, action_definitions=action_definitions, step_actions=step_actions,
        )
        intermediate["step9_first_point_of_failure"] = step9_result
        rubric_dict["first_point_of_failure"] = step9_result
        return step9_result

    async def _failure_only_trajectory(
        self, context, rubric_dict, intermediate, evidence_by_criterion, outcome_result, total_states,
    ):
        self.logger.info(
            "[failure_analysis_only] Running step 9b (trajectory-informed task verification)..."
        )
        step9b_result = await self._classify_task_with_trajectory(
            rubric_dict, evidence_by_criterion, context['task'], context['init_url_context'],
            context['action_history'], context['predicted_output'], outcome_result=outcome_result,
            total_states=total_states, apps=context['apps_str'],
        )
        intermediate["step9b_task_verification_with_trajectory"] = step9b_result
        rubric_dict["task_verification_with_trajectory"] = step9b_result

    async def _failure_only_task(self, context, rubric_dict, intermediate):
        self.logger.info(
            "[failure_analysis_only] Running step 10 (task verification)..."
        )
        step10_result = await self._classify_task(
            context["task"], context["init_url"], apps=context["apps_list"]
        )
        intermediate["step10_task_verification"] = step10_result
        rubric_dict["task_verification"] = step10_result
        rubric_dict["intermediate_mm_rubric_steps"] = intermediate

    async def _outcome_attempt(self, messages):
        response_text = await self._call_llm(
            messages, self._judge_client, json_output=True
        )
        result = json.loads(response_text)
        if "primary_intent" not in result:
            raise ValueError("Missing required field: primary_intent")
        if (
            not isinstance(result["primary_intent"], str)
            or not result["primary_intent"]
        ):
            raise ValueError("primary_intent must be a non-empty string")
        if "reasoning" not in result:
            raise ValueError("Missing required field: reasoning")
        if not isinstance(result["reasoning"], str) or not result["reasoning"]:
            raise ValueError("reasoning must be a non-empty string")
        if "output_success" not in result:
            raise ValueError("Missing required field: output_success")
        if not isinstance(result["output_success"], bool):
            raise ValueError(
                f"output_success must be a boolean, got {type(result['output_success']).__name__}"
            )
        self.logger.info(
            f"Outcome verification result: output_success={result['output_success']}, primary_intent={result['primary_intent']}"
        )
        return result

    async def _side_effect_attempt(self, messages):
        response_text = await self._call_llm(
            messages, self._judge_client, json_output=True
        )
        result = json.loads(response_text)
        if "reasoning" not in result:
            raise ValueError("Missing required field: reasoning")
        if not isinstance(result["reasoning"], str) or not result["reasoning"]:
            raise ValueError(
                f"reasoning must be a non-empty string, got {type(result['reasoning']).__name__}"
            )
        if "requires_penalty" not in result:
            raise ValueError("Missing required field: requires_penalty")
        if not isinstance(result["requires_penalty"], bool):
            raise ValueError(
                f"requires_penalty must be a boolean, got {type(result['requires_penalty']).__name__}"
            )
        if "penalty_criteria" not in result:
            raise ValueError("Missing required field: penalty_criteria")
        if not isinstance(result["penalty_criteria"], list):
            raise ValueError(
                f"penalty_criteria must be a list, got {type(result['penalty_criteria']).__name__}"
            )
        for i, penalty in enumerate(result["penalty_criteria"]):
            self._validate_penalty(penalty, i)
        if result.get("requires_penalty"):
            for p in result["penalty_criteria"]:
                p["penalty"] = True
            return {
                "reasoning": result["reasoning"],
                "requires_penalty": True,
                "penalty_criteria": result["penalty_criteria"],
            }
        return {
            "reasoning": result["reasoning"],
            "requires_penalty": False,
            "penalty_criteria": [],
        }

    async def _failure_attempt(self, messages, step_actions, action_definitions):
        response_text = await self._call_llm(
            messages, self._judge_client, json_output=True
        )
        result = json.loads(response_text)
        if "reasoning" not in result:
            raise ValueError("Missing required field: reasoning")
        if not isinstance(result["reasoning"], str) or not result["reasoning"]:
            raise ValueError("reasoning must be a non-empty string")
        if "has_failure" not in result:
            raise ValueError("Missing required field: has_failure")
        if not isinstance(result["has_failure"], bool):
            raise ValueError(
                f"has_failure must be a boolean, got {type(result['has_failure']).__name__}"
            )
        if "failure_points" not in result:
            raise ValueError("Missing required field: failure_points")
        if not isinstance(result["failure_points"], list):
            raise ValueError(
                f"failure_points must be a list, got {type(result['failure_points']).__name__}"
            )
        for i, fp in enumerate(result["failure_points"]):
            self._validate_failure_point(fp, i)
        self._merge_tool_failures(result, step_actions, action_definitions)
        first_failure_step, first_failure_summary = self._compute_first_failure(
            result["failure_points"]
        )
        result["first_failure_step"] = first_failure_step
        result["first_failure_summary"] = first_failure_summary
        self.logger.info(
            f"Points of failure result: has_failure={result['has_failure']}, first_failure_step={result['first_failure_step']}, num_failure_points={len(result['failure_points'])}"
        )
        return result

    async def _trajectory_attempt(self, messages):
        response_text = await self._call_llm(
            messages, self._action_client, json_output=True
        )
        result = json.loads(response_text)
        validity._validate_verification_result(result)
        self.logger.info(
            "Step 9b task verification result: is_ambiguous=%s, is_invalid=%s",
            result["is_ambiguous"],
            result["is_invalid"],
        )
        return result

    async def _condition_attempt(self, messages, rubric, conditional_indices):
        response_text = await self._call_llm(
            messages, self._judge_client, json_output=True
        )
        result = json.loads(response_text)
        if "disambiguation" not in result:
            raise ValueError("Missing required field: 'disambiguation'")
        entries = result["disambiguation"]
        if not isinstance(entries, list):
            raise ValueError(
                f"'disambiguation' must be a list, got {type(entries).__name__}"
            )
        if len(entries) != len(conditional_indices):
            raise ValueError(
                f"Expected {len(conditional_indices)} entries, got {len(entries)}"
            )
        for i, entry in enumerate(entries):
            self._validate_condition_entry(entry, i, rubric, conditional_indices)
        for entry in entries:
            idx = entry["criterion_idx"]
            rubric["items"][idx]["is_condition_met"] = entry["is_condition_met"]
            rubric["items"][idx]["condition_disambiguation_reasoning"] = entry[
                "reasoning"
            ]
        return rubric

    async def _reality_attempt(self, messages, rubric, num_criteria):
        response_text = await self._call_llm(
            messages, self._judge_client, json_output=True
        )
        result = json.loads(response_text)
        if "reality_checks" not in result:
            raise ValueError("Missing required field: 'reality_checks'")
        checks = result["reality_checks"]
        if not isinstance(checks, list):
            raise ValueError(
                f"'reality_checks' must be a list, got {type(checks).__name__}"
            )
        if len(checks) != num_criteria:
            raise ValueError(
                f"Expected {num_criteria} reality_checks entries, got {len(checks)}"
            )
        for i, check in enumerate(checks):
            if "criterion_idx" not in check:
                raise ValueError(f"Entry {i} missing 'criterion_idx'")
            if check["criterion_idx"] != i:
                raise ValueError(
                    f"Entry {i} has criterion_idx={check['criterion_idx']}, expected {i}"
                )
            if "reality_notes" not in check:
                raise ValueError(f"Entry {i} missing 'reality_notes'")
            if not isinstance(check["reality_notes"], str):
                raise ValueError(
                    f"Entry {i}: 'reality_notes' must be string, got {type(check['reality_notes']).__name__}"
                )
        for check in checks:
            rubric["items"][check["criterion_idx"]]["reality_notes"] = check[
                "reality_notes"
            ]
        return rubric

    async def _rubric_rescore_attempt(self, messages, rubric, num_criteria, skipped):
        response_text = await self._call_llm(
            messages, self._judge_client, json_output=True
        )
        result = json.loads(response_text)
        if "items" not in result:
            raise ValueError("Missing required field: 'items'")
        items = result["items"]
        if not isinstance(items, list):
            raise ValueError(f"'items' must be a list, got {type(items).__name__}")
        if len(items) != num_criteria:
            raise ValueError(f"Expected {num_criteria} items, got {len(items)}")
        for i, item in enumerate(items):
            if "criterion_idx" not in item:
                raise ValueError(f"Item {i} missing 'criterion_idx'")
            if item["criterion_idx"] != i:
                raise ValueError(
                    f"Item {i} has criterion_idx={item['criterion_idx']}, expected {i}"
                )
            scoring.validate_rescore(
                item,
                rubric["items"][i]["max_points"],
                prefix=f"Item {i}: ",
                evidence_mode=self.evidence_mode,
            )
        for i, item in enumerate(items):
            if i in skipped:
                continue
            rubric["items"][i]["applicable_evidence"] = item["applicable_evidence"]
            rubric["items"][i][self.justification_field] = item[
                self.justification_field
            ]
            rubric["items"][i][self.score_field] = float(item[self.score_field])
        return rubric

    async def _criterion_rescore_attempt(self, messages, criterion):
        response_text = await self._call_llm(
            messages, self._action_client, json_output=True
        )
        rescore = json.loads(response_text)
        scoring.validate_rescore(
            rescore, criterion["max_points"], evidence_mode=self.evidence_mode
        )
        criterion["applicable_evidence"] = rescore["applicable_evidence"]
        criterion[self.justification_field] = rescore[self.justification_field]
        criterion[self.score_field] = float(rescore[self.score_field])
