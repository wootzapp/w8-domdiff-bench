"""Evaluate finalized ledger recordings while preserving their Batch queues."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ledger", type=Path, required=True)
parser.add_argument("--rubric-dir", type=Path, default=Path("data/rubrics"))
parser.add_argument("--compare-profiles", action="store_true",
    help="evaluate primary and Pro profiles separately")
parser.add_argument("--execute", action="store_true",
    help="authorize judging or poll submitted work; otherwise check inputs only")
args = parser.parse_args()
rows = [json.loads(line) for line in args.ledger.read_text().splitlines() if line.strip()]
runs = [row["recording"] for row in rows if (Path(row["recording"]) / "final.json").is_file()]
if not runs:
    parser.error("no finalized recordings available for judging")
groups = {}
for run in runs:
    queue = Path(run).resolve().parent.parent / "evaluations" / "batch_jobs"
    groups.setdefault(str(queue), []).append(run)
pending = False
for queue, selected_runs in groups.items():
    command = [sys.executable, "-m", "w8bench.verifier.run_comparison", "--run", *selected_runs,
        "--rubric", str(args.rubric_dir), "--judge-model", "gpt-6.1-sol",
        "--judge-transport", "batch"]
    if args.compare_profiles:
        command.append("--compare-profiles")
    if args.execute:
        command.append("--execute")
    result = subprocess.run(command, check=False)
    if result.returncode not in (0, 75):
        sys.exit(result.returncode)
    pending = pending or result.returncode == 75
    print(json.dumps({"queue": queue, "exit_code": result.returncode}))
sys.exit(75 if pending else 0)
