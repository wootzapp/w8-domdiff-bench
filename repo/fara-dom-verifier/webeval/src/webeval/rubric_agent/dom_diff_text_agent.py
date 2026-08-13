"""Universal Verifier evidence agent for refined ``dom_diffN.txt`` only."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence

from webeval.rubric_agent.dom_diff_agent import DOMDiffMMRubricAgent, _EVIDENCE_STATUSES
from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_compaction import (
    aggregate_text_compaction_metrics,
    compact_text_frames,
    render_full_compact_frame,
)
from webeval.rubric_agent.dom_diff_text_evidence import (
    DOMDiffTextEvidenceFrame,
    load_dom_diff_text_frames,
)
from webeval.rubric_agent.dom_diff_text_prompts import (
    DOM_DIFF_TEXT_GROUNDING_RULES,
    TEXT_BATCHED_RELEVANCE_PROMPT,
    TEXT_PACKED_ANALYSIS_PROMPT,
)
from webeval.rubric_agent.dom_diff_text_retrieval import (
    build_selection_receipts,
    build_text_retrieval_terms,
    render_batched_relevance_evidence,
    render_packed_analysis_evidence,
)


logger = logging.getLogger(__name__)


class DOMDiffTextMMRubricAgent(DOMDiffMMRubricAgent):
    """Reuse shared scoring while replacing only refined-text evidence hooks."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._text_runtime_metrics: dict[str, Any] = {}

    def _setting(self, name: str, default: Any) -> Any:
        return getattr(self.config, name, default)

    @property
    def _judge_model_name(self) -> str:
        return str(self._setting("text_judge_model", "gpt-5.2"))

    @property
    def _frame_starting_tokens(self) -> int:
        return int(self._setting("text_frame_starting_tokens", 1500))

    @property
    def _trajectory_starting_tokens(self) -> int:
        return int(self._setting("text_trajectory_starting_tokens", 16000))

    @property
    def _analysis_starting_tokens(self) -> int:
        return int(self._setting("text_analysis_starting_tokens", 24000))

    @property
    def _max_chunk_tokens(self) -> int:
        return int(self._setting("text_max_chunk_tokens", 256))

    @property
    def _model_context_window_tokens(self) -> int:
        return int(self._setting("text_model_context_window_tokens", 128000))

    @property
    def _relevance_completion_reserve(self) -> int:
        return int(self._setting("text_relevance_completion_reserve_tokens", 4096))

    @property
    def _analysis_completion_reserve(self) -> int:
        return int(self._setting("text_analysis_completion_reserve_tokens", 8192))

    @property
    def _prompt_headroom_tokens(self) -> int:
        return int(self._setting("text_prompt_headroom_tokens", 1024))

    @property
    def _allow_budget_expansion(self) -> bool:
        return bool(self._setting("text_allow_budget_expansion", True))

    def _reset_text_metrics(self) -> None:
        self._text_runtime_metrics = {
            "pipeline": "parse_normalize_compact_retrieve_pack",
            "requests": [],
            "selection_receipts": [],
            "retrieval_term_count": 0,
            "audit_receipts": [],
        }

    def _record_request(
        self,
        *,
        stage: str,
        prompt: str,
        evidence: Any,
        validation_attempt: int,
        unit: str,
    ) -> None:
        estimator = TokenEstimator(self._judge_model_name)
        self._text_runtime_metrics.setdefault("requests", []).append(
            {
                "stage": stage,
                "unit": unit,
                "validation_attempt": validation_attempt,
                "prompt_chars": len(prompt),
                "prompt_estimated_tokens": estimator.count(prompt),
                "evidence_chars": len(evidence.text),
                "evidence_estimated_tokens": evidence.estimated_tokens,
                "tokenizer": evidence.tokenizer,
                "records_omitted_by_context_limit": evidence.records_omitted_by_budget,
                "budget": evidence.budget_receipt.to_dict(),
                "context_limit_omissions": [
                    item.to_dict() for item in evidence.omission_receipts
                ],
                "retrieval_omissions": [
                    item.to_dict() for item in evidence.retrieval_omissions
                ],
                "criterion_chunk_assignments": {
                    str(key): list(value)
                    for key, value in sorted(
                        (evidence.criterion_chunk_assignments or {}).items()
                    )
                },
            }
        )

    def text_runtime_metrics(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._text_runtime_metrics))

    def _load_dom_evidence(
        self, dom_actions: list[dict[str, Any]]
    ) -> list[DOMDiffTextEvidenceFrame]:
        self._reset_text_metrics()
        frames = load_dom_diff_text_frames(dom_actions)
        frames = compact_text_frames(
            frames,
            max_chunk_tokens=self._max_chunk_tokens,
            model=self._judge_model_name,
        )
        if self.config.dom_top_k is not None:
            raise ValueError(
                "dom_top_k is unsupported for refined text because every action step "
                "must remain chronologically represented"
            )
        compact_frames = [frame.compact for frame in frames]
        self._text_runtime_metrics["compaction"] = aggregate_text_compaction_metrics(
            compact_frames
        )
        estimator = TokenEstimator(self._judge_model_name)
        frame_diagnostics: list[dict[str, Any]] = []
        for frame in frames:
            compact_tokens = estimator.count(render_full_compact_frame(frame.compact))
            raw_tokens = estimator.count(
                Path(frame.text_path).read_text(encoding="utf-8", errors="strict")
            )
            frame_diagnostics.append({
                "step": frame.action_ordinal,
                "starting_target_tokens": self._frame_starting_tokens,
                "raw_evidence_estimated_tokens": raw_tokens,
                "full_compact_estimated_tokens": compact_tokens,
                "starting_target_exceeded": compact_tokens > self._frame_starting_tokens,
                "records_or_chunks_omitted_for_starting_target": 0,
            })
        self._text_runtime_metrics["frame_budget_diagnostics"] = frame_diagnostics
        self._text_runtime_metrics["raw_evidence_estimated_tokens"] = sum(
            item["raw_evidence_estimated_tokens"] for item in frame_diagnostics
        )
        self._text_runtime_metrics["model_compact_estimated_tokens"] = sum(
            item["full_compact_estimated_tokens"] for item in frame_diagnostics
        )
        self._text_runtime_metrics["audit_receipts"] = [
            {
                "source": frame.audit.to_dict(),
                "compaction": frame.compact.receipt.to_dict(),
            }
            for frame in frames
        ]
        return frames

    def _compact_dom_trajectory_metadata(
        self, frames: list[DOMDiffTextEvidenceFrame], *, limit: int = 12000
    ) -> str:
        del limit
        rows = [
            {
                "step": frame.action_ordinal,
                "action": frame.action_type,
                "status": frame.status,
                "before_url": frame.before_url,
                "after_url": frame.after_url,
                "coverage_warnings": list(frame.coverage_warnings),
            }
            for frame in frames
        ]
        return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    async def _generate_dom_retrieval_terms(
        self,
        frames: list[DOMDiffTextEvidenceFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
        predicted_output: str,
    ) -> list[str]:
        del frames, init_url_context
        terms = build_text_retrieval_terms(
            task=task,
            rubric_items=rubric.get("items", []),
            predicted_output=predicted_output,
        )
        self._text_runtime_metrics["retrieval_term_count"] = len(terms)
        # Keep predicted output available to the evidence-specific scoring hook
        # without changing the inherited method signature.
        self._text_runtime_metrics["predicted_output"] = predicted_output
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
        frames: list[DOMDiffTextEvidenceFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
        retrieval_terms: list[str] | None = None,
    ) -> Dict[int, Dict]:
        del retrieval_terms
        predicted_output = str(self._text_runtime_metrics.get("predicted_output") or "")
        compact_frames = [frame.compact for frame in frames]
        if str(self._setting("text_relevance_mode", "batched_llm")) != "batched_llm":
            raise ValueError(
                "The production refined-text verifier has one relevance path: "
                "batched_llm"
            )

        rubric_text = self._rubric_text(rubric)
        estimator = TokenEstimator(self._judge_model_name)
        empty_prompt = TEXT_BATCHED_RELEVANCE_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            text_frames="",
            rubric_criteria=rubric_text,
            grounding_rules=DOM_DIFF_TEXT_GROUNDING_RULES,
        )
        evidence = render_batched_relevance_evidence(
            compact_frames,
            rubric,
            task=task,
            predicted_output=predicted_output,
            starting_target_tokens=self._trajectory_starting_tokens,
            model_context_window_tokens=self._model_context_window_tokens,
            completion_reserve_tokens=self._relevance_completion_reserve,
            prompt_headroom_tokens=self._prompt_headroom_tokens,
            fixed_prompt_tokens=estimator.count(empty_prompt),
            allow_budget_expansion=self._allow_budget_expansion,
            model=self._judge_model_name,
        )
        prompt = TEXT_BATCHED_RELEVANCE_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            text_frames=evidence.text,
            rubric_criteria=rubric_text,
            grounding_rules=DOM_DIFF_TEXT_GROUNDING_RULES,
        )
        if estimator.count(prompt) > evidence.budget_receipt.safe_prompt_limit_tokens:
            raise ValueError("Batched text relevance prompt exceeds safe model context")
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        criterion_count = len(rubric["items"])
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_iters + 1):
            self._record_request(
                stage="text_relevance_batched",
                prompt=prompt,
                evidence=evidence,
                validation_attempt=attempt,
                unit="all_frames",
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
                    if int(row.get("evidence_idx", -1)) != expected_idx:
                        raise ValueError(f"Expected evidence_idx={expected_idx}")
                    normalized: Dict[Any, Any] = {}
                    for criterion_idx in range(criterion_count):
                        value = int(row.get(f"criterion_{criterion_idx}"))
                        if not 0 <= value <= 10:
                            raise ValueError("Relevance score outside [0,10]")
                        normalized[criterion_idx] = value
                    normalized.update(screenshot_idx=expected_idx, evidence_idx=expected_idx)
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
        logger.warning("Batched refined-text relevance failed: %s", last_error)
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
        frames: list[DOMDiffTextEvidenceFrame],
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
        filtered = {
            criterion_idx: list(indices)
            for criterion_idx, indices in grouped_frames.items()
        }
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
        compact_frames = [frame.compact for frame in frames]
        if relevance_scores is not None:
            self._text_runtime_metrics["selection_receipts"] = [
                receipt.to_dict()
                for receipt in build_selection_receipts(
                    compact_frames,
                    filtered,
                    relevance_scores,
                    rubric,
                    predicted_output=predicted_output,
                    task=task,
                )
            ]

        criterion_indices = list(range(len(rubric["items"])))
        criteria_block, conditional = self._criteria_block(rubric, criterion_indices)
        estimator = TokenEstimator(self._judge_model_name)
        empty_prompt = TEXT_PACKED_ANALYSIS_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            packed_evidence="",
            criteria_info_block=criteria_block,
            grounding_rules=DOM_DIFF_TEXT_GROUNDING_RULES,
        )
        packed = render_packed_analysis_evidence(
            compact_frames,
            filtered,
            rubric,
            predicted_output=predicted_output,
            task=task,
            starting_target_tokens=self._analysis_starting_tokens,
            model_context_window_tokens=self._model_context_window_tokens,
            completion_reserve_tokens=self._analysis_completion_reserve,
            prompt_headroom_tokens=self._prompt_headroom_tokens,
            fixed_prompt_tokens=estimator.count(empty_prompt),
            allow_budget_expansion=self._allow_budget_expansion,
            model=self._judge_model_name,
        )
        prompt = TEXT_PACKED_ANALYSIS_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            packed_evidence=packed.text,
            criteria_info_block=criteria_block,
            grounding_rules=DOM_DIFF_TEXT_GROUNDING_RULES,
        )
        if estimator.count(prompt) > packed.budget_receipt.safe_prompt_limit_tokens:
            raise ValueError("Packed refined-text analysis exceeds safe model context")
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_iters + 1):
            self._record_request(
                stage="text_analysis_packed",
                prompt=prompt,
                evidence=packed,
                validation_attempt=attempt,
                unit="selected_frames",
            )
            try:
                raw = json.loads(
                    await self._call_llm(messages, self._gpt5_client, json_output=True)
                )
                analyses = self._normalize_batched_analysis_response(raw, criterion_indices)
                if analyses is None or len(analyses) != len(criterion_indices):
                    raise ValueError("Wrong packed analysis count")
                result: Dict[int, List[Dict]] = {idx: [] for idx in criterion_indices}
                for analysis, expected_idx in zip(analyses, criterion_indices):
                    returned_idx = analysis.pop("criterion_idx", expected_idx)
                    if returned_idx != expected_idx:
                        raise ValueError(
                            f"Expected criterion_idx={expected_idx}, got {returned_idx}"
                        )
                    status = str(analysis.get("evidence_status") or "")
                    if status not in _EVIDENCE_STATUSES:
                        raise ValueError(f"Invalid evidence status {status!r}")
                    allowed = filtered.get(expected_idx, [])
                    returned = analysis.pop("evidence_indices", allowed)
                    if not isinstance(returned, list):
                        raise ValueError("evidence_indices must be a list")
                    normalized_indices = [int(index) for index in returned]
                    if any(index not in allowed for index in normalized_indices):
                        raise ValueError("Packed analysis cited an unassigned frame")
                    if not normalized_indices:
                        normalized_indices = list(allowed)
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
                            f"Error: {exc}. Return one valid analysis for every criterion."
                        ),
                    }
                )
        logger.warning("Packed refined-text analysis failed: %s", last_error)
        result = {idx: [] for idx in criterion_indices}
        for criterion_idx in criterion_indices:
            allowed = filtered.get(criterion_idx, [])
            frame_idx = allowed[0] if allowed else 0
            step = frames[frame_idx].action_ordinal if frames else 0
            result[criterion_idx].append(
                {
                    "evidence_status": "unknown",
                    "evidence_text": "Refined DOM-diff text analysis unavailable",
                    "screenshot_evidence": "Refined DOM-diff text analysis unavailable",
                    "criterion_analysis": (
                        "Unknown because refined DOM-diff evidence could not be analyzed"
                    ),
                    "discrepancies": "Unknown",
                    "environment_issues_confirmed": False,
                    "evidence_idx": frame_idx,
                    "screenshot_idx": frame_idx,
                    "evidence_indices": list(allowed),
                    "steps": [step],
                    **(
                        {"condition_verification": False}
                        if criterion_idx in conditional
                        else {}
                    ),
                }
            )
        return result

    @staticmethod
    def _build_all_screenshot_evidence_text(
        rubric: dict,
        evidence_by_criterion: Dict[int, List[Dict]],
        total_screenshots: int,
        evidence_mode: str = "dom",
    ) -> str:
        del evidence_mode
        lines: list[str] = [DOM_DIFF_TEXT_GROUNDING_RULES, ""]
        for criterion_idx, criterion in enumerate(rubric["items"]):
            lines.append(
                f'## Criterion {criterion_idx}: "{criterion.get("criterion", f"Criterion {criterion_idx}")}"'
            )
            analyses = evidence_by_criterion.get(criterion_idx, [])
            if not analyses:
                lines.extend(["No refined DOM-diff text evidence was selected for this criterion.", ""])
                continue
            for analysis in sorted(analyses, key=lambda item: item.get("evidence_idx", 0)):
                frame_idx = int(analysis.get("evidence_idx", 0))
                steps = analysis.get("steps") or [frame_idx + 1]
                lines.extend(
                    [
                        f"### Refined DOM-diff text steps {steps} of {total_screenshots}:",
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
