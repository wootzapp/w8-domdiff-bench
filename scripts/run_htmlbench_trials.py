#!/usr/bin/env python3
"""Run a balanced, resumable baseline-versus-HTMLBench recorder experiment."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from htmlbench_profiles import profile_names  # noqa: E402

DEFAULT_TASK_SET = ROOT / "configs" / "htmlbench_eval_tasks.json"


def load_tasks(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError("task set must be a non-empty JSON array")
    tasks = []
    for row in value:
        if not isinstance(row, dict) or not row.get("key") or not row.get("task_json"):
            raise ValueError("every task entry needs key and task_json")
        source = (ROOT / str(row["task_json"])).resolve()
        task = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(task, dict):
            raise ValueError(f"{source} is not a JSON object")
        tasks.append({**row, "definition": task, "source": str(source)})
    return tasks


def completed_trial(directory: Path, trial_id: str, profile: str) -> bool:
    if not directory.exists():
        return False
    for manifest_path in directory.rglob("manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        treatment = manifest.get("htmlbench_eval")
        if (
            str(manifest.get("task_id", "")).startswith(trial_id + "-")
            and isinstance(treatment, dict)
            and treatment.get("profile") == profile
            and manifest.get("status") in {"success", "failure", "error"}
        ):
            return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--task-set", type=Path, default=DEFAULT_TASK_SET)
    parser.add_argument(
        "--profiles", nargs="+", choices=profile_names(),
        default=["baseline", "htmlbench-full"],
    )
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument(
        "--task-key",
        action="append",
        help="run only the named frozen task key; repeat to select more than one",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be positive")
    tasks = load_tasks(args.task_set)
    if args.task_key:
        requested = set(args.task_key)
        known = {str(task["key"]) for task in tasks}
        unknown = sorted(requested - known)
        if unknown:
            raise SystemExit(f"unknown --task-key values: {', '.join(unknown)}")
        tasks = [task for task in tasks if str(task["key"]) in requested]
    failures = []
    for repetition in range(1, args.repetitions + 1):
        for task_index, task in enumerate(tasks):
            ordered_profiles = list(args.profiles)
            if (repetition + task_index) % 2 == 0:
                ordered_profiles.reverse()
            definition = task["definition"]
            for profile in ordered_profiles:
                trial_id = f"hbe-{task['key']}-{profile}-r{repetition}"
                output_dir = args.output_root.resolve() / profile / str(task["key"])
                if not args.rerun and completed_trial(output_dir, trial_id, profile):
                    print(f"skip completed {trial_id}")
                    continue
                command = [
                    str(ROOT / "run-task"),
                    trial_id,
                    str(definition.get("task_name") or task["key"]),
                    "--task", str(definition["instruction"]),
                    "--start-url", str(definition["start_url"]),
                    "--env-file", str(args.env_file.resolve()),
                    "--output-dir", str(output_dir),
                    "--htmlbench-profile", profile,
                    "--model", str(definition.get("model") or "gpt-5.1"),
                    "--max-steps", str(args.max_steps),
                    "--no-human-intervention",
                ]
                print(shlex.join(command), flush=True)
                if args.dry_run:
                    continue
                completed = subprocess.run(command, cwd=ROOT, check=False)
                if completed.returncode != 0:
                    failures.append({
                        "trial_id": trial_id,
                        "returncode": completed.returncode,
                    })
                    if args.stop_on_error:
                        print(json.dumps({"failures": failures}, indent=2))
                        return completed.returncode
    print(json.dumps({"failures": failures, "failure_count": len(failures)}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
