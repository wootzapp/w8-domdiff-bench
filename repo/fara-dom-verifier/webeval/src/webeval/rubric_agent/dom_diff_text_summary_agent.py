"""Isolated summary-S3 verifier agent for refined ``dom_diffN.txt`` files."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from webeval.rubric_agent.dom_diff_agent import _EVIDENCE_STATUSES
from webeval.rubric_agent.dom_diff_summary_agent import DOMDiffSummaryMMRubricAgent
from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_evidence import (
    DOMDiffTextEvidenceFrame,
    load_dom_diff_text_frames,
)
from webeval.rubric_agent.dom_diff_text_summary_projection import (
    aggregate_text_summary_projection_metrics,
    project_text_summary_frames,
)
from webeval.rubric_agent.dom_diff_text_summary_prompts import (
    DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
    TEXT_SUMMARY_BATCHED_RELEVANCE_PROMPT,
    TEXT_SUMMARY_PACKED_ANALYSIS_PROMPT,
)
from webeval.rubric_agent.dom_diff_text_summary_rendering import (
    render_batched_text_summary_relevance_evidence,
    render_packed_text_summary_analysis_evidence,
)


logger = logging.getLogger(__name__)


class DOMDiffTextSummaryMMRubricAgent(DOMDiffSummaryMMRubricAgent):
    """Keep the summary S3 call graph; replace only text-format boundaries."""

    def _load_dom_evidence(
        self, dom_actions: list[dict[str, Any]]
    ) -> list[DOMDiffTextEvidenceFrame]:
        self._reset_summary_metrics()
        frames = load_dom_diff_text_frames(dom_actions)
        frames = project_text_summary_frames(
            frames,
            max_record_chars=int(self._setting("summary_max_record_chars", 600)),
        )
        if self.config.dom_top_k is not None:
            frames = frames[: self.config.dom_top_k]
        self._summary_runtime_metrics[
            "compaction"
        ] = aggregate_text_summary_projection_metrics(
            [frame.compact for frame in frames]
        )
        self._summary_runtime_metrics["evidence_source"] = "dom_diff_text_summary"
        return frames

    async def _score_relevance_batched(
        self,
        frames: list[DOMDiffTextEvidenceFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
    ) -> Dict[int, Dict]:
        rubric_text = self._rubric_text(rubric)
        estimator = TokenEstimator(self._judge_model_name)
        empty_prompt = TEXT_SUMMARY_BATCHED_RELEVANCE_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            text_summary_frames="",
            rubric_criteria=rubric_text,
            grounding_rules=DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
        )
        evidence_budget = (
            self._trajectory_token_budget - estimator.count(empty_prompt) - 64
        )
        if evidence_budget < 120:
            raise ValueError(
                "summary_trajectory_token_budget is too small for fixed relevance prompt context"
            )
        evidence = render_batched_text_summary_relevance_evidence(
            [frame.compact for frame in frames],
            token_budget=evidence_budget,
            model=self._judge_model_name,
        )
        prompt = TEXT_SUMMARY_BATCHED_RELEVANCE_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            text_summary_frames=evidence.text,
            rubric_criteria=rubric_text,
            grounding_rules=DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
        )
        if estimator.count(prompt) > self._trajectory_token_budget:
            raise ValueError(
                "Batched text-summary relevance prompt exceeds configured token budget"
            )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        criterion_count = len(rubric["items"])
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_iters + 1):
            self._record_request(
                stage="text_summary_relevance_batched",
                prompt=prompt,
                evidence_chars=len(evidence.text),
                evidence_estimated_tokens=evidence.estimated_tokens,
                tokenizer=evidence.tokenizer,
                unit="all_frames",
                validation_attempt=attempt,
                omitted_records=evidence.records_omitted_by_budget,
            )
            try:
                raw = json.loads(
                    await self._call_llm(messages, self._gpt5_client, json_output=True)
                )
                rows = raw.get("frames") if isinstance(raw, dict) else None
                if not isinstance(rows, list) or len(rows) != len(frames):
                    raise ValueError(f"Expected {len(frames)} relevance rows")
                result: Dict[int, Dict] = {}
                for expected_idx, row in enumerate(rows):
                    if not isinstance(row, dict):
                        raise ValueError("Every relevance row must be an object")
                    returned_idx = int(row.get("evidence_idx", -1))
                    if returned_idx != expected_idx:
                        raise ValueError(
                            f"Expected evidence_idx={expected_idx}, got {returned_idx}"
                        )
                    normalized: Dict[Any, Any] = {}
                    for criterion_idx in range(criterion_count):
                        value = int(row.get(f"criterion_{criterion_idx}"))
                        if not 0 <= value <= 10:
                            raise ValueError("relevance score outside [0,10]")
                        normalized[criterion_idx] = value
                    normalized.update(
                        screenshot_idx=expected_idx,
                        evidence_idx=expected_idx,
                    )
                    result[expected_idx] = normalized
                return result
            except Exception as exc:
                last_error = exc
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error: {exc}. Return one complete row for every frame.",
                    }
                )
        logger.warning("Batched text-summary relevance failed: %s", last_error)
        return {
            frame_idx: {
                **{idx: 0 for idx in range(criterion_count)},
                "screenshot_idx": frame_idx,
                "evidence_idx": frame_idx,
            }
            for frame_idx in range(len(frames))
        }

    async def _analyze_packed(
        self,
        frames: list[DOMDiffTextEvidenceFrame],
        rubric: dict,
        grouped_frames: Dict[int, List[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
    ) -> Dict[int, List[Dict]]:
        criterion_indices = list(range(len(rubric["items"])))
        criteria_block, conditional = self._criteria_block(rubric, criterion_indices)
        estimator = TokenEstimator(self._judge_model_name)
        empty_prompt = TEXT_SUMMARY_PACKED_ANALYSIS_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            packed_evidence="",
            criteria_info_block=criteria_block,
            grounding_rules=DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
        )
        evidence_budget = (
            self._analysis_token_budget - estimator.count(empty_prompt) - 64
        )
        if evidence_budget < 160:
            raise ValueError(
                "summary_analysis_token_budget is too small for fixed analysis prompt context"
            )
        packed = render_packed_text_summary_analysis_evidence(
            [frame.compact for frame in frames],
            grouped_frames,
            token_budget=evidence_budget,
            model=self._judge_model_name,
        )
        prompt = TEXT_SUMMARY_PACKED_ANALYSIS_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            packed_evidence=packed.text,
            criteria_info_block=criteria_block,
            grounding_rules=DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
        )
        if estimator.count(prompt) > self._analysis_token_budget:
            raise ValueError(
                "Packed text-summary analysis prompt exceeds configured token budget"
            )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_iters + 1):
            self._record_request(
                stage="text_summary_analysis_packed",
                prompt=prompt,
                evidence_chars=len(packed.text),
                evidence_estimated_tokens=packed.estimated_tokens,
                tokenizer=packed.tokenizer,
                unit="selected_frames",
                validation_attempt=attempt,
                omitted_records=packed.records_omitted_by_budget,
            )
            try:
                raw = json.loads(
                    await self._call_llm(messages, self._gpt5_client, json_output=True)
                )
                analyses = self._normalize_batched_analysis_response(
                    raw, criterion_indices
                )
                if analyses is None or len(analyses) != len(criterion_indices):
                    raise ValueError("wrong packed analysis count")
                result: Dict[int, List[Dict]] = {idx: [] for idx in criterion_indices}
                for analysis, expected_idx in zip(analyses, criterion_indices):
                    returned_idx = analysis.pop("criterion_idx", expected_idx)
                    if returned_idx != expected_idx:
                        raise ValueError(
                            f"Expected criterion_idx={expected_idx}, got {returned_idx}"
                        )
                    status = str(analysis.get("evidence_status") or "")
                    if status not in _EVIDENCE_STATUSES:
                        raise ValueError(f"invalid evidence status {status!r}")
                    allowed_indices = grouped_frames.get(expected_idx, [])
                    returned_indices = analysis.pop("evidence_indices", allowed_indices)
                    if not isinstance(returned_indices, list):
                        raise ValueError("evidence_indices must be a list")
                    normalized_indices = [int(index) for index in returned_indices]
                    if any(
                        index not in allowed_indices for index in normalized_indices
                    ):
                        raise ValueError(
                            f"criterion {expected_idx} cited an unassigned FRAME; "
                            f"allowed={allowed_indices}"
                        )
                    if not normalized_indices:
                        normalized_indices = list(allowed_indices)
                    frame_idx = normalized_indices[0] if normalized_indices else 0
                    self._dual_write_evidence_fields(analysis)
                    self._validate_evidence_analysis(
                        analysis, expected_idx in conditional
                    )
                    analysis["evidence_idx"] = frame_idx
                    analysis["screenshot_idx"] = frame_idx
                    analysis["evidence_indices"] = normalized_indices
                    analysis["steps"] = [
                        frames[index].action_ordinal for index in normalized_indices
                    ]
                    result[expected_idx].append(analysis)
                return result
            except Exception as exc:
                last_error = exc
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Error: {exc}. Return one valid analysis for every criterion "
                            "and cite only assigned zero-based FRAME values, never STEP values."
                        ),
                    }
                )
        logger.warning("Packed text-summary analysis failed: %s", last_error)
        result = {idx: [] for idx in criterion_indices}
        for criterion_idx in criterion_indices:
            allowed = grouped_frames.get(criterion_idx, [])
            frame_idx = allowed[0] if allowed else 0
            step = frames[frame_idx].action_ordinal if frames else 0
            for idx, analysis in self._unknown_analyses(
                [criterion_idx], conditional, frame_idx, step
            ):
                result[idx].append(analysis)
        return result

    @staticmethod
    def _build_all_screenshot_evidence_text(
        rubric: dict,
        evidence_by_criterion: Dict[int, List[Dict]],
        total_screenshots: int,
        evidence_mode: str = "dom",
    ) -> str:
        del evidence_mode
        lines: list[str] = [DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES, ""]
        for criterion_idx, criterion in enumerate(rubric["items"]):
            lines.append(
                f'## Criterion {criterion_idx}: "{criterion.get("criterion", f"Criterion {criterion_idx}")}"'
            )
            analyses = evidence_by_criterion.get(criterion_idx, [])
            if not analyses:
                lines.extend(
                    ["No compact refined DOM-diff text evidence was selected.", ""]
                )
                continue
            for analysis in sorted(
                analyses, key=lambda item: item.get("evidence_idx", 0)
            ):
                frame_idx = int(analysis.get("evidence_idx", 0))
                steps = analysis.get("steps") or [frame_idx + 1]
                lines.extend(
                    [
                        f"### DOM-text summary steps {steps} of {total_screenshots}:",
                        f"**Evidence Status:** {analysis.get('evidence_status', 'unknown')}",
                        f"**Evidence:** {analysis.get('evidence_text', analysis.get('screenshot_evidence', 'N/A'))}",
                        f"**Analysis:** {analysis.get('criterion_analysis', 'N/A')}",
                        f"**Discrepancies:** {analysis.get('discrepancies', 'N/A')}",
                        "**Environment Issues Confirmed:** "
                        f"{analysis.get('environment_issues_confirmed', False)}",
                        "",
                    ]
                )
        return "\n".join(lines)

    def text_summary_runtime_metrics(self) -> dict[str, Any]:
        return self.summary_runtime_metrics()
