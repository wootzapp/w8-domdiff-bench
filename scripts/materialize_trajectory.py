"""Materialize label-safe CUAVerifierBench rows into Fara trajectory folders."""

import argparse
import json
from pathlib import Path
from typing import Any

from cuav_data import CONFIG, DATASET_ID, SPLIT, load_frozen_split


ALLOWED_INPUT_FIELDS = {
    "task_id", "instruction", "init_url", "web_surfer_log", "screenshots",
    "final_answer", "is_aborted",
}
ROOT = Path("data/materialized")
TRAJ_ROOT = ROOT / "traj"
TASKS_PATH = ROOT / "tasks.json"
MANIFEST_PATH = Path("data/manifests/trajectory_manifest.json")
SUMMARY_ROOT = Path("outputs/day1")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def materialize(index: int, row: dict[str, Any]) -> dict[str, Any]:
    unexpected = set(row) - (ALLOWED_INPUT_FIELDS | {"start_timestamp", "end_timestamp", "n_screenshots"})
    task_id = str(row["task_id"])
    task_dir = TRAJ_ROOT / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    log_text = row["web_surfer_log"]
    if not isinstance(log_text, str):
        raise TypeError(f"{task_id}: expected string web_surfer_log, got {type(log_text).__name__}")
    log_lines = [line for line in log_text.splitlines() if line.strip()]
    for line in log_lines:
        json.loads(line)
    (task_dir / "web_surfer.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    screenshots = row["screenshots"] or []
    screenshot_names: list[str] = []
    for screenshot_index, image in enumerate(screenshots):
        name = f"screenshot{screenshot_index}.png"
        image.save(task_dir / name, format="PNG")
        screenshot_names.append(name)

    final_answer_payload = {
        "final_answer": row.get("final_answer", "<no_answer>"),
        "env_state_json": "<no_answer>",
        "env_state_raw": "<no_answer>",
        "screenshots": screenshot_names,
        "is_aborted": bool(row.get("is_aborted", False)),
        "is_rel_paths": True,
        "token_usage": {},
    }
    final_answer_path = task_dir / f"{task_id}_final_answer.json"
    _write_json(final_answer_path, final_answer_payload)

    input_summary = {
        "dataset": DATASET_ID, "config": CONFIG, "split": SPLIT,
        "dataset_index": index, "task_id": task_id,
        "included_fields": sorted(ALLOWED_INPUT_FIELDS),
        "excluded_annotation_fields": sorted(unexpected),
        "instruction_length": len(row["instruction"]),
        "init_url_present": bool(row.get("init_url")),
        "log_line_count": len(log_lines), "screenshot_count": len(screenshot_names),
        "final_answer_length": len(final_answer_payload["final_answer"]),
        "is_aborted": final_answer_payload["is_aborted"],
    }
    _write_json(SUMMARY_ROOT / task_id / "input_summary.json", input_summary)
    return {
        "dataset_index": index, "task_id": task_id,
        "screenshot_count": len(screenshot_names),
        "log_path": str(task_dir / "web_surfer.log"),
        "final_answer_path": str(final_answer_path),
        "input_summary_path": str(SUMMARY_ROOT / task_id / "input_summary.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--indices", type=int, nargs="+", required=True)
    args = parser.parse_args()
    dataset = load_frozen_split()
    tasks: list[dict[str, str]] = []
    manifest: list[dict[str, Any]] = []
    for index in args.indices:
        manifest_row = materialize(index, dataset[index])
        manifest.append(manifest_row)
        row = dataset[index]
        tasks.append({
            "task_id": manifest_row["task_id"],
            "confirmed_task": row["instruction"],
            "website": row.get("init_url", ""),
        })
    _write_json(TASKS_PATH, tasks)
    _write_json(MANIFEST_PATH, manifest)
    print(json.dumps({"tasks": tasks, "manifest": manifest}, indent=2))


if __name__ == "__main__":
    main()
