from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .action_mapping import sanitize_action_arguments, validate_action
from .aria_parser import parse_aria_tree
from .schemas import (
    ActionRecord,
    PageState,
    PreflightResult,
    SemanticState,
    StagehandTrajectory,
    TaskDefinition,
)
from .state_alignment import align_actions_to_states


STEP_RE = re.compile(r"^step_(\d+)$")
EXCLUDED_BASENAMES = {
    "screenshot.png",
    "evidence.png",
    "final_screenshot.png",
    "agent_input.json",
    "agent_output.json",
    "model_request.json",
    "model_prompt.txt",
    "stagehand_logs.jsonl",
    "trajectory.jsonl",
    "evidence.jsonl",
}


def _safe_path(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"Evidence path escapes task directory: {path}")
    return resolved


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = _safe_path(root, path)
    if resolved.name in EXCLUDED_BASENAMES:
        raise ValueError(f"Excluded artifact cannot be loaded: {resolved.name}")
    if not resolved.is_file():
        raise FileNotFoundError(f"Required JSON file is missing: {resolved}")
    with resolved.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {resolved}")
    return value


def _read_text(root: Path, path: Path) -> str:
    resolved = _safe_path(root, path)
    if resolved.name in EXCLUDED_BASENAMES:
        raise ValueError(f"Excluded artifact cannot be loaded: {resolved.name}")
    if not resolved.is_file():
        raise FileNotFoundError(f"Required text file is missing: {resolved}")
    return resolved.read_text(encoding="utf-8")


def _bounded(value: Any, limit: int = 4_000) -> Any:
    """Remove image/ARIA duplication and recursively bound tool outputs."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            lowered = key.casefold()
            if any(token in lowered for token in ("screenshot", "image", "base64")):
                continue
            if lowered in {"ariatree", "aria_tree"}:
                result[key] = "[omitted: duplicate ARIA state]"
                continue
            result[key] = _bounded(child, limit=limit)
        return result
    if isinstance(value, list):
        return [_bounded(item, limit=limit) for item in value[:100]]
    if isinstance(value, str):
        if value.startswith("[Buffer "):
            return "[omitted: binary buffer]"
        return value if len(value) <= limit else value[: limit - 1] + "…"
    return value


def _tool_result_projection(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    return _bounded(
        {
            "ok": payload.get("ok"),
            "error": payload.get("error"),
            "result": {
                "toolName": result.get("toolName"),
                "input": result.get("input"),
                "output": result.get("output"),
                "dynamic": result.get("dynamic"),
            },
        }
    )


def _page_state(payload: dict[str, Any]) -> PageState:
    viewport = payload.get("viewport") if isinstance(payload.get("viewport"), dict) else {}
    return PageState(
        url=str(payload.get("url") or ""),
        title=str(payload.get("title") or ""),
        ready_state=str(payload.get("readyState") or ""),
        scroll_x=float(payload.get("scrollX") or 0),
        scroll_y=float(payload.get("scrollY") or 0),
        viewport_width=float(viewport.get("width") or 0),
        viewport_height=float(viewport.get("height") or 0),
        device_pixel_ratio=float(viewport.get("devicePixelRatio") or 1),
        body_text_preview=str(payload.get("bodyTextPreview") or "")[:4_000],
    )


def _load_state(root: Path, step_dir: Path, ordinal: int) -> SemanticState:
    aria = _read_text(root, step_dir / "aria.txt")
    nodes, unparsed = parse_aria_tree(aria)
    page = _page_state(_read_json(root, step_dir / "page_state.json"))
    return SemanticState(
        ordinal=ordinal,
        page=page,
        nodes=nodes,
        raw_unparsed_lines=unparsed,
        capture_status="complete" if nodes or page.body_text_preview else "partial",
    )


def _synthetic_initial_state() -> SemanticState:
    return SemanticState(
        ordinal=0,
        page=PageState(
            url="about:blank",
            title="",
            ready_state="complete",
            scroll_x=0,
            scroll_y=0,
            viewport_width=0,
            viewport_height=0,
            device_pixel_ratio=1,
            body_text_preview="",
        ),
        nodes=(),
        capture_status="synthetic",
        coverage="synthetic_about_blank",
        synthetic=True,
    )


def _step_directories(root: Path) -> list[tuple[int, Path]]:
    found: dict[int, list[Path]] = {}
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = STEP_RE.fullmatch(child.name)
        if match:
            found.setdefault(int(match.group(1)), []).append(child)
    duplicates = {key: value for key, value in found.items() if len(value) != 1}
    if duplicates:
        raise ValueError(f"Duplicate step ordinals: {sorted(duplicates)}")
    actual = sorted(found)
    expected = list(range(1, len(actual) + 1))
    if actual != expected:
        raise ValueError(f"Step ordinals must be contiguous: expected {expected}, got {actual}")
    if not actual:
        raise ValueError(f"No step_XXX directories found under {root}")
    return [(ordinal, found[ordinal][0]) for ordinal in actual]


def _load_task(root: Path, override: dict[str, Any] | None) -> TaskDefinition:
    if override is not None:
        payload = override
        task_id = str(payload.get("id") or payload.get("task_id") or root.name)
        instruction = str(payload.get("question") or payload.get("confirmed_task") or "")
        init_url = str(payload.get("init_url") or payload.get("website") or "")
        rubric = payload.get("precomputed_rubric")
    elif (root / "task_data.json").is_file():
        payload = _read_json(root, root / "task_data.json")
        task_id = str(payload.get("id") or payload.get("task_id") or root.name)
        instruction = str(payload.get("question") or payload.get("confirmed_task") or "")
        init_url = str(payload.get("init_url") or payload.get("website") or "")
        rubric = payload.get("precomputed_rubric")
    else:
        payload = _read_json(root, root / "task.json")
        task_id = str(payload.get("task_id") or root.name)
        instruction = str(payload.get("task") or "")
        init_url = str(payload.get("start_url") or "")
        rubric = None
    if not instruction:
        raise ValueError("Task instruction is empty")
    if rubric is not None and not isinstance(rubric, dict):
        raise ValueError("precomputed_rubric must be a JSON object")
    return TaskDefinition(task_id, instruction, init_url, rubric)


def _load_answer(root: Path, task_id: str) -> tuple[str, bool, dict[str, Any], str]:
    candidates = [root / f"{task_id}_answer.json", root / "final_answer.json"]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        extras = sorted(root.glob("*_answer.json"))
        existing = extras
    if not existing:
        raise FileNotFoundError(f"No final-answer JSON found under {root}")
    payload = _read_json(root, existing[0])
    final_answer = payload.get("final_answer")
    if final_answer is None:
        final_answer = payload.get("message")
    if final_answer is None and payload.get("output") is not None:
        final_answer = payload.get("output")
    if not isinstance(final_answer, str):
        final_answer = json.dumps(final_answer, ensure_ascii=False)
    usage = payload.get("token_usage") if isinstance(payload.get("token_usage"), dict) else {}
    observation = payload.get("observation") if isinstance(payload.get("observation"), dict) else {}
    return final_answer, bool(payload.get("is_aborted", False)), usage, str(observation.get("url") or "")


def _validate_web_log(root: Path, actions: list[ActionRecord]) -> None:
    path = root / "web_surfer.log"
    alternate = root / "websurfer.log"
    if not path.is_file() and alternate.is_file():
        path = alternate
    if not path.is_file():
        return
    parsed: list[dict[str, Any]] = []
    for line_number, line in enumerate(_read_text(root, path).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed web log line {line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"Web log line {line_number} must be an object")
        parsed.append(item)
    if len(parsed) != len(actions):
        raise ValueError(
            f"web_surfer.log/action.json mismatch: {len(parsed)} events vs {len(actions)} actions"
        )
    for expected, event in zip(actions, parsed):
        event_name = str(event.get("action") or "")
        arguments = event.get("arguments") if isinstance(event.get("arguments"), dict) else {}
        if not event_name:
            event_name = str(arguments.get("action") or "")
        if event_name != expected.name:
            raise ValueError(
                f"web_surfer.log action mismatch at step {expected.ordinal}: "
                f"{event_name!r} != {expected.name!r}"
            )


def load_stagehand_trajectory(
    path: str | Path,
    *,
    task_data: dict[str, Any] | None = None,
) -> tuple[StagehandTrajectory, PreflightResult]:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    task = _load_task(root, task_data)
    steps = _step_directories(root)
    states = {ordinal: _load_state(root, step_dir, ordinal) for ordinal, step_dir in steps}

    action_steps: list[tuple[int, Path]] = []
    terminal_steps: list[tuple[int, Path]] = []
    for ordinal, step_dir in steps:
        if (step_dir / "action.json").is_file():
            action_steps.append((ordinal, step_dir))
        else:
            terminal_steps.append((ordinal, step_dir))
    if len(terminal_steps) != 1 or terminal_steps[0][0] != steps[-1][0]:
        raise ValueError("Exactly one final no-action step is required")
    if [item[0] for item in action_steps] != list(range(1, len(action_steps) + 1)):
        raise ValueError("Action-bearing steps must be contiguous from step_001")

    actions: list[ActionRecord] = []
    warnings: list[str] = []
    tool_errors: list[dict[str, Any]] = []
    for ordinal, step_dir in action_steps:
        payload = _read_json(root, step_dir / "action.json")
        name = str(payload.get("action") or "")
        arguments = sanitize_action_arguments(name, payload.get("arguments") or {})
        action_errors = validate_action(name, arguments)
        for error in action_errors:
            error["step"] = ordinal
            error["action_id"] = f"stagehand-{ordinal:04d}"
        tool_errors.extend(action_errors)
        tool_payload = _read_json(root, step_dir / "tool_result.json")
        projected_tool = _tool_result_projection(tool_payload)
        actions.append(
            ActionRecord(
                ordinal=ordinal,
                action_id=f"stagehand-{ordinal:04d}",
                name=name,
                arguments=arguments,
                url=states[ordinal].page.url,
                tool_result=projected_tool,
                source_path=str(step_dir / "action.json"),
            )
        )
    if tool_errors:
        warnings.extend(error["message"] for error in tool_errors)

    _validate_web_log(root, actions)
    if not actions:
        raise ValueError("Trajectory has no actions")
    first = actions[0]
    if first.name != "goto" or task.init_url not in {"", "about:blank"}:
        raise ValueError(
            "No explicit initial state exists; synthetic state is allowed only for "
            "a first goto action from about:blank"
        )
    initial = _synthetic_initial_state()
    frames = list(align_actions_to_states(actions, states, initial))

    terminal_ordinal, _ = terminal_steps[0]
    terminal_state = states[terminal_ordinal]
    final_answer, is_aborted, solver_usage, final_observation_url = _load_answer(
        root, task.task_id
    )
    if final_observation_url and final_observation_url != terminal_state.page.url:
        warnings.append(
            "final_answer observation URL differs from the authoritative terminal page state"
        )
    manifest = {
        "schema_version": "stagehand-semantic-trajectory/v1",
        "task_id": task.task_id,
        "action_count": len(actions),
        "state_count": len(states),
        "terminal_state_ordinal": terminal_ordinal,
        "final_observation_url": final_observation_url,
        "action_to_state_mapping": [
            {
                "action_ordinal": frame.action.ordinal,
                "action_id": frame.action.action_id,
                "before_state": frame.before.ordinal,
                "after_state": frame.after.ordinal,
            }
            for frame in frames
        ],
        "capture_coverage": {
            "aria_states": sum(bool(state.nodes) for state in states.values()),
            "page_states": len(states),
            "synthetic_initial_state": True,
            "terminal_state_present": True,
        },
        "excluded_artifacts": sorted(EXCLUDED_BASENAMES),
        "warnings": warnings,
        "deterministic_tool_errors": tool_errors,
    }
    preflight = PreflightResult(
        task_id=task.task_id,
        action_count=len(actions),
        state_count=len(states),
        transition_count=len(frames),
        terminal_state_present=True,
        synthetic_initial_state=True,
        alignment_complete=len(actions) == len(frames),
        warnings=warnings,
    )
    return (
        StagehandTrajectory(
            path=root,
            task=task,
            final_answer=final_answer,
            is_aborted=is_aborted,
            solver_token_usage=solver_usage,
            actions=tuple(actions),
            frames=tuple(frames),
            terminal_state=terminal_state,
            manifest=manifest,
        ),
        preflight,
    )

