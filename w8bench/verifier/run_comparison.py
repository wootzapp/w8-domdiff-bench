"""Grade and evaluate each actor run using its own paired browser evidence."""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from w8bench.task_recorder.prepare_verifier_data import inspect_recording, read_object, prepare_recording
from .common import write_json
from w8bench.task_recorder.runner import load_env

from .common import native_judge_model, NATIVE_JUDGE_PROFILES, CANONICAL_SETTINGS, load_json, canonical_sha256

from .completion import grade_run
from w8bench.settings import evaluation_settings, stage_settings, require_same_settings, completion_settings
from w8bench.model_identity import ModelResponseRefusal
from w8bench.usage import valid_token_component

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPOSITORY_ROOT / "config"


def _arg_value(command: list[str], flag: str) -> str:
    if flag not in command:
        raise ValueError(f"Missing controlled command argument: {flag}")
    index = command.index(flag)
    if index + 1 >= len(command):
        raise ValueError(f"Controlled command argument has no value: {flag}")
    return command[index + 1]


def validate_command_parity(run_commands: dict[str, list[str]]) -> dict[str, Any]:
    """Validate shared numerical scoring controls before paid calls."""

    screenshot = run_commands["screenshot_verifier"]
    dom_model = run_commands["dom_model"]
    controls = {
        "judge_model": (
            _arg_value(screenshot, "--judge-model"),
            _arg_value(dom_model, "--judge-model"),
        ),
        "action_judge_model": (
            _arg_value(screenshot, "--action-model"),
            _arg_value(dom_model, "--action-model"),
        ),
        "rubric_threshold": (
            _arg_value(screenshot, "--rubric-threshold"),
            _arg_value(dom_model, "--rubric-threshold"),
        ),
        "max_evidence_items_per_criterion": (
            _arg_value(screenshot, "--max-images-per-criterion"),
            _arg_value(dom_model, "--max-evidence-per-criterion"),
        ),
        # screenshot exposes no CLI flag for this copied-agent setting; its
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
        name: {"screenshot_verifier": left, "dom_model": right}
        for name, (left, right) in controls.items()
        if left != right
    }
    redo = {
        "screenshot_verifier": "--redo-eval" in screenshot,
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
    for name in ("google-genai", "tiktoken", "httpx", "Pillow", "pydantic"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "missing"
    versions["python"] = ".".join(map(str, sys.version_info[:3]))
    return versions


def _run_logged(command: list[str], log_path: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    output = completed.stdout
    # Only traceback file references are reformatted here. Do not rewrite
    # page evidence, model answers, URLs, or arbitrary quoted strings.
    for filename in re.findall(r'^\s+File "(/[^"\n]+)", line \d+, in ', output, re.MULTILINE):
        output = output.replace(f'File "{filename}", line ',
                                f'File "{os.path.relpath(filename, REPOSITORY_ROOT)}", line ')
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(f"\nEvaluation attempt: {datetime.now(timezone.utc).isoformat()}\n")
        stream.write(output)
    if completed.returncode == 130:
        raise KeyboardInterrupt()
    if completed.returncode:
        raise RuntimeError(
            f"Verifier failed with exit code {completed.returncode}; "
            f"see {os.path.relpath(log_path, REPOSITORY_ROOT)}"
        )


def commands(
    *, screenshot_task: Path, dom_task: Path, rubric_file: Path,
    generation_metrics: Path, eval_config: Path, run_root: Path,
) -> dict[str, list[str]]:
    screenshot_output = run_root / "screenshot_verifier"
    dom_output = run_root / "dom_model"
    return {
        "screenshot_verifier": [
            sys.executable, "-m", "w8bench.verifier.screenshot_verifier.runner",
            "--input", str(screenshot_task),
            "--rubric-file", str(rubric_file),
            "--eval-config", str(eval_config),
            "--output", str(screenshot_output),
            "--judge-model", native_judge_model(),
            "--action-model", native_judge_model(),
            "--rubric-threshold", str(CANONICAL_SETTINGS["rubric_threshold"]),
            "--max-images-per-criterion", str(CANONICAL_SETTINGS["max_evidence_items_per_criterion"]),
            "--majority-vote-instances", str(CANONICAL_SETTINGS["majority_vote_instances"]),
            "--success", str(CANONICAL_SETTINGS["success_criterion"]),
            "--redo-eval",
        ],
        "dom_model": [
            sys.executable, "-m", "w8bench.verifier.dom_model.runner",
            "--input", str(dom_task),
            "--rubric-file", str(rubric_file),
            "--generation-metrics", str(generation_metrics),
            "--eval-config", str(eval_config),
            "--output", str(dom_output),
            "--judge-model", native_judge_model(),
            "--action-model", native_judge_model(),
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
    parser.add_argument("--run", type=Path, nargs="+", required=True, help="one or more recordings to evaluate")
    parser.add_argument("--rubric", type=Path, required=True)
    parser.add_argument("--judge-model", required=True,
        help="gemini-3.6-flash completion judge; responses require its exact ID or a numeric/date/version suffix")
    parser.add_argument("--judge-evidence-policy", choices=["paired", "actor_native"], default="paired")
    parser.add_argument("--eval-config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env")
    parser.add_argument("--judge-profile", choices=tuple(NATIVE_JUDGE_PROFILES), default=None)
    parser.add_argument("--compare-profiles", action="store_true", help="evaluate primary and pro native profiles separately on the same recordings")
    parser.add_argument("--stage", choices=("evaluate", "adjudicate"), default="evaluate",
        help="evaluate completion, native evidence and inventory; adjudicate saved inventories")
    parser.add_argument("--execute", action="store_true",
        help="evaluate the run; saved effective settings must match before any stage resumes")
    args = parser.parse_args(argv)
    if args.judge_model != "gemini-3.6-flash":
        parser.error("completion judge must be explicitly set to gemini-3.6-flash")
    if args.stage == "adjudicate" and args.judge_evidence_policy != "paired":
        parser.error("adjudication requires the paired evidence policy")
    return args


def _attempt_history(stage):
    history = list(stage.get("attempt_history", []))
    if stage:
        prior = {key: value for key, value in stage.items() if key not in {"attempt_history", "result_sha256"}}
        if prior.get("status") == "running":
            prior.update(status="interrupted", usage_coverage="unknown")
        history.append(prior)
    return history


def _prepare_inputs(run, recording):
    task = recording["task"]
    output = run.parent.parent / "evaluations" / "profiles" / os.environ.get("NATIVE_JUDGE_PROFILE", "primary")
    root = output / str(task.get("run_name") or recording["manifest"]["run_name"]) / task["observation_mode"] / task["source_task_id"] / recording["recording_sha256"]
    if root.exists():
        receipt = read_object(root / "input_receipt.json")
        if receipt["recording_sha256"] != recording["recording_sha256"] or receipt["source_files_sha256"] != recording["files"]:
            raise ValueError("evaluation staging belongs to another recording")
        for folder, hashes in receipt["projected_files_sha256"].items():
            for name, digest in hashes.items():
                path = root / folder / task["source_task_id"] / name
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError("staged evaluation input changed")
    else:
        if os.environ.get("NATIVE_JUDGE_PROFILE", "primary") == "pro":
            original = run.parent.parent / "evaluations" / "profiles" / "primary" / str(task.get("run_name") or recording["manifest"]["run_name"]) / task["observation_mode"] / task["source_task_id"] / recording["recording_sha256"]
            if original.exists():
                root.mkdir(parents=True)
                for name in ("data-ss", "data-dom"):
                    shutil.copytree(original / name, root / name)
                shutil.copy2(original / "input_receipt.json", root / "input_receipt.json")
            else:
                prepare_recording(recording, output)
        else:
            prepare_recording(recording, output)
    screenshot_task = root / "data-ss" / task["source_task_id"]
    dom_task = root / "data-dom" / task["source_task_id"]
    return root, screenshot_task, dom_task


def _prepare_rubric(args, root, task, load_canonical_rubric):
    provided = read_object(args.rubric)
    if provided.get("task_id") != task["source_task_id"]:
        raise ValueError("rubric belongs to another task")
    for field in ("instruction", "start_url"):
        if field in provided and provided[field] != task[field]:
            raise ValueError(f"rubric {field} differs from the task")
    if "precomputed_rubric" in provided:
        canonical = provided
        declaration = {"origin": "validated_import", "weights": "preserved"}
    else:
        criteria = provided.get("criteria")
        if not criteria:
            raise ValueError("full evaluation requires frozen task criteria")
        canonical = {"task_id": task["source_task_id"], "instruction": task["instruction"],
            "start_url": task["start_url"], "precomputed_rubric": {"items": [
                {"criterion": item["id"], "description": item["description"], "max_points": 1,
                 "earned_points": None, "justification": None} for item in criteria]}}
        declaration = {"origin": "validated_import", "weights": "equal_positive_integer", "max_points": 1,
            "criterion_mapping": [{"source_id": item["id"], "criterion": item["id"]} for item in criteria]}
    rubric_hash = canonical_sha256(canonical["precomputed_rubric"])
    declaration.update(source=str(args.rubric.resolve()), model_calls=0)
    rubric, generation = root / "frozen_rubric.json", root / "rubric_generation_metrics.json"
    if rubric.exists() and read_object(rubric) != canonical:
        raise ValueError("evaluation frozen rubric changed")
    write_json(rubric, canonical)
    frozen = load_canonical_rubric(rubric, expected_task_id=task["source_task_id"])
    write_json(root / "rubric_import.json", declaration)
    return rubric, generation, frozen, rubric_hash


def _open_evaluation(root, recording, rubric_hash, effective_settings=None):
    task = recording["task"]
    evaluation_file = root / "evaluation.json"
    evaluation = read_object(evaluation_file) if evaluation_file.exists() else {
        "schema_version": "within-run-evaluation/v3", "recording_sha256": recording["recording_sha256"],
        "rubric_sha256": rubric_hash, "task_id": task["source_task_id"], "actor_arm": task["observation_mode"],
        "trial_id": str(task.get("run_name") or recording["manifest"]["run_name"]), "coverage": recording["coverage"],
        "validity_date": read_object(root / "input_receipt.json")["validity_date"],
        "verifier_packages": None, "runtime": _package_versions(), "stages": {}, "preflight": None}
    if evaluation["recording_sha256"] != recording["recording_sha256"] or evaluation["rubric_sha256"] != rubric_hash:
        raise ValueError("evaluation identity or frozen rubric changed")
    if effective_settings is not None:
        if evaluation_file.exists():
            require_same_settings(evaluation.get("effective_settings"), effective_settings, label="evaluation resume")
            for name, stage in evaluation["stages"].items():
                require_same_settings(stage.get("effective_settings"), stage_settings(effective_settings, name), label=f"{name} resume")
        evaluation["effective_settings"] = effective_settings
    evaluation.update(status="running", started_at=evaluation.get("started_at") or datetime.now(timezone.utc).isoformat())
    write_json(evaluation_file, evaluation)
    return evaluation_file, evaluation


def _primary_completion(args, run, root, recording, rubric, rubric_hash, evaluation, evaluation_file):
    primary = root / "paired_completion.json"
    previous = evaluation["stages"].get("paired_completion", {})
    common = Path(os.environ["W8_JUDGE_COMPLETION_TARGET"]) if os.environ.get("W8_JUDGE_COMPLETION_TARGET") else run / "completion.json"
    if common.exists() and read_object(common).get("method") != "ungraded" and (
            not primary.exists() or read_object(primary).get("method") == "ungraded"):
        write_json(primary, read_object(common))

    grade = None
    if primary.exists():
        if previous.get("result_sha256") and hashlib.sha256(primary.read_bytes()).hexdigest() != previous["result_sha256"]:
            raise ValueError("saved primary grade artifact changed")
        grade = read_object(primary)
        if grade["recording_sha256"] != recording["recording_sha256"] or grade["rubric_sha256"] != rubric_hash:
            raise ValueError("saved primary grade belongs to different inputs")
        current = completion_settings(recording, rubric_hash=rubric_hash, judge_model=args.judge_model,
            base_url=os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"), evidence_policy="paired")
        require_same_settings(grade.get("effective_settings"), current, label="saved completion")
    history = list(previous.get("attempt_history", []))
    if grade is None or grade["method"] == "ungraded":
        history = _attempt_history(previous)
        if len(history) > len(previous.get("attempt_history", [])) and primary.exists():
            archived = root / "_attempts" / f"paired_completion_{len(history):04d}.json"
            archived.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(primary, archived)
            history[-1].update(result=str(archived))
        evaluation["stages"]["paired_completion"] = {"status": "running", "usage_coverage": "unknown", "attempt_history": history,
            "effective_settings": stage_settings(evaluation.get("effective_settings"), "paired_completion")}
        write_json(evaluation_file, evaluation)
        try:
            grade = asyncio.run(grade_run(run, rubric, judge_model=args.judge_model,
                api_key=os.environ["GEMINI_API_KEY"], base_url=os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
                execute=True, evidence_policy="paired"))
        except BaseException as error:
            evaluation["stages"]["paired_completion"].update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                error=f"{type(error).__name__}: {error}")
            write_json(evaluation_file, evaluation)
            raise
        write_json(primary, grade)
    evaluation["stages"]["paired_completion"] = {"status": grade["method"], "verdict": grade["verdict"],
        "result": str(primary), "result_sha256": hashlib.sha256(primary.read_bytes()).hexdigest(),
        "usage": grade.get("usage"), "calls": grade.get("judge_calls", 0),
        "model_settings": grade.get("model_settings"), "transport": grade.get("transport", "normal"),
        "attempt_history": history,
        "effective_settings": stage_settings(evaluation.get("effective_settings"), "paired_completion"),
        "usage_coverage": "complete" if grade.get("judge_calls", 0) == 0 or all(
            valid_token_component((grade.get("usage") or {}).get(component))
            for component in ("input_tokens", "output_tokens")) else "unknown"}
    write_json(evaluation_file, evaluation)
    return grade


def _audit_configuration_error(resolve_audit_config):
    audit_configuration_error = None
    try:
        audit_config = resolve_audit_config()
        if (audit_config["inventory"]["model"] != "gemini-3.1-pro-preview" or
                audit_config["inventory"]["provider"] != "google" or
                audit_config["adjudication"]["model"] != "gemini-4-argon" or
                audit_config["adjudication"]["provider"] != "google"):
            raise ValueError("audit inventory must be gemini-3.1-pro-preview and adjudication must be gemini-4-argon through Google")
        if not os.environ.get("GEMINI_API_KEY"):
            raise ValueError("Google credentials are required for the evidence audit")
    except Exception as error:
        audit_configuration_error = f"{type(error).__name__}: {error}"
    return audit_configuration_error


def _prepare_generation(root, generation, frozen, screenshot_task, dom_task, validate_generation_metrics):
    if generation.exists():
        metrics = validate_generation_metrics(generation, frozen)
        if metrics.get("origin") != "validated_import" or metrics.get("rubric_generation_calls") != 0:
            raise ValueError("evaluation rubric must be a zero-call frozen import")
    else:
        zero_usage = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
        write_json(generation, {"phase": "A", "origin": "validated_import", "task_id": frozen.task_id,
            "frozen_rubric_sha256": frozen.sha256, "criterion_count": len(frozen.rubric["items"]),
            "criterion_denominator": frozen.denominator,
            "criteria": [item["criterion"] for item in frozen.rubric["items"]],
            "maximum_points": [float(item["max_points"]) for item in frozen.rubric["items"]],
            "rubric_generation_calls": 0, "api_attempts": 0, "retries": 0, "http_attempts_complete": True,
            "call_metrics": {model: {"logical_calls": 0, "api_attempts": 0, "retries": 0} for model in
                (native_judge_model(), native_judge_model())},
            "token_usage": {**{model: zero_usage for model in (native_judge_model(), native_judge_model())}, "combined": zero_usage}})
    for projection in (screenshot_task, dom_task):
        task_path = projection / "task_data.json"
        payload = load_json(task_path)
        sidecar = [{**payload[0], "precomputed_rubric": frozen.rubric}] if isinstance(payload, list) else {**payload, "precomputed_rubric": frozen.rubric}
        sidecar_path = projection / "task_data_with_canonical_rubric.json"
        if sidecar_path.exists() and load_json(sidecar_path) != sidecar:
            raise ValueError("evaluation frozen-rubric sidecar changed")
        write_json(sidecar_path, sidecar)


def _prepare_verifiers(args, root, rubric, generation, frozen, screenshot_task, dom_task, evaluation, evaluation_file, require_local_packages, validate_generation_metrics, validate_pair, validate_endpoint_configs):
    auxiliary_control_error = None
    try:
        evaluation["verifier_packages"] = require_local_packages()
    except Exception as error:
        auxiliary_control_error = f"{type(error).__name__}: {error}"
        evaluation["auxiliary_package_error"] = auxiliary_control_error
    auxiliary_preparation_error = None
    try:
        _prepare_generation(root, generation, frozen, screenshot_task, dom_task, validate_generation_metrics)
    except Exception as error:
        auxiliary_preparation_error = f"{type(error).__name__}: {error}"
    try:
        if auxiliary_preparation_error is not None:
            raise ValueError(auxiliary_preparation_error)
        preflight = validate_pair(screenshot_task, dom_task, rubric_file=rubric,
            generation_metrics=generation, eval_config=args.eval_config, require_sidecars=True)
        evaluation["preflight"] = {"status": "passed", **preflight}
    except Exception as error:
        evaluation["preflight"] = {"status": "failed", "error": f"{type(error).__name__}: {error}"}
    try:
        evaluation["auxiliary_endpoint_config"] = validate_endpoint_configs(args.eval_config)
    except Exception as error:
        auxiliary_control_error = f"{type(error).__name__}: {error}"
    write_json(evaluation_file, evaluation)
    run_commands = commands(screenshot_task=screenshot_task, dom_task=dom_task, rubric_file=rubric,
        generation_metrics=generation, eval_config=Path(args.eval_config), run_root=root)
    try:
        evaluation["verifier_parity"] = validate_command_parity(run_commands)
    except Exception as error:
        auxiliary_control_error = f"{type(error).__name__}: {error}"
    return run_commands, auxiliary_control_error


def _verifier_history(stage, root, name):
    history = _attempt_history(stage)
    if len(history) > len(stage.get("attempt_history", [])):
        prior = history[-1]
        snapshots = {}
        for filename in ("result.json", "run_metrics.json", "run.log"):
            original = root / name / filename
            if original.is_file():
                archived = root / name / "_attempts" / f"attempt_{len(history):04d}" / filename
                archived.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, archived)
                snapshots[filename] = {"path": str(archived),
                    **({"sha256": hashlib.sha256(archived.read_bytes()).hexdigest()} if filename == "run_metrics.json" else {})}
        prior["artifact_snapshots"] = snapshots

    return history


def _score_verifier(name, normalizer, root, screenshot_task, dom_task, rubric, generation, stage, run_commands, evaluation_file, evaluation):
    try:
        _run_logged(run_commands[name], root / name / "run.log")
        metrics = normalizer(root / name / "result.json", input_task=screenshot_task if name == "screenshot_verifier" else dom_task,
            rubric_file=rubric, generation_metrics=generation, run_log=root / name / "run.log")
        native_result = read_object(root / name / "result.json")
        write_json(root / name / "run_metrics.json", metrics)
        log = (root / name / "run.log").read_text()[stage["log_start_offset"]:]
        fallback_patterns = {
            "zero_relevance": r"Failed relevance for DOM state|Failed to score screenshot \d+ after",
            "baseline_rescore": r"Failed to rescore (?:criterion \d+|rubric) after",
            "no_penalties": r"Failed to detect side effects after",
            "unknown_outcome": r"Failed outcome verification after",
            "evidence_analysis": r"Failed criterion \d+ / DOM state|Failed to analyze criterion|Batched (?:DOM-state )?analysis failed"}
        fallback_counts = {kind: len(re.findall(pattern, log, flags=re.I)) for kind, pattern in fallback_patterns.items()}
        stage.update(status="ungraded" if metrics.get("status") == "ungraded" or metrics.get("result", {}).get("status") == "ungraded" else "complete",
            artifacts_sha256={filename: hashlib.sha256((root / name / filename).read_bytes()).hexdigest()
                for filename in ("result.json", "run_metrics.json", "run.log")},
            usage=metrics.get("token_usage"), calls=metrics.get("llm_calls"),
            signals=metrics["result"], criteria=metrics["criteria"], penalty_criteria=metrics.get("penalty_criteria", []),
            evidence_diagnostics=metrics.get("dom_model_evidence_audit"),
            citation_checks=native_result.get("citation_checks", (native_result.get("dom_model_evidence_audit") or {}).get("citation_checks")),
            fallback_counts=fallback_counts,
            judgment_quality="fallback_observed" if any(fallback_counts.values()) or metrics.get("result", {}).get("status") == "ungraded" else "no_fallback_observed",
            judgment_quality_basis="Existing warning logs; absence of warnings is not proof that every judgment is correct.",
            reason=metrics.get("ungraded_reason", metrics.get("result", {}).get("ungraded_reason")),
            judge_fallback=metrics.get("judge_fallback", metrics.get("result", {}).get("judge_fallback")),
            validation_repair_events=len(re.findall(r"(?:Error .*attempt|attempt failed|invalid.*retry)", log, flags=re.I)),
            fallback_events=[line for line in log.splitlines() if re.search(
                r"(?:keeping baseline|falling back|fallback|Failed .* after|Failed after)", line, flags=re.I)])
    except BaseException as error:
        stage.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            error=f"{type(error).__name__}: {error}", usage_coverage="unknown")
        write_json(evaluation_file, evaluation)
        if not isinstance(error, Exception):
            raise
    write_json(evaluation_file, evaluation)


def _run_verifier(name, normalizer, root, screenshot_task, dom_task, rubric, generation, evaluation, evaluation_file, run_commands, auxiliary_control_error, preflight_screenshot_task, preflight_dom_model_task):
    stage = evaluation["stages"].get(name, {})
    current_settings = stage_settings(evaluation.get("effective_settings"), name)
    if stage.get("status") == "complete":
        for filename, digest in stage["artifacts_sha256"].items():
            if hashlib.sha256((root / name / filename).read_bytes()).hexdigest() != digest:
                raise ValueError(f"saved {name} judge artifact changed: {filename}")
        return
    history = _verifier_history(stage, root, name)
    try:
        if auxiliary_control_error is not None:
            raise ValueError(auxiliary_control_error)
        if name == "screenshot_verifier":
            format_preflight = preflight_screenshot_task(screenshot_task)
            evidence_count = format_preflight["screenshots"]
        else:
            _, format_preflight, _ = preflight_dom_model_task(dom_task, rubric_file=rubric, generation_metrics=generation)
            evidence_count = format_preflight["dom_model_states"]
    except Exception as error:
        evaluation["stages"][name] = {"status": "blocked", "reason": "auxiliary_preflight_failed",
            "error": f"{type(error).__name__}: {error}", "calls": 0,
            "usage": {"combined": {"total_tokens": 0}}, "usage_coverage": "complete", "attempt_history": history,
            "effective_settings": current_settings}
        write_json(evaluation_file, evaluation)
        return
    if evidence_count == 0:
        evaluation["stages"][name] = {"status": "not_available", "reason": "no_available_format_states",
            "calls": 0, "usage": {"combined": {"total_tokens": 0}}, "usage_coverage": "complete",
            "effective_settings": current_settings}
        write_json(evaluation_file, evaluation)
        return
    stage = {"status": "running", "configured_models": {"judge": native_judge_model(), "action": native_judge_model()},
        "effective_settings": current_settings,
        "result": str(root / name / "result.json"), "usage": None, "usage_coverage": "unknown",
        "attempt_history": history, "preflight": format_preflight,
        "log_start_offset": len((root / name / "run.log").read_text()) if (root / name / "run.log").is_file() else 0}
    evaluation["stages"][name] = stage
    write_json(evaluation_file, evaluation)
    _score_verifier(name, normalizer, root, screenshot_task, dom_task, rubric, generation, stage, run_commands, evaluation_file, evaluation)


def _request_audit(root, screenshot_task, dom_task, rubric, task, evaluation, evaluation_file, audit_history, run_evidence_audit, *, phase="evaluate"):
    call_records = []
    inventory_path = root / "audit_inventory.json"
    inventory_receipt = evaluation["stages"].get("audit", {}).get("inventory")
    evaluation["stages"]["audit"] = {"status": "running", "phase": phase, "calls": call_records,
        "usage_coverage": "unknown", "attempt_history": audit_history,
        "effective_settings": stage_settings(evaluation.get("effective_settings"), "audit"),
        **({"inventory": inventory_receipt} if inventory_receipt else {})}
    write_json(evaluation_file, evaluation)
    try:
        audit = run_evidence_audit(screenshot_dir=screenshot_task, dom_dir=dom_task, rubric_file=rubric,
            screenshot_result=root / "screenshot_verifier" / "result.json", dom_result=root / "dom_model" / "result.json",
            task_alias=task["source_task_id"], model="gemini-3.1-pro-preview", adjudicator_model="gemini-4-argon",
            audit_provider="google", adjudicator_provider="google", call_records=call_records,
            run_name=evaluation["trial_id"], inventory_only=phase == "evaluate", inventory_path=inventory_path)
        inventory_receipt = {"status": "complete", "result": str(inventory_path),
            "result_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest()}
        if phase == "evaluate":
            audit_stage = {"status": "awaiting_adjudication", "phase": phase,
                "inventory": inventory_receipt, "calls": audit["calls"], "usage_coverage": "complete"}
        else:
            write_json(root / "evidence_audit.json", audit)
            audit_stage = {"status": "complete", "phase": phase, "inventory": inventory_receipt,
                "result": str(root / "evidence_audit.json"),
                "result_sha256": hashlib.sha256((root / "evidence_audit.json").read_bytes()).hexdigest(),
                "metrics": audit["metrics"], "calls": call_records}
    except BaseException as error:
        refusal = isinstance(error, ModelResponseRefusal) or any(row.get("refusal_reason") for row in call_records)
        audit_stage = {"status": "interrupted" if isinstance(error, KeyboardInterrupt) else "ungraded" if refusal else "failed",
            "phase": phase, "reason": str(error) if refusal else None,
            "error": f"{type(error).__name__}: {error}", "calls": call_records, "usage_coverage": "unknown",
            **({"inventory": inventory_receipt} if inventory_receipt else {})}
        if not isinstance(error, Exception):
            audit_stage["attempt_history"] = audit_history
            audit_stage["effective_settings"] = stage_settings(evaluation.get("effective_settings"), "audit")
            evaluation["stages"]["audit"] = audit_stage
            write_json(evaluation_file, evaluation)
            raise
    return audit_stage


def _evaluate_audit(root, screenshot_task, dom_task, rubric, recording, task, evaluation, evaluation_file, run_commands, audit_configuration_error, run_evidence_audit, *, phase="evaluate"):
    audit_stage = evaluation["stages"].get("audit", {})
    inventory_receipt = audit_stage.get("inventory")
    if audit_stage.get("status") == "complete":
        if hashlib.sha256((root / "evidence_audit.json").read_bytes()).hexdigest() != audit_stage["result_sha256"]:
            raise ValueError("saved audit judge artifact changed")
        return
    if phase == "evaluate" and audit_stage.get("phase") == "adjudicate":
        raise ValueError("adjudication has started; resume with --stage adjudicate")
    if audit_stage.get("status") == "awaiting_adjudication":
        inventory = audit_stage.get("inventory") or {}
        if (inventory.get("status") != "complete" or Path(inventory.get("result", "")).resolve() != (root / "audit_inventory.json").resolve()
                or not (root / "audit_inventory.json").is_file()
                or hashlib.sha256((root / "audit_inventory.json").read_bytes()).hexdigest() != inventory.get("result_sha256")):
            raise ValueError("saved inventory artifact changed or is missing")
        if phase == "evaluate":
            return
    audit_history = _attempt_history(audit_stage)
    if not recording["coverage"]["audit_eligible_states"]:
        audit_stage = {"status": "not_eligible", "reason": "no_eligible_paired_states", "calls": [], "usage_coverage": "complete"}
    elif audit_configuration_error is not None:
        audit_stage = {"status": "blocked", "reason": "audit_configuration_failed",
            "error": audit_configuration_error, "calls": [], "usage_coverage": "complete"}
    elif evaluation["preflight"]["status"] != "passed":
        audit_stage = {"status": "blocked", "reason": "paired_preflight_failed",
            "error": evaluation["preflight"].get("error"), "calls": [], "usage_coverage": "complete"}
    elif any(evaluation["stages"][name]["status"] != "complete" for name in run_commands):
        audit_stage = {"status": "blocked", "reason": "verifier_results_unavailable", "usage_coverage": "none"}
    else:
        audit_stage = _request_audit(root, screenshot_task, dom_task, rubric, task, evaluation, evaluation_file, audit_history, run_evidence_audit, phase=phase)
    if inventory_receipt is not None:
        audit_stage.setdefault("inventory", inventory_receipt)
    audit_stage.setdefault("phase", phase)
    audit_stage["attempt_history"] = audit_history
    audit_stage["effective_settings"] = stage_settings(evaluation.get("effective_settings"), "audit")
    evaluation["stages"]["audit"] = audit_stage


def _evaluate_recording(args, run, recording):
    from .audit_requests import resolve_audit_config
    from .evidence_audit import run_evidence_audit
    from .package_manifests import require_local_packages
    from .validate_inputs import validate_pair
    from .common import load_canonical_rubric, validate_generation_metrics, validate_endpoint_configs
    from .dom_model.runner import preflight_dom_model_task
    from .screenshot_verifier.preflight import preflight_screenshot_task
    from .normalize_results import normalize_dom_model, normalize_screenshot
    phase = args.stage
    if phase == "evaluate" and not os.environ.get("GEMINI_API_KEY"):
        raise ValueError("primary model grading requires an explicitly configured Google credential")
    task = recording["task"]
    root, screenshot_task, dom_task = _prepare_inputs(run, recording)
    rubric, generation, frozen, rubric_hash = _prepare_rubric(args, root, task, load_canonical_rubric)
    current_settings = evaluation_settings(recording, eval_config=args.eval_config, rubric_hash=rubric_hash,
        judge_model=args.judge_model, evidence_policy="paired")
    if phase == "adjudicate":
        evaluation_file = root / "evaluation.json"
        if not evaluation_file.is_file():
            raise ValueError("adjudication requires a saved evaluation and inventory")
        evaluation = read_object(evaluation_file)
        audit = evaluation.get("stages", {}).get("audit", {})
        if not recording["coverage"]["audit_eligible_states"] or any(
                evaluation.get("stages", {}).get(name, {}).get("status") in {"ungraded", "failed", "blocked", "not_available"}
                for name in ("screenshot_verifier", "dom_model")):
            return 1
        primary = root / "paired_completion.json"
        inventory = audit.get("inventory") or {}
        checkpoint = root / "audit_inventory.json"
        if (not primary.is_file() or read_object(primary).get("method") not in {"model_judge", "exact_final_answer"}
                or any(evaluation.get("stages", {}).get(name, {}).get("status") != "complete"
                    for name in ("screenshot_verifier", "dom_model"))
                or inventory.get("status") != "complete" or not checkpoint.is_file()
                or Path(inventory.get("result", "")).resolve() != checkpoint.resolve()
                or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != inventory.get("result_sha256")):
            raise ValueError("adjudication requires completed completion, native verifiers and an unchanged saved inventory")
    evaluation_file, evaluation = _open_evaluation(root, recording, rubric_hash, current_settings)
    grade = _primary_completion(args, run, root, recording, rubric, rubric_hash, evaluation, evaluation_file)
    audit_configuration_error = _audit_configuration_error(resolve_audit_config)
    evaluation["audit_configuration_error"] = audit_configuration_error
    run_commands, auxiliary_control_error = _prepare_verifiers(args, root, rubric, generation, frozen, screenshot_task, dom_task, evaluation, evaluation_file, require_local_packages, validate_generation_metrics, validate_pair, validate_endpoint_configs)
    for name, normalizer in (("screenshot_verifier", normalize_screenshot), ("dom_model", normalize_dom_model)):
        _run_verifier(name, normalizer, root, screenshot_task, dom_task, rubric, generation, evaluation, evaluation_file, run_commands, auxiliary_control_error, preflight_screenshot_task, preflight_dom_model_task)
    _evaluate_audit(root, screenshot_task, dom_task, rubric, recording, task, evaluation, evaluation_file, run_commands, audit_configuration_error, run_evidence_audit, phase=phase)
    stage_ready = grade is not None and grade["method"] != "ungraded" and all(
        evaluation["stages"][name].get("status") == "complete" for name in ("screenshot_verifier", "dom_model"))
    evaluation.update(status="complete" if stage_ready and evaluation["stages"]["audit"].get("status") == "complete"
        else "awaiting_adjudication" if stage_ready and evaluation["stages"]["audit"].get("status") == "awaiting_adjudication" else "incomplete",
        completed_at=datetime.now(timezone.utc).isoformat())
    if inspect_recording(run)["recording_sha256"] != recording["recording_sha256"]:
        raise ValueError("actor recording changed during full evaluation")
    write_json(evaluation_file, evaluation)
    print(json.dumps({"completion": grade, "evaluation": str(evaluation_file), "status": evaluation["status"]}, indent=2))
    return 0 if evaluation["status"] in {"complete", "awaiting_adjudication"} else 1


def main(argv: list[str] | None = None) -> int:
    import copy
    from .compare_results import compare_profiles
    args = parse_args(argv)
    load_env(args.env_file)
    previous_environment = {key: os.environ.get(key) for key in (
        "NATIVE_JUDGE_PROFILE", "W8_JUDGE_COMPLETION_TARGET")}
    runs = [path.resolve(strict=True) for path in args.run]
    if len(set(runs)) != len(runs):
        raise ValueError("duplicate recording in evaluation selection")
    profiles = ("primary", "pro") if args.compare_profiles else (args.judge_profile or os.environ.get("NATIVE_JUDGE_PROFILE", "primary"),)
    try:
        failed = False
        for profile in profiles:
            os.environ["NATIVE_JUDGE_PROFILE"] = profile
            for run in runs:
                selected = copy.copy(args)
                selected.run = run
                recording = inspect_recording(run)
                selected.rubric = (args.rubric / f"{recording['task']['source_task_id']}.json"
                    if args.rubric.is_dir() else args.rubric)
                if not args.execute:
                    provided = read_object(selected.rubric)
                    if provided.get("task_id") != recording["task"]["source_task_id"]:
                        raise ValueError("rubric belongs to another task")
                    print(json.dumps({"status": "preflight", "recording_sha256": recording["recording_sha256"],
                        "coverage": recording["coverage"], "judge_model": args.judge_model,
                        "native_profile": profile, "native_model": native_judge_model(), "transport": "normal",
                        "evidence_policy": args.judge_evidence_policy, "stage": args.stage,
                        "model_calls": 0, "writes_performed": False}))
                    continue
                common = (run.parent.parent / "evaluations" / "common" /
                    str(recording["task"].get("run_name") or recording["manifest"]["run_name"]) /
                    recording["task"]["observation_mode"] / recording["task"]["source_task_id"] /
                    recording["recording_sha256"] / ("completion_actor_native.json" if args.judge_evidence_policy == "actor_native" else "completion.json"))
                os.environ["W8_JUDGE_COMPLETION_TARGET"] = str(common)
                if args.judge_evidence_policy == "actor_native":
                    os.environ.pop("W8_JUDGE_COMPLETION_TARGET", None)
                    asyncio.run(grade_run(run, selected.rubric, judge_model=args.judge_model,
                        api_key=os.environ.get("GEMINI_API_KEY", ""), base_url=os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
                        execute=True, evidence_policy="actor_native"))
                else:
                    failed = bool(_evaluate_recording(selected, run, recording)) or failed
        if args.compare_profiles and args.execute:
            report = compare_profiles(runs, runs[0].parent.parent / "evaluations" / "profile_comparison.json")
            print(json.dumps({"profile_comparison": report["output"]}))
        return 1 if failed else 0
    finally:
        for key, value in previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
