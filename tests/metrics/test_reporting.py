"""Bound result normalization and reporting diagnostics."""

import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tests.conftest import write_attempt_ledger
from w8bench.run_paths import resolve_run_name, run_directory
from w8bench.task_recorder import runner, task_cli
from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.task_recorder.recorder_support import write_json, write_json_lines
from w8bench.verifier.common import canonical_sha256
from w8bench.verifier.compare_results import compare
from w8bench.verifier.completion import grade_run
from w8bench.verifier.normalize_results import normalize_dom_model, normalize_screenshot
from w8bench.verifier.paired_metrics import aggregate
from w8bench.verifier.run_full_comparison import main as compare_main
from w8bench.verifier.run_metrics import summarize


def completion_for(recording, **overrides):
    return {
        "recording_sha256": recording["recording_sha256"],
        "task_id": recording["task"]["source_task_id"],
        "observation_mode": recording["task"]["observation_mode"],
        "rubric_sha256": "frozen-rubric",
        "evidence_policy": "paired",
        "method": "model_judge",
        "verdict": "success",
        "judge_model": "gpt-6.1-sol",
        "returned_judge_model": "gpt-6.1-sol",
        "judge_calls": 1,
        "criteria": [{"id": "title", "verdict": "success"}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
        **overrides,
    }

def evaluation_for(recording, **overrides):
    return {
        "recording_sha256": recording["recording_sha256"],
        "task_id": recording["task"]["source_task_id"],
        "actor_arm": recording["task"]["observation_mode"],
        "trial_id": recording["task"]["run_name"],
        "rubric_sha256": "frozen-rubric",
        "stages": {},
        **overrides,
    }

def evaluation_path(recording):
    source = Path(recording["source"])
    task = recording["task"]
    return (source.parent.parent / "evaluations" / task["run_name"] / task["observation_mode"]
            / task["source_task_id"] / recording["recording_sha256"] / "evaluation.json")

def pair_for(recording):
    row = summarize(recording)
    return {"task_id": recording["task"]["source_task_id"], "trial_id": recording["task"]["run_name"],
            "shared_controls": {"model": "gemini-3.1-pro-preview"},
            "dom": deepcopy(row), "screenshot": deepcopy(row), "both_successful": False,
            "successful_pair_turn_delta": None}

@pytest.mark.usefixtures('no_network')
def test_shared_controls_must_match_and_cli_passes_mode(run_pair, tmp_path):
    paths, *_ = run_pair
    dom, ss = [inspect_recording(paths[m]) for m in ("dom", "screenshot")]
    ss["manifest"]["controls"]["max_turns"] += 1
    with pytest.raises(ValueError, match="shared controls"):
        compare(dom, ss)
    command = task_cli.build_runner_command({"instruction": "Report done.", "start_url": "https://example.test"},
        task_id="task_01", task_name="fixture", run_id="task_01", output_dir=tmp_path,
        env_file=tmp_path / "absent.env",
        observation_mode="screenshot", max_steps=4)
    args = runner.parse_args(command[3:])
    assert args.observation_mode == "screenshot" and args.max_steps == 4

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("use_alias", [False, True])
def test_comparison_rejects_recording_reused_across_trials(run_pair, tmp_path, use_alias):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    recordings = {(1, mode): path for mode, path in paths.items()}
    for mode, path in paths.items():
        alias = tmp_path / f"alias_{mode}"
        if use_alias:
            alias.symlink_to(path, target_is_directory=True)
        recordings[2, mode] = alias if use_alias else path
    write_attempt_ledger(ledger, recordings, 2)
    with pytest.raises(ValueError, match="recording.*path|reused|duplicate.*recording"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")])

@pytest.mark.usefixtures('no_network')
def test_comparison_rejects_scheduled_run_name_mismatch(run_pair, tmp_path):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    rows[0]["run_name"] = "different_scheduled_trial"
    write_json_lines(ledger, rows)
    with pytest.raises(ValueError, match="run_name|run name|scheduled.*task|scheduled.*trial"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")])

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("key,value", [("model", "different-model"), ("max_turns", 99),
    ("max_output_tokens", 6000), ("viewport", [800, 600]), ("reasoning_effort", "low")])
def test_comparison_rejects_uniform_schedule_that_differs_from_actual_controls(run_pair, tmp_path, key, value):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    for row in rows:
        row["configuration"][key] = value
    write_json_lines(ledger, rows)
    with pytest.raises(ValueError, match="schedule|configuration|model|budget|control"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")])

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("binding", ["rubric_sha256", "judge_model"])
def test_comparison_rejects_grade_not_bound_to_schedule(run_pair, tmp_path, monkeypatch, binding):
    paths, *_ = run_pair
    rubric = tmp_path / "rubric.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.", "start_url": "https://example.test",
        "criteria": [{"id": "result", "description": "The result is established."}]})
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self, payload: {
        "model": "gpt-6.1-sol", "output_text": json.dumps({"criteria": [{"id": "result", "verdict": "success",
            "reason": "Observed", "states": [1]}]}), "usage": {"input_tokens": 100, "output_tokens": 10}})
    for path in paths.values():
        asyncio.run(grade_run(path, rubric, judge_model="gpt-6.1-sol", api_key="test", execute=True))
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    for row in rows:
        row.update(rubric=str(rubric), rubric_sha256=hashlib.sha256(rubric.read_bytes()).hexdigest(),
            judge_model="gpt-6.1-sol")
        row[binding] = "0" * 64 if binding == "rubric_sha256" else "different-judge"
    write_json_lines(ledger, rows)
    with pytest.raises(ValueError, match="rubric|judge|grading"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")])

@pytest.mark.usefixtures('no_network')
def test_comparison_rejects_unverified_profiles_and_changed_runtime(run_pair):
    import copy
    paths, *_ = run_pair
    dom, ss = [inspect_recording(paths[m]) for m in ("dom","screenshot")]
    bad = copy.deepcopy(ss)
    bad["manifest"]["browser_profile_provenance"]["profile_fresh_at_run_start"] = None
    with pytest.raises(ValueError, match="freshness"):
        compare(dom,bad)
    bad = copy.deepcopy(ss)
    bad["manifest"]["browser_profile_provenance"]["browser_environment"]["LANG"] = "different"
    with pytest.raises(ValueError, match="environments"):
        compare(dom,bad)

@pytest.mark.usefixtures('no_network')
def test_ungraded_primary_policy_cannot_be_mixed(run_pair):
    paths, *_ = run_pair
    for mode, policy in (("dom","paired"),("screenshot","actor_native")):
        recording = inspect_recording(paths[mode])
        write_json(paths[mode]/"completion.json", {"task_id":"task_01", "observation_mode":mode,
            "recording_sha256":recording["recording_sha256"], "method":"ungraded", "verdict":"ungraded",
            "evidence_policy":policy})
    with pytest.raises(ValueError, match="evidence_policy"):
        compare(*(inspect_recording(paths[m]) for m in ("dom","screenshot")))

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("change",["environment","missing_environment","missing_build","capture","renderer"])
def test_ledger_requires_shared_capture_and_environment_across_all_trials(run_pair,tmp_path,change):
    import shutil
    paths, *_ = run_pair
    recordings = {}
    for trial in (1,2):
        for mode in ("dom","screenshot"):
            path = tmp_path/f"trial_{trial:04d}"/mode/"task_01"
            shutil.copytree(paths[mode],path)
            for filename in ("task.json","manifest.json"):
                value = json.loads((path/filename).read_text())
                value["run_name"] = f"trial_{trial:04d}"
                if filename=="manifest.json":
                    profile = value["browser_profile_provenance"]
                    if change=="environment" and trial==2:
                        profile["browser_environment"]["LANG"] = "changed-in-both-arms"
                    if change=="missing_environment" and trial==1 and mode=="dom":
                        profile["browser_environment"] = {}
                    if change=="missing_build" and trial==1 and mode=="dom":
                        profile["browser_build"].pop("image_id")
                    if change=="capture" and mode=="screenshot":
                        value["dom_capture_parameters"]["max_nodes"] += 1
                    if change=="renderer" and mode=="screenshot":
                        value["renderer_versions"]["full"]["sha256"] = "changed"
                write_json(path/filename,value)
            recordings[(trial,mode)] = path
    ledger = tmp_path/"schedule.jsonl"
    write_attempt_ledger(ledger,recordings,2)
    with pytest.raises(ValueError,match="environment|build|capture|renderer"):
        compare_main(["--ledger",str(ledger),"--output",str(tmp_path/"report")])

@pytest.mark.usefixtures('no_network')
def test_comparison_rejects_selected_catalog_hash_mismatch(run_pair):
    import copy
    paths, *_ = run_pair
    dom, screenshot = [inspect_recording(paths[mode]) for mode in ("dom", "screenshot")]
    dom["manifest"]["catalog_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="catalog hashes differ"):
        compare(dom, screenshot)
    dom["task"]["catalog_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="catalog hash differs between arms"):
        compare(dom, screenshot)
    screenshot["task"]["catalog_sha256"] = screenshot["manifest"]["catalog_sha256"] = "f" * 64
    first, _ = compare(dom, screenshot)
    first["trial_id"] = "1"
    second = copy.deepcopy(first)
    second.update(trial_id="2", catalog_sha256="e" * 64)
    with pytest.raises(ValueError, match="catalog hashes differ across"):
        aggregate([first, second])

@pytest.mark.parametrize("usage", [None, {}, {"input_tokens": 0, "output_tokens": 0}])
def test_actor_usage_distinguishes_reported_zero_from_absence(metric_recording_factory, usage):
    result = summarize(metric_recording_factory(usage=usage))
    reported = usage is not None and bool(usage)
    assert result["model_turns"] == 1
    assert result["turns_missing_usage"] == (0 if reported else 1)
    assert result["token_usage"]["total_tokens"] == (0 if reported else None)
    for key in ("input_tokens", "output_tokens"):
        assert result["token_usage_known_calls"][key] == int(reported)
        assert result["tokens_per_turn"][key]["mean"] == (0 if reported else None)
    assert result["cost_streams"]["actor"]["cost"]["estimated_usd"] == (0 if reported else None)

@pytest.mark.parametrize("field", ["recording_sha256", "task_id", "actor_arm", "trial_id"])
def test_summary_refuses_evaluation_receipts_from_another_run(metric_recording_factory, field):
    recording = metric_recording_factory(usage={"input_tokens": 4, "output_tokens": 2})
    receipt = evaluation_for(recording, **{field: "another-run"})
    write_json(evaluation_path(recording), receipt)
    with pytest.raises(ValueError, match="different task, arm, trial or recording"):
        summarize(recording)

@pytest.mark.parametrize("field", ["recording_sha256", "task_id", "observation_mode"])
def test_summary_refuses_primary_completion_from_another_run(metric_recording_factory, field):
    recording = metric_recording_factory()
    write_json(Path(recording["source"]) / "completion.json", completion_for(recording, **{field: "another-run"}))
    with pytest.raises(ValueError, match="stale or belongs to a different run"):
        summarize(recording)

@pytest.mark.parametrize("field", ["recording_sha256", "task_id", "observation_mode", "evidence_policy"])
def test_summary_refuses_secondary_completion_with_wrong_identity_or_policy(metric_recording_factory, field):
    recording = metric_recording_factory()
    grade = completion_for(recording, evidence_policy="actor_native")
    grade[field] = "another-run"
    write_json(Path(recording["source"]) / "completion_actor_native.json", grade)
    with pytest.raises(ValueError, match="secondary completion grade is stale or has the wrong policy"):
        summarize(recording)

def test_primary_completion_must_match_the_evaluation_rubric(metric_recording_factory):
    recording = metric_recording_factory()
    write_json(evaluation_path(recording), evaluation_for(recording, rubric_sha256="another-rubric"))
    write_json(Path(recording["source"]) / "completion.json", completion_for(recording))
    with pytest.raises(ValueError, match="frozen rubric hashes differ"):
        summarize(recording)

@pytest.mark.parametrize("symlink", [False, True])
def test_completion_fallback_cannot_read_outside_its_evaluation_folder(metric_recording_factory, tmp_path, symlink):
    recording = metric_recording_factory()
    outside = tmp_path / "outside-grade.json"
    write_json(outside, completion_for(recording))
    path = evaluation_path(recording)
    selected = outside
    if symlink:
        path.parent.mkdir(parents=True)
        selected = path.parent / "grade.json"
        selected.symlink_to(outside)
    write_json(path, evaluation_for(recording, stages={"paired_completion": {"result": str(selected)}}))
    with pytest.raises(ValueError, match="outside its evaluation folder"):
        summarize(recording)

def test_bound_completion_fallback_retains_grade_and_judge_usage(metric_recording_factory):
    recording = metric_recording_factory()
    path = evaluation_path(recording)
    grade = completion_for(recording)
    write_json(path.parent / "paired_completion.json", grade)
    write_json(path, evaluation_for(recording, stages={"paired_completion": {"result": str(path.parent / "paired_completion.json")}}))
    result = summarize(recording)
    assert result["completion"] == grade
    assert result["judge_usage"] == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert result["judge_calls"] == 1 and result["judge_calls_missing_usage"] == 0
    assert result["token_usage"]["total_tokens"] is None

def test_secondary_grade_keeps_its_own_usage_and_primary_verdict(metric_recording_factory):
    recording = metric_recording_factory(usage={"input_tokens": 4, "output_tokens": 2})
    source = Path(recording["source"])
    primary = completion_for(recording)
    secondary = completion_for(recording, evidence_policy="actor_native", verdict="failure",
                               usage={"input_tokens": 20, "output_tokens": 7})
    write_json(source / "completion.json", primary)
    write_json(source / "completion_actor_native.json", secondary)
    result = summarize(recording)
    assert result["completion"]["verdict"] == "success"
    assert result["secondary_completion"]["verdict"] == "failure"
    assert result["judge_usage_streams"]["paired_completion"]["usage"]["total_tokens"] == 15
    assert result["judge_usage_streams"]["actor_native_completion"]["usage"]["total_tokens"] == 27
    assert result["judge_usage"] == {"input_tokens": 30, "output_tokens": 12, "total_tokens": 42}
    assert result["judge_calls"] == 2
    assert result["token_usage"]["total_tokens"] == 6

def test_summary_refuses_a_changed_normalized_verifier_usage_artifact(metric_recording_factory):
    recording = metric_recording_factory()
    path = evaluation_path(recording)
    write_json(path.parent / "dom_model" / "run_metrics.json", {"provider_call_metrics": {}})
    write_json(path, evaluation_for(recording, stages={"dom_model": {"status": "complete", "normalized_metrics_sha256": "0" * 64}}))
    with pytest.raises(ValueError, match="normalized verifier accounting artifact changed"):
        summarize(recording)

def test_summary_refuses_an_unknown_completion_verdict(metric_recording_factory):
    recording = metric_recording_factory()
    write_json(Path(recording["source"]) / "completion.json", completion_for(recording, verdict="probably"))
    with pytest.raises(ValueError, match="invalid completion verdict"):
        summarize(recording)

@pytest.mark.parametrize("requested", [[], [0], [-1], [True], ["1"], [2]])
def test_pass_at_k_refuses_invalid_or_unsupported_requests(metric_recording_factory, requested):
    pair = pair_for(metric_recording_factory())
    with pytest.raises(ValueError, match="positive integers|at least k"):
        aggregate([pair], pass_k=requested)

def test_aggregate_requires_a_nonempty_trial_selection():
    with pytest.raises(ValueError, match="no matched task pairs"):
        aggregate([])

@pytest.mark.parametrize("changed", ["controls", "returned_model", "task_label"])
def test_cross_trial_aggregation_refuses_conflicting_shared_controls(metric_recording_factory, changed):
    first = pair_for(metric_recording_factory(trial="trial_0001"))
    second = pair_for(metric_recording_factory(trial="trial_0002"))
    if changed == "controls":
        second["shared_controls"] = {"model": "another-model"}
        message = "shared actor controls differ"
    elif changed == "returned_model":
        second["screenshot"]["returned_actor_models"] = ["gemini-3.1-pro-preview-2026-11-01"]
        message = "returned actor model versions differ"
    else:
        first["difficulty"], second["difficulty"] = "medium", "hard"
        message = "category or difficulty differs"
    with pytest.raises(ValueError, match=message):
        aggregate([first, second])

def test_directional_audit_rates_use_available_criterion_denominators(metric_recording_factory):
    pairs = [pair_for(metric_recording_factory(trial=f"trial_{trial:04d}")) for trial in (1, 2, 3)]
    for pair, count, denominator in zip(pairs[:2], (1, 0), (2, 8)):
        pair["dom"].update(evidence_audit_status="complete", evidence_audit={
            "screenshot_evidence_loss": {"count": count, "denominator": denominator, "rate": count / denominator}})
    result = aggregate(pairs)
    assert result["modes"]["dom"]["evidence_audit"]["screenshot_evidence_loss"] == {
        "count": 1, "denominator": 10, "rate": 0.1, "audited_runs": 2, "attempted_runs": 3}
    for arm, direction in (("dom", "dom_model_evidence_loss"), ("screenshot", "screenshot_evidence_loss")):
        assert result["modes"][arm]["evidence_audit"][direction] == {
            "count": None, "denominator": None, "rate": None, "audited_runs": 0, "attempted_runs": 3}

@pytest.mark.parametrize("returned,matched", [
    ("gemini-3.1-pro-preview", True), ("gemini-3.1-pro-preview-001", True),
    ("gemini-3.1-pro-preview-v2", True), ("gemini-3.1-pro-preview-mini", False),
    ("another-model", False), (None, False),
])
def test_native_returned_models_are_diagnostic_without_changing_grades(
    metric_recording_factory, metric_evaluation_factory, returned, matched
):
    recording = metric_recording_factory(usage={"input_tokens": 4, "output_tokens": 2})
    call = {"configured_model": "gemini-3.1-pro-preview", "returned_model": returned,
            "stage": "evidence_analysis", "input_tokens": 3, "output_tokens": 1, "usage_reported": True}
    metric_evaluation_factory(recording, stages={"dom_model": {
        "status": "complete", "usage_coverage": "complete", "calls": {"gemini-3.1-pro-preview": 1},
        "usage": {"gemini-3.1-pro-preview": {"input_tokens": 3, "output_tokens": 1}},
        "provider_call_metrics": {"judge": {"calls": [call]}},
        "signals": {"process_score": 0.5, "rubric_is_success": False},
    }})
    result = summarize(recording)
    assert result["completion"]["verdict"] == "ungraded"
    assert result["auxiliary_verifiers"]["dom_model"]["signals"]["process_score"] == 0.5
    mismatches = result["native_model_mismatches"]
    assert len(mismatches) == (0 if matched else 1)
    if mismatches:
        row = mismatches[0]
        assert row["configured_model"] == "gemini-3.1-pro-preview" and row["returned_model"] == returned
        assert row["task_id"] == "custom" and row["actor_arm"] == "dom"
        assert row["trial_id"] == "trial_0001" and row["recording_sha256"] == recording["recording_sha256"]
        assert row["verifier"] == "dom_model" and row["stage"] == "evidence_analysis"
        assert row["form"] == "refused"

def test_native_model_mismatches_from_resume_history_reach_every_arm_summary(
    metric_recording_factory, metric_evaluation_factory
):
    summaries = {}
    for arm in ("dom", "screenshot"):
        recording = metric_recording_factory(arm=arm, usage={"input_tokens": 4, "output_tokens": 2})
        prior = {"configured_model": "gemini-3.1-pro-preview", "returned_model": "gemini-3.1-pro-preview-mini",
                 "stage": "relevance", "input_tokens": 2, "output_tokens": 1, "usage_reported": True}
        current = {**prior, "returned_model": None, "stage": "evidence_analysis"}
        metric_evaluation_factory(recording, stages={"dom_model": {
            "status": "complete", "usage_coverage": "complete", "calls": {"gemini-3.1-pro-preview": 1},
            "usage": {"gemini-3.1-pro-preview": {"input_tokens": 2, "output_tokens": 1}},
            "provider_call_metrics": {"judge": {"calls": [current]}},
            "attempt_history": [{"status": "failed", "usage_coverage": "complete",
                "calls": {"gemini-3.1-pro-preview": 1},
                "usage": {"gemini-3.1-pro-preview": {"input_tokens": 2, "output_tokens": 1}},
                "provider_call_metrics": {"judge": {"calls": [prior]}}}],
        }})
        summaries[arm] = summarize(recording)
    result = aggregate([{"task_id": "custom", "trial_id": "trial_0001", "shared_controls": {},
                         "both_successful": False, "successful_pair_turn_delta": None, **summaries}])
    assert len(result["native_model_mismatches"]) == 4
    for arm in ("dom", "screenshot"):
        rows = result["modes"][arm]["native_model_mismatches"]
        assert len(rows) == 2 and {row["actor_arm"] for row in rows} == {arm}
        assert {row["stage"] for row in rows} == {"relevance", "evidence_analysis"}

def test_citation_diagnostics_pool_checked_denominators_without_changing_scores(
    metric_recording_factory, metric_evaluation_factory
):
    pairs = []
    for trial, counts in ((1, (1, 2)), (2, (1, 8)), (3, None)):
        summaries = {}
        for arm in ("dom", "screenshot"):
            recording = metric_recording_factory(arm=arm, trial=f"trial_{trial:04d}", usage={"input_tokens": 4, "output_tokens": 2})
            signals = {"process_score": 0.5, "rubric_is_success": False}
            checks = None
            if counts is not None:
                invalid, checked = counts
                checks = {"checked_citations": checked, "valid_citations": checked - invalid,
                    "invalid_citations": invalid, "invalid_citation_rate": invalid / checked,
                    "checks": [{"stage": "evidence_analysis", "analyzed_state_id": 1,
                                "cited_state_id": 2, "citation": "state 2", "valid": False, "errors": ["state_not_supplied"]}]}
            metric_evaluation_factory(recording, stages={"dom_model": {"status": "complete", "signals": signals,
                **({"citation_checks": checks} if checks is not None else {})}})
            summaries[arm] = summarize(recording)
            assert summaries[arm]["citation_checks"]["dom_model"] == checks
            assert summaries[arm]["auxiliary_verifiers"]["dom_model"]["signals"]["process_score"] == 0.5
        pairs.append({"task_id": "custom", "trial_id": f"trial_{trial:04d}", "shared_controls": {},
                      "both_successful": False, "successful_pair_turn_delta": None, **summaries})
    result = aggregate(pairs)
    for arm in ("dom", "screenshot"):
        diagnostics = result["modes"][arm]["citation_checks"]["dom_model"]
        assert diagnostics["checked_citations"] == 10
        assert diagnostics["valid_citations"] == 8 and diagnostics["invalid_citations"] == 2
        assert diagnostics["invalid_citation_rate"] == 0.2
        assert diagnostics["checked_runs"] == 2 and diagnostics["attempted_runs"] == 3
        assert len(diagnostics["per_run"]) == 3
        assert result["modes"][arm]["auxiliary_verifiers"]["dom_model"]["signals"]["process_score"]["mean"] == 0.5
        assert result["modes"][arm]["evidence_audit"]["dom_model_evidence_loss"]["rate"] is None

@pytest.mark.parametrize("normalizer_name", ["normalize_dom_model", "normalize_screenshot"])
def test_native_ungraded_normalization_preserves_null_scores_and_usage(pair_factory, tmp_path, normalizer_name):
    from w8bench.verifier import normalize_results
    from w8bench.verifier.common import canonical_sha256

    pair = pair_factory()
    rubric = json.loads(pair["rubric"].read_text())["precomputed_rubric"]
    raw = {"task_id": pair["task"]["task_id"], "rubric_sha256": canonical_sha256(rubric),
           "status": "ungraded", "ungraded_reason": "scoring retries exhausted",
           "judge_fallback": {"stage": "action_scoring", "reason": "scoring retries exhausted"},
           "rubric_score": None, "rubric_total_max_points": None, "rubric_total_earned_points": None,
           "rubric_is_success": None, "rubric_generation_calls": 0,
           "token_usage": {"judge": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}},
           "call_metrics": {"judge": {"logical_calls": 1, "api_attempts": 1, "retries": 0}}}
    path = tmp_path / "ungraded.json"
    write_json(path, raw)
    normalized = getattr(normalize_results, normalizer_name)(path, input_task=pair["dom"],
        rubric_file=pair["rubric"], generation_metrics=pair["metrics"], run_log=tmp_path / "run.log")
    result = normalized["result"]
    assert result["status"] == "ungraded" and result["ungraded_reason"] == "scoring retries exhausted"
    assert result["judge_fallback"] == raw["judge_fallback"]
    for key in ("process_score", "rubric_is_success", "frozen_full_score", "total_earned_points", "total_max_points"):
        assert result[key] is None
    assert normalized["criteria"] == []
    assert normalized["token_usage"]["combined"]["total_tokens"] == 4
    assert normalized["llm_calls"]["total"] == 1

@pytest.mark.parametrize("policy", ["completion_policy_version", "acceptance_policy_version"])
def test_aggregation_refuses_mixed_policy_versions_for_ungraded_receipts(
    metric_recording_factory, metric_evaluation_factory, policy
):
    pairs = []
    for trial in (1, 2):
        summaries = {}
        for arm in ("dom", "screenshot"):
            recording = metric_recording_factory(arm=arm, trial=f"trial_{trial:04d}", usage={"input_tokens": 4, "output_tokens": 2})
            metric_evaluation_factory(recording, grade_usage={"input_tokens": 3, "output_tokens": 1})
            path = Path(recording["source"]) / "completion.json"
            grade = json.loads(path.read_text())
            grade.update(method="ungraded", verdict="ungraded")
            if trial == 1:
                grade[policy] = "paired-completion/v4" if policy == "completion_policy_version" else "returned-model-acceptance/v2"
            write_json(path, grade)
            summaries[arm] = summarize(recording)
        pairs.append({"task_id": "custom", "trial_id": f"trial_{trial:04d}", "shared_controls": {},
                      "both_successful": False, "successful_pair_turn_delta": None, **summaries})
    with pytest.raises(ValueError, match="completion policy|acceptance policy|policy versions"):
        aggregate(pairs)

def test_aggregation_keeps_unstarted_placeholders_with_versioned_grades(
    metric_recording_factory, metric_evaluation_factory
):
    recording = metric_recording_factory(usage={"input_tokens": 4, "output_tokens": 2})
    metric_evaluation_factory(recording, grade_usage={"input_tokens": 3, "output_tokens": 1})
    path = Path(recording["source"]) / "completion.json"
    grade = json.loads(path.read_text())
    grade.update(completion_policy_version="paired-completion/v4", acceptance_policy_version="returned-model-acceptance/v2")
    write_json(path, grade)
    graded = summarize(recording)
    placeholder = deepcopy(graded)
    placeholder.update(completion={"method": "ungraded", "verdict": "ungraded"}, completion_grade_available=False)
    result = aggregate([{"task_id": "custom", "trial_id": "1", "shared_controls": {}, "dom": graded,
                         "screenshot": placeholder, "both_successful": False, "successful_pair_turn_delta": None}])
    assert result["modes"]["screenshot"]["completion_counts"] == {"ungraded": 1}

@pytest.mark.parametrize("native", ["dom_model", "screenshot_verifier"])
def test_ungraded_native_results_keep_costs_and_stay_out_of_score_means(
    metric_recording_factory, metric_evaluation_factory, native
):
    pairs = []
    for trial, status, score in ((1, "ungraded", None), (2, "complete", 0.75)):
        summaries = {}
        for arm in ("dom", "screenshot"):
            recording = metric_recording_factory(arm=arm, trial=f"trial_{trial:04d}", usage={"input_tokens": 4, "output_tokens": 2})
            call = {"configured_model": "gemini-3.1-pro-preview", "returned_model": "gemini-3.1-pro-preview",
                    "input_tokens": 3, "output_tokens": 1, "usage_reported": True}
            metric_evaluation_factory(recording, stages={native: {
                "status": status, "calls": {"gemini-3.1-pro-preview": 1}, "usage_coverage": "complete",
                "usage": {"gemini-3.1-pro-preview": {"input_tokens": 3, "output_tokens": 1}},
                "provider_call_metrics": {"judge": {"calls": [call]}},
                "signals": {"process_score": score, "rubric_is_success": None if status == "ungraded" else False},
            }})
            summaries[arm] = summarize(recording)
        pairs.append({"task_id": "custom", "trial_id": f"trial_{trial:04d}", "shared_controls": {},
                      "both_successful": False, "successful_pair_turn_delta": None, **summaries})
    result = aggregate(pairs)
    for arm in ("dom", "screenshot"):
        auxiliary = result["modes"][arm]["auxiliary_verifiers"][native]
        assert auxiliary["status_counts"] == {"ungraded": 1, "complete": 1}
        assert auxiliary["signals"]["process_score"]["mean"] == 0.75
        assert auxiliary["signals"]["process_score"]["known_runs"] == 1
        assert result["modes"][arm]["judge_usage_streams"][f"{native}:gemini-3.1-pro-preview"]["calls"] == 2
        assert result["modes"][arm]["cost_streams"][f"{native}:gemini-3.1-pro-preview"]["cost"]["estimated_usd"] > 0

def test_empty_citation_checks_differ_from_unavailable_diagnostics(
    metric_recording_factory, metric_evaluation_factory
):
    recording = metric_recording_factory(usage={"input_tokens": 4, "output_tokens": 2})
    checks = {"schema_version": "dom-citation-checks/v1", "checked_citations": 0,
              "valid_citations": 0, "invalid_citations": 0, "invalid_citation_rate": None,
              "quote_checked_citations": 0, "quote_unavailable_citations": 0, "checks": []}
    metric_evaluation_factory(recording, stages={"dom_model": {"status": "complete", "citation_checks": checks}})
    summary = summarize(recording)
    result = aggregate([{"task_id": "custom", "trial_id": "trial_0001", "shared_controls": {},
                         "dom": summary, "screenshot": deepcopy(summary), "both_successful": False,
                         "successful_pair_turn_delta": None}])
    diagnostics = result["modes"]["dom"]["citation_checks"]
    assert diagnostics["dom_model"]["checked_citations"] == 0
    assert diagnostics["dom_model"]["invalid_citation_rate"] is None
    assert diagnostics["dom_model"]["checked_runs"] == 1
    assert diagnostics["dom_model"]["quote_checked_citations"] == 0
    assert diagnostics["screenshot_verifier"]["checked_citations"] is None
    assert diagnostics["screenshot_verifier"]["checked_runs"] == 0

@pytest.mark.parametrize("normalizer_name", ["normalize_dom_model", "normalize_screenshot"])
@pytest.mark.parametrize("status", ["complete", "ungraded"])
@pytest.mark.parametrize("placement", ["top", "evidence_metadata", "both"])
def test_citation_diagnostics_do_not_enter_normalized_results(
    pair_factory, tmp_path, normalizer_name, status, placement
):
    from w8bench.verifier import normalize_results
    from w8bench.verifier.common import canonical_sha256

    pair = pair_factory()
    rubric = json.loads(pair["rubric"].read_text())["precomputed_rubric"]
    raw = {"task_id": pair["task"]["task_id"], "rubric_sha256": canonical_sha256(rubric),
           "rubric_generation_calls": 0, "rubric_total_max_points": 10,
           "rubric_total_earned_points": 10, "rubric_score": 1, "rubric_is_success": True,
           "dom_model_evidence_audit": {"required_states": [0], "selected": [{"analysis": "Observed title."}]},
           "intermediate_mm_rubric_steps": {"step6_rescoring_summary": [
               {**item, "earned_points": item["max_points"], "post_image_earned_points": item["max_points"]}
               for item in rubric["items"]]}}
    if status == "ungraded":
        raw.update(status="ungraded", ungraded_reason="scoring unavailable", rubric_total_max_points=None,
                   rubric_total_earned_points=None, rubric_score=None, rubric_is_success=None)
    path = tmp_path / "result.json"
    write_json(path, raw)
    normalize = getattr(normalize_results, normalizer_name)
    kwargs = {"input_task": pair["dom"], "rubric_file": pair["rubric"],
              "generation_metrics": pair["metrics"], "run_log": tmp_path / "run.log"}
    baseline = normalize(path, **kwargs)
    checks = {"checked_citations": 2, "valid_citations": 1, "invalid_citations": 1,
              "invalid_citation_rate": 0.5, "checks": [{"citation": "state 99", "valid": False}]}
    if placement in {"top", "both"}:
        raw["citation_checks"] = checks
    if placement in {"evidence_metadata", "both"}:
        raw["dom_model_evidence_audit"]["citation_checks"] = checks
        raw["dom_model_evidence_audit"]["selected"][0]["citation_checks"] = checks
    write_json(path, raw)
    assert normalize(path, **kwargs) == baseline

def test_run_citation_diagnostics_use_the_raw_stage_counter_record(
    metric_recording_factory, metric_evaluation_factory
):
    recording = metric_recording_factory(usage={"input_tokens": 4, "output_tokens": 2})
    checks = {"checked_citations": 1, "valid_citations": 0, "invalid_citations": 1,
              "invalid_citation_rate": 1, "checks": []}
    root, evaluation = metric_evaluation_factory(recording, stages={"dom_model": {
        "status": "complete", "signals": {"citation_checks": checks},
        "evidence_diagnostics": {"citation_checks": checks},
    }})
    assert summarize(recording)["citation_checks"]["dom_model"] is None
    evaluation["stages"]["dom_model"]["citation_checks"] = checks
    write_json(root / "evaluation.json", evaluation)
    assert summarize(recording)["citation_checks"]["dom_model"] == checks

@pytest.mark.parametrize("points_field", ["post_image_earned_points", "post_dom_earned_points"])
def test_penalties_normalize_without_changing_frozen_criteria(pair_factory, tmp_path, points_field):
    pair = pair_factory()
    original_rubric = pair["rubric"].read_bytes()
    rubric = json.loads(original_rubric)["precomputed_rubric"]
    rows = [{**item, "earned_points": item["max_points"],
             points_field: item["max_points"]} for item in rubric["items"]]
    raw = {"task_id": pair["task"]["task_id"], "rubric_sha256": canonical_sha256(rubric),
           "criterion_denominator": 10, "rubric_total_max_points": 12,
           "rubric_total_earned_points": 10, "rubric_score": 10 / 12,
           "intermediate_mm_rubric_steps": {"step6_rescoring_summary": rows,
               "step7_penalty_criteria": [{"criterion": "Unsolicited material side effect",
                   "max_points": 2, "earned_points": 0, points_field: 0,
                   "penalty": True}]}}
    result_file = tmp_path / "penalty.json"
    result_file.write_text(json.dumps(raw))
    kwargs = {"input_task": pair["screenshot"], "rubric_file": pair["rubric"],
              "generation_metrics": pair["metrics"], "run_log": tmp_path / "run.log"}
    screenshot = normalize_screenshot(result_file, **kwargs)
    dom = normalize_dom_model(result_file, **kwargs)
    assert screenshot["frozen_rubric_sha256"] == dom["frozen_rubric_sha256"] == canonical_sha256(rubric)
    for value in (screenshot, dom):
        assert sum(item["max_points"] for item in value["criteria"]) == 10
        assert value["result"]["frozen_full_score"] is True
        assert value["result"]["frozen_total_earned_points"] == 10
        assert value["result"]["frozen_total_max_points"] == 10
        assert value["result"]["runtime_penalty_total_max_points"] == 2
        assert value["result"]["process_score"] == 10 / 12
        assert value["result"]["total_max_points"] == 12
        assert value["penalty_criteria"][0]["final_points"] == 0
    assert pair["rubric"].read_bytes() == original_rubric
    raw["intermediate_mm_rubric_steps"]["step7_penalty_criteria"][0][points_field] = 1
    result_file.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="zero earned points"):
        (normalize_dom_model if points_field.startswith("post_dom") else normalize_screenshot)(result_file, **kwargs)

@pytest.mark.parametrize("normalizer", [normalize_screenshot, normalize_dom_model])
@pytest.mark.parametrize("drift", ["hash", "order", "maximum", "generation", "denominator"])
def test_normalizer_rejects_frozen_contract_drift(pair_factory, tmp_path, drift, normalizer):
    pair = pair_factory()
    rubric = json.loads(pair["rubric"].read_text())["precomputed_rubric"]
    rows = [{**item, "earned_points": item["max_points"], "post_image_earned_points": item["max_points"],
             "post_dom_earned_points": item["max_points"]} for item in rubric["items"]]
    raw = {"task_id": pair["task"]["task_id"], "rubric_sha256": canonical_sha256(rubric),
        "criterion_denominator": 10, "rubric_total_max_points": 10, "rubric_total_earned_points": 10,
        "rubric_score": 1, "intermediate_mm_rubric_steps": {"step6_rescoring_summary": rows}}
    if drift == "hash":
        raw["rubric_sha256"] = "different"
    elif drift == "order":
        rows.reverse()
    elif drift == "maximum":
        rows[0]["max_points"] = 6; rows[1]["max_points"] = 4
    elif drift == "generation":
        raw["rubric_generation_calls"] = 1
    else:
        raw["rubric_total_max_points"] = 9
    path = tmp_path / "result.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        normalizer(path, input_task=pair["dom"], rubric_file=pair["rubric"], generation_metrics=pair["metrics"], run_log=tmp_path / "run.log")

@pytest.mark.parametrize(
    ("points_field", "normalizer"),
    [
        ("post_image_earned_points", normalize_screenshot),
        ("post_dom_earned_points", normalize_dom_model),
        ("post_image_earned_points", normalize_dom_model),
    ],
    ids=("screenshot", "dom-native", "dom-historical"),
)
def test_normalizer_accepts_conditional_denominator(
    tmp_path, points_field, normalizer
):
    items = [
        {
            "criterion": "always",
            "description": "always applies",
            "max_points": 7,
            "justification": "",
            "earned_points": "",
        },
        {
            "criterion": "conditional",
            "description": "applies only when unavailable",
            "max_points": 3,
            "justification": "",
            "earned_points": "",
        },
    ]
    rubric = {"items": items}
    rubric_file = tmp_path / "rubric.json"
    rubric_file.write_text(json.dumps({"task_id": "task", "precomputed_rubric": rubric}))
    generation_metrics = tmp_path / "generation.json"
    generation_metrics.write_text("{}")
    run_log = tmp_path / "run.log"
    run_log.write_text("")
    result = {
        "task_id": "task",
        "rubric_sha256": canonical_sha256(rubric),
        "criterion_denominator": 10,
        "rubric_total_max_points": 7,
        "rubric_total_earned_points": 7,
        "rubric_score": 1.0,
        "rubric_generation_calls": 0,
        "intermediate_mm_rubric_steps": {
            "step6_rescoring_summary": [
                {
                    "criterion": "always",
                    "max_points": 7,
                    "earned_points": 7,
                    points_field: 7,
                },
                {
                    "criterion": "conditional",
                    "max_points": 3,
                    "earned_points": 0,
                    points_field: 0,
                    "condition": "Only when unavailable",
                    "is_condition_met": False,
                },
            ]
        },
    }
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps(result))

    normalized = normalizer(
        result_file,
        input_task=tmp_path,
        rubric_file=rubric_file,
        generation_metrics=generation_metrics,
        run_log=run_log,
    )

    assert normalized["result"]["total_max_points"] == 7
    assert normalized["criteria"][1]["is_applicable"] is False
    assert normalized["result"]["process_score"] == 1
    assert normalized["result"]["frozen_full_score"] is False
    assert normalized["result"]["frozen_total_earned_points"] == 7
    assert normalized["result"]["frozen_total_max_points"] == 10

@pytest.mark.parametrize("normalizer", [normalize_screenshot, normalize_dom_model])
@pytest.mark.parametrize("include_validity", [False, True])
def test_normalizer_reads_ambiguity_from_its_actual_stage_and_preserves_missing(pair_factory, tmp_path, normalizer, include_validity):
    pair = pair_factory()
    rubric = json.loads(pair["rubric"].read_text())["precomputed_rubric"]
    steps = {"step6_rescoring_summary": [{**item, "earned_points": item["max_points"]} for item in rubric["items"]],
        "step9_first_point_of_failure": {"has_failure": False, "is_ambiguous": False, "ambiguity_codes": []}}
    if include_validity:
        steps["step9b_task_verification_with_trajectory"] = {"is_ambiguous": True, "ambiguity_codes": ["7.1"], "is_invalid": False}
        steps["step10_task_verification"] = {"is_ambiguous": False, "ambiguity_codes": [], "is_invalid": True}
    raw = {"task_id": pair["task"]["task_id"], "rubric_sha256": canonical_sha256(rubric),
        "rubric_total_max_points": 10, "rubric_total_earned_points": 10, "rubric_score": 1,
        "intermediate_mm_rubric_steps": steps}
    path = tmp_path / "result.json"
    path.write_text(json.dumps(raw))
    value = normalizer(path, input_task=pair["dom"], rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"], run_log=tmp_path / "run.log")["result"]
    assert value["is_ambiguous"] is (True if include_validity else None)
    assert value["ambiguity_codes"] == (["7.1"] if include_validity else None)
    assert value["is_invalid"] is (True if include_validity else None)
    assert value["trajectory_task_verification"] == (steps["step9b_task_verification_with_trajectory"] if include_validity else None)
    assert value["task_only_verification"] == (steps["step10_task_verification"] if include_validity else None)
    assert value["process_score"] == 1 and value["frozen_full_score"] is True

def test_run_selection_and_no_double_nesting(monkeypatch):
    monkeypatch.delenv("W8_RUN_NAME", raising=False)
    assert resolve_run_name() == "run_1"
    monkeypatch.setenv("W8_RUN_NAME", "run_2")
    assert run_directory("recordings") == Path("recordings/run_2")
    assert run_directory("recordings/run_3", "run_3") == Path("recordings/run_3")
    assert resolve_run_name("run_3") == "run_3"
    for value in ("", "..", "/tmp/other", "run/2", "a\\b"):
        with pytest.raises(ValueError):
            resolve_run_name(value)
