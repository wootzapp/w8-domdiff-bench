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
from .generate_frozen_rubric import main as generate_rubric
from .run_comparison import main as run_comparison


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, help="Task folder alias, e.g. task_01")
    parser.add_argument("--screenshot-task")
    parser.add_argument("--dom-task")
    parser.add_argument("--data-root", default=str(REPOSITORY_ROOT / "data"))
    parser.add_argument("--eval-config", default=str(ROOT / "config"))
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--results-root", default=str(REPOSITORY_ROOT / "evaluation"))
    parser.add_argument("--run-id")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def _task_path(explicit: str | None, data_root: Path, folder: str, task: str) -> Path:
    return ensure_under(
        Path(explicit or data_root / folder / task).resolve(strict=True),
        data_root,
        label=f"{folder} task",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_root = Path(args.data_root).resolve(strict=True)
    screenshot_source = _task_path(args.screenshot_task, data_root, "data-ss", args.task)
    dom_source = _task_path(args.dom_task, data_root, "data-dom", args.task)
    if screenshot_source.name != dom_source.name:
        raise ValueError("Screenshot and DOM task folder aliases must match")

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
                    "workflow": [
                        "generate one fresh Microsoft rubric",
                        "freeze the rubric on isolated task copies",
                        "score screenshot and DOM evidence with the same rubric",
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
            "--execute",
        ]
        return run_comparison(phase_b_args)


if __name__ == "__main__":
    raise SystemExit(main())
