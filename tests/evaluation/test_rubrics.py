"""Offline evaluation rubrics contracts."""
from __future__ import annotations

from PIL import Image
from copy import deepcopy
from importlib import import_module
from tests.conftest import native_agent
from tests.evaluation.conftest import _state
from types import SimpleNamespace
from unittest.mock import AsyncMock
from w8bench.verifier import audit_requests as audit
from w8bench.verifier import rubric_scoring as scoring
from w8bench.verifier import validity
from w8bench.verifier.common import load_frozen_rubric, require_matching_embedded_rubric
from w8bench.verifier.common import rubric_receipt
from w8bench.verifier.common import validate_rubric
from w8bench.verifier.dom_model.evidence import DomModelRubricAgent
from w8bench.verifier.dom_model.evidence import DomModelRubricAgent, base_audit, batched_prompt, criterion_prompt, relevance_prompt, validate_grounded_analysis
from w8bench.verifier.dom_model.prompts import EVIDENCE_ANALYSIS_GROUNDING_POLICY, GROUNDING_POLICY_VERSION, REALITY_CHECK_GROUNDING_POLICY, RELEVANCE_GROUNDING_POLICY, RESCORING_GROUNDING_POLICY, MM_CRITERION_RESCORING_PROMPT, MM_RUBRIC_RESCORING_PROMPT, RUBRIC_REALITY_CHECK_PROMPT
from w8bench.verifier.dom_model.states import load_dom_model_states, pack_state
from w8bench.verifier.rubric_scoring import get_init_url_context
from w8bench.verifier.validate_inputs import compare_semantic_actions, parse_actions
import asyncio
import httpx
import importlib
import json
import logging
import openai
import pytest
import re


def test_oversized_state_packs_records_and_reports_every_omission(tmp_path):
    body = "".join(f"Control {index}: role=button name=Button-{index} value=Value-{index}\n" for index in range(30))
    (tmp_path / "dom_model0.txt").write_text(
        "URL: https://example.test/final\n"
        "Title: Final page\n"
        "Snapshot: returnedNodes=32 groups=1 truncated=true\n"
        "=== VISIBLE CONTENT ===\n"
        + body
        + "Dialog: Saved successfully\n"
        + "Error: none\n",
        encoding="utf-8",
    )
    state = load_dom_model_states(tmp_path, action_count=0)[0]
    rendered, omissions = pack_state(state, action_count=0, max_chars=700)
    assert omissions
    assert "URL: https://example.test/final" in rendered
    assert "Title: Final page" in rendered
    assert "truncated=true" in rendered
    assert "Dialog: Saved successfully" in rendered
    assert "Error: none" in rendered
    assert "DOM_MODEL_CONTEXT_OMISSIONS:" in rendered
    assert all(item["provenance"].startswith("m0:L") for item in omissions)
    assert all(item["char_count"] > 0 and item["estimated_tokens"] > 0 for item in omissions)


def test_grouping_prefers_later_state_on_tie():
    agent = object.__new__(DomModelRubricAgent)
    agent.config = type("Config", (), {"max_states_per_criterion": 2})()
    grouped = agent._group_evidence_by_criterion(
        {
            0: {0: 8, "dom_model_state_idx": 0},
            1: {0: 8, "dom_model_state_idx": 1},
            2: {0: 7, "dom_model_state_idx": 2},
        },
        1,
    )
    assert grouped == {0: [1, 0]}


def test_loader_includes_all_n_plus_one_states(dom_pair_factory):
    pair = dom_pair_factory()
    agent = object.__new__(DomModelRubricAgent)
    agent.config = type("Config", (), {"dom_model_state_char_budget": 350000})()

    states = agent._load_evidence(str(pair["dom"]), actions_list=[{}])

    assert [state.index for state in states] == [0, 1]
    assert [state.path.name for state in states] == ["dom_model0.txt", "dom_model1.txt"]
    assert agent.evidence_audit["state_selection_policy"] == "all_states_0_through_n"
    assert agent.evidence_audit["source_complete_state_count"] == 2
    assert agent.evidence_audit["complete_state_count"] == 2
    assert agent.evidence_audit["excluded_source_states"] == []


def test_screenshot_default_does_not_drop_zero_relevance_top_k():
    """Regression for Task 16: zero scores still reach the top-K analysis set."""

    agent = object.__new__(DomModelRubricAgent)
    agent.config = type(
        "Config", (), {"max_states_per_criterion": 2, "min_relevance_threshold": 0}
    )()
    relevance = {
        0: {0: 0, "dom_model_state_idx": 0},
        1: {0: 0, "dom_model_state_idx": 1},
        2: {0: 0, "dom_model_state_idx": 2},
    }
    grouped = agent._group_evidence_by_criterion(relevance, 1)

    assert grouped == {0: [2, 1]}
    assert agent.config.min_relevance_threshold == 0


def test_zero_relevance_top_k_reaches_dom_evidence_analysis():
    agent = object.__new__(DomModelRubricAgent)
    agent.config = type("Config", (), {"max_iters": 1})()
    agent.evidence_audit = {"selection": {}}
    analyzed = []

    async def fake_analyze_pair(**kwargs):
        analyzed.append((kwargs["criterion_idx"], kwargs["state_idx"]))
        return kwargs["criterion_idx"], {
            "dom_model_evidence": "DOM_MODEL_STATE_INDEX: test",
            "criterion_analysis": "EVIDENCE_STATUS: UNKNOWN",
            "discrepancies": "None",
            "environment_issues_confirmed": False,
            "dom_model_state_idx": kwargs["state_idx"],
        }

    agent._analyze_pair = fake_analyze_pair
    evidence = asyncio.run(
        agent._analyze_evidence_batched(
            dom_states=[object(), object(), object()],
            rubric={"items": [{"criterion": "Deliver final recommendation"}]},
            grouped_dom_states={0: [2, 1]},
            task="task",
            init_url_context="",
            action_history="",
            predicted_output="",
            relevance_scores={
                0: {0: 0}, 1: {0: 0}, 2: {0: 0},
            },
            min_relevance_threshold=0,
        )
    )

    assert analyzed == [(0, 2), (0, 1)]
    assert len(evidence[0]) == 2


def test_analysis_prompts_require_status_and_state_provenance():
    state = _state()
    single = criterion_prompt(
        task="Report the account value",
        init_url_context="",
        action_history="navigate",
        predicted_output="Active",
        criterion_info="Criterion 0",
        conditional_check="",
        conditional_output="",
        state=state,
        action_count=1,
    )
    batched = batched_prompt(
        task="Report the account value",
        init_url_context="",
        action_history="navigate",
        predicted_output="Active",
        criteria_info="Criterion 0",
        state=state,
        action_count=1,
    )
    for prompt in (single, batched):
        for status in ("SUPPORTED", "PARTIAL", "CONTRADICTED", "UNKNOWN"):
            assert f"EVIDENCE_STATUS: {status}" in prompt
        assert "DOM_MODEL_STATE_INDEX" in prompt
        assert "outside knowledge" in prompt
        assert "not contradicted is not supported" in prompt
        assert "browser-derived claims require DOM support" in prompt


def test_relevance_cannot_be_invented_from_answer_or_outside_knowledge():
    prompt = relevance_prompt(
        task="Report the account value",
        init_url_context="",
        criteria_text="0. Account value",
        state=_state(),
        action_count=1,
    )
    assert "judge only explicit state content" in prompt
    assert "outside knowledge" in prompt
    assert "Absent, omitted, truncated, and pixel-only facts" in prompt


def test_downstream_dom_prompts_preserve_unknown_as_unproven():
    for prompt in (MM_CRITERION_RESCORING_PROMPT, MM_RUBRIC_RESCORING_PROMPT):
        assert "browser facts require explicit DOM support for full credit" in prompt
        assert "UNKNOWN gives no confirmation" in prompt
        assert "Actions prove actions" in prompt
        assert "neither proves browser state" in prompt
        assert "outside knowledge" in prompt
        assert "text is not rendered" in prompt
    assert "PARTIAL or UNKNOWN cannot establish facts" in RUBRIC_REALITY_CHECK_PROMPT
    assert "Never replace missing support" in RUBRIC_REALITY_CHECK_PROMPT


def test_llm_facing_evidence_prompts_use_dom_model_terminology():
    state = _state()
    evidence_prompts = (
        criterion_prompt(
            task="task", init_url_context="", action_history="", predicted_output="",
            criterion_info="Criterion 0", conditional_check="", conditional_output="",
            state=state, action_count=1,
        ),
        batched_prompt(
            task="task", init_url_context="", action_history="", predicted_output="",
            criteria_info="Criterion 0", state=state, action_count=1,
        ),
        MM_CRITERION_RESCORING_PROMPT, MM_RUBRIC_RESCORING_PROMPT, RUBRIC_REALITY_CHECK_PROMPT,
    )
    assert all("DOM-model" in prompt for prompt in evidence_prompts)
    legacy_terms = ("screen" + "shot", "im" + "age", "vis" + "ual")
    assert all(
        not re.search(rf"\b{term}\w*\b", prompt, re.I)
        for prompt in evidence_prompts
        for term in legacy_terms
    )
    assert "dom_model_evidence" in evidence_prompts[0]


def test_dom_facing_evidence_key_is_validated_without_schema_translation():
    analysis = {
        "dom_model_evidence": "DOM_MODEL_STATE_INDEX: 1; Value: Active",
        "criterion_analysis": "EVIDENCE_STATUS: SUPPORTED",
        "discrepancies": "None",
        "environment_issues_confirmed": False,
    }
    validated = DomModelRubricAgent._validate_dom_model_analysis(analysis)
    assert validated["dom_model_evidence"].startswith("DOM_MODEL_STATE_INDEX")
    assert validated is analysis


def test_policy_is_general_and_audited():
    all_policy_text = "\n".join(

        (
            RELEVANCE_GROUNDING_POLICY,
            EVIDENCE_ANALYSIS_GROUNDING_POLICY,
            REALITY_CHECK_GROUNDING_POLICY,
            RESCORING_GROUNDING_POLICY,
        )
    ).lower()
    for task_specific_term in ("task36", "typescript", "pick<", "omit<", "exclude<", "extract<"):
        assert task_specific_term not in all_policy_text
    audit = base_audit([_state()])
    assert audit["grounding_policy_version"] == GROUNDING_POLICY_VERSION
    assert audit["evidence_mode"] == "dom_model"


@pytest.mark.parametrize("status", ("SUPPORTED", "PARTIAL", "CONTRADICTED", "UNKNOWN"))
def test_all_grounding_statuses_validate(status):
    analysis = {
        "criterion_analysis": f"EVIDENCE_STATUS: {status}\nGrounded explanation.",
        "dom_model_evidence": "DOM_MODEL_STATE_INDEX: 1; Value: Active",
    }
    assert validate_grounded_analysis(analysis) == status


@pytest.mark.parametrize(
    ("criterion_analysis", "dom_model_evidence"),
    (
        ("No status", "DOM_MODEL_STATE_INDEX: 1"),
        ("EVIDENCE_STATUS: PLAUSIBLE", "DOM_MODEL_STATE_INDEX: 1"),
        ("EVIDENCE_STATUS: SUPPORTED", "No state citation"),
    ),
)
def test_malformed_grounding_is_rejected(criterion_analysis, dom_model_evidence):
    with pytest.raises(ValueError):
        validate_grounded_analysis(
            {
                "criterion_analysis": criterion_analysis,
                "dom_model_evidence": dom_model_evidence,
            }
        )


def test_loads_required_canonical_rubric(tmp_path):
    rubric = {"items": [{"criterion": "One", "description": "D", "max_points": 10}]}
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps({"task_id": "task", "precomputed_rubric": rubric}))
    frozen = load_frozen_rubric(path, expected_task_id="task")
    assert len(frozen.sha256) == 64
    assert require_matching_embedded_rubric({}, frozen)["precomputed_rubric"] == rubric


def test_rejects_wrong_task_and_embedded_drift(tmp_path):
    rubric = {"items": [{"criterion": "One", "description": "D", "max_points": 10}]}
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps({"task_id": "task", "precomputed_rubric": rubric}))
    with pytest.raises(ValueError, match="task_id mismatch"):
        load_frozen_rubric(path, expected_task_id="other")
    frozen = load_frozen_rubric(path, expected_task_id="task")
    with pytest.raises(ValueError, match="differs"):
        require_matching_embedded_rubric({"precomputed_rubric": {"items": []}}, frozen)


@pytest.mark.parametrize("reformulate,bad_first", [(False, False), (True, False), (False, True)])
def test_original_generation_records_dependency_response_and_repair_without_freezing(monkeypatch, tmp_path, reformulate, bad_first):
    from w8bench.verifier.screenshot_verifier.rubric_agent import MMRubricAgent, MMRubricAgentConfig
    rubric = {"items": [{"criterion": "Report the heading", "description": "Report visible heading text.",
        "max_points": 10, "earned_points": "", "justification": ""}]}
    revised = json.loads(json.dumps(rubric))
    revised["items"][0]["description"] = "Report the heading visible at run time."
    dependency = {"reasoning": "Independent criterion", "needs_reformulation": reformulate,
        "reformulated_rubric": revised if reformulate else {}}
    responses = (["invalid JSON"] if bad_first else []) + [json.dumps(rubric), json.dumps(dependency)]
    agent = MMRubricAgent(config=MMRubricAgentConfig(action_client=object(), judge_client=object()))
    call = AsyncMock(side_effect=responses)
    monkeypatch.setattr(agent, "_call_llm", call)
    result = asyncio.run(agent._generate_rubric("Read public heading.", get_init_url_context("https://example.test")))
    assert result == (revised if reformulate else rubric)
    trace = agent.rubric_generation_trace
    assert trace[-1]["stage"] == "dependency_check" and trace[-1]["accepted"] is True
    assert trace[-1]["response"] == dependency
    assert sum(row["stage"] == "dependency_check" for row in trace) == 1
    assert call.await_count == 2 + int(bad_first)
    assert "https://example.test" in trace[-1]["messages"][0]["content"]
    if bad_first:
        assert trace[0]["response_text"] == "invalid JSON" and trace[0]["accepted"] is False
        assert "JSONDecodeError" in trace[0]["error"]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_outcome_prompt_uses_task_evidence_dates_without_fixed_collection_year(package):
    import importlib
    prompt = importlib.import_module(f"w8bench.verifier.{package}.prompts").OUTCOME_VERIFICATION_PROMPT
    assert "Do not assume a fixed trajectory-collection year" in prompt
    assert "Use a year explicitly specified by the task or established by the recorded evidence" in prompt
    assert "2025 (when these trajectories were collected)" not in prompt
    assert "October 4-13, 2025 is the correct interpretation" not in prompt


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("whole", [False, True])
@pytest.mark.parametrize("case", ["missing", "empty_evidence", "justification_type", "score_type", "below_range", "above_range", "multiple"])
def test_rescore_validation_preserves_exact_repair_request(package, whole, case):
    import importlib
    from types import SimpleNamespace
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    field = "post_dom" if package == "dom_model" else "post_image"
    justification, points = f"{field}_justification", f"{field}_earned_points"
    valid = {"applicable_evidence": "State 1", justification: "The requested fact is present.", points: 2.5}
    bad = dict(valid)
    prefix = "Item 0: " if whole else ""
    if case == "missing":
        bad = {}
        error = f"Invalid rescoring output. Missing fields: applicable_evidence, {justification}, {points}. "
    elif case == "empty_evidence":
        bad["applicable_evidence"] = ""
        error = f"Invalid rescoring output. Errors: {prefix}applicable_evidence cannot be empty."
    elif case == "justification_type":
        bad[justification] = 7
        error = f"Invalid rescoring output. Errors: {prefix}{justification} must be a string, got int."
    elif case == "score_type":
        bad[points] = "2.5"
        error = f"Invalid rescoring output. Errors: {prefix}{points} must be a number, got str."
    elif case == "below_range":
        bad[points] = -1
        error = f"Invalid rescoring output. Errors: {prefix}{points} must be between 0 and 10, got -1."
    elif case == "above_range":
        bad[points] = 11
        error = f"Invalid rescoring output. Errors: {prefix}{points} must be between 0 and 10, got 11."
    else:
        bad = {"applicable_evidence": "", points: 11}
        error = (f"Invalid rescoring output. Missing fields: {justification}. Errors: "
            f"{prefix}applicable_evidence cannot be empty; {prefix}{points} must be between 0 and 10, got 11.")
    responses = [{"items": [{"criterion_idx": 0, **value}]} if whole else value for value in (bad, valid)]
    calls = []
    async def complete(messages, client, json_output=False):
        calls.append((json.loads(json.dumps(messages)), client, json_output))
        return json.dumps(responses.pop(0))
    agent = object.__new__(module.MMRubricAgent)
    agent.config = SimpleNamespace(max_iters=2, action_client=object(), judge_client=object())
    agent._call_llm = complete
    name = f"_rescore_{'rubric' if whole else 'criterion'}"
    rubric = {"items": [{"criterion": "Report the heading", "description": "Report the visible heading.",
        "max_points": 10, "earned_points": 3, "justification": "The action reached the page."}]}
    result = asyncio.run(getattr(agent, name)(rubric, {}, "Report the heading.", "", "Read page", "Heading"))
    assert result is rubric and result["items"][0][points] == 2.5
    assert result["items"][0][justification] == valid[justification]
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0][:-1]
    ending = "all 1 criteria in the correct format." if whole else "all required fields in the correct format."
    assert calls[1][0][-1] == {"role": "user", "content": f"Error: {error}. Please ensure your output includes {ending}"}
    expected_client = agent.config.judge_client if whole else agent.config.action_client
    assert all(client is expected_client and json_output is True for _, client, json_output in calls)


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


def test_empty_action_log_represents_a_valid_zero_action_trajectory(tmp_path):
    log = tmp_path / "empty.log"
    log.write_text("", encoding="utf-8")

    assert parse_actions(log, mode="screenshot") == []
    assert parse_actions(log, mode="dom_model") == []


def test_key_action_is_preserved_and_compared(tmp_path):
    screenshot_log = tmp_path / "screenshot.log"
    dom_log = tmp_path / "dom.log"
    event = json.dumps({"action": "key", "arguments": {"action": "key", "key": "Enter"}}) + "\n"
    screenshot_log.write_text(event, encoding="utf-8")
    dom_log.write_text(event, encoding="utf-8")

    screenshot_actions = parse_actions(screenshot_log, mode="screenshot")
    dom_actions = parse_actions(dom_log, mode="dom_model")

    assert screenshot_actions[0]["action"] == "key"
    assert screenshot_actions[0]["key"] == "Enter"
    compare_semantic_actions(screenshot_actions, dom_actions)


def test_wait_action_is_preserved_and_compared(tmp_path):
    screenshot_log = tmp_path / "screenshot.log"
    dom_log = tmp_path / "dom.log"
    event = json.dumps({"action": "wait", "arguments": {"action": "wait", "seconds": 1.0}}) + "\n"
    screenshot_log.write_text(event, encoding="utf-8")
    dom_log.write_text(event, encoding="utf-8")

    screenshot_actions = parse_actions(screenshot_log, mode="screenshot")
    dom_actions = parse_actions(dom_log, mode="dom_model")

    assert screenshot_actions[0]["action"] == "wait"
    assert screenshot_actions[0]["seconds"] == 1.0
    compare_semantic_actions(screenshot_actions, dom_actions)


def test_select_action_is_preserved_and_compared(tmp_path):
    screenshot_log = tmp_path / "screenshot.log"
    dom_log = tmp_path / "dom.log"
    event = json.dumps({"action": "select", "arguments": {"action": "select", "ref": "e69", "text": "Avg. Customer Review"}}) + "\n"
    screenshot_log.write_text(event, encoding="utf-8")
    dom_log.write_text(event, encoding="utf-8")

    screenshot_actions = parse_actions(screenshot_log, mode="screenshot")
    dom_actions = parse_actions(dom_log, mode="dom_model")

    assert screenshot_actions[0]["action"] == "select"
    compare_semantic_actions(screenshot_actions, dom_actions)


def test_history_back_aliases_normalize_to_screenshot_action(tmp_path):
    screenshot_log = tmp_path / "screenshot.log"
    dom_log = tmp_path / "dom.log"
    screenshot_log.write_text(
        json.dumps({"action": "back", "arguments": {}}) + "\n",
        encoding="utf-8",
    )
    dom_log.write_text(
        json.dumps({"action": "history_back", "arguments": {}}) + "\n",
        encoding="utf-8",
    )

    screenshot_actions = parse_actions(screenshot_log, mode="screenshot")
    dom_actions = parse_actions(dom_log, mode="dom_model")
    compare_semantic_actions(screenshot_actions, dom_actions)

    assert screenshot_actions[0]["action"] == "history_back"
    assert dom_actions[0]["action"] == "history_back"


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
