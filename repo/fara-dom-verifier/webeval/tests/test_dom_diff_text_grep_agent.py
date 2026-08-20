from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from webeval.oai_clients.messages import CreateResult, RequestUsage
from webeval.rubric_agent.dom_diff_text_grep_agent import DOMDiffTextGrepMMRubricAgent
from webeval.rubric_agent.dom_evidence import project_dom_transition_timeline
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgentConfig


def _tool_result(call_id: str, name: str, arguments: dict[str, Any]) -> CreateResult:
    call = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )
    return CreateResult(
        content="",
        usage=RequestUsage(prompt_tokens=30, completion_tokens=4),
        finish_reason="tool_calls",
        message=SimpleNamespace(content=None, tool_calls=[call]),
        tool_calls=[call],
    )


def _json_result(value: dict[str, Any]) -> CreateResult:
    content = json.dumps(value)
    return CreateResult(
        content=content,
        usage=RequestUsage(prompt_tokens=40, completion_tokens=12),
        finish_reason="stop",
        message=SimpleNamespace(content=content, tool_calls=None),
    )


class ScriptedClient:
    def __init__(self, responses: list[CreateResult]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self._max_tokens = 100_000

    async def create(self, **kwargs: Any) -> CreateResult:
        self.requests.append(copy.deepcopy(kwargs))
        if not self.responses:
            raise AssertionError("Scripted client has no response left")
        return self.responses.pop(0)

    def count_tokens(self, *, messages: list[Any], tools: list[Any]) -> int:
        serialized = json.dumps({"messages": messages, "tools": tools})
        return max(1, len(serialized) // 4)


def _agent(tmp_path: Path, client: ScriptedClient, texts: list[str]):
    actions = []
    for ordinal, text in enumerate(texts, start=1):
        path = tmp_path / f"dom_diff{ordinal}.txt"
        path.write_text(text, encoding="utf-8")
        actions.append(
            {
                "id": ordinal,
                "dom_action_ordinal": ordinal,
                "dom_action_id": str(ordinal),
                "dom_task_id": "fixture-task",
                "dom_diff_text_path": str(path),
            }
        )
    agent = DOMDiffTextGrepMMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=object(),
            gpt5_client=client,
            evidence_mode="dom",
            max_images_per_criterion=1,
            ignore_irrelevant_screenshots=False,
            grep_max_tool_rounds=8,
            grep_max_tool_calls=10,
            grep_max_result_chars=2_000,
        )
    )
    return agent, agent._load_dom_evidence(actions)


def _rubric() -> dict[str, Any]:
    return {
        "items": [
            {
                "criterion": "The page shows price 42 USD",
                "description": "Confirm the displayed price.",
                "max_points": 1,
            },
            {
                "criterion": "The completion state is shown",
                "description": "Confirm the success status.",
                "max_points": 1,
            },
        ]
    }


def _analysis(criterion: int, frames: list[int]) -> dict[str, Any]:
    return {
        "criterion_idx": criterion,
        "evidence_status": "supported",
        "evidence_text": f"FRAME {frames[0]}, line 2 supports this criterion",
        "criterion_analysis": "The retrieved source explicitly supports it.",
        "discrepancies": "None explicitly shown",
        "environment_issues_confirmed": False,
        "evidence_indices": frames,
    }


def test_fake_relevance_matrix_shared_top_k_analysis_and_instrumentation(tmp_path):
    sentinel = "RAW_ONLY_SENTINEL_99117"
    relevance = {
        "frames": [
            {"evidence_idx": 0, "criterion_0": 10, "criterion_1": 1},
            {"evidence_idx": 1, "criterion_0": 2, "criterion_1": 9},
        ]
    }
    client = ScriptedClient(
        [
            _tool_result(
                "rel-1",
                "grep_evidence",
                {
                    "query": "42 USD", "file_ids": [], "mode": "literal",
                    "case_sensitive": False, "context_before": 0,
                    "context_after": 0, "match_offset": 0, "max_matches": 10,
                },
            ),
            _json_result(relevance),
            _tool_result(
                "ana-1", "read_file",
                {"file_id": "evidence_frame_0000", "start_line": 1,
                 "end_line": 2, "start_column": 0},
            ),
            _tool_result(
                "ana-2", "read_file",
                {"file_id": "evidence_frame_0001", "start_line": 1,
                 "end_line": 2, "start_column": 0},
            ),
            _json_result(
                {"analyses": [_analysis(0, [0]), _analysis(1, [1])]}
            ),
        ]
    )
    agent, frames = _agent(
        tmp_path, client,
        [f"status=changes_present\nprice 42 USD {sentinel}\n",
         "status=changes_present\ncompleted successfully\n"],
    )
    initial = json.dumps(agent.build_relevance_initial_messages(_rubric(), "task", "url"))
    assert sentinel not in initial
    assert "input_file" not in initial and "file_data" not in initial
    assert str(tmp_path) not in initial

    matrix = asyncio.run(
        agent._score_dom_criterion_relevance(frames, _rubric(), "task", "url")
    )
    assert matrix[0][0] == 10 and matrix[1][1] == 9
    grouped = agent._group_screenshots_by_criterion(matrix, 2)
    assert grouped == {0: [0], 1: [1]}
    evidence = asyncio.run(
        agent._analyze_dom_evidence_batched(
            frames, _rubric(), grouped, "task", "url", "actions", "answer",
            relevance_scores=matrix,
        )
    )
    assert evidence[0][0]["evidence_indices"] == [0]
    assert evidence[1][0]["evidence_indices"] == [1]

    metrics = agent.grep_runtime_metrics()
    assert metrics["criterion_frame_assignments"] == {0: [0], 1: [1]}
    assert metrics["stages"]["grep_relevance"]["validation_attempts"] == 1
    assert metrics["stages"]["grep_analysis"]["validation_attempts"] == 1
    assert len(metrics["model_calls"]) == 5 and len(metrics["tool_calls"]) == 3
    assert sum(c["usage"]["prompt_tokens"] for c in metrics["model_calls"]) == 170
    assert all(c["result_chars"] > 0 for c in metrics["tool_calls"])
    analysis_initial = json.dumps(client.requests[2]["messages"])
    assert "C0=[0]" in analysis_initial and "C1=[1]" in analysis_initial
    assert sentinel not in analysis_initial
    assert sentinel in json.dumps(client.requests[3]["messages"])


def test_relevance_retry_logs_rejected_response_and_error(tmp_path):
    bad = {"frames": [{"evidence_idx": 1, "criterion_0": 5, "criterion_1": 5}]}
    good = {"frames": [{"evidence_idx": 0, "criterion_0": 5, "criterion_1": 5}]}
    client = ScriptedClient(
        [
            _tool_result(
                "rel-1", "read_file",
                {"file_id": "evidence_frame_0000", "start_line": 1,
                 "end_line": 1, "start_column": 0},
            ),
            _json_result(bad),
            _json_result(good),
        ]
    )
    agent, frames = _agent(tmp_path, client, ["status=changes_present\n"])
    result = asyncio.run(
        agent._score_dom_criterion_relevance(frames, _rubric(), "task", "url")
    )
    assert result[0][0] == 5
    failures = agent.grep_runtime_metrics()["stages"]["grep_relevance"]["validation_failures"]
    assert len(failures) == 1
    assert "Expected evidence_idx=0" in failures[0]["error"]
    assert json.dumps(bad) in failures[0]["raw_rejected_response"]


def test_analysis_reports_all_invalid_criterion_frames_together(tmp_path):
    agent, _ = _agent(
        tmp_path, ScriptedClient([]),
        ["first evidence\n", "second evidence\n", "third evidence\n"],
    )
    raw = json.dumps({"analyses": [_analysis(0, [1]), _analysis(1, [2])]})
    with pytest.raises(ValueError) as excinfo:
        agent._validate_analysis_response(
            raw, {0}, rubric=_rubric(), assignments={0: [0], 1: [0]}
        )
    error = str(excinfo.value)
    assert "Criterion 0 cited invalid FRAME [1]" in error
    assert "Criterion 1 cited invalid FRAME [2]" in error
    assert "without a successful analysis-stage tool result" in error


def test_allowed_but_never_retrieved_frame_cannot_be_cited(tmp_path):
    agent, _ = _agent(tmp_path, ScriptedClient([]), ["first\n", "second\n"])
    with pytest.raises(ValueError, match="without a successful analysis-stage"):
        agent._validate_analysis_response(
            json.dumps({"analyses": [_analysis(0, [1]), _analysis(1, [0])]}),
            {0}, rubric=_rubric(), assignments={0: [1], 1: [0]},
        )


def test_shared_transition_projection_contains_no_raw_corpus(tmp_path):
    sentinel = "RAW_TRANSITION_SENTINEL_7766"
    _, frames = _agent(
        tmp_path, ScriptedClient([]),
        [f"status=changes_present\n{sentinel}\n"],
    )
    rendered = project_dom_transition_timeline(
        frames, frame_char_budget=100, context_char_budget=100
    )
    assert sentinel not in rendered
