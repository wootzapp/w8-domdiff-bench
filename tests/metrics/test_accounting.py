"""Provider usage, token coverage and cost accounting."""

import asyncio
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
from google.genai import Client as GoogleClient
from google.genai.errors import ClientError, ServerError
import pytest

from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.task_recorder.recorder_support import write_json, write_json_lines
from w8bench.verifier.common import sum_call_metrics, sum_usage
from w8bench.verifier.compare_results import compare
from w8bench.verifier.paired_metrics import aggregate
from w8bench.verifier.run_full_comparison import main as compare_main
from w8bench.verifier.run_metrics import summarize


@pytest.mark.parametrize('metadata', ['configured', 'prior_settings', 'stage_settings', 'unknown'])
def test_completion_attempt_history_prices_only_the_recorded_model(tmp_path, metadata):
    from w8bench.verifier.run_metrics import _append_attempt_history, _price_call
    prior = {'calls':1,'usage':{'input_tokens':1000,'output_tokens':1000},'transport':'normal',
        'usage_coverage':'complete','status':'ungraded'}
    stage = {'attempt_history':[prior]}
    if metadata == 'configured':
        prior['model_settings'] = {'configured_model':'gemini-3.6-flash','returned_model':None}
    elif metadata == 'prior_settings':
        prior['effective_settings'] = {'models':['gemini-3.6-flash']}
    elif metadata == 'stage_settings':
        stage['effective_settings'] = {'models':['gemini-3.6-flash']}
    streams = {}
    _append_attempt_history(streams, {'paired_completion':stage}, tmp_path/'evaluation.json')
    stream = streams['paired_completion']
    call = stream['history_attempts'][0]['call_records'][0]
    amount = _price_call(call, stream, set(), set())
    if metadata == 'unknown':
        assert call['model'] is None and amount is None
    else:
        assert call['model'] == 'gemini-3.6-flash'
        assert amount == pytest.approx(.0045)


def _verifier_usage_recording(tmp_path):
    import hashlib

    source = tmp_path / "recordings/task"
    source.mkdir(parents=True)
    fingerprint = "a" * 64
    recording = {
        "source": str(source), "recording_sha256": fingerprint,
        "task": {"source_task_id": "task", "observation_mode": "dom",
            "model": "gemini-3.1-pro-preview", "run_name": "trial"},
        "manifest": {"controls": {"max_turns": 200}, "steps": [], "states": [], "run_name": "trial"},
        "decisions": [], "final": {"run_status": "completed"},
    }
    folder = tmp_path / "evaluations/profiles/primary/trial/dom/task" / fingerprint
    metrics = folder / "dom_model/run_metrics.json"
    metrics.parent.mkdir(parents=True)
    calls = [{"configured_model": "gemini-3.1-pro-preview", "returned_model": "gemini-3.1-pro-preview", "usage_reported": True,
        "input_tokens": 10, "output_tokens": 2, "reasoning_tokens": 0,
        "cached_input_tokens": 0, "cache_write_input_tokens": 0}]
    metrics.write_text(json.dumps({"provider_call_metrics": {"judge": {"calls": calls}}}))
    digest = hashlib.sha256(metrics.read_bytes()).hexdigest()
    stage = {
        "status": "complete", "calls": {"gemini-3.1-pro-preview": 1},
        "usage": {"gemini-3.1-pro-preview": {"prompt_tokens": 10, "completion_tokens": 2,
            "total_tokens": 12, "reasoning_tokens": 0, "cached_input_tokens": 0,
            "cache_write_input_tokens": 0}},
        "normalized_metrics_sha256": digest, "artifacts_sha256": {"run_metrics.json": digest},
    }
    evaluation = {"recording_sha256": fingerprint, "task_id": "task", "actor_arm": "dom",
        "trial_id": "trial", "stages": {"dom_model": stage}}
    path = folder / "evaluation.json"
    path.write_text(json.dumps(evaluation))
    return recording, evaluation, path, metrics, calls

INVALID_USAGE = [None, True, False, -1, float("nan"), float("inf"), float("-inf"), "4"]

COMPONENT_PATHS = {
    "input_tokens": ("input_tokens",),
    "output_tokens": ("output_tokens",),
    "reasoning_tokens": ("output_tokens_details", "reasoning_tokens"),
    "cached_input_tokens": ("input_tokens_details", "cached_tokens"),
    "cache_write_input_tokens": ("input_tokens_details", "cache_write_tokens"),
}

@pytest.mark.usefixtures('no_network')
def test_actor_tpt_uses_separate_known_call_denominators_and_preserves_missing_usage(run_pair):
    import copy
    paths, *_ = run_pair
    recording = copy.deepcopy(inspect_recording(paths["dom"]))
    recording["decisions"][0]["usage"] = {"input_tokens": 100, "output_tokens": 40,
        "input_tokens_details": {"cached_tokens": 60}, "output_tokens_details": {"reasoning_tokens": 30}}
    recording["decisions"][1]["usage"] = {"input_tokens": 200}
    recording["decisions"][2]["usage"] = {}
    recording["decisions"][3]["usage"] = {"input_tokens": 300, "output_tokens": 60}
    result = summarize(recording)
    assert result["model_turns"] == 4 and result["rejected_turns"] == 2
    assert result["termination_turns"] == 1
    assert result["token_usage"]["input_tokens"] == 600
    assert result["token_usage"]["output_tokens"] == 100
    assert result["token_usage"]["total_tokens"] == 700
    assert result["token_usage"]["reasoning_tokens"] == 30
    assert result["token_usage"]["cached_input_tokens"] == 60
    assert result["token_usage"]["cache_write_input_tokens"] is None
    assert result["tokens_per_turn"]["input_tokens"]["known_calls"] == 3
    assert result["tokens_per_turn"]["input_tokens"]["known_usage_mean"] == 200
    assert result["tokens_per_turn"]["output_tokens"]["known_calls"] == 2
    assert result["tokens_per_turn"]["output_tokens"]["known_usage_mean"] == 50
    assert result["tokens_per_turn"]["input_tokens"]["mean"] is None
    assert result["turns_missing_usage"] == 2
    assert result["arm_token_usage"]["coverage"] == "partial"
    assert result["arm_token_usage"]["usage"]["total_tokens"] is None
    assert result["arm_token_usage"]["known_usage_lower_bound"]["total_tokens"] == 700

@pytest.mark.usefixtures('no_network')
def test_actor_hard_cap_and_output_limit_rates_include_all_recorded_calls(run_pair):
    import copy
    paths, *_ = run_pair
    recording = copy.deepcopy(inspect_recording(paths["dom"]))
    recording["manifest"]["controls"]["max_turns"] = 200
    recording["final"]["run_status"] = "turn_limit"
    recording["decisions"] = [{"accepted": False, "usage": {"input_tokens": 10, "output_tokens": 5},
        "output_limit_hit": index < 2} for index in range(200)]
    dom = summarize(recording)
    assert dom["step_cap_hit"] is True and dom["model_turns"] == 200
    assert dom["tokens_per_turn"]["input_tokens"]["mean"] == 10
    screenshot = copy.deepcopy(dom)
    screenshot["step_cap_hit"] = False
    pair = {"task_id": "cap_task", "trial_id": "1", "shared_controls": {}, "dom": dom,
        "screenshot": screenshot, "both_successful": False, "successful_pair_turn_delta": None}
    result = aggregate([pair])
    assert result["modes"]["dom"]["hard_cap_200_rate"] == 1
    assert result["modes"]["screenshot"]["hard_cap_200_rate"] == 0
    assert result["modes"]["dom"]["output_limit_hit_rate"] == .01

@pytest.mark.usefixtures('no_network')
def test_no_reported_actor_usage_remains_unknown_in_totals_and_tpt(run_pair):
    import copy
    paths, *_ = run_pair
    pair, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    for mode in ("dom", "screenshot"):
        recording = copy.deepcopy(inspect_recording(paths[mode]))
        for row in recording["decisions"]:
            row["usage"] = None
        pair[mode] = summarize(recording)
        assert pair[mode]["token_usage"]["input_tokens"] is None
        assert pair[mode]["tokens_per_turn"]["input_tokens"]["known_calls"] == 0
    result = aggregate([pair])
    assert result["modes"]["dom"]["token_usage"]["input_tokens"] is None
    assert result["modes"]["dom"]["tokens_per_turn"]["input_tokens"]["known_usage_mean"] is None
    assert result["modes"]["dom"]["mean_tokens_all_attempts"] is None
    assert result["modes"]["dom"]["distributions"]["input_tokens"]["known_runs"] == 0

@pytest.mark.usefixtures('no_network')
def test_resumed_judge_attempt_costs_keep_known_history_and_unknown_coverage(run_pair):
    paths, *_ = run_pair
    recording = inspect_recording(paths["dom"])
    task = recording["task"]
    root = paths["dom"].parent.parent / "evaluations" / "profiles" / "primary" / str(task["run_name"]) / "dom" / task["source_task_id"] / recording["recording_sha256"]
    root.mkdir(parents=True)
    grade = {"recording_sha256": recording["recording_sha256"], "task_id": task["source_task_id"],
        "observation_mode": "dom", "rubric_sha256": "frozen", "evidence_policy": "paired",
        "method": "model_judge", "verdict": "success", "judge_model": "gemini-3.6-flash", "judge_calls": 1,
        "returned_judge_model": "gemini-3.6-flash-2026-10-01",
        "usage": {"input_tokens": 30, "output_tokens": 10}}
    write_json(root / "paired_completion.json", grade)
    evaluation = {"recording_sha256": recording["recording_sha256"], "task_id": task["source_task_id"],
        "actor_arm": "dom", "trial_id": str(task["run_name"]), "rubric_sha256": "frozen", "stages": {
        "paired_completion": {"status": "model_judge", "result": str(root / "paired_completion.json"), "attempt_history": [
            {"status": "ungraded", "calls": 1, "usage": {"input_tokens": 20, "output_tokens": 5}, "usage_coverage": "complete",
                "model_settings": {"returned_model": "gemini-3.6-flash-2026-10-01"}},
            {"status": "interrupted", "usage_coverage": "unknown"}]},
        "dom_model": {"status": "complete", "usage_coverage": "complete", "calls": {"gemini-3.5-flash-lite": 2},
            "usage": {"gemini-3.5-flash-lite": {"input_tokens": 60, "output_tokens": 15}}, "attempt_history": [
            {"status": "failed", "calls": {"gemini-3.5-flash-lite": 1}, "usage": {"gemini-3.5-flash-lite": {"input_tokens": 10, "output_tokens": 2}}, "usage_coverage": "complete"}]}}}
    write_json(root / "evaluation.json", evaluation)
    result = summarize(recording)
    stream = result["judge_usage_streams"]["paired_completion"]
    assert stream["usage"]["input_tokens"] == 50 and stream["usage"]["output_tokens"] == 15
    assert stream["usage"]["total_tokens"] == 65
    assert stream["calls"] is None and stream["known_calls"] == 2
    assert stream["unknown_attempts"] == 1 and stream["usage_coverage"] == "partial"
    assert {row["returned_model"] for row in stream["call_records"]} == {"gemini-3.6-flash-2026-10-01"}
    auxiliary = result["judge_usage_streams"]["dom_model:gemini-3.5-flash-lite"]
    assert auxiliary["usage"]["input_tokens"] == 70 and auxiliary["usage"]["output_tokens"] == 17
    assert auxiliary["calls"] == 3 and auxiliary["usage_coverage"] == "complete"
    assert result["judge_usage"]["input_tokens"] == 50
    assert summarize(recording)["judge_usage_streams"] == result["judge_usage_streams"]

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize('large_context', [False, True])
def test_actor_list_price_estimate_uses_per_call_rates_and_subsets(run_pair, large_context):
    from w8bench.verifier.run_metrics import summarize
    paths, *_ = run_pair
    recording = inspect_recording(paths['dom'])
    for row in recording['decisions']:
        row['usage'] = {'input_tokens': 300000 if large_context else 100, 'output_tokens': 20,
            'input_tokens_details': {'cached_tokens': 40, 'cache_write_tokens': 20},
            'output_tokens_details': {'reasoning_tokens': 10}}
    priced = summarize(recording)['cost_streams']['actor']['cost']
    per_call = (((300000 if large_context else 100) - 60) * .75 + 40 * .075 + 20 * .75 + 20 * 3.75) / 1000000
    assert priced['estimated_usd'] == pytest.approx(per_call * len(recording['decisions']))
    assert priced['priced_calls'] == len(recording['decisions'])
    assert priced['kind'] == 'estimated_from_list_prices'

@pytest.mark.usefixtures('no_network')
def test_actor_cost_missing_usage_is_not_a_zero_price(run_pair):
    from w8bench.verifier.run_metrics import summarize
    paths, *_ = run_pair
    recording = inspect_recording(paths['dom'])
    recording['decisions'][0]['usage'] = {}
    priced = summarize(recording)['cost_streams']['actor']['cost']
    assert priced['estimated_usd'] is None
    assert priced['known_usage_estimate_usd'] > 0
    assert priced['unpriced_calls'] == 1
    assert priced['coverage'] == 'partial'

@pytest.mark.usefixtures('inline_sdk_header_initialization')
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

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_wire_attempts_and_provider_usage_without_changing_requests(monkeypatch, package):
    wrapper = importlib.import_module(f"w8bench.verifier.clients.providers")
    requests = []
    async def respond(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(500, json={"error": {"code": 500, "message": "temporary", "status": "INTERNAL"}})
        return httpx.Response(200, json={"modelVersion": "gemini-3.5-flash-lite-001",
            "candidates": [{"finishReason": "MAX_TOKENS", "content": {"role": "model", "parts": [{"text": "{}"}]}}],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 4, "thoughtsTokenCount": 6,
                "totalTokenCount": 30, "cachedContentTokenCount": 8}})
    def sdk(**kwargs):
        options = kwargs["http_options"]
        transport = options.httpx_async_client
        transport._transport = httpx.MockTransport(respond)
        transport._mounts = {}
        return GoogleClient(**kwargs)
    monkeypatch.setattr(wrapper.genai, "Client", sdk)
    client = wrapper.GeminiClientWrapper(package, api_key="offline-test", model="gemini-3.5-flash-lite")
    async def exercise():
        try:
            with pytest.raises(ServerError):
                await client.create([{"role": "user", "content": "unchanged"}], json_output=True)
            await client.create([{"role": "user", "content": "unchanged"}], json_output=True)
        finally:
            await client.close()
    asyncio.run(exercise())
    assert len(requests) == 2 and requests[0] == requests[1]
    assert requests[0]["contents"] == [{"role": "user", "parts": [{"text": "unchanged"}]}]
    assert requests[0]["generationConfig"] == {"responseMimeType": "application/json", "mediaResolution": "MEDIA_RESOLUTION_HIGH"}
    failed, record = client._call_records
    assert failed["usage_reported"] is False and failed["error_type"] == "ServerError"
    assert record["configured_model"] == record["requested_model"] == "gemini-3.5-flash-lite"
    assert record["returned_model"] == "gemini-3.5-flash-lite-001"
    assert record["reasoning_effort"] is None and record["temperature"] is None and record["max_output_tokens"] is None
    assert record["http_attempts"] == failed["http_attempts"] == 1 and record["http_attempts_observed"] is True
    assert record["input_tokens"] == 20 and record["output_tokens"] == 10
    assert record["cached_input_tokens"] == 8 and record["reasoning_tokens"] == 6
    assert record["total_tokens"] == 30 and record["cache_write_input_tokens"] is None
    assert record["output_limit_hit"] is True and record["finish_reason"] == "MAX_TOKENS"
    assert client.total_usage().prompt_tokens == 20 and client.total_usage().completion_tokens == 10

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_failed_provider_call_retains_wire_attempt_and_unknown_usage(monkeypatch, package):
    wrapper = importlib.import_module(f"w8bench.verifier.clients.providers")
    async def respond(request):
        return httpx.Response(400, json={"error": {"code": 400, "message": "invalid request", "status": "INVALID_ARGUMENT"}})
    monkeypatch.setattr(wrapper.genai, "Client", lambda **kwargs: (
        setattr(kwargs["http_options"].httpx_async_client, "_transport", httpx.MockTransport(respond)),
        setattr(kwargs["http_options"].httpx_async_client, "_mounts", {}), GoogleClient(**kwargs))[-1])
    client = wrapper.GeminiClientWrapper(package, api_key="offline-test", model="gemini-3.5-flash-lite")
    async def exercise():
        try:
            with pytest.raises(ClientError):
                await client.create([{"role": "user", "content": "test"}])
        finally:
            await client.close()
    asyncio.run(exercise())
    record, = client._call_records
    assert record["http_attempts"] == 1
    assert record["usage_reported"] is False and record["returned_model"] is None
    assert record["error_type"] == "ClientError"

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_missing_subsets_stay_unknown_and_stage_survives_timeout_task(monkeypatch, package):
    wrapper = importlib.import_module(f"w8bench.verifier.clients.providers")
    graceful = importlib.import_module(f"w8bench.verifier.clients.retry")
    accounting = importlib.import_module(f"w8bench.verifier.{package}.runner")
    async def respond(request):
        return httpx.Response(200, json={"modelVersion": "gemini-3.5-flash-lite",
            "candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [{"text": "{}"}]}}],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 10, "thoughtsTokenCount": 0, "totalTokenCount": 37}})
    monkeypatch.setattr(wrapper.genai, "Client", lambda **kwargs: (
        setattr(kwargs["http_options"].httpx_async_client, "_transport", httpx.MockTransport(respond)),
        setattr(kwargs["http_options"].httpx_async_client, "_mounts", {}), GoogleClient(**kwargs))[-1])
    endpoint = wrapper.GeminiClientWrapper(package, api_key="offline-test", model="gemini-3.5-flash-lite")
    monkeypatch.setattr(endpoint, "count_tokens", lambda **kwargs: 0)
    client = graceful.GracefulRetryClient([endpoint], timeout=1, evidence_mode=package)
    accounting.instrument_client_calls(client)
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
    assert record["reasoning_tokens"] == 0 and record["cached_input_tokens"] is None
    assert record["cache_write_input_tokens"] is None
    assert endpoint.total_usage().reasoning_tokens == 0
    usage = accounting.usage_dict(client)
    assert usage["reasoning_tokens"] == 0 and usage["cached_input_tokens"] is None
    assert usage["total_tokens"] == 37
    assert usage["unattributed_tokens"] == 7 and usage["token_components_reconcile"] is False
    assert usage["usage_known_calls"]["input_tokens"] == usage["usage_known_calls"]["output_tokens"] == 1
    assert usage["usage_known_calls"]["reasoning_tokens"] == 1
    assert usage["usage_known_calls"]["cached_input_tokens"] == 0

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("reported_zero", [False, True])
def test_unreported_provider_usage_is_distinct_from_reported_zero(monkeypatch, package, reported_zero):
    wrapper = importlib.import_module(f"w8bench.verifier.clients.providers")
    accounting = importlib.import_module(f"w8bench.verifier.{package}.runner")
    async def respond(request):
        payload = {"modelVersion": "gemini-3.5-flash-lite",
            "candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [{"text": "{}"}]}}]}
        if reported_zero:
            payload["usageMetadata"] = {"promptTokenCount": 0, "candidatesTokenCount": 0, "thoughtsTokenCount": 0, "totalTokenCount": 0}
        return httpx.Response(200, json=payload)
    monkeypatch.setattr(wrapper.genai, "Client", lambda **kwargs: (
        setattr(kwargs["http_options"].httpx_async_client, "_transport", httpx.MockTransport(respond)),
        setattr(kwargs["http_options"].httpx_async_client, "_mounts", {}), GoogleClient(**kwargs))[-1])
    endpoint = wrapper.GeminiClientWrapper(package, api_key="offline-test", model="gemini-3.5-flash-lite")
    async def exercise():
        try:
            await endpoint.create([{"role": "user", "content": "offline"}])
        finally:
            await endpoint.close()
    asyncio.run(exercise())
    usage = accounting.usage_dict(SimpleNamespace(_clients=[endpoint]))
    expected = 0 if reported_zero else None
    assert usage["prompt_tokens"] == usage["input_tokens"] == expected
    assert usage["completion_tokens"] == usage["output_tokens"] == expected
    assert usage["total_tokens"] == expected
    assert usage["usage_known_calls"]["input_tokens"] == usage["usage_known_calls"]["output_tokens"] == int(reported_zero)
    assert usage["calls_without_reported_usage"] == int(not reported_zero)
    assert endpoint._call_records[0].get("input_tokens") == expected
    assert endpoint._call_records[0].get("output_tokens") == expected
    assert endpoint.total_usage().prompt_tokens == endpoint.total_usage().completion_tokens == 0

@pytest.mark.usefixtures('inline_sdk_header_initialization')
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

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("effort", ["medium", "low"])
def test_chat_provider_payload_response_retry_usage_and_close(monkeypatch, package, effort):
    wrapper = importlib.import_module("w8bench.verifier.clients.providers")
    requests, transports = [], []
    async def respond(request):
        requests.append((str(request.url), json.loads(request.content)))
        if len(requests) == 1:
            return httpx.Response(500, json={"error": {"code": 500, "message": "temporary", "status": "INTERNAL"}})
        return httpx.Response(200, json={"modelVersion": "gemini-3.5-flash-lite-001",
            "candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [
                {"text": "done"}, {"functionCall": {"name": "inspect", "args": {}}}]}}],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 4, "thoughtsTokenCount": 6,
                "totalTokenCount": 30, "cachedContentTokenCount": 8}})
    def sdk(**kwargs):
        options = kwargs["http_options"]
        transport = options.httpx_async_client
        transport._transport = httpx.MockTransport(respond)
        transport._mounts = {}
        transports.append(transport)
        return GoogleClient(**kwargs)
    monkeypatch.setattr(wrapper.genai, "Client", sdk)
    client = wrapper.GeminiClientWrapper(package, api_key="offline-test", model="gemini-3.5-flash-lite")
    tools = [{"type": "function", "function": {"name": "inspect", "parameters": {"type": "object"}}}]
    extra = {"temperature": 0.25, "reasoning_effort": effort, "max_output_tokens": 10000, "top_k": 4}
    async def exercise():
        try:
            with pytest.raises(ServerError):
                await client.create([{"role": "user", "content": "Inspect the page."}], tools=tools,
                    json_output=True, extra_create_args=extra)
            return await client.create([{"role": "user", "content": "Inspect the page."}], tools=tools,
                json_output=True, extra_create_args=extra)
        finally:
            await client.close()
    result = asyncio.run(exercise())
    assert len(requests) == 2 and requests[0] == requests[1]
    payload = requests[0][1]
    assert payload["contents"] == [{"role": "user", "parts": [{"text": "Inspect the page."}]}]
    assert payload["generationConfig"] == {"mediaResolution": "MEDIA_RESOLUTION_HIGH", "responseMimeType": "application/json",
        "temperature": .25, "thinkingConfig": {"thinkingLevel": effort.upper()}, "maxOutputTokens": 10000, "topK": 4}
    assert payload["tools"] == [{"functionDeclarations": [{"name": "inspect", "parameters": {"type": "OBJECT"}}]}]
    assert requests[0][0] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
    assert extra == {"temperature": 0.25, "reasoning_effort": effort, "max_output_tokens": 10000, "top_k": 4}
    assert result.content == "done" and result.finish_reason == "STOP"
    assert result.tool_calls[0]["name"] == "inspect" and result.tool_calls[0]["args"] == {}
    assert (result.usage.prompt_tokens, result.usage.completion_tokens, result.usage.reasoning_tokens) == (20, 10, 6)
    failed, record = client._call_records
    assert failed["error_type"] == "ServerError" and failed["usage_reported"] is False
    assert record["configured_model"] == record["requested_model"] == "gemini-3.5-flash-lite"
    assert record["returned_model"] == "gemini-3.5-flash-lite-001"
    assert record["http_attempts"] == 1 and record["http_attempts_observed"] is True
    assert record["input_tokens"] == 20 and record["output_tokens"] == 10 and record["total_tokens"] == 30
    assert record["cached_input_tokens"] == 8 and record["reasoning_tokens"] == 6
    assert record["reasoning_effort"] == effort.upper() and record["temperature"] == 0.25
    assert record["max_output_tokens"] == 10000 and record["output_limit_hit"] is False
    assert record["finish_reason"] == "STOP" and record["error_type"] is None
    total = client.total_usage()
    assert (total.prompt_tokens, total.completion_tokens, total.reasoning_tokens) == (20, 10, 6)
    assert all(transport.is_closed for transport in transports)

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_native_error_propagates_with_unknown_usage_and_closed_transport(monkeypatch, package):
    wrapper = importlib.import_module("w8bench.verifier.clients.providers")
    requests, transports = [], []
    async def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(400, json={"error": {"code": 400, "message": "invalid request", "status": "INVALID_ARGUMENT"}})
    def sdk(**kwargs):
        options = kwargs["http_options"]
        transport = options.httpx_async_client
        transport._transport = httpx.MockTransport(respond)
        transport._mounts = {}
        transports.append(transport)
        return GoogleClient(**kwargs)
    monkeypatch.setattr(wrapper.genai, "Client", sdk)
    client = wrapper.GeminiClientWrapper(package, api_key="offline-test", model="gemini-3.5-flash-lite")
    async def exercise():
        try:
            with pytest.raises(ClientError, match="invalid request"):
                await client.create([{"role": "user", "content": "Inspect."}])
        finally:
            await client.close()
    asyncio.run(exercise())
    assert requests == [{"contents": [{"role": "user", "parts": [{"text": "Inspect."}]}],
        "generationConfig": {"mediaResolution": "MEDIA_RESOLUTION_HIGH"}}]
    record, = client._call_records
    assert record["error_type"] == "ClientError" and record["http_attempts"] == 1
    assert record["usage_reported"] is False and record["returned_model"] is None
    assert "input_tokens" not in record and "output_tokens" not in record
    assert all(transport.is_closed for transport in transports)

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("config_name", ["google_gemini3_5_flash_lite.json", "google_gemini3_1_pro_preview.json"])
def test_pinned_client_config_metadata_preserves_sdk_defaults_and_wire_payload(monkeypatch, package, config_name):
    wrapper = importlib.import_module("w8bench.verifier.clients.providers")
    factory = importlib.import_module("w8bench.verifier.clients.factory")
    common = importlib.import_module("w8bench.verifier.common")
    configuration = json.loads((Path(common.__file__).resolve().parents[2] / "config" / config_name).read_text())
    configuration["CHAT_COMPLETION_KWARGS_JSON"]["api_key"] = "offline-test"
    configuration["CHAT_COMPLETION_KWARGS_JSON"].update(model_capabilities={"function_calling": True, "json_output": True, "vision": True}, max_retries=5)
    minimal = json.loads(json.dumps(configuration))
    minimal["CHAT_COMPLETION_KWARGS_JSON"].pop("model_capabilities")
    minimal["CHAT_COMPLETION_KWARGS_JSON"].pop("max_retries")
    sdk_options, requests = [], []
    async def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"modelVersion": configuration["CHAT_COMPLETION_KWARGS_JSON"]["model"],
            "candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [{"text": "done"}]}}]})
    def sdk(**kwargs):
        sdk_options.append(dict(kwargs))
        options = kwargs["http_options"]
        transport = options.httpx_async_client
        transport._transport = httpx.MockTransport(respond)
        transport._mounts = {}
        return GoogleClient(**kwargs)
    monkeypatch.setattr(wrapper.genai, "Client", sdk)
    async def exercise():
        results = []
        for value in (configuration, minimal):
            client = factory.create_client_from_config(value, evidence_mode=package)
            try:
                assert client._http_options["retry_options"].attempts == 1
                result = await client.create([{"role": "user", "content": "Inspect."}], json_output=True)
                results.append((result.content, result.finish_reason, client.metadata, client._call_records))
            finally:
                await client.close()
        return results
    first, second = asyncio.run(exercise())
    assert first == second
    assert [value["api_key"] for value in sdk_options] == ["offline-test", "offline-test"]
    assert all(value["http_options"].retry_options.attempts == 1 for value in sdk_options)
    assert requests[0] == requests[1]
    assert requests[0]["contents"] == [{"role": "user", "parts": [{"text": "Inspect."}]}]
    assert requests[0]["generationConfig"] == {"mediaResolution": "MEDIA_RESOLUTION_HIGH", "responseMimeType": "application/json",
        "thinkingConfig": {"thinkingLevel": "MEDIUM"}}
    assert first[2]["provider"] == "google" and first[3][0]["reasoning_effort"] == "MEDIUM"

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("model", ["gemini-3.1-pro-preview", "gemini-3.5-flash-lite"])
def test_google_judge_wire_routing_settings_and_usage(monkeypatch, package, model):
    wrapper = importlib.import_module("w8bench.verifier.clients.providers")
    factory = importlib.import_module("w8bench.verifier.clients.factory")
    graceful = importlib.import_module("w8bench.verifier.clients.retry")
    monkeypatch.setenv("GEMINI_API_KEY", "offline-google-key")
    requests = []
    async def respond(request):
        requests.append((str(request.url), request.headers["x-goog-api-key"], json.loads(request.content)))
        return httpx.Response(200, json={"modelVersion": f"{model}-001",
            "candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [{"text": "{}"}]}}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 10, "thoughtsTokenCount": 20,
                "totalTokenCount": 130, "cachedContentTokenCount": 40}})
    monkeypatch.setattr(wrapper.genai, "Client", lambda **kwargs: (
        setattr(kwargs["http_options"].httpx_async_client, "_transport", httpx.MockTransport(respond)),
        setattr(kwargs["http_options"].httpx_async_client, "_mounts", {}), GoogleClient(**kwargs))[-1])
    endpoint = factory.create_client_from_config({"CHAT_COMPLETION_PROVIDER": "google",
        "CHAT_COMPLETION_KWARGS_JSON": {"model": model, "reasoning_effort": "medium"}}, evidence_mode=package)
    monkeypatch.setattr(endpoint, "count_tokens", lambda **kwargs: 0)
    client = graceful.GracefulRetryClient([endpoint], evidence_mode=package)
    messages = [{"role": "user", "content": [{"type": "text", "text": "Check the recorded state."},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,b2ZmbGluZQ==", "detail": "high"}}]}]
    async def exercise():
        try:
            return await client.create(messages, json_output=True, extra_create_args={"reasoning_effort": "medium"})
        finally:
            await client.close()
    result = asyncio.run(exercise())
    assert len(requests) == 1 and requests[0][0] == f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    assert requests[0][1] == "offline-google-key"
    assert requests[0][2]["generationConfig"] == {"mediaResolution": "MEDIA_RESOLUTION_HIGH", "responseMimeType": "application/json",
        "thinkingConfig": {"thinkingLevel": "MEDIUM"}}
    parts = requests[0][2]["contents"][0]["parts"]
    assert parts[0] == {"text": "Check the recorded state."}
    assert len(parts) == (2 if package == "screenshot_verifier" else 1)
    record, = endpoint._call_records
    assert record["provider"] == "google" and record["configured_model"] == model
    assert record["returned_model"] == f"{model}-001"
    assert record["reasoning_effort"] == "MEDIUM" and record["max_output_tokens"] is None
    assert record["input_tokens"] == 100 and record["cached_input_tokens"] == 40
    assert record["output_tokens"] == 30 and record["reasoning_tokens"] == 20
    assert record["total_tokens"] == 130 and record["http_attempts"] == 1
    assert result.usage.prompt_tokens == 100 and result.usage.completion_tokens == 30

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("package", ["dom_model", "screenshot_verifier"])
def test_google_judge_requires_its_credential(monkeypatch, package):
    factory = importlib.import_module("w8bench.verifier.clients.factory")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        factory.create_client_from_config({"CHAT_COMPLETION_PROVIDER": "google",
            "CHAT_COMPLETION_KWARGS_JSON": {"model": "gemini-3.1-pro-preview"}}, evidence_mode=package)

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("artifact_digest", ["matching", "different", "absent"])
def test_verifier_usage_prefers_an_explicit_metrics_checksum(tmp_path, artifact_digest):
    from w8bench.verifier.run_metrics import summarize

    recording, evaluation, path, _, calls = _verifier_usage_recording(tmp_path)
    stage = evaluation["stages"]["dom_model"]
    if artifact_digest == "different":
        stage["artifacts_sha256"]["run_metrics.json"] = "f" * 64
    elif artifact_digest == "absent":
        stage.pop("artifacts_sha256")
    path.write_text(json.dumps(evaluation))
    summary = summarize(recording)
    stream = summary["judge_usage_streams"]["dom_model:gemini-3.1-pro-preview"]
    assert stream["call_records"] == calls
    assert stream["usage_coverage"] == "complete"
    assert stream["cost"]["priced_calls"] == 1
    assert stream["cost"]["estimated_usd"] == pytest.approx(0.000044)

@pytest.mark.usefixtures('inline_sdk_header_initialization')
def test_verifier_usage_rejects_changed_metrics_bytes(tmp_path):
    from w8bench.verifier.run_metrics import summarize

    recording, _, _, metrics, _ = _verifier_usage_recording(tmp_path)
    metrics.write_text(metrics.read_text() + "\n")
    with pytest.raises(ValueError, match="^normalized verifier accounting artifact changed$"):
        summarize(recording)

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("digest", [None, ""])
def test_verifier_usage_preserves_an_explicit_empty_metrics_checksum(tmp_path, digest):
    from w8bench.verifier.run_metrics import summarize

    recording, evaluation, path, metrics, _ = _verifier_usage_recording(tmp_path)
    evaluation["stages"]["dom_model"]["normalized_metrics_sha256"] = digest
    path.write_text(json.dumps(evaluation))
    metrics.write_text("not JSON")
    stream = summarize(recording)["judge_usage_streams"]["dom_model:gemini-3.1-pro-preview"]
    assert stream["call_records"] == []
    assert stream["cost"]["priced_calls"] == 0
    assert stream["cost"]["estimated_usd"] is None

@pytest.mark.usefixtures('inline_sdk_header_initialization')
def test_verifier_usage_reads_a_stage_artifact_checksum(tmp_path):
    from w8bench.verifier.run_metrics import summarize

    recording, evaluation, path, _, _ = _verifier_usage_recording(tmp_path)
    expected = summarize(recording)
    evaluation["stages"]["dom_model"].pop("normalized_metrics_sha256")
    path.write_text(json.dumps(evaluation))
    expected["evaluation"]["stages"]["dom_model"].pop("normalized_metrics_sha256")
    assert summarize(recording) == expected

@pytest.mark.usefixtures('inline_sdk_header_initialization')
def test_verifier_usage_rejects_changed_artifact_metrics_bytes(tmp_path):
    from w8bench.verifier.run_metrics import summarize

    recording, evaluation, path, metrics, _ = _verifier_usage_recording(tmp_path)
    evaluation["stages"]["dom_model"].pop("normalized_metrics_sha256")
    path.write_text(json.dumps(evaluation))
    metrics.write_text(metrics.read_text() + "\n")
    with pytest.raises(ValueError, match="^normalized verifier accounting artifact changed$"):
        summarize(recording)

@pytest.mark.usefixtures('inline_sdk_header_initialization')
@pytest.mark.parametrize("digest", ["matching", None])
@pytest.mark.parametrize("artifact_map", ["not a map", ["not a map"], 17])
def test_explicit_metrics_checksum_does_not_consult_artifact_shape(tmp_path, digest, artifact_map):
    from w8bench.verifier.run_metrics import summarize

    recording, evaluation, path, metrics, calls = _verifier_usage_recording(tmp_path)
    stage = evaluation["stages"]["dom_model"]
    stage["artifacts_sha256"] = artifact_map
    if digest is None:
        stage["normalized_metrics_sha256"] = None
        metrics.write_text("not JSON")
    path.write_text(json.dumps(evaluation))
    stream = summarize(recording)["judge_usage_streams"]["dom_model:gemini-3.1-pro-preview"]
    assert stream["call_records"] == (calls if digest == "matching" else [])
    assert stream["cost"]["priced_calls"] == (1 if digest == "matching" else 0)

@pytest.mark.parametrize("native", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("actor_usage", [None, {"input_tokens": 10, "output_tokens": 5}])
@pytest.mark.parametrize("history_coverage", ["complete", "unknown"])
def test_resumed_native_history_preserves_actor_model_and_usage_coverage(
    metric_recording_factory, metric_evaluation_factory, native, actor_usage, history_coverage
):
    recording = metric_recording_factory(usage=actor_usage)
    baseline = summarize(recording)
    metric_evaluation_factory(recording, stages={native: {
        "status": "failed", "attempt_history": [{
            "status": "failed", "usage_coverage": history_coverage,
            "calls": {"gemini-3.8-flash": 1},
            "usage": {"gemini-3.8-flash": {"input_tokens": 2, "output_tokens": 1}},
        }],
    }})
    result = summarize(recording)
    for key in ("returned_actor_models", "turns_missing_usage", "cost_coverage", "token_usage"):
        assert result[key] == baseline[key]
    assert result["returned_actor_models"] == ["gemini-3.8-flash"]
    history = result["judge_usage_streams"][f"{native}:gemini-3.8-flash"]
    assert history["known_calls"] == 1
    assert history["usage"]["total_tokens"] == 3

@pytest.mark.parametrize("component", list(COMPONENT_PATHS))
@pytest.mark.parametrize("invalid", INVALID_USAGE, ids=["unknown", "true", "false", "negative", "nan", "infinity", "negative_infinity", "text"])
def test_actor_token_components_require_finite_nonnegative_nonboolean_numbers(
    metric_recording_factory, component, invalid
):
    usage = {"input_tokens": 100, "output_tokens": 50,
             "input_tokens_details": {"cached_tokens": 10, "cache_write_tokens": 8},
             "output_tokens_details": {"reasoning_tokens": 5}}
    path = COMPONENT_PATHS[component]
    target = usage
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid
    result = summarize(metric_recording_factory(usage=usage))
    assert result["token_usage"][component] is None
    assert result["token_usage_known_calls"][component] == 0
    if component in {"input_tokens", "output_tokens"}:
        assert result["turns_missing_usage"] == 1
        assert result["cost_coverage"] == "partial"
        assert result["tokens_per_turn"][component]["mean"] is None
        assert result["cost_streams"]["actor"]["cost"]["estimated_usd"] is None

@pytest.mark.parametrize("invalid", [True, False, -1, float("nan"), float("inf"), float("-inf"), "4"])
@pytest.mark.parametrize("field", ["input_tokens", "output_tokens", "cached_tokens", "cache_write_tokens", "ttl_12h_tokens"])
def test_invalid_pricing_components_never_produce_an_exact_cost(metric_recording_factory, field, invalid):
    usage = {"input_tokens": 100, "output_tokens": 50,
             "input_tokens_details": {"cached_tokens": 10, "cache_write_tokens": 8,
                                      "cache_write_tokens_details": {"ttl_12h_tokens": 2}}}
    if field in {"input_tokens", "output_tokens"}:
        usage[field] = invalid
    elif field == "ttl_12h_tokens":
        usage["input_tokens_details"]["cache_write_tokens_details"][field] = invalid
    else:
        usage["input_tokens_details"][field] = invalid
    result = summarize(metric_recording_factory(usage=usage))
    assert result["cost_streams"]["actor"]["cost"]["estimated_usd"] is None

@pytest.mark.parametrize("component", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("invalid", INVALID_USAGE, ids=["unknown", "true", "false", "negative", "nan", "infinity", "negative_infinity", "text"])
def test_completion_usage_requires_valid_principal_counts(
    metric_recording_factory, metric_evaluation_factory, component, invalid
):
    recording = metric_recording_factory(usage={"input_tokens": 1, "output_tokens": 1})
    usage = {"input_tokens": 10, "output_tokens": 5}
    usage[component] = invalid
    metric_evaluation_factory(recording, grade_usage=usage)
    result = summarize(recording)
    stream = result["judge_usage_streams"]["paired_completion"]
    assert stream["usage"][component] is None
    assert stream["usage_coverage"] != "complete"
    assert result["judge_usage"][component] is None
    assert result["judge_calls_missing_usage"] == 1
    assert stream["cost"]["estimated_usd"] is None

@pytest.mark.parametrize("outcome", ["startup_failure", "not_started", "interrupted", "incomplete_recording"])
@pytest.mark.parametrize("attempt_evidence", [False, "request", "response", "result", "counter", "malformed_counter", "malformed_decisions", "steps"])
def test_scheduled_actor_cost_is_zero_only_when_no_calls_are_known(
    tmp_path, outcome, attempt_evidence
):
    rows = []
    for arm in ("dom", "screenshot"):
        recording = tmp_path / arm / "custom"
        if attempt_evidence:
            if attempt_evidence in {"request", "response", "result"}:
                write_json(recording / "turns" / "turn_000001" / f"{attempt_evidence}.json", {"model": "gemini-3.1-pro-preview"})
            elif attempt_evidence in {"counter", "malformed_counter"}:
                write_json(recording / "manifest.json", {"model_turns": 1 if attempt_evidence == "counter" else "1"})
            elif attempt_evidence == "malformed_decisions":
                recording.mkdir(parents=True)
                (recording / "decisions.jsonl").write_text('{"model_turn":1,')
            else:
                write_json(recording / "manifest.json", {"steps": [{"action_succeeded": True, "action": {"action": "wait"}}]})
        rows.append({"task_id": "custom", "trial": 1, "trials": 1, "arm": arm,
                     "run_name": "trial_0001", "recording": str(recording),
                     "technical_outcome": outcome, "configuration": {"model": "gemini-3.1-pro-preview"},
                     "task": {"instruction": "Read title.", "start_url": "https://example.test"}})
    ledger = tmp_path / "ledger.jsonl"
    write_json_lines(ledger, rows)
    assert compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")]) == 0
    pairs = json.loads((tmp_path / "report" / "pairs.json").read_text())
    expected_zero = outcome in {"startup_failure", "not_started"} and not attempt_evidence
    for arm in ("dom", "screenshot"):
        summary = pairs[0][arm]
        cost = summary["cost_streams"]["actor"]["cost"]
        assert summary["cost_coverage"] == ("complete" if expected_zero else "partial")
        assert summary["turns_complete"] is expected_zero
        assert cost["coverage"] == ("complete" if expected_zero else "unknown")
        assert cost["estimated_usd"] == (0 if expected_zero else None)
        assert summary["token_usage"]["total_tokens"] == (0 if expected_zero else None)

def test_attempted_unknown_usage_never_becomes_zero_cost(metric_recording_factory):
    result = summarize(metric_recording_factory(usage={}))
    assert result["model_turns"] == 1
    assert result["token_usage"]["total_tokens"] is None
    assert result["cost_streams"]["actor"]["cost"]["estimated_usd"] is None

@pytest.mark.parametrize("stage_name", ["dom_model", "screenshot_verifier"])
@pytest.mark.parametrize("invalid", INVALID_USAGE, ids=["unknown", "true", "false", "negative", "nan", "infinity", "negative_infinity", "text"])
def test_native_usage_declarations_cannot_make_invalid_counts_complete(
    metric_recording_factory, metric_evaluation_factory, stage_name, invalid
):
    recording = metric_recording_factory(usage={"input_tokens": 1, "output_tokens": 1})
    metric_evaluation_factory(recording, stages={stage_name: {
        "status": "complete", "usage_coverage": "complete",
        "calls": {"gemini-3.1-pro-preview": 1},
        "usage": {"gemini-3.1-pro-preview": {"input_tokens": invalid, "output_tokens": 2}},
    }})
    stream = summarize(recording)["judge_usage_streams"][f"{stage_name}:gemini-3.1-pro-preview"]
    assert stream["usage"]["input_tokens"] is None
    assert stream["usage_coverage"] != "complete"

@pytest.mark.parametrize("model,input_tokens,expected", [
    ("gemini-3.8-flash", 1000000, 0.75 + 3.75),
    ("gemini-3.1-pro-preview", 100000, 0.2 + 12),
    ("gemini-3.1-pro-preview", 200001, 0.800004 + 18),
])
def test_actor_and_native_judge_standard_prices_match_requested_models(model, input_tokens, expected):
    from w8bench.verifier.run_metrics import _price_call
    assumptions, sources = set(), set()
    value = _price_call({"configured_model": model, "returned_model": model,
        "usage": {"input_tokens": input_tokens, "output_tokens": 1000000,
            "cached_input_tokens": 0, "cache_write_input_tokens": 0}}, {}, assumptions, sources)
    assert value == pytest.approx(expected)
    assert "https://aistudio.google.com/docs/pricing" in sources

@pytest.mark.parametrize("returned", ["gemini-3.8-flash", "gemini-3.8-flash-001", "gemini-3.8-flash-v2", "gemini-3.8-flash-2026-11-18"])
def test_accepted_actor_model_versions_use_the_canonical_tariff(returned):
    from w8bench.verifier.run_metrics import _price_call
    value = _price_call({"configured_model": "gemini-3.8-flash", "returned_model": returned,
        "usage": {"input_tokens": 100, "output_tokens": 20}}, {}, set(), set())
    assert value == pytest.approx((100 * .75 + 20 * 3.75) / 1000000)


def test_unrecognized_returned_model_is_not_priced_as_the_configured_actor():
    from w8bench.verifier.run_metrics import _price_call
    assert _price_call({"configured_model": "gemini-3.8-flash", "returned_model": "gemini-3.8-flash-mini",
        "usage": {"input_tokens": 100, "output_tokens": 20}}, {}, set(), set()) is None


@pytest.mark.usefixtures('no_network')
def test_stall_advisory_counts_remain_private_and_aggregate_per_arm(run_pair):
    paths, *_ = run_pair
    pair, _ = compare(*(inspect_recording(paths[mode]) for mode in ('dom', 'screenshot')))
    for mode, count in [('dom', 2), ('screenshot', 1)]:
        recording = inspect_recording(paths[mode])
        for index, decision in enumerate(recording['decisions']):
            decision['stall_advisory'] = 'recent duplicate' if index < count else None
        pair[mode] = summarize(recording)
        assert pair[mode]['stall_advisory_matches'] == count
        assert pair[mode]['stall_advisory_match_counts'] == {'recent duplicate': count}
    result = aggregate([pair])
    for mode, count in [('dom', 2), ('screenshot', 1)]:
        summary = result['modes'][mode]
        assert summary['stall_advisory_matches'] == count
        assert summary['stall_advisory_match_counts'] == {'recent duplicate': count}
        assert summary['stall_advisory_matches_per_run'] == [{'run': pair[mode]['run'], 'matches': count}]
