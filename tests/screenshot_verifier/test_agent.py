"""Offline task serialization, message preservation and client configuration."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image as PILImage


def test_task_serialization_preserves_identity_and_instruction():
    from w8bench.verifier.screenshot_verifier import DataPoint, Task

    task = Task(task_id="t1", instruction="Read the saved marker.")
    restored = DataPoint.from_dict(DataPoint(task=task).to_dict())
    assert restored.task.task_id == "t1"
    assert restored.task.instruction == "Read the saved marker."


def test_wrapper_accepts_openai_dicts_without_conversion():
    """The rubric agent emits raw OpenAI dicts. The wrappers' ``_to_oai_messages``
    must pass dicts through unchanged so no adapter is needed."""
    from w8bench.verifier.clients.providers import _to_oai_messages

    buf = io.BytesIO()
    PILImage.new("RGB", (4, 4), (255, 0, 0)).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
                },
                {"type": "text", "text": "score the image"},
            ],
        },
    ]
    out = _to_oai_messages(messages, evidence_mode='screenshot_verifier')
    assert out == messages


def test_mm_rubric_agent_config_requires_clients():
    """MMRubricAgentConfig needs at least one of the two clients or a
    config dict — construction should assert when both are missing."""
    from w8bench.verifier.screenshot_verifier import MMRubricAgent, MMRubricAgentConfig

    with pytest.raises(AssertionError):
        MMRubricAgent(config=MMRubricAgentConfig())


def test_mm_rubric_agent_accepts_client_instance():
    """Passing a pre-built ChatCompletionClient should satisfy config validation."""

    class _DummyClient:
        async def create(self, *a, **k):  # pragma: no cover — never called here
            raise RuntimeError("dummy")

        def supports_json(self):
            return True

    from w8bench.verifier.screenshot_verifier import MMRubricAgent, MMRubricAgentConfig

    agent = MMRubricAgent(
        config=MMRubricAgentConfig(
            action_client=_DummyClient(),
            judge_client=_DummyClient(),
        )
    )
    assert agent.config.action_client is not None
    assert agent.config.judge_client is not None
