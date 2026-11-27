"""Scheduled denominators and paired outcome aggregation."""

import asyncio
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
from w8bench.run_paths import run_directory

import pytest

from tests.conftest import _audit, _row, write_attempt_ledger
from w8bench.task_recorder import task_cli
from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.task_recorder.recorder_support import write_json, write_json_lines
from w8bench.verifier import aggregate_runs as audit_aggregate, audit_requests as audit
from w8bench.verifier.common import canonical_sha256
from w8bench.verifier.compare_results import compare
from w8bench.verifier.completion import grade_run
from w8bench.verifier.paired_metrics import aggregate
from w8bench.verifier.run_full_comparison import main as compare_main
from w8bench.verifier.run_metrics import summarize


def runs(tmp_path, *, k, flagged=None):
    counts = (2, 2)
    tmp_path = tmp_path / "evaluations"
    flagged = flagged or {}
    roots = []
    for pass_index in range(k):
        root = tmp_path / f"pass{pass_index + 1}"
        roots.append(root)
        for task_index, count in enumerate(counts):
            task_id = f"task_{task_index + 1:02d}"
            rows = []
            for index in range(count):
                values = {key: (pass_index, task_index, index, key) in flagged for key in (*audit_aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")}
                row = _row(screen_loss=values[(*audit_aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")[0]], dom_loss=values[(*audit_aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")[1]],
                           screen_caught=not values[(*audit_aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")[2]], dom_caught=not values[(*audit_aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")[3]])
                row.update(criterion_index=index, criterion=f"Criterion {index}", description="Evidence requirement",
                           max_points=1, adjudication={key: {"confirmed": value, "explanation": "Saved evidence requirement."} for key, value in values.items()})
                rows.append(row)
            value = _audit(task_id, rows)
            value["task_alias"] = task_id
            value["shared_trajectory"] = {"task_id": task_id, "initial_url": "https://example.test", "recording_id": root.name}
            value["frozen_rubric_sha256"] = canonical_sha256([
                {key: row[key] for key in ("criterion_index", "criterion", "description", "max_points")}
                for row in rows])
            value["input_fingerprints"] = {
                "frozen_rubric": value["frozen_rubric_sha256"],
                "shared_trajectory": canonical_sha256(value["shared_trajectory"]),
                "screenshot_verifier_result": "1" * 64, "dom_verifier_result": "2" * 64,
                "screenshot_sources": {"screenshot0.png": "3" * 64},
                "dom_sources": {"dom_model0.txt": "4" * 64},
            }
            value["generation_settings"] = {
                stage: {"provider": provider, "api_version": version, "requested": deepcopy(settings),
                        "actual": [deepcopy(settings)], "injected_complete": False}
                for stage, provider, version, settings in (
                    ("inventory", "google", "v1beta", audit.GEMINI_GENERATION_SETTINGS),
                    ("adjudication", "google", "v1beta", audit.GEMINI_GENERATION_SETTINGS))
            }
            evidence = tmp_path / "evidence" / task_id
            evidence.mkdir(parents=True, exist_ok=True)
            for filename in ("screenshot0.png", "dom_model0.txt", "ss-web_surfer.log", "dom-web_surfer.log"):
                (evidence / filename).write_bytes(filename.encode())
            value["evidence_paths"] = {
                "screenshots": [str(evidence / "screenshot0.png")],
                "dom_states": [str(evidence / "dom_model0.txt")],
                "action_history": {"screenshot": str(evidence / "ss-web_surfer.log"),
                                   "dom_model": str(evidence / "dom-web_surfer.log")},
            }
            value["calls"] = [
                {"stage": "inventory", "response_model": "inventory-response"},
                {"stage": "adjudication", "response_model": "adjudication-response"},
            ]
            path = root / task_id / "evidence_audit.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
            write_json(tmp_path.parent / "recordings" / root.name / task_id / "manifest.json", {
                "browser_profile_provenance": {"profile_fresh_at_run_start": True,
                    "freshly_recreated_by_launcher": True, "launch_mode": "fresh",
                    "tasks_previously_run_in_container": 0,
                    "browser_environment": {"CHROMIUM_RESET_PROFILE": "1"}}})
    return roots

def _actor_trial_pair(trial, verdict):
    row = {
        "returned_actor_models": ["gemini-3.1-pro-preview"],
        "completion": {"method": "ungraded" if verdict == "ungraded" else "model_judge",
            "verdict": verdict, "criteria": [{"id": "done", "verdict": verdict}]},
        "token_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        "model_turns": 1, "rejected_turns": 0, "turns_missing_usage": 0,
        "action_attempts": 1, "actor_latency_seconds": 0,
        "action_errors": 0, "model_error_turns": 0, "parse_error_turns": 0,
        "run_status": "completed",
    }
    return {"task_id": "task", "trial_id": str(trial), "shared_controls": {},
        "both_successful": verdict == "success", "successful_pair_turn_delta": 0,
        "dom": deepcopy(row), "screenshot": deepcopy(row)}

def compare_case(case):
    write_json_lines(case.ledger, case.rows)
    return compare_main(["--ledger", str(case.ledger), "--output", str(case.output)])

@pytest.mark.usefixtures('no_network')
def test_arbitrary_trial_count_pass_k_unknowns_and_criterion_identity(run_pair):
    import copy
    paths, *_ = run_pair
    receipt, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    pairs = []
    for index, verdict in enumerate(("success", "failure", "uncertain", "failure", "success"), 1):
        pair = copy.deepcopy(receipt)
        pair['trial_id'] = f'repeat_{index}'
        for mode in ('dom', 'screenshot'):
            pair[mode]['completion'] = {'method':'model_judge','verdict':verdict,'rubric_sha256':'frozen',
                'criteria':[{'id':'c01','verdict':'success' if index==1 else 'failure'}]}
        pair['both_successful'] = verdict=='success'
        pair['successful_pair_turn_delta'] = 1 if verdict=='success' else None
        pairs.append(pair)
    summary = aggregate(pairs)
    assert summary['paired_tasks']==1 and summary['paired_attempts']==5
    assert summary['evaluated_k']==[1,2,3,4,5]
    result=summary['modes']['dom']
    assert result['attempted_runs']==5 and result['tokens']==600
    assert result['pass_at_k']['1']['confirmed_lower']==pytest.approx(2/5)
    assert result['pass_at_k']['1']['possible_upper']==pytest.approx(3/5)
    assert result['pass_at_k']['1']['estimate'] is None
    assert result['pass_at_k']['2']['confirmed_lower']==pytest.approx(0.7)
    assert result['pass_at_k']['2']['possible_upper']==pytest.approx(0.9)
    assert result['pass_at_k']['5']['estimate']==1
    criterion=summary['per_task']['task_01']['dom']['criteria']['c01']
    assert criterion['pass_at_k']['2']['estimate']==pytest.approx(2/5)
    assert summary['both_successful_pairs']==2 and summary['both_successful_tasks']==1
    assert result['all_trials_success_rate_confirmed']==0
    with pytest.raises(ValueError,match='at least k'):
        aggregate(pairs,pass_k=[6])
    broken=copy.deepcopy(pairs);broken[1]['dom']['completion']['rubric_sha256']='changed'
    with pytest.raises(ValueError,match='frozen rubric'):
        aggregate(broken)
    with pytest.raises(ValueError,match='duplicate trial'):
        aggregate(pairs+[pairs[0]])
    extra=copy.deepcopy(pairs[1]);extra['task_id']='another_task'
    uneven=aggregate(pairs+[extra])
    assert uneven['evaluated_k']==[1] and not uneven['balanced_trial_counts']
    assert uneven['modes']['dom']['pass_at_k']['1']['confirmed_lower']==pytest.approx(0.2)
    assert uneven['modes']['dom']['pass_at_k']['1']['possible_upper']==pytest.approx(0.3)

@pytest.mark.usefixtures('no_network')
def test_ledger_comparison_uses_every_scheduled_trial_and_rejects_omissions(run_pair, tmp_path):
    import shutil
    paths, *_ = run_pair
    rubric = tmp_path / "frozen.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.",
        "start_url": "https://example.test", "expected_answer": "done"})
    recordings = {}
    for trial in range(1, 3):
        run_name = f"trial_{trial:04d}"
        for mode in ("dom", "screenshot"):
            run = tmp_path / "repeated" / run_name / mode / "task_01"
            shutil.copytree(paths[mode], run)
            for filename in ("task.json", "manifest.json"):
                value = json.loads((run / filename).read_text())
                value["run_name"] = run_name
                write_json(run / filename, value)
            asyncio.run(grade_run(run, rubric))
            recordings[trial, mode] = run
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, recordings, 2)
    output = tmp_path / "multi-report"
    assert compare_main(["--ledger", str(ledger), "--output", str(output)]) == 0
    summary = json.loads((output / "summary.json").read_text())
    assert summary["paired_tasks"] == 1 and summary["paired_attempts"] == 2
    assert summary["scheduled_attempts"] == 4
    assert summary["trial_ids"] == ["1", "2"]
    assert summary["modes"]["dom"]["pass_at_k"]["2"]["estimate"] == 1
    assert summary["unmatched_arms"] == []
    assert (output / "per_task.json").is_file()
    write_json_lines(ledger, rows[:-1])
    with pytest.raises(ValueError, match="omits a scheduled"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "missing-row")])
    write_json_lines(ledger, rows + rows[:1])
    with pytest.raises(ValueError, match="duplicate ledger"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "duplicate-row")])

@pytest.mark.usefixtures('no_network')
def test_ledger_keeps_missing_recording_and_ungraded_in_denominator(run_pair, tmp_path, capsys):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    write_attempt_ledger(ledger, {(1, "dom"): paths["dom"]}, 1)
    output = tmp_path / "unmatched-report"
    capsys.readouterr()
    assert compare_main(["--ledger", str(ledger), "--output", str(output)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["paired_attempts"] == 0 and printed["paired_tasks"] == 0
    summary = json.loads((output / "summary.json").read_text())
    assert summary["scheduled_attempts"] == 2
    assert summary["paired_attempts"] == 0
    assert summary["scheduled_pairs"] == 1
    assert summary["unmatched_arms"] == [{"task_id": "task_01", "trial": 1,
        "arm": "screenshot", "technical_outcome": "startup_failure"}]
    for mode in ("dom", "screenshot"):
        result = summary["modes"][mode]
        assert result["attempted_runs"] == 1
        assert result["completion_counts"] == {"ungraded": 1}
        assert result["success_rate_definitively_graded"] is None
        assert result["pass_at_k"]["1"]["confirmed_lower"] == 0
        assert result["pass_at_k"]["1"]["possible_upper"] == 1
    assert summary["modes"]["dom"]["actor_turns"] == 4
    assert summary["modes"]["screenshot"]["actor_turns"] == 0

@pytest.mark.usefixtures('no_network')
def test_partial_recording_keeps_known_cost_and_discloses_unknown_coverage(run_pair, tmp_path):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    (paths["dom"] / "final.json").unlink()
    rows[0]["technical_outcome"] = "interrupted"
    write_json_lines(ledger, rows)
    output = tmp_path / "partial-report"
    assert compare_main(["--ledger", str(ledger), "--output", str(output)]) == 0
    summary = json.loads((output / "summary.json").read_text())
    pairs = json.loads((output / "pairs.json").read_text())
    dom = pairs[0]["dom"]
    assert summary["scheduled_attempts"] == 2 and summary["paired_attempts"] == 0
    assert dom["run_status"] == "interrupted"
    assert dom["partial_recording"] is True
    assert dom["cost_coverage"] == "partial"
    assert dom["turns_complete"] is False
    assert dom["model_turns"] == 4
    assert dom["token_usage"]["input_tokens"] == 80
    assert dom["token_usage"]["output_tokens"] == 40
    assert dom["token_usage"]["total_tokens"] == 120
    assert dom["completion"]["verdict"] == "ungraded"
    result = summary["modes"]["dom"]
    assert result["attempted_runs"] == 1
    assert result["cost_coverage"] == {"partial": 1}
    assert result["tokens_complete"] is False and result["turns_complete"] is False
    assert result["mean_tokens_all_attempts"] is None
    assert result["mean_tokens_all_attempts_lower_bound"] == 120
    assert summary["technical_outcomes"]["interrupted"] == 1

@pytest.mark.usefixtures('no_network')
def test_batch_partial_recording_is_not_zero_cost_startup_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test"}) + "\n")
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    for raw in catalog.read_text().splitlines():
        row = json.loads(raw)
        write_json(rubrics / f"{row['task_id']}.json", {**row,
            "criteria": [{"id": "heading", "description": "Read the heading."}]})
    output = tmp_path / "recordings"
    def run(command, **kwargs):
        mode = command[command.index("--observation-mode") + 1]
        name = command[command.index("--run-name") + 1]
        root = Path(command[command.index("--output-dir") + 1])
        directory = root / name / mode / "custom"
        write_json(directory / "manifest.json", {"status": "running", "model_turns": 1})
        write_json_lines(directory / "decisions.jsonl", [{"model_turn": 1,
            "usage": {"input_tokens": 7, "output_tokens": 5}, "latency_seconds": 0.1}])
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(task_cli.subprocess, "run", run)
    assert task_cli.main(["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gemini-3.6-flash", "--output-dir", str(output),
        "--run-name", "partial", "--env-file", str(tmp_path / "absent.env"), "--model", "gemini-3.8-flash"]) == 0
    ledger = output / "partial" / "ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert all(row["completed"] and row["technical_outcome"] == "incomplete_recording" for row in rows)
    report = tmp_path / "partial-report"
    assert compare_main(["--ledger", str(ledger), "--output", str(report)]) == 0
    summary = json.loads((report / "summary.json").read_text())
    for mode in ("dom", "screenshot"):
        result = summary["modes"][mode]
        assert result["tokens"] == 12
        assert result["cost_coverage"] == {"partial": 1}
        assert result["tokens_complete"] is False
        assert result["turns_complete"] is False
        assert result["mean_tokens_all_attempts"] is None
        assert result["mean_tokens_all_attempts_lower_bound"] == 12

@pytest.mark.usefixtures('no_network')
def test_evaluation_join_checks_identity_and_keeps_four_directional_metrics(run_pair):
    paths, *_ = run_pair
    recording = inspect_recording(paths["dom"])
    task = recording["task"]
    root = run_directory(paths["dom"], area="evaluations") / "primary"
    metrics = {name: {"count": index, "denominator": 4, "rate": index/4} for index, name in enumerate((
        "screenshot_evidence_loss", "dom_model_evidence_loss", "screenshot_verifier_misses", "dom_model_verifier_misses"))}
    evaluation = {"recording_sha256": recording["recording_sha256"], "task_id": task["source_task_id"],
        "actor_arm": "dom", "trial_id": str(task["run_name"]), "rubric_sha256": "frozen",
        "coverage": {"audit_eligible_states": [1]}, "stages": {"audit": {"status": "complete", "metrics": metrics,
        "calls": [{"stage": "inventory", "requested_model": "gemini-4-argon", "usage": {"prompt_tokens": 11, "completion_tokens": 7,
            "completion_tokens_details": {"reasoning_tokens": 5}}}]}}}
    root.mkdir(parents=True)
    write_json(root / "evaluation.json", evaluation)
    result = summarize(recording)
    assert result["evidence_audit"] == metrics
    assert result["judge_usage_streams"]["audit:inventory"]["usage"]["total_tokens"] == 18
    assert result["judge_usage_streams"]["audit:inventory"]["usage"]["reasoning_tokens"] == 5
    assert result["judge_usage_streams"]["audit:adjudication"]["usage"]["input_tokens"] is None
    evaluation["trial_id"] = "another-trial"
    write_json(root / "evaluation.json", evaluation)
    with pytest.raises(ValueError, match="task, arm, trial"):
        summarize(recording)

@pytest.mark.usefixtures('no_network')
def test_aggregate_distributions_categories_and_missing_audit_coverage(run_pair):
    import copy
    paths, *_ = run_pair
    pair, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    pair.update(task_id="medium_task", trial_id="1", difficulty="medium")
    other = copy.deepcopy(pair)
    other.update(task_id="hard_task", difficulty="hard")
    other["dom"]["token_usage"]["input_tokens"] = 120
    other["dom"]["token_usage"]["total_tokens"] = 160
    other["dom"]["tokens_per_turn"]["input_tokens"].update(tokens=120, known_usage_mean=30, mean=30)
    pair["dom"]["arm_token_usage"] = {
        "policy": "actor-plus-matching-verifier/v1", "matching_verifier": "dom_model",
        "actor_usage": {"input_tokens": 80, "output_tokens": 40, "total_tokens": 120},
        "matching_verifier_usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
        "usage": {"input_tokens": 90, "output_tokens": 44, "total_tokens": 134},
        "known_usage_lower_bound": {"input_tokens": 90, "output_tokens": 44, "total_tokens": 134},
        "coverage": "complete", "matching_verifier_status": "complete",
        "included_streams": ["actor", "dom_model"], "excluded_judge_streams": ["screenshot_verifier"]}
    other["dom"]["arm_token_usage"] = {
        **copy.deepcopy(pair["dom"]["arm_token_usage"]),
        "actor_usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
        "matching_verifier_usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
        "usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
        "known_usage_lower_bound": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
        "coverage": "partial", "matching_verifier_status": "running"}
    pair["dom"]["judge_usage_streams"]["screenshot_verifier"] = {
        "calls": 1, "usage": {"input_tokens": 9000, "output_tokens": 1000, "total_tokens": 10000},
        "usage_coverage": "complete"}
    pair["dom"]["evidence_audit"] = {"screenshot_evidence_loss": {"count": 1, "denominator": 4, "rate": .25}}
    pair["dom"]["evidence_audit_status"] = "complete"
    result = aggregate([pair, other])
    assert result["modes"]["dom"]["tokens_per_turn"]["input_tokens"]["known_usage_mean"] == 25
    assert result["modes"]["dom"]["distributions"]["input_tokens"]["mean"] == 100
    assert result["modes"]["dom"]["distributions"]["input_tokens"]["median"] == 100
    assert result["categories"]["medium"]["dom"]["attempted_runs"] == 1
    assert result["categories"]["hard"]["dom"]["attempted_runs"] == 1
    assert result["modes"]["dom"]["evidence_audit"]["screenshot_evidence_loss"] == {
        "count": 1, "denominator": 4, "rate": .25, "audited_runs": 1, "attempted_runs": 2}
    assert result["modes"]["screenshot"]["evidence_audit"]["screenshot_evidence_loss"]["rate"] is None
    assert len(result["audit_by_task_trial"]) == 2
    arm = result["modes"]["dom"]["arm_token_usage"]
    assert arm["usage"] == {"input_tokens": None, "output_tokens": None, "total_tokens": None}
    assert arm["known_usage_lower_bound"] == {"input_tokens": 210, "output_tokens": 84, "total_tokens": 294}
    assert arm["actor_usage"]["total_tokens"] == 280 and arm["matching_verifier_usage"]["total_tokens"] == 14
    assert arm["complete_runs"] == 1 and arm["coverage"] == "partial"
    assert arm["distributions"]["total_tokens"] == {
        "known_runs": 1, "attempted_runs": 2, "mean": 134, "median": 134, "min": 134, "max": 134, "values": [134]}
    assert result["categories"]["medium"]["dom"]["arm_token_usage"]["usage"]["total_tokens"] == 134
    assert result["categories"]["hard"]["dom"]["arm_token_usage"]["usage"]["total_tokens"] is None
    assert result["per_task"]["medium_task"]["dom"]["arm_token_usage"]["usage"]["total_tokens"] == 134
    assert result["per_task"]["hard_task"]["dom"]["arm_token_usage"]["known_usage_lower_bound"]["total_tokens"] == 160
    assert result["modes"]["screenshot"]["arm_token_usage"]["matching_verifier_usage"]["total_tokens"] is None
    assert result["modes"]["dom"]["judge_usage_streams"]["screenshot_verifier"]["usage"]["total_tokens"] == 10000

@pytest.mark.usefixtures("no_network")
def test_difficulty_groups_keep_easy_separate_from_unknown(run_pair):
    paths, *_ = run_pair
    pair, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    pairs = []
    for difficulty in ("easy", "medium", "hard", "complex", "unclassified"):
        item = deepcopy(pair)
        item.update(task_id=f"{difficulty}_task", trial_id="1", difficulty=difficulty)
        pairs.append(item)
    result = aggregate(pairs)
    assert set(result["categories"]) == {"easy", "medium", "hard", "complex", "unknown"}
    for difficulty in ("easy", "medium", "hard", "complex", "unknown"):
        for arm in ("dom", "screenshot"):
            assert result["categories"][difficulty][arm]["attempted_runs"] == 1
    assert result["task_metadata"]["easy_task"]["difficulty"] == "easy"


@pytest.mark.parametrize("k", [1, 2, 5])
def test_k_runs_means_are_not_majority_votes(tmp_path, k):
    roots = runs(tmp_path, k=k, flagged={(0, 0, 0, audit_aggregate.LOSS_FLAGS[0])})
    value, categories = audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=200)
    assert value["k"] == k
    assert value["criteria_per_run"] == 4
    assert value["mean"][audit_aggregate.LOSS_FLAGS[0]]["count"] == pytest.approx(1 / k)
    assert value["mean"][audit_aggregate.LOSS_FLAGS[0]]["rate"] == pytest.approx(1 / (4 * k))
    assert value["relative_reduction"] == 1
    assert len(categories) == 1
    assert value["confidence_intervals"]["method"] == "paired_task_then_run_percentile_bootstrap"
    subset, subset_categories = audit_aggregate.aggregate_runs(
        roots, expected_tasks=2, resamples=100, excluded_tasks=("task_01",))
    assert subset["tasks_per_run"] == 1 and subset["criteria_per_run"] == 2
    assert subset["mean"][audit_aggregate.LOSS_FLAGS[0]]["count"] == 0
    assert subset_categories == []
    with pytest.raises(ValueError, match="unknown catalog"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, excluded_tasks=("task_03",))

@pytest.mark.parametrize("field", ["frozen_rubric_sha256", "prompt_version", "criterion"])
def test_mismatched_protocol_or_rubric_rejected(tmp_path, field):
    roots = runs(tmp_path, k=2)
    path = roots[1] / "task_01/evidence_audit.json"
    value = json.loads(path.read_text())
    if field == "criterion":
        value["criteria"][0][field] = "Different criterion"
    else:
        value[field] = "a" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="mismatch|differ"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)

def test_task_set_mismatch_and_duplicates_rejected(tmp_path):
    roots = runs(tmp_path, k=2, flagged={(0, 1, 0, audit_aggregate.LOSS_FLAGS[0])})
    with pytest.raises(ValueError, match="distinct"):
        audit_aggregate.aggregate_runs([roots[0], roots[0]], expected_tasks=2)
    with pytest.raises(FileNotFoundError):
        audit_aggregate.aggregate_runs([roots[0], tmp_path / "other" / roots[0].name], expected_tasks=2)
    (roots[1] / "task_02/evidence_audit.json").unlink()
    with pytest.raises(ValueError, match="Expected 2"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2)
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    reference = {f"task_{number:02d}": json.loads(
        (roots[0] / f"task_{number:02d}/evidence_audit.json").read_text())["frozen_rubric_sha256"]
        for number in (1, 2)}
    for index, root in enumerate(roots):
        entries = [{"task_alias": alias, "frozen_rubric_sha256": digest,
                    "evaluation_status": "not_scored" if index == 1 and alias == "task_02" else "complete",
                    "captured_states": 0 if index == 1 and alias == "task_02" else 1,
                    "audit": None if index == 1 and alias == "task_02" else
                             f"evaluations/{root.name}/{alias}/evidence_audit.json",
                    "unscored_reason": "no_captured_state" if index == 1 and alias == "task_02" else None}
                   for alias, digest in reference.items()]
        (manifests / f"{root.name}.json").write_text(json.dumps({"run_name": root.name, "entries": entries}))
    value, categories = audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    assert value["catalog_tasks"] == 2 and value["tasks_per_run"] == 1
    assert value["criteria_per_run"] == 2
    assert value["coverage"]["outside_common_panel"] == ["task_02"]
    assert [run["available_tasks"] for run in value["per_run"]] == [2, 1]
    assert value["per_run"][0]["available_metrics"][audit_aggregate.LOSS_FLAGS[0]]["count"] == 1
    assert value["mean"][audit_aggregate.LOSS_FLAGS[0]]["count"] == 0 and categories == []
    assert "Available audited tasks" in audit_aggregate.render_table(value)
    path = manifests / f"{roots[1].name}.json"
    manifest = json.loads(path.read_text())
    manifest["entries"][1]["frozen_rubric_sha256"] = "a" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="hashes differ"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    manifest["entries"][1]["frozen_rubric_sha256"] = reference["task_02"]
    manifest["entries"][1]["unscored_reason"] = None
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unexplained missing"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)

def test_paired_hierarchical_intervals_are_seeded_and_keep_sides_together():
    clusters = [[(5, 2, 1), (5, 0, 0)], [(5, 4, 2), (5, 2, 1)]]
    first = audit_aggregate.hierarchical_intervals(clusters, resamples=1000, seed=1)
    assert first == audit_aggregate.hierarchical_intervals(clusters, resamples=1000, seed=1)
    assert first["relative_reduction"] == [0.5, 0.5]
    assert first["statuses"]["relative_reduction"] == "degenerate"
    assert first["undefined_relative_reduction_resamples"] > 0
    zero = audit_aggregate.hierarchical_intervals([[(3, 0, 0)]], resamples=100)
    assert zero["relative_reduction"] is None
    assert zero["undefined_relative_reduction_resamples"] == 0
    assert zero["statuses"]["relative_reduction"] == "insufficient_tasks"
    assert zero["performed_resamples"] == 0

def test_recording_provenance_and_returned_models_are_checked(tmp_path):
    roots = runs(tmp_path, k=2)
    original_path = roots[0] / "task_01/evidence_audit.json"
    path = roots[1] / "task_01/evidence_audit.json"
    original = json.loads(original_path.read_text())
    value = json.loads(path.read_text())
    value["input_fingerprints"] = original["input_fingerprints"]
    value["shared_trajectory"] = original["shared_trajectory"]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="distinct recording provenance"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    for index, root in enumerate(roots[:2], 1):
        recording = tmp_path / "recordings" / root.name / "task_01"
        recording.mkdir(parents=True, exist_ok=True)
        existing = json.loads((recording / "manifest.json").read_text())
        write_json(recording / "manifest.json", {**existing,
            "task_id": "task_01", "started_at": f"2026-01-0{index}T00:00:00Z"})
    audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    value["calls"][0]["response_model"] = "different-returned-model"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Returned model versions differ"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    value["calls"][0]["response_model"] = original["calls"][0]["response_model"]
    path.write_text(json.dumps(value))
    first = tmp_path / "recordings" / roots[0].name / "task_01/manifest.json"
    second = tmp_path / "recordings" / roots[1].name / "task_01/manifest.json"
    second.write_bytes(first.read_bytes())
    with pytest.raises(ValueError, match="Recording identity reused"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)

def test_run_manifest_selects_the_audit_batch(tmp_path):
    roots = runs(tmp_path, k=2)
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    for root in roots:
        entries = []
        for alias in ("task_01", "task_02"):
            path = root / alias / "evidence_audit.json"
            value = json.loads(path.read_text())
            entries.append({"task_alias": alias, "evaluation_status": "complete",
                            "frozen_rubric_sha256": value["frozen_rubric_sha256"],
                            "audit": path.relative_to(tmp_path).as_posix()})
        (manifests / f"{root.name}.json").write_text(json.dumps(
            {"run_name": root.name, "entries": entries}))
    duplicate = roots[0] / "task_01/batch_02/evidence_audit.json"
    duplicate.parent.mkdir()
    duplicate.write_bytes((roots[0] / "task_01/evidence_audit.json").read_bytes())
    result, _ = audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    assert result["tasks_per_run"] == 2
    (manifests / f"{roots[0].name}.json").unlink()
    with pytest.raises(ValueError, match="duplicate task alias"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)

@pytest.mark.parametrize("field", ["input_fingerprints", "calls"])
def test_missing_source_or_model_provenance_is_rejected(tmp_path, field):
    roots = runs(tmp_path, k=2)
    path = roots[0] / "task_01/evidence_audit.json"
    value = json.loads(path.read_text())
    value.pop(field)
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="fingerprints missing|returned-model provenance"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)

def test_outputs_and_figures_are_written_without_model_calls(tmp_path):
    roots = runs(tmp_path, k=2, flagged={(0, 0, 0, audit_aggregate.LOSS_FLAGS[0])})
    output, figures = tmp_path / "out", tmp_path / "figures"
    recordings = tmp_path / "recordings"
    for index, root in enumerate(roots, 1):
        for alias in ("task_01", "task_02"):
            state = recordings / root.name / alias / "steps/step_001"
            state.mkdir(parents=True)
            (state.parent.parent / "task.json").write_text("{}")
            write_json(state.parent.parent / "manifest.json", {"status": "success", "browser_profile_provenance": {
                "profile_fresh_at_run_start": True, "freshly_recreated_by_launcher": True,
                "launch_mode": "fresh", "tasks_previously_run_in_container": 0,
                "browser_environment": {"CHROMIUM_RESET_PROFILE": "1"}}})
            for name in ("screenshot.png", "dom_model.txt", "dom_full.txt", "dom.json"):
                (state / name).write_bytes(b"x" * index)
    readme = tmp_path / "README.md"
    readme.write_text("Keep intro\n<!-- recorded-runs:start -->\nold\n<!-- recorded-runs:end -->\nKeep rest\n")
    assert audit_aggregate.main([*map(str, roots), "--expected-tasks", "2", "--resamples", "100",
                           "--output-dir", str(output), "--figures-dir", str(figures),
                           "--recordings-root", str(recordings),
                           "--exploratory-exclusions", "task_01",
                           "--readme", str(readme)]) == 0
    result = json.loads((output / "summary.json").read_text())
    assert result["k"] == 2
    assert result["unclassified_losses"] == 1
    assert result["exploratory_subset"]["pre_specified"] is False
    assert result["exploratory_subset"]["criteria_per_run"] == 2
    assert result["recorded_file_sizes"]["recordings"] == 4
    assert all(value == {"success": 2} for value in result["recorded_outcomes"].values())
    sizes = result["recorded_file_sizes"]["pooled"]["dom_model.txt"]
    assert sizes == {"files": 4, "bytes": 6, "mean_kib": 1.5 / 1024, "mean_kb": 1.5 / 1000}
    assert readme.read_text().startswith("Keep intro") and readme.read_text().endswith("Keep rest\n")
    with (output / "evidence_categories.tsv").open() as stream:
        assert len(list(csv.DictReader(stream, delimiter="\t"))) == 1
    assert b"\r\n" not in (output / "evidence_categories.tsv").read_bytes()
    assert (figures / "evidence-loss-rates.svg").is_file()
    for svg in figures.glob("*.svg"):
        assert svg.with_suffix(".png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

def test_generic_task_names_and_current_trial_arm_receipts(tmp_path):
    import hashlib
    original = runs(tmp_path, k=2)
    selected = []
    for trial, source in enumerate(original, 1):
        root = tmp_path / "current" / f"trial_{trial:04d}" / "dom"
        selected.append(root)
        for old_alias, alias in (("task_01", "news-medium-a"), ("task_02", "catalog_x")):
            value = json.loads((source / old_alias / "evidence_audit.json").read_text())
            value["task_alias"] = value["task_id"] = alias
            recording = hashlib.sha256(f"{trial}:{alias}".encode()).hexdigest()
            value["shared_trajectory"].update(task_id=alias, evaluation_context={
                "actor_arm": "dom", "trial_id": f"trial_{trial:04d}", "task_id": alias, "recording_sha256": recording})
            value["input_fingerprints"]["shared_trajectory"] = audit_aggregate.canonical_sha256(value["shared_trajectory"])
            folder = root / alias / recording
            folder.mkdir(parents=True)
            path = folder / "evidence_audit.json"
            path.write_text(json.dumps(value))
            (folder / "evaluation.json").write_text(json.dumps({"trial_id": f"trial_{trial:04d}", "actor_arm": "dom",
                "task_id": alias, "rubric_sha256": value["frozen_rubric_sha256"], "recording_sha256": recording,
                "coverage": {"states": [{"state": 1}]}, "stages": {"audit": {"status": "complete",
                    "result_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}}))
    summary, _ = audit_aggregate.aggregate_runs(selected, expected_tasks=2, resamples=100, allow_nonfresh=True)
    assert summary["k"] == 2 and summary["actor_arm"] == "dom"
    assert summary["run_names"] == ["trial_0001", "trial_0002"]
    assert summary["coverage"]["compared_tasks"] == ["catalog_x", "news-medium-a"]
    # A declared ungraded task remains visible without being a zero-loss audit.
    path = next(selected[1].rglob("news-medium-a/*/evaluation.json"))
    value = json.loads(path.read_text())
    value["stages"]["audit"] = {"status": "not_eligible", "reason": "no_eligible_paired_states"}
    path.write_text(json.dumps(value)); (path.parent / "evidence_audit.json").unlink()
    summary, _ = audit_aggregate.aggregate_runs(selected, expected_tasks=2, resamples=100, allow_nonfresh=True)
    assert summary["tasks_per_run"] == 1
    assert summary["coverage"]["unscored_tasks"]["trial_0002"] == {"news-medium-a": "no_eligible_paired_states"}
    # Different actor policies may not be pooled into the same within-run audit mean.
    for path in selected[1].rglob("evaluation.json"):
        value = json.loads(path.read_text()); value["actor_arm"] = "screenshot"; path.write_text(json.dumps(value))
        audit_path = path.parent / "evidence_audit.json"
        if audit_path.is_file():
            value = json.loads(audit_path.read_text()); value["shared_trajectory"]["evaluation_context"]["actor_arm"] = "screenshot"
            value["input_fingerprints"]["shared_trajectory"] = audit_aggregate.canonical_sha256(value["shared_trajectory"])
            audit_path.write_text(json.dumps(value))
            evaluation = json.loads(path.read_text()); evaluation["stages"]["audit"]["result_sha256"] = hashlib.sha256(audit_path.read_bytes()).hexdigest(); path.write_text(json.dumps(evaluation))
    with pytest.raises(ValueError, match="different actor arms"):
        audit_aggregate.aggregate_runs(selected, expected_tasks=2, resamples=100, allow_nonfresh=True)

@pytest.mark.parametrize("verdicts,bounds", [
    (("success",), [(1, 1)]),
    (("failure",), [(0, 0)]),
    (("ungraded",), [(0, 1)]),
    (("success", "failure", "failure"), [(1 / 3, 1 / 3), (2 / 3, 2 / 3), (1, 1)]),
    (("uncertain", "failure", "failure"), [(0, 1 / 3), (0, 2 / 3), (0, 1)]),
    (("success", "uncertain", "failure"), [(1 / 3, 2 / 3), (2 / 3, 1), (1, 1)]),
    (("uncertain", "ungraded", "failure"), [(0, 2 / 3), (0, 1), (0, 1)]),
])
def test_actor_pass_at_k_preserves_task_and_criterion_bounds(verdicts, bounds):
    from w8bench.verifier.paired_metrics import aggregate as aggregate_actor_trials

    pairs = [_actor_trial_pair(trial, verdict) for trial, verdict in enumerate(verdicts, 1)]
    result = aggregate_actor_trials(pairs)
    assert result["evaluated_k"] == list(range(1, len(verdicts) + 1))
    for mode in ("dom", "screenshot"):
        task = result["per_task"]["task"][mode]
        for k, (lower, upper) in enumerate(bounds, 1):
            expected = {"confirmed_lower": pytest.approx(lower), "possible_upper": pytest.approx(upper),
                "estimate": pytest.approx(lower) if lower == upper else None}
            assert task["pass_at_k"][str(k)] == expected
            if any(verdict != "ungraded" for verdict in verdicts):
                assert task["criteria"]["done"]["pass_at_k"][str(k)] == expected
            else:
                assert task["criteria"] == {}
            assert result["modes"][mode]["pass_at_k"][str(k)] == {**expected, "tasks": 1}

@pytest.mark.parametrize("path,value", [
    (("actor", "memory_max_chars"), 7999),
    (("stages", "completion", "max_output_tokens"), 9999),
    (("stages", "dom_model", "reasoning_effort"), "high"),
    (("stages", "inventory", "prompt_sha256"), "another-prompt"),
    (("browser_source", "protocol_sha256"), "another-protocol"),
    (("rubric_sha256",), "another-rubric"),
])
def test_every_scheduled_contract_is_checked_even_without_recordings(settings_comparison_case, path, value):
    case = settings_comparison_case
    for row in case.rows:
        row.update(technical_outcome="startup_failure", recording=str(Path(row["recording"]).parent / "absent"))
    target = case.rows[1]["effective_settings"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="effective settings differ"):
        compare_case(case)

def test_schedule_refuses_mixed_settings_versions_for_startup_placeholders(settings_comparison_case):
    case = settings_comparison_case
    for row in case.rows:
        row.update(technical_outcome="startup_failure", recording=str(Path(row["recording"]).parent / "absent"))
    case.rows[1].pop("effective_settings")
    with pytest.raises(ValueError, match="effective settings differ|missing.*settings"):
        compare_case(case)

def test_deployment_names_credentials_paths_and_endpoint_ports_do_not_change_settings(settings_comparison_case):
    case = settings_comparison_case
    row = case.rows[1]
    row["configuration"].update(image="another-tag", api_key="fictional-new-key", base_url="https://user:secret@actor.example:9000/v1")
    row["effective_settings"]["actor"]["base_url"] = row["configuration"]["base_url"]
    row["effective_settings"]["stages"]["dom_model"].update(base_url="https://judge.example:9010/v1",
        config_file="/another/config.json", api_key="fictional-key", container_name="another-container")
    recording = case.recordings[row["recording"]]
    recording["manifest"]["controls"]["base_url"] = "https://actor.example:9001/v1"
    recording["manifest"]["browser_profile_provenance"]["browser_environment"].update(CDP_PORT="9333", CHROMIUM_CDP_PORT="9334")
    assert compare_case(case) == 0

@pytest.mark.parametrize("kind", ["actor", "evaluation", "missing_actor", "missing_evaluation", "actual_browser"])
def test_recorded_contracts_and_actual_browser_labels_match_the_schedule(settings_comparison_case, kind):
    case = settings_comparison_case
    recording = case.recordings[case.rows[1]["recording"]]
    if kind == "actor":
        recording["manifest"]["effective_settings"]["memory_max_chars"] = 7999
    elif kind == "missing_actor":
        recording["manifest"].pop("effective_settings")
    elif kind == "actual_browser":
        recording["manifest"]["browser_profile_provenance"]["browser_build"]["overlay_revision"] = "another-overlay"
    else:
        source = Path(recording["source"])
        path = run_directory(source, area="evaluations") / "primary" / "evaluation.json"
        value = json.loads(path.read_text())
        if kind == "missing_evaluation":
            value.pop("effective_settings")
        else:
            value["effective_settings"]["stages"]["dom_model"]["reasoning_effort"] = "high"
        write_json(path, value)
    with pytest.raises(ValueError, match="effective settings differ"):
        compare_case(case)

def test_no_receipt_rows_retain_the_scheduled_contract_and_denominator(settings_comparison_case):
    case = settings_comparison_case
    for row in case.rows:
        row.update(technical_outcome="startup_failure", recording=str(Path(row["recording"]).parent / "absent"))
    assert compare_case(case) == 0
    pair = json.loads((case.output / "pairs.json").read_text())[0]
    for arm in ("dom", "screenshot"):
        assert pair[arm]["scheduled_effective_settings"] == case.contract
        assert pair[arm]["actor_effective_settings"] is None
    summary = json.loads((case.output / "summary.json").read_text())
    assert summary["scheduled_attempts"] == 2

@pytest.mark.parametrize("kind", ["actor", "evaluation"])
def test_aggregation_refuses_new_and_unversioned_actual_contracts(settings_comparison_case, kind):
    case = settings_comparison_case
    for row in case.rows:
        row.pop("effective_settings")
    recording = case.recordings[case.rows[1]["recording"]]
    if kind == "actor":
        recording["manifest"].pop("effective_settings")
    else:
        source = Path(recording["source"])
        path = run_directory(source, area="evaluations") / "primary" / "evaluation.json"
        value = json.loads(path.read_text()); value.pop("effective_settings"); write_json(path, value)
    with pytest.raises(ValueError, match="effective settings differ"):
        compare_case(case)

def test_all_unversioned_synthetic_contracts_still_aggregate(settings_comparison_case):
    case = settings_comparison_case
    for row in case.rows:
        row.pop("effective_settings")
        recording = case.recordings[row["recording"]]
        recording["manifest"].pop("effective_settings")
        source = Path(recording["source"])
        path = run_directory(source, area="evaluations") / "primary" / "evaluation.json"
        value = json.loads(path.read_text()); value.pop("effective_settings"); write_json(path, value)
    assert compare_case(case) == 0

def test_direct_trial_aggregation_checks_effective_fields(settings_comparison_case):
    case = settings_comparison_case
    summaries = {row["arm"]: summarize(case.recordings[row["recording"]]) for row in case.rows}
    summaries["screenshot"]["actor_effective_settings"]["memory_max_chars"] = 7999
    with pytest.raises(ValueError, match="effective settings differ"):
        aggregate([{"task_id": "custom", "trial_id": "trial_0001", "shared_controls": {},
                    "both_successful": False, "successful_pair_turn_delta": None, **summaries}])

def test_different_tasks_can_have_distinct_rubrics_with_shared_policies(settings_comparison_case):
    case = settings_comparison_case
    summaries = {row["arm"]: summarize(case.recordings[row["recording"]]) for row in case.rows}
    first = {"task_id": "custom", "trial_id": "trial_0001", "shared_controls": {},
             "both_successful": False, "successful_pair_turn_delta": None, **summaries}
    other = deepcopy(first); other["task_id"] = "another-task"
    for arm in ("dom", "screenshot"):
        other[arm]["evaluation_effective_settings"]["rubric_sha256"] = "rubric-another-task"
        other[arm]["evaluation"]["rubric_sha256"] = "rubric-another-task"
    assert aggregate([first, other])["paired_tasks"] == 2

def test_identical_actual_browser_labels_still_match_the_declared_source_pin(settings_comparison_case):
    case = settings_comparison_case
    for recording in case.recordings.values():
        recording["manifest"]["browser_profile_provenance"]["browser_build"]["overlay_revision"] = "another-overlay"
    with pytest.raises(ValueError, match="effective settings differ"):
        compare_case(case)

@pytest.mark.parametrize("change", ["stage", "missing", "rubric", "browser_source", "deployment_only", None])
def test_audit_aggregation_compares_effective_stage_contracts(tmp_path, change):
    from w8bench.verifier.aggregate_runs import aggregate_runs

    roots = runs(tmp_path, k=2)
    for root in roots:
        for path in root.rglob("evidence_audit.json"):
            value = json.loads(path.read_text())
            value["effective_settings"] = {
                "schema_version": "effective-settings/v1", "rubric_sha256": value["frozen_rubric_sha256"],
                "browser_source": {"overlay_revision": "overlay-one"},
                "stages": {"inventory": {"model": "gemini-3.1-pro-preview", "prompt_sha256": "prompt-one", "base_url": "https://judge.example:443/v1"},
                           "adjudication": {"model": "gemini-4-argon", "max_output_tokens": None}},
            }
            write_json(path, value)
    selected = roots[1] / "task_01" / "evidence_audit.json"
    value = json.loads(selected.read_text())
    if change == "stage":
        value["effective_settings"]["stages"]["inventory"]["prompt_sha256"] = "another-prompt"
    elif change == "missing":
        value.pop("effective_settings")
    elif change == "rubric":
        value["effective_settings"]["rubric_sha256"] = "another-rubric"
    elif change == "browser_source":
        value["effective_settings"]["browser_source"]["overlay_revision"] = "another-overlay"
    elif change == "deployment_only":
        value["effective_settings"]["stages"]["inventory"].update(base_url="https://user:secret@judge.example:9011/v1",
            api_key="fictional-key", config_file="/another/config.json")
    write_json(selected, value)
    if change in {"stage", "missing", "rubric", "browser_source"}:
        with pytest.raises(ValueError, match="effective settings differ"):
            aggregate_runs(roots, expected_tasks=2, resamples=10)
    else:
        assert aggregate_runs(roots, expected_tasks=2, resamples=10)[0]["k"] == 2

@pytest.mark.usefixtures('no_network')
def test_technical_rerun_cost_does_not_inflate_final_actor_turns(metric_recording_factory, monkeypatch):
    from w8bench.verifier import run_full_comparison as full
    first = metric_recording_factory(usage={'input_tokens': 100, 'output_tokens': 50})
    final = metric_recording_factory(usage={'input_tokens': 20, 'output_tokens': 10})
    final['task']['instruction'] = first['task']['instruction'] = 'Read heading.'
    final['task']['start_url'] = first['task']['start_url'] = 'https://example.test'
    first['manifest'].update(status='technical_failure', run_name='trial_0001')
    first['final'].update(run_status='technical_failure', technical_failure_class='browser_crash')
    for item in (first, final):
        item['manifest']['controls']['max_output_tokens'] = 10000
        item['task']['catalog_sha256'] = None
    monkeypatch.setattr(full, 'inspect_recording', lambda path: first)
    row = {'task_id': 'custom', 'task': final['task'], 'arm': 'dom', 'trial': 1,
        'run_name': 'trial_0001', 'recording': final['source'], 'technical_outcome': 'completed',
        'configuration': final['manifest']['controls'], 'attempts': [
            {'attempt_number': 1, 'recording': first['source'], 'technical_outcome': 'technical_failure',
             'technical_failure_class': 'browser_crash', 'completed': True},
            {'attempt_number': 2, 'recording': final['source'], 'technical_outcome': 'completed', 'completed': True}]}
    write_json(Path(first['source']) / 'final.json', first['final'])
    write_json(Path(first['source']) / 'manifest.json', first['manifest'])
    write_json(Path(first['source']) / 'task.json', first['task'])
    receipt, _, _ = full._pair_attempt({'dom': row, 'screenshot': {
        **row, 'arm': 'screenshot', 'recording': '/missing/ss', 'attempts': [], 'task': final['task']}},
        {'dom': final, 'screenshot': None}, 'custom', 1)
    assert receipt['dom']['model_turns'] == 1
    assert receipt['dom']['token_usage']['input_tokens'] == 20
    technical = receipt['dom']['cost_streams']['technical_attempts:actor']
    assert technical['usage']['input_tokens'] == 100
    assert technical['calls'] == 1
    assert technical['cost']['estimated_usd'] is not None


@pytest.mark.usefixtures('no_network')
def test_terminal_technical_grade_is_not_an_actor_failure():
    pair = _actor_trial_pair(1, 'failure')
    pair['dom'].update(technical_failure=True, technical_failure_class='cdp_stall')
    result = aggregate([pair])
    assert result['modes']['dom']['technical_failures'] == 1
    assert result['modes']['dom']['agent_failure_runs'] == 0
    assert result['modes']['dom']['agent_eligible_runs'] == 0

@pytest.mark.usefixtures('no_network')
def test_partial_failed_transport_has_no_model_turn_but_unknown_cost(tmp_path):
    from w8bench.verifier.run_full_comparison import _partial_summary
    source = tmp_path / 'trial_0001' / 'dom' / 'custom'
    write_json(source / 'manifest.json', {'turn_policy': 'actor-response-turn/v2',
        'model_turns': 0, 'states': [], 'steps': [], 'controls': {'max_turns': 200}})
    write_json(source / 'turns' / 'turn_000001' / 'request.json', {'api_call_started': True})
    write_json(source / 'turns' / 'turn_000001' / 'metadata.json', {'transport_attempts': [
        {'attempt': i, 'response_received': False, 'usage': None, 'status': 'transport_error'}
        for i in (1, 2, 3)]})
    summary = _partial_summary({'recording': str(source), 'task': {'instruction': 'Read heading.'},
        'configuration': {'model': 'gemini-3.1-pro-preview'}, 'run_name': 'trial_0001',
        'technical_outcome': 'technical_failure'}, 'dom', 'custom')
    assert summary['model_turns'] == 0
    assert summary['turns_missing_usage'] == 0
    assert summary['turns_complete'] is True
    assert summary['cost_streams']['actor']['cost']['estimated_usd'] is None
    assert summary['actor_transport_attempts'] == 3


def test_audit_aggregation_requires_explicit_nonfresh_override(tmp_path):
    roots = runs(tmp_path, k=1)
    source = tmp_path / "recordings" / roots[0].name / "task_01" / "manifest.json"
    manifest = json.loads(source.read_text())
    manifest["browser_profile_provenance"].update(profile_fresh_at_run_start=False,
        freshly_recreated_by_launcher=False, launch_mode="raw")
    write_json(source, manifest)
    with pytest.raises(ValueError, match="freshness"):
        audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=10)
    summary, _ = audit_aggregate.aggregate_runs(roots, expected_tasks=2, resamples=10, allow_nonfresh=True)
    assert summary["browser_profile_policy"] == {"allow_nonfresh": True,
        "override_used": True, "nonfresh_recordings": 1}


def test_evidence_aggregation_refuses_mixed_native_judge_profiles(tmp_path):
    roots=runs(tmp_path,k=2)
    for root,profile,model in zip(roots,('primary','pro'),('gemini-3.5-flash-lite','gemini-3.1-pro-preview')):
        for path in root.rglob('evidence_audit.json'):
            value=json.loads(path.read_text())
            value['native_verifier_profiles']={mode:{'profile':profile,'configured_models':[model,model]}
                for mode in ('dom_model','screenshot_verifier')}
            path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='protocol|settings|configuration'):
        audit_aggregate.aggregate_runs(roots,expected_tasks=2,resamples=20)
