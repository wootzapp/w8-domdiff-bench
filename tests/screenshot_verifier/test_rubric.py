import json
import asyncio
from unittest.mock import AsyncMock

import pytest

from w8bench.verifier.rubric_scoring import get_init_url_context, validate_rescore

from w8bench.verifier.common import (
    load_frozen_rubric,
    require_matching_embedded_rubric,
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
@pytest.mark.parametrize("support,expected", [(True, True), (False, False), ("absent", True), ("type_error", True), ("attribute", True)])
@pytest.mark.parametrize("nested", [False, True])
def test_rubric_call_json_negotiation_and_response_text(package, support, expected, nested):
    import importlib
    from types import SimpleNamespace
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    calls = []
    messages = [{"role": "user", "content": "Inspect."}]
    async def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=SimpleNamespace(content="done") if nested else "done")
    client = SimpleNamespace(create=create)
    if support == "type_error":
        def supports_json():
            raise TypeError("Use the default JSON contract.")
        client.supports_json = supports_json
    elif support == "attribute":
        client.supports_json = False
    elif support != "absent":
        client.supports_json = lambda: support
    agent = object.__new__(module.MMRubricAgent)
    assert asyncio.run(agent._call_llm(messages, client, json_output=True)) == "done"
    assert calls == [{"messages": messages, "json_output": expected}]
    assert calls[0]["messages"] is messages
    calls.clear()
    assert asyncio.run(agent._call_llm(messages, client, json_output=False)) == "done"
    assert calls == [{"messages": messages, "json_output": False}]


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("content,error", [(42, "Expected str content from client, got int: 42"),
    (None, "Expected str content from client, got NoneType: None")])
def test_rubric_call_rejects_nontext_content_with_exact_error(package, content, error):
    import importlib
    from types import SimpleNamespace
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    async def create(**kwargs):
        return SimpleNamespace(content=content)
    agent = object.__new__(module.MMRubricAgent)
    with pytest.raises(AssertionError) as raised:
        asyncio.run(agent._call_llm([], SimpleNamespace(create=create)))
    assert str(raised.value) == error


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_rubric_call_preserves_client_exception(package):
    import importlib
    from types import SimpleNamespace
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    error = RuntimeError("The scoring endpoint is unavailable.")
    calls = []
    async def create(**kwargs):
        calls.append(kwargs)
        raise error
    agent = object.__new__(module.MMRubricAgent)
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(agent._call_llm([], SimpleNamespace(create=create)))
    assert raised.value is error and calls == [{"messages": [], "json_output": False}]


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


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("score", [0, 10, True, 2.5])
def test_rescore_validation_accepts_numeric_values(package, score):
    import importlib
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    field = "post_dom" if package == "dom_model" else "post_image"
    value = {"applicable_evidence": "State 1", f"{field}_justification": "Observed", f"{field}_earned_points": score}
    assert validate_rescore(value, 10, evidence_mode=package) is None
    assert value[f"{field}_earned_points"] is score
