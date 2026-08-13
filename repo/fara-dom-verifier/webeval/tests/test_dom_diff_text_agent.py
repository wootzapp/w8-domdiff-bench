from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import pytest

from webeval.rubric_agent.dom_diff_agent import DOMDiffMMRubricAgent
from webeval.rubric_agent.dom_diff_text_agent import DOMDiffTextMMRubricAgent
from webeval.rubric_agent.dom_diff_text_compaction import compact_text_frame
from webeval.rubric_agent.dom_diff_text_evidence import parse_dom_diff_text
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgentConfig


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "dom_diff_text"
    / "changes_present"
    / "dom_diff1.txt"
)


def _rubric() -> dict:
    return {
        "items": [
            {
                "criterion": "Report the publisher",
                "description": "Report Microsoft Studios.",
                "max_points": 5,
            },
            {
                "criterion": "Report the release date",
                "description": "Report 7/6/2022.",
                "max_points": 5,
            },
        ]
    }


def _agent(*, max_iters: int = 2) -> DOMDiffTextMMRubricAgent:
    return DOMDiffTextMMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=object(),
            gpt5_client=object(),
            evidence_mode="dom",
            max_iters=max_iters,
            text_frame_starting_tokens=1,
            text_trajectory_starting_tokens=20,
            text_analysis_starting_tokens=20,
            text_max_chunk_tokens=64,
            text_allow_budget_expansion=True,
            text_model_context_window_tokens=32000,
            text_relevance_completion_reserve_tokens=1000,
            text_analysis_completion_reserve_tokens=2000,
            text_prompt_headroom_tokens=500,
            text_judge_model="gpt-5.2",
        )
    )


def _frame():
    return parse_dom_diff_text(FIXTURE, task_id="task", action_ordinal=1)


def _compact_frame():
    return _frame().with_compact(compact_text_frame(_frame(), max_chunk_tokens=64))


def test_agent_is_thin_and_inherits_shared_downstream_orchestration() -> None:
    assert "_generate_reply" not in DOMDiffTextMMRubricAgent.__dict__
    assert DOMDiffTextMMRubricAgent._generate_reply is DOMDiffMMRubricAgent._generate_reply
    expected_hooks = {
        "_load_dom_evidence",
        "_compact_dom_trajectory_metadata",
        "_generate_dom_retrieval_terms",
        "_score_dom_criterion_relevance",
        "_analyze_dom_evidence_batched",
        "_build_all_screenshot_evidence_text",
    }
    assert expected_hooks <= set(DOMDiffTextMMRubricAgent.__dict__)


def test_load_records_soft_frame_exceedance_without_omission() -> None:
    agent = _agent()
    frames = agent._load_dom_evidence(
        [
            {
                "id": 1,
                "dom_action_ordinal": 1,
                "dom_action_id": "1",
                "dom_task_id": "task",
                "dom_diff_text_path": str(FIXTURE),
            }
        ]
    )
    assert frames[0].compact is not None
    diagnostic = agent.text_runtime_metrics()["frame_budget_diagnostics"][0]
    assert diagnostic["starting_target_exceeded"] is True
    assert diagnostic["records_or_chunks_omitted_for_starting_target"] == 0
    assert diagnostic["raw_evidence_estimated_tokens"] > 0
    assert agent.text_runtime_metrics()["raw_evidence_estimated_tokens"] == diagnostic[
        "raw_evidence_estimated_tokens"
    ]
    assert agent.text_runtime_metrics()["model_compact_estimated_tokens"] == diagnostic[
        "full_compact_estimated_tokens"
    ]
    metadata = agent._compact_dom_trajectory_metadata(frames, limit=1)
    assert "source_records" not in metadata
    assert "coverage_warnings" in metadata
    assert not metadata.endswith("…")


def test_global_dom_top_k_cannot_drop_chronological_steps() -> None:
    agent = _agent()
    agent.config.dom_top_k = 1
    with pytest.raises(ValueError, match="every action step"):
        agent._load_dom_evidence(
            [
                {
                    "id": 1,
                    "dom_action_ordinal": 1,
                    "dom_action_id": "1",
                    "dom_task_id": "task",
                    "dom_diff_text_path": str(FIXTURE),
                }
            ]
        )


def test_batched_relevance_retries_then_returns_all_frame_rows() -> None:
    agent = _agent()
    agent._reset_text_metrics()
    responses = [
        json.dumps({"frames": []}),
        json.dumps(
            {
                "frames": [
                    {"evidence_idx": 0, "criterion_0": 10, "criterion_1": 9}
                ]
            }
        ),
    ]
    prompts: list[str] = []

    async def fake_call(messages, client, json_output=False):
        del client, json_output
        prompts.append(messages[-1]["content"])
        return responses.pop(0)

    agent._call_llm = fake_call
    result = asyncio.run(
        agent._score_dom_criterion_relevance(
            [_compact_frame()], _rubric(), "Report publisher and date", "Initial URL"
        )
    )
    assert len(prompts) == 2
    assert result[0][0] == 10 and result[0][1] == 9
    assert "refined DOM-diff text" in prompts[0]
    metrics = agent.text_runtime_metrics()
    assert [request["validation_attempt"] for request in metrics["requests"]] == [1, 2]
    assert all(
        request["prompt_estimated_tokens"]
        <= request["budget"]["safe_prompt_limit_tokens"]
        for request in metrics["requests"]
    )


def test_packed_analysis_returns_standard_downstream_schema() -> None:
    agent = _agent()
    agent._reset_text_metrics()

    async def fake_call(messages, client, json_output=False):
        del client, json_output
        assert "ASSIGNMENT: C[criterion indexes]" in messages[-1]["content"]
        assert "CRITERION EVIDENCE ASSIGNMENTS" not in messages[-1]["content"]
        return json.dumps(
            {
                "analyses": [
                    {
                        "criterion_idx": 0,
                        "evidence_status": "supported",
                        "evidence_text": "Step 1 explicitly shows Microsoft Studios.",
                        "criterion_analysis": "The publisher matches.",
                        "discrepancies": "None explicitly shown",
                        "environment_issues_confirmed": False,
                        "evidence_indices": [0],
                    },
                    {
                        "criterion_idx": 1,
                        "evidence_status": "supported",
                        "evidence_text": "Step 1 explicitly shows 7/6/2022.",
                        "criterion_analysis": "The exact date matches.",
                        "discrepancies": "None explicitly shown",
                        "environment_issues_confirmed": False,
                        "evidence_indices": [0],
                    },
                ]
            }
        )

    agent._call_llm = fake_call
    result = asyncio.run(
        agent._analyze_dom_evidence_batched(
            [_compact_frame()],
            _rubric(),
            {0: [0], 1: [0]},
            "Report publisher and date",
            "Initial URL",
            "Action history",
            "Microsoft Studios; 7/6/2022",
            relevance_scores={
                0: {0: 10, 1: 9, "evidence_idx": 0, "screenshot_idx": 0}
            },
        )
    )
    assert set(result) == {0, 1}
    for criterion_idx in result:
        analysis = result[criterion_idx][0]
        assert analysis["evidence_text"] == analysis["screenshot_evidence"]
        assert analysis["evidence_indices"] == [0]
        assert analysis["steps"] == [1]


def test_unassigned_citation_exhaustion_returns_unknown() -> None:
    agent = _agent(max_iters=2)
    agent._reset_text_metrics()
    calls = 0

    async def fake_call(messages, client, json_output=False):
        nonlocal calls
        del messages, client, json_output
        calls += 1
        return json.dumps(
            {
                "analyses": [
                    {
                        "criterion_idx": criterion_idx,
                        "evidence_status": "supported",
                        "evidence_text": "Unsupported citation.",
                        "criterion_analysis": "Invalid assignment.",
                        "discrepancies": "None",
                        "environment_issues_confirmed": False,
                        "evidence_indices": [99],
                    }
                    for criterion_idx in range(2)
                ]
            }
        )

    agent._call_llm = fake_call
    result = asyncio.run(
        agent._analyze_dom_evidence_batched(
            [_compact_frame()],
            _rubric(),
            {0: [0], 1: [0]},
            "Report publisher and date",
            "Initial URL",
            "Action history",
            "Microsoft Studios; 7/6/2022",
        )
    )
    assert calls == 2
    assert all(result[index][0]["evidence_status"] == "unknown" for index in result)


def test_final_evidence_text_changes_only_modality_terminology() -> None:
    text = DOMDiffTextMMRubricAgent._build_all_screenshot_evidence_text(
        _rubric(),
        {
            0: [
                {
                    "evidence_idx": 0,
                    "steps": [1],
                    "evidence_status": "supported",
                    "evidence_text": "Published by Microsoft Studios",
                    "criterion_analysis": "Exact text is present.",
                    "discrepancies": "None",
                    "environment_issues_confirmed": False,
                }
            ]
        },
        1,
    )
    assert "Refined DOM-diff text steps [1]" in text
    assert '"Not observed" is not proof' in text
    assert "Published by Microsoft Studios" in text


def test_inherited_step_4_5_onward_runs_without_text_specific_branch() -> None:
    agent = _agent(max_iters=1)
    frame = _compact_frame()
    visited: list[str] = []
    rubric = {
        "items": [
            {
                "criterion": "Report the publisher",
                "description": "Report Microsoft Studios.",
                "max_points": 5,
                "earned_points": "",
                "justification": "",
            }
        ]
    }

    async def fake_call(messages, client, json_output=False):
        del messages, client, json_output
        return json.dumps(
            {
                "items": [
                    {
                        "criterion": "Report the publisher",
                        "earned_points": 5,
                        "justification": "The action history reached the product.",
                    }
                ]
            }
        )

    async def fake_terms(*args, **kwargs):
        del args, kwargs
        return ["microsoft studios"]

    async def fake_relevance(*args, **kwargs):
        del args, kwargs
        return {0: {0: 10, "screenshot_idx": 0, "evidence_idx": 0}}

    async def fake_analysis(*args, **kwargs):
        del args, kwargs
        return {
            0: [
                {
                    "evidence_status": "supported",
                    "evidence_text": "Step 1 shows Microsoft Studios.",
                    "screenshot_evidence": "Step 1 shows Microsoft Studios.",
                    "criterion_analysis": "The explicit publisher matches.",
                    "discrepancies": "None explicitly shown",
                    "environment_issues_confirmed": False,
                    "evidence_idx": 0,
                    "screenshot_idx": 0,
                    "evidence_indices": [0],
                    "steps": [1],
                }
            ]
        }

    async def fake_reality(rubric_value, *args, **kwargs):
        del args, kwargs
        visited.append("reality")
        return rubric_value

    async def fake_steps_6_7(rubric_value, *args, **kwargs):
        del args, kwargs
        visited.append("rescore_penalty")
        scored = copy.deepcopy(rubric_value)
        item = scored["items"][0]
        item["post_evidence_earned_points"] = 5
        item["post_evidence_justification"] = "Explicit text evidence matches."
        item["post_image_earned_points"] = 5
        item["post_image_justification"] = "Explicit text evidence matches."
        scored["total_max_points"] = 5
        scored["total_earned_points"] = 5
        return scored, 1.0, {
            "step6_rescoring_summary": {},
            "step7_penalty_criteria": [],
            "step7_reasoning": "No unsolicited side effects.",
            "step7_requires_penalty": False,
        }

    async def fake_outcome(*args, **kwargs):
        del args, kwargs
        visited.append("outcome")
        return {
            "output_success": True,
            "reasoning": "The requested publisher is reported.",
            "primary_intent": "Report the publisher.",
        }

    async def fake_failure(*args, **kwargs):
        del args, kwargs
        visited.append("failure")
        return {"failure_points": [], "first_failure_step": None}

    async def fake_trajectory_validity(*args, **kwargs):
        del args, kwargs
        visited.append("trajectory_validity")
        return {"is_valid": True, "reasoning": "Task remained valid."}

    async def fake_task_validity(*args, **kwargs):
        del args, kwargs
        visited.append("task_validity")
        return {"is_valid": True, "reasoning": "Task is well specified."}

    agent._call_llm = fake_call
    agent._load_dom_evidence = lambda actions: [frame]
    agent._generate_dom_retrieval_terms = fake_terms
    agent._score_dom_criterion_relevance = fake_relevance
    agent._analyze_dom_evidence_batched = fake_analysis
    agent._rubric_reality_check = fake_reality
    agent._run_steps_6_7_single_instance = fake_steps_6_7
    agent._outcome_verification = fake_outcome
    agent._first_point_of_failure_analysis = fake_failure
    agent._classify_task_with_trajectory = fake_trajectory_validity
    agent._classify_task = fake_task_validity

    result = asyncio.run(
        agent._generate_reply(
            {
                "task": "Report the publisher",
                "action_history": "Step 1: click product",
                "predicted_output": "Microsoft Studios",
                "actions_list": [],
                "dom_actions": [{"dom_diff_text_path": str(FIXTURE)}],
                "evidence_mode": "dom",
                "step_actions": [],
                "precomputed_rubric": rubric,
                "init_url": "https://example.test/start",
                "apps": [],
                "redo_eval": False,
            }
        )
    )
    assert visited == [
        "reality",
        "rescore_penalty",
        "outcome",
        "failure",
        "trajectory_validity",
        "task_validity",
    ]
    assert result["total_earned_points"] == result["total_max_points"] == 5
    assert result["outcome_verification"]["output_success"] is True
    assert "step5_reality_check" in result["intermediate_mm_rubric_steps"]
