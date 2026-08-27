#!/usr/bin/env python3
"""Run a balanced, resumable HTMLCure recorder experiment."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from htmlbench_profiles import get_profile, profile_names  # noqa: E402

DEFAULT_TASK_SET = ROOT / "configs" / "htmlbench_eval_tasks.json"
OFFICIAL_POSTRUN = ROOT / "scripts" / "run_official_htmlcure_postrun.py"
OFFICIAL_PYTHON = ROOT / ".runtime" / "htmlcure-venv" / "bin" / "python"


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


def resolve_start_url(definition: dict[str, Any]) -> str:
    """Resolve the separately hosted official fixture without storing a Docker IP."""
    value = str(definition["start_url"])
    if value != "${HTMLCURE_FIXTURE_URL}":
        return value
    fixture_url = os.environ.get("HTMLCURE_FIXTURE_URL")
    if not fixture_url:
        raise ValueError(
            "HTMLCURE_FIXTURE_URL is required for the official fixture task"
        )
    return fixture_url


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


def trial_run_directory(directory: Path, trial_id: str) -> Path:
    """Resolve the newly completed timestamped directory for one trial ID."""
    candidates = [
        path
        for path in directory.iterdir()
        if path.is_dir()
        and path.name.startswith(trial_id + "-")
        and (path / "manifest.json").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"no recorded run found for {trial_id} in {directory}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def run_official_postrun(run_dir: Path, profile: str) -> int:
    """Run exact official HTMLCure probes after recorder evidence is complete."""
    if not OFFICIAL_PYTHON.exists():
        raise FileNotFoundError(
            f"official HTMLCure virtual environment is missing: {OFFICIAL_PYTHON}"
        )
    port = 49345 + get_profile(profile).port_offset
    command = [
        str(OFFICIAL_PYTHON),
        str(OFFICIAL_POSTRUN),
        "--cdp-url",
        f"http://127.0.0.1:{port}",
        "--run-dir",
        str(run_dir),
    ]
    print(shlex.join(command), flush=True)
    try:
        return subprocess.run(
            command, cwd=ROOT, check=False, timeout=150
        ).returncode
    except subprocess.TimeoutExpired:
        print(
            f"official HTMLCure post-run exceeded 150 seconds: {run_dir}",
            file=sys.stderr,
        )
        return 124


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--task-set", type=Path, default=DEFAULT_TASK_SET)
    parser.add_argument(
        "--profiles", nargs="+", choices=profile_names(),
        default=["baseline", "htmlbench-full"],
    )
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument(
        "--task-key",
        action="append",
        help="run only the named frozen task key; repeat to select more than one",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument(
        "--skip-official-postrun",
        action="store_true",
        help="skip exact official HTMLCure probes after each recorded task",
    )
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
    postrun_failures = []
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
                    "--start-url", resolve_start_url(definition),
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
                run_dir = None
                try:
                    run_dir = trial_run_directory(output_dir, trial_id)
                except (FileNotFoundError, OSError) as error:
                    postrun_failures.append(
                        {"trial_id": trial_id, "error": str(error)}
                    )
                if run_dir is not None and not args.skip_official_postrun:
                    postrun_returncode = run_official_postrun(run_dir, profile)
                    if postrun_returncode != 0:
                        postrun_failures.append(
                            {
                                "trial_id": trial_id,
                                "returncode": postrun_returncode,
                            }
                        )
                if completed.returncode != 0:
                    failures.append({
                        "trial_id": trial_id,
                        "returncode": completed.returncode,
                    })
                    if args.stop_on_error:
                        print(json.dumps({"failures": failures}, indent=2))
                        return completed.returncode
                if postrun_failures and args.stop_on_error:
                    print(
                        json.dumps(
                            {
                                "failures": failures,
                                "postrun_failures": postrun_failures,
                            },
                            indent=2,
                        )
                    )
                    return 1
    print(
        json.dumps(
            {
                "failures": failures,
                "failure_count": len(failures),
                "postrun_failures": postrun_failures,
                "postrun_failure_count": len(postrun_failures),
            },
            indent=2,
        )
    )
    return 1 if failures or postrun_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
