from __future__ import annotations

import asyncio
import json
from pathlib import Path

from webeval.rubric_agent.dom_diff_text_evidence import parse_dom_diff_text
from webeval.rubric_agent.dom_diff_text_summary_agent import (
    DOMDiffTextSummaryMMRubricAgent,
)
from webeval.rubric_agent.dom_diff_text_summary_projection import (
    project_text_summary_frame,
)
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgentConfig


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "dom_diff_text"
    / "document_replaced"
    / "dom_diff1.txt"
)


def _frame():
    parsed = parse_dom_diff_text(
        FIXTURE,
        task_id="fixture-task",
        action_ordinal=1,
    )
    return parsed.with_compact(project_text_summary_frame(parsed, max_record_chars=600))


def _agent():
    return DOMDiffTextSummaryMMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=object(),
            gpt5_client=object(),
            evidence_mode="dom",
            max_iters=2,
            summary_mode="s3",
            summary_projection="compact",
            summary_relevance_mode="batched_llm",
            summary_analysis_mode="packed",
            summary_frame_token_budget=1500,
            summary_trajectory_token_budget=16000,
            summary_analysis_token_budget=24000,
            summary_max_record_chars=600,
            summary_judge_model="gpt-5.2",
        )
    )


def _rubric():
    return {
        "items": [
            {
                "criterion": "Report the release date",
                "description": "Report 7/6/2022.",
                "max_points": 2,
            }
        ]
    }


def test_one_batched_relevance_call_without_chunk_retrieval_contract():
    agent = _agent()
    agent._reset_summary_metrics()
    calls = []

    async def fake_call(messages, client, json_output=False):
        calls.append(messages)
        return json.dumps({"frames": [{"evidence_idx": 0, "criterion_0": 10}]})

    agent._call_llm = fake_call
    result = asyncio.run(
        agent._score_dom_criterion_relevance(
            [_frame()],
            _rubric(),
            "Report the release date",
            "Initial URL",
        )
    )
    assert len(calls) == 1
    assert result[0][0] == 10
    prompt = calls[0][-1]["content"]
    assert '+FRAME 0/STEP 1 url="https://example.test/result"' in prompt
    assert 'TEXT ["Release date 7/6/2022"]' in prompt
    assert "C[" not in prompt
    assert agent.summary_runtime_metrics()["requests"][0]["stage"] == (
        "text_summary_relevance_batched"
    )


def test_one_packed_analysis_call_with_summary_frame_assignments():
    agent = _agent()
    agent._reset_summary_metrics()
    calls = []

    async def fake_call(messages, client, json_output=False):
        calls.append(messages)
        return json.dumps(
            {
                "analyses": [
                    {
                        "criterion_idx": 0,
                        "evidence_status": "supported",
                        "evidence_text": "STEP 1 shows Release date 7/6/2022.",
                        "criterion_analysis": "The explicit date matches.",
                        "discrepancies": "None explicitly shown",
                        "environment_issues_confirmed": False,
                        "evidence_indices": [0],
                    }
                ]
            }
        )

    agent._call_llm = fake_call
    result = asyncio.run(
        agent._analyze_dom_evidence_batched(
            [_frame()],
            _rubric(),
            {0: [0]},
            "Report the release date",
            "Initial URL",
            "Action history",
            "Release date 7/6/2022",
            relevance_scores={0: {0: 10, "evidence_idx": 0, "screenshot_idx": 0}},
        )
    )
    assert len(calls) == 1
    assert result[0][0]["evidence_indices"] == [0]
    prompt = calls[0][-1]["content"]
    assert "CRITERION EVIDENCE ASSIGNMENTS" in prompt
    assert "criterion_0: frame_indices=[0]" in prompt
    assert "C[" not in prompt
    assert agent.summary_runtime_metrics()["requests"][0]["stage"] == (
        "text_summary_analysis_packed"
    )
