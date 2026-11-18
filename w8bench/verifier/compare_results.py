"""Compare acting-model turns and completion across independent modality runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.task_recorder.recorder_support import write_json
from .run_metrics import summarize
from .paired_metrics import validate_completion_policy_versions, validate_recorded_settings
from w8bench.settings import normalized_settings, require_same_settings

def _validate_recording_pair(dom, screenshot):
    for recording, mode in ((dom, "dom"), (screenshot, "screenshot")):
        if recording["task"]["observation_mode"] != mode:
            raise ValueError(f"expected a {mode} recording")
        if recording["task"].get("catalog_sha256") != recording["manifest"].get("catalog_sha256"):
            raise ValueError("task and manifest selected catalog hashes differ")
    for key in ("source_task_id", "instruction", "start_url"):
        if dom["task"][key] != screenshot["task"][key]:
            raise ValueError(f"tasks differ for {key}")
    from w8bench.task_recorder.runner import ACTION_SCHEMA, SCREENSHOT_ACTION_SCHEMA
    for recording, schema in ((dom, ACTION_SCHEMA), (screenshot, SCREENSHOT_ACTION_SCHEMA)):
        expected = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        if recording["manifest"]["controls"].get("action_schema_sha256") != expected:
            raise ValueError("recorded actor action schema does not match its observation contract")
    left, right = dom["manifest"]["controls"], screenshot["manifest"]["controls"]
    # Policies necessarily describe different observations. All other actor
    # controls must match; histories, final answers and state counts may differ.
    if normalized_settings({k: v for k, v in left.items() if k not in {"prompt_sha256", "action_schema_sha256"}}) != normalized_settings({k: v for k, v in right.items() if k not in {"prompt_sha256", "action_schema_sha256"}}):
        raise ValueError("actor model, budget, viewport, action schema or other shared controls differ")
    for key in ("dom_capture_parameters","renderer_versions"):
        if not dom["manifest"].get(key) or normalized_settings(dom["manifest"][key]) != normalized_settings(screenshot["manifest"].get(key)):
            raise ValueError(f"shared capture policies differ for {key}")
    if any(dom["task"].get(key) != screenshot["task"].get(key) for key in ("category", "difficulty", "catalog_sha256")):
        raise ValueError("task category, difficulty or catalog hash differs between arms")
    return left


def _validate_summary_pair(summaries):
    validate_completion_policy_versions(summaries.values())
    validate_recorded_settings([(None, row) for row in summaries.values()])
    evaluation_hashes = {row["evaluation"]["rubric_sha256"] for row in summaries.values() if row.get("evaluation")}
    if len(evaluation_hashes) > 1:
        raise ValueError("frozen evaluation rubric differs between arms")
    grades = [summaries[m]["completion"] for m in ("dom", "screenshot")]
    policies = {g["evidence_policy"] for g in grades if g.get("evidence_policy") is not None}
    if len(policies) > 1:
        raise ValueError("completion controls differ for evidence_policy")
    if all(g.get("method") != "ungraded" for g in grades):
        for key in ("rubric_sha256", "evidence_policy", "method", "judge_model", "returned_judge_model", "judge_prompt_sha256", "judge_base_url", "max_output_tokens", "judge_schema_sha256"):
            if normalized_settings({key: grades[0].get(key)}) != normalized_settings({key: grades[1].get(key)}):
                raise ValueError(f"completion controls differ for {key}")
    actual_models = [summaries[m]["returned_actor_models"] for m in ("dom", "screenshot")]
    if actual_models[0] and actual_models[1] and actual_models[0] != actual_models[1]:
        raise ValueError("returned actor model versions differ")
    return grades


def _validate_browser_pair(dom, screenshot):
    builds, environments = [], []
    for recording in (dom, screenshot):
        profile = recording["manifest"].get("browser_profile_provenance") or {}
        if profile.get("profile_fresh_at_run_start") is not True:
            raise ValueError("browser profile freshness is unverified; use the controlled task launcher")
        builds.append((profile.get("browser_build") or {}).get("image_id"))
        environments.append(profile.get("browser_environment"))
    if not all(isinstance(environment,dict) and environment for environment in environments):
        raise ValueError("browser runtime environments are unverified")
    require_same_settings(environments[0], environments[1], label="browser runtime environments")
    if all(builds) and builds[0] != builds[1]:
        raise ValueError("browser image IDs differ")
    if not all(builds):
        raise ValueError("browser builds are unverified")


def compare(dom: dict[str, Any], screenshot: dict[str, Any]) -> tuple[dict[str, Any], str]:
    left = _validate_recording_pair(dom, screenshot)
    summaries = {"dom": summarize(dom), "screenshot": summarize(screenshot)}
    grades = _validate_summary_pair(summaries)
    _validate_browser_pair(dom, screenshot)
    both_success = all(g.get("verdict") == "success" for g in grades)
    receipt = {"schema_version": "2.0", "task_id": dom["task"]["source_task_id"],
        "shared_controls": {k: v for k, v in left.items() if k not in {"prompt_sha256", "action_schema_sha256"}},
        "observation_schema_sha256": {mode: item["manifest"]["controls"]["action_schema_sha256"] for mode, item in (("dom", dom), ("screenshot", screenshot))},
        "environment_notes": [], "category": dom["task"].get("category"),
        "difficulty": dom["task"].get("difficulty"), "catalog_sha256": dom["task"].get("catalog_sha256"), **summaries,
        "screenshot_minus_dom_turns": summaries["screenshot"]["model_turns"] - summaries["dom"]["model_turns"],
        "both_successful": both_success,
        "successful_pair_turn_delta": summaries["screenshot"]["model_turns"] - summaries["dom"]["model_turns"] if both_success else None}
    lines = [f"# {receipt['task_id']}: independent actor runs", "",
        "| Mode | Completion | Actor turns | Rejected | Actions | Actor seconds | Tokens |",
        "|---|---|---:|---:|---:|---:|---:|"]
    for mode, row in summaries.items():
        tokens = str(row["token_usage"]["total_tokens"]) + (" (incomplete)" if row["turns_missing_usage"] else "")
        lines.append(f"| {mode} | {row['completion']['verdict']} | {row['model_turns']} | {row['rejected_turns']} | {row['action_attempts']} | {row['actor_latency_seconds']:.3f} | {tokens} |")
    lines += ["", "Turns include rejected proposals, malformed responses and termination. Judge calls are excluded.",
        "Cached input and reasoning tokens are subsets of input/output usage; they are not added again.",
        "A successful-pair efficiency comparison is available only when both independently graded runs succeed."]
    return receipt, "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dom-run", type=Path, required=True)
    parser.add_argument("--screenshot-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt, markdown = compare(inspect_recording(args.dom_run), inspect_recording(args.screenshot_run))
    if args.output.suffix != ".md":
        raise ValueError("--output must name a Markdown (.md) report")
    if any(args.output.resolve().is_relative_to(path.resolve()) for path in (args.dom_run, args.screenshot_run)):
        raise ValueError("reports must be outside recording folders")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    write_json(args.output.with_suffix(".json"), receipt)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
