"""Rubric validation, score arithmetic and recorded action diagnostics."""

from __future__ import annotations
import copy
import math
from difflib import SequenceMatcher
from typing import Any

CRITERION_SIMILARITY_THRESHOLD = 0.7
ACTION_METADATA_KEYS = frozenset({"thoughts", "target"})


class UngradedVerifierError(RuntimeError):
    """A scoring stage exhausted its response-repair budget."""

    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"Native verifier ungraded at {stage}: {reason}")


def validate_points(value: Any, max_points: Any, *, field: str) -> None:
    """Require a finite, nonboolean score within the criterion's weight."""
    if (isinstance(max_points, bool) or not isinstance(max_points, (int, float))
            or not math.isfinite(max_points) or max_points <= 0):
        raise ValueError("max_points must be a positive finite nonboolean number")
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f"{field} must be a finite nonboolean number")
    if not 0 <= value <= max_points:
        raise ValueError(f"{field} must be between 0 and {max_points}, got {value}")


def ungraded_result(error: UngradedVerifierError) -> dict[str, Any]:
    """Represent unavailable native scoring without a numeric substitute."""
    return {
        "status": "ungraded", "ungraded_reason": str(error),
        "judge_fallback": {"stage": error.stage, "reason": error.reason},
        "score": None, "rubric_score": None,
        "rubric_total_max_points": None, "rubric_total_earned_points": None,
        "rubric_is_success": None, "outcome": None,
    }
FARA_ACTION_DEFINITIONS: dict[str, set[str]] = {
    "key": {"keys", "key"},
    "type": {"text", "coordinate", "ref", "press_enter", "delete_existing_text"},
    "mouse_move": {"coordinate"},
    "left_click": {"coordinate", "ref"},
    "scroll": {"coordinate", "pixels", "ref"},
    "select": {"ref", "text"},
    "visit_url": {"url"},
    "web_search": {"query"},
    "history_back": set(),
    "pause_and_memorize_fact": {"fact"},
    "wait": {"time", "seconds"},
    "terminate": {"status"},
}


def verify_rubric(d: dict, *, evidence_mode: str = "screenshot_verifier") -> bool:
    assert isinstance(d, dict), f"Expected a dict, got {type(d)}"
    assert "items" in d, "Expected 'items' field in dict"
    assert isinstance(d["items"], list), "Expected 'items' field to be a list"
    for item in d["items"]:
        assert "criterion" in item, "Expected 'criterion' field in each item"
        if "items" in item:
            verify_rubric(item, evidence_mode=evidence_mode)
        else:
            _verify_scored_item(item, evidence_mode)
    return True


def _verify_scored_item(item: dict, evidence_mode: str):
    assert "max_points" in item, "Expected 'max_points' field in each item"
    assert isinstance(item["max_points"], (int, float)), (
        "'max_points' should be a number"
    )
    assert "earned_points" in item, "Expected 'earned_points' field in each item"
    validate_points(item["earned_points"], item["max_points"], field="earned_points")
    assert "justification" in item, "Expected 'justification' field in each item"
    assert isinstance(item["justification"], str) and item["justification"], (
        "'justification' should be a string"
    )
    if "condition" in item:
        assert "is_condition_met" in item, (
            f"Conditional criterion '{item['criterion']}' must have 'is_condition_met' field"
        )
        assert isinstance(item["is_condition_met"], bool), (
            f"'is_condition_met' must be a boolean for criterion '{item['criterion']}'"
        )
    _verify_evidence_score(item, evidence_mode)


def _verify_evidence_score(item: dict, evidence_mode: str):
    score_prefix = "post_dom" if evidence_mode == "dom_model" else "post_image"
    score_field = f"{score_prefix}_earned_points"
    justification_field = f"{score_prefix}_justification"
    if justification_field in item:
        assert (
            isinstance(item[justification_field], str) and item[justification_field]
        ), f"'{score_prefix}_justification' should be a non-empty string"
    if score_field in item:
        validate_points(item[score_field], item["max_points"], field=score_field)


def verify_generated_rubric(d: dict) -> bool:
    assert isinstance(d, dict), f"Expected a dict, got {type(d)}"
    assert "items" in d, "Expected 'items' field in dict"
    assert isinstance(d["items"], list), "Expected 'items' field to be a list"
    assert len(d["items"]) > 0, "Expected at least one item in rubric"
    for item in d["items"]:
        assert "criterion" in item, "Expected 'criterion' field in each item"
        assert "description" in item, "Expected 'description' field in each item"
        assert "max_points" in item, "Expected 'max_points' field in each item"
        validate_points(0, item["max_points"], field="earned_points")
        assert "justification" in item, "Expected 'justification' field in each item"
        assert "earned_points" in item, "Expected 'earned_points' field in each item"
        assert item["justification"] == "", (
            "'justification' should be empty string in generated rubric"
        )
        assert item["earned_points"] == "", (
            "'earned_points' should be empty string in generated rubric"
        )
        if "items" in item:
            verify_generated_rubric(item)
    return True


def graft_scores_onto_rubric(original: dict, scored: dict) -> dict:
    """Preserve criterion definitions and accept matching model scores."""
    result = copy.deepcopy(original)
    orig_items = result.get("items", [])
    scored_items = scored.get("items", [])
    if len(orig_items) != len(scored_items):
        raise ValueError(
            f"Rubric item count mismatch: expected {len(orig_items)} items but your response has {len(scored_items)}. Return exactly the same number of rubric items."
        )
    for i, (orig_item, scored_item) in enumerate(zip(orig_items, scored_items)):
        orig_crit = orig_item.get("criterion", "")
        scored_crit = scored_item.get("criterion", "")
        similarity = SequenceMatcher(
            None, orig_crit.lower(), scored_crit.lower()
        ).ratio()
        if similarity < CRITERION_SIMILARITY_THRESHOLD:
            raise ValueError(
                f"Criterion mismatch at position {i}: expected '{orig_crit}' but got '{scored_crit}' (similarity={similarity:.2f}, threshold={CRITERION_SIMILARITY_THRESHOLD}). Do not rephrase or reorder criteria — return them exactly as they appear in the original rubric."
            )
        orig_item["justification"] = scored_item.get("justification", "")
        if "earned_points" not in scored_item:
            raise ValueError(f"Criterion {i} missing earned_points")
        orig_item["earned_points"] = scored_item["earned_points"]
        if "condition" in orig_item:
            orig_item["is_condition_met"] = scored_item.get("is_condition_met", False)
    return result


def clear_rubric_scores(
    rubric_dict: dict, *, evidence_mode: str = "screenshot_verifier"
) -> dict:
    score_prefix = "post_dom" if evidence_mode == "dom_model" else "post_image"
    score_field = f"{score_prefix}_earned_points"
    justification_field = f"{score_prefix}_justification"
    cleared = copy.deepcopy(rubric_dict)

    def remove_penalty_criteria(items):
        return [item for item in items if not item.get("penalty", False)]

    def clear_scores_recursive(items):
        for item in items:
            if "earned_points" in item:
                item["earned_points"] = ""
            if "justification" in item:
                item["justification"] = ""
            for key in [
                "is_condition_met",
                "applicable_evidence",
                justification_field,
                score_field,
                "reality_notes",
            ]:
                item.pop(key, None)
            if "items" in item and isinstance(item["items"], list):
                item["items"] = remove_penalty_criteria(item["items"])
                clear_scores_recursive(item["items"])

    if "items" in cleared:
        cleared["items"] = remove_penalty_criteria(cleared["items"])
        clear_scores_recursive(cleared["items"])
    cleared.pop("total_earned_points", None)
    return cleared


def compute_final_scores(rubric: dict, earned_points_field: str) -> dict[str, float]:

    def sum_recursive(items):
        total_max, total_earned = (0.0, 0.0)
        for criterion in items:
            if "items" in criterion and isinstance(criterion["items"], list):
                sm, se = sum_recursive(criterion["items"])
                total_max += sm
                total_earned += se
            elif "condition" in criterion:
                validate_points(criterion.get(earned_points_field), criterion.get("max_points"), field=earned_points_field)
                if criterion.get("is_condition_met", False):
                    total_max += float(criterion["max_points"])
                    total_earned += float(criterion[earned_points_field])
            else:
                validate_points(criterion.get(earned_points_field), criterion.get("max_points"), field=earned_points_field)
                total_max += float(criterion["max_points"])
                total_earned += float(criterion[earned_points_field])
        return (total_max, total_earned)

    total_max, total_earned = sum_recursive(rubric["items"])
    return {"total_max_points": total_max, "total_earned_points": total_earned}


def validate_evidence_analysis(
    analysis: dict, is_conditional: bool, *, evidence_mode: str = "screenshot_verifier"
) -> None:
    evidence_field = (
        "dom_model_evidence" if evidence_mode == "dom_model" else "screenshot_evidence"
    )
    required = [
        evidence_field,
        "criterion_analysis",
        "discrepancies",
        "environment_issues_confirmed",
    ]
    if is_conditional:
        required.append("condition_verification")
    missing, type_errors = ([], [])
    for field in required:
        if field not in analysis:
            missing.append(field)
        elif field in ("environment_issues_confirmed", "condition_verification"):
            if not isinstance(analysis[field], bool):
                type_errors.append(
                    f"{field} must be a boolean, got {type(analysis[field]).__name__}"
                )
        elif not isinstance(analysis[field], str):
            type_errors.append(
                f"{field} must be a string, got {type(analysis[field]).__name__}"
            )
        elif not analysis[field]:
            type_errors.append(f"{field} cannot be empty")
    if missing or type_errors:
        error_msg = "Invalid analysis output. "
        if missing:
            error_msg += f"Missing required fields: {', '.join(missing)}. "
        if type_errors:
            error_msg += f"Type errors: {'; '.join(type_errors)}."
        raise ValueError(error_msg)


def normalize_batched_analysis_response(
    raw: Any,
    criterion_indices: list[int],
    *,
    evidence_mode: str = "screenshot_verifier",
) -> list | None:
    expected = len(criterion_indices)
    if isinstance(raw, list):
        return raw if len(raw) == expected else None
    if not isinstance(raw, dict):
        return None
    for val in raw.values():
        if (
            isinstance(val, list)
            and len(val) == expected
            and all((isinstance(item, dict) for item in val))
        ):
            return val
    recovered = _indexed_analyses(raw, criterion_indices)
    if recovered is not None:
        return recovered
    if expected == 1:
        return _singleton_analysis(raw, evidence_mode)
    return None


def _indexed_analyses(raw: dict, criterion_indices: list[int]):
    expected = len(criterion_indices)
    recovered = []
    for c_idx in criterion_indices:
        key_variants = [
            str(c_idx),
            c_idx,
            f"criterion_{c_idx}",
            f"Criterion {c_idx}",
            f"criterion {c_idx}",
        ]
        found = False
        for key in key_variants:
            if key in raw and isinstance(raw[key], dict):
                entry = raw[key]
                entry["criterion_idx"] = c_idx
                recovered.append(entry)
                found = True
                break
        if not found:
            break
    if len(recovered) == expected:
        return recovered
    return None


def _singleton_analysis(raw: dict, evidence_mode: str):
    evidence_field = (
        "dom_model_evidence" if evidence_mode == "dom_model" else "screenshot_evidence"
    )
    analysis_fields = {
        evidence_field,
        "criterion_analysis",
        "discrepancies",
        "environment_issues_confirmed",
    }
    if analysis_fields.intersection(raw.keys()):
        return [raw]
    for val in raw.values():
        if isinstance(val, dict) and analysis_fields.intersection(val.keys()):
            if "criterion_idx" in raw and "criterion_idx" not in val:
                val["criterion_idx"] = raw["criterion_idx"]
            return [val]
    return None


def validate_rescore(
    rescore: dict,
    max_points: float,
    *,
    prefix: str = "",
    evidence_mode: str = "screenshot_verifier",
) -> None:
    score_prefix = "post_dom" if evidence_mode == "dom_model" else "post_image"
    score_field = f"{score_prefix}_earned_points"
    justification_field = f"{score_prefix}_justification"
    required_fields = ["applicable_evidence", justification_field, score_field]
    missing_fields = []
    type_errors = []
    valid_max = (not isinstance(max_points, bool) and isinstance(max_points, (int, float))
        and math.isfinite(max_points) and max_points > 0)
    for field in required_fields:
        if field not in rescore:
            missing_fields.append(field)
        elif field in (justification_field, "applicable_evidence"):
            if not isinstance(rescore[field], str):
                type_errors.append(
                    f"{prefix}{field} must be a string, got {type(rescore[field]).__name__}"
                )
            elif not rescore[field]:
                type_errors.append(f"{prefix}{field} cannot be empty")
        elif field == score_field:
            if isinstance(rescore[field], bool):
                type_errors.append(f"{prefix}{field} must be a finite nonboolean number")
            elif not isinstance(rescore[field], (int, float)):
                type_errors.append(
                    f"{prefix}{field} must be a number, got {type(rescore[field]).__name__}"
                )
            elif not math.isfinite(rescore[field]) or (valid_max and not 0 <= rescore[field] <= max_points):
                type_errors.append(
                    f"{prefix}{field} must be between 0 and {max_points}, got {rescore[field]}"
                )
    if not valid_max:
        type_errors.append(f"{prefix}max_points must be a positive finite nonboolean number")
    if missing_fields or type_errors:
        error_msg = "Invalid rescoring output. "
        if missing_fields:
            error_msg += f"Missing fields: {', '.join(missing_fields)}. "
        if type_errors:
            error_msg += f"Errors: {'; '.join(type_errors)}."
        raise ValueError(error_msg)


def get_init_url_context(init_url: str | None) -> str:
    if not init_url:
        return ""
    if init_url.lower() in [
        "",
        "bing.com",
        "https://bing.com",
        "https://bing.com/",
        "http://bing.com",
        "https://www.bing.com",
        "http://www.bing.com",
    ]:
        return ""
    return f"\n\nIMPORTANT: The agent MAY have started on the URL: {init_url}\nThis starting URL may be considered part of the task context. The agent should NOT be penalized for using or assuming information that is implicit in this starting URL."


def parse_first_step_number(step_numbers: str) -> int:
    """Return the earliest step in comma-separated numbers and ranges, or 999999."""
    try:
        step_numbers = step_numbers.strip()
        values: list[int] = []
        for token in step_numbers.split(","):
            token = token.strip()
            if "-" in token:
                values.extend((int(p.strip()) for p in token.split("-")))
            else:
                values.append(int(token))
        return min(values) if values else 999999
    except (ValueError, IndexError):
        return 999999


def detect_tool_interaction_errors(
    step_actions: list[dict[str, Any]], action_definitions: dict[str, set[str]]
) -> list[dict]:
    """Report actions and arguments outside the recorded tool schema."""
    errors: list[dict] = []
    valid_action_names = set(action_definitions.keys())
    for sa in step_actions:
        step = sa["step_number"]
        name = sa["action_name"]
        args_keys = set(sa["action_args_keys"]) - {"_call_id"} - ACTION_METADATA_KEYS
        if not name:
            continue
        if name not in valid_action_names:
            errors.append(_hallucinated_action(step, name, valid_action_names))
        else:
            expected_args = action_definitions[name]
            unknown_args = args_keys - expected_args
            if unknown_args:
                errors.append(
                    _invalid_invocation(step, name, unknown_args, expected_args)
                )
    return errors


def _hallucinated_action(step, name: str, valid_action_names: set[str]):
    return {
        "step_numbers": str(step),
        "error_code": "6.2",
        "error_category": "Tool Interaction",
        "error_type": "Hallucinated action",
        "what_happened": f"The agent invoked `{name}` which does not exist in the available action space [{', '.join(sorted(valid_action_names))}].",
        "agent_reasoning": "",
        "evidence": f"Action `{name}` is not defined in the tool schema.",
        "impact": "The action could not be executed as intended.",
        "programmatic": True,
    }


def _invalid_invocation(
    step, name: str, unknown_args: set[str], expected_args: set[str]
):
    return {
        "step_numbers": str(step),
        "error_code": "6.1",
        "error_category": "Tool Interaction",
        "error_type": "Invalid invocation",
        "what_happened": f"The agent called `{name}` with unknown argument(s): {', '.join(sorted(unknown_args))}. Valid arguments are: {', '.join(sorted(expected_args))}.",
        "agent_reasoning": "",
        "evidence": f"Arguments {sorted(unknown_args)} are not in the schema for `{name}`.",
        "impact": "The action may not execute correctly due to invalid arguments.",
        "programmatic": True,
    }


def select_median_instance(
    instances: list[tuple[dict, float, dict]],
) -> tuple[int, dict, float, dict]:
    sorted_by_score = sorted(enumerate(instances), key=lambda x: x[1][1])
    median_pos = len(sorted_by_score) // 2
    median_idx, (rubric_dict, score, steps) = sorted_by_score[median_pos]
    return (median_idx, rubric_dict, score, steps)
