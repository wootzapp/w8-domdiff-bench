#!/usr/bin/env python3
"""Fail-closed preflight for one paired screenshot/DOM-text benchmark task."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .common import (
    canonical_json_bytes,
    load_canonical_rubric,
    load_json,
    load_one_task,
    task_id,
    task_init_url,
    task_instruction,
    validate_endpoint_configs,
    write_json,
)


_SCREENSHOT_RE = re.compile(r"^screenshot_?(\d+)\.(?:png|jpe?g|webp)$", re.I)
_DOM_DIFF_RE = re.compile(r"^dom_diff([1-9]\d*)\.txt$")
_ACTION_NAMES = {
    "left_click": "click",
    "click": "click",
    "type": "fill",
    "fill": "fill",
    "visit_url": "navigate",
    "navigate": "navigate",
    "scroll": "scroll",
}


def _parse_actions(path: Path, *, mode: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
        if not isinstance(event, dict) or event.get("action") is None:
            continue
        arguments = event.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError(f"{path}:{line_number}: arguments must be an object")
        raw_name = str(arguments.get("action") or event.get("action") or "")
        if raw_name not in _ACTION_NAMES:
            raise ValueError(f"{path}:{line_number}: unsupported action {raw_name!r}")
        normalized = _ACTION_NAMES[raw_name]
        if mode == "screenshot" and normalized == "click":
            coordinate = arguments.get("coordinate")
            if (
                not isinstance(coordinate, list)
                or len(coordinate) != 2
                or not all(isinstance(value, (int, float)) for value in coordinate)
            ):
                raise ValueError(
                    f"{path}:{line_number}: screenshot click requires [x, y] coordinate"
                )
        if mode == "dom" and normalized in {"click", "fill"}:
            if arguments.get("ref") is None and arguments.get("target") is None:
                raise ValueError(f"{path}:{line_number}: DOM {normalized} requires ref or target")
        signature: dict[str, Any] = {
            "ordinal": len(actions) + 1,
            "action": normalized,
            "after_url": str(event.get("url") or ""),
        }
        if normalized == "navigate":
            signature["url"] = str(arguments.get("url") or "")
        elif normalized == "fill":
            signature["text"] = arguments.get("text", arguments.get("value"))
        elif normalized == "scroll":
            for key in ("direction", "delta_x", "delta_y", "amount"):
                if key in arguments:
                    signature[key] = arguments[key]
        target = arguments.get("target")
        if isinstance(target, dict):
            for key in ("role", "name"):
                if target.get(key) is not None:
                    signature[f"target_{key}"] = target[key]
        if arguments.get("ref") is not None:
            signature["ref"] = arguments["ref"]
        actions.append(signature)
    if not actions:
        raise ValueError(f"No actions found in {path}")
    return actions


def _compare_semantic_actions(
    screenshot_actions: list[dict[str, Any]], dom_actions: list[dict[str, Any]]
) -> None:
    if len(screenshot_actions) != len(dom_actions):
        raise ValueError(
            f"Action count mismatch: screenshot={len(screenshot_actions)}, DOM={len(dom_actions)}"
        )
    required_keys = {"action", "after_url"}
    action_keys = {
        "navigate": {"url"},
        "fill": {"text"},
        "scroll": {"direction", "delta_x", "delta_y", "amount"},
        "click": {"ref", "target_role", "target_name"},
    }
    for ordinal, (screenshot, dom) in enumerate(zip(screenshot_actions, dom_actions), start=1):
        for key in required_keys:
            if screenshot.get(key) != dom.get(key):
                raise ValueError(
                    f"Semantic action {ordinal} differs for {key}: "
                    f"{screenshot.get(key)!r} != {dom.get(key)!r}"
                )
        optional = action_keys.get(str(screenshot["action"]), set())
        for key in optional:
            if key in screenshot and key in dom and screenshot[key] != dom[key]:
                raise ValueError(
                    f"Semantic action {ordinal} differs for {key}: "
                    f"{screenshot[key]!r} != {dom[key]!r}"
                )


def _ordered_screenshots(root: Path) -> list[Path]:
    by_ordinal: dict[int, Path] = {}
    for child in root.iterdir():
        if not child.is_file():
            continue
        match = _SCREENSHOT_RE.fullmatch(child.name)
        if match is None:
            continue
        ordinal = int(match.group(1))
        if ordinal in by_ordinal:
            raise ValueError(f"Duplicate screenshot ordinal {ordinal} in {root}")
        by_ordinal[ordinal] = child
    actual = sorted(by_ordinal)
    if actual != list(range(len(actual))):
        raise ValueError(f"Screenshots must be contiguous from 0, got {actual}")
    return [by_ordinal[index] for index in actual]


def _ordered_dom_diffs(root: Path, action_count: int) -> list[Path]:
    by_ordinal: dict[int, Path] = {}
    malformed: list[str] = []
    for child in root.iterdir():
        if not child.is_file() or not child.name.startswith("dom_diff"):
            continue
        match = _DOM_DIFF_RE.fullmatch(child.name)
        if match is None:
            malformed.append(child.name)
            continue
        ordinal = int(match.group(1))
        if ordinal in by_ordinal:
            raise ValueError(f"Duplicate DOM diff ordinal {ordinal}")
        by_ordinal[ordinal] = child
    if malformed:
        raise ValueError(f"Malformed DOM diff filenames: {sorted(malformed)}")
    expected = list(range(1, action_count + 1))
    actual = sorted(by_ordinal)
    if actual != expected:
        raise ValueError(f"DOM diffs must be action-aligned: expected {expected}, got {actual}")
    return [by_ordinal[index] for index in expected]


def _require_allowed_files(root: Path, allowed: set[str], *, mode: str) -> None:
    unexpected = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() not in allowed
    )
    if unexpected:
        raise ValueError(f"Unexpected {mode} task files: {unexpected}")


def _load_answer(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Final answer must be an object: {path}")
    if not isinstance(value.get("final_answer"), str):
        raise ValueError(f"Final answer text is missing: {path}")
    return value


def _validate_sidecar(
    task_root: Path,
    base_task: dict[str, Any],
    rubric: dict[str, Any],
) -> bool:
    path = task_root / "task_data_with_canonical_rubric.json"
    if not path.is_file():
        return False
    sidecar = load_one_task(path)
    embedded = sidecar.pop("precomputed_rubric", None)
    base_without_rubric = dict(base_task)
    base_without_rubric.pop("precomputed_rubric", None)
    if canonical_json_bytes(sidecar) != canonical_json_bytes(base_without_rubric):
        raise ValueError(f"Frozen-rubric sidecar task fields differ: {path}")
    if canonical_json_bytes(embedded) != canonical_json_bytes(rubric):
        raise ValueError(f"Frozen-rubric sidecar rubric differs: {path}")
    return True


def validate_pair(
    screenshot_task: str | Path,
    dom_task: str | Path,
    *,
    rubric_file: str | Path,
    eval_config: str | Path | None = None,
) -> dict[str, Any]:
    screenshot = Path(screenshot_task).resolve(strict=True)
    dom = Path(dom_task).resolve(strict=True)
    for root, mode in ((screenshot, "screenshot"), (dom, "DOM")):
        if not root.is_dir():
            raise ValueError(f"Missing {mode} task directory: {root}")
        for filename in ("task_data.json", "web_surfer.log", "final_answer.json"):
            if not (root / filename).is_file():
                raise ValueError(f"Missing {mode} control file: {root / filename}")

    screenshot_data = load_one_task(screenshot / "task_data.json")
    dom_data = load_one_task(dom / "task_data.json")
    if canonical_json_bytes(screenshot_data) != canonical_json_bytes(dom_data):
        raise ValueError("task_data.json differs between screenshot and DOM tasks")
    internal_task_id = task_id(screenshot_data)
    if not internal_task_id or not task_instruction(screenshot_data):
        raise ValueError("Task data must contain task ID and instruction")
    if not task_init_url(screenshot_data):
        raise ValueError("Task data must contain the initial URL")

    frozen = load_canonical_rubric(rubric_file, expected_task_id=internal_task_id)
    for label, task in (("screenshot", screenshot_data), ("DOM", dom_data)):
        embedded = task.get("precomputed_rubric")
        if embedded is not None and canonical_json_bytes(embedded) != canonical_json_bytes(
            frozen.rubric
        ):
            raise ValueError(f"{label} runtime task rubric differs from canonical rubric")

    screenshot_actions = _parse_actions(screenshot / "web_surfer.log", mode="screenshot")
    dom_actions = _parse_actions(dom / "web_surfer.log", mode="dom")
    _compare_semantic_actions(screenshot_actions, dom_actions)

    screenshots = _ordered_screenshots(screenshot)
    if len(screenshots) != len(screenshot_actions) + 1:
        raise ValueError(
            "Controlled Microsoft dataset requires intentional N+1 screenshot states: "
            f"actions={len(screenshot_actions)}, screenshots={len(screenshots)}"
        )
    diffs = _ordered_dom_diffs(dom, len(dom_actions))

    screenshot_answer = _load_answer(screenshot / "final_answer.json")
    dom_answer = _load_answer(dom / "final_answer.json")
    for field in ("final_answer", "is_aborted"):
        if screenshot_answer.get(field) != dom_answer.get(field):
            raise ValueError(f"Final-answer field differs between modalities: {field}")
    if "screenshots" in dom_answer:
        raise ValueError("DOM final_answer.json must not contain a screenshots key")
    if dom_answer.get("token_usage") != {}:
        raise ValueError("DOM final_answer.json must contain token_usage: {}")
    references = screenshot_answer.get("screenshots") or []
    for reference in references:
        if not isinstance(reference, str) or not (screenshot / reference).is_file():
            raise ValueError(f"Missing screenshot referenced by final answer: {reference!r}")

    screenshot_sidecar = _validate_sidecar(screenshot, screenshot_data, frozen.rubric)
    dom_sidecar = _validate_sidecar(dom, dom_data, frozen.rubric)

    screenshot_allowed = {
        "task_data.json",
        "web_surfer.log",
        "final_answer.json",
        *(path.name for path in screenshots),
    }
    dom_allowed = {
        "task_data.json",
        "web_surfer.log",
        "final_answer.json",
        *(path.name for path in diffs),
    }
    if screenshot_sidecar:
        screenshot_allowed.add("task_data_with_canonical_rubric.json")
    if dom_sidecar:
        dom_allowed.add("task_data_with_canonical_rubric.json")
    _require_allowed_files(screenshot, screenshot_allowed, mode="screenshot")
    _require_allowed_files(dom, dom_allowed, mode="DOM")

    endpoint_receipt = validate_endpoint_configs(eval_config) if eval_config is not None else None
    return {
        "status": "pass",
        "task_alias": screenshot.name,
        "task_id": internal_task_id,
        "instruction": task_instruction(screenshot_data),
        "init_url": task_init_url(screenshot_data),
        "actions": len(screenshot_actions),
        "screenshot_states": len(screenshots),
        "dom_text_frames": len(diffs),
        "semantic_action_contract": "matched",
        "separate_action_logs_expected": True,
        "frozen_rubric_path": str(frozen.path),
        "frozen_rubric_sha256": frozen.sha256,
        "criterion_count": len(frozen.rubric["items"]),
        "criterion_denominator": frozen.denominator,
        "screenshot_sidecar_validated": screenshot_sidecar,
        "dom_sidecar_validated": dom_sidecar,
        "endpoint_config": endpoint_receipt,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot-task", required=True)
    parser.add_argument("--dom-task", required=True)
    parser.add_argument("--rubric-file", required=True)
    parser.add_argument("--eval-config")
    parser.add_argument("--receipt")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    receipt = validate_pair(
        args.screenshot_task,
        args.dom_task,
        rubric_file=args.rubric_file,
        eval_config=args.eval_config,
    )
    if args.receipt:
        write_json(args.receipt, receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
