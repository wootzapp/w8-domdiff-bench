"""Isolated adapter and preflight for root-level refined ``dom_diffN.txt``."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import (
    Action,
    ComputerObservation,
    DataPoint,
    DataPointMetadata,
    Outcome,
    SolverLog,
    SolverStatus,
    Task,
)
from .trajectory import (
    DOMDiffTrajectory,
    load_dom_diff_trajectory,
    ordered_action_events,
)
from .evidence import (
    DOM_DIFF_TEXT_SCHEMA,
    DOMDiffTextEvidenceFrame,
    load_dom_diff_text_frames,
)
from .rubric_agent import MMRubricAgent, verify_generated_rubric


_DIFF_RE = re.compile(r"^dom_diff([1-9][0-9]*)\.txt$")
_ACTION_TYPES = {
    "left_click": "click",
    "type": "fill",
    "visit_url": "navigate",
    "scroll": "scroll",
}
# Exact verifier-local copy of ``src/fara/fara_agent.py``'s canonical mapping.
# Importing the package initializes browser dependencies, so preflight must not
# import it merely to obtain this data.  Parity is protected by a source-hash
# gate and a dedicated test.
_BASE_FARA_ACTION_DEFINITIONS: dict[str, set[str]] = {
    "key": {"keys"},
    "type": {"text", "coordinate", "press_enter", "delete_existing_text"},
    "mouse_move": {"coordinate"},
    "left_click": {"coordinate"},
    "scroll": {"coordinate", "pixels"},
    "visit_url": {"url"},
    "web_search": {"query"},
    "history_back": set(),
    "pause_and_memorize_fact": {"fact"},
    "wait": {"time"},
    "terminate": {"status"},
}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_FORBIDDEN_EXACT = {
    "dom_diff.json",
    "dom_diff_summary.json",
    "before_dom.json",
    "after_dom.json",
    "before_page_state.json",
    "after_page_state.json",
    "verifier_action.json",
}
_FORBIDDEN_MARKERS = (
    "agent-browser",
    "agent_browser",
    "before_dom",
    "after_dom",
    "dom_snapshot",
    "snapshot",
    "page_state",
    "verifier_action",
)


def discover_dom_diff_text_paths(
    candidate_path: str | Path, action_count: int
) -> list[Path]:
    """Discover only canonical root-level ``dom_diff1.txt..dom_diffN.txt``."""
    root = Path(candidate_path).resolve()
    if action_count <= 0:
        raise ValueError("action_count must be positive")
    by_ordinal: dict[int, Path] = {}
    malformed: list[str] = []
    for child in root.iterdir():
        if not child.is_file():
            continue
        match = _DIFF_RE.fullmatch(child.name)
        if match is None:
            if child.name.startswith("dom_diff") and child.suffix == ".txt":
                malformed.append(child.name)
            continue
        ordinal = int(match.group(1))
        if ordinal in by_ordinal:
            raise ValueError(f"Duplicate refined DOM diff ordinal {ordinal}")
        by_ordinal[ordinal] = child
    if malformed:
        raise ValueError(
            f"Noncanonical refined DOM diff filenames: {sorted(malformed)}"
        )
    expected = list(range(1, action_count + 1))
    actual = sorted(by_ordinal)
    if actual != expected:
        raise ValueError(
            "Refined DOM diffs must be contiguous and action-aligned: "
            f"expected {expected}, got {actual}"
        )
    return [by_ordinal[index].resolve(strict=False) for index in expected]


def reject_forbidden_evidence(candidate_path: str | Path) -> None:
    """Reject every alternate browser-observation modality in the DOM bundle."""
    root = Path(candidate_path).resolve()
    forbidden: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        lower = path.name.casefold()
        if path.suffix.casefold() in _IMAGE_SUFFIXES:
            forbidden.append(relative)
            continue
        if lower in _FORBIDDEN_EXACT or any(
            marker in lower for marker in _FORBIDDEN_MARKERS
        ):
            forbidden.append(relative)
    if forbidden:
        raise ValueError(
            "Refined DOM task exposes forbidden page-observation evidence: "
            + ", ".join(sorted(forbidden))
        )


def _read_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _read_task_data(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError(f"task_data.json must contain exactly one task: {path}")
        value = value[0]
    if not isinstance(value, dict):
        raise ValueError(f"task_data.json must be one object or one-item list: {path}")
    return value


def validate_control_files(
    candidate_path: str | Path, task_data: Mapping[str, Any]
) -> None:
    """Require the approved root-level control files and one canonical task."""
    root = Path(candidate_path).resolve()
    task_files = sorted(path for path in root.glob("task_data*.json") if path.is_file())
    expected_task = root / "task_data.json"
    allowed_task_files = {
        expected_task,
        root / "task_data_with_canonical_rubric.json",
    }
    unexpected_task_files = [
        path for path in task_files if path not in allowed_task_files
    ]
    if expected_task not in task_files or unexpected_task_files:
        raise ValueError(
            f"Expected task_data.json and optionally "
            f"task_data_with_canonical_rubric.json in {root}; "
            f"unexpected {[path.name for path in unexpected_task_files]}; "
            f"found {[path.name for path in task_files]}"
        )
    log_files = [
        path
        for path in (root / "web_surfer.log", root / "websurfer.log")
        if path.is_file()
    ]
    expected_log = root / "web_surfer.log"
    if log_files != [expected_log]:
        raise ValueError(
            f"Expected exactly web_surfer.log in {root}; "
            f"found {[path.name for path in log_files]}"
        )
    on_disk = _read_task_data(expected_task)
    provided = dict(task_data)
    on_disk_rubric = on_disk.pop("precomputed_rubric", None)
    provided_rubric = provided.pop("precomputed_rubric", None)
    if on_disk != provided:
        raise ValueError("Provided task data does not match the task_data.json on disk")
    if (
        on_disk_rubric is not None
        and json.dumps(on_disk_rubric, sort_keys=True, separators=(",", ":"))
        != json.dumps(provided_rubric, sort_keys=True, separators=(",", ":"))
    ):
        raise ValueError("Embedded task rubric differs from the canonical rubric")


def validate_dom_final_answer(candidate_path: str | Path) -> dict[str, Any]:
    root = Path(candidate_path).resolve()
    candidates = sorted(root.glob("*answer*.json"))
    expected = root / "final_answer.json"
    if candidates != [expected]:
        raise ValueError(
            f"Expected exactly final_answer.json in {root}; found {[path.name for path in candidates]}"
        )
    answer = _read_json_object(expected)
    if "screenshots" in answer:
        raise ValueError("DOM final_answer.json must not contain a screenshots key")
    if answer.get("token_usage") != {}:
        raise ValueError("DOM final_answer.json must contain token_usage: {}")
    if not isinstance(answer.get("final_answer"), str):
        raise ValueError("DOM final_answer.json final_answer must be a string")
    return answer


def normalize_log_action_name(value: Any) -> str:
    name = str(value or "")
    if name not in _ACTION_TYPES:
        raise ValueError(f"Unsupported DOM log action {name!r}")
    return _ACTION_TYPES[name]


def _task_id(task_data: Mapping[str, Any], candidate: DOMDiffTrajectory) -> str:
    value = task_data.get("id") or task_data.get("task_id") or candidate.path.name
    return str(value)


def _task_question(task_data: Mapping[str, Any]) -> str:
    return str(task_data.get("question") or task_data.get("confirmed_task") or "")


def _task_url(task_data: Mapping[str, Any]) -> str:
    return str(task_data.get("init_url") or task_data.get("website") or "")


def _rubric_object(task_data: Mapping[str, Any]) -> dict[str, Any] | None:
    rubric = task_data.get("precomputed_rubric")
    if isinstance(rubric, list):
        if len(rubric) != 1 or not isinstance(rubric[0], dict):
            raise ValueError("precomputed_rubric list must contain exactly one object")
        rubric = rubric[0]
    if rubric is not None and not isinstance(rubric, dict):
        raise ValueError("precomputed_rubric must be an object")
    return rubric


def validate_frozen_rubric(task_data: Mapping[str, Any]) -> tuple[str, float]:
    rubric = _rubric_object(task_data)
    if rubric is None:
        raise ValueError("Scoring requires a task-specific frozen precomputed_rubric")
    items = rubric.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Frozen rubric must contain a non-empty items array")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Frozen rubric item {index} must be an object")
        scored_fields = {
            key: item.get(key)
            for key in (
                "earned_points",
                "post_image_earned_points",
                "post_evidence_earned_points",
            )
            if key in item and item.get(key) not in (None, "")
        }
        if scored_fields:
            raise ValueError(
                f"Frozen rubric item {index} is already scored: {sorted(scored_fields)}"
            )
    try:
        verify_generated_rubric(rubric)
    except (AssertionError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid frozen generated rubric: {exc}") from exc
    denominator = 0.0
    for index, item in enumerate(items):
        points = item["max_points"]
        if (
            not isinstance(points, (int, float))
            or isinstance(points, bool)
            or points <= 0
        ):
            raise ValueError(f"Frozen rubric item {index} max_points must be positive")
        denominator += float(points)
    encoded = json.dumps(
        rubric, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), denominator


def semantic_action_definitions() -> dict[str, set[str]]:
    """Return a verifier-local copy; the FARA source mapping is never mutated."""
    definitions = {
        name: set(arguments)
        for name, arguments in _BASE_FARA_ACTION_DEFINITIONS.items()
    }
    for name in ("left_click", "type", "scroll"):
        definitions[name].update({"ref", "target"})
    return definitions


def _create_text_datapoint(
    task_data: dict[str, Any], candidate: DOMDiffTrajectory, paths: list[Path]
) -> DataPoint:
    action_events = ordered_action_events(candidate)
    task_id = _task_id(task_data, candidate)
    metadata: dict[str, Any] = {
        "evidence_mode": "dom",
        "requested_evidence_mode": "dom_diff_text",
    }
    rubric = _rubric_object(task_data)
    if rubric is not None:
        metadata["precomputed_rubric"] = rubric
    task = Task(
        task_id=task_id,
        instruction=_task_question(task_data),
        environment_config={"init_url": _task_url(task_data)},
        metadata=metadata,
    )
    events: list[Any] = []
    for ordinal, (event, path) in enumerate(zip(action_events, paths), start=1):
        arguments = event.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError(f"Action {ordinal} arguments must be an object")
        action_name = str(arguments.get("action") or event.get("action") or "")
        action_args = {
            key: value for key, value in arguments.items() if key != "action"
        }
        action_id = str(ordinal)
        events.append(ComputerObservation(url=str(event.get("url") or "")))
        events.append(
            Action(
                id=action_id,
                action_name=action_name,
                content={"action": action_name, "arguments": action_args},
                action_nl_description=str(arguments.get("thoughts") or ""),
            )
        )
        # The shared extractor transports the path through its existing legacy
        # field.  build_dom_diff_text_input immediately moves and clears it.
        events.append(
            ComputerObservation(
                evidence_mode="dom",
                screenshot_path="",
                dom_evidence_schema_version=DOM_DIFF_TEXT_SCHEMA,
                dom_action_ordinal=ordinal,
                dom_action_id=action_id,
                dom_diff_path=str(path),
                dom_capture_status="complete",
                dom_coverage_status="text_diff_only",
                action_id=action_id,
            )
        )
    return DataPoint(
        task=task,
        solver_log=SolverLog(
            events=events,
            status=SolverStatus.ABORTED
            if candidate.is_aborted
            else SolverStatus.COMPLETE,
            outcome=Outcome(answer=candidate.final_answer),
        ),
        metadata=DataPointMetadata(run_id=candidate.path.name),
    )


def build_dom_diff_text_input(
    task_data: dict[str, Any],
    candidate: DOMDiffTrajectory,
    *,
    redo_eval: bool = False,
) -> dict[str, Any]:
    actions = ordered_action_events(candidate)
    paths = discover_dom_diff_text_paths(candidate.path, len(actions))
    datapoint = _create_text_datapoint(task_data, candidate, paths)
    value = MMRubricAgent._extract_input_from_datapoint(
        datapoint, screenshots_dir=None, redo_eval=redo_eval
    )
    task_id = _task_id(task_data, candidate)
    dom_actions = value.get("dom_actions") or []
    if len(dom_actions) != len(paths):
        raise ValueError("Shared DataPoint extraction lost text action alignment")
    for ordinal, (action, path) in enumerate(zip(dom_actions, paths), start=1):
        transported = str(action.get("dom_diff_path") or "")
        resolved = str(path.resolve(strict=False))
        if transported != resolved:
            raise ValueError(
                f"Text path bridge mismatch for action {ordinal}: {transported!r} != {resolved!r}"
            )
        action["id"] = ordinal
        action["dom_action_ordinal"] = ordinal
        action["dom_task_id"] = task_id
        action["dom_diff_text_path"] = resolved
        action["dom_diff_path"] = ""
        action["dom_diff_summary_path"] = ""
        action["dom_before_snapshot_path"] = ""
        action["dom_after_snapshot_path"] = ""
        action["dom_before_page_state_path"] = ""
        action["dom_after_page_state_path"] = ""
        action["dom_verifier_action_path"] = ""
        action["dom_coverage_status"] = "text_diff_only"
    value.update(
        evidence_mode="dom",
        requested_evidence_mode="dom_diff_text",
        screenshots_dir=None,
        declared_evidence_paths=[str(path) for path in paths],
        action_definitions=semantic_action_definitions(),
    )
    return value


def validate_text_input_paths(input_dict: dict[str, Any], action_count: int) -> None:
    actions = input_dict.get("dom_actions") or []
    if len(actions) != action_count:
        raise ValueError(
            f"Action/text mismatch: {action_count} actions, {len(actions)} text records"
        )
    declared: list[str] = []
    for ordinal, action in enumerate(actions, start=1):
        if int(action.get("dom_action_ordinal") or 0) != ordinal:
            raise ValueError(
                f"Text actions must be contiguous: expected {ordinal}, "
                f"got {action.get('dom_action_ordinal')}"
            )
        path = str(action.get("dom_diff_text_path") or "")
        match = _DIFF_RE.fullmatch(Path(path).name)
        if not path or match is None or int(match.group(1)) != ordinal:
            raise ValueError(f"Action {ordinal} has no valid refined-text path")
        forbidden = {
            key: action.get(key)
            for key in (
                "dom_diff_path",
                "dom_diff_summary_path",
                "dom_before_snapshot_path",
                "dom_after_snapshot_path",
                "dom_before_page_state_path",
                "dom_after_page_state_path",
                "dom_verifier_action_path",
            )
            if action.get(key)
        }
        if forbidden:
            raise ValueError(
                f"Action {ordinal} exposes forbidden text-mode evidence: {forbidden}"
            )
        declared.append(str(Path(path).resolve(strict=False)))
    expected = [
        str(Path(path).resolve(strict=False))
        for path in input_dict.get("declared_evidence_paths") or []
    ]
    if declared != expected:
        raise ValueError(
            "Declared text evidence paths do not match action-aligned paths"
        )


def validate_action_frame_alignment(
    candidate: DOMDiffTrajectory, frames: Iterable[DOMDiffTextEvidenceFrame]
) -> None:
    actions = ordered_action_events(candidate)
    frame_list = list(frames)
    if len(actions) != len(frame_list):
        raise ValueError("Action/frame count mismatch")
    for ordinal, (event, frame) in enumerate(zip(actions, frame_list), start=1):
        action_type = normalize_log_action_name(event.get("action"))
        if action_type != frame.action_type:
            raise ValueError(
                f"Action {ordinal} type mismatch: log={action_type}, diff={frame.action_type}"
            )
        event_url = str(event.get("url") or "")
        if event_url != frame.after_url:
            raise ValueError(
                f"Action {ordinal} URL mismatch: log={event_url!r}, after={frame.after_url!r}"
            )


def preflight_dom_diff_text_bundle(
    trajectory_dir: str | Path,
    task_data: dict[str, Any],
    *,
    redo_eval: bool = False,
    require_frozen_rubric: bool = True,
) -> tuple[DOMDiffTrajectory, dict[str, Any], list[DOMDiffTextEvidenceFrame]]:
    """Validate the full isolated bundle before any judge is initialized."""
    root = Path(trajectory_dir).resolve()
    validate_control_files(root, task_data)
    reject_forbidden_evidence(root)
    validate_dom_final_answer(root)
    trajectory = load_dom_diff_trajectory(root)
    input_dict = build_dom_diff_text_input(task_data, trajectory, redo_eval=redo_eval)
    action_count = len(ordered_action_events(trajectory))
    validate_text_input_paths(input_dict, action_count)
    frames = load_dom_diff_text_frames(input_dict["dom_actions"])
    validate_action_frame_alignment(trajectory, frames)
    if require_frozen_rubric:
        rubric_hash, denominator = validate_frozen_rubric(task_data)
        input_dict["frozen_rubric_sha256"] = rubric_hash
        input_dict["frozen_input_denominator"] = denominator
    return trajectory, input_dict, frames


def _semantic_event(event: Mapping[str, Any]) -> dict[str, Any]:
    arguments = event.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("Action arguments must be objects")
    excluded = {"coordinate", "ref", "target"}
    normalized_arguments = {
        key: value
        for key, value in arguments.items()
        if key not in excluded and key != "action"
    }
    return {
        "action": normalize_log_action_name(event.get("action")),
        "timestamp": event.get("timestamp"),
        "url": event.get("url"),
        "arguments": normalized_arguments,
    }


def validate_cross_modality_semantic_pair(
    dom_dir: str | Path, screenshot_dir: str | Path
) -> None:
    """Validate semantic equivalence while allowing only target representation."""
    dom_root = Path(dom_dir).resolve()
    screenshot_root = Path(screenshot_dir).resolve()
    dom_task = json.loads((dom_root / "task_data.json").read_text(encoding="utf-8"))
    screenshot_task = json.loads(
        (screenshot_root / "task_data.json").read_text(encoding="utf-8")
    )
    if dom_task != screenshot_task:
        raise ValueError("Paired task_data.json files differ")
    dom = load_dom_diff_trajectory(dom_root)
    screenshot = load_dom_diff_trajectory(screenshot_root)
    dom_actions = ordered_action_events(dom)
    screenshot_actions = ordered_action_events(screenshot)
    if len(dom_actions) != len(screenshot_actions):
        raise ValueError("Paired trajectories have different action counts")
    for ordinal, (dom_event, screenshot_event) in enumerate(
        zip(dom_actions, screenshot_actions), start=1
    ):
        if _semantic_event(dom_event) != _semantic_event(screenshot_event):
            raise ValueError(f"Paired semantic action differs at ordinal {ordinal}")
    if (
        dom.final_answer != screenshot.final_answer
        or dom.is_aborted != screenshot.is_aborted
    ):
        raise ValueError("Paired semantic final answers differ")
