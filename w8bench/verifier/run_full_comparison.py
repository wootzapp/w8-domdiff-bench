#!/usr/bin/env python3
"""Aggregate actor efficiency, completion and within-run evaluation receipts."""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter
import json
import re
from pathlib import Path

from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.task_recorder.recorder_support import write_json
from .compare_results import compare
from .paired_metrics import aggregate, validate_settings_contracts, validate_recorded_settings
from .run_metrics import summarize, _price_stream
from w8bench.usage import valid_token_component
from w8bench.settings import normalized_settings, require_same_settings


def _read_ledger(path):
    ledger = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not ledger:
        raise ValueError("empty attempt ledger")
    identities = [(row["task_id"], row["trial"], row["arm"]) for row in ledger]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate ledger task/arm/trial")
    trial_counts = {row["trials"] for row in ledger}
    if len(trial_counts) != 1 or next(iter(trial_counts)) <= 0:
        raise ValueError("invalid configured trial count")
    n = next(iter(trial_counts))
    paths = [str(Path(row["recording"]).resolve()) for row in ledger]
    if len(set(paths)) != len(paths):
        raise ValueError("a recording path is reused across scheduled attempts")
    attempt_paths = []
    for row in ledger:
        attempts = row.get("attempts", [])
        if len(attempts) > 2 or [item.get("attempt_number") for item in attempts] != list(range(1, len(attempts) + 1)):
            raise ValueError("technical attempt ledger must contain at most two ordered attempts")
        if attempts and str(Path(attempts[-1]["recording"]).resolve()) != str(Path(row["recording"]).resolve()):
            raise ValueError("scheduled recording is not the final technical attempt")
        attempt_paths.extend(str(Path(item["recording"]).resolve()) for item in attempts)
    if len(attempt_paths) != len(set(attempt_paths)):
        raise ValueError("a technical attempt recording is reused across scheduled rows")
    task_ids = {row["task_id"] for row in ledger}
    if set(identities) != {(task, trial, arm) for task in task_ids for trial in range(1,n+1) for arm in ("dom","screenshot")}:
        raise ValueError("ledger omits a scheduled task/arm/trial")
    validate_settings_contracts(((row["task_id"], row.get("effective_settings")) for row in ledger), label="scheduled")
    return ledger, n, task_ids


def _validate_scheduled_recording(row, mode, task, manifest):
    if (task["source_task_id"] != row["task_id"] or task["observation_mode"] != mode
            or task["instruction"] != row["task"]["instruction"] or task["start_url"] != row["task"]["start_url"]
            or task["run_name"] != row["run_name"] or manifest["run_name"] != row["run_name"]
            or any(task.get(key) != row["task"].get(key) for key in ("category", "difficulty"))):
        raise ValueError("recording differs from its scheduled task, arm or run name")
    if (task.get("catalog_sha256") != manifest.get("catalog_sha256")
            or task.get("catalog_sha256") != row.get("catalog_sha256")
            or task.get("catalog_sha256") != row["task"].get("catalog_sha256")):
        raise ValueError("recording selected catalog hash differs from its schedule")
    if manifest["status"] != row["technical_outcome"]:
        raise ValueError("ledger technical outcome disagrees with recording")


def _scheduled_summary(row, recording, manifest):
    configuration = row["configuration"]
    compared = ("model", "max_turns", "max_output_tokens", "viewport", "reasoning_effort", "base_url",
                "browser_lang", "browser_accept_language", "recorder_code_sha256")
    require_same_settings({key: configuration[key] for key in compared if key in configuration},
        {key: manifest["controls"].get(key) for key in compared if key in configuration}, label="recording controls against schedule")
    expected = row.get("effective_settings")
    if expected is not None:
        require_same_settings(expected.get("actor"), manifest.get("effective_settings"), label="scheduled actor")
    recording["scheduled_effective_settings"] = expected
    summary = summarize(recording)
    if expected is not None and summary.get("evaluation") is not None:
        require_same_settings(expected, summary.get("evaluation_effective_settings"), label="scheduled evaluation")
    if row.get("evaluation_path") and summary.get("evaluation_path") and Path(row["evaluation_path"]).resolve() != Path(summary["evaluation_path"]).resolve():
        raise ValueError("evaluation receipt path differs from its scheduled attempt")
    if row.get("evaluation_outcome") in {"complete", "incomplete", "awaiting_adjudication"} and (
            summary.get("evaluation") is None or row["evaluation_outcome"] != summary["evaluation"].get("status")):
        raise ValueError("evaluation outcome differs from its scheduled receipt")
    return summary


def _scheduled_grade(row, summary):
    grade = summary["completion"]
    grade_available = summary.get("completion_grade_available") is True or grade.get("method") != "ungraded"
    if (grade_available or summary.get("evaluation")) and row.get("rubric"):
        frozen = json.loads(Path(row["rubric"]).read_text())
        rubric_hash = hashlib.sha256(json.dumps(frozen.get("precomputed_rubric", frozen),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        rubric_hashes = {rubric_hash}
        if "criteria" in frozen and "precomputed_rubric" not in frozen:
            canonical = {"items": [{"criterion": item["id"], "description": item["description"],
                "max_points": 1, "earned_points": None, "justification": None} for item in frozen["criteria"]]}
            rubric_hashes.add(hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest())
        if (hashlib.sha256(Path(row["rubric"]).read_bytes()).hexdigest() != row["rubric_sha256"]
                or summary.get("evaluation") is not None and summary["evaluation"].get("rubric_sha256") not in rubric_hashes
                or grade_available and (grade.get("rubric_sha256") not in rubric_hashes
                    or grade.get("judge_model") != row["judge_model"] or grade.get("evidence_policy") != "paired")):
            raise ValueError("grade differs from scheduled rubric, judge or primary evidence policy")
    return grade


def _browser_identity(manifest, *, allow_nonfresh=False):
    profile = manifest.get("browser_profile_provenance") or {}
    fresh = (profile.get("profile_fresh_at_run_start") is True
        and profile.get("freshly_recreated_by_launcher") is True
        and profile.get("launch_mode") == "fresh"
        and type(profile.get("tasks_previously_run_in_container")) is int
            and profile["tasks_previously_run_in_container"] == 0
        and (profile.get("browser_environment") or {}).get("CHROMIUM_RESET_PROFILE") == "1")
    build = (profile.get("browser_build") or {}).get("image_id")
    environment = profile.get("browser_environment")
    if not build or not isinstance(environment,dict) or not environment:
        raise ValueError("browser build or runtime environment is unverified")
    if not fresh and not allow_nonfresh:
        raise ValueError("browser profile freshness is unverified; explicitly allow nonfresh runs to compare them")
    return build, environment


def _recorded_attempts(ledger, *, allow_nonfresh=False):
    indexed = [{}, {}]
    records = {}
    protocols, builds, models, grading_policies, configurations = {}, set(), set(), set(), set()
    environments, capture_policies = set(), set()
    summaries = []
    for row in ledger:
        configurations.add(json.dumps(normalized_settings({key: value for key, value in row["configuration"].items()
            if key not in {"prompt_sha256", "action_schema_sha256"}}), sort_keys=True))
        source = Path(row["recording"])
        key = (row["run_name"], row["task_id"])
        if row["technical_outcome"] in {"not_started", "running"}:
            continue
        if not (source / "final.json").is_file():
            continue
        if row["technical_outcome"] == "technical_failure" and not (source / "manifest.json").is_file():
            continue
        recording = inspect_recording(source)
        mode, task, manifest = row["arm"], recording["task"], recording["manifest"]
        _validate_scheduled_recording(row, mode, task, manifest)
        indexed[0 if mode == "dom" else 1][key] = recording
        records[(row["task_id"],row["trial"],mode)] = recording
        summary = _scheduled_summary(row, recording, manifest)
        summaries.append((row["task_id"], summary))
        models.update(summary["returned_actor_models"])
        grade = _scheduled_grade(row, summary)
        if grade.get("evidence_policy") is not None:
            grading_policies.add(grade["evidence_policy"])
        build, environment = _browser_identity(manifest, allow_nonfresh=allow_nonfresh)
        builds.add(build)
        environments.add(json.dumps(normalized_settings(environment),sort_keys=True))
        capture_policies.add(json.dumps(normalized_settings({key: manifest.get(key) for key in
            ("dom_capture_parameters","renderer_versions")}),sort_keys=True))
        protocol = json.dumps(normalized_settings({"controls": manifest["controls"],
            "dom_capture": manifest.get("dom_capture_parameters"), "renderers": manifest.get("renderer_versions"),
            "action_driver": manifest.get("action_driver"), "action_driver_version": manifest.get("action_driver_version")}), sort_keys=True)
        if mode in protocols and protocols[mode] != protocol:
            raise ValueError(f"{mode} observation/action policy differs across trials")
        protocols[mode] = protocol
    if (len(configurations)>1 or len(builds)>1 or len(models)>1 or len(grading_policies)>1
            or len(environments)>1 or len(capture_policies)>1):
        raise ValueError("scheduled controls, browser builds/environments, capture policies, actor models or judge policies differ")
    validate_recorded_settings(summaries)
    return indexed, records


def _partial_summary(row, arm, task_id):
    source = Path(row["recording"])
    decisions = []
    undecodable_decisions = False
    partial = source / "decisions.jsonl"
    if partial.is_file():
        for line in partial.read_text().splitlines():
            try:
                decision = json.loads(line)
            except json.JSONDecodeError:
                undecodable_decisions = undecodable_decisions or bool(line.strip())
                continue
            if isinstance(decision, dict):
                decisions.append(decision)
            else:
                undecodable_decisions = True
    task = {**row["task"], "source_task_id": task_id, "observation_mode": arm,
        "run_name": row["run_name"]}
    partial_manifest = {"steps": [], "states": [], "controls": row["configuration"]}
    if (source / "manifest.json").is_file():
        partial_manifest = json.loads((source / "manifest.json").read_text())
    turn_evidence = any(any((source / "turns").glob(f"turn_*/{name}.json"))
                        for name in ("request", "response", "result"))
    reported_turns = partial_manifest.get("model_turns")
    counter_clear = ("model_turns" not in partial_manifest or
                     valid_token_component(reported_turns) and reported_turns == 0)
    no_calls = ((row["technical_outcome"] in {"not_started", "startup_failure"} or row.get("actor_calls_attempted") is False)
        and not decisions and not undecodable_decisions and not turn_evidence
        and counter_clear and not partial_manifest.get("steps"))
    summary = summarize({"source": str(source), "task": task,
        "manifest": partial_manifest, "decisions": decisions, "recording_sha256": None,
        "actor_calls_known_zero": no_calls,
        "scheduled_effective_settings": row.get("effective_settings"),
        "partial_recording": True, "final": {"run_status": row["technical_outcome"]}})
    summary.update(recording_available=False, partial_recording=source.exists(),
        turns_complete=no_calls, cost_coverage="complete" if no_calls else "partial")
    response_turn_policy = partial_manifest.get("turn_policy") == "actor-response-turn/v2"
    if response_turn_policy:
        response_turns = {path.parent.name for path in (source / "turns").glob("*/response.json")}
        for transport in (source / "turns").glob("*/transport_attempts.jsonl"):
            for line in transport.read_text().splitlines():
                try:
                    receipt = json.loads(line)
                except json.JSONDecodeError:
                    undecodable_decisions = True
                    continue
                if receipt.get("response_received") is True:
                    response_turns.add(transport.parent.name)
        summary["turns_complete"] = (not decisions and not undecodable_decisions and valid_token_component(reported_turns)
            and reported_turns == 0 and not response_turns
            and not any(json.loads(path.read_text()).get("status") == "started" for path in (source / "turns").glob("*/transport_pending.json")))
    if not no_calls and not decisions and not response_turn_policy:
        summary["turns_missing_usage"] = 1
    if no_calls:
        summary["token_usage"].update(input_tokens=0, output_tokens=0, total_tokens=0)
    return summary


def _pair_attempt(rows, available, task_id, trial, *, allow_nonfresh=False):
    reports, unmatched = [], []
    if all(available.values()):
        receipt, markdown = compare(available["dom"], available["screenshot"], allow_nonfresh=allow_nonfresh)
        reports.append(f"Trial: {trial}\n\n{markdown}")
    else:
        receipt = {"task_id": task_id, "shared_controls": {}, "both_successful": False,
            "successful_pair_turn_delta": None}
        for arm in ("dom", "screenshot"):
            if available[arm]:
                receipt[arm] = summarize(available[arm])
            else:
                unmatched.append({"task_id": task_id, "trial": trial, "arm": arm,
                    "technical_outcome": rows[arm]["technical_outcome"]})
                receipt[arm] = _partial_summary(rows[arm], arm, task_id)
    if "browser_profile_policy" not in receipt:
        nonfresh = []
        for arm, recording in available.items():
            if recording is None:
                continue
            profile = recording["manifest"].get("browser_profile_provenance") or {}
            if not (profile.get("profile_fresh_at_run_start") is True
                    and profile.get("freshly_recreated_by_launcher") is True
                    and profile.get("launch_mode") == "fresh"
                    and type(profile.get("tasks_previously_run_in_container")) is int
            and profile["tasks_previously_run_in_container"] == 0
                    and (profile.get("browser_environment") or {}).get("CHROMIUM_RESET_PROFILE") == "1"):
                nonfresh.append(arm)
        receipt["browser_profile_policy"] = {"allow_nonfresh": allow_nonfresh,
            "nonfresh_arms": nonfresh, "override_used": bool(nonfresh)}
    for arm in ("dom", "screenshot"):
        scheduled, summary = rows[arm], receipt[arm]
        summary["attempt_number"] = scheduled.get("attempt_number", 1)
        summary["attempts"] = scheduled.get("attempts", [])
        summary["technical_failure"] = scheduled["technical_outcome"] == "technical_failure"
        summary["technical_failure_class"] = scheduled.get("technical_failure_class")
        if summary["technical_failure"]:
            summary["technical_completion_diagnostic"] = summary["completion"]
            summary["completion"] = {"method": "ungraded", "verdict": "ungraded", "reason": "technical_failure"}
            summary["completion_grade_available"] = False
        prior = []
        for attempt in scheduled.get("attempts", []):
            if attempt.get("technical_outcome") != "technical_failure" or Path(attempt["recording"]).resolve() == Path(scheduled["recording"]).resolve():
                continue
            attempt_path = Path(attempt["recording"])
            previous = {**scheduled, **attempt}
            if all((attempt_path / name).is_file() for name in ("final.json", "manifest.json", "task.json")):
                recording = inspect_recording(attempt_path)
                _validate_scheduled_recording(previous, arm, recording["task"], recording["manifest"])
                item = summarize(recording)
            else:
                item = _partial_summary(previous, arm, task_id)
            prior.append({"attempt_number": attempt["attempt_number"], "recording": str(attempt_path),
                "technical_failure_class": attempt.get("technical_failure_class"),
                "recording_sha256": item.get("recording_sha256"), "actor_model_turns": item["model_turns"],
                "actor_cost": item["cost_streams"]["actor"]})
        summary["technical_attempts"] = prior
        members = [item["actor_cost"] for item in prior]
        keys = ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens", "cache_write_input_tokens")
        stream = {"model": scheduled["configuration"].get("model"),
            "calls": sum(item["calls"] for item in members) if all(type(item.get("calls")) is int for item in members) else None,
            "call_records": [call for item in members for call in item.get("call_records", [])],
            "unknown_attempts": sum(item.get("unknown_attempts", 0) for item in members),
            "usage": {key: sum(values) if (values := [(item.get("usage") or {})[key] for item in members
                if valid_token_component((item.get("usage") or {}).get(key))]) else 0 if not members else None for key in keys},
            "usage_coverage": "complete" if all(item.get("usage_coverage") == "complete" for item in members) else "partial",
            "attempt_count": len(prior), "scope": "Prior technical attempts; excluded from final actor turns and tokens."}
        _price_stream(stream)
        summary["cost_streams"]["technical_attempts:actor"] = stream
    if any(receipt[arm]["technical_failure"] for arm in ("dom", "screenshot")):
        receipt.update(both_successful=False, successful_pair_turn_delta=None)
    receipt["category"] = rows["dom"]["task"].get("category")
    receipt["difficulty"] = rows["dom"]["task"].get("difficulty")
    receipt["catalog_sha256"] = rows["dom"].get("catalog_sha256")
    if rows["dom"].get("catalog_sha256") != rows["screenshot"].get("catalog_sha256"):
        raise ValueError("scheduled arms use different selected catalog hashes")
    receipt["trial_id"] = str(trial)
    receipt["recordings_paired"] = all(available.values())
    return receipt, reports, unmatched


def _paired_attempts(ledger, n, task_ids, records, *, allow_nonfresh=False):
    pairs, reports, unmatched = [], [], []
    for task_id in sorted(task_ids):
        for trial in range(1,n+1):
            rows = {row["arm"]: row for row in ledger if row["task_id"]==task_id and row["trial"]==trial}
            available = {arm: records.get((task_id,trial,arm)) for arm in ("dom","screenshot")}
            receipt, report, missing = _pair_attempt(rows, available, task_id, trial, allow_nonfresh=allow_nonfresh)
            reports.extend(report)
            unmatched.extend(missing)
            pairs.append(receipt)
    # Shared controls are checked across every recorded attempt, including unmatched ones.
    shared = {json.dumps(normalized_settings({k:v for k,v in r["manifest"]["controls"].items() if k not in {"prompt_sha256", "action_schema_sha256"}}),sort_keys=True)
        for r in records.values()}
    if len(shared)>1:
        raise ValueError("shared actor controls differ across recorded attempts")
    for pair in pairs:
        pair["shared_controls"] = json.loads(next(iter(shared))) if shared else next(iter(ledger))["configuration"]
    return pairs, reports, unmatched


def _report_markdown(summary, pairs, reports):
    lines = ["# DOM versus screenshot actor turns", "",
        f"Scheduled tasks: {summary['scheduled_tasks']}; recorded pairs: {summary['paired_attempts']}; scheduled pairs: {len(pairs)}. No model calls were performed.", "",
        "| Mode | Confirmed successes / attempts | Definitively graded | Mean actor turns (all attempts) | Rejected turns | Stall advisories |",
        "|---|---:|---:|---:|---:|---:|"]
    for mode, row in summary["modes"].items():
        lines.append(f"| {mode} | {row['completion_counts'].get('success', 0)} / {row['attempted_runs']} | {row['definitively_graded_tasks']} | {row['mean_turns_all_attempts']} | {row['rejected_turns']} | {row['stall_advisory_matches']} |")
    lines += ["", "| Mode | Actor-only tokens (known) | Matching native verifier | Matching-verifier tokens (known) | Actor + matching-verifier tokens | Complete runs |",
        "|---|---:|---|---:|---:|---:|"]
    for mode, row in summary["modes"].items():
        arm = row["arm_token_usage"]
        actor = arm["actor_usage"]["total_tokens"]
        native = arm["matching_verifier_usage"]["total_tokens"]
        combined, lower = arm["usage"]["total_tokens"], arm["known_usage_lower_bound"]["total_tokens"]
        displayed = str(combined) if valid_token_component(combined) else f"≥ {lower}" if valid_token_component(lower) else "unknown"
        lines.append(f"| {mode} | {actor if valid_token_component(actor) else 'unknown'} | {arm['matching_verifier']} | {native if valid_token_component(native) else 'unknown'} | {displayed} | {arm['complete_runs']} / {arm['attempted_runs']} |")
    lines += ["", "Arm tokens include the actor and its matching native verifier. Both native verifiers still run for each recording; all judge cost streams remain separate.",
        "Component columns show known recorded usage; ≥ marks a lower bound. Actor tokens per turn remain actor-only."]
    lines += ["", "| Mode | k | pass@k confirmed lower | Possible upper |", "|---|---:|---:|---:|"]
    for mode in ("dom", "screenshot"):
        for k, estimate in summary["modes"][mode]["pass_at_k"].items():
            lines.append(f"| {mode} | {k} | {estimate['confirmed_lower']:.4f} | {estimate['possible_upper']:.4f} |")
    lines += ["", "pass@k requires at least one success among k attempts; all-trials reliability is reported separately.",
        "Per-task criterion results and pass@k are in per_task.json; actor/judge usage and error coverage are in summary.json.",
        "", f"Both-successful matched trial/task pairs: {summary['both_successful_pairs']}.", "", *summary["denominator_notes"], "", *reports]
    return "\n".join(lines) + "\n"


def _write_reports(output, indexed, summary, pairs, reports):
    # Prevent reports from being mixed into immutable source recordings.
    output = output.resolve()
    from w8bench.run_paths import TEMPORAL_NAME_PATTERN
    if any(not re.fullmatch(r"[0-9a-fA-F]{64}(?:_\d+)?(?:\.[A-Za-z0-9]+)?", part) and TEMPORAL_NAME_PATTERN.search(part) for part in output.parts):
        raise ValueError("Report names must use labels and sequence numbers without dates or times")
    if any(output.is_relative_to(Path(r["source"])) for catalog in indexed for r in catalog.values()):
        raise ValueError("reports must be outside recording folders")
    base, number = output, 1
    while True:
        try:
            output.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            number += 1
            output = base.with_name(f"{base.name}_{number}")
    write_json(output / "summary.json", summary)
    write_json(output / "pairs.json", pairs)
    write_json(output / "per_task.json", summary["per_task"])
    (output / "report.md").write_text(_report_markdown(summary, pairs, reports), encoding="utf-8")
    print(json.dumps({"report": str(output / "report.md"), "paired_tasks": summary["paired_tasks"],
        "paired_attempts": summary["paired_attempts"], "scheduled_pairs": summary["scheduled_pairs"],
        "scheduled_tasks": summary["scheduled_tasks"], "evaluated_k": summary["evaluated_k"]}, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True, help="batch schedule and attempt outcomes")
    parser.add_argument("--pass-k", type=int, nargs="+", help="k values; default is all scheduled trial counts")
    parser.add_argument("--output", type=Path, required=True, help="new report directory")
    parser.add_argument("--allow-nonfresh", action="store_true",
        help="explicitly include reused or unverified browser profiles and record the override")
    args = parser.parse_args(argv)
    ledger, n, task_ids = _read_ledger(args.ledger)
    indexed, records = _recorded_attempts(ledger, allow_nonfresh=args.allow_nonfresh)
    pairs, reports, unmatched = _paired_attempts(ledger, n, task_ids, records, allow_nonfresh=args.allow_nonfresh)
    summary = aggregate(pairs, pass_k=args.pass_k)
    summary.update(browser_profile_policy={"allow_nonfresh": args.allow_nonfresh,
        "override_used": any(pair.get("browser_profile_policy", {}).get("override_used") for pair in pairs)},
        scheduled_attempts=len(ledger), scheduled_pairs=len(pairs),
        paired_tasks=len({pair["task_id"] for pair in pairs if pair["recordings_paired"]}),
        paired_attempts=sum(pair["recordings_paired"] for pair in pairs),
        scheduled_tasks=len(task_ids), unmatched_arms=unmatched,
        ledger=str(args.ledger.resolve()),
        technical_outcomes=dict(Counter(row["technical_outcome"] for row in ledger)),
        actor_attempts=sum(sum(bool(item.get("started_at")) or item.get("completed") is True
            for item in row["attempts"]) if row.get("attempts") else int(row["technical_outcome"] not in {"not_started", "running"}) for row in ledger),
        technical_reruns=sum(len(row.get("attempts", [])) == 2 and
            (bool(row["attempts"][1].get("started_at")) or row["attempts"][1].get("completed") is True) for row in ledger),
        technical_failures=sum(row["technical_outcome"] == "technical_failure" for row in ledger),
        evaluation_outcomes=dict(Counter(row.get("evaluation_outcome", "not_available") for row in ledger)),
        full_evaluation_completed_attempts=sum(row.get("evaluation_outcome") == "complete" for row in ledger),
        full_evaluation_completion_rate=sum(row.get("evaluation_outcome") == "complete" for row in ledger) / len(ledger),
        judge_processes_without_usage=sum(bool(row.get("judge_started_at")) and not (Path(row["recording"])/"completion.json").is_file() for row in ledger))
    _write_reports(args.output, indexed, summary, pairs, reports)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
