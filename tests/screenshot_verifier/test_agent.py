"""Smoke tests for the ported Universal Verifier package.

These tests don't hit any LLM — they only verify the ported modules
import cleanly, the DataPoint ⇄ dict round-trip works, and the client
adapter converts OpenAI-format messages into webeval-native message
types correctly.
"""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image as PILImage


def test_rubric_agent_imports_are_self_contained():
    """Exported classes resolve to their native or shared model modules."""
    from w8bench.verifier.screenshot_verifier import (
        DataPoint,
        MMRubricAgent,
        MMRubricAgentConfig,
        MMRubricOutcomeResult,
        MMRubricResult,
        Task,
    )

    for cls in (
        MMRubricAgent,
        MMRubricAgentConfig,
        DataPoint,
        Task,
        MMRubricResult,
        MMRubricOutcomeResult,
    ):
        expected_module = ("w8bench.verifier.models" if cls in
            (MMRubricResult, MMRubricOutcomeResult) else "w8bench.verifier.screenshot_verifier")
        assert cls.__module__.startswith(expected_module), (
            f"{cls.__name__} resolved to {cls.__module__}, expected a "
            f"module inside {expected_module}"
        )

    # DataPoint round-trip
    t = Task(task_id="t1", instruction="buy socks")
    dp = DataPoint(task=t)
    restored = DataPoint.from_dict(dp.to_dict())
    assert restored.task.task_id == "t1"
    assert restored.task.instruction == "buy socks"


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
    # Identical-by-reference because each dict round-trips unchanged.
    assert out is not messages  # new list…
    assert out == messages       # …with the same contents


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
