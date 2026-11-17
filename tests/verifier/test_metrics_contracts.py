"""Usage coverage, receipt identity and scheduled-result aggregation contracts."""

from copy import deepcopy
from pathlib import Path

import pytest

from w8bench.task_recorder.recorder_support import write_json
from w8bench.verifier.paired_metrics import aggregate
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
