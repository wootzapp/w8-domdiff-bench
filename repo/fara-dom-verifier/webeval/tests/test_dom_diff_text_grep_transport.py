from __future__ import annotations

import json
from types import SimpleNamespace

from webeval.oai_clients.messages import CreateResult
from webeval.rubric_agent.dom_diff_text_grep_transport import (
    append_assistant_tool_calls,
    append_tool_output,
    normalize_tool_calls,
    response_family,
)


def test_chat_tool_call_normalization_and_transcript():
    raw = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="grep_evidence", arguments=json.dumps({"query": "price"})
        ),
    )
    message = SimpleNamespace(content=None, tool_calls=[raw])
    result = CreateResult(
        content="", message=message, tool_calls=[raw], finish_reason="tool_calls"
    )
    calls = normalize_tool_calls(result)
    assert calls[0].name == "grep_evidence"
    assert calls[0].arguments == {"query": "price"}
    messages = []
    family = append_assistant_tool_calls(messages, result, calls)
    append_tool_output(
        messages, family=family, call_id="call_1", output='{"ok":true}'
    )
    assert family == "chat"
    assert messages[0]["role"] == "assistant"
    assert messages[1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": '{"ok":true}',
    }


def test_responses_tool_call_normalization_and_transcript():
    call = {
        "type": "function_call",
        "call_id": "call_r",
        "name": "read_file",
        "arguments": '{"file_id":"evidence_frame_0000"}',
    }
    response = SimpleNamespace(output=[call])
    result = CreateResult(content="", message=response, finish_reason="completed")
    calls = normalize_tool_calls(result)
    assert calls[0].call_id == "call_r"
    assert calls[0].name == "read_file"
    assert response_family(result) == "responses"
    messages = []
    family = append_assistant_tool_calls(messages, result, calls)
    append_tool_output(
        messages, family=family, call_id="call_r", output='{"ok":true}'
    )
    assert messages[0] == call
    assert messages[1] == {
        "type": "function_call_output",
        "call_id": "call_r",
        "output": '{"ok":true}',
    }
