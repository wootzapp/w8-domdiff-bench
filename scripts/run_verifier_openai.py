"""Run the official verifier with local output capture and no key disclosure."""

import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(".")
LOG_PATH = ROOT / "outputs/day1/logs/verifier_run_openai.log"
SUMMARY_PATH = ROOT / "outputs/day1/verifier_run_openai_status.json"


def main() -> int:
    key = dotenv_values(ROOT / ".env").get("OPENAI_API_KEY")
    if not key:
        raise SystemExit(".env does not contain a non-empty OPENAI_API_KEY")
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = key
    command = [
        sys.executable,
        "repo/fara/webeval/scripts/verify_trajectories.py",
        "--input", "data/materialized/traj",
        "--task-data", "data/materialized/tasks.json",
        "--task-data-format", "om2w",
        "--eval-config", "endpoint_configs/openai/prod",
        "--judge-model", "gpt-4o",
        "--o4mini-model", "gpt-4o",
        "--processes", "1",
        "--limit", "1",
        "--rubric-threshold", "0.8",
        "--max-images-per-criterion", "5",
        "--mm-keypoint-score-threshold", "3",
        "--majority-vote-instances", "1",
        "--success", "outcome",
        "--report", "outputs/day1/verify_report_openai.jsonl",
    ]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    payload = {"returncode": completed.returncode, "log_path": str(LOG_PATH)}
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
