"""Mode-specific evidence and rubric configuration."""

from __future__ import annotations
import asyncio
import io
import json
import logging
import re
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Set, Tuple
from PIL import Image
from pydantic import ConfigDict, model_validator
from ..models import (
    AgentConfig,
    MMRubricResult,
    MMRubricOutcomeResult,
    MajorityVoteMetadata,
    UserMessageType,
    VerificationResult,
)
from ..rubric_agent import RubricAgent, resolve_tools, tools_to_action_definitions
from .. import rubric_scoring as scoring
from . import prompts


class MMRubricAgentConfig(AgentConfig):
    """Configuration for the multimodal rubric verification agent."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    name: str = "mm_rubric_agent"
    action_client: Any = None
    judge_client: Any = None
    action_client_config: Optional[Dict[str, Any]] = None
    judge_client_config: Optional[Dict[str, Any]] = None
    max_states_per_criterion: int = 5
    evidence_dir: Optional[str] = None
    rescore_whole_mm_rubric: bool = True
    batch_dom_analysis: bool = True
    min_relevance_threshold: int = 0
    ignore_irrelevant_dom_states: bool = True
    majority_vote_instances: int = 1
    redo_eval: bool = False
    failure_analysis_only: bool = False
    rubric_score_threshold: float = 0.8
    max_iters: int = 5
    validity_date: Optional[str] = None
    tools: Optional[List[str]] = None
    action_definitions: Optional[Dict[str, Set[str]]] = None

    @model_validator(mode="after")
    def _set_action_definitions_from_tools(self) -> "MMRubricAgentConfig":
        if self.action_definitions is None and self.tools is not None:
            self.action_definitions = tools_to_action_definitions(
                resolve_tools(self.tools)
            )
        return self


_LOGICAL_STAGE_NAMES = {"dom_model": {}}
_LOGICAL_STAGE_EXCLUDES = (
    "_action_records",
    "_conditional_evidence_text",
    "_reality_evidence_text",
    "_criterion_analyses_text",
)


class MMRubricAgent(RubricAgent):
    config_type = MMRubricAgentConfig
    logger = logging.getLogger(__name__)
    prompts = prompts
    task_verification_logger = logging.getLogger(__package__ + ".utils.validity")
    evidence_mode = "dom_model"
    score_field = "post_dom_earned_points"
    justification_field = "post_dom_justification"
    evidence_field = "dom_model_evidence"
    state_index_field = "dom_model_state_idx"
    evidence_dir_key = "evidence_dir"
    evidence_limit_key = "max_states_per_criterion"
    batch_config_key = "batch_dom_analysis"
    filter_config_key = "ignore_irrelevant_dom_states"
    state_count_key = "step1_num_dom_states"
    grouped_states_key = "step3_grouped_dom_states"
    record_generation_trace = False
    criterion_evidence_placeholder = "concatenated_dom_model_analyses"
    all_evidence_placeholder = "all_dom_model_evidence"
    loading_evidence_log = "[Step 1/9] Loading dom_states..."
    grouping_evidence_log = "[Step 3/9] Grouping dom_states..."
    analyzing_evidence_log = "[Step 4/9] Analyzing DOM-model evidence..."
    missing_evidence_message = "evidence_dir is required for rubric evaluation."
    evidence_count_suffix = " dom_states"
    relevance_count_suffix = " dom_states)..."
    relevance_error_prefix = "DOM state "
    index_error_prefix = "dom_model_state_idx mismatch: dict key is "
    relevance_key_prefix = "dom_state_"
    filtered_pairs_suffix = " irrelevant (criterion, DOM state) pairs before step 4"
    final_score_prefix = "Final Score (post-DOM): "
    DEFAULT_SYSTEM_MESSAGES = [
        {"role": "system", "content": "You are a helpful AI assistant."}
    ]

    @staticmethod
    def _action_records(summaries):
        return [{"id": s.index} for s in summaries]

    @staticmethod
    def _load_evidence(evidence_dir: str, actions_list: list) -> list:
        raise NotImplementedError(
            "DOM evidence loader must be implemented by the evidence agent"
        )

    async def _score_evidence_relevance(
        self, dom_states: list, rubric: dict, task: str, init_url_context: str
    ) -> Dict[int, Dict]:
        raise NotImplementedError(
            "DOM relevance scoring must be implemented by the evidence agent"
        )

    async def _analyze_evidence(
        self,
        dom_states: list,
        rubric: dict,
        grouped_dom_states: Dict[int, List[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
    ) -> Dict[int, List[Dict]]:
        raise NotImplementedError(
            "DOM evidence analysis must be implemented by the evidence agent"
        )

    async def _analyze_evidence_batched(
        self,
        dom_states: list,
        rubric: dict,
        grouped_dom_states: Dict[int, List[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
        relevance_scores: Dict[int, Dict] | None = None,
        min_relevance_threshold: int = 0,
    ) -> Dict[int, List[Dict]]:
        raise NotImplementedError(
            "Batched DOM evidence analysis must be implemented by the evidence agent"
        )

    @staticmethod
    def _conditional_evidence_text(rubric, evidence_by_criterion, conditional_indices):
        conditional_criteria_with_evidence = ""
        for c_idx in conditional_indices:
            criterion = rubric["items"][c_idx]
            conditional_criteria_with_evidence += (
                f"\n## Criterion {c_idx}: {criterion['criterion']}\n"
            )
            conditional_criteria_with_evidence += (
                f"**Condition:** {criterion['condition']}\n"
            )
            conditional_criteria_with_evidence += (
                f"**Description:** {criterion['description']}\n"
            )
            conditional_criteria_with_evidence += (
                f"**Max Points:** {criterion['max_points']}\n"
            )
            for analysis in sorted(
                evidence_by_criterion.get(c_idx, []),
                key=lambda x: x.get("dom_model_state_idx", 0),
            ):
                sn = analysis.get("dom_model_state_idx", 0)
                conditional_criteria_with_evidence += (
                    f"\n### DOM-model state {sn} evidence:\n"
                )
                conditional_criteria_with_evidence += (
                    f"- Evidence: {analysis.get('dom_model_evidence', 'N/A')}\n"
                )
                conditional_criteria_with_evidence += (
                    f"- Analysis: {analysis.get('criterion_analysis', 'N/A')}\n"
                )
                conditional_criteria_with_evidence += (
                    f"- Discrepancies: {analysis.get('discrepancies', 'N/A')}\n"
                )
                if "condition_verification" in analysis:
                    conditional_criteria_with_evidence += f"- Per-DOM-state condition verification: {analysis['condition_verification']}\n"
        return conditional_criteria_with_evidence

    @staticmethod
    def _reality_evidence_text(rubric, evidence_by_criterion):
        criteria_with_evidence = ""
        for c_idx, criterion in enumerate(rubric["items"]):
            criteria_with_evidence += (
                f"\n## Criterion {c_idx}: {criterion['criterion']}\n"
            )
            criteria_with_evidence += f"**Description:** {criterion['description']}\n"
            criteria_with_evidence += f"**Max Points:** {criterion['max_points']}\n"
            for analysis in sorted(
                evidence_by_criterion.get(c_idx, []),
                key=lambda x: x.get("dom_model_state_idx", 0),
            ):
                sn = analysis.get("dom_model_state_idx", 0)
                criteria_with_evidence += f"\n### DOM-model state {sn} evidence:\n"
                criteria_with_evidence += (
                    f"- Evidence: {analysis.get('dom_model_evidence', 'N/A')}\n"
                )
                criteria_with_evidence += (
                    f"- Analysis: {analysis.get('criterion_analysis', 'N/A')}\n"
                )
                criteria_with_evidence += (
                    f"- Discrepancies: {analysis.get('discrepancies', 'N/A')}\n"
                )
            if not evidence_by_criterion.get(c_idx):
                criteria_with_evidence += "\nNo DOM-model evidence available.\n"
        return criteria_with_evidence

    @staticmethod
    def _criterion_analyses_text(evidence_by_criterion, c_idx, total_states):
        analyses = sorted(
            evidence_by_criterion.get(c_idx, []),
            key=lambda x: x.get("dom_model_state_idx", 0),
        )
        concatenated = ""
        for i_a, analysis in enumerate(analyses):
            sn = analysis.get("dom_model_state_idx", i_a)
            concatenated += f"\n### DOM-model state {sn} analysis:\n"
            concatenated += (
                f"**Evidence:** {analysis.get('dom_model_evidence', 'N/A')}\n"
            )
            concatenated += (
                f"**Analysis:** {analysis.get('criterion_analysis', 'N/A')}\n"
            )
            concatenated += (
                f"**Discrepancies:** {analysis.get('discrepancies', 'N/A')}\n"
            )
            concatenated += f"**Environment Issues Confirmed:** {analysis.get('environment_issues_confirmed', False)}\n"
        if not concatenated:
            concatenated = "No DOM-model evidence available for this criterion."
        return concatenated

    @staticmethod
    def _build_all_evidence_text(
        rubric: dict, evidence_by_criterion: Dict[int, List[Dict]], total_states: int
    ) -> str:
        lines = []
        for c_idx, criterion in enumerate(rubric["items"]):
            lines.append(
                f'## Criterion {c_idx}: "{criterion.get("criterion", f"Criterion {c_idx}")}"'
            )
            analyses = evidence_by_criterion.get(c_idx, [])
            if not analyses:
                lines.append("No DOM-model evidence available for this criterion.")
                lines.append("")
                continue
            for analysis in sorted(
                analyses, key=lambda x: x.get("dom_model_state_idx", 0)
            ):
                sn = analysis.get("dom_model_state_idx", 0)
                lines.append(f"### DOM-model state {sn} analysis:")
                lines.append(
                    f"**Evidence:** {analysis.get('dom_model_evidence', 'N/A')}"
                )
                lines.append(
                    f"**Analysis:** {analysis.get('criterion_analysis', 'N/A')}"
                )
                lines.append(
                    f"**Discrepancies:** {analysis.get('discrepancies', 'N/A')}"
                )
                lines.append(
                    f"**Environment Issues Confirmed:** {analysis.get('environment_issues_confirmed', False)}"
                )
                lines.append("")
            lines.append("")
        return "\n".join(lines)
