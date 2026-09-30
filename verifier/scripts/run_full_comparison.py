#!/usr/bin/env python3
"""Generate one frozen rubric, then score screenshot and DOM evidence with it."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
for package_src in (
    ROOT / "microsoft_verifier" / "src",
    ROOT / "dom_diff" / "src",
):
    source = str(package_src)
    if source not in sys.path:
        sys.path.insert(0, source)

from .common import ensure_under
from .common import load_json, write_json
from .dataset_sync import (
    DEFAULT_CACHE_ROOT,
    DEFAULT_REPO_ID,
    DEFAULT_REVISION,
    fetch_trajectories,
)
from .evidence_audit import DEFAULT_AUDIT_MODEL, aggregate_audits, render_aggregate_markdown
from .generate_frozen_rubric import main as generate_rubric
from .run_comparison import main as run_comparison


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--task", help="Task folder alias, e.g. task_01")
    selection.add_argument("--all", action="store_true", help="Run every paired task")
    parser.add_argument("--eval-config", default=str(ROOT / "config"))
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--results-root", default=str(REPOSITORY_ROOT / "evaluation"))
    parser.add_argument("--run-id")
    parser.add_argument("--audit-model", default=DEFAULT_AUDIT_MODEL)
    parser.add_argument("--hf-repo", default=DEFAULT_REPO_ID)
    parser.add_argument("--hf-revision", default=DEFAULT_REVISION)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


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
        raise ValueError("Hugging Face cache lacks paired data-ss and data-dom directories")
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


def _run_all(args: argparse.Namespace) -> int:
    data_root = DEFAULT_CACHE_ROOT.resolve(strict=True)
    tasks = _paired_tasks(data_root)
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
        child_args = [
            "--task", task,
            "--eval-config", args.eval_config,
            "--env-file", args.env_file,
            "--results-root", str(results_root),
            "--run-id", run_id,
            "--audit-model", args.audit_model,
            "--hf-repo", args.hf_repo,
            "--hf-revision", args.hf_revision,
            "--execute",
        ]
        try:
            rc = main(child_args)
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
    summary.update({"run_id": run_id, "selected_tasks": len(tasks)})
    batch_root.mkdir(parents=True)
    write_json(batch_root / "evidence_loss_summary.json", summary)
    (batch_root / "evidence_loss_summary.md").write_text(
        render_aggregate_markdown(summary), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    fetched = fetch_trajectories(
        data_root=DEFAULT_CACHE_ROOT,
        task=None if args.all else args.task,
        repo_id=args.hf_repo,
        revision=args.hf_revision,
    )
    print(json.dumps({"dataset_fetch": fetched}, ensure_ascii=False, indent=2))
    if args.all:
        return _run_all(args)
    data_root = DEFAULT_CACHE_ROOT.resolve(strict=True)
    screenshot_source = _task_path(data_root, "data-ss", args.task)
    dom_source = _task_path(data_root, "data-dom", args.task)

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
                    "screenshot_task": str(screenshot_source),
                    "dom_task": str(dom_source),
                    "eval_config": str(eval_config),
                    "results_root": str(results_root),
                    "run_id": run_id,
                    "audit_model": args.audit_model,
                    "workflow": [
                        "generate one fresh Microsoft rubric",
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
        prefix=f".{args.task}-phase-a-", dir=ROOT
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
        return run_comparison(phase_b_args)


if __name__ == "__main__":
    raise SystemExit(main())
