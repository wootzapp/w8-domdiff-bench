"""Evidence-specific agent for the isolated DOM-diff-only ablation."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from webeval.rubric_agent.dom_diff_evidence import (
    DOMDiffEvidenceFrame,
    load_dom_diff_frames,
    project_dom_diff_frame,
    summarize_diff,
)
from webeval.rubric_agent.dom_diff_prompts import (
    DOM_DIFF_BATCHED_EVIDENCE_ANALYSIS_PROMPT,
    DOM_DIFF_CRITERION_RELEVANCE_PROMPT,
    DOM_DIFF_GROUNDING_RULES,
)
from webeval.rubric_agent.dom_evidence import build_dom_retrieval_terms
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgent


logger = logging.getLogger(__name__)
_EVIDENCE_STATUSES = {"supported", "contradicted", "partial", "unknown"}


class DOMDiffMMRubricAgent(MMRubricAgent):
    """Reuse Universal Verifier scoring while replacing only evidence stages."""

    def _load_dom_evidence(
        self, dom_actions: list[dict[str, Any]]
    ) -> list[DOMDiffEvidenceFrame]:
        frames = load_dom_diff_frames(dom_actions)
        if self.config.dom_top_k is not None:
            frames = frames[: self.config.dom_top_k]
        return frames

    def _compact_dom_trajectory_metadata(
        self, frames: list[DOMDiffEvidenceFrame], *, limit: int = 12000
    ) -> str:
        rows = [
            {
                "step": frame.action_ordinal,
                "schema": frame.schema_version,
                "method": frame.method,
                "capture": frame.capture_status,
                "explicit_change_summary": summarize_diff(frame.diff),
                "omissions": [
                    "before_snapshot",
                    "after_snapshot",
                    "page_state",
                    "screenshot",
                ],
            }
            for frame in frames
        ]
        text = json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2)
        return text if len(text) <= limit else text[: limit - 1] + "…"

    async def _score_dom_criterion_relevance(
        self,
        frames: list[DOMDiffEvidenceFrame],
        rubric: dict,
        task: str,
        init_url_context: str,
        retrieval_terms: list[str] | None = None,
    ) -> Dict[int, Dict]:
        rubric_text = "".join(
            f"\n{idx}. **{item['criterion']}**\n"
            f"   Description: {item['description']}\n"
            for idx, item in enumerate(rubric["items"])
        )
        if retrieval_terms is None:
            retrieval_terms = build_dom_retrieval_terms(
                task=task, rubric_items=rubric.get("items", [])
            )
        projections = [
            project_dom_diff_frame(
                frame,
                terms=retrieval_terms,
                frame_char_budget=min(
                    self.config.dom_frame_char_budget,
                    self.config.dom_context_char_budget,
                ),
            )
            for frame in frames
        ]
        criterion_count = len(rubric["items"])

        async def score_frame(frame_idx: int, frame_text: str) -> Dict:
            prompt = DOM_DIFF_CRITERION_RELEVANCE_PROMPT.substitute(
                task_definition=task,
                init_url_context=init_url_context,
                dom_diff_frame=frame_text,
                rubric_criteria=rubric_text,
                grounding_rules=DOM_DIFF_GROUNDING_RULES,
            )
            messages = self.DEFAULT_SYSTEM_MESSAGES + [
                {"role": "user", "content": prompt}
            ]
            last_error: Exception | None = None
            for _ in range(self.config.max_iters):
                try:
                    raw = json.loads(
                        await self._call_llm(
                            messages, self._gpt5_client, json_output=True
                        )
                    )
                    result: Dict[Any, Any] = {}
                    for criterion_idx in range(criterion_count):
                        keys = (
                            f"criterion_{criterion_idx}",
                            str(criterion_idx),
                            criterion_idx,
                        )
                        found = next((raw[key] for key in keys if key in raw), None)
                        score = int(found)
                        if not 0 <= score <= 10:
                            raise ValueError(
                                f"criterion_{criterion_idx} score outside [0, 10]"
                            )
                        result[criterion_idx] = score
                    result["screenshot_idx"] = frame_idx
                    result["evidence_idx"] = frame_idx
                    return result
                except Exception as exc:
                    last_error = exc
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Error: {exc}. Return scores for all "
                                f"{criterion_count} criteria as JSON."
                            ),
                        }
                    )
            logger.warning(
                "DOM-diff relevance failed for frame %s: %s", frame_idx, last_error
            )
            return {
                **{idx: 0 for idx in range(criterion_count)},
                "screenshot_idx": frame_idx,
                "evidence_idx": frame_idx,
            }

        results = await asyncio.gather(
            *(score_frame(idx, text) for idx, text in enumerate(projections))
        )
        return {result["evidence_idx"]: result for result in results}

    async def _analyze_dom_evidence_batched(
        self,
        frames: list[DOMDiffEvidenceFrame],
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
        frame_to_criteria = self._invert_grouped_screenshots(grouped_frames)
        if retrieval_terms is None:
            retrieval_terms = build_dom_retrieval_terms(
                task=task,
                rubric_items=rubric.get("items", []),
                predicted_output=predicted_output,
            )
        projections = [
            project_dom_diff_frame(
                frame,
                terms=retrieval_terms,
                frame_char_budget=min(
                    self.config.dom_frame_char_budget,
                    self.config.dom_context_char_budget,
                ),
            )
            for frame in frames
        ]

        async def analyze(frame_idx: int, criterion_indices: List[int]):
            if min_relevance_threshold and relevance_scores is not None:
                criterion_indices = [
                    idx
                    for idx in criterion_indices
                    if relevance_scores.get(frame_idx, {}).get(idx, 0)
                    > min_relevance_threshold
                ]
            if not criterion_indices:
                return []

            criteria_text = ""
            conditional: set[int] = set()
            for idx in criterion_indices:
                item = rubric["items"][idx]
                criteria_text += (
                    f"\n**Criterion {idx}:** {item['criterion']}\n"
                    f"**Description:** {item['description']}\n"
                    f"**Max Points:** {item['max_points']}\n"
                )
                if "condition" in item:
                    conditional.add(idx)
                    criteria_text += (
                        f'**CONDITIONAL:** "{item["condition"]}"; include '
                        "condition_verification.\n"
                    )

            prompt = DOM_DIFF_BATCHED_EVIDENCE_ANALYSIS_PROMPT.substitute(
                task_definition=task,
                init_url_context=init_url_context,
                action_history=action_history,
                agent_predicted_output=predicted_output,
                dom_diff_frame=projections[frame_idx],
                criteria_info_block=criteria_text,
                grounding_rules=DOM_DIFF_GROUNDING_RULES,
            )
            messages = self.DEFAULT_SYSTEM_MESSAGES + [
                {"role": "user", "content": prompt}
            ]
            last_error: Exception | None = None
            for _ in range(self.config.max_iters):
                try:
                    raw = json.loads(
                        await self._call_llm(
                            messages, self._gpt5_client, json_output=True
                        )
                    )
                    analyses = self._normalize_batched_analysis_response(
                        raw, criterion_indices
                    )
                    if analyses is None or len(analyses) != len(criterion_indices):
                        raise ValueError(
                            f"Expected {len(criterion_indices)} analysis entries"
                        )
                    output = []
                    for analysis, expected_idx in zip(analyses, criterion_indices):
                        returned_idx = analysis.pop("criterion_idx", expected_idx)
                        if returned_idx != expected_idx:
                            raise ValueError(
                                f"Expected criterion_idx={expected_idx}, got {returned_idx}"
                            )
                        status = str(analysis.get("evidence_status") or "")
                        if status not in _EVIDENCE_STATUSES:
                            raise ValueError(
                                f"Invalid evidence_status {status!r}; expected one of "
                                f"{sorted(_EVIDENCE_STATUSES)}"
                            )
                        self._dual_write_evidence_fields(analysis)
                        self._validate_evidence_analysis(
                            analysis, expected_idx in conditional
                        )
                        analysis["evidence_idx"] = frame_idx
                        analysis["screenshot_idx"] = frame_idx
                        output.append((expected_idx, analysis))
                    return output
                except Exception as exc:
                    last_error = exc
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Error: {exc}. Return exactly one valid analysis "
                                "per listed criterion."
                            ),
                        }
                    )

            logger.warning(
                "DOM-diff analysis failed for frame %s: %s", frame_idx, last_error
            )
            return [
                (
                    idx,
                    {
                        "evidence_status": "unknown",
                        "evidence_text": "Diff analysis unavailable",
                        "screenshot_evidence": "Diff analysis unavailable",
                        "criterion_analysis": (
                            "Unknown because explicit diff evidence could not be analyzed"
                        ),
                        "discrepancies": "Unknown",
                        "environment_issues_confirmed": False,
                        "evidence_idx": frame_idx,
                        "screenshot_idx": frame_idx,
                        **(
                            {"condition_verification": False}
                            if idx in conditional
                            else {}
                        ),
                    },
                )
                for idx in criterion_indices
            ]

        nested = await asyncio.gather(
            *(analyze(idx, criteria) for idx, criteria in frame_to_criteria.items())
        )
        result: Dict[int, List[Dict]] = {
            idx: [] for idx in range(len(rubric["items"]))
        }
        for entries in nested:
            for criterion_idx, analysis in entries:
                result[criterion_idx].append(analysis)
        return result

    @staticmethod
    def _build_all_screenshot_evidence_text(
        rubric: dict,
        evidence_by_criterion: Dict[int, List[Dict]],
        total_screenshots: int,
        evidence_mode: str = "dom",
    ) -> str:
        lines: list[str] = [DOM_DIFF_GROUNDING_RULES, ""]
        for criterion_idx, criterion in enumerate(rubric["items"]):
            lines.append(
                f'## Criterion {criterion_idx}: "{criterion.get("criterion", f"Criterion {criterion_idx}")}"'
            )
            analyses = evidence_by_criterion.get(criterion_idx, [])
            if not analyses:
                lines.extend(["No DOM diff evidence available for this criterion.", ""])
                continue
            for analysis in sorted(
                analyses, key=lambda item: item.get("evidence_idx", 0)
            ):
                frame_idx = analysis.get("evidence_idx", 0)
                lines.append(
                    f"### DOM diff {frame_idx + 1} of {total_screenshots} Analysis:"
                )
                lines.append(
                    f"**Evidence Status:** {analysis.get('evidence_status', 'unknown')}"
                )
                lines.append(
                    f"**Evidence:** {analysis.get('evidence_text', analysis.get('screenshot_evidence', 'N/A'))}"
                )
                lines.append(
                    f"**Analysis:** {analysis.get('criterion_analysis', 'N/A')}"
                )
                lines.append(
                    f"**Discrepancies:** {analysis.get('discrepancies', 'N/A')}"
                )
                lines.append(
                    "**Environment Issues Confirmed:** "
                    f"{analysis.get('environment_issues_confirmed', False)}"
                )
                lines.append("")
            lines.append("")
        return "\n".join(lines)
