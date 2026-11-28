"""DOM evidence prompts, grounding validation, audit records, and scoring hooks."""

from __future__ import annotations
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any
from .rubric_agent import MMRubricAgent
from .. import rubric_scoring as scoring
from .prompts import (
    EVIDENCE_ANALYSIS_GROUNDING_POLICY,
    EVIDENCE_STATUSES,
    GROUNDING_POLICY_VERSION,
    RELEVANCE_GROUNDING_POLICY,
)
from .states import DomModelState, load_dom_model_states, pack_state


_LOGICAL_STAGE_NAMES = {
    "dom_model": {
        "_validate_dom_model_analysis": "w8bench.verifier.dom_model.dom_model_agent._validate_dom_model_analysis",
        "_load_evidence": "w8bench.verifier.dom_model.dom_model_agent._load_dom_states",
        "_record_evidence_request": "w8bench.verifier.dom_model.dom_model_agent._record_evidence_request",
        "_score_evidence_relevance": "w8bench.verifier.dom_model.dom_model_agent._score_dom_state_criterion_relevance",
        "_record_selection": "w8bench.verifier.dom_model.dom_model_agent._record_selection",
        "_criterion_info": "w8bench.verifier.dom_model.dom_model_agent._criterion_info",
        "_conditional_fields": "w8bench.verifier.dom_model.dom_model_agent._conditional_fields",
        "_analyze_pair": "w8bench.verifier.dom_model.dom_model_agent._analyze_pair",
        "_analyze_evidence": "w8bench.verifier.dom_model.dom_model_agent._analyze_dom_evidence",
        "_analyze_evidence_batched": "w8bench.verifier.dom_model.dom_model_agent._analyze_dom_evidence_batched",
        "score_state": "w8bench.verifier.dom_model.dom_model_agent.score_state",
        "analyze_state": "w8bench.verifier.dom_model.dom_model_agent.analyze_state",
    },
}


def validate_grounded_analysis(analysis: dict) -> str:
    """Validate the grounding status and DOM citation."""
    first_line = analysis["criterion_analysis"].splitlines()[0].strip()
    prefix = "EVIDENCE_STATUS: "
    if not first_line.startswith(prefix):
        raise ValueError("criterion_analysis must start with EVIDENCE_STATUS")
    status = first_line.removeprefix(prefix)
    if status not in EVIDENCE_STATUSES:
        raise ValueError(f"Invalid DOM evidence status: {status!r}")
    if "DOM_MODEL_STATE_INDEX" not in analysis["dom_model_evidence"]:
        raise ValueError("DOM-model evidence must cite DOM_MODEL_STATE_INDEX")
    return status


LIMITATIONS = (
    "DOM-model evidence cannot prove pixel-only color, styling, geometry, overlap, clipping, "
    "z-order, or unrepresented non-text media or pixel-only content. Treat absent content as unproven, "
    "not false; source-declared truncation further limits coverage."
)


def relevance_prompt(
    *,
    task: str,
    init_url_context: str,
    criteria_text: str,
    state: DomModelState,
    action_count: int,
    rendered_state: str | None = None,
) -> str:
    return f"""Evaluate how relevant this complete DOM-model browser state is to every rubric criterion.

Task:
{task}{init_url_context}

Rubric criteria:
{criteria_text}

Evidence rules:
- Score every criterion from 0 (irrelevant) through 10 (directly decisive).
- Return one JSON key criterion_0, criterion_1, and so on, with integer values only.
- This is a full ordered state, not a DOM diff.
- {LIMITATIONS}

{RELEVANCE_GROUNDING_POLICY}

DOM-model evidence:
{rendered_state if rendered_state is not None else state.model_text(action_count=action_count)}
"""


def criterion_prompt(
    *,
    task: str,
    init_url_context: str,
    action_history: str,
    predicted_output: str,
    criterion_info: str,
    conditional_check: str,
    conditional_output: str,
    state: DomModelState,
    action_count: int,
    rendered_state: str | None = None,
) -> str:
    return f"""Analyze the DOM-model state as evidence for exactly one rubric criterion.

Task: {task}{init_url_context}
Action history:
{action_history}
Agent predicted output:
{predicted_output}

{criterion_info}

Return JSON with nonempty string fields dom_model_evidence, criterion_analysis, discrepancies;
and a boolean environment_issues_confirmed{conditional_output}.{conditional_check}
{LIMITATIONS}

{EVIDENCE_ANALYSIS_GROUNDING_POLICY}

DOM-model evidence:
{rendered_state if rendered_state is not None else state.model_text(action_count=action_count)}
"""


def batched_prompt(
    *,
    task: str,
    init_url_context: str,
    action_history: str,
    predicted_output: str,
    criteria_info: str,
    state: DomModelState,
    action_count: int,
    rendered_state: str | None = None,
) -> str:
    return f"""Analyze one DOM-model state against the listed rubric criteria in order.

Task: {task}{init_url_context}
Action history:
{action_history}
Agent predicted output:
{predicted_output}

Criteria:
{criteria_info}

Return JSON {{"analyses": [...]}} with exactly one ordered entry per criterion. Each entry must
contain criterion_idx, nonempty string fields dom_model_evidence, criterion_analysis, discrepancies,
and boolean environment_issues_confirmed. Conditional criteria also require boolean
condition_verification.
{LIMITATIONS}

{EVIDENCE_ANALYSIS_GROUNDING_POLICY}

DOM-model evidence:
{rendered_state if rendered_state is not None else state.model_text(action_count=action_count)}
"""


def base_audit(states: list[DomModelState]) -> dict[str, Any]:
    return {
        "evidence_mode": "dom_model",
        "grounding_policy_version": GROUNDING_POLICY_VERSION,
        "complete_state_count": len(states),
        "final_state_index": states[-1].index if states else None,
        "states": [state.audit_dict() for state in states],
        "estimated_evidence_tokens": sum(state.estimated_tokens for state in states),
        "context_omissions": [],
        "coverage_limited": any(state.source_truncated for state in states),
        "limitations": [LIMITATIONS],
    }


logger = logging.getLogger("dom_model")


class DomModelRubricAgent(MMRubricAgent):
    """Score complete DOM states through the shared rubric engine."""

    evidence_audit: dict[str, Any]

    @staticmethod
    def _validate_dom_model_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
        """Validate the DOM-native evidence response schema."""
        if "dom_model_evidence" not in analysis:
            raise ValueError("Missing required field: dom_model_evidence")
        return analysis

    @staticmethod
    def _criterion_info(criterion_idx: int, criterion: dict) -> str:
        return f"**Criterion {criterion_idx}:** {criterion['criterion']}\n**Description:** {criterion['description']}\n**Max Points:** {criterion['max_points']}"

    @staticmethod
    def _conditional_fields(criterion: dict) -> tuple[str, str, bool]:
        if "condition" not in criterion:
            return ("", "", False)
        condition = criterion["condition"]
        return (
            f"\nAlso verify condition_verification as true only when the state proves this condition is met: {condition!r}; otherwise false.",
            ", plus boolean condition_verification",
            True,
        )

    def _load_evidence(
        self, evidence_dir: str, actions_list: list
    ) -> list[DomModelState]:
        action_count = len(actions_list)
        all_states = load_dom_model_states(evidence_dir, action_count=action_count)
        states = all_states
        task = (
            json.loads(
                (Path(evidence_dir) / "task_data.json").read_text(encoding="utf-8")
            )
            if (Path(evidence_dir) / "task_data.json").is_file()
            else {}
        )
        task = task[0] if isinstance(task, list) else task
        context = task.get("evaluation_context") or {}
        if not context and len(states) != action_count + 1:
            raise ValueError(
                "DOM evidence must contain exactly N+1 states for N actions"
            )
        self._dom_action_count = action_count
        self._dom_states_by_index = {state.index: state for state in states}
        self._initialize_state_audit(states, all_states, context)
        budget = int(getattr(self.config, "dom_model_state_char_budget", 350000))
        packed = [
            pack_state(
                state,
                action_count=action_count,
                max_chars=budget,
                initial_state_index=context["expected_state_ids"][0] if context else 0,
            )
            for state in states
        ]
        self._record_context_packing(states, packed, budget)
        return states

    def _initialize_state_audit(self, states, all_states, context) -> None:
        self.evidence_audit = base_audit(states)
        self.evidence_audit["citation_checks"] = {
            "schema_version": "dom-citation-checks/v1",
            "checked_citations": 0, "valid_citations": 0, "invalid_citations": 0,
            "invalid_citation_rate": None, "quote_checked_citations": 0,
            "quote_unavailable_citations": 0, "checks": [],
        }
        self.evidence_audit["state_selection_policy"] = (
            "all_available_original_states" if context else "all_states_0_through_n"
        )
        if context:
            self.evidence_audit["missing_source_states"] = context.get(
                "format_gaps", {}
            ).get("dom_model", [])
            self.evidence_audit["navigation_states"] = context.get(
                "navigation_states", []
            )
        self.evidence_audit["source_complete_state_count"] = len(all_states)
        self.evidence_audit["excluded_source_states"] = []

    def _record_context_packing(self, states, packed, budget: int) -> None:
        self._dom_rendered_states = {
            state.index: rendered for state, (rendered, _) in zip(states, packed)
        }
        omissions = [item for _, state_omissions in packed for item in state_omissions]
        self.evidence_audit["context_char_budget_per_state"] = budget
        self.evidence_audit["context_omissions"] = omissions
        self.evidence_audit["context_omitted_estimated_tokens"] = sum(
            int(item["estimated_tokens"]) for item in omissions
        )
        self.evidence_audit["coverage_limited"] = (
            bool(omissions) or self.evidence_audit["coverage_limited"]
        )
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

    def _record_evidence_request(
        self,
        *,
        stage: str,
        state_index: int,
        criterion_indices: list[int],
        messages: list[dict],
    ) -> None:
        serialized = json.dumps(
            messages, ensure_ascii=False, sort_keys=True, default=str
        )
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
                    1
                    for item in self.evidence_audit["context_omissions"]
                    if item["state_index"] == state_index
                ),
            }
        )

    async def _score_evidence_relevance(
        self,
        dom_states: list[DomModelState],
        rubric: dict,
        task: str,
        init_url_context: str,
    ) -> dict[int, dict]:
        criteria_text = "".join(
            f"\n{idx}. **{criterion['criterion']}**\n   Description: {criterion['description']}\n"
            for idx, criterion in enumerate(rubric["items"])
        )
        criterion_count = len(rubric["items"])
        action_count = getattr(self, "_dom_action_count", max(0, len(dom_states) - 1))
        results = await asyncio.gather(
            *(
                self.score_state(
                    state,
                    task,
                    init_url_context,
                    criteria_text,
                    criterion_count,
                    action_count,
                )
                for state in dom_states
            )
        )
        by_state = {result["dom_model_state_idx"]: result for result in results}
        self.evidence_audit["relevance"] = {
            str(state_idx): {
                str(key): value
                for key, value in scores.items()
                if key != "dom_model_state_idx"
            }
            for state_idx, scores in by_state.items()
        }
        return by_state

    async def score_state(
        self,
        state: DomModelState,
        task: str,
        init_url_context: str,
        criteria_text: str,
        criterion_count: int,
        action_count: int,
    ) -> dict:
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
                    messages, self._judge_client, json_output=True
                )
                result = self._parse_relevance_scores(
                    json.loads(response_text), criterion_count
                )
                result["dom_model_state_idx"] = state.index
                return result
            except Exception as exc:
                if isinstance(exc, scoring.UngradedVerifierError):
                    raise
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
                        "content": f"Error: {exc}. Return scores for ALL {criterion_count} criteria using the exact requested JSON format.",
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
        fallback["dom_model_state_idx"] = state.index
        return fallback

    @staticmethod
    def _parse_relevance_scores(raw, criterion_count: int) -> dict:
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
        return result

    def _record_selection(
        self,
        grouped: dict[int, list[int]],
        relevance_scores: dict[int, dict] | None = None,
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
            entries = []
            for state_idx in state_indices:
                entries.append(
                    {
                        "state_index": state_idx,
                        "relevance_score": relevance_scores.get(state_idx, {}).get(
                            criterion_idx
                        )
                        if relevance_scores is not None
                        else self.evidence_audit.get("relevance", {})
                        .get(str(state_idx), {})
                        .get(str(criterion_idx)),
                        "selected": state_idx in selected_set,
                        "omission_reason": None
                        if state_idx in selected_set
                        else "outside_top_k_or_filtered",
                    }
                )
            selection[str(criterion_idx)] = entries
        self.evidence_audit["selection"] = selection

    def _pair_messages(
        self,
        criterion_idx,
        state_idx,
        states,
        rubric,
        task,
        init_url_context,
        action_history,
        predicted_output,
    ) -> tuple[list[dict], bool]:
        criterion = rubric["items"][criterion_idx]
        conditional_check, conditional_output, is_conditional = (
            self._conditional_fields(criterion)
        )
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
        return self.DEFAULT_SYSTEM_MESSAGES + [
            {"role": "user", "content": prompt}
        ], is_conditional

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
        messages, is_conditional = self._pair_messages(
            criterion_idx,
            state_idx,
            states,
            rubric,
            task,
            init_url_context,
            action_history,
            predicted_output,
        )
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
                    messages, self._judge_client, json_output=True
                )
                analysis = self._parse_pair_analysis(
                    response_text, is_conditional, state_idx
                )
                return criterion_idx, analysis
            except Exception as exc:
                if isinstance(exc, scoring.UngradedVerifierError):
                    raise
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
                        "content": (
                            f"Error: {exc}. Include every required field with the correct type. "
                            "The first line of criterion_analysis must be exactly EVIDENCE_STATUS: "
                            "SUPPORTED, PARTIAL, CONTRADICTED, or UNKNOWN, with explanation on the next "
                            "line encoded as \\n in JSON. Cite the actual DOM_MODEL_STATE_INDEX in "
                            "dom_model_evidence. Required strings must be nonempty; use 'None.' for "
                            "discrepancies only when no mismatch was found."
                        ),
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
        return criterion_idx, self._pair_fallback(state_idx)

    def _parse_pair_analysis(
        self, response_text: str, is_conditional: bool, state_idx: int
    ) -> dict:
        analysis = self._validate_dom_model_analysis(json.loads(response_text))
        scoring.validate_evidence_analysis(
            analysis, is_conditional, evidence_mode="dom_model"
        )
        validate_grounded_analysis(analysis)
        analysis["dom_model_state_idx"] = state_idx
        self._record_citation_checks(analysis, state_idx, "pair_analysis")
        return analysis

    def _record_citation_checks(self, analysis: dict, state_idx: int, stage: str) -> None:
        """Record citation diagnostics without changing accepted evidence or scores."""
        if not hasattr(self, "evidence_audit") or "citation_checks" not in self.evidence_audit:
            return
        diagnostic = self.evidence_audit["citation_checks"]
        citation = analysis["dom_model_evidence"]
        markers = list(re.finditer(r"DOM_MODEL_STATE_INDEX\s*[:=]\s*(-?[0-9]+\b(?![\w.+-]))?", citation))
        for position, marker in enumerate(markers or [None]):
            identifier = marker.group(1) if marker is not None else None
            quote_scope = citation
            if len(markers) > 1:
                end = markers[position + 1].start() if position + 1 < len(markers) else len(citation)
                quote_scope = citation[marker.end():end]
            quotes = [match[0] or match[1] for match in re.findall(r'"([^"\n]+)"|`([^`\n]+)`', quote_scope)]
            try:
                cited_idx = int(identifier) if identifier is not None else None
            except (ValueError, OverflowError):
                cited_idx = None
            errors = []
            state = getattr(self, "_dom_states_by_index", {}).get(cited_idx)
            if cited_idx is None:
                errors.append("Missing or malformed DOM_MODEL_STATE_INDEX")
            elif state is None:
                errors.append("Cited state is absent from the supplied DOM evidence")
            supplied = getattr(self, "_dom_rendered_states", {}).get(cited_idx, "")
            quote_checks = [{"quote": quote,
                "valid": bool(state is not None and quote in state.raw_text),
                "supplied_text_match": quote in supplied} for quote in quotes]
            if any(not item["valid"] for item in quote_checks):
                errors.append("Quoted text is absent from the recorded state")
            valid = not errors
            diagnostic["checks"].append({
                "stage": stage, "analyzed_state_id": state_idx, "cited_state_id": cited_idx,
                "matches_analyzed_state": cited_idx == state_idx,
                "citation": citation, "valid": valid, "errors": errors,
                "quote_status": "checked" if quotes else "unavailable", "quote_checks": quote_checks,
            })
            diagnostic["checked_citations"] += 1
            diagnostic["valid_citations" if valid else "invalid_citations"] += 1
            diagnostic["quote_checked_citations" if quotes else "quote_unavailable_citations"] += 1
        diagnostic["invalid_citation_rate"] = diagnostic["invalid_citations"] / diagnostic["checked_citations"]

    def _pair_fallback(self, state_idx: int) -> dict:
        return {
            "dom_model_evidence": f"Error: Analysis failed after {self.config.max_iters} attempts",
            "criterion_analysis": "Unable to analyze due to repeated errors",
            "discrepancies": "N/A",
            "environment_issues_confirmed": False,
            "dom_model_state_idx": state_idx,
        }

    async def _analyze_evidence(
        self,
        dom_states: list[DomModelState],
        rubric: dict,
        grouped_dom_states: dict[int, list[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
    ) -> dict[int, list[dict]]:
        self._record_selection(grouped_dom_states)
        tasks = [
            self._analyze_pair(
                criterion_idx=criterion_idx,
                state_idx=state_idx,
                states=dom_states,
                rubric=rubric,
                task=task,
                init_url_context=init_url_context,
                action_history=action_history,
                predicted_output=predicted_output,
            )
            for criterion_idx, state_indices in grouped_dom_states.items()
            for state_idx in state_indices
        ]
        results = await asyncio.gather(*tasks)
        evidence = {index: [] for index in range(len(rubric["items"]))}
        for criterion_idx, analysis in results:
            evidence[criterion_idx].append(analysis)
        return evidence

    async def _analyze_evidence_batched(
        self,
        dom_states: list[DomModelState],
        rubric: dict,
        grouped_dom_states: dict[int, list[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
        relevance_scores: dict[int, dict] | None = None,
        min_relevance_threshold: int = 0,
    ) -> dict[int, list[dict]]:
        states_to_criteria = self._batch_criteria(
            grouped_dom_states, relevance_scores, min_relevance_threshold
        )
        effective_grouped = {index: [] for index in range(len(rubric["items"]))}
        for state_idx, criteria in states_to_criteria.items():
            for criterion_idx in criteria:
                effective_grouped[criterion_idx].append(state_idx)
        self._record_selection(effective_grouped, relevance_scores)
        batches = await asyncio.gather(
            *(
                self.analyze_state(
                    state_idx,
                    criteria,
                    dom_states,
                    rubric,
                    task,
                    init_url_context,
                    action_history,
                    predicted_output,
                )
                for state_idx, criteria in states_to_criteria.items()
            )
        )
        evidence = {index: [] for index in range(len(rubric["items"]))}
        for batch in batches:
            for criterion_idx, analysis in batch:
                evidence[criterion_idx].append(analysis)
        return evidence

    def _batch_criteria(self, grouped, relevance_scores, min_relevance_threshold):
        states_to_criteria = self._invert_grouped_evidence(grouped)
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
        return states_to_criteria

    def _batch_messages(
        self,
        state_idx,
        criterion_indices,
        dom_states,
        rubric,
        task,
        init_url_context,
        action_history,
        predicted_output,
    ):
        conditional = {
            index
            for index in criterion_indices
            if "condition" in rubric["items"][index]
        }
        criteria_info = ""
        for criterion_idx in criterion_indices:
            criterion = rubric["items"][criterion_idx]
            criteria_info += (
                "\n" + self._criterion_info(criterion_idx, criterion) + "\n"
            )
            if criterion_idx in conditional:
                criteria_info += f"**CONDITIONAL:** include boolean condition_verification for {criterion['condition']!r}.\n"
        prompt = batched_prompt(
            task=task,
            init_url_context=init_url_context,
            action_history=action_history,
            predicted_output=predicted_output,
            criteria_info=criteria_info,
            state=self._dom_states_by_index[state_idx],
            action_count=getattr(self, "_dom_action_count", len(dom_states) - 1),
            rendered_state=self._dom_rendered_states[state_idx],
        )
        return self.DEFAULT_SYSTEM_MESSAGES + [
            {"role": "user", "content": prompt}
        ], conditional

    async def analyze_state(
        self,
        state_idx: int,
        criterion_indices: list[int],
        dom_states,
        rubric,
        task,
        init_url_context,
        action_history,
        predicted_output,
    ):
        if len(criterion_indices) == 1:
            return [
                await self._analyze_pair(
                    criterion_idx=criterion_indices[0],
                    state_idx=state_idx,
                    states=dom_states,
                    rubric=rubric,
                    task=task,
                    init_url_context=init_url_context,
                    action_history=action_history,
                    predicted_output=predicted_output,
                )
            ]
        messages, conditional = self._batch_messages(
            state_idx,
            criterion_indices,
            dom_states,
            rubric,
            task,
            init_url_context,
            action_history,
            predicted_output,
        )
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
                    messages, self._judge_client, json_output=True
                )
                return self._parse_batch_analysis(
                    response_text, criterion_indices, conditional, state_idx
                )
            except Exception as exc:
                if isinstance(exc, scoring.UngradedVerifierError):
                    raise
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
                            f"Error: {exc}. Return exactly {len(criterion_indices)} ordered entries "
                            f"for criterion indices {criterion_indices}. The first line of each "
                            "criterion_analysis must be exactly EVIDENCE_STATUS: SUPPORTED, PARTIAL, "
                            "CONTRADICTED, or UNKNOWN; put explanation on the next line encoded as \\n "
                            "in JSON. Cite the actual DOM_MODEL_STATE_INDEX in dom_model_evidence. "
                            "All required strings must be nonempty; use 'None.' for discrepancies "
                            "only when no mismatch was found. Include boolean environment_issues_confirmed "
                            "and condition_verification for conditional criteria."
                        ),
                    }
                )
                remaining -= 1
        return await self._batch_fallback(
            state_idx,
            criterion_indices,
            dom_states,
            rubric,
            task,
            init_url_context,
            action_history,
            predicted_output,
            last_error,
        )

    def _parse_batch_analysis(
        self, response_text, criterion_indices, conditional, state_idx
    ):
        analyses = scoring.normalize_batched_analysis_response(
            json.loads(response_text), criterion_indices, evidence_mode="dom_model"
        )
        if analyses is None or len(analyses) != len(criterion_indices):
            raise ValueError(
                f"Expected {len(criterion_indices)} entries, got {(len(analyses) if analyses else 'None')}"
            )
        results = []
        for position, (analysis, expected_idx) in enumerate(
            zip(analyses, criterion_indices)
        ):
            if not isinstance(analysis, dict):
                raise ValueError(f"Entry {position} is not an object")
            returned_idx = analysis.get("criterion_idx")
            self._validate_dom_model_analysis(analysis)
            if returned_idx is None:
                analysis["criterion_idx"] = expected_idx
            elif returned_idx != expected_idx:
                raise ValueError(
                    f"Entry {position}: expected criterion_idx={expected_idx}, got {returned_idx}"
                )
            scoring.validate_evidence_analysis(
                analysis, expected_idx in conditional, evidence_mode="dom_model"
            )
            validate_grounded_analysis(analysis)
        for analysis, expected_idx in zip(analyses, criterion_indices):
            analysis.pop("criterion_idx", None)
            analysis["dom_model_state_idx"] = state_idx
            self._record_citation_checks(analysis, state_idx, "batch_analysis")
            results.append((expected_idx, analysis))
        return results

    async def _batch_fallback(
        self,
        state_idx,
        criterion_indices,
        dom_states,
        rubric,
        task,
        init_url_context,
        action_history,
        predicted_output,
        last_error,
    ):
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
                    states=dom_states,
                    rubric=rubric,
                    task=task,
                    init_url_context=init_url_context,
                    action_history=action_history,
                    predicted_output=predicted_output,
                )
                for criterion_idx in criterion_indices
            )
        )
