"""Offline evaluation workflows contracts."""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from tests.conftest import RUBRIC, judge_response, write_attempt_ledger
from types import SimpleNamespace
from unittest.mock import AsyncMock
from w8bench.task_recorder import runner
from w8bench.task_recorder.prepare_verifier_data import inspect_recording, prepare_recording
from w8bench.task_recorder.recorder_support import write_json
from w8bench.verifier import completion
from w8bench.verifier import completion, package_manifests
from w8bench.verifier import evidence_audit
from w8bench.verifier import generate_frozen_rubric as generator
from w8bench.verifier import rubric_scoring as scoring
from w8bench.verifier import run_comparison as comparison
from w8bench.verifier.compare_results import compare
from w8bench.verifier.completion import grade_run
from w8bench.verifier.dom_model.runner import parse_args as parse_dom_args, run as run_dom
from w8bench.verifier.package_manifests import require_local_packages
from w8bench.verifier.paired_metrics import aggregate
from w8bench.verifier.run_comparison import commands, validate_command_parity
from w8bench.verifier.run_comparison import main as comparison_main
from w8bench.verifier.run_full_comparison import main as compare_main
from w8bench.verifier.run_metrics import summarize
from w8bench.verifier.validate_inputs import validate_pair
import asyncio
import hashlib
import json
import os
import pytest
import subprocess
import sys


@pytest.mark.usefixtures("no_network")
def test_reference_grading_reports_success_without_judge_calls(run_pair, tmp_path, monkeypatch):
    paths, *_ = run_pair
    def forbidden(*args, **kwargs):
        raise AssertionError("reference grading must be offline")
    monkeypatch.setattr(runner.ModelClient, "_post", forbidden)
    rubric = tmp_path / "rubric.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.",
        "start_url": "https://example.test", "expected_answer": "done"})
    for path in paths.values():
        grade = asyncio.run(grade_run(path, rubric))
        assert grade["verdict"] == "success" and grade["judge_calls"] == 0
    receipt, _ = compare(*(inspect_recording(paths[m]) for m in ("dom", "screenshot")))
    assert receipt["successful_pair_turn_delta"] == 1
    summary = aggregate([receipt])
    assert summary["both_successful_tasks"] == 1
    assert summary["mean_successful_pair_turn_delta"] == 1
    output = tmp_path / "report"
    ledger = tmp_path / "ledger.jsonl"
    write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    assert compare_main(["--ledger", str(ledger), "--output", str(output)]) == 0
    assert (output / "summary.json").is_file()
    exported = prepare_recording(inspect_recording(paths["screenshot"]), tmp_path / "export")
    receipt = json.loads((Path(exported["output"]) / "input_receipt.json").read_text())
    assert exported["recording_sha256"] == inspect_recording(paths["screenshot"])["recording_sha256"]
    assert receipt["recording_sha256"] == exported["recording_sha256"]
    assert Path(exported["screenshot_task"], "task_data.json").is_file()
    assert Path(exported["dom_task"], "task_data.json").is_file()


@pytest.mark.usefixtures("no_network")
def test_optional_judge_uses_only_its_runs_channel(run_pair, tmp_path, monkeypatch):
    paths, *_ = run_pair
    rubric = tmp_path / "criteria.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.", "start_url": "https://example.test",
        "criteria": [{"id": "C1", "description": "The requested result is established."}]})
    payloads = []
    def post(self, payload):
        payloads.append(payload)
        return {"model": "gemini-3.6-flash", "output_text": json.dumps({"criteria": [
            {"id": "C1", "verdict": "uncertain", "reason": "insufficient support", "states": [1]}]})}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    for mode, path in paths.items():
        grade = asyncio.run(grade_run(path, rubric, judge_model="gemini-3.6-flash", api_key="offline-placeholder", execute=True, evidence_policy="actor_native"))
        assert grade["verdict"] == "uncertain" and grade["judge_calls"] == 1
        content = payloads[-1]["contents"][0]["parts"]
        assert any("inlineData" in c for c in content) == (mode == "screenshot")
        assert ("DOM_ONLY_SECRET" in json.dumps(content)) == (mode == "dom")
    receipt, _ = compare(*(inspect_recording(paths[m]) for m in ("dom", "screenshot")))
    assert receipt["successful_pair_turn_delta"] is None
    assert receipt["dom"]["model_turns"] == 4  # Judge calls are not actor turns.


@pytest.mark.usefixtures("no_network")
def test_common_judge_evidence_and_secondary_policy(run_pair, tmp_path, monkeypatch):
    paths, *_ = run_pair
    rubric = tmp_path / "criteria.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.",
        "start_url": "https://example.test", "criteria": [{"id": "result", "description": "Report done."}]})
    seen = []
    def post(self, payload):
        seen.append(payload)
        return {"model": "gemini-3.6-flash", "output_text": json.dumps({"criteria": [
            {"id": "result", "verdict": "success", "reason": "Observed", "states": [1]}]}),
            "usage": {"input_tokens": 100, "output_tokens": 10}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    for mode in ("dom", "screenshot"):
        grade = asyncio.run(grade_run(paths[mode], rubric, judge_model="gemini-3.6-flash", api_key="test", execute=True))
        content = seen[-1]["contents"][0]["parts"]
        assert grade["evidence_policy"] == "paired"
        assert any("inlineData" in item for item in content)
        assert "DOM_ONLY_SECRET" in json.dumps(content)
        assert "[ref=e1]" not in json.dumps(content)
    primary = (paths["dom"] / "completion.json").read_bytes()
    grade = asyncio.run(grade_run(paths["dom"], rubric, judge_model="gemini-3.6-flash", api_key="test", execute=True,
        evidence_policy="actor_native"))
    assert grade["evidence_policy"] == "actor_native"
    assert (paths["dom"] / "completion_actor_native.json").exists()
    assert (paths["dom"] / "completion.json").read_bytes() == primary
    # Mixing policies is rejected even if every other grading control matches.
    write_json(paths["dom"] / "completion.json", grade)
    with pytest.raises(ValueError, match="evidence_policy"):
        compare(*(inspect_recording(paths[m]) for m in ("dom", "screenshot")))


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("failure", ["parse", "incomplete"])
def test_judge_failure_is_ungraded_and_keeps_its_usage_separate(run_pair, tmp_path, monkeypatch, failure):
    paths, *_ = run_pair
    rubric = tmp_path / "criteria.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.", "start_url": "https://example.test",
        "criteria": [{"id": "result", "description": "The result is established."}]})
    def post(self, payload):
        return {"id": "failed-judge-response", "model": "gemini-3.6-flash", "status": "incomplete" if failure == "incomplete" else "completed",
            "incomplete_details": {"reason": "max_output_tokens"} if failure == "incomplete" else None,
            "output_text": "malformed judge JSON", "usage": {"input_tokens": 101, "output_tokens": 17,
                "output_tokens_details": {"reasoning_tokens": 11}}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    grade = asyncio.run(grade_run(paths["dom"], rubric, judge_model="gemini-3.6-flash", api_key="test", execute=True))
    assert grade["method"] == "ungraded" and grade["verdict"] == "ungraded"
    assert grade["judge_calls"] == 1 and grade["judge_error"]
    assert grade["usage"]["input_tokens"] == 101 and grade["usage"]["output_tokens"] == 17
    assert grade["returned_judge_model"] == "gemini-3.6-flash"
    assert grade["evidence_policy"] == "paired"
    assert json.loads((paths["dom"] / "completion.json").read_text()) == grade
    receipt, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    summary = aggregate([receipt])
    assert summary["modes"]["dom"]["actor_turns"] == 4
    assert summary["modes"]["dom"]["tokens"] == 120
    assert summary["modes"]["dom"]["judge_calls"] == 1
    assert summary["modes"]["dom"]["judge_usage"]["input_tokens"] == 101
    assert summary["modes"]["dom"]["judge_usage"]["output_tokens"] == 17
    assert summary["modes"]["dom"]["completion_counts"] == {"ungraded": 1}


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("field", ["thoughts", "screen_description"])
def test_judge_visible_history_mismatch_fails_before_execution(pair_factory, field):
    from w8bench.verifier.validate_inputs import dataset_only_preflight
    pair = pair_factory()
    path = pair["dom"] / "web_surfer.log"
    event = json.loads(path.read_text())
    event["arguments"][field] = "Different judge-visible annotation"
    path.write_text(json.dumps(event) + "\n")
    with pytest.raises(ValueError, match="judge-visible action histories differ"):
        dataset_only_preflight(pair["screenshot"], pair["dom"])


@pytest.mark.usefixtures("no_network")
def test_dom_runner_dry_preflight_constructs_no_clients_or_outputs(pair_factory, tmp_path):
    pair = pair_factory()
    output = tmp_path / "must-not-exist"
    result = run_dom(
        parse_dom_args(
            [
                "--input", str(pair["dom"]),
                "--rubric-file", str(pair["rubric"]),
                "--generation-metrics", str(pair["metrics"]),
                "--eval-config", str(pair["config"]),
                "--output", str(output),
                "--redo-eval",
                "--dry-run",
            ]
        )
    )
    assert result["status"] == "preflight_passed"
    assert result["paid_calls_authorized"] is False
    assert not output.exists()


@pytest.mark.usefixtures("no_network")
def test_recording_cli_dry_run_never_enters_paid_or_batch_paths(tmp_path, monkeypatch, capsys):
    recording = tmp_path / "recording"
    recording.mkdir()
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps({"task_id": "task"}))
    seen = []
    monkeypatch.setattr(comparison, "load_env", lambda path: None)
    monkeypatch.setattr(comparison, "inspect_recording", lambda path: {"task": {"source_task_id": "task"}, "recording_sha256": "a" * 64, "coverage": {}})
    async def grade(run, rubric_path, **kwargs):
        seen.append(kwargs)
        assert kwargs["execute"] is False
        return {"method": "ungraded", "judge_calls": 0}
    monkeypatch.setattr(comparison, "grade_run", grade)
    monkeypatch.setattr(comparison, "_run_logged", lambda *args: pytest.fail("Paid scorer path entered"))
    assert comparison_main(["--run", str(recording), "--rubric", str(rubric), "--judge-model", "gemini-3.6-flash"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["model_calls"] == 0 and receipt["writes_performed"] is False
    assert seen == []
    assert list(recording.iterdir()) == []


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_full_pipeline_freezes_inputs_grades_both_formats_and_resumes(full_evaluation, tmp_path, mode):
    paths, rubric, calls = full_evaluation
    before = comparison.inspect_recording(paths[mode])["recording_sha256"]
    args = ["--run", str(paths[mode]), "--rubric", str(rubric), "--judge-model", "gemini-3.6-flash", "--execute"]
    assert comparison.main(args) == 0
    output = next(tmp_path.rglob("evaluation.json"))
    value = json.loads(output.read_text())
    assert value["status"] == "awaiting_adjudication"
    inventory = output.parent / "audit_inventory.json"
    inventory_before = inventory.read_bytes()
    assert not (output.parent / "evidence_audit.json").exists()
    assert [call["stage"] for call in value["stages"]["audit"]["calls"]] == ["inventory"]
    assert comparison.main(args) == 0
    assert inventory.read_bytes() == inventory_before
    assert len(calls["audit"]) == 1
    assert comparison.main([*args, "--stage", "adjudicate"]) == 0
    value = json.loads(output.read_text())
    assert value["status"] == "complete"
    assert set(value["stages"]) == {"paired_completion", "screenshot_verifier", "dom_model", "audit"}
    assert len(calls["primary"]) == 1 and len(calls["scorers"]) == 2 and len(calls["audit"]) == 2
    assert [call["stage"] for call in value["stages"]["audit"]["calls"]] == ["adjudication"]
    assert inventory.read_bytes() == inventory_before
    streams = summarize(inspect_recording(paths[mode]))["judge_usage_streams"]
    assert streams["audit:inventory"]["calls"] == streams["audit:adjudication"]["calls"] == 1
    assert streams["audit:inventory"]["usage"]["total_tokens"] == streams["audit:adjudication"]["usage"]["total_tokens"] == 20
    assert value["stages"]["paired_completion"]["usage"]["total_tokens"] == 70
    for name in ("screenshot_verifier", "dom_model"):
        assert value["stages"][name]["signals"]["frozen_full_score"] is True
        assert value["stages"][name]["signals"]["runtime_penalty_total_max_points"] == 0
    assert value["coverage"]["audit_eligible_states"] == value["coverage"]["expected_state_ids"]
    assert comparison.inspect_recording(paths[mode])["recording_sha256"] == before
    receipt = json.loads((output.parent / "input_receipt.json").read_text())
    assert receipt["recording_sha256"] == before and receipt["actor_arm"] == mode
    assert value["validity_date"] == receipt["validity_date"]
    generation = json.loads((output.parent / "rubric_generation_metrics.json").read_text())
    assert generation["origin"] == "validated_import" and generation["rubric_generation_calls"] == 0
    assert comparison.main(args) == 0
    assert len(calls["primary"]) == 1 and len(calls["scorers"]) == 2 and len(calls["audit"]) == 2
    judge_result = output.parent / "dom_model" / "result.json"
    original = judge_result.read_bytes()
    judge_result.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="judge artifact changed"):
        comparison.main(args)
    judge_result.write_bytes(original)
    evidence = next((output.parent / "data-dom").rglob("dom_model*.txt"))
    evidence.write_text(evidence.read_text() + "Changed staged evidence")
    with pytest.raises(ValueError, match="staged evaluation input changed"):
        comparison.main(args)
    assert len(calls["primary"]) == 1


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_completely_missing_passive_format_keeps_primary_and_available_verifier(full_evaluation, tmp_path, mode):
    paths, rubric, calls = full_evaluation
    source = paths[mode]
    manifest = json.loads((source / "manifest.json").read_text())
    remove = ["screenshot.png"] if mode == "dom" else ["dom.json", "dom_full.txt", "dom_model.json", "dom_model.txt"]
    phase = "screenshot" if mode == "dom" else "dom_model"
    for state in manifest["states"]:
        for name in remove:
            artifact = state["artifacts"].pop(name)
            (source / artifact["path"]).unlink()
        state["capture"]["paired_complete"] = False
        state["capture"]["passive_capture_errors"] = [{"phase": phase, "error": "Mock passive failure"}]
        capture_path = source / state["directory"] / "capture.json"
        capture_path.write_text(json.dumps(state["capture"]))
        state["artifacts"]["capture.json"]["sha256"] = hashlib.sha256(capture_path.read_bytes()).hexdigest()
    (source / "manifest.json").write_text(json.dumps(manifest))
    assert comparison.main(["--run", str(source), "--rubric", str(rubric), "--judge-model", "gemini-3.6-flash", "--execute"]) == 1
    output = next(tmp_path.rglob("evaluation.json"))
    value = json.loads(output.read_text())
    available, absent = ("dom_model", "screenshot_verifier") if mode == "dom" else ("screenshot_verifier", "dom_model")
    assert value["stages"]["paired_completion"]["verdict"] == "success"
    assert value["stages"][available]["status"] == "complete"
    assert value["stages"][absent]["status"] == "not_available"
    assert value["stages"]["audit"]["status"] == "not_eligible"
    assert value["coverage"]["audit_eligible_states"] == []
    assert len(calls["primary"]) == len(calls["scorers"]) == 1 and calls["audit"] == []


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("interrupted_stage", ["paired_completion", "screenshot_verifier", "audit"])
def test_interrupted_judge_stages_retain_attempt_cost_history_on_resume(full_evaluation, tmp_path, monkeypatch, interrupted_stage):
    paths, rubric, calls = full_evaluation
    args = ["--run", str(paths["dom"]), "--rubric", str(rubric), "--judge-model", "gemini-3.6-flash", "--execute"]
    if interrupted_stage == "paired_completion":
        original = completion.ModelClient._post
        def interrupt(self, payload):
            raise KeyboardInterrupt()
        monkeypatch.setattr(completion.ModelClient, "_post", interrupt)
    elif interrupted_stage == "screenshot_verifier":
        original = comparison._run_logged
        def interrupt(command, log_path):
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("Earlier incomplete attempt\n")
            raise KeyboardInterrupt()
        monkeypatch.setattr(comparison, "_run_logged", interrupt)
    else:
        original = evidence_audit.run_evidence_audit
        def interrupt(**kwargs):
            kwargs["call_records"].append({"stage": "inventory", "response_model": "gemini-3.1-pro-preview", "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9}})
            raise KeyboardInterrupt()
        monkeypatch.setattr(evidence_audit, "run_evidence_audit", interrupt)
    with pytest.raises(KeyboardInterrupt):
        comparison.main(args)
    output = next(tmp_path.rglob("evaluation.json"))
    interrupted = json.loads(output.read_text())["stages"][interrupted_stage]
    assert interrupted["status"] == "interrupted" and interrupted["usage_coverage"] == "unknown"
    if interrupted_stage == "paired_completion":
        monkeypatch.setattr(completion.ModelClient, "_post", original)
    elif interrupted_stage == "screenshot_verifier":
        monkeypatch.setattr(comparison, "_run_logged", original)
    else:
        monkeypatch.setattr(evidence_audit, "run_evidence_audit", original)
    assert comparison.main(args) == 0
    stage = json.loads(output.read_text())["stages"][interrupted_stage]
    prior, = stage["attempt_history"]
    assert prior["status"] == "interrupted" and prior["usage_coverage"] == "unknown"
    if interrupted_stage == "audit":
        assert prior["calls"][0]["usage"]["total_tokens"] == 9
    if interrupted_stage == "screenshot_verifier":
        saved_log = Path(prior["artifact_snapshots"]["run.log"]["path"])
        assert saved_log.read_text() == "Earlier incomplete attempt\n"


@pytest.mark.usefixtures("no_network")
def test_logged_verifier_attempts_append_instead_of_erasing_failure_output(tmp_path, monkeypatch):
    from types import SimpleNamespace
    outcomes = [SimpleNamespace(returncode=1, stdout="first attempt failed\n"), SimpleNamespace(returncode=0, stdout="second attempt complete\n")]
    monkeypatch.setattr(comparison.subprocess, "run", lambda *args, **kwargs: outcomes.pop(0))
    log = tmp_path / "run.log"
    with pytest.raises(RuntimeError):
        comparison._run_logged(["offline-command"], log)
    comparison._run_logged(["offline-command"], log)
    assert "first attempt failed" in log.read_text() and "second attempt complete" in log.read_text()


@pytest.mark.usefixtures("no_network")
def test_existing_fallback_warnings_are_disclosed_without_rewriting_scores(full_evaluation, tmp_path, monkeypatch):
    paths, rubric, calls = full_evaluation
    original = comparison._run_logged
    def score(command, log_path):
        original(command, log_path)
        with log_path.open("a") as stream:
            stream.write("Failed to score screenshot 1 after 5 attempts.\n"
                "Failed to rescore rubric after 5 attempts.\n"
                "Failed to detect side effects after 5 attempts.\n"
                "Failed outcome verification after 5 attempts.\n"
                "Failed to analyze criterion 0, screenshot 1 after 5 attempts.\n")
    monkeypatch.setattr(comparison, "_run_logged", score)
    assert comparison.main(["--run", str(paths["dom"]), "--rubric", str(rubric), "--judge-model", "gemini-3.6-flash", "--execute"]) == 0
    stage = json.loads(next(tmp_path.rglob("evaluation.json")).read_text())["stages"]["screenshot_verifier"]
    assert stage["judgment_quality"] == "fallback_observed"
    assert stage["fallback_counts"] == {"zero_relevance": 1, "baseline_rescore": 1,
        "no_penalties": 1, "unknown_outcome": 1, "evidence_analysis": 1}
    assert stage["signals"]["process_score"] == 1 and stage["signals"]["frozen_full_score"] is True


@pytest.mark.usefixtures("no_network")
def test_dom_initial_url_guard_does_not_block_primary_or_screenshot_judge(full_evaluation, tmp_path):
    paths, rubric, calls = full_evaluation
    # A passive DOM snapshot can fail the original DOM-specific URL alignment
    # guard independently of a valid actor recording and screenshot projection.
    source = paths["screenshot"]
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    artifact = manifest["states"][0]["artifacts"]["dom_model.txt"]
    path = source / artifact["path"]
    path.write_text(path.read_text().replace("https://example.test", "https://other.test"))
    artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    before = comparison.inspect_recording(source)["recording_sha256"]
    args = ["--run", str(source), "--rubric", str(rubric), "--judge-model", "gemini-3.6-flash", "--execute"]
    assert comparison.main(args) == 1
    output = next(tmp_path.rglob("evaluation.json"))
    evaluation = json.loads(output.read_text())
    assert evaluation["stages"]["paired_completion"]["verdict"] == "success"
    assert evaluation["stages"]["screenshot_verifier"]["status"] == "complete"
    dom = evaluation["stages"]["dom_model"]
    assert dom["status"] == "blocked" and dom["reason"] == "auxiliary_preflight_failed"
    assert "Initial URL differs" in dom["error"]
    assert dom["calls"] == 0 and dom["usage_coverage"] == "complete"
    assert evaluation["preflight"]["status"] == "failed"
    assert "Initial URL differs" in evaluation["preflight"]["error"]
    assert evaluation["stages"]["audit"]["reason"] == "paired_preflight_failed"
    assert evaluation["coverage"]["audit_eligible_states"] == [1, 2, 3]
    assert comparison.inspect_recording(source)["recording_sha256"] == before
    assert len(calls["primary"]) == len(calls["scorers"]) == 1 and calls["audit"] == []
    # The successful independent grade and screenshot score are immutable cache
    # hits on resume, while the failed auxiliary guard is recorded again.
    assert comparison.main(args) == 1
    assert len(calls["primary"]) == len(calls["scorers"]) == 1
    assert comparison.inspect_recording(source)["recording_sha256"] == before


@pytest.mark.usefixtures("no_network")
def test_missing_audit_credential_does_not_block_primary_or_original_verifiers(full_evaluation, tmp_path, monkeypatch):
    paths, rubric, calls = full_evaluation
    args = ["--run", str(paths["dom"]), "--rubric", str(rubric), "--judge-model", "gemini-3.6-flash", "--execute"]
    assert comparison.main(args) == 0
    output = next(tmp_path.rglob("evaluation.json"))
    evaluation = json.loads(output.read_text())
    assert evaluation["stages"]["paired_completion"]["verdict"] == "success"
    assert evaluation["stages"]["screenshot_verifier"]["status"] == "complete"
    assert evaluation["stages"]["dom_model"]["status"] == "complete"
    assert evaluation["stages"]["audit"]["status"] == "awaiting_adjudication"
    inventory_before = (output.parent / "audit_inventory.json").read_bytes()
    monkeypatch.delenv("GEMINI_API_KEY")
    assert comparison.main([*args, "--stage", "adjudicate"]) == 1
    evaluation = json.loads(output.read_text())
    assert evaluation["stages"]["audit"]["reason"] == "audit_configuration_failed"
    assert "Google credentials" in evaluation["stages"]["audit"]["error"]
    assert len(calls["primary"]) == 1 and len(calls["scorers"]) == 2 and len(calls["audit"]) == 1
    monkeypatch.setenv("GEMINI_API_KEY", "offline-adjudication-key")
    assert comparison.main([*args, "--stage", "adjudicate"]) == 0
    assert (output.parent / "audit_inventory.json").read_bytes() == inventory_before
    assert len(calls["primary"]) == 1 and len(calls["scorers"]) == 2 and len(calls["audit"]) == 2


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("usage,coverage", [(None, "unknown"), ({}, "unknown"),
    ({"input_tokens": None, "output_tokens": None}, "unknown"),
    ({"input_tokens": 0}, "unknown"), ({"input_tokens": 0, "output_tokens": 0}, "complete")])
def test_primary_usage_coverage_requires_both_reported_components(full_evaluation, tmp_path, monkeypatch, usage, coverage):
    paths, rubric, calls = full_evaluation
    original = completion.ModelClient._post
    def respond(self, payload):
        response = original(self, payload)
        response["usage"] = usage
        return response
    monkeypatch.setattr(completion.ModelClient, "_post", respond)
    assert comparison.main(["--run", str(paths["dom"]), "--rubric", str(rubric),
        "--judge-model", "gemini-3.6-flash", "--execute"]) == 0
    stage = json.loads(next(tmp_path.rglob("evaluation.json")).read_text())["stages"]["paired_completion"]
    assert stage["usage_coverage"] == coverage


@pytest.mark.parametrize("verdicts,expected", [
    (("success", "success"), "success"),
    (("success", "uncertain"), "uncertain"),
    (("uncertain", "uncertain"), "uncertain"),
    (("success", "failure"), "failure"),
    (("uncertain", "failure"), "failure"),
])
def test_completion_combines_frozen_criteria_with_failure_precedence(completion_case, verdicts, expected):
    case = completion_case
    case.responses.append(judge_response(verdicts))
    result = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gemini-3.6-flash", api_key="offline-key", execute=True))
    assert result["verdict"] == expected
    assert [row["id"] for row in result["criteria"]] == ["saved", "source"]
    assert result["usage"]["total_tokens"] == 28 and result["judge_calls"] == 1
    payload, = case.requests
    content = payload["contents"][0]["parts"]
    shared = json.loads(content[0]["text"])
    assert shared["frozen_criteria"] == case.rubric["criteria"]
    assert shared["observed_url_timeline"] == case.recording["coverage"]["observed_url_timeline"]
    assert any(part.get("text") == "Marker: SAVED\n" for part in content)
    assert any("inlineData" in part for part in content)
    assert all("[ref=e1]" not in part.get("text", "") for part in content)
    assert json.loads((case.run / "completion.json").read_text())["verdict"] == expected


@pytest.mark.parametrize("states", [[], [0], [2], [True], [1.0], ["1"]])
def test_completion_rejects_success_without_real_integer_state_citations(completion_case, states):
    case = completion_case
    case.responses.append(judge_response(("success", "success"), states=states))
    result = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gemini-3.6-flash", api_key="offline-key", execute=True))
    assert result["method"] == result["verdict"] == "ungraded"
    assert "judge_error" in result
    assert result["usage"]["total_tokens"] == 28 and result["judge_calls"] == 1


@pytest.mark.parametrize("field,value", [
    ("task_id", "another-task"), ("instruction", "A different request."),
    ("start_url", "https://example.test/another-source"),
])
def test_completion_refuses_task_rubric_drift_before_transport(completion_case, field, value):
    case = completion_case
    case.rubric[field] = value
    case.rubric_path.write_text(json.dumps(case.rubric))
    with pytest.raises(ValueError, match="differs from the task"):
        asyncio.run(completion.grade_run(case.run, case.rubric_path,
            judge_model="gemini-3.6-flash", api_key="offline-key", execute=True))
    assert case.requests == []
    assert not (case.run / "completion.json").exists()


@pytest.mark.parametrize("technical,answer,expected", [
    ("completed", "  SAVED\n", "success"), ("completed", "saved", "failure"),
    ("error", "SAVED", "failure"), ("interrupted", "SAVED", "failure"),
])
def test_author_designated_answer_requires_exact_text_and_normal_completion(completion_case, technical, answer, expected):
    case = completion_case
    case.rubric["expected_answer"] = "SAVED"
    case.rubric_path.write_text(json.dumps(case.rubric))
    case.recording["final"].update(run_status=technical, final_answer=answer)
    result = asyncio.run(completion.grade_run(case.run, case.rubric_path))
    assert result["method"] == "exact_final_answer" and result["verdict"] == expected
    assert result["judge_calls"] == 0 and case.requests == []


def test_completion_retains_a_missing_passive_format_as_unavailable(completion_case):
    case = completion_case
    case.recording["manifest"]["states"][0]["artifacts"].pop("screenshot.png")
    case.responses.append(judge_response(("uncertain", "uncertain"), states=[]))
    result = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gemini-3.6-flash", api_key="offline-key", execute=True))
    assert result["verdict"] == "uncertain"
    content = case.requests[0]["contents"][0]["parts"]
    assert {"text": "Recorder evidence unavailable: screenshot.png"} in content
    assert all("inlineData" not in part for part in content)


def test_completion_refuses_to_save_if_source_identity_changes(completion_case, monkeypatch):
    case = completion_case
    case.responses.append(judge_response(("success", "success")))
    snapshots = [deepcopy(case.recording), {**case.recording, "recording_sha256": "b" * 64}]
    monkeypatch.setattr(completion, "inspect_recording", lambda path: snapshots.pop(0))
    with pytest.raises(ValueError, match="recording changed during grading"):
        asyncio.run(completion.grade_run(case.run, case.rubric_path,
            judge_model="gemini-3.6-flash", api_key="offline-key", execute=True))
    assert not (case.run / "completion.json").exists()
    assert len(case.requests) == 1


@pytest.mark.parametrize("mutation", ["content", "missing_source", "extra_source", "symlink"])
def test_verifier_integrity_refuses_changed_or_redirected_sources(isolated_verifier_package, mutation):
    case = isolated_verifier_package
    assert package_manifests.require_local_package("dom_model")["tree_sha256"] == case.receipt["tree_sha256"]
    source = case.package / "runner.py"
    if mutation == "content":
        source.write_text('"""A different runner."""\n')
    elif mutation == "missing_source":
        source.unlink()
    elif mutation == "extra_source":
        (case.package / "other.py").write_text('"""Another source."""\n')
    else:
        source.unlink()
        source.symlink_to(case.package.parent / "models.py")
    with pytest.raises(RuntimeError, match="manifest|symlinks"):
        package_manifests.require_local_package("dom_model")


def test_verifier_integrity_requires_an_existing_manifest(isolated_verifier_package):
    isolated_verifier_package.manifest.unlink()
    with pytest.raises(FileNotFoundError):
        package_manifests.require_local_package("dom_model")


def test_phase_b_requires_matching_sidecars_metrics_and_rubric(pair_factory):
    pair = pair_factory()
    receipt = validate_pair(
        pair["screenshot"], pair["dom"], rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"], eval_config=pair["config"],
    )
    assert receipt["screenshot_sidecar_validated"] is True
    assert receipt["dom_model_sidecar_validated"] is True
    assert receipt["rubric_generation_calls_during_scoring"] == 0
    assert receipt["maximum_points"] == [7.0, 3.0]


def test_both_commands_share_exact_rubric_and_redo_eval(tmp_path):
    rubric = tmp_path / "frozen.json"
    built = commands(
        screenshot_task=tmp_path / "s", dom_task=tmp_path / "d", rubric_file=rubric,
        generation_metrics=tmp_path / "metrics.json", eval_config=tmp_path / "config",
        run_root=tmp_path / "run",
    )
    values = []
    for command in built.values():
        values.append(command[command.index("--rubric-file") + 1])
        assert "--redo-eval" in command
    assert values == [str(rubric), str(rubric)]
    dom_command = built["dom_model"]
    assert dom_command[dom_command.index("--output") + 1] == str(
            tmp_path / "run" / "dom_model"
    )
    parity = validate_command_parity(built)
    assert parity["min_relevance_threshold"] == "0"
    assert parity["max_evidence_items_per_criterion"] == "5"
    assert parity["redo_eval"] is True


def test_command_parity_rejects_dom_relevance_filter(tmp_path):
    built = commands(
        screenshot_task=tmp_path / "s", dom_task=tmp_path / "d",
        rubric_file=tmp_path / "rubric.json",
        generation_metrics=tmp_path / "metrics.json",
        eval_config=tmp_path / "config", run_root=tmp_path / "run",
    )
    dom = built["dom_model"]
    dom[dom.index("--min-relevance-threshold") + 1] = "3"
    with pytest.raises(ValueError, match="min_relevance_threshold"):
        validate_command_parity(built)


def test_command_parity_rejects_any_shared_control_drift(tmp_path):
    built = commands(
        screenshot_task=tmp_path / "s", dom_task=tmp_path / "d",
        rubric_file=tmp_path / "rubric.json",
        generation_metrics=tmp_path / "metrics.json",
        eval_config=tmp_path / "config", run_root=tmp_path / "run",
    )
    dom = built["dom_model"]
    dom[dom.index("--rubric-threshold") + 1] = "0.9"
    with pytest.raises(ValueError, match="rubric_threshold"):
        validate_command_parity(built)


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_native_runner_writes_ungraded_result_with_attempt_receipts(pair_factory, monkeypatch, tmp_path, mode):
    from w8bench.verifier.clients.retry import GracefulRetryClient
    from w8bench.verifier.instrumentation import instrument_client_calls
    pair = pair_factory()
    runner = import_module(f"w8bench.verifier.{mode}.runner")
    source = pair["dom" if mode == "dom_model" else "screenshot"]
    record = {"configured_model": "gemini-3.8-flash", "returned_model": None,
        "error_type": "AuthenticationError", "usage_reported": False, "http_attempts": 1}
    endpoint = SimpleNamespace(_call_records=[record], _http_attempts=1, _http_attempts_observed=True,
        total_usage=lambda: SimpleNamespace(prompt_tokens=0, completion_tokens=0), create=AsyncMock())
    action_client = GracefulRetryClient([endpoint])
    judge_client = GracefulRetryClient([SimpleNamespace(_call_records=[], _http_attempts=0,
        _http_attempts_observed=True, total_usage=lambda: SimpleNamespace(prompt_tokens=0, completion_tokens=0), create=AsyncMock())])
    instrument_client_calls(action_client)
    instrument_client_calls(judge_client)
    agent = SimpleNamespace(config=SimpleNamespace(validity_date="2026-11-17"),
        _generate_reply=AsyncMock(side_effect=scoring.UngradedVerifierError("action_scoring", "AuthenticationError")))
    if mode == "dom_model":
        monkeypatch.setattr(runner, "dom_source_receipt", lambda: {})
        monkeypatch.setattr(runner, "_dom_agent", lambda *args: (action_client, judge_client, agent))
    else:
        monkeypatch.setattr(runner, "preflight_screenshot_task", lambda *args: {"actions": 1})
        monkeypatch.setattr(runner, "_evaluation_agent", lambda *args: (agent, action_client, judge_client))
        monkeypatch.setattr(runner, "_evaluation_input", lambda *args: {})
    argv = ["--input", str(source), "--rubric-file", str(pair["rubric"]),
        "--eval-config", str(pair["config"]), "--output", str(tmp_path / mode)]
    if mode == "dom_model":
        argv.extend(["--generation-metrics", str(pair["metrics"])])
    result = runner.run(runner.parse_args(argv))
    assert result["status"] == "ungraded"
    assert result["judge_fallback"] == {"stage": "action_scoring", "reason": "AuthenticationError"}
    for field in ["score", "rubric_score", "rubric_total_max_points", "rubric_total_earned_points", "rubric_is_success", "outcome"]:
        assert result[field] is None
    assert result["call_metrics"]["action_judge"]["calls"] == [record]
    assert result["token_usage"]["action_judge"]["prompt_tokens"] is None
    saved = json.loads((tmp_path / mode / "result.json").read_text())
    assert saved["status"] == "ungraded" and saved["rubric_score"] is None


def test_rubric_draft_catalog_continues_after_auth_ungraded_task(monkeypatch, tmp_path, pair_factory):
    from w8bench.verifier import generate_frozen_rubric as generation
    rubric = {"items": [{"criterion": "Saved", "description": "Saved marker", "max_points": 1.5,
        "earned_points": "", "justification": ""}]}
    create = AsyncMock(side_effect=[scoring.UngradedVerifierError("authentication", "invalid credentials"), rubric])
    agent = SimpleNamespace(_generate_rubric=create, rubric_generation_trace=[{"stage": "rubric_generation", "accepted": False}])
    monkeypatch.setattr(generation, "_rubric_agent", lambda *args: agent)
    monkeypatch.setattr(generation, "load_env_file", lambda *args: None)
    tasks = [{"task_id": name, "instruction": "Save marker", "start_url": "https://example.test"}
        for name in ["first", "second"]]
    args = SimpleNamespace(env_file="offline", eval_config=str(pair_factory()["config"]))
    drafts, frozen, metrics = tmp_path / "drafts", tmp_path / "frozen", tmp_path / "generation.json"
    status = generation._draft_catalog(args, tasks, "a" * 64, drafts, frozen, metrics, {"stage": "draft"})
    result = json.loads(metrics.read_text())
    assert status == 1 and result["status"] == "partial"
    assert [row["status"] for row in result["tasks"]] == ["ungraded", "complete"]
    first = json.loads((drafts / "first.metrics.json").read_text())
    assert first["status"] == "ungraded" and first["error_type"] == "UngradedVerifierError"
    assert first["generation_trace"] == agent.rubric_generation_trace
    assert not (drafts / "first.json").exists()
    assert json.loads((drafts / "second.json").read_text())["precomputed_rubric"] == rubric


def test_both_local_packages_match_fixed_manifests():
    receipt = require_local_packages()
    assert set(receipt) == {"screenshot_verifier", "dom_model"}
    assert all(item["file_count"] > 0 for item in receipt.values())


def test_each_runner_imports_from_the_installed_package(tmp_path):
    for module in (
        "w8bench.verifier.screenshot_verifier.runner",
        "w8bench.verifier.dom_model.runner",
    ):
        completed = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr


def test_catalog_draft_dry_preflight_has_no_calls_or_writes(catalog_case, monkeypatch, capsys):
    monkeypatch.setattr(generator.GracefulRetryClient, "from_path",
        lambda *args, **kwargs: pytest.fail("dry preflight constructed a model client"))
    assert generator.main(catalog_case["args"] + ["--stage", "draft"]) == 0
    preflight = json.loads(capsys.readouterr().out)
    assert preflight["paid_calls_authorized"] is False
    assert preflight["models"] == ["gemini-3.1-pro-preview"]
    assert not catalog_case["drafts"].exists()
    assert not catalog_case["frozen"].exists()


def test_catalog_drafts_use_original_workflow_then_resume_without_calls(catalog_case, monkeypatch):
    args = catalog_case["args"] + ["--stage", "draft", "--execute"]
    assert generator.main(args) == 0
    for number in (1, 2):
        receipt = json.loads((catalog_case["drafts"] / f"task_{number:02d}.metrics.json").read_text())
        assert receipt["status"] == "complete" and receipt["rubric_generation_calls"] == 2
        assert receipt["token_usage"]["gemini-3.1-pro-preview"]["total_tokens"] == 10
        assert set(receipt["token_usage"]) == {"gemini-3.1-pro-preview"}
    monkeypatch.setattr(generator.GracefulRetryClient, "from_path",
        lambda *args, **kwargs: pytest.fail("completed rubric was regenerated"))
    assert generator.main(args) == 0
    assert not catalog_case["frozen"].exists()


@pytest.mark.parametrize("previous_transport", [None, "normal", "batch"])
@pytest.mark.parametrize("fails", [False, True])
def test_rubric_preparation_uses_google_and_restores_transport(catalog_case, monkeypatch, previous_transport, fails):
    from w8bench.verifier.batch import judge_transport
    if previous_transport is None:
        monkeypatch.delenv("JUDGE_TRANSPORT", raising=False)
    else:
        monkeypatch.setenv("JUDGE_TRANSPORT", previous_transport)
    original = generator.GracefulRetryClient.from_path
    def client(*args, **kwargs):
        assert judge_transport() == "normal"
        assert kwargs["eval_model"] == "gemini-3.1-pro-preview"
        if fails:
            raise ValueError("synthetic client failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(generator.GracefulRetryClient, "from_path", client)
    args = catalog_case["args"] + ["--stage", "draft", "--execute"]
    if fails:
        with pytest.raises(ValueError, match="synthetic client failure"):
            generator.main(args)
    else:
        assert generator.main(args) == 0
        receipt = json.loads((catalog_case["drafts"] / "task_01.metrics.json").read_text())
        assert receipt["effective_settings"]["transport"] == "normal"
        assert receipt["effective_settings"]["models"] == ["gemini-3.1-pro-preview"]
    assert os.environ.get("JUDGE_TRANSPORT") == previous_transport


def test_rubric_preparation_requires_google_credentials_before_writing(catalog_case, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        generator.main(catalog_case["args"] + ["--stage", "draft", "--execute"])
    assert not catalog_case["drafts"].exists()
    assert not (catalog_case["drafts"].parent / "generation.json").exists()


def test_catalog_freeze_requires_review_approval_and_preserves_weights(catalog_case):
    args = catalog_case["args"]
    generator.main(args + ["--stage", "draft", "--execute"])
    generator.main(args + ["--stage", "review", "--execute"])
    with pytest.raises(ValueError, match="explicit approval"):
        generator.main(args + ["--stage", "freeze", "--execute"])
    review = json.loads(catalog_case["review"].read_text())
    review.update(approved_by="task reviewer", approval_date="2026-11-14")
    for task in review["tasks"]:
        task.update(approved=True, review_notes="All documented checks reviewed against task.")
    catalog_case["review"].write_text(json.dumps(review))
    assert generator.main(args + ["--stage", "freeze"]) == 0
    assert not catalog_case["frozen"].exists()
    assert generator.main(args + ["--stage", "freeze", "--execute"]) == 0
    assert generator.main(args + ["--stage", "freeze", "--execute"]) == 0
    for number in (1, 2):
        frozen = json.loads((catalog_case["frozen"] / f"task_{number:02d}.json").read_text())
        assert frozen["precomputed_rubric"] == RUBRIC
        assert frozen["instruction"].endswith("- Use run-time evidence.")
        assert frozen["rubric_approval_sha256"]


def test_changed_draft_invalidates_prior_approval(catalog_case):
    args = catalog_case["args"]
    generator.main(args + ["--stage", "draft", "--execute"])
    generator.main(args + ["--stage", "review", "--execute"])
    review = json.loads(catalog_case["review"].read_text())
    review.update(approved_by="reviewer", approval_date="2026-11-14")
    for item in review["tasks"]:
        item.update(approved=True, review_notes="Reviewed")
    catalog_case["review"].write_text(json.dumps(review))
    draft = catalog_case["drafts"] / "task_01.json"
    value = json.loads(draft.read_text())
    value["precomputed_rubric"]["items"][0]["description"] = "Corrected observable criterion."
    draft.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="hashes changed"):
        generator.main(args + ["--stage", "freeze", "--execute"])
    generator.main(args + ["--stage", "review", "--execute"])
    updated = json.loads(catalog_case["review"].read_text())
    assert updated["tasks"][0]["approved"] is False
    assert updated["tasks"][1]["approved"] is True
    assert list((catalog_case["review"].parent / "review_history").glob("*.json"))


def test_failed_draft_preserves_calls_and_resume_attempt_history(catalog_case, monkeypatch):
    original = generator.MMRubricAgent._generate_rubric

    async def fail_second(self, task, context):
        if "page 2" in task:
            await self._call_llm([{"role": "user", "content": "attempt"}], self._judge_client)
            raise KeyboardInterrupt()
        return await original(self, task, context)

    monkeypatch.setattr(generator.MMRubricAgent, "_generate_rubric", fail_second)
    with pytest.raises(KeyboardInterrupt):
        generator.main(catalog_case["args"] + ["--stage", "draft", "--execute"])
    path = catalog_case["drafts"] / "task_02.metrics.json"
    receipt = json.loads(path.read_text())
    assert receipt["status"] == "interrupted" and receipt["rubric_generation_calls"] == 1
    assert receipt["token_usage"]["gemini-3.1-pro-preview"]["total_tokens"] == 5
    assert not (catalog_case["drafts"] / "task_02.json").exists()
    monkeypatch.setattr(generator.MMRubricAgent, "_generate_rubric", original)
    generator.main(catalog_case["args"] + ["--stage", "draft", "--execute"])
    saved = json.loads(path.read_text())
    assert saved["status"] == "complete" and saved["attempt_history"][0]["rubric_generation_calls"] == 1


def test_catalog_edit_and_unsafe_task_id_fail_before_generation(catalog_case):
    args = catalog_case["args"]
    generator.main(args + ["--stage", "draft", "--execute"])
    rows = [json.loads(s) for s in catalog_case["catalog"].read_text().splitlines()]
    rows[0]["instruction"] = "Changed task."
    catalog_case["catalog"].write_text("".join(json.dumps(x) + "\n" for x in rows))
    with pytest.raises(ValueError, match="task changed"):
        generator.main(args + ["--stage", "draft", "--execute"])
    rows[0]["task_id"] = "../escape"
    catalog_case["catalog"].write_text("".join(json.dumps(x) + "\n" for x in rows))
    with pytest.raises(Exception, match="task id|Task ID|task-id|task ID"):
        generator.main(args + ["--stage", "draft"])


def test_public_catalog_has_only_eight_fields_and_shared_constraints():
    from collections import Counter
    root = Path(__file__).resolve().parents[2]
    rows = [json.loads(line) for line in (root / "data/tasks.jsonl").read_text().splitlines()]
    fields = {"task_id", "task_name", "category", "difficulty", "instruction", "start_url",
        "stopping_condition", "constraints"}
    assert len(rows) == 40
    assert {row["task_id"] for row in rows} == {f"task_{number:02d}" for number in range(1, 41)}
    assert Counter(row["difficulty"] for row in rows) == {"easy": 10, "medium": 10, "hard": 10, "complex": 10}
    constraints = rows[0]["constraints"]
    assert len(constraints) == 6 and all(isinstance(item, str) and item.strip() for item in constraints)
    for row in rows:
        assert set(row) == fields
        assert row["constraints"] == constraints
        assert len(row["instruction"].splitlines()) == 1 and len(row["instruction"]) <= 1800
        assert len(row["stopping_condition"].splitlines()) == 1
        assert all(isinstance(row[field], str) and row[field].strip() for field in fields - {"constraints"})
        generator.validate_task_definition(generator.catalog_task_instruction(row), row["start_url"])


def test_unreceipted_prior_attempt_is_unknown_not_zero_in_review(catalog_case):
    args = catalog_case["args"]
    generator.main(args + ["--stage", "draft", "--execute"])
    path = catalog_case["drafts"] / "task_02.metrics.json"
    receipt = json.loads(path.read_text())
    receipt.update(status="running")
    receipt.pop("rubric_generation_calls")
    receipt.pop("token_usage")
    path.write_text(json.dumps(receipt))
    (catalog_case["drafts"] / "task_02.json").unlink()
    generator.main(args + ["--stage", "draft", "--execute"])
    generator.main(args + ["--stage", "review", "--execute"])
    review = json.loads(catalog_case["review"].read_text())
    entry = review["tasks"][1]
    assert entry["generation_calls_all_attempts"] is None
    assert entry["generation_calls_known_lower_bound"] == 2
    assert entry["prior_attempt_usage"][0]["token_usage"] is None
    assert entry["generation_cost"]["estimated_usd"] is None


@pytest.mark.parametrize("native", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("stage,reason", [
    ("rubric_rescore", "Invalid earned points after response-repair budget"),
    ("authentication", "AuthenticationError: invalid credentials after endpoint budget"),
])
def test_native_ungraded_blocks_audit_and_excludes_loss_rates(
    full_evaluation, tmp_path, monkeypatch, native, stage, reason
):
    paths, rubric, calls = full_evaluation
    original = comparison._run_logged

    def score(command, log_path):
        original(command, log_path)
        if f"w8bench.verifier.{native}.runner" in command:
            path = log_path.parent / "result.json"
            raw = json.loads(path.read_text())
            raw.update(scoring.ungraded_result(scoring.UngradedVerifierError(stage, reason)),
                intermediate_mm_rubric_steps=None)
            path.write_text(json.dumps(raw))

    monkeypatch.setattr(comparison, "_run_logged", score)
    assert comparison.main(["--run", str(paths["dom"]), "--rubric", str(rubric),
        "--judge-model", "gemini-3.6-flash", "--execute"]) == 1
    receipt = next(tmp_path.rglob("evaluation.json"))
    evaluation = json.loads(receipt.read_text())
    assert evaluation["status"] == "incomplete"
    assert evaluation["preflight"]["status"] == "passed"
    assert evaluation["coverage"]["audit_eligible_states"]
    assert evaluation["stages"]["paired_completion"]["verdict"] == "success"
    assert evaluation["stages"][native]["status"] == "ungraded"
    assert evaluation["stages"][native]["judge_fallback"] == {"stage": stage, "reason": reason}
    other = "dom_model" if native == "screenshot_verifier" else "screenshot_verifier"
    assert evaluation["stages"][other]["status"] == "complete"
    audit = evaluation["stages"]["audit"]
    assert audit["status"] == "blocked" and audit["reason"] == "verifier_results_unavailable"
    assert "metrics" not in audit
    assert not (receipt.parent / "evidence_audit.json").exists()
    assert len(calls["primary"]) == 1 and len(calls["scorers"]) == 2
    assert calls["audit"] == []

    summaries = {arm: summarize(comparison.inspect_recording(path)) for arm, path in paths.items()}
    assert summaries["dom"]["evidence_audit"] is None
    assert summaries["dom"]["evidence_audit_status"] == "blocked"
    assert summaries["dom"]["auxiliary_verifiers"][native]["signals"]["process_score"] is None
    stream = summaries["dom"]["judge_usage_streams"][f"{native}:gemini-3.5-flash-lite"]
    assert stream["usage"]["total_tokens"] == 16
    result = aggregate([{"task_id": "task_01", "trial_id": evaluation["trial_id"],
        "shared_controls": {}, "both_successful": False,
        "successful_pair_turn_delta": None, **summaries}])
    arm = result["modes"]["dom"]
    assert arm["audit_status_counts"] == {"blocked": 1}
    for direction in ("screenshot_evidence_loss", "dom_model_evidence_loss",
                      "screenshot_verifier_misses", "dom_model_verifier_misses"):
        metric = arm["evidence_audit"][direction]
        assert metric == {"count": None, "denominator": None, "rate": None,
                          "audited_runs": 0, "attempted_runs": 1}


def test_batch_resume_does_not_resubmit_answered_or_submitted_items(tmp_path,monkeypatch,batch_providers):
    from w8bench.verifier import batch
    root=tmp_path/'queue';jobs=batch.BatchJobs(root,clients=batch_providers.clients)
    identity={'task':'t','arm':'dom','trial':1,'recording':'hash','profile':'primary'}
    body={'model':'gemini-3.5-flash-lite','messages':[{'role':'user','content':'Saved'}]}
    for _ in range(2):
        with batch.evaluation_scope(root,identity):
            with pytest.raises(batch.BatchPending):batch.request(body,provider='google',endpoint='generateContent',stage='dom.relevance')
        jobs.poll();jobs.submit()
    assert len(batch_providers.batches.created)==1
    batch_providers.batches.finish(0)
    jobs.poll()
    with batch.evaluation_scope(root,identity):
        record={}
        value=batch.request(body,provider='google',endpoint='generateContent',stage='dom.relevance',record=record)
    assert value['status_code']==200 and record['transport']=='batch'
    assert record['batch_job_id']=='batches/job_1'
    assert jobs.submit()==0 and len(batch_providers.batches.created)==1


@pytest.mark.parametrize('state',['expired','failed'])
def test_terminal_batch_keeps_partial_answers_and_retries_only_missing_items(tmp_path,monkeypatch,batch_providers,state):
    from w8bench.verifier import batch
    jobs=batch.BatchJobs(tmp_path,clients=batch_providers.clients)
    bodies=[{'model':'gemini-3.5-flash-lite','messages':[{'role':'user','content':text}]} for text in ('a','b')]
    with batch.evaluation_scope(tmp_path,{'run':'r'}):
        for body in bodies:
            with pytest.raises(batch.BatchPending):batch.request(body,provider='google',endpoint='generateContent',stage='relevance')
    jobs.submit();rows=batch_providers.batches.created[0]['rows']
    first=rows[0]['key']
    batch_providers.batches.finish(0,status=state,results=[{'key':first,'response':{'ok':True}}])
    jobs.poll()
    with batch.evaluation_scope(tmp_path,{'run':'r'}):
        values=[batch.request(body,provider='google',endpoint='generateContent',stage='relevance') for body in bodies]
        assert sorted(v['status_code'] for v in values)==[200,503]
        failed_index=next(i for i,v in enumerate(values) if v['status_code']==503)
        with pytest.raises(batch.BatchPending):batch.request(bodies[failed_index],provider='google',endpoint='generateContent',stage='relevance')
    assert jobs.submit()==1
    assert len(batch_providers.batches.created[1]['rows'])==1
    assert batch_providers.batches.created[1]['rows'][0]['request']==bodies[failed_index]


def test_batch_partial_item_error_preserves_nonretryable_status(tmp_path,batch_providers):
    from w8bench.verifier import batch
    jobs=batch.BatchJobs(tmp_path,clients=batch_providers.clients)
    with batch.evaluation_scope(tmp_path,{'run':'r'}):
        with pytest.raises(batch.BatchPending):batch.request({'model':'gemini-3.5-flash-lite'},provider='google',endpoint='generateContent',stage='validity')
    jobs.submit();key=batch_providers.batches.created[0]['rows'][0]['key']
    batch_providers.batches.finish(0,results=[{'key':key,'error':{'code':3,'message':'Invalid request'}}]);jobs.poll()
    with batch.evaluation_scope(tmp_path,{'run':'r'}):
        assert batch.request({'model':'gemini-3.5-flash-lite'},provider='google',endpoint='generateContent',stage='validity')['status_code']==400


def test_uncertain_batch_creation_is_not_repeated(tmp_path,monkeypatch,batch_providers):
    from w8bench.verifier import batch
    jobs=batch.BatchJobs(tmp_path,clients=batch_providers.clients)
    with batch.evaluation_scope(tmp_path,{'run':'r'}):
        with pytest.raises(batch.BatchPending):batch.request({'model':'gemini-3.5-flash-lite'},provider='google',endpoint='generateContent',stage='relevance')
    original=batch_providers.batches.create
    def accepted_then_disconnected(**kwargs):
        original(**kwargs)
        raise ConnectionError('Submission acknowledgement lost')
    monkeypatch.setattr(batch_providers.batches,'create',accepted_then_disconnected)
    with pytest.raises(ConnectionError):jobs.submit()
    assert len(batch_providers.batches.created)==1
    with pytest.raises(RuntimeError,match='reconciliation'):jobs.poll()
    with pytest.raises(RuntimeError,match='uncertain'):jobs.submit()
    assert len(batch_providers.batches.created)==1


def test_batch_cancellation_refuses_late_writes(tmp_path,batch_providers):
    from w8bench.verifier import batch
    jobs=batch.BatchJobs(tmp_path,clients=batch_providers.clients)
    with batch.evaluation_scope(tmp_path,{'run':'r'}):
        with pytest.raises(batch.BatchPending):batch.request({'model':'gemini-3.5-flash-lite'},provider='google',endpoint='generateContent',stage='relevance')
    jobs.submit();jobs.cancel();batch_providers.batches.finish(0)
    assert batch_providers.batches.cancelled==['batches/job_1']
    with pytest.raises(batch.BatchCancelled):jobs.poll()
    with batch.evaluation_scope(tmp_path,{'run':'r'}):
        with pytest.raises(batch.BatchCancelled):batch.request({'model':'gemini-3.5-flash-lite'},provider='google',endpoint='generateContent',stage='relevance')
    assert not (tmp_path/'responses').exists()


def test_batch_rounds_preserve_dependencies_and_collect_ready_runs(run_pair,tmp_path,monkeypatch,batch_providers):
    from w8bench.verifier import batch,run_comparison as pipeline
    paths,*_=run_pair
    monkeypatch.setenv('JUDGE_TRANSPORT','batch')
    monkeypatch.setattr(pipeline,'BatchJobs',lambda root:batch.BatchJobs(root,clients=batch_providers.clients))
    rubric=tmp_path/'criteria.json';rubric.write_text(json.dumps({'task_id':'task_01'}))
    stages=['relevance','selected_state_analysis','global_rescore','inventory','adjudication']
    def evaluate(args,run,recording):
        for stage in stages:
            if stage == 'adjudication' and args.stage == 'evaluate':
                return 0
            provider='google'
            model='gemini-4-argon' if stage=='adjudication' else 'gemini-3.1-pro-preview' if stage=='inventory' else 'gemini-3.5-flash-lite'
            batch.request({'model':model,'messages':[{'role':'user','content':stage}]},provider=provider,
                endpoint='generateContent',stage=f'audit.{stage}' if stage in {'inventory', 'adjudication'} else stage)
        return 0
    monkeypatch.setattr(pipeline,'_evaluate_recording',evaluate)
    args=['--run',*[str(p) for p in paths.values()],'--rubric',str(rubric),'--judge-model','gemini-3.6-flash','--execute']
    for index,stage in enumerate(stages):
        selected_args = [*args, '--stage', 'adjudicate'] if stage == 'adjudication' else args
        if stage == 'adjudication':
            assert pipeline.main(args) == 0
        assert pipeline.main(selected_args)==75
        created=batch_providers.batches.created[index]
        assert len(created['rows'])==2
        assert all(row['request']['messages'][0]['content']==stage for row in created['rows'])
        # Polling a running job never submits another copy or advances dependencies.
        assert pipeline.main(selected_args)==75 and len(batch_providers.batches.created)==index+1
        batch_providers.batches.finish(index)
    assert pipeline.main([*args, '--stage', 'adjudicate'])==0 and len(batch_providers.batches.created)==len(stages)


def test_invalid_batch_answer_uses_existing_completion_refusal(completion_case,tmp_path,monkeypatch):
    from w8bench.verifier import batch
    case=completion_case
    monkeypatch.setenv('JUDGE_TRANSPORT','batch')
    identity={'run':'r','profile':'primary'}
    args=dict(judge_model='gemini-3.6-flash',execute=True)
    with batch.evaluation_scope(tmp_path/'queue',identity):
        with pytest.raises(batch.BatchPending):asyncio.run(completion.grade_run(case.run,case.rubric_path,**args))
    item=json.loads(next((tmp_path/'queue/requests').glob('*.json')).read_text())
    batch._save(tmp_path/'queue/responses'/f"{item['id']}.json",{'job_id':'job','status_code':200,'body':{
        'modelVersion':'wrong-model','usageMetadata':{'promptTokenCount':7,'candidatesTokenCount':2,'thoughtsTokenCount':0,'totalTokenCount':9},
        'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"criteria":[]}'}]}}]}})
    with batch.evaluation_scope(tmp_path/'queue',identity):
        grade=asyncio.run(completion.grade_run(case.run,case.rubric_path,**args))
    assert grade['method']==grade['verdict']=='ungraded'
    assert grade['usage']['input_tokens']==7 and grade['usage']['output_tokens']==2
    assert grade['transport']=='batch' and grade['refusal_reason']
    # A new grading attempt has its own ID; it never re-submits the answered item.
    with batch.evaluation_scope(tmp_path/'queue',identity):
        monkeypatch.setenv('W8_JUDGE_STAGE_ATTEMPT','2')
        with pytest.raises(batch.BatchPending):asyncio.run(completion.grade_run(case.run,case.rubric_path,**args))
    assert len(list((tmp_path/'queue/requests').glob('*.json')))==2


def test_native_profile_comparison_reuses_completion_and_separates_outputs(full_evaluation,tmp_path,monkeypatch):
    from w8bench.verifier import run_comparison as pipeline
    paths,rubric,calls=full_evaluation
    args=['--run',*[str(path) for path in paths.values()],'--rubric',str(rubric),'--judge-model','gemini-3.6-flash',
        '--judge-transport','normal','--compare-profiles','--execute']
    assert pipeline.main(args)==0
    assert pipeline.main([*args,'--stage','adjudicate'])==0
    assert len(calls['primary'])==2  # One shared grade per independent recording.
    assert len(calls['scorers'])==8 and len(calls['audit'])==8
    report=json.loads(next(tmp_path.rglob('profile_comparison.json')).read_text())
    assert len(report['rows'])==4 and all(row['agreement']==1 for row in report['rows'])
    assert all(subset['agreement'] is None for row in report['rows'] for subset in row['screenshot_only_subsets'].values())
    for path in tmp_path.rglob('evaluation.json'):
        value=json.loads(path.read_text())
        profile='pro' if '/profiles/pro/' in str(path) else 'primary'
        expected='gemini-3.1-pro-preview' if profile=='pro' else 'gemini-3.5-flash-lite'
        assert value['effective_settings']['stages']['dom_model']['models']==[expected,expected]
    assert pipeline.main(args)==0
    assert len(calls['primary'])==2 and len(calls['scorers'])==8 and len(calls['audit'])==8
    assert next(tmp_path.rglob('profile_comparison_2.json')).is_file()


def test_batch_preflight_is_read_only_for_each_profile(full_evaluation,tmp_path):
    from w8bench.verifier import run_comparison as pipeline
    paths,rubric,calls=full_evaluation
    assert pipeline.main(['--run',*[str(path) for path in paths.values()],'--rubric',str(rubric),
        '--judge-model','gemini-3.6-flash','--compare-profiles','--judge-transport','batch'])==0
    assert not list(tmp_path.rglob('batch_jobs')) and not list(tmp_path.rglob('evaluation.json'))
    assert all(not value for value in calls.values())


def test_batch_transport_and_profile_are_bound_but_actor_is_unchanged(run_pair,monkeypatch):
    from w8bench.settings import evaluation_settings,require_same_settings
    from w8bench.verifier import batch
    paths,*_=run_pair;recording=inspect_recording(paths['dom'])
    monkeypatch.setenv('JUDGE_TRANSPORT','normal')
    normal=evaluation_settings(recording,eval_config='config',rubric_hash='r',judge_model='gemini-3.6-flash')
    monkeypatch.setenv('JUDGE_TRANSPORT','batch')
    current=evaluation_settings(recording,eval_config='config',rubric_hash='r',judge_model='gemini-3.6-flash')
    assert normal['actor']==current['actor']
    assert current['stages']['rubric_preparation']['transport']=='normal'
    for name in ('completion','screenshot_verifier','dom_model','inventory','adjudication'):
        assert current['stages'][name]['transport']=='batch'
    with pytest.raises(ValueError,match='transport'):require_same_settings(normal,current)
    monkeypatch.setenv('NATIVE_JUDGE_PROFILE','pro')
    pro=evaluation_settings(recording,eval_config='config',rubric_hash='r',judge_model='gemini-3.6-flash')
    assert pro['actor']==current['actor']
    assert pro['stages']['completion']==current['stages']['completion']
    assert pro['stages']['inventory']==current['stages']['inventory']
    with pytest.raises(ValueError,match='models|judge_profile'):require_same_settings(current,pro)
    monkeypatch.delenv('JUDGE_TRANSPORT')
    assert batch.judge_transport()=='batch'


def test_cancelled_batch_blocks_native_and_completion_result_publication(tmp_path,monkeypatch):
    from w8bench.verifier import batch,common
    from w8bench.verifier.screenshot_verifier.runner import _write_result
    monkeypatch.setenv('JUDGE_TRANSPORT','batch')
    root=tmp_path/'queue'
    with batch.evaluation_scope(root,{'run':'r'}):
        batch.BatchJobs(root).cancel()
        with pytest.raises(batch.BatchCancelled):common.write_json(tmp_path/'grade.json',{'verdict':'success'})
        with pytest.raises(batch.BatchCancelled):_write_result({'score':1},tmp_path/'native')
    assert not (tmp_path/'grade.json').exists() and not (tmp_path/'native/result.json').exists()


def test_invalid_batch_inventory_response_uses_original_validation_budget(pair_factory,tmp_path):
    from tests.evaluation.conftest import _responses
    from w8bench.verifier import batch,audit_requests as audit
    pair=pair_factory()
    inventory,_=_responses()
    options={'criteria':[{'criterion_index':i} for i in range(2)],
        'screenshot_sources':{'screenshot0.png','screenshot1.png'},'dom_sources':{'dom_model0.txt','dom_model1.txt'},
        'screenshot_root':pair['screenshot'],'dom_root':pair['dom']}
    body={'model':'gemini-3.1-pro-preview','messages':[{'role':'user','content':'Audit the evidence.'}]}
    def call(model,messages):
        return batch.request({**body,'messages':messages},provider='google',endpoint='generateContent',stage='audit.inventory')['body']
    with batch.evaluation_scope(tmp_path/'queue',{'run':'r'}):
        with pytest.raises(batch.BatchPending):audit._request_validated_audit(model=body['model'],messages=body['messages'],complete=call,**options)
    first=next((tmp_path/'queue/requests').glob('*.json'));item=json.loads(first.read_text())
    batch._save(tmp_path/'queue/responses'/first.name,{'job_id':'j1','status_code':200,'body':{'criteria':[]}})
    with batch.evaluation_scope(tmp_path/'queue',{'run':'r'}):
        with pytest.raises(batch.BatchPending):audit._request_validated_audit(model=body['model'],messages=body['messages'],complete=call,**options)
    second=next(path for path in (tmp_path/'queue/requests').glob('*.json') if path!=first)
    batch._save(tmp_path/'queue/responses'/second.name,{'job_id':'j2','status_code':200,'body':inventory})
    with batch.evaluation_scope(tmp_path/'queue',{'run':'r'}):
        rows,raw,attempts=audit._request_validated_audit(model=body['model'],messages=body['messages'],complete=call,**options)
    assert attempts==2 and len(rows)==2 and len(list((tmp_path/'queue/requests').glob('*.json')))==2


def test_shared_completion_is_queued_once_across_native_profiles(tmp_path,batch_providers):
    from w8bench.verifier import batch
    body={'contents':[{'role':'user','parts':[{'text':'same paired recording'}]}]}
    for profile in ('primary','pro'):
        with batch.evaluation_scope(tmp_path,{'recording':'r','profile':profile}):
            with pytest.raises(batch.BatchPending):batch.request(body,provider='google',endpoint='generateContent',model='gemini-3.6-flash',stage='completion.paired')
    assert len(list((tmp_path/'requests').glob('*.json')))==1
    jobs=batch.BatchJobs(tmp_path,clients=batch_providers.clients)
    assert jobs.submit()==1 and len(batch_providers.batches.created[0]['rows'])==1


def test_pending_batch_cost_records_keep_known_and_unknown_items(tmp_path,batch_providers):
    from w8bench.verifier import batch
    from w8bench.verifier.run_metrics import _price_stream
    identity={'recording':'r','profile':'primary'}
    jobs=batch.BatchJobs(tmp_path,clients=batch_providers.clients)
    with batch.evaluation_scope(tmp_path,identity):
        for text in ('state 1','state 2'):
            with pytest.raises(batch.BatchPending):batch.request({'model':'gemini-3.5-flash-lite','input':text},
                provider='google',endpoint='generateContent',stage='dom_model.relevance')
    jobs.submit()
    created=batch_providers.batches.created[0]
    answered=created['rows'][0]['key']
    jobs._answer(answered,{'job_id':created['id']},200,{'modelVersion':'gemini-3.5-flash-lite',
        'usageMetadata':{'promptTokenCount':1000,'candidatesTokenCount':100,'thoughtsTokenCount':0,'totalTokenCount':1100}})
    records=jobs.records(identity,'dom_model.','1')
    assert len(records)==2 and {r['status'] for r in records}=={'answered','submitted'}
    stream={'calls':2,'call_records':records,'usage_coverage':'partial'}
    _price_stream(stream)
    assert stream['cost']['estimated_usd'] is None
    assert stream['cost']['known_usage_estimate_usd']==pytest.approx((.30*1000+2.5*100)/2_000_000)
    assert not jobs.records({**identity,'profile':'pro'},'dom_model.','1')


def test_rejected_batch_creation_can_resume_without_an_accepted_job(tmp_path,monkeypatch,batch_providers):
    from w8bench.verifier import batch
    jobs=batch.BatchJobs(tmp_path,clients=batch_providers.clients)
    with batch.evaluation_scope(tmp_path,{'run':'r'}):
        with pytest.raises(batch.BatchPending):batch.request({'model':'gemini-3.5-flash-lite'},provider='google',endpoint='generateContent',stage='relevance')
    original=batch_providers.batches.create
    class Rejected(Exception):status_code=429
    monkeypatch.setattr(batch_providers.batches,'create',lambda **kwargs:(_ for _ in ()).throw(Rejected()))
    with pytest.raises(Rejected):jobs.submit()
    assert not batch_providers.batches.created
    assert json.loads(next((tmp_path/'jobs').glob('*.json')).read_text())['status']=='creation_rejected'
    monkeypatch.setattr(batch_providers.batches,'create',original)
    jobs.poll();assert jobs.submit()==1
    assert len(batch_providers.batches.created)==1


@pytest.mark.parametrize('complete_usage', [False, True])
def test_answered_google_batch_usage_survives_before_stage_consumption(tmp_path, monkeypatch, batch_providers, complete_usage):
    from w8bench.verifier import batch
    from w8bench.verifier.run_metrics import _price_call
    monkeypatch.setenv('JUDGE_TRANSPORT','batch')
    identity = {'recording':'r','profile':'common'}
    body = {'contents':[{'role':'user','parts':[{'text':'result'}]}]}
    with batch.evaluation_scope(tmp_path, identity):
        with pytest.raises(batch.BatchPending):
            batch.request(body, provider='google', endpoint='generateContent', model='gemini-3.6-flash', stage='completion.paired')
    jobs = batch.BatchJobs(tmp_path, clients=batch_providers.clients)
    assert jobs.submit() == 1
    item = batch_providers.batches.created[0]['rows'][0]
    usage = {'promptTokenCount':10, 'candidatesTokenCount':3}
    if complete_usage:
        usage.update(thoughtsTokenCount=2,totalTokenCount=15,cachedContentTokenCount=2)
    batch_providers.batches.finish(0, results=[{'key':item['key'],'response':{
        'modelVersion':'gemini-3.6-flash-001','usageMetadata':usage,
        'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{}'}]}}]}}])
    jobs.poll()
    records = jobs.records(identity, 'completion.', '1')
    assert len(records) == 1 and records[0]['status'] == 'answered'
    assert records[0]['returned_model'] == 'gemini-3.6-flash-001'
    assert records[0]['usage']['prompt_tokens'] == 10
    assert records[0]['usage']['completion_tokens'] == (5 if complete_usage else None)
    amount = _price_call(records[0], {}, set(), set())
    if complete_usage:
        assert amount == pytest.approx(.00001245)
    else:
        assert amount is None


def test_pending_completion_keeps_its_attempt_identity_on_resume(full_evaluation, tmp_path, monkeypatch, batch_providers):
    from w8bench.verifier import batch
    paths, rubric, _ = full_evaluation
    monkeypatch.setattr(comparison, 'BatchJobs', lambda root: batch.BatchJobs(root, clients=batch_providers.clients))
    args = ['--run', str(paths['dom']), '--rubric', str(rubric), '--judge-model',
        'gemini-3.6-flash', '--judge-transport', 'batch', '--execute']
    monkeypatch.setenv('JUDGE_TRANSPORT', 'batch')
    assert comparison.main(args) == 75
    jobs = len(batch_providers.batches.created)
    requests = {p.name for p in tmp_path.rglob('requests/*.json')}
    evaluation = json.loads(next(tmp_path.rglob('evaluation.json')).read_text())
    assert evaluation['stages']['paired_completion']['status'] == 'batch_pending'
    assert comparison.main(args) == 75
    assert len(batch_providers.batches.created) == jobs
    assert {p.name for p in tmp_path.rglob('requests/*.json')} == requests
    assert evaluation['stages']['paired_completion']['attempt_history'] == []
    item = batch_providers.batches.created[0]['rows'][0]
    batch_providers.batches.finish(0, results=[{'key': item['key'], 'response': {
        'modelVersion': 'gemini-3.6-flash',
        'candidates': [{'finishReason':'STOP', 'content':{'parts':[{'text':json.dumps({'criteria': [
            {'id':'done','verdict':'success','reason':'Recorded result','states':[1]}]})}]}}],
        'usageMetadata': {'promptTokenCount':50,'candidatesTokenCount':20,'thoughtsTokenCount':0,'totalTokenCount':70}}}])
    assert comparison.main(args) == 0
    assert comparison.main(args) == 0
    assert len(batch_providers.batches.created) == jobs


@pytest.mark.parametrize('status', ['running', 'interrupted', 'batch_pending'])
def test_unfinished_batch_stage_keeps_its_attempt_namespace(monkeypatch, status):
    monkeypatch.setenv('JUDGE_TRANSPORT', 'batch')
    history = [{'status': 'ungraded', 'usage': {'input_tokens': 4}}]
    assert comparison._attempt_history({'status': status, 'attempt_history': history}) == history


def test_profile_comparison_reports_both_subsets_and_quality(full_evaluation, tmp_path):
    from w8bench.verifier import batch
    paths, rubric, _ = full_evaluation
    assert comparison.main(['--run', str(paths['dom']), '--rubric', str(rubric),
        '--judge-model', 'gemini-3.6-flash', '--compare-profiles', '--execute']) == 0
    assert comparison.main(['--run', str(paths['dom']), '--rubric', str(rubric),
        '--judge-model', 'gemini-3.6-flash', '--compare-profiles', '--stage', 'adjudicate', '--execute']) == 0
    for file in tmp_path.rglob('evaluation.json'):
        profile = 'pro' if '/profiles/pro/' in str(file) else 'primary'
        evaluation = json.loads(file.read_text())
        for mode in ('screenshot_verifier', 'dom_model'):
            evaluation['stages'][mode]['criteria'] = [
                {'criterion': f'C{index}', 'max_points': 1, 'final_points':
                    0 if profile == 'primary' and index == 1 else 1} for index in range(3)]
            evaluation['stages'][mode]['validation_repair_events'] = 2
        evaluation['stages']['audit']['calls'] = [
            {'stage': 'inventory', 'refusal_reason': 'model mismatch'},
            {'stage': 'inventory'}, {'stage': 'adjudication'}]
        file.write_text(json.dumps(evaluation))
        audit_file = file.parent / 'evidence_audit.json'
        audit = json.loads(audit_file.read_text())
        indices = {0, 1} if profile == 'primary' else {1, 2}
        audit['criteria'] = [{'criterion_index': index, 'screenshot': {'coverage': 'COMPLETE'},
            'dom_model': {'coverage': 'PARTIAL' if index in indices else 'COMPLETE'},
            'dom_model_evidence_loss': index in indices} for index in range(3)]
        audit_file.write_text(json.dumps(audit))
    report = batch.compare_profiles([paths['dom']], tmp_path / 'separate_subsets.json')
    for row in report['rows']:
        subsets = row['screenshot_only_subsets']
        assert subsets['primary']['criterion_indices'] == [0, 1]
        assert subsets['pro']['criterion_indices'] == [1, 2]
        assert subsets['union']['criterion_indices'] == [0, 1, 2]
        assert subsets['intersection']['criterion_indices'] == [1]
        assert subsets['primary']['agreement'] == subsets['pro']['agreement'] == 0.5
        assert subsets['union']['agreement'] == pytest.approx(2 / 3)
        assert subsets['intersection']['agreement'] == 0
    for quality in report['profile_quality'].values():
        assert quality['runs'] == 1 and quality['ungraded_native_results'] == 0
        assert quality['native_validation_repair_events'] == 4
        assert quality['audit_repair_attempts'] == 1 and quality['repair_attempts'] == 5
        assert quality['refusals'] == 1
        assert quality['audits_blocked_by_unavailable_native'] == quality['runs_without_loss_values'] == 0
    pro_file = next(file for file in tmp_path.rglob('evaluation.json') if '/profiles/pro/' in str(file))
    value = json.loads(pro_file.read_text())
    value['stages']['dom_model']['status'] = 'ungraded'
    value['stages']['audit'].update(status='blocked', reason='verifier_results_unavailable')
    pro_file.write_text(json.dumps(value))
    report = batch.compare_profiles([paths['dom']], tmp_path / 'missing_audit.json')
    assert report['profile_quality']['pro']['ungraded_native_results'] == 1
    assert report['profile_quality']['pro']['audits_blocked_by_unavailable_native'] == 1
    assert report['profile_quality']['pro']['runs_without_loss_values'] == 1
    row, = report['rows']
    assert row['format'] == 'screenshot_verifier'
    assert row['screenshot_only_subsets']['primary']['criterion_indices'] == [0, 1]
    for name in ('pro', 'union', 'intersection'):
        assert row['screenshot_only_subsets'][name]['available'] is False
        assert row['screenshot_only_subsets'][name]['agreement'] is None
        assert row['screenshot_only_subsets'][name]['criteria'] is None

@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_empty_exports_reach_completion_native_verifiers_and_audit(empty_dom_pair, tmp_path, mode):
    from w8bench.task_recorder.capture import EMPTY_DOM_MARKER
    from w8bench.verifier.audit_evidence import shared_trajectory_payload
    from w8bench.verifier.dom_model.states import load_dom_model_states
    from w8bench.verifier.validate_inputs import dataset_only_preflight
    from tests.evaluation.conftest import _complete, _finding, _responses, _run, _source_decision
    paths, *_ = empty_dom_pair
    recording = inspect_recording(paths[mode])
    exported = prepare_recording(recording, tmp_path/"staged")
    ss, dom = Path(exported["screenshot_task"]), Path(exported["dom_task"])
    dataset_only_preflight(ss, dom)
    states = load_dom_model_states(dom, action_count=len(recording["manifest"]["steps"]))
    assert len(states) == len(recording["manifest"]["states"])
    assert all(EMPTY_DOM_MARKER in state.raw_text for state in states)
    context = shared_trajectory_payload(ss, dom)["evaluation_context"]
    assert context["audit_eligible_states"] == context["expected_state_ids"]
    assert context["format_gaps"] == {"screenshot": [], "dom_model": []}
    payload = completion._judge_payload(paths[mode], recording, [], "paired")
    assert EMPTY_DOM_MARKER in json.dumps(payload)
    assert "Recorder evidence unavailable" not in json.dumps(payload)
    assert sum("inlineData" in part for part in payload["contents"][0]["parts"]) == len(states)
    rubric = tmp_path/"rubric.json"
    write_json(rubric, {"task_id": "task_01", "precomputed_rubric": RUBRIC})
    inventory, adjudication = _responses()
    for proposal, final in zip(inventory["criteria"], adjudication["criteria"]):
        proposal.update(dom_model=_source_decision("dom_model", coverage="ABSENT"),
            screenshot_evidence_loss=False, dom_model_evidence_loss=True,
            explanation="The required visible fact is absent from the empty DOM export.")
        final.update(dom_model_evidence_loss=_finding(True, evidence="Saved", modality="screenshot"),
            explanation="Screenshot evidence establishes the fact; DOM has no exported content.")
    pair = {"screenshot": ss, "dom": dom, "rubric": rubric, "staged": tmp_path,
        "task": {"task_id": "task_01"}}
    result = _run(pair, _complete(inventory, adjudication))
    assert result["metrics"]["dom_model_evidence_loss"] == {"count": 2, "denominator": 2, "rate": 1.0}
    assert result["metrics"]["screenshot_evidence_loss"] == {"count": 0, "denominator": 2, "rate": 0.0}
