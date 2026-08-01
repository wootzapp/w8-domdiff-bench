#!/usr/bin/env python3
"""Validate paired screenshot/DOM tasks and an optional frozen rubric."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_DOM_RELATIVE = (
    "before/chromiumrl_dom.json",
    "after/chromiumrl_dom.json",
    "dom_diff.json",
    "before/page_state.json",
    "after/page_state.json",
    "verifier_action.json",
)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalized_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def task_row(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError(f"Expected one task in {path}")
        return value[0]
    if not isinstance(value, dict):
        raise ValueError(f"Expected task object/list in {path}")
    return value


def action_count(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
            if event.get("action"):
                count += 1
    return count


def answer_files(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("*_answer.json") if path.is_file())


def extract_rubric_from_task(path: Path) -> Any:
    if not path.is_file():
        return None
    return task_row(path).get("precomputed_rubric")


def rubric_total(rubric: dict[str, Any]) -> float:
    items = rubric.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Rubric must contain a non-empty items list")
    seen: set[str] = set()
    total = 0.0
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Rubric item {index} is not an object")
        criterion = item.get("criterion")
        if not isinstance(criterion, str) or not criterion.strip():
            raise ValueError(f"Rubric item {index} has no criterion")
        if criterion in seen:
            raise ValueError(f"Duplicate rubric criterion: {criterion}")
        seen.add(criterion)
        points = item.get("max_points")
        if not isinstance(points, (int, float)) or points <= 0:
            raise ValueError(f"Invalid max_points for {criterion}")
        if item.get("justification", "") != "" or item.get("earned_points", "") != "":
            raise ValueError(f"Frozen rubric is already scored: {criterion}")
        total += float(points)
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot-task", type=Path, required=True)
    parser.add_argument("--dom-task", type=Path, required=True)
    parser.add_argument("--rubric-json", type=Path)
    parser.add_argument("--rubric-tsv", type=Path)
    parser.add_argument("--expected-total", type=float, default=10.0)
    args = parser.parse_args()
    errors: list[str] = []

    screenshot = args.screenshot_task.resolve()
    dom = args.dom_task.resolve()
    for label, root in (("screenshot", screenshot), ("DOM", dom)):
        if not root.is_dir():
            fail(errors, f"Missing {label} task directory: {root}")
            continue
        for filename in ("task_data.json", "final_answer.json", "web_surfer.log"):
            if not (root / filename).is_file():
                fail(errors, f"Missing {label} input: {root / filename}")

    if errors:
        print("\n".join(f"ERROR: {value}" for value in errors), file=sys.stderr)
        return 1

    screenshot_task = task_row(screenshot / "task_data.json")
    dom_task = task_row(dom / "task_data.json")
    screenshot_id = str(screenshot_task.get("task_id") or screenshot_task.get("id") or "")
    dom_id = str(dom_task.get("task_id") or dom_task.get("id") or "")
    screenshot_instruction = screenshot_task.get("confirmed_task") or screenshot_task.get("question")
    dom_instruction = dom_task.get("confirmed_task") or dom_task.get("question")
    if screenshot_id != dom_id:
        fail(errors, f"Task ID mismatch: {screenshot_id!r} != {dom_id!r}")
    if screenshot_instruction != dom_instruction:
        fail(errors, "Task instruction mismatch between evidence modes")

    screenshot_log_hash = hashlib.sha256((screenshot / "web_surfer.log").read_bytes()).hexdigest()
    dom_log_hash = hashlib.sha256((dom / "web_surfer.log").read_bytes()).hexdigest()
    if screenshot_log_hash != dom_log_hash:
        fail(errors, "web_surfer.log hashes differ between evidence modes")
    screenshot_actions = action_count(screenshot / "web_surfer.log")
    dom_actions = action_count(dom / "web_surfer.log")
    if screenshot_actions != dom_actions:
        fail(errors, f"Action count mismatch: {screenshot_actions} != {dom_actions}")

    for label, root in (("screenshot", screenshot), ("DOM", dom)):
        answers = answer_files(root)
        if len(answers) != 1:
            fail(errors, f"Expected exactly one *_answer.json in {label} task; found {len(answers)}")
    screenshot_answer = load_json(screenshot / "final_answer.json")
    dom_answer = load_json(dom / "final_answer.json")
    for field in ("final_answer", "is_aborted"):
        if screenshot_answer.get(field) != dom_answer.get(field):
            fail(errors, f"Final-answer field mismatch: {field}")

    screenshot_references = screenshot_answer.get("screenshots") or []
    if len(screenshot_references) < screenshot_actions:
        fail(
            errors,
            f"Screenshot reference/action mismatch: {len(screenshot_references)} references for {screenshot_actions} actions",
        )
    for reference in screenshot_references:
        if not isinstance(reference, str) or not (screenshot / reference).is_file():
            fail(errors, f"Missing referenced screenshot: {reference!r}")

    screenshots = sorted(path for path in screenshot.rglob("*") if path.is_file() and "screenshot" in path.name.lower() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    dom_screenshots = sorted(path for path in dom.rglob("*") if path.is_file() and "screenshot" in path.name.lower() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    if not screenshots:
        fail(errors, "Screenshot task contains no screenshot images")
    if dom_screenshots:
        fail(errors, f"DOM task contains {len(dom_screenshots)} screenshot images")
    if dom_answer.get("screenshots") not in ([], None):
        fail(errors, "DOM final_answer.json must have an empty screenshots list")

    steps = sorted(path for path in dom.glob("step_[0-9][0-9][0-9]") if path.is_dir())
    if len(steps) != dom_actions:
        fail(errors, f"DOM step/action mismatch: {len(steps)} steps for {dom_actions} actions")
    for ordinal, step in enumerate(steps, 1):
        expected_name = f"step_{ordinal:03d}"
        if step.name != expected_name:
            fail(errors, f"Non-contiguous DOM step: expected {expected_name}, got {step.name}")
        for relative in REQUIRED_DOM_RELATIVE:
            if not (step / relative).is_file():
                fail(errors, f"Missing DOM evidence: {step / relative}")

    rubric = None
    rubric_hash = None
    if bool(args.rubric_json) != bool(args.rubric_tsv):
        fail(errors, "Provide both --rubric-json and --rubric-tsv, or neither")
    elif args.rubric_json and args.rubric_tsv:
        rubric = load_json(args.rubric_json.resolve())
        total = rubric_total(rubric)
        if total != args.expected_total:
            fail(errors, f"Rubric maximum is {total}, expected {args.expected_total}")
        rubric_hash = normalized_hash(rubric)
        with args.rubric_tsv.resolve().open("r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        if len(rows) != 1:
            fail(errors, f"Expected one TSV row; found {len(rows)}")
        else:
            row = rows[0]
            if row.get("id") != screenshot_id:
                fail(errors, f"TSV ID {row.get('id')!r} != task ID {screenshot_id!r}")
            if row.get("task_summary") != screenshot_instruction:
                fail(errors, "TSV task instruction differs from task_data.json")
            try:
                tsv_rubric = json.loads(row.get("precomputed_rubric") or "")
            except json.JSONDecodeError as exc:
                fail(errors, f"Invalid TSV rubric JSON: {exc}")
            else:
                if tsv_rubric != rubric:
                    fail(errors, "TSV rubric differs from canonical rubric JSON")
        for label, path in (
            ("screenshot", screenshot / "task_data_with_canonical_rubric.json"),
            ("DOM", dom / "task_data_with_canonical_rubric.json"),
        ):
            embedded = extract_rubric_from_task(path)
            if embedded is None:
                fail(errors, f"Missing task-local frozen rubric: {path}")
            elif embedded != rubric:
                fail(errors, f"Task-local {label} rubric differs from canonical rubric")

    if errors:
        print("\n".join(f"ERROR: {value}" for value in errors), file=sys.stderr)
        return 1

    print(json.dumps({
        "status": "pass",
        "task_id": screenshot_id,
        "instruction": screenshot_instruction,
        "actions": screenshot_actions,
        "screenshot_images": len(screenshots),
        "dom_steps": len(steps),
        "dom_screenshot_images": len(dom_screenshots),
        "web_surfer_sha256": screenshot_log_hash,
        "frozen_rubric_sha256": rubric_hash,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
