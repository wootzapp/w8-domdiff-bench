"""Offline numeric, retry, prompt and citation contracts for native evaluation."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from importlib import import_module
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import openai
import pytest

from w8bench.verifier import rubric_scoring as scoring
from w8bench.verifier.common import rubric_receipt


def native_agent(mode, *, responses=(), max_iters=2):
    module = import_module(f"w8bench.verifier.{mode}.rubric_agent")
    client = SimpleNamespace(create=AsyncMock(side_effect=[
        SimpleNamespace(content=json.dumps(value)) for value in responses]),
        supports_json=lambda: True)
    return module.MMRubricAgent(config=module.MMRubricAgentConfig(
        action_client=client, judge_client=client, max_iters=max_iters)), client


def test_fractional_rubric_denominator_matches_score_arithmetic(tmp_path):
    rubric = {"items": [{"criterion": "Saved", "max_points": 1.5, "earned_points": 1.5}]}
    receipt = rubric_receipt(path=str(tmp_path / "rubric.json"), sha256="a" * 64, rubric=rubric)
    assert receipt["criterion_denominator"] == 1.5
    assert receipt["criterion_denominator"] == scoring.compute_final_scores(rubric, "earned_points")["total_max_points"]


@pytest.mark.parametrize("score", [-1, 11, True, float("nan"), float("inf"), None])
@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_native_baseline_rejects_invalid_earned_points(mode, score):
    item = {"criterion": "Saved", "max_points": 10, "earned_points": score, "justification": "Recorded marker."}
    with pytest.raises((AssertionError, ValueError)):
        scoring.verify_rubric({"items": [item]}, evidence_mode=mode)


@pytest.mark.parametrize("score", [True, False, float("nan"), float("inf"), -1, 11])
@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_native_rescore_rejects_invalid_earned_points(mode, score):
    prefix = "post_dom" if mode == "dom_model" else "post_image"
    with pytest.raises(ValueError):
        scoring.validate_rescore({"applicable_evidence": "State 0", f"{prefix}_justification": "Recorded marker.",
            f"{prefix}_earned_points": score}, 10, evidence_mode=mode)


def test_missing_baseline_score_cannot_become_zero():
    rubric = {"items": [{"criterion": "Saved", "max_points": 10, "earned_points": "", "justification": ""}]}
    with pytest.raises(ValueError, match="earned_points"):
        scoring.graft_scores_onto_rubric(rubric, {"items": [{"criterion": "Saved", "justification": "Recorded marker."}]})


@pytest.mark.parametrize("score_field", ["earned_points", "post_dom_earned_points", "post_image_earned_points"])
@pytest.mark.parametrize("score", [None, True, -1, 11, float("nan"), float("inf")])
def test_score_arithmetic_refuses_unknown_or_invalid_earned_points(score_field, score):
    item = {"criterion": "Saved", "max_points": 10}
    if score is not None:
        item[score_field] = score
    with pytest.raises(ValueError):
        scoring.compute_final_scores({"items": [item]}, score_field)


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("stage", ["baseline", "whole_rescore", "criterion_rescore", "penalty"])
def test_exhausted_scoring_stage_is_ungraded_instead_of_a_score(mode, stage):
    agent, client = native_agent(mode, responses=[{}, {}])
    item = {"criterion": "Saved", "description": "Marker is saved", "max_points": 10,
        "earned_points": 4, "justification": "Actions support part of the request."}
    rubric = {"items": [item]}
    context = dict(task="Save marker", init_url_context="", action_history="", predicted_output="", actions_list=[])
    async def exercise():
        if stage == "baseline":
            return await agent._score_action_history(context, rubric)
        if stage == "whole_rescore":
            return await agent._rescore_rubric(rubric, {}, "Save marker", "", "", "")
        if stage == "criterion_rescore":
            return await agent._rescore_one_criterion([], item, 0)
        return await agent._detect_unsolicited_side_effects(rubric, {}, "Save marker", "", "")
    with pytest.raises(RuntimeError, match="ungraded"):
        asyncio.run(exercise())
    assert client.create.await_count == 2
    assert agent.score_field not in item


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_native_rescore_repairs_invalid_number_then_accepts_fractional_score(mode):
    prefix = "post_dom" if mode == "dom_model" else "post_image"
    valid = {"criterion_idx": 0, "applicable_evidence": "State 0", f"{prefix}_justification": "Recorded marker.",
        f"{prefix}_earned_points": 1.5}
    invalid = {**valid, f"{prefix}_earned_points": True}
    agent, client = native_agent(mode, responses=[{"items": [invalid]}, {"items": [valid]}])
    rubric = {"items": [{"criterion": "Saved", "description": "Saved marker", "max_points": 1.5,
        "earned_points": 0, "justification": "Not proved by actions."}]}
    result = asyncio.run(agent._rescore_rubric(rubric, {}, "Save marker", "", "", ""))
    assert result["items"][0][agent.score_field] == 1.5
    assert client.create.await_count == 2


@pytest.mark.parametrize("kind", ["authentication", "access_token"])
def test_authentication_refresh_obeys_attempt_budget_and_retains_receipts(monkeypatch, kind):
    from w8bench.verifier.clients.retry import GracefulRetryClient
    response = httpx.Response(401 if kind == "authentication" else 400,
        request=httpx.Request("POST", "https://offline.example.test"))
    error = (openai.AuthenticationError if kind == "authentication" else openai.BadRequestError)(
        "check-access-response-enc" if kind == "access_token" else "invalid credentials", response=response, body={})
    receipts = []
    async def create(**kwargs):
        receipts.append({"error_type": type(error).__name__, "usage_reported": False})
        if len(receipts) > 2:
            raise RuntimeError("attempt budget exceeded")
        raise error
    endpoint = SimpleNamespace(description="offline", endpoint="offline", count_tokens=lambda **kwargs: 1,
        create=create, refresh_credentials=Mock(), _call_records=receipts)
    monkeypatch.setattr("w8bench.verifier.clients.retry.asyncio.sleep", AsyncMock())
    pool = GracefulRetryClient([endpoint], max_retries=2)
    with pytest.raises(type(error), match="credentials|check-access"):
        asyncio.run(pool.create([{"role": "user", "content": "Read marker"}]))
    assert len(receipts) == 2 and all(row["usage_reported"] is False for row in receipts)
    assert endpoint.refresh_credentials.call_count == 1


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_rendered_native_rescore_prompt_has_json_braces_and_all_criteria(mode):
    agent, _ = native_agent(mode)
    rubric = {"items": [{"criterion": "Saved", "description": "Saved marker", "max_points": 10,
        "earned_points": 0, "justification": "No action evidence.", "condition": "Dialog appears", "is_condition_met": False}]}
    messages = agent._rubric_rescore_messages(rubric, {}, "Save marker", "", "", "", 1, 1)
    text = messages[-1]["content"]
    assert "{{" not in text and "}}" not in text
    assert "{num_criteria_minus_1}" not in text
    assert "criterion 0" in text
    assert "remain in the rubric and response order" in text


@pytest.mark.parametrize("citation,valid", [
    ('DOM_MODEL_STATE_INDEX: 0; "Marker: SAVED"', True),
    ('DOM_MODEL_STATE_INDEX: 9; "Marker: SAVED"', False),
    ('DOM_MODEL_STATE_INDEX: 0; "Marker: INVENTED"', False),
    ('DOM_MODEL_STATE_INDEX: nonsense', False),
])
def test_dom_citation_diagnostics_record_errors_without_changing_analysis(tmp_path, citation, valid):
    from w8bench.verifier.dom_model.evidence import DomModelRubricAgent
    from w8bench.verifier.dom_model.rubric_agent import MMRubricAgentConfig
    (tmp_path / "dom_model0.txt").write_text("URL: https://example.test\nMarker: SAVED\n")
    agent = DomModelRubricAgent(config=MMRubricAgentConfig(action_client=object(), judge_client=object()))
    agent._load_evidence(str(tmp_path), [])
    analysis = {"dom_model_evidence": citation, "criterion_analysis": "EVIDENCE_STATUS: SUPPORTED\nThe marker is saved.",
        "discrepancies": "None", "environment_issues_confirmed": False}
    original = deepcopy(analysis)
    result = agent._parse_pair_analysis(json.dumps(analysis), False, 0)
    assert result == {**original, "dom_model_state_idx": 0}
    checks = agent.evidence_audit["citation_checks"]
    assert checks["checked_citations"] == 1
    assert checks["valid_citations"] == int(valid)
    assert checks["invalid_citations"] == int(not valid)
    assert checks["checks"][0]["valid"] is valid


@pytest.mark.parametrize("identifier", ["0.5", "0e0", "0x0", "0_0", "0suffix", "9" * 5000])
def test_dom_citation_diagnostics_handle_complete_integer_tokens(tmp_path, identifier):
    from w8bench.verifier.dom_model.evidence import DomModelRubricAgent
    from w8bench.verifier.dom_model.rubric_agent import MMRubricAgentConfig
    (tmp_path / "dom_model0.txt").write_text("URL: https://example.test\nMarker: SAVED\n")
    agent = DomModelRubricAgent(config=MMRubricAgentConfig(action_client=object(), judge_client=object()))
    agent._load_evidence(str(tmp_path), [])
    analysis = {"dom_model_evidence": f'DOM_MODEL_STATE_INDEX: {identifier}; "Marker: SAVED"',
        "criterion_analysis": "EVIDENCE_STATUS: SUPPORTED\nThe marker is saved.",
        "discrepancies": "None", "environment_issues_confirmed": False}
    result = agent._parse_pair_analysis(json.dumps(analysis), False, 0)
    assert result == {**analysis, "dom_model_state_idx": 0}
    assert agent.evidence_audit["citation_checks"]["invalid_citations"] == 1


def test_dom_citation_diagnostics_use_cited_source_state_and_record_request_scope(tmp_path):
    from w8bench.verifier.dom_model.evidence import DomModelRubricAgent
    from w8bench.verifier.dom_model.rubric_agent import MMRubricAgentConfig
    for index, marker in [(0, "INITIAL"), (1, "SAVED")]:
        (tmp_path / f"dom_model{index}.txt").write_text(f"URL: https://example.test\nMarker: {marker}\n")
    agent = DomModelRubricAgent(config=MMRubricAgentConfig(action_client=object(), judge_client=object()))
    agent._load_evidence(str(tmp_path), [{}])
    # The recorded state exists even when context packing does not supply this text.
    agent._dom_rendered_states[1] = "DOM_MODEL_STATE_INDEX: 1\n[context omitted]"
    analysis = {"dom_model_evidence": 'DOM_MODEL_STATE_INDEX: 1; "Marker: SAVED"',
        "criterion_analysis": "EVIDENCE_STATUS: SUPPORTED\nThe marker is saved.",
        "discrepancies": "None", "environment_issues_confirmed": False}
    result = agent._parse_pair_analysis(json.dumps(analysis), False, 0)
    assert result == {**analysis, "dom_model_state_idx": 0}
    checks = agent.evidence_audit["citation_checks"]
    assert checks["valid_citations"] == 1 and checks["invalid_citations"] == 0
    entry, = checks["checks"]
    assert entry["cited_state_id"] == 1 and entry["analyzed_state_id"] == 0
    assert entry["matches_analyzed_state"] is False
    quote, = entry["quote_checks"]
    assert quote == {"quote": "Marker: SAVED", "valid": True, "supplied_text_match": False}


@pytest.mark.parametrize("separator", [". ", "\n"])
def test_dom_citation_diagnostics_associate_quotes_with_each_state_marker(tmp_path, separator):
    from w8bench.verifier.dom_model.evidence import DomModelRubricAgent
    from w8bench.verifier.dom_model.rubric_agent import MMRubricAgentConfig
    for index, marker in [(0, "A"), (1, "B")]:
        (tmp_path / f"dom_model{index}.txt").write_text(f"URL: https://example.test\nMarker: {marker}\n")
    agent = DomModelRubricAgent(config=MMRubricAgentConfig(action_client=object(), judge_client=object()))
    agent._load_evidence(str(tmp_path), [{}])
    analysis = {"dom_model_evidence": f'DOM_MODEL_STATE_INDEX: 0; "A"{separator}DOM_MODEL_STATE_INDEX: 1; "B"',
        "criterion_analysis": "EVIDENCE_STATUS: SUPPORTED\nBoth markers are recorded.",
        "discrepancies": "None", "environment_issues_confirmed": False}
    result = agent._parse_pair_analysis(json.dumps(analysis), False, 0)
    assert result == {**analysis, "dom_model_state_idx": 0}
    checks = agent.evidence_audit["citation_checks"]
    assert checks["checked_citations"] == checks["valid_citations"] == 2
    assert checks["invalid_citations"] == 0
    assert [[quote["quote"] for quote in row["quote_checks"]] for row in checks["checks"]] == [["A"], ["B"]]


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("score", [True, False, -1, 1, float("nan"), float("inf")])
def test_penalty_score_requires_numeric_zero_within_finite_weight(mode, score):
    agent, _ = native_agent(mode)
    penalty = {"criterion": "Unsolicited change", "description": "The agent changed an unrelated value.",
        "max_points": 2, agent.score_field: score, agent.justification_field: "Unrelated value changed."}
    with pytest.raises(ValueError):
        agent._validate_penalty(penalty, 0)


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


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("stage", ["baseline", "rescore", "outcome", "generation", "validity"])
def test_terminal_authentication_is_ungraded_without_stage_repair(mode, stage):
    from w8bench.verifier import validity
    response = httpx.Response(401, request=httpx.Request("POST", "https://offline.example.test"))
    error = openai.AuthenticationError("invalid credentials", response=response, body={})
    agent, client = native_agent(mode)
    client.create.side_effect = error
    rubric = {"items": [{"criterion": "Saved", "description": "Saved marker", "max_points": 10,
        "earned_points": 0, "justification": "No action evidence."}]}
    context = dict(task="Save marker", init_url_context="", action_history="", predicted_output="", actions_list=[])
    async def exercise():
        if stage == "baseline":
            return await agent._score_action_history(context, rubric)
        if stage == "rescore":
            return await agent._rescore_rubric(rubric, {}, "Save marker", "", "", "")
        if stage == "outcome":
            return await agent._outcome_verification(rubric, {}, "Save marker", "", "", "")
        if stage == "generation":
            return await agent._generate_rubric("Save marker", "")
        return await validity.classify_task("Save marker", "https://example.test", client,
            prompt_template="$task_definition $url $date $apps", logger=agent.logger)
    with pytest.raises(RuntimeError, match="ungraded"):
        asyncio.run(exercise())
    assert client.create.await_count == 1


def test_rubric_draft_catalog_continues_after_auth_ungraded_task(monkeypatch, tmp_path, pair_factory):
    from w8bench.verifier import generate_frozen_rubric as generation
    rubric = {"items": [{"criterion": "Saved", "description": "Saved marker", "max_points": 1.5,
        "earned_points": "", "justification": ""}]}
    create = AsyncMock(side_effect=[scoring.UngradedVerifierError("authentication", "invalid credentials"), rubric])
    agent = SimpleNamespace(_generate_rubric=create, rubric_generation_trace=[{"stage": "rubric_generation", "accepted": False}])
    monkeypatch.setattr(generation, "_rubric_agent", lambda *args: agent)
    monkeypatch.setattr(generation, "load_env_file", lambda *args: None)
    monkeypatch.setattr(generation, "require_openai_key", lambda: "offline")
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
