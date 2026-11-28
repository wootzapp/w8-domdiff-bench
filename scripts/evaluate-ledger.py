"""Evaluate finalized ledger recordings using their own paired evidence."""

import argparse
import hashlib
import json
from pathlib import Path
from w8bench.run_paths import run_directory
import subprocess
import sys


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ledger", type=Path, required=True)
parser.add_argument("--rubric-dir", type=Path, default=Path("data/rubrics"))
parser.add_argument("--compare-profiles", action="store_true",
    help="evaluate primary and Pro profiles separately")
parser.add_argument("--stage", choices=("evaluate", "adjudicate"), default="evaluate",
    help="evaluate completion, native evidence and inventory, or adjudicate saved inventory")
parser.add_argument("--execute", action="store_true",
    help="authorize judging; otherwise check inputs only")
args = parser.parse_args()
rows = [json.loads(line) for line in args.ledger.read_text().splitlines() if line.strip()]
if args.stage == "adjudicate" and any(not row.get("completed")
        or row.get("technical_outcome") in {"not_started", "running"}
        or row.get("technical_outcome") == "technical_failure" and len(row.get("attempts", [])) < 2
        or row.get("attempts") and not row["attempts"][-1].get("completed") for row in rows):
    parser.error("adjudication requires every scheduled actor and technical rerun to finish")
runs = [row["recording"] for row in rows if (Path(row["recording"]) / "final.json").is_file()]
if args.stage == "adjudicate":
    from w8bench.task_recorder.prepare_verifier_data import inspect_recording
    from w8bench.verifier.run_full_comparison import _read_ledger, _validate_scheduled_recording, _scheduled_summary, _scheduled_grade
    try:
        _read_ledger(args.ledger)
    except (KeyError, TypeError, ValueError) as error:
        parser.error(str(error))
    runs, unavailable = [], []
    for row in rows:
        source = Path(row["recording"])
        if not all((source / name).is_file() for name in ("manifest.json", "final.json")):
            unavailable.append({"recording": str(source), "reason": "recording_not_finalized"})
            continue
        checked = inspect_recording(source)
        _validate_scheduled_recording(row, row["arm"], checked["task"], checked["manifest"])
        summary = _scheduled_summary({**row, "evaluation_outcome": None}, checked, checked["manifest"])
        _scheduled_grade(row, summary)
        if not checked["coverage"]["audit_eligible_states"]:
            unavailable.append({"recording": str(source), "reason": "no_eligible_paired_states"})
            continue
        ready = False
        for profile in (("primary", "pro") if args.compare_profiles else ("primary",)):
            root = run_directory(source, area="evaluations") / profile
            receipt = root / "evaluation.json"
            if not receipt.is_file():
                parser.error(f"evaluate {source} with profile {profile} before adjudication")
            evaluation = json.loads(receipt.read_text())
            if any(evaluation.get(key) != expected for key, expected in (
                    ("recording_sha256", checked["recording_sha256"]), ("task_id", row["task_id"]),
                    ("actor_arm", row["arm"]), ("trial_id", row["run_name"]))):
                parser.error(f"evaluation receipt belongs to different inputs: {receipt}")
            stages = evaluation.get("stages", {})
            if any(stages.get(name, {}).get("status") in {"ungraded", "blocked", "not_available", "not_eligible"}
                    for name in ("paired_completion", "screenshot_verifier", "dom_model")):
                unavailable.append({"recording": str(source), "profile": profile,
                    "reason": "verifier_results_unavailable"})
                continue
            inventory = stages.get("audit", {}).get("inventory", {})
            inventory_path = root / "audit_inventory.json"
            if (inventory.get("status") != "complete" or not inventory_path.is_file()
                    or Path(inventory.get("result", "")).resolve() != inventory_path.resolve()
                    or hashlib.sha256(inventory_path.read_bytes()).hexdigest() != inventory.get("result_sha256")):
                parser.error(f"complete inventory evaluation before adjudication: {root}")
            ready = True
        if ready:
            runs.append(row["recording"])
    if unavailable:
        print(json.dumps({"stage": "adjudicate", "unavailable": unavailable}))
    if not runs:
        print(json.dumps({"stage": "adjudicate", "eligible_recordings": 0, "model_calls": 0}))
        sys.exit(0)
if not runs:
    parser.error("no finalized recordings available for judging")
command = [sys.executable, "-m", "w8bench.verifier.run_comparison", "--run", *runs,
    "--rubric", str(args.rubric_dir), "--judge-model", "gemini-3.6-flash", "--stage", args.stage]
if args.compare_profiles:
    command.append("--compare-profiles")
if args.execute:
    command.append("--execute")
result = subprocess.run(command, check=False)
if args.execute:
    from w8bench.task_recorder.task_cli import _execute_batch_judge, task_transition_lock, RUNTIME_ROOT
    from w8bench.task_recorder.recorder_support import write_json_lines, utc_now
    with task_transition_lock(RUNTIME_ROOT / "batch.lock"):
        rows = [json.loads(line) for line in args.ledger.read_text().splitlines() if line.strip()]
        selected_rows = [row for row in rows if row["recording"] in runs]
        _execute_batch_judge(args, selected_rows, reconcile_only=True)
        if result.returncode == 130:
            for row in selected_rows:
                row.update(evaluation_outcome="interrupted", grade_outcome="ungraded",
                    judge_exit_code=130, grade_completed=False, judge_ended_at=utc_now())
        write_json_lines(args.ledger, rows)
print(json.dumps({"stage": args.stage, "recordings": len(runs), "exit_code": result.returncode}))
sys.exit(result.returncode)
