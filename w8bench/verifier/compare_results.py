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
from w8bench.usage import valid_token_component

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
        "| Mode | Completion | Actor turns | Rejected | Stall advisories | Actions | Actor seconds | Actor-only tokens |",
        "|---|---|---:|---:|---:|---:|---:|---:|"]
    for mode, row in summaries.items():
        tokens = str(row["token_usage"]["total_tokens"]) + (" (incomplete)" if row["turns_missing_usage"] else "")
        lines.append(f"| {mode} | {row['completion']['verdict']} | {row['model_turns']} | {row['rejected_turns']} | {row['stall_advisory_matches']} | {row['action_attempts']} | {row['actor_latency_seconds']:.3f} | {tokens} |")
    lines += ["", "| Mode | Actor-only tokens (known) | Matching native verifier | Matching-verifier tokens (known) | Actor + matching-verifier tokens | Coverage |",
        "|---|---:|---|---:|---:|---|"]
    for mode, row in summaries.items():
        arm = row["arm_token_usage"]
        actor = arm["actor_usage"]["total_tokens"]
        native = arm["matching_verifier_usage"]["total_tokens"]
        combined, lower = arm["usage"]["total_tokens"], arm["known_usage_lower_bound"]["total_tokens"]
        displayed = str(combined) if valid_token_component(combined) else f"≥ {lower}" if valid_token_component(lower) else "unknown"
        lines.append(f"| {mode} | {actor if valid_token_component(actor) else 'unknown'} | {arm['matching_verifier']} | {native if valid_token_component(native) else 'unknown'} | {displayed} | {arm['coverage']} |")
    lines += ["", f"Browser profiles: {'nonfresh override used for ' + ', '.join(profile_policy['nonfresh_arms']) if profile_policy['override_used'] else 'verified fresh launches'}.",
        "", "Turns include rejected proposals, malformed responses and termination. Judge calls are excluded.",
        "Arm tokens include the actor and its matching native verifier; both native verifiers execute and all judge cost streams remain separate.",
        "Component columns show known recorded usage; ≥ marks a lower bound. Tokens per turn remain actor-only.",
        "Cached input and reasoning tokens are subsets of input/output usage; they are not added again.",
        "A successful-pair efficiency comparison is available only when both independently graded runs succeed."]
    return receipt, "\n".join(lines) + "\n"



def compare_profiles(runs, output):
    """Compare separately bound native judgments without pairing run evidence."""
    from w8bench.task_recorder.prepare_verifier_data import inspect_recording
    from .run_metrics import _price_stream, _evaluation_streams
    rows, unavailable, evaluation_costs, profile_runs = [], [], [], []
    for run in runs:
        recording = inspect_recording(run)
        task = recording["task"]
        suffix = Path(str(task.get("run_name") or recording["manifest"]["run_name"])) / task["observation_mode"] / task["source_task_id"] / recording["recording_sha256"]
        base = run.parent.parent / "evaluations"
        roots = {"primary": base / "profiles" / "primary" / suffix, "pro": base / "profiles" / "pro" / suffix}
        evaluations = {profile: json.loads((root / "evaluation.json").read_text()) for profile, root in roots.items()}
        bindings = {(value["recording_sha256"], value["rubric_sha256"], value["task_id"], value["actor_arm"], value["trial_id"])
            for value in evaluations.values()}
        if len(bindings) != 1 or next(iter(bindings))[0] != recording["recording_sha256"]:
            raise ValueError("Judge profiles are not bound to the same recording and rubric")
        audits = {profile: json.loads((root / "evidence_audit.json").read_text())
            if evaluations[profile]["stages"].get("audit", {}).get("status") == "complete" else None for profile, root in roots.items()}
        profile_costs = {}
        for profile, value in evaluations.items():
            for mode in ("screenshot_verifier", "dom_model"):
                expected = "gemini-3.5-flash-lite" if profile == "primary" else "gemini-3.1-pro-preview"
                if value["effective_settings"]["stages"][mode]["models"] != [expected, expected]:
                    raise ValueError("Native model profile does not match its output location")
            grade_path = roots[profile] / "paired_completion.json"
            grade = json.loads(grade_path.read_text()) if grade_path.exists() else None
            streams, _ = _evaluation_streams(value["stages"], value, roots[profile] / "evaluation.json", grade, None)
            for stream in streams.values():
                _price_stream(stream)
            native_stages = {mode: value["stages"].get(mode, {})
                for mode in ("screenshot_verifier", "dom_model")}
            native_repairs = sum(attempt.get("validation_repair_events", 0)
                for stage in native_stages.values() for attempt in [*stage.get("attempt_history", []), stage])
            audit_stage = value["stages"].get("audit", {})
            audit_repairs = sum(max(0, sum(call.get("stage") == part for call in attempt.get("calls", [])) - 1)
                for attempt in [*audit_stage.get("attempt_history", []), audit_stage]
                for part in ("inventory", "adjudication"))
            calls = [call for name, stream in streams.items()
                if name not in {"paired_completion", "actor_native_completion", "rubric_import"}
                for call in stream.get("call_records", [])]
            losses_available = audits[profile] is not None and all(
                isinstance(audits[profile].get("metrics", {}).get(key, {}).get("rate"), (int, float))
                and not isinstance(audits[profile]["metrics"][key]["rate"], bool)
                for key in ("screenshot_evidence_loss", "dom_model_evidence_loss"))
            profile_runs.append({"profile": profile, "task_id": task["source_task_id"],
                "arm": task["observation_mode"], "trial": task.get("run_name"),
                "recording_sha256": recording["recording_sha256"],
                "native_statuses": {mode: stage.get("status", "missing") for mode, stage in native_stages.items()},
                "ungraded_native_results": [mode for mode, stage in native_stages.items() if stage.get("status") != "complete"],
                "repair_attempts": native_repairs + audit_repairs,
                "native_validation_repair_events": native_repairs, "audit_repair_attempts": audit_repairs,
                "refusals": sum(bool(call.get("refusal_reason")) or call.get("error_type") == "ModelResponseRefusal" for call in calls),
                "audit_blocked_by_unavailable_native": audit_stage.get("reason") == "verifier_results_unavailable",
                "loss_values_available": losses_available, "audit_status": audit_stage.get("status", "missing")})
            profile_costs[profile] = {name: {"cost": stream["cost"], "usage": stream.get("usage"), "calls": stream.get("calls")}
                for name, stream in streams.items() if name not in {"paired_completion", "actor_native_completion", "rubric_import"}}
        evaluation_costs.append({"task_id": task["source_task_id"], "arm": task["observation_mode"],
            "trial": task.get("run_name"), "recording_sha256": recording["recording_sha256"], "profiles": profile_costs,
            "shared_completion": "One common completion grade, charged once under the primary evaluation."})
        screenshot_only = {profile: None if audit is None else {
            item["criterion_index"] for item in audit.get("criteria", [])
            if item["screenshot"]["coverage"] == "COMPLETE" and item["dom_model"]["coverage"] != "COMPLETE"
            and item["dom_model_evidence_loss"]} for profile, audit in audits.items()}
        both_available = all(value is not None for value in screenshot_only.values())
        screenshot_only.update(union=screenshot_only["primary"] | screenshot_only["pro"] if both_available else None,
            intersection=screenshot_only["primary"] & screenshot_only["pro"] if both_available else None)
        for mode in ("screenshot_verifier", "dom_model"):
            stages = {profile: value["stages"].get(mode, {}) for profile, value in evaluations.items()}
            if any(value.get("status") != "complete" for value in stages.values()):
                unavailable.append({"task_id": task["source_task_id"], "arm": task["observation_mode"],
                    "trial": task.get("run_name"), "format": mode, "reason": "native_profile_ungraded"})
                continue
            criteria = {profile: value["criteria"] for profile, value in stages.items()}
            if len(criteria["primary"]) != len(criteria["pro"]):
                raise ValueError("Native profile criterion lists differ")
            details = []
            costs = {}
            for profile, root in roots.items():
                metrics = json.loads((root / mode / "run_metrics.json").read_text())
                calls = [call for value in metrics["provider_call_metrics"].values() for call in value.get("calls", [])]
                stream = {"calls": metrics["llm_calls"].get("total"), "call_records": calls, "usage_coverage": "complete"}
                _price_stream(stream)
                costs[profile] = {"cost": stream["cost"], "tokens": metrics["token_usage"], "calls": metrics["llm_calls"].get("total")}
            for index, (a, b) in enumerate(zip(criteria["primary"], criteria["pro"])):
                if (a["criterion"], a["max_points"]) != (b["criterion"], b["max_points"]):
                    raise ValueError("Native profile frozen criterion identity differs")
                details.append({"criterion_index": index, "criterion": a["criterion"], "primary_points": a["final_points"],
                    "pro_points": b["final_points"], "agrees": a["final_points"] == b["final_points"],
                    "screenshot_only_evidence": {name: None if indices is None else index in indices
                        for name, indices in screenshot_only.items()}})
            subsets = {}
            for name, indices in screenshot_only.items():
                only = [item for item in details if indices is not None and item["criterion_index"] in indices]
                subsets[name] = {"available": indices is not None,
                    "criterion_indices": sorted(indices) if indices is not None else None,
                    "criteria": len(only) if indices is not None else None,
                    "agreements": sum(item["agrees"] for item in only) if indices is not None else None,
                    "agreement": sum(item["agrees"] for item in only) / len(only) if only else None}
            losses = {profile: None if audit is None else {key: audit["metrics"][key]
                for key in ("screenshot_evidence_loss", "dom_model_evidence_loss")} for profile, audit in audits.items()}
            loss_differences = {key: None if any(value is None for value in losses.values()) else
                losses["primary"][key]["rate"] - losses["pro"][key]["rate"]
                for key in ("screenshot_evidence_loss", "dom_model_evidence_loss")}
            rows.append({"task_id": task["source_task_id"], "arm": task["observation_mode"], "trial": task.get("run_name"),
                "recording_sha256": recording["recording_sha256"], "format": mode,
                "criteria": details, "agreement": sum(item["agrees"] for item in details) / len(details),
                "disagreements": [item for item in details if not item["agrees"]],
                "screenshot_only_subsets": subsets, "losses": losses, "loss_rate_difference_primary_minus_pro": loss_differences,
                "completion_effect": "none; the common completion judge has no native-verifier input and its grade is reused",
                "usage_and_cost": costs})
    quality = {}
    for profile in ("primary", "pro"):
        selected = [row for row in profile_runs if row["profile"] == profile]
        quality[profile] = {"runs": len(selected),
            "ungraded_native_results": sum(len(row["ungraded_native_results"]) for row in selected),
            "repair_attempts": sum(row["repair_attempts"] for row in selected),
            "native_validation_repair_events": sum(row["native_validation_repair_events"] for row in selected),
            "audit_repair_attempts": sum(row["audit_repair_attempts"] for row in selected),
            "refusals": sum(row["refusals"] for row in selected),
            "audits_blocked_by_unavailable_native": sum(row["audit_blocked_by_unavailable_native"] for row in selected),
            "runs_without_loss_values": sum(not row["loss_values_available"] for row in selected),
            "by_arm": {arm: {"runs": sum(row["arm"] == arm for row in selected),
                "ungraded_native_results": sum(len(row["ungraded_native_results"]) for row in selected if row["arm"] == arm),
                "repair_attempts": sum(row["repair_attempts"] for row in selected if row["arm"] == arm),
                "refusals": sum(row["refusals"] for row in selected if row["arm"] == arm),
                "audits_blocked_by_unavailable_native": sum(row["audit_blocked_by_unavailable_native"] for row in selected if row["arm"] == arm),
                "runs_without_loss_values": sum(not row["loss_values_available"] for row in selected if row["arm"] == arm)}
                for arm in ("dom", "screenshot")}}
    report = {"schema_version": "native-profile-comparison/v2", "profiles": {
        "primary": "gemini-3.5-flash-lite", "pro": "gemini-3.1-pro-preview"}, "rows": rows, "unavailable": unavailable, "evaluation_costs": evaluation_costs,
        "screenshot_only_subset": "Each profile's own same-run audit: screenshot COMPLETE, DOM PARTIAL or ABSENT, adjudicated DOM loss; report both subsets, their union and intersection. Judge-defined, not human ground truth. Missing audits give unavailable subsets, not empty ones.",
        "profile_quality": quality, "profile_runs": profile_runs,
        "quality_scope": "Native and audit stages, including recorded prior attempts; shared completion excluded. Repair counts combine observed native validation-repair log events and audit calls beyond the first per stage/attempt. Refusals require an explicit refusal receipt; absence of such a receipt is not proof that none occurred. Categories overlap.",
        "pairing": "Each audit uses only one recording's own formats; the four arm/direction values are reported under their driving arm."}
    output = Path(output)
    number = 2
    target = output
    while target.exists():
        target = output.with_name(f"{output.stem}_{number}{output.suffix}")
        number += 1
    report["output"] = str(target)
    write_json(target, report)
    return report


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
