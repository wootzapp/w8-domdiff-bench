"""Offline verifier message conversion, model selection and usage contracts."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest


def test_message_to_openai_format_text_only():
    from w8bench.verifier.clients import SystemMessage, UserMessage, message_to_openai_format

    assert message_to_openai_format(SystemMessage(content="hi"), evidence_mode='dom_model') == {
        "role": "system",
        "content": "hi",
    }
    assert message_to_openai_format(UserMessage(content="ping"), evidence_mode='dom_model') == {
        "role": "user",
        "content": "ping",
    }


def test_message_to_openai_format_text_parts():
    from w8bench.verifier.clients import UserMessage, message_to_openai_format

    msg = UserMessage(content=["look", {"type": "text", "text": "DOM state"}])
    out = message_to_openai_format(msg, evidence_mode='dom_model')
    assert out["role"] == "user"
    parts = out["content"]
    assert len(parts) == 2
    assert parts[0] == {"type": "text", "text": "look"}
    assert parts[1] == {"type": "text", "text": "DOM state"}


def test_graceful_retry_from_path_filters_by_eval_model(tmp_path):
    from w8bench.verifier.clients import GracefulRetryClient

    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    # Two configs: one gpt-4o, one gemini-3.8-flash.
    (cfg_dir / "a.json").write_text(
        json.dumps(
            {
                "CHAT_COMPLETION_PROVIDER": "openai",
                "CHAT_COMPLETION_KWARGS_JSON": {
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                },
            }
        )
    )
    (cfg_dir / "b.json").write_text(
        json.dumps(
            {
                "CHAT_COMPLETION_PROVIDER": "google",
                "CHAT_COMPLETION_KWARGS_JSON": {
                    "model": "gemini-3.8-flash",
                    "api_key": "sk-test",
                },
            }
        )
    )

    import logging

    logger = logging.getLogger(__name__)

    g4o = GracefulRetryClient.from_path(cfg_dir, logger=logger, eval_model="gpt-4o", evidence_mode='dom_model')
    assert len(g4o._clients) == 1
    assert "gpt-4o" in g4o._clients[0].description

    action = GracefulRetryClient.from_path(cfg_dir, logger=logger, eval_model="gemini-3.8-flash", evidence_mode='dom_model')
    assert len(action._clients) == 1
    assert "gemini-3.8-flash" in action._clients[0].description

    star = GracefulRetryClient.from_path(cfg_dir, logger=logger, eval_model="*", evidence_mode='dom_model')
    assert len(star._clients) == 2

    with pytest.raises(ValueError):
        GracefulRetryClient.from_path(cfg_dir, logger=logger, eval_model="nope", evidence_mode='dom_model')


def test_openai_wrapper_create_round_trip(monkeypatch):
    """Stub the OpenAI client and verify .create() returns a CreateResult
    with text content and updated usage."""
    from w8bench.verifier.clients import UserMessage, OpenAIClientWrapper

    captured = {}

    async def fake_chat_create(**kwargs):
        captured["kwargs"] = kwargs
        message = SimpleNamespace(content="hi there", tool_calls=None)
        choice = SimpleNamespace(message=message, finish_reason="stop")
        usage = SimpleNamespace(
            prompt_tokens=12,
            completion_tokens=3,
            completion_tokens_details=None,
        )
        return SimpleNamespace(choices=[choice], usage=usage)

    client = OpenAIClientWrapper('dom_model', model="gpt-4o", api_key="sk-test")
    monkeypatch.setattr(
        client.client.chat.completions, "create", fake_chat_create, raising=True
    )

    result = asyncio.run(
        client.create(messages=[UserMessage(content="ping")])
    )
    assert result.content == "hi there"
    assert result.finish_reason == "stop"
    assert result.usage.prompt_tokens == 12
    assert result.usage.completion_tokens == 3
    assert client.total_usage().prompt_tokens == 12
    # Verify message conversion routed correctly.
    assert captured["kwargs"]["messages"] == [{"role": "user", "content": "ping"}]
    assert captured["kwargs"]["model"] == "gpt-4o"


def test_client_wrapper_from_config_returns_chat_client(monkeypatch):
    """Construct the configured completion client."""
    from w8bench.verifier.clients import ChatCompletionClient, create_client_from_config

    cfg = {
        "CHAT_COMPLETION_PROVIDER": "openai",
        "CHAT_COMPLETION_KWARGS_JSON": {"model": "gpt-4o", "api_key": "sk-test"},
    }
    client = create_client_from_config(cfg, evidence_mode='dom_model')
    assert isinstance(client, ChatCompletionClient)
    assert client.metadata["model"] == "gpt-4o"
    assert client.endpoint == "gpt-4o"
