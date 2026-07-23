"""Materialize all 106 frozen trajectories using only the E0 input allow-list."""

import json
from typing import Any

from e0_common import (
    ALLOWED_INPUT_FIELDS,
    MANIFEST_ROOT,
    TASKS_PATH,
    TRAJ_ROOT,
    PROJECT_ROOT,
    ensure_output_dirs,
    write_json,
    write_jsonl,
)
from cuav_data import CONFIG, DATASET_ID, SPLIT, load_frozen_split


EXPECTED_ROWS = 106


def sanitize(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in ALLOWED_INPUT_FIELDS}


def main() -> None:
    ensure_output_dirs()
    dataset = load_frozen_split()
    if len(dataset) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} rows, found {len(dataset)}")

    tasks: list[dict[str, str]] = []
    manifest: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()

    for dataset_index in range(len(dataset)):
        safe = sanitize(dataset[dataset_index])
        task_id = str(safe["task_id"])
        if task_id in seen_task_ids:
            raise RuntimeError(f"Duplicate task_id: {task_id}")
        seen_task_ids.add(task_id)
        task_dir = TRAJ_ROOT / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        log_text = safe["web_surfer_log"]
        if not isinstance(log_text, str):
            raise TypeError(f"{task_id}: web_surfer_log must be a string")
        log_lines = [line for line in log_text.splitlines() if line.strip()]
        events = [json.loads(line) for line in log_lines]
        (task_dir / "web_surfer.log").write_text(
            "\n".join(log_lines) + ("\n" if log_lines else ""), encoding="utf-8"
        )

        screenshot_names: list[str] = []
        for screenshot_index, image in enumerate(safe["screenshots"] or []):
            name = f"screenshot{screenshot_index}.png"
            image.save(task_dir / name, format="PNG")
            screenshot_names.append(name)

        final_answer = safe.get("final_answer") or "<no_answer>"
        final_answer_path = task_dir / f"{task_id}_final_answer.json"
        write_json(
            final_answer_path,
            {
                "final_answer": final_answer,
                "env_state_json": "<no_answer>",
                "env_state_raw": "<no_answer>",
                "screenshots": screenshot_names,
                "is_aborted": bool(safe.get("is_aborted", False)),
                "is_rel_paths": True,
                "token_usage": {},
            },
        )

        tasks.append(
            {
                "task_id": task_id,
                "confirmed_task": safe["instruction"] or "",
                "website": safe.get("init_url") or "",
            }
        )
        manifest.append(
            {
                "dataset_index": dataset_index,
                "task_id": task_id,
                "instruction_present": bool(safe.get("instruction")),
                "initial_url_present": bool(safe.get("init_url")),
                "action_count": sum(1 for event in events if event.get("action")),
                "screenshot_count": len(screenshot_names),
                "final_answer_present": bool(final_answer and final_answer != "<no_answer>"),
                "materialized_path": str(task_dir.relative_to(PROJECT_ROOT)),
                "input_validation_status": "pending",
            }
        )

    write_json(TASKS_PATH, tasks)
    write_jsonl(MANIFEST_ROOT / "full_corpus_manifest.jsonl", manifest)
    write_json(
        MANIFEST_ROOT / "materialization_summary.json",
        {
            "dataset": DATASET_ID,
            "configuration": CONFIG,
            "split": SPLIT,
            "row_count": len(dataset),
            "unique_task_ids": len(seen_task_ids),
            "allowed_input_fields": sorted(ALLOWED_INPUT_FIELDS),
            "human_or_stored_verifier_fields_copied": False,
        },
    )
    print(json.dumps({"materialized": len(manifest), "tasks": len(tasks)}))


if __name__ == "__main__":
    main()
