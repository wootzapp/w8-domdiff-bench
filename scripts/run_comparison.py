#!/usr/bin/env python3
"""Preflight or execute one controlled screenshot-vs-DOM-text comparison.

Without ``--execute`` this command performs every offline check and makes zero
judge calls. ``--execute`` is the explicit paid-evaluation authorization.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import (
    CANONICAL_ACTION_MODEL,
    CANONICAL_JUDGE_MODEL,
    CANONICAL_SETTINGS,
    load_env_file,
    require_openai_key,
    write_json,
)
from .compare_results import compare
from .results import normalize_dom_text, normalize_screenshot
from .validate_inputs import validate_pair


ROOT = Path(__file__).resolve().parents[1]


def _package_versions() -> dict[str, str]:
    names = ("openai", "tiktoken", "httpx", "Pillow", "pydantic", "azure-identity")
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "missing"
    versions["python"] = ".".join(map(str, sys.version_info[:3]))
    return versions


def _run_logged(command: list[str], log_path: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=ROOT.parent,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Verifier command failed with exit code {completed.returncode}; see {log_path}"
        )


def _prepare_isolated_inputs(
    *, screenshot_task: Path, dom_task: Path, run_root: Path
) -> tuple[Path, Path]:
    """Copy validated source tasks into a run-local, disposable input bundle.

    The unchanged Microsoft adapter creates canonical screenshot-name symlinks.
    Running it against this copy prevents those compatibility files from
    mutating the immutable source dataset or breaking a later preflight.
    """
    input_root = run_root / "_inputs"
    screenshot_copy = input_root / "screenshot"
    dom_copy = input_root / "dom"
    if input_root.exists():
        raise ValueError(f"Isolated input directory already exists: {input_root}")
    input_root.mkdir(parents=True)
    shutil.copytree(screenshot_task, screenshot_copy)
    shutil.copytree(dom_task, dom_copy)
    return screenshot_copy, dom_copy


def _commands(
    *,
    screenshot_task: Path,
    dom_task: Path,
    rubric_file: Path,
    eval_config: Path,
    run_root: Path,
) -> dict[str, list[str]]:
    screenshot_output = run_root / "microsoft_verifier"
    dom_output = run_root / "dom_diff_text"
    return {
        "microsoft_verifier": [
            sys.executable,
            "-m",
            "microsoft_verifier.runner",
            "--input",
            str(screenshot_task),
            "--rubric-file",
            str(rubric_file),
            "--eval-config",
            str(eval_config),
            "--output",
            str(screenshot_output),
            "--judge-model",
            CANONICAL_JUDGE_MODEL,
            "--o4mini-model",
            CANONICAL_ACTION_MODEL,
            "--rubric-threshold",
            str(CANONICAL_SETTINGS["rubric_threshold"]),
            "--max-images-per-criterion",
            str(CANONICAL_SETTINGS["max_evidence_items_per_criterion"]),
            "--majority-vote-instances",
            str(CANONICAL_SETTINGS["majority_vote_instances"]),
            "--success",
            str(CANONICAL_SETTINGS["success_criterion"]),
            "--redo-eval",
        ],
        "dom_diff_text": [
            sys.executable,
            "-m",
            "dom_diff_text.runner",
            "--input",
            str(dom_task),
            "--rubric-file",
            str(rubric_file),
            "--eval-config",
            str(eval_config),
            "--output",
            str(dom_output),
            "--report",
            str(dom_output / "verify_report_dom_diff_text.jsonl"),
            "--judge-model",
            CANONICAL_JUDGE_MODEL,
            "--o4mini-model",
            CANONICAL_ACTION_MODEL,
            "--processes",
            "1",
            "--rubric-threshold",
            str(CANONICAL_SETTINGS["rubric_threshold"]),
            "--max-evidence-per-criterion",
            str(CANONICAL_SETTINGS["max_evidence_items_per_criterion"]),
            "--mm-keypoint-score-threshold",
            str(CANONICAL_SETTINGS["mm_keypoint_score_threshold"]),
            "--majority-vote-instances",
            str(CANONICAL_SETTINGS["majority_vote_instances"]),
            "--success",
            str(CANONICAL_SETTINGS["success_criterion"]),
            "--dom-frame-char-budget",
            "16000",
            "--dom-context-char-budget",
            "48000",
            "--text-frame-starting-tokens",
            "1500",
            "--text-trajectory-starting-tokens",
            "16000",
            "--text-analysis-starting-tokens",
            "24000",
            "--text-max-chunk-tokens",
            "256",
            "--text-model-context-window-tokens",
            "128000",
            "--text-relevance-completion-reserve-tokens",
            "4096",
            "--text-analysis-completion-reserve-tokens",
            "8192",
            "--text-prompt-headroom-tokens",
            "1024",
            "--request-timeout-seconds",
            "180",
            "--max-api-retries",
            "2",
            "--redo-eval",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, help="Task folder alias, e.g. task4")
    parser.add_argument("--screenshot-task")
    parser.add_argument("--dom-task")
    parser.add_argument("--rubric-file")
    parser.add_argument(
        "--eval-config",
        default=str(ROOT / "config/endpoints/openai/canonical"),
    )
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--results-root", default=str(ROOT / "results"))
    parser.add_argument("--run-id")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    screenshot_task = Path(
        args.screenshot_task or ROOT / "data/data-new-screenshot" / args.task
    ).resolve(strict=True)
    dom_task = Path(args.dom_task or ROOT / "data/data-new-short-dom" / args.task).resolve(
        strict=True
    )
    rubric_file = Path(args.rubric_file or ROOT / "rubrics" / f"{args.task}.json").resolve(
        strict=True
    )
    eval_config = Path(args.eval_config).resolve(strict=True)
    preflight = validate_pair(
        screenshot_task,
        dom_task,
        rubric_file=rubric_file,
        eval_config=eval_config,
    )
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = Path(args.results_root).resolve() / args.task / run_id
    if run_root.exists():
        raise ValueError(f"Run output already exists; choose a new --run-id: {run_root}")
    isolated_screenshot = run_root / "_inputs" / "screenshot"
    isolated_dom = run_root / "_inputs" / "dom"
    commands = _commands(
        screenshot_task=isolated_screenshot,
        dom_task=isolated_dom,
        rubric_file=rubric_file,
        eval_config=eval_config,
        run_root=run_root,
    )
    manifest: dict[str, Any] = {
        "status": "preflight_passed",
        "paid_calls_authorized": bool(args.execute),
        "preflight": preflight,
        "runtime": _package_versions(),
        "commands": commands,
        "source_inputs": {
            "screenshot": str(screenshot_task),
            "dom": str(dom_task),
        },
        "isolated_inputs": {
            "screenshot": str(isolated_screenshot),
            "dom": str(isolated_dom),
        },
        "run_root": str(run_root),
    }
    if not args.execute:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    load_env_file(args.env_file)
    require_openai_key()
    run_root.mkdir(parents=True)
    copied_screenshot, copied_dom = _prepare_isolated_inputs(
        screenshot_task=screenshot_task,
        dom_task=dom_task,
        run_root=run_root,
    )
    if copied_screenshot != isolated_screenshot or copied_dom != isolated_dom:
        raise RuntimeError("Isolated input paths drifted from the planned commands")
    write_json(run_root / "run_manifest.json", manifest)

    screenshot_root = run_root / "microsoft_verifier"
    _run_logged(commands["microsoft_verifier"], screenshot_root / "run.log")
    screenshot_metrics = normalize_screenshot(
        screenshot_root / "result.json",
        input_task=screenshot_task,
        rubric_file=rubric_file,
        run_log=screenshot_root / "run.log",
    )
    write_json(screenshot_root / "run_metrics.json", screenshot_metrics)

    dom_root = run_root / "dom_diff_text"
    _run_logged(commands["dom_diff_text"], dom_root / "run.log")
    dom_metrics = normalize_dom_text(
        dom_root / "verify_report_dom_diff_text.jsonl",
        input_task=dom_task,
        rubric_file=rubric_file,
        run_log=dom_root / "run.log",
    )
    write_json(dom_root / "run_metrics.json", dom_metrics)

    comparison_receipt, comparison_markdown = compare(screenshot_metrics, dom_metrics)
    comparison_path = run_root / "comparison.md"
    comparison_path.write_text(comparison_markdown, encoding="utf-8")
    write_json(run_root / "comparison.json", comparison_receipt)
    manifest.update(
        {
            "status": "complete",
            "screenshot_metrics": str(screenshot_root / "run_metrics.json"),
            "dom_diff_text_metrics": str(dom_root / "run_metrics.json"),
            "comparison_report": str(comparison_path),
        }
    )
    write_json(run_root / "run_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
