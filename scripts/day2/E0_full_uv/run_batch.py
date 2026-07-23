"""Run one fixed E0 stage through Microsoft's official verifier entry point."""

import argparse
import json
import os
import subprocess
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

from e0_common import (
    BATCH_REPORT_ROOT,
    LOG_ROOT,
    PROJECT_ROOT,
    RUN_INPUTS_ROOT,
    TASKS_PATH,
    ensure_output_dirs,
    write_json,
)

ALLOWED_BATCHES = {"preflight", "preflight_cache_check", "batch_10", "remainder", "retry"}


def archive_existing(path: Path) -> None:
    """Never silently overwrite evidence from an earlier batch attempt."""
    if not path.exists():
        return
    attempt = 1
    while True:
        archived = path.with_name(f"{path.stem}_attempt_{attempt}{path.suffix}")
        if not archived.exists():
            shutil.move(path, archived)
            return
        attempt += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch", choices=sorted(ALLOWED_BATCHES))
    parser.add_argument("--input-name", default=None)
    parser.add_argument("--redo-eval", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_output_dirs()
    input_name = args.input_name or ("preflight" if args.batch == "preflight_cache_check" else args.batch)
    input_root = RUN_INPUTS_ROOT / input_name
    if not input_root.is_dir():
        raise SystemExit(f"Missing staged input root: {input_root}")

    key = dotenv_values(PROJECT_ROOT / ".env").get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Ignored .env does not contain a non-empty OPENAI_API_KEY")
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = key
    report = BATCH_REPORT_ROOT / f"{args.batch}.jsonl"
    log = LOG_ROOT / f"{args.batch}.log"
    status_path = LOG_ROOT / f"{args.batch}_status.json"
    for artifact in (report, log, status_path):
        archive_existing(artifact)
    command = [
        sys.executable,
        "repo/fara/webeval/scripts/verify_trajectories.py",
        "--input", str(input_root.relative_to(PROJECT_ROOT)),
        "--task-data", str(TASKS_PATH.relative_to(PROJECT_ROOT)),
        "--task-data-format", "om2w",
        "--eval-config", "endpoint_configs/openai/canonical",
        "--judge-model", "gpt-5.2",
        "--o4mini-model", "o4-mini",
        "--processes", "1",
        "--rubric-threshold", "0.8",
        "--max-images-per-criterion", "5",
        "--mm-keypoint-score-threshold", "3",
        "--majority-vote-instances", "1",
        "--success", "outcome",
        "--report", str(report.relative_to(PROJECT_ROOT)),
    ]
    if args.redo_eval:
        command.append("--redo-eval")
    started = datetime.now(timezone.utc)
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    ended = datetime.now(timezone.utc)
    payload = {
        "batch": args.batch,
        "input_name": input_name,
        "command": command,
        "started_at_utc": started.isoformat(),
        "ended_at_utc": ended.isoformat(),
        "duration_sec": round((ended - started).total_seconds(), 2),
        "returncode": completed.returncode,
        "report_path": str(report.relative_to(PROJECT_ROOT)),
        "log_path": str(log.relative_to(PROJECT_ROOT)),
        "credential_source": "ignored .env",
        "secret_logged_by_wrapper": False,
    }
    write_json(status_path, payload)
    print(json.dumps({key: payload[key] for key in ("batch", "duration_sec", "returncode", "report_path", "log_path")}))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
