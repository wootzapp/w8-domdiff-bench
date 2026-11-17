"""Offline completion, rubric, source-integrity and task-validity behavior."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from w8bench.verifier import completion, package_manifests, validity
from w8bench.verifier.common import validate_rubric




def judge_response(verdicts, *, states=None):
    return {"id": "offline-grade", "model": "gpt-6.1-sol", "status": "completed",
        "usage": {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28},
        "output_text": json.dumps({"criteria": [
            {"id": identity, "verdict": verdict, "reason": "Recorded marker evidence.",
                "states": [1] if states is None else states}
            for identity, verdict in zip(("saved", "source"), verdicts)]})}


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
        judge_model="gpt-6.1-sol", api_key="offline-key", execute=True))
    assert result["verdict"] == expected
    assert [row["id"] for row in result["criteria"]] == ["saved", "source"]
    assert result["usage"]["total_tokens"] == 28 and result["judge_calls"] == 1
    payload, = case.requests
    content = payload["input"][0]["content"]
    shared = json.loads(content[0]["text"])
    assert shared["frozen_criteria"] == case.rubric["criteria"]
    assert shared["observed_url_timeline"] == case.recording["coverage"]["observed_url_timeline"]
    assert any(part.get("text") == "Marker: SAVED\n" for part in content)
    assert any(part["type"] == "input_image" for part in content)
    assert all("[ref=e1]" not in part.get("text", "") for part in content)
    assert json.loads((case.run / "completion.json").read_text())["verdict"] == expected


@pytest.mark.parametrize("states", [[], [0], [2], [True], [1.0], ["1"]])
def test_completion_rejects_success_without_real_integer_state_citations(completion_case, states):
    case = completion_case
    case.responses.append(judge_response(("success", "success"), states=states))
    result = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gpt-6.1-sol", api_key="offline-key", execute=True))
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
            judge_model="gpt-6.1-sol", api_key="offline-key", execute=True))
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
        judge_model="gpt-6.1-sol", api_key="offline-key", execute=True))
    assert result["verdict"] == "uncertain"
    content = case.requests[0]["input"][0]["content"]
    assert {"type": "input_text", "text": "Recorder evidence unavailable: screenshot.png"} in content
    assert all(part["type"] != "input_image" for part in content)


def test_completion_refuses_to_save_if_source_identity_changes(completion_case, monkeypatch):
    case = completion_case
    case.responses.append(judge_response(("success", "success")))
    snapshots = [deepcopy(case.recording), {**case.recording, "recording_sha256": "b" * 64}]
    monkeypatch.setattr(completion, "inspect_recording", lambda path: snapshots.pop(0))
    with pytest.raises(ValueError, match="recording changed during grading"):
        asyncio.run(completion.grade_run(case.run, case.rubric_path,
            judge_model="gpt-6.1-sol", api_key="offline-key", execute=True))
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


@pytest.mark.parametrize("points", [0, -1, True, float("nan"), float("inf"), "3"])
def test_frozen_rubric_refuses_invalid_weights(points):
    rubric = {"items": [{"criterion": "Saved marker", "description": "The marker is visible.",
        "max_points": points, "justification": "", "earned_points": ""}]}
    with pytest.raises(ValueError, match="positive and finite"):
        validate_rubric(rubric)


def test_task_validity_retries_malformed_answers_without_trajectory_context():
    answer = {"reasoning_is_ambiguous": "The requested marker is explicit.", "is_ambiguous": False,
        "ambiguity_codes": [], "reasoning_is_invalid": "The source is public.",
        "is_invalid": False, "invalid_task_codes": []}
    client = SimpleNamespace(create=AsyncMock(side_effect=[SimpleNamespace(content="not json"),
        SimpleNamespace(content=json.dumps(answer))]), supports_json=lambda: True)
    result = asyncio.run(validity.classify_task("Read the saved marker.", "https://example.test/marker",
        client, prompt_template="Task: $task_definition\nURL: $url\nDate: $date\nApps: $apps",
        date="2026-11-17", logger=logging.getLogger("offline-validity")))
    assert result.score == 1 and result.is_invalid is False and result.is_ambiguous is False
    assert client.create.await_count == 2
    messages = client.create.call_args.kwargs["messages"]
    assert "Date: 2026-11-17" in messages[1]["content"]
    assert "Please ensure your output follows the exact JSON format" in messages[-1]["content"]
    assert all("trajectory" not in message["content"].casefold() for message in messages)


def test_task_validity_exhaustion_reports_unknown_instead_of_valid():
    client = SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(content="{}")),
        supports_json=lambda: True)
    result = asyncio.run(validity.classify_task("Read marker.", "https://example.test", client,
        prompt_template="$task_definition $url $date $apps", date="2026-11-17",
        logger=logging.getLogger("offline-validity")))
    assert client.create.await_count == 5
    assert result.score is None and result.is_invalid is None and result.is_ambiguous is None
    assert "Failed after 5 attempts" in result.reasoning


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("rescore_valid", [True, False])
def test_native_verifier_flow_reuses_frozen_rubric_and_keeps_outcome_separate(tmp_path, mode, rescore_valid):
    """The real native pipeline consumes mocked client answers at every stage."""
    from importlib import import_module
    from PIL import Image
    from w8bench.verifier.clients.messages import CreateResult
    module = import_module(f"w8bench.verifier.{mode}.rubric_agent")
    if mode == "dom_model":
        from w8bench.verifier.dom_model.evidence import DomModelRubricAgent
        agent_type = DomModelRubricAgent
        evidence_key, score_key, justification_key = "evidence_dir", "post_dom_earned_points", "post_dom_justification"
        (tmp_path / "dom_model0.txt").write_text("URL: https://example.test\nTitle: Saved marker\nMarker: SAVED\n")
        actions = []
        evidence_analysis = {"dom_model_evidence": "DOM_MODEL_STATE_INDEX: 0; Marker: SAVED",
            "criterion_analysis": "EVIDENCE_STATUS: SUPPORTED\nThe saved marker is explicit."}
    else:
        agent_type = module.MMRubricAgent
        evidence_key, score_key, justification_key = "screenshots_dir", "post_image_earned_points", "post_image_justification"
        Image.new("RGB", (24, 16), "white").save(tmp_path / "screenshot_1.png")
        actions = [{"id": 1, "screenshot": "screenshot_1.png"}]
        evidence_analysis = {"screenshot_evidence": "The SAVED marker is visible.",
            "criterion_analysis": "The saved marker meets the criterion."}
    evidence_analysis.update(discrepancies="None", environment_issues_confirmed=False)
    rubric = {"items": [{"criterion": "Saved marker", "description": "The SAVED marker is established.",
        "max_points": 10, "earned_points": "", "justification": ""}]}
    original = deepcopy(rubric)
    task_validity = {"reasoning_is_ambiguous": "The marker is specified.", "is_ambiguous": False,
        "ambiguity_codes": [], "reasoning_is_invalid": "The public page is accessible.",
        "is_invalid": False, "invalid_task_codes": []}
    action_answers = [
        {"items": [{"criterion": "Saved marker", "earned_points": 0, "justification": "Actions alone do not prove the marker."}]},
        task_validity, task_validity,
    ]
    judge_answers = [
        {"criterion_0": 10}, evidence_analysis,
        {"reality_checks": [{"criterion_idx": 0, "reality_notes": "The marker is directly observable."}]},
        {"items": [{"criterion_idx": 0, "applicable_evidence": "The saved marker.",
            score_key: 10, justification_key: "The marker is explicitly established."}]} if rescore_valid else {},
        {"reasoning": "No unsolicited state changes.", "requires_penalty": False, "penalty_criteria": []},
        {"primary_intent": "Establish the saved marker.", "reasoning": "The recorded marker meets the task.", "output_success": True},
        {"reasoning": "The task is complete.", "has_failure": False, "failure_points": []},
    ]
    action_client = SimpleNamespace(create=AsyncMock(side_effect=[CreateResult(content=json.dumps(value)) for value in action_answers]),
        supports_json=lambda: True)
    judge_client = SimpleNamespace(create=AsyncMock(side_effect=[CreateResult(content=json.dumps(value)) for value in judge_answers]),
        supports_json=lambda: True)
    config = module.MMRubricAgentConfig(action_client=action_client, judge_client=judge_client,
        max_iters=1, validity_date="2026-11-17",
        action_definitions={"wait": {"seconds"}}, **{evidence_key: str(tmp_path)})
    agent = agent_type(config=config)
    agent_input = {"task": "Establish the saved marker.",
        "action_history": "", "predicted_output": "SAVED", "actions_list": actions,
        "init_url": "https://example.test", "precomputed_rubric": rubric,
        evidence_key: str(tmp_path), "redo_eval": True}
    if not rescore_valid:
        from w8bench.verifier.rubric_scoring import UngradedVerifierError
        with pytest.raises(UngradedVerifierError, match="rubric_rescore"):
            asyncio.run(agent._generate_reply(agent_input))
        assert rubric == original
        assert action_client.create.await_count == 1 and judge_client.create.await_count == 4
        return
    result = asyncio.run(agent._generate_reply(agent_input))
    scored, outcome = agent._wrap_result(result)
    assert rubric == original
    assert scored.total_max_points == 10
    assert scored.total_earned_points == 10
    assert scored.rubric_is_success is True
    assert outcome.output_success is True
    assert result["items"][0]["criterion"] == "Saved marker"
    assert result["items"][0]["max_points"] == 10
    assert action_client.create.await_count == 3 and judge_client.create.await_count == 7
    assert result["task_verification"]["is_invalid"] is False
    assert result["task_verification_with_trajectory"]["is_invalid"] is False


@pytest.mark.parametrize("score_field", ["post_dom_earned_points", "post_image_earned_points"])
@pytest.mark.parametrize("condition_met,expected", [(False, (12, 6)), (True, (15, 9))])
def test_rubric_arithmetic_counts_nested_applicable_criteria_and_penalties(score_field, condition_met, expected):
    from w8bench.verifier.rubric_scoring import compute_final_scores
    rubric = {"items": [
        {"criterion": "Group", "items": [
            {"criterion": "Source", "max_points": 4, score_field: 4},
            {"criterion": "Result", "max_points": 6, score_field: 2}]},
        {"criterion": "Conditional", "condition": "A dialog appears", "is_condition_met": condition_met,
            "max_points": 3, score_field: 3},
        {"criterion": "Unsolicited effect", "penalty": True, "max_points": 2, score_field: 0},
    ]}
    assert compute_final_scores(rubric, score_field) == {
        "total_max_points": expected[0], "total_earned_points": expected[1]}
    assert compute_final_scores({"items": []}, score_field) == {
        "total_max_points": 0, "total_earned_points": 0}


@pytest.mark.parametrize("mode,score_field,reason_field", [
    ("dom_model", "post_dom_earned_points", "post_dom_justification"),
    ("screenshot_verifier", "post_image_earned_points", "post_image_justification"),
])
def test_rubric_score_reset_preserves_definitions_and_input(mode, score_field, reason_field):
    from w8bench.verifier.rubric_scoring import clear_rubric_scores
    criterion = {"criterion": "Result", "description": "The result is explicit.", "max_points": 10,
        "earned_points": 4, "justification": "Partial action support.", score_field: 9,
        reason_field: "Visible result.", "condition": "A result appears", "is_condition_met": True,
        "applicable_evidence": "State 1", "reality_notes": "Observable"}
    rubric = {"items": [{"criterion": "Group", "items": [deepcopy(criterion),
        {"criterion": "Penalty", "penalty": True, "max_points": 2, "earned_points": 0}]}],
        "total_earned_points": 9}
    original = deepcopy(rubric)
    result = clear_rubric_scores(rubric, evidence_mode=mode)
    assert rubric == original
    expected = {key: value for key, value in criterion.items() if key in
        {"criterion", "description", "max_points", "condition"}}
    expected.update(earned_points="", justification="")
    assert result == {"items": [{"criterion": "Group", "items": [expected]}]}


def test_rubric_median_preserves_the_selected_instances_evidence():
    from w8bench.verifier.rubric_scoring import select_median_instance
    runs = [({"marker": "highest"}, 1.0, {"state": 3}),
        ({"marker": "lowest"}, 0.0, {"state": 1}),
        ({"marker": "middle"}, 0.5, {"state": 2})]
    index, rubric, score, evidence = select_median_instance(runs)
    assert (index, rubric, score, evidence) == (2, {"marker": "middle"}, 0.5, {"state": 2})


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("tokens,accepted", [(115000, True), (115001, False)])
def test_verifier_input_guard_checks_the_boundary_before_transport(mode, tokens, accepted):
    from w8bench.verifier.clients.messages import CreateResult
    from w8bench.verifier.clients.retry import GracefulRetryClient
    endpoint = SimpleNamespace(description="offline-verifier", endpoint="offline-verifier",
        count_tokens=lambda **kwargs: tokens,
        create=AsyncMock(return_value=CreateResult(content='{"marker":"SAVED"}')))
    pool = GracefulRetryClient(clients=[endpoint], max_tokens=115000,
        max_retries=1, evidence_mode=mode)
    messages = [{"role": "user", "content": "Read the saved marker."}]
    if accepted:
        result = asyncio.run(pool.create(messages=messages, json_output=True))
        assert json.loads(result.content) == {"marker": "SAVED"}
        endpoint.create.assert_awaited_once_with(messages=messages, tools=(),
            json_output=True, extra_create_args={})
    else:
        with pytest.raises(RuntimeError, match="115001 tokens exceeding 115000"):
            asyncio.run(pool.create(messages=messages, json_output=True))
        endpoint.create.assert_not_awaited()
