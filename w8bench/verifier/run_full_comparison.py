#!/usr/bin/env python3
"""Generate one frozen rubric, then score screenshot and DOM evidence with it."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
import os
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

from .common import ensure_under
from .common import load_json, write_json
from .dataset_sync import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_REPO_ID,
    DEFAULT_REVISION,
    fetch_trajectories,
)
from .evidence_audit import DEFAULT_AUDIT_MODEL, aggregate_audits, render_aggregate_markdown
from .generate_frozen_rubric import main as generate_rubric
from .run_comparison import main as run_comparison
from .validate_inputs import dataset_only_preflight


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--task", help="Task folder alias, e.g. task_01")
    selection.add_argument("--all", action="store_true", help="Run every paired task")
    parser.add_argument("--data-source", choices=("local", "huggingface"), default="huggingface",
                        help="Use local prepared trajectories or published Hugging Face trajectories")
    parser.add_argument("--data-root", type=Path,
                        help="Local trajectory folder (default in local mode: trajectories/)")
    parser.add_argument("--eval-config", default=str(REPOSITORY_ROOT / "config"))
    parser.add_argument("--env-file", default=str(REPOSITORY_ROOT / ".env"))
    parser.add_argument("--results-root", default=str(REPOSITORY_ROOT / "evaluation"))
    parser.add_argument("--run-id")
    parser.add_argument("--audit-model", default=DEFAULT_AUDIT_MODEL)
    parser.add_argument("--hf-repo", default=DEFAULT_REPO_ID)
    parser.add_argument("--hf-revision", default=DEFAULT_REVISION)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.data_source == "huggingface" and args.data_root is not None:
        parser.error("--data-root requires --data-source local")
    if args.task and (Path(args.task).name != args.task or args.task in {".", ".."} or "\\" in args.task):
        parser.error("--task must name one task folder, not a path")
    return args


def _task_path(data_root: Path, folder: str, task: str) -> Path:
    return ensure_under(
        (data_root / folder / task).resolve(strict=True),
        data_root,
        label=f"{folder} task",
    )


def _paired_tasks(data_root: Path) -> list[str]:
    screenshot_root = data_root / "data-ss"
    dom_root = data_root / "data-dom"
    if not screenshot_root.is_dir() or not dom_root.is_dir():
        raise ValueError(f"Verifier inputs lack paired data-ss and data-dom directories: {data_root}")
    screenshot = {path.name for path in screenshot_root.iterdir() if path.is_dir()}
    dom = {path.name for path in dom_root.iterdir() if path.is_dir()}
    if screenshot != dom:
        raise ValueError(
            "Paired task aliases differ: "
            + json.dumps(
                {"screenshot_only": sorted(screenshot - dom), "dom_only": sorted(dom - screenshot)}
            )
        )
    if not screenshot:
        raise ValueError("No paired tasks were found")
    return sorted(screenshot)


def _validate_task(data_root: Path, task: str) -> dict:
    return dataset_only_preflight(
        _task_path(data_root, "data-ss", task), _task_path(data_root, "data-dom", task)
    )


def _verify_local_preparation(data_root: Path, task: str) -> None:
    """Detect stale or edited bundles using the converter's saved receipts."""
    report_path = data_root / "preparation_report.json"
    if not report_path.is_file():
        return  # Explicit local pairs prepared outside this converter remain supported.
    report = _preparation_report(data_root)
    matches = [row for row in report.get("prepared", []) if row.get("task") == task]
    if len(matches) != 1 or not isinstance(matches[0].get("output_sha256"), dict):
        raise ValueError(f"Local task has no unique preparation receipt: {task}")
    expected = matches[0]["output_sha256"]
    actual = {}
    for modality in ("data-ss", "data-dom"):
        root = _task_path(data_root, modality, task)
        for path in root.rglob("*"):
            if path.is_file():
                if not path.resolve(strict=True).is_relative_to(root):
                    raise ValueError(f"Local evidence escapes its task folder: {path}")
                actual[path.relative_to(data_root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not actual or actual != expected:
        raise ValueError(f"Local verifier inputs differ from the preparation receipt: {task}")


def _preparation_report(data_root: Path) -> dict:
    report = load_json(data_root / "preparation_report.json")
    if not isinstance(report, dict) or report.get("schema_version") != "1.0":
        raise ValueError("Invalid preparation report schema")
    for name in ("prepared", "excluded"):
        rows = report.get(name)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"Preparation report {name} must be a list of objects")
    if (report.get("prepared_count") != len(report["prepared"])
        or report.get("excluded_count") != len(report["excluded"])
        or report.get("selected_recordings") != len(report["prepared"]) + len(report["excluded"])):
        raise ValueError("Preparation report counts disagree")
    return report


def _input_source(args: argparse.Namespace, data_root: Path) -> dict:
    receipt = {"data_source": args.data_source, "data_root": os.path.relpath(data_root, REPOSITORY_ROOT)}
    if args.data_source == "huggingface":
        receipt.update(hf_repo=args.hf_repo, hf_revision=args.hf_revision)
    else:
        report = data_root / "preparation_report.json"
        if report.is_file():
            receipt["preparation_report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
            prepared = _preparation_report(data_root)
            receipt.update(selected_recordings=prepared["selected_recordings"],
                           prepared_count=prepared["prepared_count"], excluded_count=prepared["excluded_count"])
    return receipt


def _run_all(args: argparse.Namespace, data_root: Path) -> int:
    tasks = _paired_tasks(data_root)
    # Validate every selected input before any task can initialize paid clients.
    for task in tasks:
        if args.data_source == "local":
            _verify_local_preparation(data_root, task)
        _validate_task(data_root, task)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_root = ensure_under(Path(args.results_root), REPOSITORY_ROOT, label="results root")
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "preflight_ready",
                    "paid_calls_authorized": False,
                    "selected_tasks": len(tasks),
                    "tasks": tasks,
                    "input_source": _input_source(args, data_root),
                    "audit_model": args.audit_model,
                    "run_id": run_id,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    audits: list[dict] = []
    failures: list[dict[str, str]] = []
    batch_root = results_root / "batches" / run_id
    if batch_root.exists():
        raise ValueError(f"Batch output already exists: {batch_root}")
    for ordinal, task in enumerate(tasks, start=1):
        print(f"[{ordinal}/{len(tasks)}] {task}", flush=True)
        child_args = argparse.Namespace(**vars(args))
        child_args.task, child_args.all, child_args.run_id = task, False, run_id
        try:
            rc = _run_task(child_args, data_root)
            if rc:
                raise RuntimeError(f"comparison exited with status {rc}")
            task_root = results_root / task / run_id
            audit_path = task_root / "evidence_audit.json"
            if not audit_path.is_file():
                error_path = task_root / "evidence_audit_error.json"
                if error_path.is_file():
                    receipt = load_json(error_path)
                    raise RuntimeError(
                        "audit_failed: " + str(receipt.get("message", "unknown audit error"))
                    )
                raise RuntimeError("comparison completed without an evidence-audit artifact")
            audits.append(load_json(audit_path))
        except Exception as exc:  # Batch runs must report rather than silently drop failures.
            failures.append({"task": task, "error": f"{type(exc).__name__}: {exc}"})
            print(f"{task}: FAILED: {exc}", file=sys.stderr, flush=True)

    if not audits:
        raise RuntimeError("All selected task comparisons failed; no aggregate was written")
    summary = aggregate_audits(audits, failures)
    summary.update({"run_id": run_id, "selected_tasks": len(tasks),
                    "input_source": _input_source(args, data_root)})
    batch_root.mkdir(parents=True)
    write_json(batch_root / "evidence_loss_summary.json", summary)
    (batch_root / "evidence_loss_summary.md").write_text(
        render_aggregate_markdown(summary), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.data_source == "huggingface":
        if (DEFAULT_DATASET_ROOT / "preparation_report.json").exists():
            raise ValueError("The download folder contains locally prepared inputs; use local mode or a separate download folder")
        fetched = fetch_trajectories(
            data_root=DEFAULT_DATASET_ROOT,
            task=None if args.all else args.task,
            repo_id=args.hf_repo,
            revision=args.hf_revision,
        )
        print(json.dumps({"dataset_fetch": fetched}, ensure_ascii=False, indent=2))
        data_root = DEFAULT_DATASET_ROOT.resolve(strict=True)
    else:
        # Local mode has no downloader call and no fallback to hosted inputs.
        data_root = (args.data_root or REPOSITORY_ROOT / "trajectories").resolve(strict=True)
    if args.all:
        return _run_all(args, data_root)
    return _run_task(args, data_root)


def _run_task(args: argparse.Namespace, data_root: Path) -> int:
    screenshot_source = _task_path(data_root, "data-ss", args.task)
    dom_source = _task_path(data_root, "data-dom", args.task)
    if args.data_source == "local":
        _verify_local_preparation(data_root, args.task)
    preflight = _validate_task(data_root, args.task)

    eval_config = Path(args.eval_config).resolve(strict=True)
    env_file = Path(args.env_file).resolve(strict=args.execute)
    results_root = ensure_under(
        Path(args.results_root), REPOSITORY_ROOT, label="results root"
    )
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "preflight_ready",
                    "paid_calls_authorized": False,
                    "task": args.task,
                    "screenshot_task": os.path.relpath(screenshot_source, REPOSITORY_ROOT),
                    "dom_task": os.path.relpath(dom_source, REPOSITORY_ROOT),
                    "input_source": _input_source(args, data_root),
                    "validation": preflight,
                    "eval_config": os.path.relpath(eval_config, REPOSITORY_ROOT),
                    "results_root": os.path.relpath(results_root, REPOSITORY_ROOT),
                    "run_id": run_id,
                    "audit_model": args.audit_model,
                    "workflow": [
                        "generate one fresh screenshot rubric",
                        "freeze the rubric on isolated task copies",
                        "score screenshot and DOM evidence with the same rubric",
                        "inventory and adjudicate evidence loss and verifier misses automatically",
                        "write the comparison",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    results_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{args.task}-phase-a-", dir=REPOSITORY_ROOT
    ) as staging_name:
        staging_root = Path(staging_name)
        screenshot_staged = staging_root / "data-ss" / args.task
        dom_staged = staging_root / "data-dom" / args.task
        shutil.copytree(screenshot_source, screenshot_staged)
        shutil.copytree(dom_source, dom_staged)
        rubric_file = staging_root / "frozen_rubric.json"
        metrics_file = staging_root / "rubric_generation_metrics.json"

        phase_a_args = [
            "--screenshot-task", str(screenshot_staged),
            "--dom-task", str(dom_staged),
            "--staged-root", str(staging_root),
            "--rubric-file", str(rubric_file),
            "--metrics-file", str(metrics_file),
            "--eval-config", str(eval_config),
            "--env-file", str(env_file),
            "--overwrite",
            "--execute",
        ]
        if generate_rubric(phase_a_args) != 0:
            return 1

        phase_b_args = [
            "--task", args.task,
            "--screenshot-task", str(screenshot_staged),
            "--dom-task", str(dom_staged),
            "--staged-root", str(staging_root),
            "--rubric-file", str(rubric_file),
            "--generation-metrics", str(metrics_file),
            "--eval-config", str(eval_config),
            "--env-file", str(env_file),
            "--results-root", str(results_root),
            "--run-id", run_id,
            "--audit-model", args.audit_model,
            "--execute",
        ]
        result = run_comparison(phase_b_args)
        run_root = results_root / args.task / run_id
        if run_root.is_dir():
            write_json(run_root / "input_source.json", _input_source(args, data_root))
        return result


if __name__ == "__main__":
    raise SystemExit(main())
