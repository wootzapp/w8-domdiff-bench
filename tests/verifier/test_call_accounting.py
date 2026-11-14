from w8bench.verifier.common import sum_call_metrics, sum_usage


def test_call_and_token_accounting_keeps_reasoning_as_subset():
    calls = sum_call_metrics(
        {"logical_calls": 2, "api_attempts": 3},
        {"logical_calls": 1, "api_attempts": 1},
    )
    assert calls == {"logical_calls": 3, "api_attempts": 4, "retries": 1}
    usage = sum_usage(
        {"prompt_tokens": 10, "completion_tokens": 5, "reasoning_tokens": 3, "total_tokens": 15},
        {"prompt_tokens": 4, "completion_tokens": 2, "reasoning_tokens": 1, "total_tokens": 6},
    )
    assert usage == {"prompt_tokens": 14, "completion_tokens": 7, "reasoning_tokens": 4, "total_tokens": 21}



import asyncio
import importlib
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI, BadRequestError


@pytest.fixture(autouse=True)
def inline_sdk_header_initialization(monkeypatch):
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(asyncio, "to_thread", inline)


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_wire_attempts_and_provider_usage_without_changing_requests(monkeypatch, package):
    wrapper = importlib.import_module(f"w8bench.verifier.{package}.clients.wrapper")
    requests = []
    async def respond(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(500, json={"error": {"message": "temporary", "type": "server_error"}}, headers={"retry-after-ms": "1"})
        return httpx.Response(200, json={"id": "response-1", "object": "chat.completion", "created": 0,
            "model": "resolved-gpt-5.2-2026", "choices": [{"index": 0, "finish_reason": "length", "message": {"role": "assistant", "content": "{}"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30,
                "prompt_tokens_details": {"cached_tokens": 8}, "completion_tokens_details": {"reasoning_tokens": 6}}})
    def sdk(**kwargs):
        return AsyncOpenAI(http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)), **kwargs)
    monkeypatch.setattr(wrapper, "AsyncOpenAI", sdk)
    client = wrapper.OpenAIClientWrapper(api_key="offline-test", model="gpt-5.2")
    async def exercise():
        try:
            await client.create([{"role": "user", "content": "unchanged"}], json_output=True)
        finally:
            await client.close()
    asyncio.run(exercise())
    assert len(requests) == 2
    assert requests[0] == requests[1] == {"model": "gpt-5.2", "messages": [{"role": "user", "content": "unchanged"}], "response_format": {"type": "json_object"}}
    record, = client._call_records
    assert record["configured_model"] == record["requested_model"] == "gpt-5.2"
    assert record["returned_model"] == "resolved-gpt-5.2-2026"
    assert record["reasoning_effort"] is None and record["temperature"] is None and record["max_output_tokens"] is None
    assert record["http_attempts"] == 2 and record["http_attempts_observed"] is True
    assert record["input_tokens"] == 20 and record["output_tokens"] == 10
    assert record["cached_input_tokens"] == 8 and record["reasoning_tokens"] == 6
    assert record["total_tokens"] == 30 and record["cache_write_input_tokens"] is None
    assert record["output_limit_hit"] is True and record["finish_reason"] == "length"
    assert client.total_usage().prompt_tokens == 20 and client.total_usage().completion_tokens == 10


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_failed_provider_call_retains_wire_attempt_and_unknown_usage(monkeypatch, package):
    wrapper = importlib.import_module(f"w8bench.verifier.{package}.clients.wrapper")
    async def respond(request):
        return httpx.Response(400, json={"error": {"message": "invalid request", "type": "invalid_request_error"}})
    monkeypatch.setattr(wrapper, "AsyncOpenAI", lambda **kwargs: AsyncOpenAI(http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)), **kwargs))
    client = wrapper.OpenAIClientWrapper(api_key="offline-test", model="gpt-5.2")
    async def exercise():
        try:
            with pytest.raises(BadRequestError):
                await client.create([{"role": "user", "content": "test"}])
        finally:
            await client.close()
    asyncio.run(exercise())
    record, = client._call_records
    assert record["http_attempts"] == 1
    assert record["usage_reported"] is False and record["returned_model"] is None
    assert record["error_type"] == "BadRequestError"


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_missing_subsets_stay_unknown_and_stage_survives_timeout_task(monkeypatch, package):
    wrapper = importlib.import_module(f"w8bench.verifier.{package}.clients.wrapper")
    graceful = importlib.import_module(f"w8bench.verifier.{package}.clients.graceful_client")
    accounting = importlib.import_module(f"w8bench.verifier.{package}." + ("instrumentation" if package == "dom_model" else "runner"))
    async def respond(request):
        return httpx.Response(200, json={"id": "response-1", "object": "chat.completion", "created": 0,
            "model": "gpt-5.2", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "{}"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}})
    monkeypatch.setattr(wrapper, "AsyncOpenAI", lambda **kwargs: AsyncOpenAI(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)), **kwargs))
    endpoint = wrapper.OpenAIClientWrapper(api_key="offline-test", model="gpt-5.2")
    monkeypatch.setattr(endpoint, "count_tokens", lambda **kwargs: 0)
    client = graceful.GracefulRetryClient([endpoint], timeout=1)
    (accounting.instrument_client_calls if package == "dom_model" else accounting._instrument_client_calls)(client)
    namespace = {"__name__": f"w8bench.verifier.{package}.rubric_agent", "client": client}
    exec("async def _offline_scoring_stage():\n    return await client.create([{'role': 'user', 'content': 'offline'}])", namespace)
    async def exercise():
        try:
            await namespace["_offline_scoring_stage"]()
        finally:
            await client.close()
    asyncio.run(exercise())
    record, = endpoint._call_records
    assert record["stage"] == f"w8bench.verifier.{package}.rubric_agent._offline_scoring_stage"
    assert record["stage_call_path"] == [record["stage"]]
    assert record["reasoning_tokens"] is None and record["cached_input_tokens"] is None
    assert record["cache_write_input_tokens"] is None
    assert endpoint.total_usage().reasoning_tokens == 0
    usage = (accounting.usage_dict if package == "dom_model" else accounting._usage_dict)(client)
    assert usage["reasoning_tokens"] is None and usage["cached_input_tokens"] is None
    assert usage["total_tokens"] == 30
    assert usage["usage_known_calls"]["input_tokens"] == usage["usage_known_calls"]["output_tokens"] == 1
    assert usage["usage_known_calls"]["reasoning_tokens"] == usage["usage_known_calls"]["cached_input_tokens"] == 0


@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("reported_zero", [False, True])
def test_unreported_provider_usage_is_distinct_from_reported_zero(monkeypatch, package, reported_zero):
    wrapper = importlib.import_module(f"w8bench.verifier.{package}.clients.wrapper")
    accounting = importlib.import_module(f"w8bench.verifier.{package}." + ("instrumentation" if package == "dom_model" else "runner"))
    async def respond(request):
        payload = {"id": "response-1", "object": "chat.completion", "created": 0,
            "model": "gpt-5.2", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "{}"}}]}
        if reported_zero:
            payload["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return httpx.Response(200, json=payload)
    monkeypatch.setattr(wrapper, "AsyncOpenAI", lambda **kwargs: AsyncOpenAI(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)), **kwargs))
    endpoint = wrapper.OpenAIClientWrapper(api_key="offline-test", model="gpt-5.2")
    async def exercise():
        try:
            await endpoint.create([{"role": "user", "content": "offline"}])
        finally:
            await endpoint.close()
    asyncio.run(exercise())
    usage = (accounting.usage_dict if package == "dom_model" else accounting._usage_dict)(SimpleNamespace(_clients=[endpoint]))
    expected = 0 if reported_zero else None
    assert usage["prompt_tokens"] == usage["input_tokens"] == expected
    assert usage["completion_tokens"] == usage["output_tokens"] == expected
    assert usage["total_tokens"] == expected
    assert usage["usage_known_calls"]["input_tokens"] == usage["usage_known_calls"]["output_tokens"] == int(reported_zero)
    assert usage["calls_without_reported_usage"] == int(not reported_zero)
    assert endpoint._call_records[0]["input_tokens"] == expected
    assert endpoint._call_records[0]["output_tokens"] == expected
    assert endpoint.total_usage().prompt_tokens == endpoint.total_usage().completion_tokens == 0


def test_combined_usage_preserves_missing_instead_of_zero():
    unknown = {'prompt_tokens': None, 'completion_tokens': None, 'total_tokens': None,
        'cached_input_tokens': None, 'reasoning_tokens': None, 'usage_known_calls': {'input_tokens': 0}}
    combined = sum_usage(unknown, unknown)
    assert combined['prompt_tokens'] is None and combined['input_tokens'] is None
    assert combined['completion_tokens'] is None and combined['output_tokens'] is None
    assert combined['total_tokens'] is None and combined['usage_known_calls']['input_tokens'] == 0
    reported_zero = {**unknown, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
        'usage_known_calls': {'input_tokens': 1}}
    combined = sum_usage(unknown, reported_zero)
    assert combined['input_tokens'] == combined['output_tokens'] == combined['total_tokens'] == 0
    assert combined['usage_known_calls']['input_tokens'] == 1
    unused = {**unknown, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    combined = sum_usage({**unknown, 'calls_without_reported_usage': 1}, unused)
    assert combined['input_tokens'] is None and combined['output_tokens'] is None
    assert combined['total_tokens'] is None and combined['calls_without_reported_usage'] == 1
