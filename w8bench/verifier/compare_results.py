"""Compare acting-model turns and completion across independent modality runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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


def _validate_browser_pair(dom, screenshot, *, allow_nonfresh=False):
    builds, environments, nonfresh = [], [], []
    for mode, recording in (("dom", dom), ("screenshot", screenshot)):
        profile = recording["manifest"].get("browser_profile_provenance") or {}
        fresh = (profile.get("profile_fresh_at_run_start") is True
            and profile.get("freshly_recreated_by_launcher") is True
            and profile.get("launch_mode") == "fresh"
            and type(profile.get("tasks_previously_run_in_container")) is int
            and profile["tasks_previously_run_in_container"] == 0
            and (profile.get("browser_environment") or {}).get("CHROMIUM_RESET_PROFILE") == "1")
        if not fresh:
            nonfresh.append(mode)
        builds.append((profile.get("browser_build") or {}).get("image_id"))
        environments.append(profile.get("browser_environment"))
    if not all(isinstance(environment,dict) and environment for environment in environments):
        raise ValueError("browser runtime environments are unverified")
    require_same_settings(environments[0], environments[1], label="browser runtime environments")
    if all(builds) and builds[0] != builds[1]:
        raise ValueError("browser image IDs differ")
    if not all(builds):
        raise ValueError("browser builds are unverified")
    if nonfresh and not allow_nonfresh:
        raise ValueError("browser profile freshness is unverified; use the controlled task launcher or explicitly allow nonfresh runs")
    return {"allow_nonfresh": bool(allow_nonfresh), "nonfresh_arms": nonfresh,
        "override_used": bool(nonfresh)}


def compare(dom: dict[str, Any], screenshot: dict[str, Any], *, allow_nonfresh: bool = False) -> tuple[dict[str, Any], str]:
    left = _validate_recording_pair(dom, screenshot)
    summaries = {"dom": summarize(dom), "screenshot": summarize(screenshot)}
    grades = _validate_summary_pair(summaries)
    profile_policy = _validate_browser_pair(dom, screenshot, allow_nonfresh=allow_nonfresh)
    both_success = all(g.get("verdict") == "success" for g in grades)
    receipt = {"schema_version": "2.0", "task_id": dom["task"]["source_task_id"],
        "shared_controls": {k: v for k, v in left.items() if k not in {"prompt_sha256", "action_schema_sha256"}},
        "observation_schema_sha256": {mode: item["manifest"]["controls"]["action_schema_sha256"] for mode, item in (("dom", dom), ("screenshot", screenshot))},
        "environment_notes": [], "browser_profile_policy": profile_policy, "category": dom["task"].get("category"),
        "difficulty": dom["task"].get("difficulty"), "catalog_sha256": dom["task"].get("catalog_sha256"), **summaries,
        "screenshot_minus_dom_turns": summaries["screenshot"]["model_turns"] - summaries["dom"]["model_turns"],
        "both_successful": both_success,
        "successful_pair_turn_delta": summaries["screenshot"]["model_turns"] - summaries["dom"]["model_turns"] if both_success else None}
    lines = [f"# {receipt['task_id']}: independent actor runs", "",
        "| Mode | Completion | Actor turns | Rejected | Stall advisories | Actions | Actor seconds | Tokens |",
        "|---|---|---:|---:|---:|---:|---:|---:|"]
    for mode, row in summaries.items():
        tokens = str(row["token_usage"]["total_tokens"]) + (" (incomplete)" if row["turns_missing_usage"] else "")
        lines.append(f"| {mode} | {row['completion']['verdict']} | {row['model_turns']} | {row['rejected_turns']} | {row['stall_advisory_matches']} | {row['action_attempts']} | {row['actor_latency_seconds']:.3f} | {tokens} |")
    lines += ["", f"Browser profiles: {'nonfresh override used for ' + ', '.join(profile_policy['nonfresh_arms']) if profile_policy['override_used'] else 'verified fresh launches'}.",
        "", "Turns include rejected proposals, malformed responses and termination. Judge calls are excluded.",
        "Cached input and reasoning tokens are subsets of input/output usage; they are not added again.",
        "A successful-pair efficiency comparison is available only when both independently graded runs succeed."]
    return receipt, "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dom-run", type=Path, required=True)
    parser.add_argument("--screenshot-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-nonfresh", action="store_true",
        help="explicitly compare reused or unverified browser profiles and record the override")
    args = parser.parse_args(argv)
    receipt, markdown = compare(inspect_recording(args.dom_run), inspect_recording(args.screenshot_run),
        allow_nonfresh=args.allow_nonfresh)
    from w8bench.run_paths import TEMPORAL_NAME_PATTERN
    if any(not re.fullmatch(r"[0-9a-fA-F]{64}(?:_\d+)?(?:\.[A-Za-z0-9]+)?", part) and TEMPORAL_NAME_PATTERN.search(part) for part in args.output.parts):
        raise ValueError("Report names must use labels and sequence numbers without dates or times")
    if args.output.suffix != ".md":
        raise ValueError("--output must name a Markdown (.md) report")
    if any(args.output.resolve().is_relative_to(path.resolve()) for path in (args.dom_run, args.screenshot_run)):
        raise ValueError("reports must be outside recording folders")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    base, number = args.output, 1
    while args.output.exists() or args.output.with_suffix(".json").exists():
        number += 1
        args.output = base.with_name(f"{base.stem}_{number}{base.suffix}")
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(markdown)
    write_json(args.output.with_suffix(".json"), receipt)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
