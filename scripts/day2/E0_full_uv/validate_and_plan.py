"""Validate all E0 inputs and build the fixed staged execution plan."""

import json
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from e0_common import (
    CORPUS_MANIFEST_PATH,
    EXECUTION_PLAN_PATH,
    FORBIDDEN_ANNOTATION_FIELDS,
    MANIFEST_ROOT,
    PROJECT_ROOT,
    RUN_INPUTS_ROOT,
    TASKS_PATH,
    TRAJ_ROOT,
    VALIDATION_PATH,
    ensure_output_dirs,
    read_jsonl,
    write_json,
    write_jsonl,
)

FARA_ROOT = PROJECT_ROOT / "repo/fara"
sys.path.insert(0, str(FARA_ROOT / "webeval/src"))
sys.path.insert(0, str(FARA_ROOT / "src"))
from webeval.trajectory import Trajectory  # noqa: E402


SCREENSHOT_RE = re.compile(r"^screenshot(\d+)\.png$")


def validate_one(task_dir: Path, task_ids: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "task_id": task_dir.name,
        "status": "valid",
        "reason": None,
        "event_count": 0,
        "action_count": 0,
        "screenshot_count": 0,
        "final_answer_json_readable": False,
        "task_present_in_tasks_json": task_dir.name in task_ids,
        "screenshots_open_successfully": False,
        "screenshots_contiguous_and_ordered": False,
        "forbidden_annotation_fields_present": [],
    }
    try:
        log_path = task_dir / "web_surfer.log"
        final_answers = sorted(task_dir.glob("*_final_answer.json"))
        if not log_path.is_file() or len(final_answers) != 1:
            result.update(status="missing_file", reason="missing action log or unique final-answer JSON")
            return result
        if task_dir.name not in task_ids:
            result.update(status="invalid_input", reason="task ID absent from tasks.json")
            return result

        log_text = log_path.read_text(encoding="utf-8")
        for line in log_text.splitlines():
            if line.strip():
                json.loads(line)
        final_text = final_answers[0].read_text(encoding="utf-8")
        json.loads(final_text)
        result["final_answer_json_readable"] = True

        leaked = sorted(
            field
            for field in FORBIDDEN_ANNOTATION_FIELDS
            if field in log_text or field in final_text
        )
        result["forbidden_annotation_fields_present"] = leaked
        if leaked:
            result.update(status="invalid_input", reason="forbidden annotation field materialized")
            return result

        screenshots: list[tuple[int, Path]] = []
        for path in task_dir.glob("screenshot*.png"):
            match = SCREENSHOT_RE.match(path.name)
            if match:
                screenshots.append((int(match.group(1)), path))
        screenshots.sort()
        indices = [index for index, _ in screenshots]
        result["screenshot_count"] = len(screenshots)
        result["screenshots_contiguous_and_ordered"] = indices == list(range(len(indices)))
        if not screenshots or not result["screenshots_contiguous_and_ordered"]:
            result.update(status="invalid_input", reason="screenshots absent or non-contiguous")
            return result
        for _, screenshot in screenshots:
            with Image.open(screenshot) as image:
                image.verify()
        result["screenshots_open_successfully"] = True

        trajectory = Trajectory.from_folder(task_dir)
        if trajectory is None:
            result.update(status="parse_failure", reason="Trajectory.from_folder returned None")
            return result
        actions = [event for event in trajectory.events if event.get("action")]
        result["event_count"] = len(trajectory.events)
        result["action_count"] = len(actions)
        if not actions:
            result.update(status="invalid_input", reason="no parsed actions")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError) as exc:
        result.update(status="parse_failure", reason=f"{type(exc).__name__}: {exc}")
    except Exception as exc:  # keep every dataset row accounted for
        result.update(status="parse_failure", reason=f"{type(exc).__name__}: {exc}")
    return result


def reset_link_root(name: str, task_ids: list[str]) -> Path:
    root = RUN_INPUTS_ROOT / name
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            raise RuntimeError(f"Unexpected real directory in generated link root: {child}")
    for task_id in task_ids:
        (root / task_id).symlink_to(TRAJ_ROOT / task_id, target_is_directory=True)
    return root


def main() -> None:
    ensure_output_dirs()
    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    task_ids = {str(row["task_id"]) for row in tasks}
    manifest = read_jsonl(CORPUS_MANIFEST_PATH)
    if len(manifest) != 106 or len(task_ids) != 106:
        raise RuntimeError(f"Expected 106 manifest rows and task IDs; got {len(manifest)} and {len(task_ids)}")

    validation = [validate_one(TRAJ_ROOT / row["task_id"], task_ids) for row in manifest]
    validation_by_id = {row["task_id"]: row for row in validation}
    for row in manifest:
        checked = validation_by_id[row["task_id"]]
        row["input_validation_status"] = checked["status"]
        row["validation_reason"] = checked["reason"]
    write_jsonl(VALIDATION_PATH, validation)
    write_jsonl(CORPUS_MANIFEST_PATH, manifest)

    valid = [row for row in manifest if row["input_validation_status"] == "valid"]
    eligible = sorted(valid, key=lambda row: (row["screenshot_count"], row["task_id"]))
    if len(eligible) < 13:
        raise RuntimeError(f"Need at least 13 valid tasks for staged E0; found {len(eligible)}")
    preflight_rows = [eligible[0], eligible[len(eligible) // 2], eligible[-1]]
    if len({row["task_id"] for row in preflight_rows}) != 3:
        raise RuntimeError("Short/medium/long preflight selection did not yield three unique tasks")
    preflight_ids = [row["task_id"] for row in preflight_rows]
    remaining_ids = [row["task_id"] for row in valid if row["task_id"] not in set(preflight_ids)]
    batch_10_ids = remaining_ids[:10]
    remainder_ids = remaining_ids[10:]

    roots = {
        "preflight": reset_link_root("preflight", preflight_ids),
        "batch_10": reset_link_root("batch_10", batch_10_ids),
        "remainder": reset_link_root("remainder", remainder_ids),
    }
    selection_roles = ["short", "medium", "long"]
    selection = [
        {
            "role": role,
            "task_id": row["task_id"],
            "action_count": row["action_count"],
            "screenshot_count": row["screenshot_count"],
            "selection_basis": "valid input; screenshot-count order only",
        }
        for role, row in zip(selection_roles, preflight_rows)
    ]
    plan = {
        "total_rows": len(manifest),
        "valid_inputs": len(valid),
        "invalid_inputs": len(manifest) - len(valid),
        "preflight": preflight_ids,
        "batch_10": batch_10_ids,
        "remainder": remainder_ids,
        "run_input_roots": {key: str(value.relative_to(PROJECT_ROOT)) for key, value in roots.items()},
        "selection_uses_labels_or_stored_verifier_outputs": False,
    }
    write_json(MANIFEST_ROOT / "preflight_selection.json", selection)
    write_json(EXECUTION_PLAN_PATH, plan)
    counts: dict[str, int] = {}
    for row in validation:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(json.dumps({"validation": counts, "plan_counts": {"preflight": 3, "batch_10": len(batch_10_ids), "remainder": len(remainder_ids)}, "selection": selection}))


if __name__ == "__main__":
    main()
