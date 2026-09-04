#!/usr/bin/env python3
"""Phase B preflight or paid Microsoft-screenshot versus DOM-model comparison.

Without ``--execute`` all validation runs offline, no clients are constructed,
no subprocesses run, and no files are written.
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
    ensure_under,
    load_env_file,
    load_json,
    require_openai_key,
    write_json,
)
from .compare_results import compare
from .normalize_results import normalize_dom_model, normalize_screenshot
from .package_manifests import require_local_packages
from .validate_inputs import ordered_screenshots, validate_pair


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/endpoints/openai/canonical"


def _arg_value(command: list[str], flag: str, *, default: str | None = None) -> str:
    if flag not in command:
        if default is None:
            raise ValueError(f"Missing controlled command argument: {flag}")
        return default
    index = command.index(flag)
    if index + 1 >= len(command):
        raise ValueError(f"Controlled command argument has no value: {flag}")
    return command[index + 1]


def validate_command_parity(run_commands: dict[str, list[str]]) -> dict[str, Any]:
    """Fail before paid calls if verifier behavior differs beyond evidence I/O."""

    screenshot = run_commands["microsoft_verifier"]
    dom_model = run_commands["dom_model"]
    controls = {
        "judge_model": (
            _arg_value(screenshot, "--judge-model"),
            _arg_value(dom_model, "--judge-model"),
        ),
        "action_judge_model": (
            _arg_value(screenshot, "--o4mini-model"),
            _arg_value(dom_model, "--o4mini-model"),
        ),
        "rubric_threshold": (
            _arg_value(screenshot, "--rubric-threshold"),
            _arg_value(dom_model, "--rubric-threshold"),
        ),
        "max_evidence_items_per_criterion": (
            _arg_value(screenshot, "--max-images-per-criterion"),
            _arg_value(dom_model, "--max-evidence-per-criterion"),
        ),
        # Microsoft exposes no CLI flag for this copied-agent setting; its
        # effective value is zero. DOM must explicitly match it.
        "min_relevance_threshold": (
            str(CANONICAL_SETTINGS["min_relevance_threshold"]),
            _arg_value(dom_model, "--min-relevance-threshold"),
        ),
        "majority_vote_instances": (
            _arg_value(screenshot, "--majority-vote-instances"),
            _arg_value(dom_model, "--majority-vote-instances"),
        ),
        "success_criterion": (
            _arg_value(screenshot, "--success"),
            _arg_value(dom_model, "--success"),
        ),
    }
    mismatches = {
        name: {"microsoft_verifier": left, "dom_model": right}
        for name, (left, right) in controls.items()
        if left != right
    }
    redo = {
        "microsoft_verifier": "--redo-eval" in screenshot,
        "dom_model": "--redo-eval" in dom_model,
    }
    if len(set(redo.values())) != 1 or not all(redo.values()):
        mismatches["redo_eval"] = redo
    if mismatches:
        raise ValueError(
            "Verifier command parity failed; only evidence loading may differ: "
            + json.dumps(mismatches, sort_keys=True)
        )
    return {
        name: left for name, (left, _) in controls.items()
    } | {"redo_eval": True}


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in ("openai", "tiktoken", "httpx", "Pillow", "pydantic", "azure-identity"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "missing"
    versions["python"] = ".".join(map(str, sys.version_info[:3]))
    return versions


def _subprocess_env(package_src: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(package_src.resolve(strict=True))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run_logged(command: list[str], log_path: Path, *, package_src: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=_subprocess_env(package_src),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"Verifier failed with exit code {completed.returncode}; see {log_path}")


def prepare_isolated_inputs(
    *, screenshot_task: Path, dom_task: Path, rubric_file: Path,
    generation_metrics: Path, run_root: Path, action_count: int,
) -> tuple[Path, Path, Path, Path]:
    input_root = run_root / "_inputs"
    if input_root.exists():
        raise ValueError(f"Isolated input directory already exists: {input_root}")
    input_root.mkdir(parents=True)
    screenshot_copy = input_root / "screenshot"
    dom_copy = input_root / "dom_model"
    shutil.copytree(screenshot_task, screenshot_copy)
    shutil.copytree(dom_task, dom_copy)

    # Keep every browser state available to the evidence selector. The real
    # action history remains N actions; this staged answer only controls which
    # screenshot files the verifier may inspect as evidence.
    screenshot_states = ordered_screenshots(screenshot_copy)
    if len(screenshot_states) != action_count + 1:
        raise ValueError(
            "Isolated screenshot task must contain exactly N+1 browser states"
        )
    answer_files = list(screenshot_copy.glob("*_answer.json"))
    if len(answer_files) != 1:
        raise ValueError(
            f"Expected exactly one isolated *_answer.json, found {len(answer_files)}"
        )
    answer = load_json(answer_files[0])
    answer["screenshots"] = [path.name for path in screenshot_states]
    write_json(answer_files[0], answer)

    rubric_copy = input_root / "frozen_rubric.json"
    metrics_copy = input_root / "rubric_generation_metrics.json"
    shutil.copy2(rubric_file, rubric_copy)
    shutil.copy2(generation_metrics, metrics_copy)
    return screenshot_copy, dom_copy, rubric_copy, metrics_copy


def commands(
    *, screenshot_task: Path, dom_task: Path, rubric_file: Path,
    generation_metrics: Path, eval_config: Path, run_root: Path,
) -> dict[str, list[str]]:
    microsoft_output = run_root / "microsoft_verifier"
    dom_output = run_root / "dom_model"
    return {
        "microsoft_verifier": [
            sys.executable, "-m", "microsoft_verifier.runner",
            "--input", str(screenshot_task),
            "--rubric-file", str(rubric_file),
            "--eval-config", str(eval_config),
            "--output", str(microsoft_output),
            "--judge-model", CANONICAL_JUDGE_MODEL,
            "--o4mini-model", CANONICAL_ACTION_MODEL,
            "--rubric-threshold", str(CANONICAL_SETTINGS["rubric_threshold"]),
            "--max-images-per-criterion", str(CANONICAL_SETTINGS["max_evidence_items_per_criterion"]),
            "--majority-vote-instances", str(CANONICAL_SETTINGS["majority_vote_instances"]),
            "--success", str(CANONICAL_SETTINGS["success_criterion"]),
            "--redo-eval",
        ],
        "dom_model": [
            sys.executable, "-m", "dom_model.runner",
            "--input", str(dom_task),
            "--rubric-file", str(rubric_file),
            "--generation-metrics", str(generation_metrics),
            "--eval-config", str(eval_config),
            "--output", str(dom_output),
            "--judge-model", CANONICAL_JUDGE_MODEL,
            "--o4mini-model", CANONICAL_ACTION_MODEL,
            "--rubric-threshold", str(CANONICAL_SETTINGS["rubric_threshold"]),
            "--max-evidence-per-criterion", str(CANONICAL_SETTINGS["max_evidence_items_per_criterion"]),
            "--min-relevance-threshold", str(CANONICAL_SETTINGS["min_relevance_threshold"]),
            "--dom-model-state-char-budget", "350000",
            "--majority-vote-instances", str(CANONICAL_SETTINGS["majority_vote_instances"]),
            "--success", str(CANONICAL_SETTINGS["success_criterion"]),
            "--redo-eval",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, help="Task folder alias, e.g. task13")
    parser.add_argument("--screenshot-task")
    parser.add_argument("--dom-task")
    parser.add_argument("--rubric-file")
    parser.add_argument("--generation-metrics")
    parser.add_argument("--staged-root", default=str(ROOT / "data"))
    parser.add_argument("--eval-config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--results-root", default=str(ROOT / "results"))
    parser.add_argument("--run-id")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    staged_root = Path(args.staged_root).resolve(strict=True)
    screenshot_source = ensure_under(
        Path(args.screenshot_task or staged_root / "data-new-screenshot" / args.task).resolve(strict=True),
        staged_root,
        label="screenshot task",
    )
    dom_source = ensure_under(
        Path(args.dom_task or staged_root / "data-new-dom-model" / args.task).resolve(strict=True),
        staged_root,
        label="DOM-model task",
    )
    rubric_source = ensure_under(
        Path(args.rubric_file or ROOT / "rubrics" / f"{args.task}.json").resolve(strict=True),
        ROOT,
        label="rubric file",
    )
    generation_source = ensure_under(
        Path(args.generation_metrics or ROOT / "rubrics" / f"{args.task}_generation_metrics.json").resolve(strict=True),
        ROOT,
        label="generation metrics",
    )
    eval_config = Path(args.eval_config).resolve(strict=True)
    preflight = validate_pair(
        screenshot_source,
        dom_source,
        rubric_file=rubric_source,
        generation_metrics=generation_source,
        eval_config=eval_config,
        require_sidecars=True,
    )
    packages = require_local_packages()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_root = ensure_under(Path(args.results_root), ROOT, label="results root")
    run_root = results_root / args.task / run_id
    if run_root.exists():
        raise ValueError(f"Run output already exists; choose a new --run-id: {run_root}")
    isolated = run_root / "_inputs"
    isolated_screenshot = isolated / "screenshot"
    isolated_dom = isolated / "dom_model"
    isolated_rubric = isolated / "frozen_rubric.json"
    isolated_generation = isolated / "rubric_generation_metrics.json"
    run_commands = commands(
        screenshot_task=isolated_screenshot,
        dom_task=isolated_dom,
        rubric_file=isolated_rubric,
        generation_metrics=isolated_generation,
        eval_config=eval_config,
        run_root=run_root,
    )
    parity_controls = validate_command_parity(run_commands)
    microsoft_rubric_arg = run_commands["microsoft_verifier"][run_commands["microsoft_verifier"].index("--rubric-file") + 1]
    dom_rubric_arg = run_commands["dom_model"][run_commands["dom_model"].index("--rubric-file") + 1]
    if microsoft_rubric_arg != dom_rubric_arg:
        raise RuntimeError("Phase B command construction produced different rubric paths")
    if "--redo-eval" not in run_commands["microsoft_verifier"] or "--redo-eval" not in run_commands["dom_model"]:
        raise RuntimeError("Both Phase B commands must include --redo-eval")
    phase_a = load_json(generation_source)
    manifest: dict[str, Any] = {
        "status": "preflight_passed",
        "phase": "B",
        "paid_calls_authorized": bool(args.execute),
        "writes_performed": False,
        "preflight": preflight,
        "verifier_packages": packages,
        "runtime": _package_versions(),
        "commands": run_commands,
        "verifier_parity": {
            "status": "passed",
            "only_intentional_difference": "evidence_loader_and_representation",
            "controls": parity_controls,
        },
        "source_inputs": {
            "screenshot": str(screenshot_source),
            "dom_model": str(dom_source),
            "frozen_rubric": str(rubric_source),
            "generation_metrics": str(generation_source),
        },
        "isolated_inputs": {
            "screenshot": str(isolated_screenshot),
            "dom_model": str(isolated_dom),
            "frozen_rubric": str(isolated_rubric),
            "generation_metrics": str(isolated_generation),
        },
        "phase_a_usage_separate_from_scoring": phase_a.get("token_usage", {}),
        "rubric_generation_calls_during_scoring": 0,
        "run_root": str(run_root),
    }
    if not args.execute:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    load_env_file(args.env_file)
    require_openai_key()
    run_root.mkdir(parents=True)
    copied = prepare_isolated_inputs(
        screenshot_task=screenshot_source,
        dom_task=dom_source,
        rubric_file=rubric_source,
        generation_metrics=generation_source,
        run_root=run_root,
        action_count=int(preflight["actions"]),
    )
    if copied != (isolated_screenshot, isolated_dom, isolated_rubric, isolated_generation):
        raise RuntimeError("Isolated input paths drifted from planned command paths")
    manifest["writes_performed"] = True
    write_json(run_root / "run_manifest.json", manifest)

    microsoft_root = run_root / "microsoft_verifier"
    _run_logged(
        run_commands["microsoft_verifier"],
        microsoft_root / "run.log",
        package_src=ROOT / "microsoft_verifier/src",
    )
    microsoft_metrics = normalize_screenshot(
        microsoft_root / "result.json",
        input_task=screenshot_source,
        rubric_file=isolated_rubric,
        generation_metrics=isolated_generation,
        run_log=microsoft_root / "run.log",
    )
    write_json(microsoft_root / "run_metrics.json", microsoft_metrics)

    dom_root = run_root / "dom_model"
    _run_logged(
        run_commands["dom_model"],
        dom_root / "run.log",
        package_src=ROOT / "dom_model/src",
    )
    dom_metrics = normalize_dom_model(
        dom_root / "result.json",
        input_task=dom_source,
        rubric_file=isolated_rubric,
        generation_metrics=isolated_generation,
        run_log=dom_root / "run.log",
    )
    write_json(dom_root / "run_metrics.json", dom_metrics)
    comparison_receipt, comparison_markdown = compare(microsoft_metrics, dom_metrics)
    (run_root / "comparison.md").write_text(comparison_markdown, encoding="utf-8")
    write_json(run_root / "comparison.json", comparison_receipt)
    manifest.update(
        {
            "status": "complete",
            "microsoft_metrics": str(microsoft_root / "run_metrics.json"),
            "dom_model_metrics": str(dom_root / "run_metrics.json"),
            "comparison_report": str(run_root / "comparison.md"),
        }
    )
    write_json(run_root / "run_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
