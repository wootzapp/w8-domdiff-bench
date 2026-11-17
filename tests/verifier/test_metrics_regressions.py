"""Actor/judge accounting boundaries and diagnostic aggregation contracts."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from w8bench.task_recorder.recorder_support import write_json, write_json_lines
from w8bench.verifier.paired_metrics import aggregate
from w8bench.verifier.run_full_comparison import main as compare_main
from w8bench.verifier.run_metrics import summarize


@pytest.mark.parametrize("native", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("actor_usage", [None, {"input_tokens": 10, "output_tokens": 5}])
@pytest.mark.parametrize("history_coverage", ["complete", "unknown"])
def test_resumed_native_history_preserves_actor_model_and_usage_coverage(
    metric_recording_factory, metric_evaluation_factory, native, actor_usage, history_coverage
):
    recording = metric_recording_factory(usage=actor_usage)
    baseline = summarize(recording)
    metric_evaluation_factory(recording, stages={native: {
        "status": "failed", "attempt_history": [{
            "status": "failed", "usage_coverage": history_coverage,
            "calls": {"gemini-3.8-flash": 1},
            "usage": {"gemini-3.8-flash": {"input_tokens": 2, "output_tokens": 1}},
        }],
    }})
    result = summarize(recording)
    for key in ("returned_actor_models", "turns_missing_usage", "cost_coverage", "token_usage"):
        assert result[key] == baseline[key]
    assert result["returned_actor_models"] == ["gemini-3.1-pro-preview"]
    history = result["judge_usage_streams"][f"{native}:gemini-3.8-flash"]
    assert history["known_calls"] == 1
    assert history["usage"]["total_tokens"] == 3


INVALID_USAGE = [None, True, False, -1, float("nan"), float("inf"), float("-inf"), "4"]
COMPONENT_PATHS = {
    "input_tokens": ("input_tokens",),
    "output_tokens": ("output_tokens",),
    "reasoning_tokens": ("output_tokens_details", "reasoning_tokens"),
    "cached_input_tokens": ("input_tokens_details", "cached_tokens"),
    "cache_write_input_tokens": ("input_tokens_details", "cache_write_tokens"),
}


@pytest.mark.parametrize("component", list(COMPONENT_PATHS))
@pytest.mark.parametrize("invalid", INVALID_USAGE, ids=["unknown", "true", "false", "negative", "nan", "infinity", "negative_infinity", "text"])
def test_actor_token_components_require_finite_nonnegative_nonboolean_numbers(
    metric_recording_factory, component, invalid
):
    usage = {"input_tokens": 100, "output_tokens": 50,
             "input_tokens_details": {"cached_tokens": 10, "cache_write_tokens": 8},
             "output_tokens_details": {"reasoning_tokens": 5}}
    path = COMPONENT_PATHS[component]
    target = usage
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid
    result = summarize(metric_recording_factory(usage=usage))
    assert result["token_usage"][component] is None
    assert result["token_usage_known_calls"][component] == 0
    if component in {"input_tokens", "output_tokens"}:
        assert result["turns_missing_usage"] == 1
        assert result["cost_coverage"] == "partial"
        assert result["tokens_per_turn"][component]["mean"] is None
        assert result["cost_streams"]["actor"]["cost"]["estimated_usd"] is None


@pytest.mark.parametrize("invalid", [True, False, -1, float("nan"), float("inf"), float("-inf"), "4"])
@pytest.mark.parametrize("field", ["input_tokens", "output_tokens", "cached_tokens", "cache_write_tokens", "ttl_12h_tokens"])
def test_invalid_pricing_components_never_produce_an_exact_cost(metric_recording_factory, field, invalid):
    usage = {"input_tokens": 100, "output_tokens": 50,
             "input_tokens_details": {"cached_tokens": 10, "cache_write_tokens": 8,
                                      "cache_write_tokens_details": {"ttl_12h_tokens": 2}}}
    if field in {"input_tokens", "output_tokens"}:
        usage[field] = invalid
    elif field == "ttl_12h_tokens":
        usage["input_tokens_details"]["cache_write_tokens_details"][field] = invalid
    else:
        usage["input_tokens_details"][field] = invalid
    result = summarize(metric_recording_factory(usage=usage))
    assert result["cost_streams"]["actor"]["cost"]["estimated_usd"] is None


@pytest.mark.parametrize("component", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("invalid", INVALID_USAGE, ids=["unknown", "true", "false", "negative", "nan", "infinity", "negative_infinity", "text"])
def test_completion_usage_requires_valid_principal_counts(
    metric_recording_factory, metric_evaluation_factory, component, invalid
):
    recording = metric_recording_factory(usage={"input_tokens": 1, "output_tokens": 1})
    usage = {"input_tokens": 10, "output_tokens": 5}
    usage[component] = invalid
    metric_evaluation_factory(recording, grade_usage=usage)
    result = summarize(recording)
    stream = result["judge_usage_streams"]["paired_completion"]
    assert stream["usage"][component] is None
    assert stream["usage_coverage"] != "complete"
    assert result["judge_usage"][component] is None
    assert result["judge_calls_missing_usage"] == 1
    assert stream["cost"]["estimated_usd"] is None


@pytest.mark.parametrize("outcome", ["startup_failure", "not_started", "interrupted", "incomplete_recording"])
@pytest.mark.parametrize("attempt_evidence", [False, "request", "response", "result", "counter", "malformed_counter", "malformed_decisions", "steps"])
def test_scheduled_actor_cost_is_zero_only_when_no_calls_are_known(
    tmp_path, outcome, attempt_evidence
):
    rows = []
    for arm in ("dom", "screenshot"):
        recording = tmp_path / arm / "custom"
        if attempt_evidence:
            if attempt_evidence in {"request", "response", "result"}:
                write_json(recording / "turns" / "turn_000001" / f"{attempt_evidence}.json", {"model": "gemini-3.1-pro-preview"})
            elif attempt_evidence in {"counter", "malformed_counter"}:
                write_json(recording / "manifest.json", {"model_turns": 1 if attempt_evidence == "counter" else "1"})
            elif attempt_evidence == "malformed_decisions":
                recording.mkdir(parents=True)
                (recording / "decisions.jsonl").write_text('{"model_turn":1,')
            else:
                write_json(recording / "manifest.json", {"steps": [{"action_succeeded": True, "action": {"action": "wait"}}]})
        rows.append({"task_id": "custom", "trial": 1, "trials": 1, "arm": arm,
                     "run_name": "trial_0001", "recording": str(recording),
                     "technical_outcome": outcome, "configuration": {"model": "gemini-3.1-pro-preview"},
                     "task": {"instruction": "Read title.", "start_url": "https://example.test"}})
    ledger = tmp_path / "ledger.jsonl"
    write_json_lines(ledger, rows)
    assert compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")]) == 0
    pairs = json.loads((tmp_path / "report" / "pairs.json").read_text())
    expected_zero = outcome in {"startup_failure", "not_started"} and not attempt_evidence
    for arm in ("dom", "screenshot"):
        summary = pairs[0][arm]
        cost = summary["cost_streams"]["actor"]["cost"]
        assert summary["cost_coverage"] == ("complete" if expected_zero else "partial")
        assert summary["turns_complete"] is expected_zero
        assert cost["coverage"] == ("complete" if expected_zero else "unknown")
        assert cost["estimated_usd"] == (0 if expected_zero else None)
        assert summary["token_usage"]["total_tokens"] == (0 if expected_zero else None)


def test_attempted_unknown_usage_never_becomes_zero_cost(metric_recording_factory):
    result = summarize(metric_recording_factory(usage={}))
    assert result["model_turns"] == 1
    assert result["token_usage"]["total_tokens"] is None
    assert result["cost_streams"]["actor"]["cost"]["estimated_usd"] is None


@pytest.mark.parametrize("stage_name", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("invalid", INVALID_USAGE, ids=["unknown", "true", "false", "negative", "nan", "infinity", "negative_infinity", "text"])
def test_native_usage_declarations_cannot_make_invalid_counts_complete(
    metric_recording_factory, metric_evaluation_factory, stage_name, invalid
):
    recording = metric_recording_factory(usage={"input_tokens": 1, "output_tokens": 1})
    metric_evaluation_factory(recording, stages={stage_name: {
        "status": "complete", "usage_coverage": "complete",
        "calls": {"gemini-3.1-pro-preview": 1},
        "usage": {"gemini-3.1-pro-preview": {"input_tokens": invalid, "output_tokens": 2}},
    }})
    stream = summarize(recording)["judge_usage_streams"][f"{stage_name}:gemini-3.1-pro-preview"]
    assert stream["usage"]["input_tokens"] is None
    assert stream["usage_coverage"] != "complete"


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
