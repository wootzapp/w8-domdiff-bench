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
    max_images_per_criterion: int = 5
    screenshots_dir: Optional[str] = None
    rescore_whole_mm_rubric: bool = True
    batch_screenshot_analysis: bool = True
    min_relevance_threshold: int = 0
    ignore_irrelevant_screenshots: bool = True
    majority_vote_instances: int = 1
    redo_eval: bool = False
    failure_analysis_only: bool = False
    rubric_score_threshold: float = 0.8
    max_iters: int = 2
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


_LOGICAL_STAGE_NAMES = {
    "screenshot_verifier": {
        "_load_evidence": "w8bench.verifier.screenshot_verifier.rubric_agent._load_screenshots",
        "_score_evidence_relevance": "w8bench.verifier.screenshot_verifier.rubric_agent._score_screenshot_criterion_relevance",
        "_analyze_evidence": "w8bench.verifier.screenshot_verifier.rubric_agent._analyze_screenshot_evidence",
        "_analyze_evidence_batched": "w8bench.verifier.screenshot_verifier.rubric_agent._analyze_screenshot_evidence_batched",
        "_encode_image": "w8bench.verifier.screenshot_verifier.rubric_agent._encode_image",
        "score_single_screenshot": "w8bench.verifier.screenshot_verifier.rubric_agent.score_single_screenshot",
        "analyze_single_pair": "w8bench.verifier.screenshot_verifier.rubric_agent.analyze_single_pair",
        "analyze_single_pair_for_batch": "w8bench.verifier.screenshot_verifier.rubric_agent.analyze_single_pair_for_batch",
        "analyze_multi_criteria_screenshot": "w8bench.verifier.screenshot_verifier.rubric_agent.analyze_multi_criteria_screenshot",
    }
}
_LOGICAL_STAGE_EXCLUDES = (
    "_action_records",
    "_conditional_evidence_text",
    "_reality_evidence_text",
    "_criterion_analyses_text",
    "_screenshot_index",
    "_load_screenshot_action",
    "_validate_screenshot_order",
    "_raise_screenshot_load_errors",
    "_image_messages",
    "_collect_relevance_value",
    "_relevance_scores",
    "_repair_relevance",
    "_pair_messages",
    "_pair_analysis",
    "_repair_pair",
    "_pair_failure",
    "_batch_messages",
    "_validate_batch_analyses",
    "_batch_analyses",
    "_repair_batch",
    "_batch_state_criteria",
)


def _screenshot_index(filename: str) -> int:
    match = re.search("screenshot_?(\\d+)", Path(filename).stem)
    return int(match.group(1)) if match else 0


def _load_screenshot_action(
    action, evidence_dir, evidence, native_ids, missing, load_errors, id_mismatches,
):
    screenshot_file = action.get("screenshot", "")
    if not screenshot_file:
        missing.append(f"Action {action.get('id')} has no screenshot field")
        return
    sid = _screenshot_index(screenshot_file)
    try:
        aid = int(action["id"])
    except (TypeError, ValueError, KeyError):
        raise ValueError(
            f"Action id '{action.get('id')}' is not an int (file: {screenshot_file})"
        )
    if aid != sid:
        id_mismatches.append(
            f"Action id {aid} does not match screenshot index {sid} (file: {screenshot_file})"
        )
    screenshot_path = Path(evidence_dir) / screenshot_file
    if not screenshot_path.exists():
        missing.append(
            f"Action {action.get('id')}: file does not exist at {screenshot_path}"
        )
        return
    try:
        img = Image.open(screenshot_path).convert("RGB").copy()
        if native_ids:
            evidence[action["state_id"]] = img
        else:
            evidence.append(img)
    except Exception as e:
        if isinstance(e, scoring.UngradedVerifierError):
            raise
        load_errors.append(f"Action {action.get('id')}: failed to load - {e}")


def _validate_screenshot_order(sorted_actions, native_ids, id_mismatches):
    if id_mismatches:
        raise ValueError(
            f"Screenshot-action ordering mismatch ({len(id_mismatches)}):\n"
            + "\n".join((f"  - {m}" for m in id_mismatches))
        )
    sorted_indices = sorted(
        (
            _screenshot_index(a.get("screenshot", ""))
            for a in sorted_actions
            if a.get("screenshot")
        )
    )
    if sorted_indices and (not native_ids):
        expected = list(
            range(sorted_indices[0], sorted_indices[0] + len(sorted_indices))
        )
        if sorted_indices != expected:
            raise ValueError(
                f"Screenshot indices not consecutive. Got {sorted_indices}, expected {expected}"
            )


def _raise_screenshot_load_errors(sorted_actions, evidence, missing, load_errors):
    if missing or load_errors:
        error_msg = f"Failed to load ALL screenshots. Expected {len(sorted_actions)}, got {len(evidence)}.\n"
        if missing:
            error_msg += (
                "Missing:\n" + "\n".join((f"  - {m}" for m in missing[:10])) + "\n"
            )
        if load_errors:
            error_msg += (
                "Errors:\n" + "\n".join((f"  - {m}" for m in load_errors[:10])) + "\n"
            )
        raise RuntimeError(error_msg)


class MMRubricAgent(RubricAgent):
    config_type = MMRubricAgentConfig
    logger = logging.getLogger(__name__)
    prompts = prompts
    task_verification_logger = logging.getLogger(__package__ + ".utils.validity")
    evidence_mode = "screenshot_verifier"
    score_field = "post_image_earned_points"
    justification_field = "post_image_justification"
    evidence_field = "screenshot_evidence"
    state_index_field = "screenshot_idx"
    evidence_dir_key = "screenshots_dir"
    evidence_limit_key = "max_images_per_criterion"
    batch_config_key = "batch_screenshot_analysis"
    filter_config_key = "ignore_irrelevant_screenshots"
    state_count_key = "step1_num_screenshots"
    grouped_states_key = "step3_grouped_screenshots"
    record_generation_trace = True
    criterion_evidence_placeholder = "concatenated_screenshot_analyses"
    all_evidence_placeholder = "all_screenshot_evidence"
    loading_evidence_log = "[Step 1/9] Loading screenshots..."
    grouping_evidence_log = "[Step 3/9] Grouping screenshots..."
    analyzing_evidence_log = "[Step 4/9] Analyzing screenshot evidence..."
    missing_evidence_message = "screenshots_dir is required for rubric evaluation."
    evidence_count_suffix = " screenshots"
    relevance_count_suffix = " screenshots)..."
    relevance_error_prefix = "Screenshot "
    index_error_prefix = "screenshot_idx mismatch: dict key is "
    relevance_key_prefix = "screenshot_"
    filtered_pairs_suffix = " irrelevant (criterion, screenshot) pairs before step 4"
    final_score_prefix = "Final Score (post-image): "
    DEFAULT_SYSTEM_MESSAGES = [
        {"role": "system", "content": "You are a helpful AI assistant."}
    ]

    def _image_messages(self, screenshot, prompt):
        img_b64 = self._encode_image(screenshot)
        messages = self.DEFAULT_SYSTEM_MESSAGES + [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        return messages

    @staticmethod
    def _collect_relevance_value(scores_dict, criterion_idx, result, invalid_values):
        key_variants = [f"criterion_{criterion_idx}", str(criterion_idx), criterion_idx]
        found = False
        for key in key_variants:
            if key in scores_dict:
                try:
                    score = int(scores_dict[key])
                    if 0 <= score <= 10:
                        result[criterion_idx] = score
                        found = True
                        break
                    else:
                        invalid_values.append(
                            f"criterion_{criterion_idx}: score {score} not in range [0, 10]"
                        )
                except (ValueError, TypeError):
                    invalid_values.append(
                        f"criterion_{criterion_idx}: value '{scores_dict[key]}' is not an integer"
                    )
        return found

    def _relevance_scores(self, scores_dict, num_criteria, screenshot_idx):
        result = {}
        missing_keys, invalid_values = ([], [])
        for criterion_idx in range(num_criteria):
            if not self._collect_relevance_value(
                scores_dict, criterion_idx, result, invalid_values
            ):
                missing_keys.append(f"criterion_{criterion_idx}")
        if missing_keys or invalid_values:
            error_msg = (
                f"Incomplete or invalid scores for screenshot {screenshot_idx}. "
            )
            if missing_keys:
                error_msg += f"Missing scores for: {', '.join(missing_keys)}. "
            if invalid_values:
                error_msg += f"Invalid values: {'; '.join(invalid_values)}. "
            error_msg += f"Expected scores for ALL {num_criteria} criteria (criterion_0 through criterion_{num_criteria - 1})."
            raise ValueError(error_msg)
        result[self.state_index_field] = screenshot_idx
        return result

    def _repair_relevance(
        self, messages, screenshot_idx, max_iters, num_criteria, e,
    ):
        self.logger.error(
            f"Error scoring screenshot {screenshot_idx} (attempt {self.config.max_iters + 1 - max_iters}): {e}"
        )
        messages.append(
            {
                "role": "user",
                "content": f"Error: {e}. Please provide scores for ALL {num_criteria} criteria using the exact format specified.",
            }
        )

    def _pair_messages(
        self, criterion_idx, criterion, screenshot, task, init_url_context,
        action_history, predicted_output,
    ):
        criterion_info = f"**Criterion {criterion_idx}:** {criterion['criterion']}\n"
        criterion_info += f"**Description:** {criterion['description']}\n"
        criterion_info += f"**Max Points:** {criterion['max_points']}"
        conditional_check = ""
        is_conditional = "condition" in criterion
        if is_conditional:
            conditional_check = f'\n\n5. **condition_verification**: This is a CONDITIONAL criterion that only applies if: "{criterion["condition"]}"\n   Based on what you see in the screenshot, verify whether this condition is actually met.\n   - Output true if the condition IS met (criterion should be evaluated)\n   - Output false if the condition is NOT met (criterion should be skipped)'
        prompt = Template(
            self.prompts.MM_SCREENSHOT_EVIDENCE_ANALYSIS_PROMPT
        ).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            criterion_info=criterion_info,
            conditional_check=conditional_check,
        )
        return (self._image_messages(screenshot, prompt), is_conditional)

    def _pair_analysis(
        self, response_text, is_conditional, screenshot_idx, evidence,
    ):
        analysis = json.loads(response_text)
        scoring.validate_evidence_analysis(
            analysis, is_conditional, evidence_mode=self.evidence_mode
        )
        analysis[self.state_index_field] = screenshot_idx
        if isinstance(evidence, dict):
            analysis["source_state_id"] = screenshot_idx
        return analysis

    def _repair_pair(
        self, messages, criterion_idx, screenshot_idx, max_iters, e,
    ):
        self.logger.error(
            f"Error analyzing criterion {criterion_idx}, screenshot {screenshot_idx} (attempt {self.config.max_iters + 1 - max_iters}): {e}"
        )
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Error: {e}. Include nonempty screenshot_evidence, criterion_analysis and "
                    "discrepancies strings, and boolean environment_issues_confirmed. Use 'None.' "
                    "for discrepancies only when no mismatch was found. Include boolean "
                    "condition_verification for a conditional criterion."
                ),
            }
        )

    def _pair_failure(self, screenshot_idx, evidence):
        return {
            self.evidence_field: f"Error: Analysis failed after {self.config.max_iters} attempts",
            "criterion_analysis": "Unable to analyze due to repeated errors",
            "discrepancies": "N/A",
            "environment_issues_confirmed": False,
            self.state_index_field: screenshot_idx,
            **(
                {"source_state_id": screenshot_idx}
                if isinstance(evidence, dict)
                else {}
            ),
        }

    def _batch_messages(
        self, screenshot, criterion_indices, rubric, task, init_url_context,
        action_history, predicted_output,
    ):
        criteria_info_block = ""
        conditional_criteria = set()
        for c_idx in criterion_indices:
            criterion = rubric["items"][c_idx]
            criteria_info_block += (
                f"\n**Criterion {c_idx}:** {criterion['criterion']}\n"
            )
            criteria_info_block += f"**Description:** {criterion['description']}\n"
            criteria_info_block += f"**Max Points:** {criterion['max_points']}\n"
            if "condition" in criterion:
                conditional_criteria.add(c_idx)
                criteria_info_block += f'**CONDITIONAL:** This criterion only applies if: "{criterion["condition"]}". You MUST include "condition_verification": true/false in the output for this criterion.\n'
        prompt = Template(
            self.prompts.MM_SCREENSHOT_BATCHED_EVIDENCE_ANALYSIS_PROMPT
        ).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            criteria_info_block=criteria_info_block,
        )
        return (self._image_messages(screenshot, prompt), conditional_criteria)

    def _validate_batch_analyses(
        self, analyses, criterion_indices, conditional_criteria
    ):
        for i, (analysis, expected_c_idx) in enumerate(
            zip(analyses, criterion_indices)
        ):
            if not isinstance(analysis, dict):
                raise ValueError(f"Entry {i} is not a dict")
            returned_idx = analysis.get("criterion_idx")
            if returned_idx is None:
                analysis["criterion_idx"] = expected_c_idx
            elif returned_idx != expected_c_idx:
                raise ValueError(
                    f"Entry {i}: expected criterion_idx={expected_c_idx}, got {returned_idx}"
                )
            is_conditional = expected_c_idx in conditional_criteria
            scoring.validate_evidence_analysis(
                analysis, is_conditional, evidence_mode=self.evidence_mode
            )

    def _batch_analyses(
        self, response_text, criterion_indices, conditional_criteria, screenshot_idx,
        evidence,
    ):
        analyses = json.loads(response_text)
        analyses = scoring.normalize_batched_analysis_response(
            analyses, criterion_indices, evidence_mode=self.evidence_mode
        )
        if analyses is None or len(analyses) != len(criterion_indices):
            raise ValueError(
                f"Expected {len(criterion_indices)} entries, got {(len(analyses) if analyses else 'None')}"
            )
        self._validate_batch_analyses(analyses, criterion_indices, conditional_criteria)
        results = []
        for analysis, expected_c_idx in zip(analyses, criterion_indices):
            analysis.pop("criterion_idx", None)
            analysis[self.state_index_field] = screenshot_idx
            if isinstance(evidence, dict):
                analysis["source_state_id"] = screenshot_idx
            results.append((expected_c_idx, analysis))
        return results

    def _repair_batch(
        self, messages, screenshot_idx, criterion_indices, max_iters, e,
    ):
        self.logger.error(
            f"Error analyzing screenshot {screenshot_idx} (criteria {criterion_indices}, attempt {self.config.max_iters + 1 - max_iters}): {e}"
        )
        messages.append(
            {
                "role": "user",
                "content": (
                    f'Error: {e}. Return a JSON object with an "analyses" list containing exactly '
                    f'{len(criterion_indices)} ordered entries for criterion indices {criterion_indices}. '
                    'Each entry needs its criterion_idx, nonempty screenshot_evidence, criterion_analysis and discrepancies '
                    "strings, and boolean environment_issues_confirmed. Use 'None.' for discrepancies "
                    'only when no mismatch was found. Include boolean condition_verification for '
                    'conditional criteria. Analyze the attached screenshot image.'
                ),
            }
        )

    def _batch_state_criteria(
        self, grouped_evidence, relevance_scores, min_relevance_threshold
    ):
        screenshots_to_criteria = self._invert_grouped_evidence(grouped_evidence)
        if min_relevance_threshold > 0 and relevance_scores is not None:
            for s_idx in list(screenshots_to_criteria.keys()):
                scores = relevance_scores.get(s_idx, {})
                filtered = [
                    c
                    for c in screenshots_to_criteria[s_idx]
                    if scores.get(c, 0) > min_relevance_threshold
                ]
                if filtered:
                    screenshots_to_criteria[s_idx] = filtered
                else:
                    del screenshots_to_criteria[s_idx]
        return screenshots_to_criteria

    @staticmethod
    def _load_evidence(
        evidence_dir: str, actions_list: list
    ) -> List[Any] | Dict[int, Any]:
        sorted_actions = sorted(
            actions_list, key=lambda a: _screenshot_index(str(a.get("screenshot", "")))
        )
        native_ids = any(("state_id" in action for action in sorted_actions))
        evidence = {} if native_ids else []
        missing, load_errors, id_mismatches = ([], [], [])
        for action in sorted_actions:
            _load_screenshot_action(
                action,
                evidence_dir,
                evidence,
                native_ids,
                missing,
                load_errors,
                id_mismatches,
            )
        _validate_screenshot_order(sorted_actions, native_ids, id_mismatches)
        _raise_screenshot_load_errors(sorted_actions, evidence, missing, load_errors)
        if len(evidence) != len(sorted_actions):
            raise RuntimeError(
                f"Screenshot count mismatch: expected {len(sorted_actions)}, loaded {len(evidence)}"
            )
        return evidence

    async def score_single_screenshot(
        self, screenshot_idx, screenshot, rubric_criteria_text, num_criteria, task,
        init_url_context,
    ):
        prompt = Template(
            self.prompts.MM_SCREENSHOT_CRITERION_RELEVANCE_PROMPT
        ).substitute(
            task_definition=task,
            init_url_context=init_url_context,
            rubric_criteria=rubric_criteria_text,
        )
        messages = self._image_messages(screenshot, prompt)
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                response_text = await self._call_llm(
                    messages, self._judge_client, json_output=True
                )
                return self._relevance_scores(
                    json.loads(response_text), num_criteria, screenshot_idx
                )
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self._repair_relevance(
                    messages, screenshot_idx, max_iters, num_criteria, e
                )
                max_iters -= 1
        self.logger.warning(
            f"Failed to score screenshot {screenshot_idx} after {self.config.max_iters} attempts. Last error: {last_error}"
        )
        fallback = {i: 0 for i in range(num_criteria)}
        fallback[self.state_index_field] = screenshot_idx
        return fallback

    async def _score_evidence_relevance(
        self, evidence: List[Any] | Dict[int, Any], rubric: dict, task: str,
        init_url_context: str,
    ) -> Dict[int, Dict]:
        rubric_criteria_text = ""
        for idx, criterion in enumerate(rubric["items"]):
            rubric_criteria_text += f"\n{idx}. **{criterion['criterion']}**\n"
            rubric_criteria_text += f"   Description: {criterion['description']}\n"
        num_criteria = len(rubric["items"])
        tasks = [
            self.score_single_screenshot(
                idx, s, rubric_criteria_text, num_criteria, task, init_url_context
            )
            for idx, s in (
                evidence.items() if isinstance(evidence, dict) else enumerate(evidence)
            )
        ]
        results = await asyncio.gather(*tasks)
        return {r[self.state_index_field]: r for r in results}

    async def analyze_single_pair(
        self, criterion_idx, screenshot_idx, evidence, rubric, task, init_url_context,
        action_history, predicted_output,
    ):
        criterion = rubric["items"][criterion_idx]
        screenshot = evidence[screenshot_idx]
        messages, is_conditional = self._pair_messages(
            criterion_idx, criterion, screenshot, task, init_url_context,
            action_history, predicted_output,
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                response_text = await self._call_llm(
                    messages, self._judge_client, json_output=True
                )
                analysis = self._pair_analysis(
                    response_text, is_conditional, screenshot_idx, evidence
                )
                return (criterion_idx, analysis)
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self._repair_pair(messages, criterion_idx, screenshot_idx, max_iters, e)
                max_iters -= 1
        self.logger.warning(
            f"Failed to analyze criterion {criterion_idx}, screenshot {screenshot_idx} after {self.config.max_iters} attempts. Last error: {last_error}"
        )
        return (criterion_idx, self._pair_failure(screenshot_idx, evidence))

    async def analyze_single_pair_for_batch(
        self, criterion_idx, screenshot_idx, evidence, rubric, task, init_url_context,
        action_history, predicted_output,
    ):
        criterion = rubric["items"][criterion_idx]
        screenshot = evidence[screenshot_idx]
        messages, is_conditional = self._pair_messages(
            criterion_idx, criterion, screenshot, task, init_url_context,
            action_history, predicted_output,
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                response_text = await self._call_llm(
                    messages, self._judge_client, json_output=True
                )
                analysis = self._pair_analysis(
                    response_text, is_conditional, screenshot_idx, evidence
                )
                return [(criterion_idx, analysis)]
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self._repair_pair(messages, criterion_idx, screenshot_idx, max_iters, e)
                max_iters -= 1
        self.logger.warning(
            f"Failed to analyze criterion {criterion_idx}, screenshot {screenshot_idx} after {self.config.max_iters} attempts. Last error: {last_error}"
        )
        return [(criterion_idx, self._pair_failure(screenshot_idx, evidence))]

    async def _analyze_evidence(
        self, evidence: List[Any] | Dict[int, Any], rubric: dict,
        grouped_evidence: Dict[int, List[int]], task: str, init_url_context: str,
        action_history: str, predicted_output: str,
    ) -> Dict[int, List[Dict]]:
        all_tasks = []
        for c_idx, s_indices in grouped_evidence.items():
            for s_idx in s_indices:
                all_tasks.append(
                    self.analyze_single_pair(
                        c_idx, s_idx, evidence, rubric, task, init_url_context,
                        action_history, predicted_output,
                    )
                )
        results = await asyncio.gather(*all_tasks)
        evidence_by_criterion: Dict[int, List[Dict]] = {
            i: [] for i in range(len(rubric["items"]))
        }
        for c_idx, analysis in results:
            evidence_by_criterion[c_idx].append(analysis)
        return evidence_by_criterion

    async def analyze_multi_criteria_screenshot(
        self, screenshot_idx, criterion_indices, evidence, rubric, task,
        init_url_context, action_history, predicted_output,
    ):
        screenshot = evidence[screenshot_idx]
        messages, conditional_criteria = self._batch_messages(
            screenshot, criterion_indices, rubric, task, init_url_context,
            action_history, predicted_output,
        )
        max_iters = self.config.max_iters
        last_error = None
        while max_iters > 0:
            try:
                response_text = await self._call_llm(
                    messages, self._judge_client, json_output=True
                )
                return self._batch_analyses(
                    response_text, criterion_indices, conditional_criteria,
                    screenshot_idx, evidence,
                )
            except Exception as e:
                if isinstance(e, scoring.UngradedVerifierError):
                    raise
                last_error = str(e)
                self._repair_batch(
                    messages, screenshot_idx, criterion_indices, max_iters, e
                )
                max_iters -= 1
        self.logger.warning(
            f"Batched analysis failed for screenshot {screenshot_idx} (criteria {criterion_indices}) after {self.config.max_iters} attempts. Falling back to per-pair calls. Last error: {last_error}"
        )
        fallback_tasks = [
            self.analyze_single_pair_for_batch(
                c, screenshot_idx, evidence, rubric, task, init_url_context,
                action_history, predicted_output,
            )
            for c in criterion_indices
        ]
        fallback_results = await asyncio.gather(*fallback_tasks)
        return [item for sublist in fallback_results for item in sublist]

    async def _analyze_evidence_batched(
        self, evidence: List[Any] | Dict[int, Any], rubric: dict,
        grouped_evidence: Dict[int, List[int]], task: str, init_url_context: str,
        action_history: str, predicted_output: str,
        relevance_scores: Dict[int, Dict] | None = None,
        min_relevance_threshold: int = 0,
    ) -> Dict[int, List[Dict]]:
        screenshots_to_criteria = self._batch_state_criteria(
            grouped_evidence, relevance_scores, min_relevance_threshold
        )
        all_tasks = []
        for s_idx, c_indices in screenshots_to_criteria.items():
            if len(c_indices) == 1:
                all_tasks.append(
                    self.analyze_single_pair_for_batch(
                        c_indices[0], s_idx, evidence, rubric, task, init_url_context,
                        action_history, predicted_output,
                    )
                )
            else:
                all_tasks.append(
                    self.analyze_multi_criteria_screenshot(
                        s_idx, c_indices, evidence, rubric, task, init_url_context,
                        action_history, predicted_output,
                    )
                )
        all_results = await asyncio.gather(*all_tasks)
        evidence_by_criterion: Dict[int, List[Dict]] = {
            i: [] for i in range(len(rubric["items"]))
        }
        for result_list in all_results:
            for c_idx, analysis in result_list:
                evidence_by_criterion[c_idx].append(analysis)
        return evidence_by_criterion

    @staticmethod
    def _action_records(summaries):
        return [
            {"id": s.index, "screenshot": s.screenshot_path.replace("_post.", "_pre.")}
            for s in summaries
        ]

    @staticmethod
    def _encode_image(image: Any) -> str:
        import base64

        if image.mode == "RGBA":
            image = image.convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

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
                key=lambda x: x.get("screenshot_idx", 0),
            ):
                sn = analysis.get(
                    "source_state_id", analysis.get("screenshot_idx", 0) + 1
                )
                conditional_criteria_with_evidence += (
                    f"\n### Screenshot {sn} Evidence:\n"
                )
                conditional_criteria_with_evidence += (
                    f"- Evidence: {analysis.get('screenshot_evidence', 'N/A')}\n"
                )
                conditional_criteria_with_evidence += (
                    f"- Analysis: {analysis.get('criterion_analysis', 'N/A')}\n"
                )
                conditional_criteria_with_evidence += (
                    f"- Discrepancies: {analysis.get('discrepancies', 'N/A')}\n"
                )
                if "condition_verification" in analysis:
                    conditional_criteria_with_evidence += f"- Per-screenshot condition verification: {analysis['condition_verification']}\n"
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
                key=lambda x: x.get("screenshot_idx", 0),
            ):
                sn = analysis.get(
                    "source_state_id", analysis.get("screenshot_idx", 0) + 1
                )
                criteria_with_evidence += f"\n### Screenshot {sn} Evidence:\n"
                criteria_with_evidence += (
                    f"- Evidence: {analysis.get('screenshot_evidence', 'N/A')}\n"
                )
                criteria_with_evidence += (
                    f"- Analysis: {analysis.get('criterion_analysis', 'N/A')}\n"
                )
                criteria_with_evidence += (
                    f"- Discrepancies: {analysis.get('discrepancies', 'N/A')}\n"
                )
            if not evidence_by_criterion.get(c_idx):
                criteria_with_evidence += "\nNo screenshot evidence available.\n"
        return criteria_with_evidence

    @staticmethod
    def _criterion_analyses_text(evidence_by_criterion, c_idx, total_states):
        analyses = sorted(
            evidence_by_criterion.get(c_idx, []),
            key=lambda x: x.get("screenshot_idx", 0),
        )
        concatenated = ""
        for i_a, analysis in enumerate(analyses):
            sn = analysis.get(
                "source_state_id", analysis.get("screenshot_idx", i_a) + 1
            )
            concatenated += (
                f"\n### Screenshot state {sn} ({total_states} available) Analysis:\n"
                if "source_state_id" in analysis
                else f"\n### Screenshot {sn} of {total_states} Analysis:\n"
            )
            concatenated += (
                f"**Evidence:** {analysis.get('screenshot_evidence', 'N/A')}\n"
            )
            concatenated += (
                f"**Analysis:** {analysis.get('criterion_analysis', 'N/A')}\n"
            )
            concatenated += (
                f"**Discrepancies:** {analysis.get('discrepancies', 'N/A')}\n"
            )
            concatenated += f"**Environment Issues Confirmed:** {analysis.get('environment_issues_confirmed', False)}\n"
        if not concatenated:
            concatenated = "No screenshot evidence available for this criterion."
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
                lines.append("No screenshot evidence available for this criterion.")
                lines.append("")
                continue
            for analysis in sorted(analyses, key=lambda x: x.get("screenshot_idx", 0)):
                sn = analysis.get(
                    "source_state_id", analysis.get("screenshot_idx", 0) + 1
                )
                lines.append(
                    f"### Screenshot state {sn} ({total_states} available) Analysis:"
                    if "source_state_id" in analysis
                    else f"### Screenshot {sn} of {total_states} Analysis:"
                )
                lines.append(
                    f"**Evidence:** {analysis.get('screenshot_evidence', 'N/A')}"
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
