from __future__ import annotations

import asyncio
import hashlib
import json

from webeval.rubric_agent.dom_diff_summary_agent import DOMDiffSummaryMMRubricAgent
from webeval.rubric_agent.dom_diff_summary_compaction import compact_summary_frame
from webeval.rubric_agent.dom_diff_summary_evidence import DOMDiffSummaryEvidenceFrame
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgentConfig


def _raw_summary(text: str) -> dict:
    return {
        "schema_version": "1.0",
        "method": "local_agent_observation_summary",
        "captured_at": "2026-01-01T00:00:00Z",
        "url": {
            "before": "https://example.test/",
            "after": "https://example.test/fact",
            "changed": True,
        },
        "title": {"before": "Example", "after": "Fact", "changed": True},
        "scroll": {
            "before": {"scrollY": 0, "scrollHeight": 1000},
            "after": {"scrollY": 100, "scrollHeight": 1000},
            "changed": True,
        },
        "stats": {
            "before": {
                "candidateInteractives": 0,
                "returnedInteractives": 0,
                "candidateContentBlocks": 0,
                "returnedContentBlocks": 0,
            },
            "after": {
                "candidateInteractives": 0,
                "returnedInteractives": 0,
                "candidateContentBlocks": 0,
                "returnedContentBlocks": 0,
            },
            "elements_added": 0,
            "elements_removed": 0,
            "elements_changed": 0,
        },
        "visible_text_added": [text],
        "visible_text_removed": [],
        "interactive_added": [],
        "interactive_removed": [],
        "interactive_changed": [],
    }


def _frame(ordinal: int, text: str) -> DOMDiffSummaryEvidenceFrame:
    raw = _raw_summary(text)
    raw_bytes = json.dumps(raw, separators=(",", ":")).encode()
    compact = compact_summary_frame(
        raw,
        action_ordinal=ordinal,
        action_id=str(ordinal),
        source_path=f"/tmp/step_{ordinal:03d}/dom_diff_summary.json",
        source_hash=hashlib.sha256(raw_bytes).hexdigest(),
        source_bytes=len(raw_bytes),
    )
    return DOMDiffSummaryEvidenceFrame(
        action_ordinal=ordinal,
        action_id=str(ordinal),
        summary_path=compact.source_path,
        summary=raw,
        diff=raw,
        compact=compact,
        source_sha256=compact.source_sha256,
        source_bytes=compact.source_bytes,
        schema_version="1.0",
        method="local_agent_observation_summary",
    )


def _agent(mode: str) -> DOMDiffSummaryMMRubricAgent:
    return DOMDiffSummaryMMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=object(),
            gpt5_client=object(),
            evidence_mode="dom",
            max_iters=2,
            summary_mode=mode,
            summary_projection="raw" if mode == "s0" else "compact",
            summary_relevance_mode=(
                "batched_llm" if mode in {"s2", "s3"} else "per_frame_llm"
            ),
            summary_analysis_mode="packed" if mode == "s3" else "selected_frames",
            summary_frame_token_budget=800,
            summary_trajectory_token_budget=2000,
            summary_analysis_token_budget=2000,
            summary_max_record_chars=600,
            summary_judge_model="gpt-5.2",
        )
    )


def _rubric() -> dict:
    return {
        "items": [
            {
                "criterion": "Report height",
                "description": "Report 330 m.",
                "max_points": 5,
            },
            {
                "criterion": "Report location",
                "description": "Report Paris.",
                "max_points": 5,
            },
        ]
    }


def test_s2_uses_one_batched_relevance_call() -> None:
    frames = [_frame(1, "Height 330 m"), _frame(2, "Location Paris")]
    agent = _agent("s2")
    agent._reset_summary_metrics()
    calls = []

    async def fake_call(messages, client, json_output=False):
        calls.append(messages)
        return json.dumps(
            {
                "frames": [
                    {"evidence_idx": 0, "criterion_0": 10, "criterion_1": 1},
                    {"evidence_idx": 1, "criterion_0": 1, "criterion_1": 10},
                ]
            }
        )

    agent._call_llm = fake_call
    result = asyncio.run(
        agent._score_dom_criterion_relevance(
            frames, _rubric(), "Report height and location", "Initial URL"
        )
    )
    assert len(calls) == 1
    assert result[0][0] == 10
    assert result[1][1] == 10
    metrics = agent.summary_runtime_metrics()
    assert metrics["requests"][0]["stage"] == "summary_relevance_batched"


def test_s3_packed_analysis_returns_downstream_compatible_schema() -> None:
    frames = [_frame(1, "Height 330 m"), _frame(2, "Location Paris")]
    agent = _agent("s3")
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
                        "evidence_text": "Step 1 explicitly adds Height 330 m.",
                        "criterion_analysis": "The value and unit match.",
                        "discrepancies": "None explicitly shown",
                        "environment_issues_confirmed": False,
                        "evidence_indices": [0],
                    },
                    {
                        "criterion_idx": 1,
                        "evidence_status": "supported",
                        "evidence_text": "Step 2 explicitly adds Location Paris.",
                        "criterion_analysis": "The location matches.",
                        "discrepancies": "None explicitly shown",
                        "environment_issues_confirmed": False,
                        "evidence_indices": [1],
                    },
                ]
            }
        )

    agent._call_llm = fake_call
    result = asyncio.run(
        agent._analyze_dom_evidence_batched(
            frames,
            _rubric(),
            {0: [0], 1: [1]},
            "Report height and location",
            "Initial URL",
            "Action history",
            "Height 330 m; Location Paris",
            relevance_scores={
                0: {0: 10, 1: 1, "evidence_idx": 0, "screenshot_idx": 0},
                1: {0: 1, 1: 10, "evidence_idx": 1, "screenshot_idx": 1},
            },
        )
    )
    assert len(calls) == 1
    assert result[0][0]["evidence_status"] == "supported"
    assert result[0][0]["evidence_text"] == result[0][0]["screenshot_evidence"]
    assert result[0][0]["steps"] == [1]
    assert result[1][0]["steps"] == [2]
    metrics = agent.summary_runtime_metrics()
    assert metrics["requests"][0]["stage"] == "summary_analysis_packed"

