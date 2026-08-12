"""Universal Verifier evidence agent for DOM-diff summaries only.

Modes are deliberately isolated from raw DOM diffs and full DOM evidence:

* S0: historical raw summaries and call graph;
* S1: compact summaries with the historical call graph;
* S2: compact summaries with one batched relevance call;
* S3: compact summaries with batched relevance and packed analysis.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Sequence

from webeval.rubric_agent.dom_diff_agent import (
    DOMDiffMMRubricAgent,
    _EVIDENCE_STATUSES,
)
from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_summary_evidence import (
    DOMDiffSummaryEvidenceFrame,
    load_dom_diff_summary_frames,
    render_summary_result,
    summary_compaction_metrics,
)
from webeval.rubric_agent.dom_diff_summary_prompts import (
    DOM_DIFF_SUMMARY_GROUNDING_RULES,
    SUMMARY_BATCHED_RELEVANCE_PROMPT,
    SUMMARY_FRAME_ANALYSIS_PROMPT,
    SUMMARY_FRAME_RELEVANCE_PROMPT,
    SUMMARY_PACKED_ANALYSIS_PROMPT,
)
from webeval.rubric_agent.dom_diff_summary_retrieval import (
    build_selection_receipts,
    build_summary_retrieval_terms,
    local_relevance_scores,
    render_batched_relevance_evidence,
    render_packed_analysis_evidence,
)


logger = logging.getLogger(__name__)
SUMMARY_MODES = {"s0", "s1", "s2", "s3"}


class DOMDiffSummaryMMRubricAgent(DOMDiffMMRubricAgent):
    """Reuse Universal Verifier scoring with summary-only compact evidence."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._summary_runtime_metrics: dict[str, Any] = {}

    def _setting(self, name: str, default: Any) -> Any:
        return getattr(self.config, name, default)

    @property
    def _summary_mode(self) -> str:
        mode = str(self._setting("summary_mode", "s1")).lower()
        if mode not in SUMMARY_MODES:
            raise ValueError(f"Unsupported summary_mode {mode!r}")
        return mode

    @property
    def _summary_projection(self) -> str:
        configured = self._setting("summary_projection", None)
        if configured is not None:
            projection = str(configured).lower()
        else:
            projection = "raw" if self._summary_mode == "s0" else "compact"
        if projection not in {"raw", "compact"}:
            raise ValueError(f"Unsupported summary_projection {projection!r}")
        return projection

    @property
    def _judge_model_name(self) -> str:
        return str(self._setting("summary_judge_model", "gpt-5.2"))

    @property
    def _frame_token_budget(self) -> int:
        return int(self._setting("summary_frame_token_budget", 1500))

    @property
    def _trajectory_token_budget(self) -> int:
        return int(self._setting("summary_trajectory_token_budget", 16000))

    @property
    def _analysis_token_budget(self) -> int:
        return int(self._setting("summary_analysis_token_budget", 24000))

    def _reset_summary_metrics(self) -> None:
        self._summary_runtime_metrics = {
            "summary_mode": self._summary_mode,
            "summary_projection": self._summary_projection,
            "requests": [],
            "selection_receipts": [],
            "retrieval_term_count": 0,
        }

    def _record_request(
        self,
        *,
        stage: str,
        prompt: str,
        evidence_chars: int,
        evidence_estimated_tokens: int,
        tokenizer: str,
        unit: str,
        validation_attempt: int,
        omitted_records: int = 0,
    ) -> None:
        estimator = TokenEstimator(self._judge_model_name)
        self._summary_runtime_metrics.setdefault("requests", []).append(
            {
                "stage": stage,
                "unit": unit,
                "validation_attempt": validation_attempt,
                "prompt_chars": len(prompt),
                "prompt_estimated_tokens": estimator.count(prompt),
                "evidence_chars": evidence_chars,
                "evidence_estimated_tokens": evidence_estimated_tokens,
                "tokenizer": tokenizer,
                "records_omitted_by_budget": omitted_records,
            }
        )

    def summary_runtime_metrics(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._summary_runtime_metrics))

    def _load_dom_evidence(
        self, dom_actions: list[dict[str, Any]]
    ) -> list[DOMDiffSummaryEvidenceFrame]:
        self._reset_summary_metrics()
        frames = load_dom_diff_summary_frames(
            dom_actions,
            max_record_chars=int(self._setting("summary_max_record_chars", 600)),
        )
        if self.config.dom_top_k is not None:
            frames = frames[: self.config.dom_top_k]
        self._summary_runtime_metrics["compaction"] = summary_compaction_metrics(frames)
        return frames

    def _compact_dom_trajectory_metadata(
        self, frames: list[DOMDiffSummaryEvidenceFrame], *, limit: int = 12000
    ) -> str:
        rows = [
            {
                "step": frame.action_ordinal,
                "capture": frame.capture_status,
                "source_sha256": frame.source_sha256,
                "source_bytes": frame.source_bytes,
                "compact_bytes": frame.compact.compact_bytes,
                "page_transition": frame.compact.page,
                "counts": frame.compact.counts,
                "receipt": frame.compact.to_dict()["receipt"],
            }
            for frame in frames
        ]
        text = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return text if len(text) <= limit else text[: limit - 1] + "…"

    async def _generate_dom_retrieval_terms(
        self,
        frames: list[DOMDiffSummaryEvidenceFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
        predicted_output: str,
    ) -> list[str]:
        del frames, init_url_context
        terms = build_summary_retrieval_terms(
            task=task,
            rubric_items=rubric.get("items", []),
            predicted_output=predicted_output,
        )
        self._summary_runtime_metrics["retrieval_term_count"] = len(terms)
        return terms

    @staticmethod
    def _rubric_text(rubric: dict) -> str:
        return "".join(
            f"\n{idx}. **{item['criterion']}**\n"
            f"   Description: {item['description']}\n"
            for idx, item in enumerate(rubric["items"])
        )

    @staticmethod
    def _criteria_block(
        rubric: dict, criterion_indices: Sequence[int]
    ) -> tuple[str, set[int]]:
        block = ""
        conditional: set[int] = set()
        for idx in criterion_indices:
            item = rubric["items"][idx]
            block += (
                f"\n**Criterion {idx}:** {item['criterion']}\n"
                f"**Description:** {item['description']}\n"
                f"**Max Points:** {item['max_points']}\n"
            )
            if "condition" in item:
                conditional.add(idx)
                block += (
                    f"**CONDITIONAL:** {item['condition']}; include "
                    "condition_verification.\n"
                )
        return block, conditional

    async def _score_dom_criterion_relevance(
        self,
        frames: list[DOMDiffSummaryEvidenceFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
        retrieval_terms: list[str] | None = None,
    ) -> Dict[int, Dict]:
        del retrieval_terms
        relevance_mode = str(self._setting("summary_relevance_mode", ""))
        if not relevance_mode:
            relevance_mode = "batched_llm" if self._summary_mode in {"s2", "s3"} else "per_frame_llm"
        predicted_output = str(self._setting("summary_predicted_output", ""))
        if relevance_mode == "local":
            result = local_relevance_scores(
                [frame.compact for frame in frames],
                rubric,
                task=task,
                predicted_output=predicted_output,
            )
            self._summary_runtime_metrics["local_relevance"] = True
            return result
        if relevance_mode == "batched_llm":
            return await self._score_relevance_batched(
                frames, rubric, task, init_url_context
            )
        if relevance_mode != "per_frame_llm":
            raise ValueError(f"Unsupported summary_relevance_mode: {relevance_mode!r}")
        return await self._score_relevance_per_frame(
            frames, rubric, task, init_url_context
        )

    async def _score_relevance_per_frame(
        self,
        frames: list[DOMDiffSummaryEvidenceFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
    ) -> Dict[int, Dict]:
        rubric_text = self._rubric_text(rubric)
        criterion_count = len(rubric["items"])

        async def score(frame_idx: int, frame: DOMDiffSummaryEvidenceFrame) -> Dict:
            rendered = render_summary_result(
                frame,
                projection=self._summary_projection,
                token_budget=self._frame_token_budget,
                model=self._judge_model_name,
            )
            prompt = SUMMARY_FRAME_RELEVANCE_PROMPT.substitute(
                task_definition=task,
                init_url_context=init_url_context,
                summary_frame=rendered.text,
                rubric_criteria=rubric_text,
                grounding_rules=DOM_DIFF_SUMMARY_GROUNDING_RULES,
            )
            messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
            last_error: Exception | None = None
            for attempt in range(1, self.config.max_iters + 1):
                self._record_request(
                    stage="summary_relevance_per_frame",
                    prompt=prompt,
                    evidence_chars=len(rendered.text),
                    evidence_estimated_tokens=rendered.estimated_tokens,
                    tokenizer=rendered.tokenizer,
                    unit=f"frame_{frame_idx}",
                    validation_attempt=attempt,
                    omitted_records=rendered.records_omitted_by_budget,
                )
                try:
                    raw = json.loads(
                        await self._call_llm(messages, self._gpt5_client, json_output=True)
                    )
                    row: Dict[Any, Any] = {}
                    for criterion_idx in range(criterion_count):
                        keys = (f"criterion_{criterion_idx}", str(criterion_idx), criterion_idx)
                        found = next((raw[key] for key in keys if key in raw), None)
                        value = int(found)
                        if not 0 <= value <= 10:
                            raise ValueError("relevance score outside [0,10]")
                        row[criterion_idx] = value
                    row.update(screenshot_idx=frame_idx, evidence_idx=frame_idx)
                    return row
                except Exception as exc:
                    last_error = exc
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Error: {exc}. Return every criterion score as JSON.",
                        }
                    )
            logger.warning("Summary relevance failed for frame %s: %s", frame_idx, last_error)
            return {
                **{idx: 0 for idx in range(criterion_count)},
                "screenshot_idx": frame_idx,
                "evidence_idx": frame_idx,
            }

        values = await asyncio.gather(*(score(index, frame) for index, frame in enumerate(frames)))
        return {value["evidence_idx"]: value for value in values}

    async def _score_relevance_batched(
        self,
        frames: list[DOMDiffSummaryEvidenceFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
    ) -> Dict[int, Dict]:
        rubric_text = self._rubric_text(rubric)
        estimator = TokenEstimator(self._judge_model_name)
        empty_prompt = SUMMARY_BATCHED_RELEVANCE_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            summary_frames="",
            rubric_criteria=rubric_text,
            grounding_rules=DOM_DIFF_SUMMARY_GROUNDING_RULES,
        )
        evidence_budget = self._trajectory_token_budget - estimator.count(empty_prompt) - 64
        if evidence_budget < 120:
            raise ValueError(
                "summary_trajectory_token_budget is too small for fixed relevance prompt context"
            )
        evidence = render_batched_relevance_evidence(
            [frame.compact for frame in frames],
            token_budget=evidence_budget,
            model=self._judge_model_name,
        )
        prompt = SUMMARY_BATCHED_RELEVANCE_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            summary_frames=evidence.text,
            rubric_criteria=rubric_text,
            grounding_rules=DOM_DIFF_SUMMARY_GROUNDING_RULES,
        )
        if estimator.count(prompt) > self._trajectory_token_budget:
            raise ValueError("Batched summary relevance prompt exceeds configured token budget")
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        criterion_count = len(rubric["items"])
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_iters + 1):
            self._record_request(
                stage="summary_relevance_batched",
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
                        screenshot_idx=expected_idx, evidence_idx=expected_idx
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
        logger.warning("Batched summary relevance failed: %s", last_error)
        return {
            frame_idx: {
                **{idx: 0 for idx in range(criterion_count)},
                "screenshot_idx": frame_idx,
                "evidence_idx": frame_idx,
            }
            for frame_idx in range(len(frames))
        }

    async def _analyze_dom_evidence_batched(
        self,
        frames: list[DOMDiffSummaryEvidenceFrame],
        rubric: dict,
        grouped_frames: Dict[int, List[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
        relevance_scores: Dict[int, Dict] | None = None,
        min_relevance_threshold: int = 0,
        retrieval_terms: list[str] | None = None,
    ) -> Dict[int, List[Dict]]:
        del retrieval_terms
        filtered = {criterion_idx: list(indices) for criterion_idx, indices in grouped_frames.items()}
        if min_relevance_threshold and relevance_scores is not None:
            filtered = {
                criterion_idx: [
                    frame_idx
                    for frame_idx in indices
                    if relevance_scores.get(frame_idx, {}).get(criterion_idx, 0)
                    > min_relevance_threshold
                ]
                for criterion_idx, indices in filtered.items()
            }
        if relevance_scores is not None:
            receipts = build_selection_receipts(
                [frame.compact for frame in frames],
                filtered,
                relevance_scores,
                rubric,
                predicted_output=predicted_output,
            )
            self._summary_runtime_metrics["selection_receipts"] = [
                receipt.to_dict() for receipt in receipts
            ]
        if self._summary_mode == "s3" or str(
            self._setting("summary_analysis_mode", "")
        ) == "packed":
            return await self._analyze_packed(
                frames,
                rubric,
                filtered,
                task,
                init_url_context,
                action_history,
                predicted_output,
            )
        return await self._analyze_selected_frames(
            frames,
            rubric,
            filtered,
            task,
            init_url_context,
            action_history,
            predicted_output,
        )

    async def _analyze_selected_frames(
        self,
        frames: list[DOMDiffSummaryEvidenceFrame],
        rubric: dict,
        grouped_frames: Dict[int, List[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
    ) -> Dict[int, List[Dict]]:
        frame_to_criteria = self._invert_grouped_screenshots(grouped_frames)

        async def analyze(frame_idx: int, criterion_indices: List[int]):
            if not criterion_indices:
                return []
            criteria_block, conditional = self._criteria_block(rubric, criterion_indices)
            rendered = render_summary_result(
                frames[frame_idx],
                projection=self._summary_projection,
                token_budget=self._frame_token_budget,
                model=self._judge_model_name,
            )
            prompt = SUMMARY_FRAME_ANALYSIS_PROMPT.substitute(
                task_definition=task,
                init_url_context=init_url_context,
                action_history=action_history,
                agent_predicted_output=predicted_output,
                summary_frame=rendered.text,
                criteria_info_block=criteria_block,
                grounding_rules=DOM_DIFF_SUMMARY_GROUNDING_RULES,
            )
            messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
            last_error: Exception | None = None
            for attempt in range(1, self.config.max_iters + 1):
                self._record_request(
                    stage="summary_analysis_per_frame",
                    prompt=prompt,
                    evidence_chars=len(rendered.text),
                    evidence_estimated_tokens=rendered.estimated_tokens,
                    tokenizer=rendered.tokenizer,
                    unit=f"frame_{frame_idx}",
                    validation_attempt=attempt,
                    omitted_records=rendered.records_omitted_by_budget,
                )
                try:
                    raw = json.loads(
                        await self._call_llm(messages, self._gpt5_client, json_output=True)
                    )
                    analyses = self._normalize_batched_analysis_response(raw, criterion_indices)
                    if analyses is None or len(analyses) != len(criterion_indices):
                        raise ValueError("wrong analysis count")
                    output = []
                    for analysis, expected_idx in zip(analyses, criterion_indices):
                        returned_idx = analysis.pop("criterion_idx", expected_idx)
                        if returned_idx != expected_idx:
                            raise ValueError(
                                f"Expected criterion_idx={expected_idx}, got {returned_idx}"
                            )
                        status = str(analysis.get("evidence_status") or "")
                        if status not in _EVIDENCE_STATUSES:
                            raise ValueError(f"invalid evidence status {status!r}")
                        self._dual_write_evidence_fields(analysis)
                        self._validate_evidence_analysis(
                            analysis, expected_idx in conditional
                        )
                        analysis["evidence_idx"] = frame_idx
                        analysis["screenshot_idx"] = frame_idx
                        analysis["steps"] = [frames[frame_idx].action_ordinal]
                        output.append((expected_idx, analysis))
                    return output
                except Exception as exc:
                    last_error = exc
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Error: {exc}. Return one valid analysis per criterion.",
                        }
                    )
            logger.warning("Summary analysis failed for frame %s: %s", frame_idx, last_error)
            return self._unknown_analyses(
                criterion_indices, conditional, frame_idx, frames[frame_idx].action_ordinal
            )

        nested = await asyncio.gather(
            *(analyze(frame_idx, indices) for frame_idx, indices in frame_to_criteria.items())
        )
        result: Dict[int, List[Dict]] = {
            idx: [] for idx in range(len(rubric["items"]))
        }
        for entries in nested:
            for criterion_idx, analysis in entries:
                result[criterion_idx].append(analysis)
        return result

    async def _analyze_packed(
        self,
        frames: list[DOMDiffSummaryEvidenceFrame],
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
        empty_prompt = SUMMARY_PACKED_ANALYSIS_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            packed_evidence="",
            criteria_info_block=criteria_block,
            grounding_rules=DOM_DIFF_SUMMARY_GROUNDING_RULES,
        )
        evidence_budget = self._analysis_token_budget - estimator.count(empty_prompt) - 64
        if evidence_budget < 160:
            raise ValueError(
                "summary_analysis_token_budget is too small for fixed analysis prompt context"
            )
        packed = render_packed_analysis_evidence(
            [frame.compact for frame in frames],
            grouped_frames,
            token_budget=evidence_budget,
            model=self._judge_model_name,
        )
        prompt = SUMMARY_PACKED_ANALYSIS_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            packed_evidence=packed.text,
            criteria_info_block=criteria_block,
            grounding_rules=DOM_DIFF_SUMMARY_GROUNDING_RULES,
        )
        if estimator.count(prompt) > self._analysis_token_budget:
            raise ValueError("Packed summary analysis prompt exceeds configured token budget")
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_iters + 1):
            self._record_request(
                stage="summary_analysis_packed",
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
                analyses = self._normalize_batched_analysis_response(raw, criterion_indices)
                if analyses is None or len(analyses) != len(criterion_indices):
                    raise ValueError("wrong packed analysis count")
                result: Dict[int, List[Dict]] = {
                    idx: [] for idx in criterion_indices
                }
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
                    if any(index not in allowed_indices for index in normalized_indices):
                        raise ValueError("packed analysis cited an unassigned frame")
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
                        "content": f"Error: {exc}. Return one valid analysis for every criterion.",
                    }
                )
        logger.warning("Packed summary analysis failed: %s", last_error)
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
    def _unknown_analyses(
        criterion_indices: Sequence[int],
        conditional: set[int],
        frame_idx: int,
        step: int,
    ) -> list[tuple[int, dict[str, Any]]]:
        return [
            (
                criterion_idx,
                {
                    "evidence_status": "unknown",
                    "evidence_text": "Compact summary analysis unavailable",
                    "screenshot_evidence": "Compact summary analysis unavailable",
                    "criterion_analysis": "Unknown because summary evidence could not be analyzed",
                    "discrepancies": "Unknown",
                    "environment_issues_confirmed": False,
                    "evidence_idx": frame_idx,
                    "screenshot_idx": frame_idx,
                    "steps": [step],
                    **(
                        {"condition_verification": False}
                        if criterion_idx in conditional
                        else {}
                    ),
                },
            )
            for criterion_idx in criterion_indices
        ]

    @staticmethod
    def _build_all_screenshot_evidence_text(
        rubric: dict,
        evidence_by_criterion: Dict[int, List[Dict]],
        total_screenshots: int,
        evidence_mode: str = "dom",
    ) -> str:
        del evidence_mode
        lines: list[str] = [DOM_DIFF_SUMMARY_GROUNDING_RULES, ""]
        for criterion_idx, criterion in enumerate(rubric["items"]):
            lines.append(
                f'## Criterion {criterion_idx}: "{criterion.get("criterion", f"Criterion {criterion_idx}")}"'
            )
            analyses = evidence_by_criterion.get(criterion_idx, [])
            if not analyses:
                lines.extend(["No compact summary evidence was selected for this criterion.", ""])
                continue
            for analysis in sorted(analyses, key=lambda item: item.get("evidence_idx", 0)):
                frame_idx = int(analysis.get("evidence_idx", 0))
                steps = analysis.get("steps") or [frame_idx + 1]
                lines.extend(
                    [
                        f"### DOM summary steps {steps} of {total_screenshots}:",
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

