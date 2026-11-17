"""Offline evaluation requests contracts."""
from __future__ import annotations

from PIL import Image
from PIL import Image as PILImage
from pathlib import Path
from tests.evaluation.conftest import _fake_google
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import AsyncMock, Mock
from unittest.mock import MagicMock
from unittest.mock import Mock
from w8bench.verifier import audit_requests as audit
from w8bench.verifier import audit_requests, completion, run_comparison
from w8bench.verifier import completion
from w8bench.verifier import rubric_scoring
from w8bench.verifier import run_comparison
from w8bench.verifier.rubric_scoring import validate_rescore
from w8bench.verifier.validate_inputs import parse_actions
import asyncio
import base64
import copy
import httpx
import importlib
import io
import json
import logging
import openai
import pytest


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_task_serialization_preserves_identity_and_instruction(mode):
    module = importlib.import_module(f"w8bench.verifier.{mode}")
    DataPoint, Task = module.DataPoint, module.Task

    task = Task(task_id="t1", instruction="Read the saved marker.")
    restored = DataPoint.from_dict(DataPoint(task=task).to_dict())
    assert restored.task.task_id == "t1"
    assert restored.task.instruction == "Read the saved marker."


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_wrapper_accepts_openai_dicts_without_conversion(mode):
    from w8bench.verifier.clients.providers import _to_oai_messages
    parts = [{"type": "text", "text": "score the DOM-model state"}]
    if mode == "screenshot_verifier":
        buf = io.BytesIO()
        PILImage.new("RGB", (4, 4), (255, 0, 0)).save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode()
        parts = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}", "detail": "high"}},
                 {"type": "text", "text": "score the image"}]
    messages = [{"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": parts}]
    assert _to_oai_messages(messages, evidence_mode=mode) == messages


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_mm_rubric_agent_config_requires_clients(mode):
    """MMRubricAgentConfig needs at least one of the two clients or a
    config dict — construction should assert when both are missing."""
    module = importlib.import_module(f"w8bench.verifier.{mode}")
    MMRubricAgent, MMRubricAgentConfig = module.MMRubricAgent, module.MMRubricAgentConfig

    with pytest.raises(AssertionError):
        MMRubricAgent(config=MMRubricAgentConfig())


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_mm_rubric_agent_accepts_client_instance(mode):
    """Passing a pre-built ChatCompletionClient should satisfy config validation."""

    class _DummyClient:
        async def create(self, *a, **k):  # pragma: no cover — never called here
            raise RuntimeError("dummy")

        def supports_json(self):
            return True

    module = importlib.import_module(f"w8bench.verifier.{mode}")
    MMRubricAgent, MMRubricAgentConfig = module.MMRubricAgent, module.MMRubricAgentConfig

    agent = MMRubricAgent(
        config=MMRubricAgentConfig(
            action_client=_DummyClient(),
            judge_client=_DummyClient(),
        )
    )
    assert agent.config.action_client is not None
    assert agent.config.judge_client is not None


@pytest.mark.usefixtures("inline_sdk_header_initialization")
@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_message_to_openai_format_text_only(mode):
    from w8bench.verifier.clients import SystemMessage, UserMessage, message_to_openai_format

    assert message_to_openai_format(SystemMessage(content="hi"), evidence_mode=mode) == {
        "role": "system",
        "content": "hi",
    }
    assert message_to_openai_format(UserMessage(content="ping"), evidence_mode=mode) == {
        "role": "user",
        "content": "ping",
    }


@pytest.mark.usefixtures("inline_sdk_header_initialization")
def test_message_to_openai_format_text_parts():
    from w8bench.verifier.clients import UserMessage, message_to_openai_format

    msg = UserMessage(content=["look", {"type": "text", "text": "DOM state"}])
    out = message_to_openai_format(msg, evidence_mode='dom_model')
    assert out["role"] == "user"
    parts = out["content"]
    assert len(parts) == 2
    assert parts[0] == {"type": "text", "text": "look"}
    assert parts[1] == {"type": "text", "text": "DOM state"}


@pytest.mark.usefixtures("inline_sdk_header_initialization")
@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_graceful_retry_from_path_filters_by_eval_model(tmp_path, mode):
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

    g4o = GracefulRetryClient.from_path(cfg_dir, logger=logger, eval_model="gpt-4o", evidence_mode=mode)
    assert len(g4o._clients) == 1
    assert "gpt-4o" in g4o._clients[0].description

    action = GracefulRetryClient.from_path(cfg_dir, logger=logger, eval_model="gemini-3.8-flash", evidence_mode=mode)
    assert len(action._clients) == 1
    assert "gemini-3.8-flash" in action._clients[0].description

    star = GracefulRetryClient.from_path(cfg_dir, logger=logger, eval_model="*", evidence_mode=mode)
    assert len(star._clients) == 2

    with pytest.raises(ValueError):
        GracefulRetryClient.from_path(cfg_dir, logger=logger, eval_model="nope", evidence_mode=mode)


@pytest.mark.usefixtures("inline_sdk_header_initialization")
@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_openai_wrapper_create_round_trip(monkeypatch, mode):
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

    client = OpenAIClientWrapper(mode, model="gpt-4o", api_key="sk-test")
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


@pytest.mark.usefixtures("inline_sdk_header_initialization")
@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_client_wrapper_from_config_returns_chat_client(monkeypatch, mode):
    """Construct the configured completion client."""
    from w8bench.verifier.clients import ChatCompletionClient, create_client_from_config

    cfg = {
        "CHAT_COMPLETION_PROVIDER": "openai",
        "CHAT_COMPLETION_KWARGS_JSON": {"model": "gpt-4o", "api_key": "sk-test"},
    }
    client = create_client_from_config(cfg, evidence_mode=mode)
    assert isinstance(client, ChatCompletionClient)
    assert client.metadata["model"] == "gpt-4o"
    assert client.endpoint == "gpt-4o"


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_runner_requires_shared_canonical_rubric(tmp_path, mode):
    module = importlib.import_module(f"w8bench.verifier.{mode}.runner")
    arguments = ["--input", str(tmp_path), "--rubric-file", str(tmp_path / "rubric.json"),
                 "--eval-config", str(tmp_path), "--output", str(tmp_path / "results")]
    if mode == "dom_model":
        arguments += ["--generation-metrics", str(tmp_path / "generation.json")]
    args = module.parse_args(arguments)
    assert args.rubric_file.endswith("rubric.json") and args.output.endswith("results")
    if mode == "dom_model":
        assert args.generation_metrics.endswith("generation.json")
        assert args.min_relevance_threshold == 0


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
def test_runner_normalizes_verified_one_item_task_data_format(tmp_path, mode):
    (tmp_path / "task_data.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "task4",
                    "confirmed_task": "Find product details",
                    "website": "https://example.test",
                }
            ]
        )
    )
    task = importlib.import_module(f"w8bench.verifier.{mode}.runner")._read_task_data(tmp_path)
    assert task["id"] == "task4"
    assert task["question"] == "Find product details"
    assert task["init_url"] == "https://example.test"


@pytest.mark.usefixtures("inline_sdk_header_initialization")
def test_message_to_openai_format_multimodal():
    from w8bench.verifier.clients import ImageObj, UserMessage, message_to_openai_format

    pil = PILImage.new("RGB", (4, 4), (10, 20, 30))
    msg = UserMessage(content=["look", ImageObj.from_pil(pil)])
    out = message_to_openai_format(msg, evidence_mode='screenshot_verifier')
    assert out["role"] == "user"
    parts = out["content"]
    assert len(parts) == 2
    assert parts[0] == {"type": "text", "text": "look"}
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.usefixtures("inline_sdk_header_initialization")
def test_request_usage_addition():
    from w8bench.verifier.clients import RequestUsage

    a = RequestUsage(prompt_tokens=10, completion_tokens=2)
    b = RequestUsage(prompt_tokens=5, completion_tokens=3)
    s = a + b
    assert s.prompt_tokens == 15
    assert s.completion_tokens == 5
    assert s.num_calls == 2


@pytest.mark.usefixtures("inline_sdk_header_initialization")
def test_should_include_model_exact_match():
    from w8bench.verifier.clients import GracefulRetryClient

    assert GracefulRetryClient._should_include_model("gpt-4o", "gpt-4o")
    assert GracefulRetryClient._should_include_model("gpt-4o", "*")
    assert GracefulRetryClient._should_include_model("gemini-3.8-flash", ["gpt-4o", "gemini-3.8-flash"])
    assert not GracefulRetryClient._should_include_model("gpt-4o", "gemini-3.8-flash")
    assert not GracefulRetryClient._should_include_model("gpt-4o-mini", "gpt-4o")


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
@pytest.mark.parametrize("score", [0, 10, 2.5])
def test_rescore_validation_accepts_numeric_values(package, score):
    import importlib
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    field = "post_dom" if package == "dom_model" else "post_image"
    value = {"applicable_evidence": "State 1", f"{field}_justification": "Observed", f"{field}_earned_points": score}
    assert validate_rescore(value, 10, evidence_mode=package) is None
    assert value[f"{field}_earned_points"] is score


def test_sparse_screenshot_binding_and_loading_keep_original_ids(tmp_path):
    from PIL import Image
    from w8bench.verifier.screenshot_verifier.runner import _bind_all_screenshot_evidence
    from w8bench.verifier.screenshot_verifier.rubric_agent import MMRubricAgent
    context = {"expected_state_ids": [1, 2, 3, 4], "format_gaps": {"screenshot": [2]}}
    names = ["screenshot1.png", "screenshot3.png", "screenshot4.png"]
    for index, name in enumerate(names):
        Image.new("RGB", (3, 2), (index * 70, 0, 0)).save(tmp_path / name)
    bound = _bind_all_screenshot_evidence({"action_history": "full 3 actions"}, names, 3, context)
    assert [item["id"] for item in bound["actions_list"]] == [1, 3, 4]
    images = MMRubricAgent._load_evidence(str(tmp_path), bound["actions_list"])
    assert list(images) == [1, 3, 4]
    assert images[3].getpixel((0, 0)) == (70, 0, 0)
    assert bound["action_history"] == "full 3 actions"


def test_contiguous_screenshot_binding_is_unchanged():
    from w8bench.verifier.screenshot_verifier.runner import _bind_all_screenshot_evidence
    input_value = {"action_history": "one actual action", "step_actions": [{"step_number": 1}]}
    assert _bind_all_screenshot_evidence(input_value, ["screenshot_1.png", "screenshot_2.png"], 1) == {
        **input_value, "actions_list": [{"id": 1, "screenshot": "screenshot_1.png"}, {"id": 2, "screenshot": "screenshot_2.png"}]}


def test_sparse_evidence_labels_preserve_source_id_without_dense_count_confusion():
    from w8bench.verifier.screenshot_verifier.rubric_agent import MMRubricAgent
    rubric = {"items": [{"criterion": "saved"}]}
    base = {"screenshot_idx": 4, "source_state_id": 4, "screenshot_evidence": "Saved", "criterion_analysis": "Shown", "discrepancies": "None"}
    text = MMRubricAgent._build_all_evidence_text(rubric, {0: [base]}, 3)
    assert "Screenshot state 4 (3 available)" in text and "4 of 3" not in text
    original = {key: value for key, value in base.items() if key != "source_state_id"}
    assert "Screenshot 5 of 6" in MMRubricAgent._build_all_evidence_text(rubric, {0: [original]}, 6)


def test_models_are_required_and_flags_override_environment(monkeypatch):
    monkeypatch.delenv("EVIDENCE_AUDIT_MODEL")
    with pytest.raises(ValueError, match="EVIDENCE_AUDIT_MODEL"):
        audit.resolve_audit_config()
    monkeypatch.setenv("EVIDENCE_AUDIT_MODEL", "gpt-env")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_MODEL", "gemini-env")
    assert audit.resolve_audit_config()["inventory"]["model"] == "gpt-env"
    selected = audit.resolve_audit_config("custom-inventory", "custom-judge", "google", "openai")
    assert selected == {"inventory": {"model": "custom-inventory", "provider": "google"},
                        "adjudication": {"model": "custom-judge", "provider": "openai"}}
    monkeypatch.delenv("EVIDENCE_ADJUDICATOR_MODEL")
    with pytest.raises(ValueError, match="EVIDENCE_ADJUDICATOR_MODEL"):
        audit.resolve_audit_config()


def test_cli_requires_explicit_completion_judge_and_keeps_audit_provider_config(monkeypatch):
    parsed = run_comparison.parse_args(["--run", "recording", "--rubric", "rubric.json", "--judge-model", "gpt-6.1-sol"])
    assert parsed.judge_model == "gpt-6.1-sol"
    assert parsed.judge_evidence_policy == "paired"
    with pytest.raises(SystemExit):
        run_comparison.parse_args(["--run", "recording", "--rubric", "rubric.json"])
    with pytest.raises(SystemExit):
        run_comparison.parse_args(["--run", "recording", "--rubric", "rubric.json", "--judge-model", "actor-model"])
    monkeypatch.setenv("EVIDENCE_AUDIT_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_MODEL", "gpt-6.1-sol")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_PROVIDER", "openai")
    selected = audit.resolve_audit_config()
    assert selected["inventory"] == {"model": "gemini-3.1-pro-preview", "provider": "google"}
    assert selected["adjudication"] == {"model": "gpt-6.1-sol", "provider": "openai"}


@pytest.mark.parametrize("model,provider", [("gemini-test", "google"), ("gpt-test", "openai"), ("o3", "openai"), ("o4-mini", "openai")])
def test_provider_inference(model, provider):
    assert audit.resolve_provider(model) == provider


def test_unknown_and_latest_fail_clearly():
    with pytest.raises(ValueError, match="set EVIDENCE"):
        audit.resolve_provider("custom-model")
    assert audit.resolve_provider("custom-model", "google") == "google"
    with pytest.raises(ValueError, match="latest"):
        audit.resolve_provider("gpt-latest", "openai")


def test_model_checks_require_exact_id(monkeypatch):
    constructor = MagicMock()
    constructor.return_value.__enter__.return_value.models.list.return_value = [SimpleNamespace(id="custom-a"), SimpleNamespace(id="custom-b")]
    monkeypatch.setattr(audit, "OpenAI", constructor)
    config = audit.resolve_audit_config("custom-a", "custom-b", "openai", "openai")
    checked = audit.check_audit_models(config)
    assert checked["stages"]["inventory"]["model_listed"] is True
    assert checked["stages"]["inventory"]["listed_at"]
    assert constructor.call_count == 1
    config["inventory"]["model"] = "custom"
    with pytest.raises(ValueError, match="not listed exactly"):
        audit.check_audit_models(config)


@pytest.mark.parametrize("status,retry", [(429, True), (500, True), (503, True), (400, False), (401, False), (403, False), (404, False), (408, False)])
def test_transport_status_retry_policy(monkeypatch, status, retry):
    class Error(Exception):
        status_code = status
    sleeps, record = [], {}
    monkeypatch.setattr(audit.time, "sleep", sleeps.append)
    def fail():
        raise Error("technical error")
    with pytest.raises(Error):
        audit._transport_request(fail, record)
    assert len(record["transport_attempts"]) == (3 if retry else 1)
    assert sleeps == ([1, 2] if retry else [])


def test_connection_retries_are_logged_and_secrets_redacted(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-secret-for-test")
    monkeypatch.setattr(audit.time, "sleep", lambda value: None)
    seen, record = [], {}
    def call():
        seen.append(True)
        if len(seen) < 3:
            raise ConnectionError("fake-secret-for-test")
        return "ok"
    assert audit._transport_request(call, record) == "ok"
    assert len(record["transport_attempts"]) == 3
    assert "fake-secret-for-test" not in str(record)
    assert record["transport_attempts"][-1]["status"] == "accepted"


def test_explicit_google_provider_uses_google_settings_for_any_model_id(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    _, generate = _fake_google(monkeypatch)
    audit._completion("custom-model", [{"role": "system", "content": audit.SYSTEM_PROMPT}], provider="google")
    config = generate.call_args.kwargs["config"]
    assert config["media_resolution"] == "MEDIA_RESOLUTION_HIGH"
    assert "temperature" not in config and "seed" not in config and "thinking_config" not in config


@pytest.mark.parametrize("mode", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("tokens,accepted", [(115000, True), (115001, False)])
def test_verifier_input_guard_checks_the_boundary_before_transport(mode, tokens, accepted):
    from w8bench.verifier.clients.messages import CreateResult
    from w8bench.verifier.clients.retry import GracefulRetryClient
    endpoint = SimpleNamespace(description="offline-verifier", endpoint="offline-verifier",
        count_tokens=lambda **kwargs: tokens,
        create=AsyncMock(return_value=CreateResult(content='{"marker":"SAVED"}')))
    pool = GracefulRetryClient(clients=[endpoint], max_tokens=115000,
        max_retries=1, evidence_mode=mode)
    messages = [{"role": "user", "content": "Read the saved marker."}]
    if accepted:
        result = asyncio.run(pool.create(messages=messages, json_output=True))
        assert json.loads(result.content) == {"marker": "SAVED"}
        endpoint.create.assert_awaited_once_with(messages=messages, tools=(),
            json_output=True, extra_create_args={})
    else:
        with pytest.raises(RuntimeError, match="115001 tokens exceeding 115000"):
            asyncio.run(pool.create(messages=messages, json_output=True))
        endpoint.create.assert_not_awaited()


def test_action_judge_model_matches_both_packages_and_endpoint_config():
    from w8bench.verifier.dom_model.runner import CANONICAL_ACTION_MODEL as dom_model
    from w8bench.verifier.common import CANONICAL_ACTION_MODEL, validate_endpoint_configs

    root = Path(__file__).resolve().parents[2]
    assert CANONICAL_ACTION_MODEL == dom_model == "gemini-3.8-flash"
    validate_endpoint_configs(root / "config")
    endpoint = json.loads((root / "config/google_gemini3_8_flash.json").read_text())
    assert endpoint["CHAT_COMPLETION_KWARGS_JSON"]["model"] == CANONICAL_ACTION_MODEL


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
def test_standalone_verifier_models_are_pinned(package):
    module = importlib.import_module(f"w8bench.verifier.{package}.runner")
    arguments = ["--input", "task", "--rubric-file", "rubric.json",
                 "--eval-config", "config", "--output", "result.json"]
    if package == "dom_model":
        arguments += ["--generation-metrics", "metrics.json"]
    assert module.parse_args(arguments).action_model == "gemini-3.8-flash"
    assert module.parse_args(arguments).judge_model == "gemini-3.1-pro-preview"
    with pytest.raises(SystemExit):
        module.parse_args(arguments + ["--action-model", "custom-model"])
    with pytest.raises(SystemExit):
        module.parse_args(arguments + ["--judge-model", "custom-model"])


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
@pytest.mark.parametrize("action,keys,expected", [
    ("left_click", ["ref", "target", "thoughts"], None),
    ("left_click", ["coordinate", "_call_id"], None),
    ("type", ["text", "thoughts"], None),
    ("type", ["ref", "text", "target", "delete_existing_text"], None),
    ("scroll", ["ref", "pixels", "target", "thoughts"], None),
    ("select", ["ref", "text", "target", "thoughts"], None),
    ("key", ["key", "thoughts"], None),
    ("key", ["keys"], None),
    ("wait", ["seconds", "thoughts"], None),
    ("wait", ["time"], None),
    ("left_click", ["ref", "unexpected_parameter"], "6.1"),
    ("visit_url", ["url", "ref"], "6.1"),
    ("invented_action", ["ref", "thoughts"], "6.2"),
])
def test_diagnostics_recognize_commands_without_hiding_real_errors(package, action, keys, expected):
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    schema = rubric_scoring
    steps = [{"step_number": 1, "action_name": action, "action_args_keys": keys}]
    original = copy.deepcopy(steps)
    errors = rubric_scoring.detect_tool_interaction_errors(steps, schema.FARA_ACTION_DEFINITIONS)
    assert [row["error_code"] for row in errors] == ([expected] if expected else [])
    assert steps == original


def test_both_verifiers_use_identical_diagnostic_definitions():
    from w8bench.verifier.dom_model.runner import FARA_ACTION_DEFINITIONS as dom_definitions
    from w8bench.verifier.screenshot_verifier.runner import FARA_ACTION_DEFINITIONS as screenshot_definitions
    assert dom_definitions is screenshot_definitions is rubric_scoring.FARA_ACTION_DEFINITIONS
    assert rubric_scoring.ACTION_METADATA_KEYS == {"thoughts", "target"}


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
def test_diagnostic_filter_does_not_strip_judge_action_context(package):
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    models = importlib.import_module(f"w8bench.verifier.{package}.models")
    schema = rubric_scoring
    arguments = {"ref": "e1", "target": {"role": "button", "name": "Save"},
                 "coordinate": [20, 30], "thoughts": "Save the value."}
    summary = models.StepSummary(index=1, action_name="left_click", action_args=arguments)
    history = module.MMRubricAgent._format_action_history([summary])
    steps = [{"step_number": 1, "action_name": "left_click", "action_args_keys": list(arguments)}]
    assert rubric_scoring.detect_tool_interaction_errors(steps, schema.FARA_ACTION_DEFINITIONS) == []
    assert module.MMRubricAgent._format_action_history([summary]) == history
    for key in arguments:
        assert f'"{key}"' in history


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
def test_failure_analysis_explains_metadata_without_changing_history(package):
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    schema = rubric_scoring
    agent = object.__new__(module.MMRubricAgent)
    agent.config = SimpleNamespace(action_definitions=schema.FARA_ACTION_DEFINITIONS,
                                   max_iters=1, judge_client=None)
    agent._call_llm = AsyncMock(return_value=json.dumps({
        "reasoning": "The recorded command is valid.", "has_failure": False, "failure_points": []
    }))
    history = 'left_click({"ref":"e1","target":{"name":"Save"},"thoughts":"Save it"})'
    result = asyncio.run(agent._first_point_of_failure_analysis(
        rubric={"items": []}, evidence_by_criterion={}, task="Inspect the page.",
        init_url_context="", action_history=history, predicted_output="Done.",
        outcome_result={"output_success": True},
        step_actions=[{"step_number": 1, "action_name": "left_click",
                       "action_args_keys": ["ref", "target", "thoughts"]}],
    ))
    assert result["has_failure"] is False
    agent._call_llm.assert_awaited_once()
    prompt = agent._call_llm.call_args.args[0][-1]["content"]
    assert history in prompt
    assert "Recorder annotations (target, thoughts)" in prompt
    assert "their presence alone is not an invalid invocation" in prompt


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
@pytest.mark.parametrize("earned", [0, 5, 10])
@pytest.mark.parametrize("success", [False, True])
def test_failure_diagnostics_do_not_change_numeric_or_outcome_scores(package, earned, success):
    module = importlib.import_module(f"w8bench.verifier.{package}.rubric_agent")
    # Exercise pure result wrapping without constructing any API clients.
    agent = object.__new__(module.MMRubricAgent)
    agent.config = SimpleNamespace(rubric_score_threshold=0.8)
    field = "post_dom_earned_points" if package == "dom_model" else "post_image_earned_points"
    result = {"items": [{"criterion": "Recorded fact", "max_points": 10, field: earned}],
              "total_max_points": 10, "total_earned_points": earned,
              "outcome_verification": {"output_success": success}}
    changed = copy.deepcopy(result)
    changed["first_point_of_failure"] = {"has_failure": True, "first_failure_step": 1}
    changed["intermediate_mm_rubric_steps"] = {"step9_first_point_of_failure": changed["first_point_of_failure"]}
    before, after = agent._wrap_result(result), agent._wrap_result(changed)
    assert before[0].score == after[0].score == earned / 10
    assert before[0].rubric_is_success == after[0].rubric_is_success == (earned >= 8)
    assert before[1].output_success == after[1].output_success == success
    assert rubric_scoring.compute_final_scores(result, field) == rubric_scoring.compute_final_scores(changed, field)
    assert module.MMRubricAgent._build_scored_rubric_summary(result) == module.MMRubricAgent._build_scored_rubric_summary(changed)


def test_keyboard_typing_does_not_require_an_element_ref(tmp_path):
    log = tmp_path / "web_surfer.log"
    log.write_text(json.dumps({"action": "type", "arguments": {"action": "type", "text": "Find this"}}) + "\n")
    assert parse_actions(log, mode="dom_model")[0]["text"] == "Find this"


def test_explicit_fill_still_requires_a_target(tmp_path):
    log = tmp_path / "web_surfer.log"
    log.write_text(json.dumps({"action": "fill", "arguments": {"action": "fill", "text": "value"}}) + "\n")
    with pytest.raises(ValueError, match="requires ref or target"):
        parse_actions(log, mode="dom_model")


def test_screenshot_click_with_ref_does_not_require_coordinates(tmp_path):
    log = tmp_path / "screenshot.log"
    log.write_text(
        json.dumps({"action": "left_click", "arguments": {"action": "left_click", "ref": "e107"}}) + "\n",
        encoding="utf-8",
    )

    actions = parse_actions(log, mode="screenshot")

    assert actions[0]["action"] == "click"
    assert actions[0]["ref"] == "e107"


@pytest.mark.parametrize("kind", ["authentication", "access_token"])
def test_authentication_refresh_obeys_attempt_budget_and_retains_receipts(monkeypatch, kind):
    from w8bench.verifier.clients.retry import GracefulRetryClient
    response = httpx.Response(401 if kind == "authentication" else 400,
        request=httpx.Request("POST", "https://offline.example.test"))
    error = (openai.AuthenticationError if kind == "authentication" else openai.BadRequestError)(
        "check-access-response-enc" if kind == "access_token" else "invalid credentials", response=response, body={})
    receipts = []
    async def create(**kwargs):
        receipts.append({"error_type": type(error).__name__, "usage_reported": False})
        if len(receipts) > 2:
            raise RuntimeError("attempt budget exceeded")
        raise error
    endpoint = SimpleNamespace(description="offline", endpoint="offline", count_tokens=lambda **kwargs: 1,
        create=create, refresh_credentials=Mock(), _call_records=receipts)
    monkeypatch.setattr("w8bench.verifier.clients.retry.asyncio.sleep", AsyncMock())
    pool = GracefulRetryClient([endpoint], max_retries=2)
    with pytest.raises(type(error), match="credentials|check-access"):
        asyncio.run(pool.create([{"role": "user", "content": "Read marker"}]))
    assert len(receipts) == 2 and all(row["usage_reported"] is False for row in receipts)
    assert endpoint.refresh_credentials.call_count == 1


@pytest.mark.parametrize("returned", [None, "gpt-5.2", "gpt-6.1-sol-mini"])
def test_completion_refuses_other_or_missing_judge_ids_and_keeps_usage(completion_case, returned):
    case = completion_case
    case.responses.append({"model": returned, "status": "completed", "usage": {"input_tokens": 7, "output_tokens": 3},
        "output_text": json.dumps({"criteria": [{"id": name, "verdict": "success", "reason": "Visible marker", "states": [1]}
            for name in ("saved", "source")]})})
    grade = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gpt-6.1-sol", api_key="offline", execute=True))
    assert grade["verdict"] == grade["method"] == "ungraded"
    assert grade["usage"] == {"input_tokens": 7, "output_tokens": 3}
    assert grade["model_id_match"]["matched"] is False
    assert grade["refusal_reason"]


@pytest.mark.parametrize("returned,form", [("gpt-6.1-sol", "exact"),
    ("gpt-6.1-sol-2026-09-29", "suffix"), ("gpt-6.1-sol-001", "suffix")])
def test_completion_records_accepted_model_form(completion_case, returned, form):
    case = completion_case
    case.responses.append({"model": returned, "status": "completed", "usage": {"input_tokens": 7, "output_tokens": 3},
        "output_text": json.dumps({"criteria": [{"id": name, "verdict": "success", "reason": "Visible marker", "states": [1]}
            for name in ("saved", "source")]})})
    grade = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gpt-6.1-sol", api_key="offline", execute=True))
    assert grade["verdict"] == "success"
    assert grade["model_id_match"]["form"] == form
    assert grade["acceptance_policy_version"]


@pytest.mark.parametrize("metadata", [{"status": "incomplete"}, {"truncated": True},
    {"output_limit_hit": True}, {"usage": {"input_tokens": 7, "output_tokens": 10000}}])
def test_completion_refuses_incomplete_or_capped_output(completion_case, metadata):
    case = completion_case
    case.responses.append({"model": "gpt-6.1-sol", "status": "completed", "usage": {"input_tokens": 7, "output_tokens": 3},
        "output_text": json.dumps({"criteria": [{"id": name, "verdict": "success", "reason": "Visible marker", "states": [1]}
            for name in ("saved", "source")]}), **metadata})
    grade = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gpt-6.1-sol", api_key="offline", execute=True))
    assert grade["verdict"] == "ungraded"
    assert grade["refusal_reason"] and grade["judge_calls"] == 1


@pytest.mark.parametrize("returned,incomplete", [(None, False), ("gpt-5.2", False), ("gpt-6.1-sol", True)])
def test_audit_refuses_response_metadata_and_retains_each_call(monkeypatch, returned, incomplete):
    def respond(model, messages, record, hooks):
        record.update(response_model=returned, incomplete=incomplete, usage={"prompt_tokens": 9, "completion_tokens": 2})
        return '{}'
    monkeypatch.setattr(audit_requests, "_openai_completion", respond)
    records = []
    with pytest.raises(ValueError, match="model|incomplete"):
        audit_requests._completion("gpt-6.1-sol", [{"role": "system", "content": audit_requests.ADJUDICATION_SYSTEM_PROMPT}], records=records)
    assert len(records) == 1 and records[0]["usage"]["prompt_tokens"] == 9
    assert records[0]["refusal_reason"]


@pytest.mark.parametrize("field", ["instruction", "start_url"])
def test_rubric_import_refuses_definition_drift_before_writing(tmp_path, field):
    task = {"source_task_id": "one", "instruction": "Read the marker", "start_url": "https://example.test"}
    supplied = {"task_id": "one", "instruction": task["instruction"], "start_url": task["start_url"],
        "criteria": [{"id": "marker", "description": "Marker visible"}]}
    supplied[field] = "Another task" if field == "instruction" else "https://other.test"
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps(supplied))
    root = tmp_path / "evaluation"
    with pytest.raises(ValueError, match=field):
        run_comparison._prepare_rubric(SimpleNamespace(rubric=path), root, task, Mock())
    assert not root.exists()


@pytest.mark.parametrize("prompt,candidates,thoughts,total", [(None, None, None, None),
    (7, 3, None, None), (None, 3, 2, None), (7, 3, 2, 12)])
def test_audit_usage_keeps_unknown_components_and_partial_lower_bounds(prompt, candidates, thoughts, total):
    from google.genai.types import GenerateContentResponseUsageMetadata
    usage = GenerateContentResponseUsageMetadata(prompt_token_count=prompt,
        candidates_token_count=candidates, thoughts_token_count=thoughts, total_token_count=total)
    response = SimpleNamespace(usage_metadata=usage, response_id="offline", model_version="gemini-3.1-pro-preview",
        candidates=[], text='{}')
    record = {}
    audit_requests._record_gemini_response(record, response, {})
    normalized = record["usage"]
    assert normalized["prompt_tokens"] is prompt
    assert normalized["completion_tokens"] == (candidates + thoughts if candidates is not None and thoughts is not None else None)
    assert normalized["total_tokens"] == total
    assert record["usage_coverage"] == ("complete" if prompt is not None and candidates is not None and thoughts is not None else "partial" if any(v is not None for v in (prompt,candidates,thoughts)) else "unknown")
    known = [v for v in (prompt,candidates,thoughts) if v is not None]
    assert record["usage_lower_bound"]["total_tokens"] == (sum(known) if known else None)


@pytest.mark.parametrize("inventory", [False, True])
@pytest.mark.parametrize("eventually_valid", [False, True])
def test_audit_refusals_consume_the_stage_budget_without_losing_usage(monkeypatch, tmp_path, inventory, eventually_valid):
    records, invalid = [], []
    def respond(model, messages, record, hooks):
        accepted = eventually_valid and len(records) == 3
        record.update(response_model=model if accepted else "gpt-5.2", incomplete=False,
            usage={"prompt_tokens": 9, "completion_tokens": 2})
        return '{"criteria":[]}'
    monkeypatch.setattr(audit_requests, "_openai_completion", respond)
    validator = Mock(return_value=[])
    monkeypatch.setattr(audit_requests, "validate_audit_response" if inventory else "validate_adjudication_response", validator)
    def complete(model, messages):
        return audit_requests._completion(model, messages, records=records)
    arguments = dict(model="gpt-6.1-sol", messages=[{"role": "system", "content": audit_requests.SYSTEM_PROMPT if inventory else audit_requests.ADJUDICATION_SYSTEM_PROMPT}],
        criteria=[], screenshot_sources=set(), dom_sources=set(), screenshot_root=tmp_path, dom_root=tmp_path,
        complete=complete, max_attempts=3, invalid_receipts=invalid, inventory=inventory)
    if eventually_valid:
        _, _, attempts = audit_requests._request_validated_audit(**arguments)
        assert attempts == 3 and validator.call_count == 1
    else:
        with pytest.raises(audit_requests.AuditValidationError, match="after 3 attempts"):
            audit_requests._request_validated_audit(**arguments)
        assert validator.call_count == 0
    assert len(records) == 3 and len(invalid) == (2 if eventually_valid else 3)
    assert sum(row["usage"]["prompt_tokens"] for row in records) == 27
    assert all(row["model_id_match"]["form"] == "refused" for row in records[:2])
