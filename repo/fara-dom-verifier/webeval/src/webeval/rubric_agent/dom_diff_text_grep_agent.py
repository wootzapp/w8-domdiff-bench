"""Raw DOM-diff grep/read evidence path for the shared Universal Verifier."""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, Callable, Dict, List, Mapping, Sequence

from webeval.rubric_agent.dom_diff_text_grep_prompts import (
    RAW_DOM_DIFF_TOOL_GROUNDING_RULES,
    RAW_GREP_ANALYSIS_PROMPT,
    RAW_GREP_RELEVANCE_PROMPT,
)
from webeval.rubric_agent.dom_diff_text_grep_tools import (
    TOOL_SCHEMAS,
    GrepEvidenceExecutor,
    RawDOMDiffFrame,
    RawEvidenceBundle,
    assert_no_raw_evidence_in_initial_payload,
)
from webeval.rubric_agent.dom_diff_text_grep_transport import (
    append_assistant_tool_calls,
    append_tool_output,
    context_limit,
    count_request_tokens,
    normalize_tool_calls,
)
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgent


logger = logging.getLogger(__name__)
_EVIDENCE_STATUSES = {"supported", "contradicted", "partial", "unknown"}


class DOMDiffTextGrepMMRubricAgent(MMRubricAgent):
    """Change only how raw DOM evidence reaches relevance and analysis."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._raw_bundle: RawEvidenceBundle | None = None
        self._grep_runtime_metrics: dict[str, Any] = {}
        self._reset_grep_metrics()

    def _setting(self, name: str, default: Any) -> Any:
        return getattr(self.config, name, default)

    def _reset_grep_metrics(self) -> None:
        self._grep_runtime_metrics = {
            "evidence_source": "raw_dom_diff_text_tools",
            "schema_version": str(
                self._setting(
                    "evidence_schema_version", "runner-dom-diff-text-grep/v1"
                )
            ),
            "model_calls": [],
            "tool_calls": [],
            "stages": {},
            "criterion_frame_assignments": {},
            "retrieval_degraded": False,
            "failure_reasons": [],
        }

    def grep_runtime_metrics(self, *, include_traces: bool = True) -> dict[str, Any]:
        value = copy.deepcopy(self._grep_runtime_metrics)
        if not include_traces:
            value.pop("model_calls", None)
            value.pop("tool_calls", None)
        return value

    @property
    def raw_bundle(self) -> RawEvidenceBundle:
        if self._raw_bundle is None:
            raise RuntimeError("Raw evidence bundle has not been loaded")
        return self._raw_bundle

    def _load_dom_evidence(
        self, dom_actions: list[dict[str, Any]]
    ) -> list[RawDOMDiffFrame]:
        self._reset_grep_metrics()
        self._raw_bundle = RawEvidenceBundle.from_dom_actions(dom_actions)
        frames = self._raw_bundle.frames()
        if self.config.dom_top_k is not None:
            frames = frames[: self.config.dom_top_k]
            allowed = {frame.file_id for frame in frames}
            self._raw_bundle = RawEvidenceBundle(
                self._raw_bundle.task_id,
                [item for item in self._raw_bundle.files if item.file_id in allowed],
            )
        self._grep_runtime_metrics["source_files"] = self.raw_bundle.audit_metadata()
        self._grep_runtime_metrics["raw_source_bytes"] = sum(
            item.source_bytes for item in self.raw_bundle.files
        )
        return frames

    async def _generate_dom_retrieval_terms(
        self,
        frames: list[RawDOMDiffFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
        predicted_output: str,
    ) -> list[str]:
        del frames, rubric, task, init_url_context, predicted_output
        return []

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

    def _tool_executor(
        self, *, allowed_file_ids: Sequence[str] | None = None
    ) -> GrepEvidenceExecutor:
        return GrepEvidenceExecutor(
            self.raw_bundle,
            allowed_file_ids=allowed_file_ids,
            max_result_chars=int(self._setting("grep_max_result_chars", 8000)),
            max_matches=int(self._setting("grep_max_matches", 100)),
            regex_timeout_seconds=float(
                self._setting("grep_regex_timeout_seconds", 2.0)
            ),
        )

    def build_relevance_initial_messages(
        self,
        rubric: dict,
        task: str,
        init_url_context: str,
    ) -> list[dict[str, Any]]:
        prompt = RAW_GREP_RELEVANCE_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            file_manifest=self.raw_bundle.manifest(),
            rubric_criteria=self._rubric_text(rubric),
            grounding_rules=RAW_DOM_DIFF_TOOL_GROUNDING_RULES,
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        assert_no_raw_evidence_in_initial_payload(
            {"messages": messages, "tools": TOOL_SCHEMAS}, self.raw_bundle
        )
        return messages

    @staticmethod
    def render_allowed_frames(
        assignments: Mapping[int, Sequence[int]]
    ) -> str:
        return "\n".join(
            f"C{criterion_idx}={list(frame_indices)}"
            for criterion_idx, frame_indices in sorted(assignments.items())
        )

    def build_analysis_initial_messages(
        self,
        *,
        rubric: dict,
        criterion_frame_assignments: Mapping[int, Sequence[int]],
        task: str,
        init_url_context: str,
        action_history: str,
        predicted_output: str,
    ) -> list[dict[str, Any]]:
        selected = sorted(
            {
                frame_idx
                for indices in criterion_frame_assignments.values()
                for frame_idx in indices
            }
        )
        file_ids = [self.raw_bundle.files[index].file_id for index in selected]
        criteria_block, _ = self._criteria_block(
            rubric, list(range(len(rubric["items"])))
        )
        prompt = RAW_GREP_ANALYSIS_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            file_manifest=self.raw_bundle.manifest(file_ids),
            allowed_frames=self.render_allowed_frames(
                criterion_frame_assignments
            ),
            criteria_info_block=criteria_block,
            grounding_rules=RAW_DOM_DIFF_TOOL_GROUNDING_RULES,
        )
        messages = self.DEFAULT_SYSTEM_MESSAGES + [{"role": "user", "content": prompt}]
        assert_no_raw_evidence_in_initial_payload(
            {"messages": messages, "tools": TOOL_SCHEMAS}, self.raw_bundle
        )
        return messages

    @staticmethod
    def _usage_dict(result: Any) -> dict[str, int]:
        usage = getattr(result, "usage", None)
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "reasoning_tokens": int(getattr(usage, "reasoning_tokens", 0) or 0),
        }

    def _degrade(self, stage: str, reason: str) -> None:
        self._grep_runtime_metrics["retrieval_degraded"] = True
        self._grep_runtime_metrics["failure_reasons"].append(
            {"stage": stage, "reason": reason}
        )

    async def _run_tool_session(
        self,
        *,
        stage: str,
        messages: list[dict[str, Any]],
        executor: GrepEvidenceExecutor,
        validator: Callable[[str, set[int]], Any],
    ) -> Any:
        max_rounds = int(self._setting("grep_max_tool_rounds", 12))
        max_calls = int(self._setting("grep_max_tool_calls", 40))
        stage_metrics = {
            "rounds": 0,
            "tool_calls": 0,
            "validation_attempts": 0,
            "validation_failures": [],
            "context_limit_events": [],
        }
        self._grep_runtime_metrics["stages"][stage] = stage_metrics
        total_tool_calls = 0
        for turn in range(1, max_rounds + 1):
            estimated_tokens = count_request_tokens(
                self._gpt5_client, messages, TOOL_SCHEMAS
            )
            limit = context_limit(self._gpt5_client)
            if estimated_tokens >= limit:
                reason = (
                    f"{stage} request estimated at {estimated_tokens} tokens "
                    f"against context limit {limit}"
                )
                stage_metrics["context_limit_events"].append(reason)
                self._degrade(stage, reason)
                raise RuntimeError(reason)
            request_messages = copy.deepcopy(messages)
            result = await self._gpt5_client.create(
                messages=messages,
                tools=TOOL_SCHEMAS,
                json_output=True,
            )
            stage_metrics["rounds"] = turn
            call_record = {
                "stage": stage,
                "turn": turn,
                "request_estimated_tokens": estimated_tokens,
                "request_messages": request_messages,
                "tools": copy.deepcopy(TOOL_SCHEMAS),
                "response_content": str(getattr(result, "content", "") or ""),
                "finish_reason": getattr(result, "finish_reason", None),
                "usage": self._usage_dict(result),
            }
            self._grep_runtime_metrics["model_calls"].append(call_record)
            try:
                calls = normalize_tool_calls(result)
            except Exception as exc:
                error = f"Invalid tool call: {type(exc).__name__}: {exc}"
                stage_metrics["validation_failures"].append(error)
                messages.append({"role": "user", "content": error})
                continue
            if calls:
                if total_tool_calls + len(calls) > max_calls:
                    reason = (
                        f"{stage} exceeded maximum {max_calls} evidence tool calls"
                    )
                    self._degrade(stage, reason)
                    raise RuntimeError(reason)
                family = append_assistant_tool_calls(messages, result, calls)
                for call in calls:
                    output_value = executor.execute(call.name, call.arguments)
                    output = json.dumps(
                        output_value,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    append_tool_output(
                        messages,
                        family=family,
                        call_id=call.call_id,
                        output=output,
                    )
                    total_tool_calls += 1
                    self._grep_runtime_metrics["tool_calls"].append(
                        {
                            "stage": stage,
                            "turn": turn,
                            "call_id": call.call_id,
                            "tool": call.name,
                            "arguments": copy.deepcopy(call.arguments),
                            "output": output_value,
                            "result_chars": len(output),
                            "estimated_result_tokens": max(1, len(output) // 4),
                        }
                    )
                stage_metrics["tool_calls"] = total_tool_calls
                continue
            stage_metrics["validation_attempts"] += 1
            try:
                value = validator(
                    str(getattr(result, "content", "") or ""),
                    set(executor.frames_returned),
                )
                stage_metrics["coverage"] = executor.coverage_receipt()
                stage_metrics["status"] = "ok"
                return value
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                stage_metrics["validation_failures"].append(
                    {
                        "error": error,
                        "raw_rejected_response": str(
                            getattr(result, "content", "") or ""
                        ),
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Validation error: {exc}. Correct the complete JSON "
                            "response without inventing or remapping FRAME values."
                        ),
                    }
                )
        reason = f"{stage} exhausted {max_rounds} tool/model rounds"
        self._degrade(stage, reason)
        stage_metrics["status"] = "failed"
        stage_metrics["coverage"] = executor.coverage_receipt()
        raise RuntimeError(reason)

    def _validate_relevance_response(
        self,
        raw_text: str,
        retrieved_frames: set[int],
        *,
        frame_count: int,
        criterion_count: int,
    ) -> Dict[int, Dict]:
        if not retrieved_frames:
            raise ValueError("Relevance must use at least one successful evidence tool result")
        raw = json.loads(raw_text)
        rows = raw.get("frames") if isinstance(raw, dict) else None
        if not isinstance(rows, list) or len(rows) != frame_count:
            raise ValueError(f"Expected exactly {frame_count} relevance rows")
        result: Dict[int, Dict] = {}
        for expected_idx, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"FRAME {expected_idx} relevance row must be an object")
            returned_idx = row.get("evidence_idx")
            if isinstance(returned_idx, bool) or not isinstance(returned_idx, int):
                raise ValueError(f"FRAME {expected_idx} evidence_idx must be an integer")
            if returned_idx != expected_idx:
                raise ValueError(
                    f"Expected evidence_idx={expected_idx}, got {returned_idx}"
                )
            normalized: Dict[Any, Any] = {}
            for criterion_idx in range(criterion_count):
                key = f"criterion_{criterion_idx}"
                value = row.get(key)
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(f"{key} must be an integer")
                if not 0 <= value <= 10:
                    raise ValueError(f"{key} score outside [0,10]")
                normalized[criterion_idx] = value
            normalized.update(
                screenshot_idx=expected_idx,
                evidence_idx=expected_idx,
            )
            result[expected_idx] = normalized
        return result

    async def _score_dom_criterion_relevance(
        self,
        frames: list[RawDOMDiffFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
        retrieval_terms: list[str] | None = None,
    ) -> Dict[int, Dict]:
        del retrieval_terms
        messages = self.build_relevance_initial_messages(
            rubric, task, init_url_context
        )
        executor = self._tool_executor()
        try:
            result = await self._run_tool_session(
                stage="grep_relevance",
                messages=messages,
                executor=executor,
                validator=lambda text, retrieved: self._validate_relevance_response(
                    text,
                    retrieved,
                    frame_count=len(frames),
                    criterion_count=len(rubric["items"]),
                ),
            )
            self._grep_runtime_metrics["relevance_matrix"] = copy.deepcopy(result)
            return result
        except Exception as exc:
            logger.warning("Raw grep relevance failed: %s", exc)
            self._degrade("grep_relevance", str(exc))
            return {
                frame_idx: {
                    **{idx: 0 for idx in range(len(rubric["items"]))},
                    "screenshot_idx": frame_idx,
                    "evidence_idx": frame_idx,
                }
                for frame_idx in range(len(frames))
            }

    def _validate_analysis_response(
        self,
        raw_text: str,
        retrieved_frames: set[int],
        *,
        rubric: dict,
        assignments: Mapping[int, Sequence[int]],
    ) -> Dict[int, List[Dict]]:
        if not retrieved_frames:
            raise ValueError("Analysis must use at least one successful evidence tool result")
        criterion_indices = list(range(len(rubric["items"])))
        _, conditional = self._criteria_block(rubric, criterion_indices)
        raw = json.loads(raw_text)
        analyses = self._normalize_batched_analysis_response(raw, criterion_indices)
        if analyses is None or len(analyses) != len(criterion_indices):
            raise ValueError(
                f"Expected exactly {len(criterion_indices)} analysis entries"
            )
        errors: list[str] = []
        validated: list[tuple[int, dict[str, Any], list[int]]] = []
        for position, expected_idx in enumerate(criterion_indices):
            analysis = analyses[position]
            if not isinstance(analysis, dict):
                errors.append(f"Criterion {expected_idx}: analysis must be an object")
                continue
            returned_idx = analysis.get("criterion_idx", expected_idx)
            if returned_idx != expected_idx:
                errors.append(
                    f"Criterion {expected_idx}: got criterion_idx={returned_idx}"
                )
            status = str(analysis.get("evidence_status") or "")
            if status not in _EVIDENCE_STATUSES:
                errors.append(
                    f"Criterion {expected_idx}: invalid evidence_status {status!r}"
                )
            returned = analysis.get("evidence_indices")
            normalized: list[int] = []
            if not isinstance(returned, list):
                errors.append(
                    f"Criterion {expected_idx}: evidence_indices must be a list"
                )
            else:
                for value in returned:
                    if isinstance(value, bool) or not isinstance(value, int):
                        errors.append(
                            f"Criterion {expected_idx}: FRAME values must be integers"
                        )
                    else:
                        normalized.append(value)
            allowed = list(assignments.get(expected_idx, []))
            invalid = sorted(set(normalized) - set(allowed))
            if invalid:
                errors.append(
                    f"Criterion {expected_idx} cited invalid FRAME {invalid}. "
                    f"Allowed FRAME values are {allowed}."
                )
            unretrieved = sorted(set(normalized) - retrieved_frames)
            if unretrieved:
                errors.append(
                    f"Criterion {expected_idx} cited FRAME {unretrieved} without "
                    "a successful analysis-stage tool result."
                )
            candidate = copy.deepcopy(analysis)
            candidate.pop("criterion_idx", None)
            candidate.pop("evidence_indices", None)
            self._dual_write_evidence_fields(candidate)
            try:
                self._validate_evidence_analysis(
                    candidate, expected_idx in conditional
                )
            except Exception as exc:
                errors.append(f"Criterion {expected_idx}: {exc}")
            validated.append((expected_idx, candidate, normalized))
        if errors:
            raise ValueError(" ".join(errors))
        result: Dict[int, List[Dict]] = {idx: [] for idx in criterion_indices}
        for criterion_idx, analysis, indices in validated:
            allowed = list(assignments.get(criterion_idx, []))
            frame_idx = indices[0] if indices else (allowed[0] if allowed else 0)
            analysis["evidence_idx"] = frame_idx
            analysis["screenshot_idx"] = frame_idx
            analysis["evidence_indices"] = indices
            analysis["steps"] = [
                self.raw_bundle.files[index].action_ordinal for index in indices
            ]
            result[criterion_idx].append(analysis)
        return result

    def _unknown_analysis_results(
        self,
        rubric: dict,
        assignments: Mapping[int, Sequence[int]],
    ) -> Dict[int, List[Dict]]:
        result: Dict[int, List[Dict]] = {}
        for criterion_idx, item in enumerate(rubric["items"]):
            allowed = list(assignments.get(criterion_idx, []))
            frame_idx = allowed[0] if allowed else 0
            step = (
                self.raw_bundle.files[frame_idx].action_ordinal
                if self.raw_bundle.files
                else 0
            )
            result[criterion_idx] = [
                {
                    "evidence_status": "unknown",
                    "evidence_text": "Raw DOM-diff tool analysis unavailable",
                    "screenshot_evidence": "Raw DOM-diff tool analysis unavailable",
                    "criterion_analysis": (
                        "Unknown because raw evidence could not be retrieved "
                        "and validated"
                    ),
                    "discrepancies": "Unknown",
                    "environment_issues_confirmed": False,
                    "evidence_idx": frame_idx,
                    "screenshot_idx": frame_idx,
                    "evidence_indices": [],
                    "steps": [step],
                    **(
                        {"condition_verification": False}
                        if "condition" in item
                        else {}
                    ),
                }
            ]
        return result

    async def _analyze_dom_evidence_batched(
        self,
        frames: list[RawDOMDiffFrame],
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
        del frames, retrieval_terms
        assignments = {
            criterion_idx: list(indices)
            for criterion_idx, indices in grouped_frames.items()
        }
        if min_relevance_threshold and relevance_scores is not None:
            assignments = {
                criterion_idx: [
                    frame_idx
                    for frame_idx in indices
                    if relevance_scores.get(frame_idx, {}).get(criterion_idx, 0)
                    > min_relevance_threshold
                ]
                for criterion_idx, indices in assignments.items()
            }
        assignments = {
            idx: list(assignments.get(idx, []))
            for idx in range(len(rubric["items"]))
        }
        self._grep_runtime_metrics["criterion_frame_assignments"] = copy.deepcopy(
            assignments
        )
        selected_frames = sorted(
            {frame_idx for indices in assignments.values() for frame_idx in indices}
        )
        self._grep_runtime_metrics["selected_frame_union"] = selected_frames
        if not selected_frames:
            self._degrade("grep_analysis", "No frames survived shared selection")
            return self._unknown_analysis_results(rubric, assignments)
        selected_file_ids = [
            self.raw_bundle.files[index].file_id for index in selected_frames
        ]
        messages = self.build_analysis_initial_messages(
            rubric=rubric,
            criterion_frame_assignments=assignments,
            task=task,
            init_url_context=init_url_context,
            action_history=action_history,
            predicted_output=predicted_output,
        )
        executor = self._tool_executor(allowed_file_ids=selected_file_ids)
        try:
            return await self._run_tool_session(
                stage="grep_analysis",
                messages=messages,
                executor=executor,
                validator=lambda text, retrieved: self._validate_analysis_response(
                    text,
                    retrieved,
                    rubric=rubric,
                    assignments=assignments,
                ),
            )
        except Exception as exc:
            logger.warning("Raw grep analysis failed: %s", exc)
            self._degrade("grep_analysis", str(exc))
            return self._unknown_analysis_results(rubric, assignments)

    @staticmethod
    def _build_all_screenshot_evidence_text(
        rubric: dict,
        evidence_by_criterion: Dict[int, List[Dict]],
        total_screenshots: int,
        evidence_mode: str = "dom",
    ) -> str:
        del evidence_mode
        lines: list[str] = [RAW_DOM_DIFF_TOOL_GROUNDING_RULES, ""]
        for criterion_idx, criterion in enumerate(rubric["items"]):
            lines.append(
                f'## Criterion {criterion_idx}: "'
                f'{criterion.get("criterion", f"Criterion {criterion_idx}")}"'
            )
            analyses = evidence_by_criterion.get(criterion_idx, [])
            if not analyses:
                lines.extend(
                    ["No raw DOM-diff tool evidence was selected.", ""]
                )
                continue
            for analysis in sorted(
                analyses, key=lambda item: item.get("evidence_idx", 0)
            ):
                lines.extend(
                    [
                        f"### Raw DOM tool evidence of {total_screenshots} frames:",
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
