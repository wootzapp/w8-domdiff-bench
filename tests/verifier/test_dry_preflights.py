import json
import hashlib
from pathlib import Path

import pytest

from w8bench.verifier.dom_model.runner import parse_args as parse_dom_args, run as run_dom
from w8bench.verifier.run_comparison import main as comparison_main, prepare_isolated_inputs
from w8bench.verifier import run_comparison as comparison
from .conftest import tree_digest


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


def test_isolated_inputs_preserve_every_source_byte_and_action(pair_factory, tmp_path):
    pair = pair_factory()
    before = tree_digest(pair["staged"])
    screenshot, dom, rubric, metrics = prepare_isolated_inputs(
        screenshot_task=pair["screenshot"], dom_task=pair["dom"], rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"], run_root=tmp_path / "evaluation", action_count=1)
    assert tree_digest(pair["staged"]) == before
    assert (dom / "dom_model0.txt").read_bytes() == (pair["dom"] / "dom_model0.txt").read_bytes()
    assert (dom / "dom_model1.txt").read_bytes() == (pair["dom"] / "dom_model1.txt").read_bytes()
    assert (screenshot / "web_surfer.log").read_bytes() == (dom / "web_surfer.log").read_bytes()
    assert json.loads((screenshot / "final_answer.json").read_text())["screenshots"] == ["screenshot0.png", "screenshot1.png"]
    assert rubric.read_bytes() == pair["rubric"].read_bytes()
    assert metrics.read_bytes() == pair["metrics"].read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        prepare_isolated_inputs(screenshot_task=pair["screenshot"], dom_task=pair["dom"], rubric_file=pair["rubric"],
            generation_metrics=pair["metrics"], run_root=tmp_path / "evaluation", action_count=1)


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
    assert comparison_main(["--run", str(recording), "--rubric", str(rubric), "--judge-model", "gpt-5.6-sol"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["model_calls"] == 0 and receipt["writes_performed"] is False
    assert seen == []
    assert list(recording.iterdir()) == []


from tests.turn_benchmark.test_modes import run_pair, no_network
from w8bench.verifier import evidence_audit
from w8bench.verifier.common import canonical_sha256


@pytest.fixture
def full_evaluation(run_pair, tmp_path, monkeypatch):
    paths, *_ = run_pair
    rubric = tmp_path / "criteria.json"
    rubric.write_text(json.dumps({"task_id": "task_01", "instruction": "Report done.", "start_url": "https://example.test",
        "criteria": [{"id": "done", "description": "The requested result is visibly established."}]}))
    calls = {"primary": [], "scorers": [], "audit": []}
    monkeypatch.setattr(comparison, "load_env", lambda path: None)
    def grade_post(self, payload):
        calls["primary"].append(payload)
        return {"id": "grade-response", "model": "gpt-5.6-sol", "status": "completed",
            "output_text": json.dumps({"criteria": [{"id": "done", "verdict": "success", "reason": "Mock established result", "states": [1]}]}),
            "usage": {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}}
    monkeypatch.setattr(comparison.ModelClient, "_post", grade_post)
    def score(command, log_path):
        calls["scorers"].append(command)
        frozen = json.loads(Path(command[command.index("--rubric-file") + 1]).read_text())["precomputed_rubric"]
        rows = [{**item, "earned_points": item["max_points"], "post_image_earned_points": item["max_points"],
                 "post_dom_earned_points": item["max_points"]} for item in frozen["items"]]
        result = {"task_id": "task_01", "rubric_sha256": canonical_sha256(frozen), "criterion_denominator": 1,
            "rubric_total_max_points": 1, "rubric_total_earned_points": 1, "rubric_score": 1, "rubric_is_success": True,
            "outcome": {"output_success": True}, "intermediate_mm_rubric_steps": {"step6_rescoring_summary": rows},
            "token_usage": {"judge": {"prompt_tokens": 10, "completion_tokens": 6, "reasoning_tokens": 2, "total_tokens": 16}},
            "call_metrics": {"judge": {"logical_calls": 1, "api_attempts": 1}}}
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Mock verifier complete\n")
        (log_path.parent / "result.json").write_text(json.dumps(result))
    monkeypatch.setattr(comparison, "_run_logged", score)
    original_audit = evidence_audit.run_evidence_audit
    def audit(**kwargs):
        calls["audit"].append(kwargs)
        def complete(model, messages):
            final = messages[0]["content"] == evidence_audit.ADJUDICATION_SYSTEM_PROMPT
            kwargs["call_records"].append({"stage": "adjudication" if final else "inventory", "response_model": model,
                "usage": {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20}})
            if final:
                false = {"confirmed": False, "decisive_evidence": "", "citations": [], "explanation": "Mock no loss"}
                return {"criteria": [{"criterion_index": 0, "explanation": "Mock paired conclusion",
                    **{field: dict(false) for field in ("screenshot_evidence_loss", "dom_model_evidence_loss", "screenshot_verifier_miss", "dom_model_verifier_miss")}}]}
            dom = next(Path(kwargs["dom_dir"]).glob("dom_model*.txt"))
            lines = dom.read_text().splitlines()
            line = next(index for index, text in enumerate(lines, 1) if text.strip())
            return {"criteria": [{"criterion_index": 0, "required_evidence": "Requested result",
                "screenshot": {"coverage": "COMPLETE", "available_evidence": ["Mock recorded page"], "missing_required_evidence": [],
                    "verifier_caught": True, "citations": [{"source": "screenshot1.png", "location": "viewport", "quote": "Mock recorded page"}]},
                "dom_model": {"coverage": "COMPLETE", "available_evidence": [lines[line - 1]], "missing_required_evidence": [],
                    "verifier_caught": True, "citations": [{"source": dom.name, "location": f"L{line}", "quote": lines[line - 1]}]},
                "screenshot_evidence_loss": False, "dom_model_evidence_loss": False, "explanation": "Mock complete evidence"}]}
        return original_audit(**kwargs, complete=complete)
    monkeypatch.setattr(evidence_audit, "run_evidence_audit", audit)
    return paths, rubric, calls


@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_full_pipeline_freezes_inputs_grades_both_formats_and_resumes(full_evaluation, tmp_path, mode):
    paths, rubric, calls = full_evaluation
    before = comparison.inspect_recording(paths[mode])["recording_sha256"]
    args = ["--run", str(paths[mode]), "--rubric", str(rubric), "--judge-model", "gpt-5.6-sol", "--execute"]
    assert comparison.main(args) == 0
    output = next(tmp_path.rglob("evaluation.json"))
    value = json.loads(output.read_text())
    assert value["status"] == "complete"
    assert set(value["stages"]) == {"paired_completion", "screenshot_verifier", "dom_model", "audit"}
    assert len(calls["primary"]) == 1 and len(calls["scorers"]) == 2 and len(calls["audit"]) == 1
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
    assert len(calls["primary"]) == 1 and len(calls["scorers"]) == 2 and len(calls["audit"]) == 1
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
    assert comparison.main(["--run", str(source), "--rubric", str(rubric), "--judge-model", "gpt-5.6-sol", "--execute"]) == 1
    output = next(tmp_path.rglob("evaluation.json"))
    value = json.loads(output.read_text())
    available, absent = ("dom_model", "screenshot_verifier") if mode == "dom" else ("screenshot_verifier", "dom_model")
    assert value["stages"]["paired_completion"]["verdict"] == "success"
    assert value["stages"][available]["status"] == "complete"
    assert value["stages"][absent]["status"] == "not_available"
    assert value["stages"]["audit"]["status"] == "not_eligible"
    assert value["coverage"]["audit_eligible_states"] == []
    assert len(calls["primary"]) == len(calls["scorers"]) == 1 and calls["audit"] == []


@pytest.mark.parametrize("interrupted_stage", ["paired_completion", "screenshot_verifier", "audit"])
def test_interrupted_judge_stages_retain_attempt_cost_history_on_resume(full_evaluation, tmp_path, monkeypatch, interrupted_stage):
    paths, rubric, calls = full_evaluation
    args = ["--run", str(paths["dom"]), "--rubric", str(rubric), "--judge-model", "gpt-5.6-sol", "--execute"]
    if interrupted_stage == "paired_completion":
        original = comparison.ModelClient._post
        def interrupt(self, payload):
            raise KeyboardInterrupt()
        monkeypatch.setattr(comparison.ModelClient, "_post", interrupt)
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
            kwargs["call_records"].append({"stage": "inventory", "response_model": "gpt-5.6-sol", "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9}})
            raise KeyboardInterrupt()
        monkeypatch.setattr(evidence_audit, "run_evidence_audit", interrupt)
    with pytest.raises(KeyboardInterrupt):
        comparison.main(args)
    output = next(tmp_path.rglob("evaluation.json"))
    interrupted = json.loads(output.read_text())["stages"][interrupted_stage]
    assert interrupted["status"] == "interrupted" and interrupted["usage_coverage"] == "unknown"
    if interrupted_stage == "paired_completion":
        monkeypatch.setattr(comparison.ModelClient, "_post", original)
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


def test_logged_verifier_attempts_append_instead_of_erasing_failure_output(tmp_path, monkeypatch):
    from types import SimpleNamespace
    outcomes = [SimpleNamespace(returncode=1, stdout="first attempt failed\n"), SimpleNamespace(returncode=0, stdout="second attempt complete\n")]
    monkeypatch.setattr(comparison.subprocess, "run", lambda *args, **kwargs: outcomes.pop(0))
    log = tmp_path / "run.log"
    with pytest.raises(RuntimeError):
        comparison._run_logged(["offline-command"], log)
    comparison._run_logged(["offline-command"], log)
    assert "first attempt failed" in log.read_text() and "second attempt complete" in log.read_text()


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
    assert comparison.main(["--run", str(paths["dom"]), "--rubric", str(rubric), "--judge-model", "gpt-5.6-sol", "--execute"]) == 0
    stage = json.loads(next(tmp_path.rglob("evaluation.json")).read_text())["stages"]["screenshot_verifier"]
    assert stage["judgment_quality"] == "fallback_observed"
    assert stage["fallback_counts"] == {"zero_relevance": 1, "baseline_rescore": 1,
        "no_penalties": 1, "unknown_outcome": 1, "evidence_analysis": 1}
    assert stage["signals"]["process_score"] == 1 and stage["signals"]["frozen_full_score"] is True


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
    args = ["--run", str(source), "--rubric", str(rubric), "--judge-model", "gpt-5.6-sol", "--execute"]
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



def test_missing_audit_credential_does_not_block_primary_or_original_verifiers(full_evaluation, tmp_path, monkeypatch):
    paths, rubric, calls = full_evaluation
    monkeypatch.delenv("GEMINI_API_KEY")
    assert comparison.main(["--run", str(paths["dom"]), "--rubric", str(rubric), "--judge-model", "gpt-5.6-sol", "--execute"]) == 1
    evaluation = json.loads(next(tmp_path.rglob("evaluation.json")).read_text())
    assert evaluation["stages"]["paired_completion"]["verdict"] == "success"
    assert evaluation["stages"]["screenshot_verifier"]["status"] == "complete"
    assert evaluation["stages"]["dom_model"]["status"] == "complete"
    assert evaluation["stages"]["audit"]["reason"] == "audit_configuration_failed"
    assert "Google credentials" in evaluation["stages"]["audit"]["error"]
    assert len(calls["primary"]) == 1 and len(calls["scorers"]) == 2 and calls["audit"] == []


@pytest.mark.parametrize("usage,coverage", [(None, "unknown"), ({}, "unknown"),
    ({"input_tokens": None, "output_tokens": None}, "unknown"),
    ({"input_tokens": 0}, "unknown"), ({"input_tokens": 0, "output_tokens": 0}, "complete")])
def test_primary_usage_coverage_requires_both_reported_components(full_evaluation, tmp_path, monkeypatch, usage, coverage):
    paths, rubric, calls = full_evaluation
    original = comparison.ModelClient._post
    def respond(self, payload):
        response = original(self, payload)
        response["usage"] = usage
        return response
    monkeypatch.setattr(comparison.ModelClient, "_post", respond)
    assert comparison.main(["--run", str(paths["dom"]), "--rubric", str(rubric),
        "--judge-model", "gpt-5.6-sol", "--execute"]) == 0
    stage = json.loads(next(tmp_path.rglob("evaluation.json")).read_text())["stages"]["paired_completion"]
    assert stage["usage_coverage"] == coverage
