import json
import asyncio
from unittest.mock import AsyncMock

import pytest

from w8bench.verifier.screenshot_verifier.utils.rubric import (
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
    agent = MMRubricAgent(config=MMRubricAgentConfig(action_client=object(), gpt5_client=object()))
    call = AsyncMock(side_effect=responses)
    monkeypatch.setattr(agent, "_call_llm", call)
    result = asyncio.run(agent._generate_rubric("Read public heading.", agent._get_init_url_context("https://example.test")))
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
