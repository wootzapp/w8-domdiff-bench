"""Microsoft verifier subclass changing only the four evidence-modality hooks."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from .rubric_agent import MMRubricAgent

from .evidence_backend import base_audit, batched_prompt, criterion_prompt, relevance_prompt
from .grounding import validate_grounded_analysis
from .schemas import DomModelState
from .context_packing import pack_state
from .state_parser import load_dom_model_states


logger = logging.getLogger("dom_model")


class DomModelRubricAgent(MMRubricAgent):
    """Run Microsoft's pipeline unchanged with full DOM-model states as evidence.

    ``_generate_reply`` is deliberately inherited. Only loading, relevance, and
    evidence-analysis hooks are rebound to text evidence.
    """

    evidence_audit: dict[str, Any]

    @staticmethod
    def _normalize_dom_model_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
        """Map the DOM-facing model response onto Microsoft's internal schema."""
        if "dom_model_evidence" not in analysis:
            raise ValueError("Missing required field: dom_model_evidence")
        if "screenshot_evidence" in analysis:
            raise ValueError("Unexpected legacy evidence field; use dom_model_evidence")
        analysis["screenshot_evidence"] = analysis.pop("dom_model_evidence")
        return analysis


    def _load_screenshots(self, screenshots_dir: str, actions_list: list) -> list[DomModelState]:
        action_count = len(actions_list)
        all_states = load_dom_model_states(screenshots_dir, action_count=action_count)
        states = all_states
        if len(states) != action_count + 1:
            raise ValueError(
                "DOM evidence must contain exactly N+1 states for N actions"
            )
        self._dom_action_count = action_count
        self._dom_states_by_index = {state.index: state for state in states}
        self.evidence_audit = base_audit(states)
        self.evidence_audit["state_selection_policy"] = "all_states_0_through_n"
        self.evidence_audit["source_complete_state_count"] = len(all_states)
        self.evidence_audit["excluded_source_states"] = []
        budget = int(getattr(self.config, "dom_model_state_char_budget", 350000))
        packed = [pack_state(state, action_count=action_count, max_chars=budget) for state in states]
        self._dom_rendered_states = {
            state.index: rendered for state, (rendered, _) in zip(states, packed)
        }
        omissions = [item for _, state_omissions in packed for item in state_omissions]
        self.evidence_audit["context_char_budget_per_state"] = budget
        self.evidence_audit["context_omissions"] = omissions
        self.evidence_audit["context_omitted_estimated_tokens"] = sum(
            int(item["estimated_tokens"]) for item in omissions
        )
        self.evidence_audit["coverage_limited"] = bool(omissions) or self.evidence_audit["coverage_limited"]
        self.evidence_audit["warnings"] = [
            {"state_index": state.index, "warning": warning}
            for state in states
            for warning in state.warnings
        ]
        self.evidence_audit["relevance"] = {}
        self.evidence_audit["selection"] = {}
        self.evidence_audit["validation_retries"] = 0
        self.evidence_audit["packed_requests"] = []
        self.evidence_audit["fallback_invocations"] = 0
        return states
    def _record_evidence_request(
        self, *, stage: str, state_index: int, criterion_indices: list[int], messages: list[dict]
    ) -> None:
        serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True, default=str)
        requests = self.evidence_audit["packed_requests"]
        requests.append(
            {
                "request_ordinal": len(requests) + 1,
                "stage": stage,
                "state_index": state_index,
                "criterion_indices": list(criterion_indices),
                "char_count": len(serialized),
                "estimated_input_tokens": (len(serialized) + 3) // 4,
                "context_omission_count": sum(
                    1 for item in self.evidence_audit["context_omissions"]
                    if item["state_index"] == state_index
                ),
            }
        )


    async def _score_screenshot_criterion_relevance(
        self,
        screenshots: list[DomModelState],
        rubric: dict,
        task: str,
        init_url_context: str,
    ) -> dict[int, dict]:
        criteria_text = "".join(
            f"\n{idx}. **{criterion['criterion']}**\n"
            f"   Description: {criterion['description']}\n"
            for idx, criterion in enumerate(rubric["items"])
        )
        criterion_count = len(rubric["items"])
        action_count = getattr(self, "_dom_action_count", max(0, len(screenshots) - 1))

        async def score_state(state: DomModelState) -> dict:
            prompt = relevance_prompt(
                task=task,
                init_url_context=init_url_context,
                criteria_text=criteria_text,
                state=state,
                action_count=action_count,
                rendered_state=self._dom_rendered_states[state.index],
            )
            messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
            remaining = self.config.max_iters
            last_error = None
            while remaining > 0:
                try:
                    self._record_evidence_request(
                        stage="relevance",
                        state_index=state.index,
                        criterion_indices=list(range(criterion_count)),
                        messages=messages,
                    )
                    response_text = await self._call_llm(
                        messages, self._gpt5_client, json_output=True
                    )
                    raw = json.loads(response_text)
                    if not isinstance(raw, dict):
                        raise ValueError("Relevance response must be a JSON object")
                    result: dict[Any, Any] = {}
                    missing: list[str] = []
                    invalid: list[str] = []
                    for criterion_idx in range(criterion_count):
                        found = False
                        for key in (
                            f"criterion_{criterion_idx}",
                            str(criterion_idx),
                            criterion_idx,
                        ):
                            if key not in raw:
                                continue
                            try:
                                score = int(raw[key])
                            except (TypeError, ValueError):
                                invalid.append(f"criterion_{criterion_idx}: not an integer")
                                continue
                            if 0 <= score <= 10:
                                result[criterion_idx] = score
                                found = True
                                break
                            invalid.append(f"criterion_{criterion_idx}: {score} outside [0, 10]")
                        if not found:
                            missing.append(f"criterion_{criterion_idx}")
                    if missing or invalid:
                        raise ValueError(
                            f"Incomplete/invalid relevance scores; missing={missing}, invalid={invalid}"
                        )
                    result["screenshot_idx"] = state.index
                    return result
                except Exception as exc:
                    last_error = str(exc)
                    self.evidence_audit["validation_retries"] += 1
                    logger.error(
                        "Error scoring DOM state %s (attempt %s): %s",
                        state.index,
                        self.config.max_iters + 1 - remaining,
                        exc,
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Error: {exc}. Return scores for ALL {criterion_count} criteria "
                                "using the exact requested JSON format."
                            ),
                        }
                    )
                    remaining -= 1
            logger.warning(
                "Failed relevance for DOM state %s after %s attempts: %s",
                state.index,
                self.config.max_iters,
                last_error,
            )
            self.evidence_audit["fallback_invocations"] += 1
            fallback = {index: 0 for index in range(criterion_count)}
            fallback["screenshot_idx"] = state.index
            return fallback

        results = await asyncio.gather(*(score_state(state) for state in screenshots))
        by_state = {result["screenshot_idx"]: result for result in results}
        self.evidence_audit["relevance"] = {
            str(state_idx): {
                str(key): value for key, value in scores.items() if key != "screenshot_idx"
            }
            for state_idx, scores in by_state.items()
        }
        return by_state

    def _record_selection(
        self, grouped: dict[int, list[int]], relevance_scores: dict[int, dict] | None = None
    ) -> None:
        audited_states = self.evidence_audit.get("states")
        state_indices = (
            [state["index"] for state in audited_states]
            if audited_states is not None
            else sorted((relevance_scores or {}).keys())
        )
        selection: dict[str, Any] = {}
        for criterion_idx, selected in grouped.items():
            selected_set = set(selected)
            selection[str(criterion_idx)] = [
                {
                    "state_index": state_idx,
                    "relevance_score": (
                        relevance_scores.get(state_idx, {}).get(criterion_idx)
                        if relevance_scores is not None
                        else self.evidence_audit.get("relevance", {})
                        .get(str(state_idx), {})
                        .get(str(criterion_idx))
                    ),
                    "selected": state_idx in selected_set,
                    "omission_reason": None if state_idx in selected_set else "outside_top_k_or_filtered",
                }
                for state_idx in state_indices
            ]
        self.evidence_audit["selection"] = selection

    @staticmethod
    def _criterion_info(criterion_idx: int, criterion: dict) -> str:
        return (
            f"**Criterion {criterion_idx}:** {criterion['criterion']}\n"
            f"**Description:** {criterion['description']}\n"
            f"**Max Points:** {criterion['max_points']}"
        )

    @staticmethod
    def _conditional_fields(criterion: dict) -> tuple[str, str, bool]:
        if "condition" not in criterion:
            return "", "", False
        condition = criterion["condition"]
        return (
            "\nAlso verify condition_verification as true only when the state proves "
            f"this condition is met: {condition!r}; otherwise false.",
            ", plus boolean condition_verification",
            True,
        )

    async def _analyze_pair(
        self,
        *,
        criterion_idx: int,
        state_idx: int,
        states: list[DomModelState],
        rubric: dict,
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
    ) -> tuple[int, dict]:
        criterion = rubric["items"][criterion_idx]
        conditional_check, conditional_output, is_conditional = self._conditional_fields(criterion)
        prompt = criterion_prompt(
            task=task,
            init_url_context=init_url_context,
            action_history=action_history,
            predicted_output=predicted_output,
            criterion_info=self._criterion_info(criterion_idx, criterion),
            conditional_check=conditional_check,
            conditional_output=conditional_output,
            state=self._dom_states_by_index[state_idx],
            action_count=getattr(self, "_dom_action_count", len(states) - 1),
            rendered_state=self._dom_rendered_states[state_idx],
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        remaining = self.config.max_iters
        last_error = None
        while remaining > 0:
            try:
                self._record_evidence_request(
                    stage="criterion_analysis",
                    state_index=state_idx,
                    criterion_indices=[criterion_idx],
                    messages=messages,
                )
                response_text = await self._call_llm(
                    messages, self._gpt5_client, json_output=True
                )
                analysis = self._normalize_dom_model_analysis(json.loads(response_text))
                self._validate_evidence_analysis(analysis, is_conditional)
                validate_grounded_analysis(analysis)
                analysis["screenshot_idx"] = state_idx
                analysis["dom_model_state_idx"] = state_idx
                return criterion_idx, analysis
            except Exception as exc:
                last_error = str(exc)
                self.evidence_audit["validation_retries"] += 1
                logger.error(
                    "Error analyzing criterion %s, DOM state %s (attempt %s): %s",
                    criterion_idx,
                    state_idx,
                    self.config.max_iters + 1 - remaining,
                    exc,
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {exc}. Include every required field with the correct type.",
                    }
                )
                remaining -= 1
        logger.warning(
            "Failed criterion %s / DOM state %s after %s attempts: %s",
            criterion_idx,
            state_idx,
            self.config.max_iters,
            last_error,
        )
        self.evidence_audit["fallback_invocations"] += 1
        return criterion_idx, {
            "screenshot_evidence": f"Error: Analysis failed after {self.config.max_iters} attempts",
            "criterion_analysis": "Unable to analyze due to repeated errors",
            "discrepancies": "N/A",
            "environment_issues_confirmed": False,
            "screenshot_idx": state_idx,
            "dom_model_state_idx": state_idx,
        }

    async def _analyze_screenshot_evidence(
        self,
        screenshots: list[DomModelState],
        rubric: dict,
        grouped_screenshots: dict[int, list[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
    ) -> dict[int, list[dict]]:
        self._record_selection(grouped_screenshots)
        tasks = [
            self._analyze_pair(
                criterion_idx=criterion_idx,
                state_idx=state_idx,
                states=screenshots,
                rubric=rubric,
                task=task,
                init_url_context=init_url_context,
                action_history=action_history,
                predicted_output=predicted_output,
            )
            for criterion_idx, state_indices in grouped_screenshots.items()
            for state_idx in state_indices
        ]
        results = await asyncio.gather(*tasks)
        evidence = {index: [] for index in range(len(rubric["items"]))}
        for criterion_idx, analysis in results:
            evidence[criterion_idx].append(analysis)
        return evidence

    async def _analyze_screenshot_evidence_batched(
        self,
        screenshots: list[DomModelState],
        rubric: dict,
        grouped_screenshots: dict[int, list[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
        relevance_scores: dict[int, dict] | None = None,
        min_relevance_threshold: int = 0,
    ) -> dict[int, list[dict]]:
        states_to_criteria = self._invert_grouped_screenshots(grouped_screenshots)
        if min_relevance_threshold > 0 and relevance_scores is not None:
            for state_idx in list(states_to_criteria):
                filtered = [
                    criterion_idx
                    for criterion_idx in states_to_criteria[state_idx]
                    if relevance_scores.get(state_idx, {}).get(criterion_idx, 0)
                    > min_relevance_threshold
                ]
                if filtered:
                    states_to_criteria[state_idx] = filtered
                else:
                    del states_to_criteria[state_idx]
        effective_grouped = {index: [] for index in range(len(rubric["items"]))}
        for state_idx, criteria in states_to_criteria.items():
            for criterion_idx in criteria:
                effective_grouped[criterion_idx].append(state_idx)
        self._record_selection(effective_grouped, relevance_scores)

        async def analyze_state(state_idx: int, criterion_indices: list[int]):
            if len(criterion_indices) == 1:
                return [
                    await self._analyze_pair(
                        criterion_idx=criterion_indices[0],
                        state_idx=state_idx,
                        states=screenshots,
                        rubric=rubric,
                        task=task,
                        init_url_context=init_url_context,
                        action_history=action_history,
                        predicted_output=predicted_output,
                    )
                ]
            conditional = {
                index for index in criterion_indices if "condition" in rubric["items"][index]
            }
            criteria_info = ""
            for criterion_idx in criterion_indices:
                criterion = rubric["items"][criterion_idx]
                criteria_info += "\n" + self._criterion_info(criterion_idx, criterion) + "\n"
                if criterion_idx in conditional:
                    criteria_info += (
                        f"**CONDITIONAL:** include boolean condition_verification for "
                        f"{criterion['condition']!r}.\n"
                    )
            prompt = batched_prompt(
                task=task,
                init_url_context=init_url_context,
                action_history=action_history,
                predicted_output=predicted_output,
                criteria_info=criteria_info,
                state=self._dom_states_by_index[state_idx],
                action_count=getattr(self, "_dom_action_count", len(screenshots) - 1),
                rendered_state=self._dom_rendered_states[state_idx],
            )
            messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
            remaining = self.config.max_iters
            last_error = None
            while remaining > 0:
                try:
                    self._record_evidence_request(
                        stage="batched_analysis",
                        state_index=state_idx,
                        criterion_indices=criterion_indices,
                        messages=messages,
                    )
                    response_text = await self._call_llm(
                        messages, self._gpt5_client, json_output=True
                    )
                    analyses = self._normalize_batched_analysis_response(
                        json.loads(response_text), criterion_indices
                    )
                    if analyses is None or len(analyses) != len(criterion_indices):
                        raise ValueError(
                            f"Expected {len(criterion_indices)} entries, got "
                            f"{len(analyses) if analyses else 'None'}"
                        )
                    results = []
                    for position, (analysis, expected_idx) in enumerate(
                        zip(analyses, criterion_indices)
                    ):
                        if not isinstance(analysis, dict):
                            raise ValueError(f"Entry {position} is not an object")
                        returned_idx = analysis.get("criterion_idx")
                        self._normalize_dom_model_analysis(analysis)
                        if returned_idx is None:
                            analysis["criterion_idx"] = expected_idx
                        elif returned_idx != expected_idx:
                            raise ValueError(
                                f"Entry {position}: expected criterion_idx={expected_idx}, got {returned_idx}"
                            )
                        self._validate_evidence_analysis(analysis, expected_idx in conditional)
                        validate_grounded_analysis(analysis)
                    for analysis, expected_idx in zip(analyses, criterion_indices):
                        analysis.pop("criterion_idx", None)
                        analysis["screenshot_idx"] = state_idx
                        analysis["dom_model_state_idx"] = state_idx
                        results.append((expected_idx, analysis))
                    return results
                except Exception as exc:
                    last_error = str(exc)
                    self.evidence_audit["validation_retries"] += 1
                    logger.error(
                        "Error analyzing DOM state %s criteria %s (attempt %s): %s",
                        state_idx,
                        criterion_indices,
                        self.config.max_iters + 1 - remaining,
                        exc,
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Error: {exc}. Return exactly {len(criterion_indices)} ordered "
                                "analysis entries with every required field."
                            ),
                        }
                    )
                    remaining -= 1
            logger.warning(
                "Batched DOM-state analysis failed for %s after %s attempts; falling back: %s",
                state_idx,
                self.config.max_iters,
                last_error,
            )
            self.evidence_audit["fallback_invocations"] += 1
            return await asyncio.gather(
                *(
                    self._analyze_pair(
                        criterion_idx=criterion_idx,
                        state_idx=state_idx,
                        states=screenshots,
                        rubric=rubric,
                        task=task,
                        init_url_context=init_url_context,
                        action_history=action_history,
                        predicted_output=predicted_output,
                    )
                    for criterion_idx in criterion_indices
                )
            )

        batches = await asyncio.gather(
            *(analyze_state(state_idx, criteria) for state_idx, criteria in states_to_criteria.items())
        )
        evidence = {index: [] for index in range(len(rubric["items"]))}
        for batch in batches:
            for criterion_idx, analysis in batch:
                evidence[criterion_idx].append(analysis)
        return evidence
