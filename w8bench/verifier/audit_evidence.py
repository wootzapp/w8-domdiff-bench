"""Paired source chronology, origin checks and shared action history."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .common import load_json
from .validate_inputs import SCREENSHOT_RE


DOM_RE = re.compile(r"^dom_model(0|[1-9]\d*)\.txt$")


def _criterion_value(container: object, index: int, default: object) -> object:
    if isinstance(container, dict):
        return container.get(str(index), container.get(index, default))
    if isinstance(container, list) and index < len(container):
        return container[index]
    return default


def extract_verifier_context(
    result: dict[str, Any], criterion_count: int
) -> list[dict[str, Any]]:
    """Extract only existing evidence-analysis and score fields for the auditor."""

    intermediate = result.get("intermediate_mm_rubric_steps") or {}
    analyses = intermediate.get("step4_evidence_by_criterion") or {}
    rescoring = intermediate.get("step6_rescoring_summary") or []
    if not isinstance(rescoring, list) or len(rescoring) != criterion_count:
        raise ValueError("Verifier result lacks complete criterion rescoring rows")
    rows: list[dict[str, Any]] = []
    for index in range(criterion_count):
        raw_analysis = _criterion_value(analyses, index, [])
        if not isinstance(raw_analysis, list):
            raw_analysis = []
        score = rescoring[index]
        if not isinstance(score, dict):
            raise ValueError(f"Verifier criterion row {index} is not an object")
        rows.append(
            {
                "criterion_index": index,
                "evidence_analysis": raw_analysis,
                "applicable_evidence": score.get("applicable_evidence", ""),
                "action_only_points": score.get("earned_points"),
                "final_points": score.get(
                    "post_dom_earned_points",
                    score.get("post_image_earned_points", score.get("earned_points")),
                ),
                "max_points": score.get("max_points"),
                "final_justification": score.get(
                    "post_dom_justification",
                    score.get(
                        "post_image_justification", score.get("justification", "")
                    ),
                ),
            }
        )
    return rows


def _single_task_data(root: Path) -> dict[str, Any]:
    value = load_json(root / "task_data.json")
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError(f"Expected one task record in {root / 'task_data.json'}")
        return value[0]
    if not isinstance(value, dict):
        raise ValueError(f"Task data must be an object or one-item list in {root}")
    return value


def _trajectory_events(root: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        (root / "web_surfer.log").read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(
                f"Trajectory line {line_number} in {root} is not an object"
            )
        arguments = (
            value.get("arguments") if isinstance(value.get("arguments"), dict) else {}
        )
        events.append(
            {
                "action_index": len(events) + 1,
                "action": value.get("action") or arguments.get("action"),
                "text": arguments.get("text"),
                "intent": arguments.get("thoughts"),
                "url": value.get("url"),
                "execution_status": value.get("execution_status"),
            }
        )
    return events


def verifier_action_history(root: Path) -> str:
    """Reconstruct the existing judges' shared text without editing inputs."""
    from .screenshot_verifier.models import StepSummary
    from .screenshot_verifier.rubric_agent import MMRubricAgent as ScreenshotAgent
    from .dom_model.rubric_agent import MMRubricAgent as DOMAgent

    summaries = []
    for line in (root / "web_surfer.log").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not event.get("action"):
            continue
        arguments = event.get("arguments") or {}
        name = arguments.get("action", event["action"])
        if name in ("stop_and_answer_question", "stop_execution"):
            name = "terminate"
        summaries.append(
            StepSummary(
                index=len(summaries) + 1,
                action_name=name,
                action_args={
                    key: value
                    for key, value in arguments.items()
                    if key not in {"action", "screen_description", "reasoning"}
                },
                url=event.get("url") or "",
                state_description=arguments.get("screen_description", ""),
            )
        )
    context = _single_task_data(root).get("evaluation_context")
    history = ScreenshotAgent._format_action_history(
        summaries, evaluation_context=context
    )
    if history != DOMAgent._format_action_history(
        summaries, evaluation_context=context
    ):
        raise ValueError("Verifier action-history formats differ")
    return history


_EVALUATION_CONTEXT_FIELDS = {
    "recording_sha256",
    "task_id",
    "actor_arm",
    "trial_id",
    "validity_date",
    "expected_state_ids",
    "format_gaps",
    "navigation_states",
    "audit_eligible_states",
    "observed_url_timeline",
    "states",
    "source_files_sha256",
}


def _validate_capture_artifacts(expected, receipt_by_state, screenshot_root, dom_root):
    for state in expected:
        receipt = receipt_by_state.get(state, {})
        for name, root, filename in (
            ("screenshot.png", screenshot_root, f"screenshot{state}.png"),
            ("dom_model.txt", dom_root, f"dom_model{state}.txt"),
        ):
            path = root / filename
            artifact = receipt.get("artifacts", {}).get(name)
            if path.is_file() and (
                not artifact
                or artifact.get("sha256")
                != hashlib.sha256(path.read_bytes()).hexdigest()
            ):
                raise ValueError(
                    f"Staged artifact differs from recorded same-run receipt: {filename}"
                )


def _validate_capture_origin(context, screenshot_root, dom_root):
    if _EVALUATION_CONTEXT_FIELDS - set(context):
        raise ValueError("Incomplete same-run evaluation origin receipt")
    if not re.fullmatch("[0-9a-f]{64}", str(context["recording_sha256"])):
        raise ValueError("Invalid same-run recording fingerprint")
    expected = context["expected_state_ids"]
    gaps = context["format_gaps"]
    receipt_by_state = {row["state"]: row for row in context["states"]}
    excluded = (
        set(gaps.get("screenshot", []))
        | set(gaps.get("dom_model", []))
        | set(context["navigation_states"])
    )
    eligible = [
        index
        for index in expected
        if index not in excluded
        and receipt_by_state.get(index, {}).get("eligible") is True
    ]
    if any(
        (
            row.get("eligible") is True and row["state"] in excluded
            for row in context["states"]
        )
    ):
        raise ValueError("Ineligible capture state declared audit-eligible")
    if context["audit_eligible_states"] != eligible:
        raise ValueError("Audit eligibility differs from paired capture/nav receipt")
    for index in eligible:
        if (
            not (screenshot_root / f"screenshot{index}.png").is_file()
            or not (dom_root / f"dom_model{index}.txt").is_file()
        ):
            raise ValueError("Audit-eligible paired state artifact is missing")
    _validate_capture_artifacts(expected, receipt_by_state, screenshot_root, dom_root)


def shared_trajectory_payload(screenshot_root: Path, dom_root: Path) -> dict[str, Any]:
    """Build representation-neutral evidence shared by both verifier inputs."""
    screenshot_task = _single_task_data(screenshot_root)
    dom_task = _single_task_data(dom_root)
    task_keys = ("task_id", "confirmed_task", "website")
    if any((screenshot_task.get(key) != dom_task.get(key) for key in task_keys)):
        raise ValueError("Screenshot and DOM task metadata differ")
    context = screenshot_task.get("evaluation_context")
    if context != dom_task.get("evaluation_context"):
        raise ValueError("Screenshot and DOM same-run origin contexts differ")
    if context:
        _validate_capture_origin(context, screenshot_root, dom_root)
    screenshot_events = _trajectory_events(screenshot_root)
    dom_events = _trajectory_events(dom_root)
    if screenshot_events != dom_events:
        raise ValueError("Screenshot and DOM normalized action histories differ")
    history = verifier_action_history(screenshot_root)
    dom_history = verifier_action_history(dom_root)
    screenshot_answer = load_json(screenshot_root / "final_answer.json")
    dom_answer = load_json(dom_root / "final_answer.json")
    if not isinstance(screenshot_answer, dict) or not isinstance(dom_answer, dict):
        raise ValueError("Final-answer sidecars must be objects")
    final_answer = screenshot_answer.get("final_answer")
    if final_answer != dom_answer.get("final_answer"):
        raise ValueError("Screenshot and DOM final answers differ")
    return {
        "task_id": screenshot_task.get("task_id"),
        "task_instruction": screenshot_task.get("confirmed_task"),
        "initial_url": screenshot_task.get("website"),
        "actions": screenshot_events,
        "verifier_action_history": {"screenshot": history, "dom_model": dom_history},
        "final_answer_claim": final_answer,
        **({"evaluation_context": context} if context else {}),
    }


def ordered_audit_screenshots(root: Path) -> list[Path]:
    """Return original screenshot states, ignoring verifier-created aliases."""

    indexed: dict[int, Path] = {}
    for path in root.iterdir():
        if not path.is_file() or path.is_symlink():
            continue
        match = SCREENSHOT_RE.fullmatch(path.name)
        if not match:
            continue
        index = int(match.group(1))
        if index in indexed:
            raise ValueError(f"Duplicate original screenshot index {index} in {root}")
        indexed[index] = path
    actual = sorted(indexed)
    context = _single_task_data(root).get("evaluation_context") or {}
    expected = (
        list(range(len(actual)))
        if not context
        else [
            index
            for index in context["expected_state_ids"]
            if index not in context.get("format_gaps", {}).get("screenshot", [])
        ]
    )
    if (not actual and not context) or actual != expected:
        raise ValueError(
            f"Original screenshots differ from recorded chronology: expected {expected}, got {actual}"
        )
    return [indexed[index] for index in actual]


def ordered_dom_states(dom_dir: Path) -> list[Path]:
    indexed: dict[int, Path] = {}
    for path in dom_dir.iterdir():
        if not path.is_file():
            continue
        match = DOM_RE.fullmatch(path.name)
        if match:
            index = int(match.group(1))
            if index in indexed:
                raise ValueError(f"Duplicate DOM state index {index}")
            indexed[index] = path
    actual = sorted(indexed)
    context = _single_task_data(dom_dir).get("evaluation_context") or {}
    expected = (
        list(range(len(actual)))
        if not context
        else [
            index
            for index in context["expected_state_ids"]
            if index not in context.get("format_gaps", {}).get("dom_model", [])
        ]
    )
    if (not actual and not context) or actual != expected:
        raise ValueError(
            f"DOM states differ from recorded chronology: expected {expected}, got {actual}"
        )
    return [indexed[index] for index in actual]
