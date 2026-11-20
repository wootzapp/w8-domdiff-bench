"""Actor input policy, action validation, model turns and interruption behavior."""
import asyncio
import base64
import io
import json
import hashlib
import os
import signal
import urllib.error
from pathlib import Path
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from tests.conftest import FakeCDP, actor_preflight_response
from w8bench import settings
from w8bench.task_recorder import capture, runner, task_cli
from w8bench.task_recorder.agent_browser import AgentBrowserClient
from w8bench.task_recorder.recorder_support import RunnerError, write_json
from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.verifier.compare_results import compare

@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"thought": ""}, "rationale"),
        ({"thought": " "}, "rationale"),
        ({"thought": 3}, "rationale"),
        ({"thought": "x" * 1201}, "rationale"),
        ({"memory": ["fact"]}, "bounded text"),
        ({"memory": "x" * 8001}, "bounded text"),
        ({"extra": "untrusted"}, "unexpected action fields"),
        ({"seconds": -0.01}, "0–10"),
        ({"seconds": 10.01}, "0–10"),
        ({"seconds": True}, "finite numeric"),
        ({"seconds": float("nan")}, "finite numeric"),
        ({"seconds": float("inf")}, "finite numeric"),
    ],
)
def test_invalid_action_fields_are_rejected_before_input(changes, reason):
    decision = {"action": "wait", "seconds": 0, "thought": "Observe the result", **changes}
    assert reason in runner.action_rejection_reason(decision, frozenset(), [])

@pytest.mark.parametrize("seconds", [0, 10])
def test_wait_and_memory_limits_accept_their_inclusive_boundaries(seconds):
    decision = {
        "action": "wait",
        "seconds": seconds,
        "thought": "x" * 1200,
        "memory": "m" * 8000,
    }
    assert runner.action_rejection_reason(decision, frozenset(), []) == ""

@pytest.mark.parametrize(
    "x, y, accepted",
    [(0, 0, True), (1000, 1000, True), (1001, 0, False), (0, 1001, False),
     (-1, 0, False), (1.0, 0, False), (True, 0, False), (float("inf"), 0, False),
     (0, float("nan"), False), (0, None, False)],
)
def test_coordinate_bounds_use_normalized_integers_and_include_1000(x, y, accepted):
    decision = {"action": "click", "x": x, "y": y, "thought": "Inspect the control"}
    reason = runner.action_rejection_reason(
        decision, frozenset(), [], observation_mode="screenshot"
    )
    assert (reason == "") is accepted

@pytest.mark.parametrize("pixels, accepted", [(-0.5, True), (0.5, True), (0, False), (False, False)])
def test_scroll_requires_a_finite_nonzero_amount(pixels, accepted):
    decision = {"action": "scroll", "pixels": pixels, "thought": "Read more content"}
    assert (runner.action_rejection_reason(decision, frozenset(), []) == "") is accepted

@pytest.mark.parametrize("url", [None, "", "file:///tmp/page", "javascript:alert(1)", "https://"])
def test_navigation_rejects_missing_or_non_http_destinations(url):
    decision = {"action": "navigate", "url": url, "thought": "Open the next page"}
    assert "HTTP(S) URL" in runner.action_rejection_reason(decision, frozenset(), [])

@pytest.mark.parametrize("action, field", [("type", "text"), ("press", "key")])
@pytest.mark.parametrize("value", [None, "", 42])
def test_focused_input_requires_nonempty_text(action, field, value):
    decision = {"action": action, field: value, "thought": "Use the focused control"}
    assert "nonempty input" in runner.action_rejection_reason(decision, frozenset(), [])

@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "timeout", "invalid_json", "non_object"])
async def test_failed_actor_responses_keep_the_request_without_inventing_usage(
    actor_request_args, monkeypatch, failure
):
    def respond(*args, **kwargs):
        preflight = actor_preflight_response(args[0])
        if preflight is not None: return preflight
        if failure == "http":
            raise urllib.error.HTTPError("https://example.test", 403, "forbidden", {}, None)
        if failure == "timeout":
            raise TimeoutError("transport timeout")
        from io import BytesIO
        return BytesIO(b"invalid" if failure == "invalid_json" else b"[]")

    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    monkeypatch.setattr(runner.urllib.request, "urlopen", respond)
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(runner.asyncio, "to_thread", inline)
    client = runner.ModelClient("secret-never-in-receipt", "gemini-3.8-flash", "https://example.test")
    with pytest.raises(RunnerError) as raised:
        await client.decide(**actor_request_args)
    assert "secret-never-in-receipt" not in str(raised.value)
    assert client.last_input_report["api_call_started"] is True
    assert client.last_response is None
    turn = actor_request_args["turn_dir"]
    assert (turn / "request.json").is_file()
    assert not (turn / "response.json").exists()

@pytest.mark.asyncio
async def test_actor_cancellation_retains_the_dispatched_request(actor_request_args, monkeypatch):
    dispatched = []
    def cancelled(payload):
        dispatched.append(payload)
        raise asyncio.CancelledError
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(runner.asyncio, "to_thread", inline)
    client = runner.ModelClient("offline", "gemini-3.8-flash", "https://example.test")
    monkeypatch.setattr(client, "_post", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await client.decide(**actor_request_args)
    assert client.last_input_report["api_call_started"] is True
    assert client.last_response is None
    assert len(dispatched) == 1
    assert json.loads((actor_request_args["turn_dir"] / "request.json").read_text())["model"] == "gemini-3.8-flash"

@pytest.mark.asyncio
async def test_interrupt_handler_returns_130_and_releases_both_signals(monkeypatch):
    loop = asyncio.get_running_loop()
    installed, released = [], []
    monkeypatch.setattr(loop, "add_signal_handler", lambda signum, callback: installed.append(signum))
    monkeypatch.setattr(loop, "remove_signal_handler", lambda signum: released.append(signum))
    async def cancelled(args):
        raise asyncio.CancelledError
    monkeypatch.setattr(runner, "run", cancelled)
    assert await runner.run_with_interrupt_handlers(object()) == 130
    assert installed == released == [signal.SIGINT, signal.SIGTERM]

@pytest.mark.usefixtures("no_network")
def test_actor_manifest_records_actual_viewport_capture_and_timeout_settings(run_pair):
    paths, *_ = run_pair
    contracts = []
    for mode, path in paths.items():
        manifest = json.loads((path / "manifest.json").read_text())
        contract = manifest["effective_settings"]
        contracts.append(contract)
        assert contract["viewport"] == [1365, 768]
        assert contract["max_turns"] == 6 and contract["settle_seconds"] == 0
        assert contract["snapshot_max_nodes"] == manifest["dom_capture_parameters"]["max_nodes"]
        assert contract["snapshot_max_text_chars"] == manifest["dom_capture_parameters"]["max_text_chars"]
        assert contract["agent_browser_timeout"] == 90 and contract["transport_timeout"] == 180 and contract["cdp_timeout"] == 90
        assert set(contract["prompt_sha256"]) == {"dom", "screenshot"}
        assert "recorder_code_sha256" not in contract
        assert contract["model"] == "gemini-3.8-flash"
    assert contracts[0] == contracts[1]

@pytest.mark.usefixtures("no_network")
@pytest.mark.asyncio
async def test_actor_refuses_changed_scheduled_policy_before_browser_or_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
    expected = settings.actor_settings({"max_turns": 99})
    monkeypatch.setenv("W8_EXPECTED_ACTOR_SETTINGS", json.dumps(expected))
    monkeypatch.setattr(runner, "CDPClient", lambda *args, **kwargs: pytest.fail("settings drift reached the browser"))
    monkeypatch.setattr(runner.ModelClient, "_post", lambda *args: pytest.fail("settings drift reached the model"))
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--task", "Read the heading.",
        "--observation-mode", "screenshot", "--output-dir", str(tmp_path / "recordings"), "--api-key", "offline"])
    with pytest.raises(RunnerError, match="effective settings differ") as caught:
        await runner.run(args)
    assert "max_turns" in str(caught.value)

@pytest.mark.usefixtures("no_network")
def test_modes_capture_and_send_only_their_channel(run_pair):
    paths, payloads, connect, snapshot = run_pair
    dom, ss = (inspect_recording(paths[mode]) for mode in ("dom", "screenshot"))
    assert list(paths["dom"].rglob("*.png"))
    assert list(paths["screenshot"].rglob("dom*"))
    assert not list(paths["screenshot"].rglob("agent_browser*"))
    assert connect.await_count == 1  # Screenshot mode never connects the DOM action tool.
    assert snapshot.await_count == 2  # One interactive reference snapshot per DOM state.
    for payload in payloads["dom"]:
        content = payload["contents"][0]["parts"]
        assert [list(c) for c in content] == [["text"]]
        assert "DOM_ONLY_SECRET" in content[0]["text"]
    for payload in payloads["screenshot"]:
        content = payload["contents"][0]["parts"]
        assert [list(c) for c in content] == [["text"], ["inlineData", "mediaResolution"]]
        assert content[1]["mediaResolution"]["level"] == "MEDIA_RESOLUTION_ULTRA_HIGH"
        assert content[1]["inlineData"]["mimeType"] == "image/png"
        assert "DOM_ONLY_SECRET" not in json.dumps(payload)
        assert "[ref=e1]" not in json.dumps(payload)
        assert "current_agent_browser_snapshot:" not in json.dumps(payload)
        assert "current_chromiumrl_evidence:" not in json.dumps(payload)
    for mode in ("dom", "screenshot"):
        for state in inspect_recording(paths[mode])["manifest"]["states"]:
            assert {"screenshot.png", "dom.json", "dom_full.txt", "dom_model.json", "dom_model.txt"} <= state["artifacts"].keys()
    for payload, row in zip(payloads["screenshot"], ss["decisions"]):
        actual = base64.b64decode(payload["contents"][0]["parts"][1]["inlineData"]["data"])
        saved = paths["screenshot"] / ss["manifest"]["states"][row["state"]-1]["observation"]
        assert hashlib.sha256(actual).hexdigest() == hashlib.sha256(saved.read_bytes()).hexdigest()

@pytest.mark.usefixtures("no_network")
def test_turn_counts_include_rejections_parse_failure_and_termination(capsys, run_pair):
    paths, *_ = run_pair
    dom, ss = [inspect_recording(paths[m]) for m in ("dom", "screenshot")]
    assert [r["model_turn"] for r in dom["decisions"]] == [1, 2, 3, 4]
    receipt, _ = compare(dom, ss)
    assert receipt["dom"]["model_turns"] == 4
    assert receipt["screenshot"]["model_turns"] == 5
    assert receipt["dom"]["action_attempts"] == 1
    assert receipt["screenshot"]["action_attempts"] == 2
    assert receipt["dom"]["rejected_turns"] == 2
    assert receipt["dom"]["termination_turns"] == 1
    assert receipt["dom"]["token_usage"]["total_tokens"] == 120
    assert receipt["successful_pair_turn_delta"] is None
    assert receipt["dom"]["completion"]["verdict"] == "ungraded"
    output = capsys.readouterr().out
    assert "[turn 4/6] terminate" in output
    assert "actor status: success; model turns: 4/6; action attempts: 1" in output
    assert "Final answer: done" in output

@pytest.mark.usefixtures("no_network")
def test_screenshot_input_dispatch_has_no_dom_fallback():
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    client = FakeCDP(observation_mode="screenshot")
    for decision in [{"action": "click", "x": 10, "y": 20}, {"action": "type", "text": "example"},
                     {"action": "press", "key": "Control+A"}, {"action": "scroll", "pixels": 500}]:
        assert asyncio.run(driver.execute(decision, cdp=client))["success"]
    assert {method.split(".")[0] for method, _ in client.calls} == {"Input"}
    assert runner.action_rejection_reason({"action": "click", "id": "e1", "thought": "click"}, frozenset({"e1"}), [], observation_mode="screenshot")
    assert runner.action_rejection_reason({"action": "click", "x": -1, "y": 20, "thought": "click"}, frozenset(), [], observation_mode="screenshot")

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("failure", ["after_capture", "model_transport"])
def test_failed_runs_retain_attempt_counts(run_pair, tmp_path, monkeypatch, failure):
    # Reuse the isolated browser/model fixture, then inject one technical fault.
    def post(self, payload):
        if failure == "model_transport":
            raise RunnerError("offline injected transport error")
        return {"output_text": json.dumps({"action": "click", "x": 10, "y": 20, "thought": "click"}),
                "model": "gemini-3.8-flash", "usage": {"input_tokens": 2, "output_tokens": 1}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    original = FakeCDP.call
    async def call(self, method, params=None, **kwargs):
        if failure == "after_capture" and method == "Page.captureScreenshot" and any(
                m == "Page.captureScreenshot" for m, _ in self.calls):
            raise RunnerError("offline injected capture error")
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeCDP, "call", call)
    root = tmp_path / "failure"
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", "screenshot",
        "--task", "Report done.", "--task-id", "failed", "--output-dir", str(root),
        "--model", "gemini-3.8-flash", "--api-key", "offline-placeholder", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root / "failed")
    assert recording["final"]["run_status"] == "technical_failure"
    assert recording["manifest"]["model_turns"] == (1 if failure == "after_capture" else 0)
    assert len(recording["manifest"]["steps"]) == (1 if failure == "after_capture" else 0)
    assert recording["manifest"]["trajectory_export"]["status"] == ("incomplete" if failure == "after_capture" else "complete")

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize('shape', ['final_with_commentary', 'multiple_finals', 'commentary_only', 'incomplete'])
def test_actor_reads_one_final_json_message(run_pair, tmp_path, monkeypatch, shape):
    paths, *_ = run_pair
    source = paths['dom'] / 'steps/step_001'
    bundle = capture.CaptureBundle(snapshot_path=source / 'dom.json',
        model_text=(source / 'dom_model.txt').read_text(),
        agent_browser_action_text=(source / 'agent_browser_actions.txt').read_text())
    click = {'action': 'click', 'id': 'e1', 'thought': 'activate the current control'}
    fake_termination = {'action': 'terminate', 'status': 'failure', 'termination_reason': 'budget_exhausted',
        'final_answer': 'budget exhausted', 'thought': 'stop prematurely'}
    commentary = {'type': 'message', 'phase': 'commentary', 'content': [
        {'type': 'output_text', 'text': json.dumps(fake_termination)}]}
    final = {'type': 'message', 'phase': 'final_answer', 'content': [
        {'type': 'output_text', 'text': json.dumps(click)}]}
    sent = []
    def post(self, payload):
        sent.append(payload)
        earlier_final = {**commentary, 'phase': 'final_answer'}
        output = [commentary] if shape == 'commentary_only' else [earlier_final, final] if shape == 'multiple_finals' else [commentary, final]
        return {'model': 'gemini-3.8-flash', 'status': 'incomplete' if shape == 'incomplete' else 'completed', 'output': output,
            'output_text': json.dumps(fake_termination) + '\n' + json.dumps(click)}
    monkeypatch.setattr(runner.ModelClient, '_post', post)
    client = runner.ModelClient('offline-placeholder', 'gemini-3.8-flash', 'https://offline.test')
    pending = client.decide(task='Activate the control.', step=8, max_steps=80, bundle=bundle,
        task_memory='', recent_actions=[], turn_dir=tmp_path / 'protocol-turn', viewport=(1365,768))
    if shape in {'final_with_commentary', 'multiple_finals'}:
        decision, _ = asyncio.run(pending)
        assert decision == click
    else:
        with pytest.raises(runner.ModelProtocolError):
            asyncio.run(pending)
    request = sent[0]
    assert not {'tools', 'tool_choice', 'parallel_tool_calls'} & request.keys()
    assert request['generationConfig']['responseMimeType'] == 'application/json'
    assert request['generationConfig']['responseJsonSchema']['additionalProperties'] is False
    assert request['generationConfig']['responseJsonSchema'] == runner.ACTION_SCHEMA
    assert 'step: 8 of 80' in request['contents'][0]['parts'][0]['text']
    assert 'turns_remaining_after_this_call: 72' in request['contents'][0]['parts'][0]['text']

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize('mode', ['dom', 'screenshot'])
def test_false_budget_exhaustion_is_rejected_but_real_blockers_are_allowed(mode):
    decision = {'action': 'terminate', 'status': 'failure', 'termination_reason': 'budget_exhausted',
        'final_answer': 'Unable to complete within the available browser turns.',
        'thought': 'The turn budget shown at the start has been exhausted.'}
    reason = runner.action_rejection_reason(decision, frozenset(), [], observation_mode=mode,
        model_turn=8, max_turns=80)
    assert '72 calls remain' in reason
    assert runner.action_rejection_reason(decision, frozenset(), [], observation_mode=mode,
        model_turn=80, max_turns=80) == ''
    blocked = {**decision, 'termination_reason': 'blocked', 'final_answer': 'The page requires sign-in.'}
    assert runner.action_rejection_reason(blocked, frozenset(), [], observation_mode=mode,
        model_turn=8, max_turns=80) == ''
    missing_reason = {k:v for k,v in decision.items() if k != 'termination_reason'}
    assert 'termination_reason' in runner.action_rejection_reason(missing_reason, frozenset(), [],
        observation_mode=mode, model_turn=8, max_turns=80)

@pytest.mark.usefixtures("no_network")
def test_rejected_termination_and_failed_action_do_not_commit_memory(run_pair, tmp_path, monkeypatch):
    queue = [
        {'action': 'wait', 'seconds': 0, 'thought': 'Observe the page.', 'memory': 'established fact'},
        {'action': 'terminate', 'status': 'failure', 'termination_reason': 'budget_exhausted',
         'final_answer': 'No turns remain.', 'thought': 'Out of turns.', 'memory': 'invented budget fact'},
        {'action': 'wait', 'seconds': 0, 'thought': 'Observe again.', 'memory': 'unconfirmed action fact'},
        {'action': 'terminate', 'status': 'failure', 'termination_reason': 'blocked',
         'final_answer': 'A visible access blocker prevents continuation.', 'thought': 'Record the blocker.'},
    ]
    inputs = []
    def post(self, payload):
        inputs.append(payload)
        return {'model': 'gemini-3.8-flash', 'output_text': json.dumps(queue.pop(0)), 'usage': {'input_tokens': 1, 'output_tokens': 1}}
    attempts = []
    async def execute(self, decision, **kwargs):
        attempts.append(decision)
        if len(attempts) == 2:
            raise RunnerError('injected failed action')
        return {'success': True}
    monkeypatch.setattr(runner.ModelClient, '_post', post)
    monkeypatch.setattr(AgentBrowserClient, 'execute', execute)
    root = tmp_path / 'budget-check'
    args = runner.parse_args(['--env-file', str(tmp_path/'absent.env'), '--observation-mode', 'screenshot',
        '--task', 'Inspect the page.', '--task-id', 'sample', '--output-dir', str(root),
        '--model', 'gemini-3.8-flash', '--api-key', 'offline-placeholder', '--max-turns', '80', '--settle-seconds', '0'])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root/'sample')
    assert recording['manifest']['model_turns'] == 4
    assert len(recording['manifest']['steps']) == 2
    assert recording['final']['termination_reason'] == 'blocked'
    assert recording['decisions'][1]['accepted'] is False
    assert '78 calls remain' in recording['decisions'][1]['rejection_reason']
    assert recording['decisions'][2]['task_memory_before'] == 'established fact'
    assert recording['decisions'][3]['task_memory_before'] == 'established fact'
    assert 'unconfirmed action fact' not in inputs[3]['contents'][0]['parts'][0]['text']

@pytest.mark.usefixtures("no_network")
def test_stalled_actions_are_advisory_and_unconfirmed_success_is_rejected():
    recent = [{'action': {'action': 'click', 'id': 'e1'}, 'action_succeeded': True,
        'progress': {'observation_changed': False, 'task_progress': None}}]
    action = {'action': 'click', 'id': 'e1', 'thought': 'click again'}
    assert runner.action_rejection_reason(action, frozenset({'e1'}), recent) == ''
    assert 'duplicate activation' in runner._stalled_action_advisory(action, 'click', recent)
    assert 'confirmed browser action' in runner.action_rejection_reason(
        {'action': 'terminate', 'status': 'success', 'termination_reason': 'completed',
         'final_answer': 'done', 'thought': 'finished'}, frozenset(), [])
    with pytest.raises(RunnerError, match='exactly one JSON'):
        runner.parse_decision('{"action":"wait"}{"action":"terminate"}')

@pytest.mark.usefixtures("no_network")
def test_actor_settings_and_output_limit_metadata(run_pair):
    paths, payloads, *_ = run_pair
    for mode in ("dom", "screenshot"):
        recording = inspect_recording(paths[mode])
        assert recording["manifest"]["reasoning_effort"] == "medium"
        assert recording["manifest"]["returned_actor_models"] == ["gemini-3.8-flash"]
        assert recording["manifest"]["configured_actor_model"] == "gemini-3.8-flash"
        for payload, row in zip(payloads[mode], recording["decisions"]):
            assert payload["generationConfig"]["maxOutputTokens"] == 10000
            assert payload["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MEDIUM"}
            assert payload["generationConfig"]["responseJsonSchema"]["properties"]["memory"]["maxLength"] == 8000
            assert row["output_limit_hit"] is False
            assert row["configured_model"] == "gemini-3.8-flash"
            assert row["max_output_tokens"] == 10000
            assert row["requested_reasoning_effort"] == "medium"

@pytest.mark.usefixtures("no_network")
def test_current_url_is_shared_and_document_language_is_private(run_pair):
    _, payloads, *_ = run_pair
    for mode in ("dom", "screenshot"):
        text = payloads[mode][0]["contents"][0]["parts"][0]["text"]
        assert "current_document_url: https://example.test" in text
        assert "current_document_language:" not in text

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_incomplete_actor_records_limit_hit_and_reasoning_usage(run_pair, tmp_path, monkeypatch, mode):
    calls = []
    def post(self, payload):
        calls.append(payload)
        return {"id": "limited-response", "model": "gemini-3.8-flash", "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "reasoning": {"effort": "medium"}, "output": [],
            "usage": {"input_tokens": 23, "output_tokens": 10000,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 9000}}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    root = tmp_path / f"limit_{mode}"
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
        "--task", "Inspect the page.", "--task-id", "limited", "--start-url", "https://example.test",
        "--output-dir", str(root), "--model", "gemini-3.8-flash", "--api-key", "offline-placeholder",
        "--max-turns", "2", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root / "limited")
    assert len(calls) == 1
    assert recording["manifest"]["model_turns"] == 1
    assert recording["manifest"]["steps"] == []
    assert recording["manifest"]["returned_actor_models"] == ["gemini-3.8-flash"]
    row = recording["decisions"][0]
    assert row["response_status"] == "incomplete"
    assert row["incomplete_details"] == {"reason": "max_output_tokens"}
    assert row["output_limit_hit"] is True
    assert row["accepted"] is False
    assert row["usage"]["output_tokens_details"]["reasoning_tokens"] == 9000
    assert row["usage"]["output_tokens"] == 10000

@pytest.mark.usefixtures("no_network")
def test_local_request_preparation_failure_is_not_a_model_call(run_pair, tmp_path, monkeypatch):
    monkeypatch.setattr(runner.Path, "read_bytes", lambda self: (_ for _ in ()).throw(OSError("unreadable observation")))
    # Read failure occurs before ModelClient starts an API request.
    client = runner.ModelClient("unused","gemini-3.8-flash","unused")
    bundle = capture.CaptureBundle(observation_mode="screenshot", screenshot_path=tmp_path/"missing.png")
    with pytest.raises(OSError):
        asyncio.run(client.decide(task="inspect",step=1,max_steps=5,bundle=bundle,task_memory="",
            recent_actions=[],turn_dir=tmp_path,viewport=(1365,768)))
    assert not client.last_input_report.get("api_call_started")

@pytest.mark.usefixtures("no_network")
def test_actor_default_limits_and_single_model_configuration(tmp_path, monkeypatch):
    args = runner.parse_args(["--env-file", str(tmp_path/"absent.env")])
    assert args.model == "gemini-3.8-flash"
    assert args.max_steps == 200 and args.max_output_tokens == 10000
    launched = task_cli.parse_args(["sample", "--output-dir", str(tmp_path)])
    assert launched.max_steps == 200 and launched.max_output_tokens == 10000
    assert runner.MAX_TASK_MEMORY_CHARS == 8000
    definition = {"instruction": "Read heading", "start_url": "https://example.test", "model": "gpt-6.1-sol"}
    command = task_cli.build_runner_command(definition, task_id="sample", task_name="sample",
        run_id="sample", output_dir=tmp_path, env_file=tmp_path/"absent.env", model="",
        max_steps=200, observation_mode="dom")
    assert command[command.index("--model")+1] == "gemini-3.8-flash"
    assert command[command.index("--max-output-tokens")+1] == "10000"
    assert "gpt-6.1-sol" not in command  # Catalog metadata cannot select a second actor.

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("configured,override", [("", None), ("gpt-6.1-sol", None),
    ("gemini-3.8-flash", "gpt-6.1-sol")])
def test_actor_startup_rejects_missing_wrong_or_overridden_model(tmp_path, monkeypatch, configured, override):
    monkeypatch.setenv("ACTOR_MODEL", configured)
    monkeypatch.setattr(runner, "CDPClient", lambda *a,**k: pytest.fail("invalid model opened a browser"))
    common = ["--env-file", str(tmp_path/"absent.env"), "--observation-mode", "dom",
        "--task", "Read heading", "--start-url", "https://example.test", "--output-dir", str(tmp_path/"run")]
    options = ["--model", override] if override is not None else []
    args = runner.parse_args(common+options)
    with pytest.raises(RunnerError, match="ACTOR_MODEL=gemini-3.8-flash"):
        asyncio.run(runner.run(args))
    with pytest.raises(RunnerError, match="ACTOR_MODEL=gemini-3.8-flash"):
        task_cli.main(["sample", *common, "--dry-run", *options])
    assert not (tmp_path/"run").exists()

@pytest.mark.usefixtures("no_network")
def test_actor_env_rejects_duplicate_or_conflicting_model_values(tmp_path, monkeypatch):
    envfile = tmp_path/"models.env"
    envfile.write_text("ACTOR_MODEL=gemini-3.8-flash\nACTOR_MODEL=gemini-3.8-flash\n")
    with pytest.raises(RunnerError, match="exactly one"):
        runner.load_env(envfile)
    envfile.write_text("ACTOR_MODEL=gpt-6.1-sol\n")
    with pytest.raises(RunnerError, match="conflicts"):
        runner.load_env(envfile)

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("returned", ["gpt-6.1-sol", "gemini-3.8-flash-mini", None])
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_non_gemini_actor_response_stops_before_any_action(run_pair, tmp_path, monkeypatch, mode, returned):
    calls = []
    def post(self,payload):
        calls.append(payload)
        return {"model": returned, "status": "completed", "output_text": json.dumps({
            "action": "wait", "seconds": 0, "thought": "observe"}),
            "usage": {"input_tokens": 10, "output_tokens": 5}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    monkeypatch.setattr(AgentBrowserClient, "execute", AsyncMock(side_effect=AssertionError("wrong actor executed")))
    root = tmp_path/f"mismatch_{mode}"
    args = runner.parse_args(["--env-file", str(tmp_path/"absent.env"), "--observation-mode", mode,
        "--task", "Read heading", "--task-id", "mismatch", "--start-url", "https://example.test",
        "--output-dir", str(root), "--api-key", "test", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root/"mismatch")
    assert len(calls) == 1 and recording["manifest"]["model_turns"] == 1
    assert recording["manifest"]["steps"] == []
    assert recording["manifest"]["configured_actor_model"] == "gemini-3.8-flash"
    assert recording["decisions"][0]["returned_model"] == returned
    assert "actor model mismatch" in recording["final"]["error"]

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("option,value,error", [("--max-output-tokens", "9000", "exactly 10000"),
    ("--max-output-tokens", "12000", "exactly 10000"), ("--max-turns", "201", "no greater than 200")])
def test_actor_rejects_output_override_and_turns_above_cap(tmp_path, monkeypatch, option, value, error):
    arguments = ["--env-file", str(tmp_path/"absent.env"), "--observation-mode", "dom",
        "--task", "Read heading", "--start-url", "https://example.test", "--output-dir", str(tmp_path/"out")]
    monkeypatch.setattr(runner, "CDPClient", lambda *a,**k: pytest.fail("invalid limits opened browser"))
    with pytest.raises(RunnerError, match=error):
        asyncio.run(runner.run(runner.parse_args(arguments+[option,value])))
    with pytest.raises(RunnerError, match=error):
        task_cli.main(["sample", *arguments, "--dry-run", option,value])
    kwargs = {"max_output_tokens": int(value)} if option=="--max-output-tokens" else {"max_steps": int(value)}
    with pytest.raises(RunnerError, match=error):
        task_cli.build_runner_command({"instruction":"Read heading", "start_url":"https://example.test"},
            task_id="sample", task_name="sample", run_id="sample", output_dir=tmp_path,
            env_file=tmp_path/"absent.env", **kwargs)
    client = runner.ModelClient("test", "gemini-3.8-flash", "https://unused.test")
    bundle = capture.CaptureBundle(snapshot_path=tmp_path/"dom.json")
    with pytest.raises(RunnerError, match=error):
        asyncio.run(client.decide(task="Read heading", step=1, max_steps=kwargs.get("max_steps", 200),
            max_output_tokens=kwargs.get("max_output_tokens", 10000), bundle=bundle,
            task_memory="", recent_actions=[], turn_dir=tmp_path, viewport=(1365,768)))
    assert not client.last_input_report.get("api_call_started")
    assert not (tmp_path/"out").exists()

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("finish_reason", ["STOP", "MAX_TOKENS", "SAFETY"])
def test_gemini_actor_native_transport_and_token_accounting(monkeypatch, finish_reason):
    requests = []
    native = {"responseId": "google-response", "modelVersion": "gemini-3.8-flash",
        "candidates": [{"finishReason": finish_reason, "content": {"parts": [
            {"text": "private thought summary", "thought": True},
            {"text": '{"action":"wait","seconds":0,"thought":"observe"}'}]}}],
        "usageMetadata": {"promptTokenCount": 100, "cachedContentTokenCount": 40,
            "candidatesTokenCount": 20, "thoughtsTokenCount": 30, "totalTokenCount": 150}}
    def respond(request, **kwargs):
        requests.append(request)
        return io.BytesIO(json.dumps(native).encode())
    monkeypatch.setattr("urllib.request.urlopen", respond)
    png = base64.b64encode(b"exact screenshot bytes").decode()
    payload = {"model": "gemini-3.8-flash", "systemInstruction": {"parts": [{"text": "Act"}]},
        "contents": [{"role": "user", "parts": [{"text": "Task"},
            {"inlineData": {"mimeType": "image/png", "data": png}}]}],
        "generationConfig": {"maxOutputTokens": 10000, "thinkingConfig": {"thinkingLevel": "MEDIUM"},
            "mediaResolution": "MEDIA_RESOLUTION_HIGH", "responseMimeType": "application/json",
            "responseJsonSchema": runner.ACTION_SCHEMA}}
    result = runner.ModelClient("fake-google-key", "gemini-3.8-flash",
        "https://generativelanguage.googleapis.com/v1beta")._post(payload)
    request = requests[0]
    assert request.full_url.endswith("/models/gemini-3.8-flash:generateContent")
    assert request.get_header("X-goog-api-key") == "fake-google-key"
    assert request.get_header("Authorization") is None
    wire = json.loads(request.data)
    assert wire == {key: value for key, value in payload.items() if key != "model"}
    assert base64.b64decode(wire["contents"][0]["parts"][1]["inlineData"]["data"]) == b"exact screenshot bytes"
    assert result["model"] == "gemini-3.8-flash" and result["provider_response"] == native
    assert result["usage"] == {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
        "input_tokens_details": {"cached_tokens": 40}, "output_tokens_details": {"reasoning_tokens": 30}}
    assert "private thought" not in result["output_text"]
    assert result["status"] == ("completed" if finish_reason == "STOP" else "incomplete")
    if finish_reason == "MAX_TOKENS":
        assert result["incomplete_details"] == {"reason": "max_output_tokens"}

@pytest.mark.usefixtures("no_network")
def test_gemini_actor_missing_usage_remains_unknown(monkeypatch):
    native = {"modelVersion": "gemini-3.8-flash", "candidates": [
        {"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(json.dumps(native).encode()))
    result = runner.ModelClient("fake-google-key", "gemini-3.8-flash", "https://offline.test")._post({})
    assert result["usage"] == {}


@pytest.mark.parametrize("action", ["click", "scroll"])
@pytest.mark.parametrize("point, viewport, expected", [
    ((0, 0), (1365, 768), (0, 0)),
    ((1000, 1000), (1365, 768), (1364, 767)),
    ((500, 500), (1365, 768), (682, 384)),
    ((122, 321), (1365, 768), (167, 247)),
    ((333, 777), (801, 601), (267, 467)),
])
def test_screenshot_executor_decodes_coordinates_once(action, point, viewport, expected):
    cdp = FakeCDP(observation_mode="screenshot")
    decision = {"action": action, "x": point[0], "y": point[1], "pixels": 300}
    original = dict(decision)
    metadata = asyncio.run(AgentBrowserClient._dispatch_pointer(decision, cdp, viewport))
    assert decision == original
    assert cdp.calls
    assert all((params["x"], params["y"]) == expected for _, params in cdp.calls)
    assert metadata == {"model_coordinates": {"x": point[0], "y": point[1], "units": "normalized_1000"},
        "executed_coordinates": {"x": expected[0], "y": expected[1], "units": "css_pixels"},
        "viewport": list(viewport)}


def test_screenshot_coordinate_schema_does_not_change_dom_schema():
    from w8bench.task_recorder.prompts import SCREENSHOT_PROMPT, SCREENSHOT_PROMPT_VERSION
    assert "CSS pixel coordinates" not in SCREENSHOT_PROMPT
    assert "0 to 1000" in SCREENSHOT_PROMPT
    assert SCREENSHOT_PROMPT_VERSION
    assert runner.ACTION_SCHEMA["properties"]["x"] == {"type": ["number", "null"]}
    for field in ("x", "y"):
        definition = runner.SCREENSHOT_ACTION_SCHEMA["properties"][field]
        assert definition["type"] == ["integer", "null"]
        assert definition["minimum"] == 0 and definition["maximum"] == 1000
        assert "screenshot" in definition["description"]


@pytest.mark.parametrize("value", [-1, 1001, 1.5, 1.0, True, float("inf"), "500"])
def test_screenshot_coordinate_rejections_use_normalized_units(value):
    reason = runner.action_rejection_reason({"action": "click", "x": value, "y": 500,
        "thought": "Click the requested button"}, frozenset(), [], observation_mode="screenshot")
    assert "integer" in reason and "0 to 1000" in reason
    assert "DOM" not in reason and "ref" not in reason and "pixel" not in reason


def test_screenshot_request_rejects_image_viewport_mismatch(tmp_path):
    image = tmp_path / 'screenshot.png'
    Image.new('RGB', (640, 480), 'white').save(image)
    bundle = capture.CaptureBundle(observation_mode='screenshot', screenshot_path=image,
        document_url='https://example.test/')
    client = runner.ModelClient('offline-key', 'gemini-3.8-flash', 'https://offline.test')
    with pytest.raises(RunnerError, match='screenshot dimensions differ'):
        client._actor_request('Click the button', 1, 200, bundle, '', [], tmp_path, (1365, 768), 10000)


@pytest.mark.parametrize('mode', ['dom', 'screenshot'])
def test_fairness_actor_history_omits_private_context_and_diagnostics(actor_observation, tmp_path, monkeypatch, mode):
    from dataclasses import replace
    monkeypatch.setenv('ACTOR_MODEL', 'gemini-3.8-flash')
    monkeypatch.setenv('ACTOR_MEDIA_RESOLUTION', 'HIGH')
    image = tmp_path/'actor_image.png'
    Image.new('RGB', (1365, 768)).save(image)
    bundle = replace(actor_observation, observation_mode=mode, document_language='fr', screenshot_path=image)
    recent = [{'model_turn': 1, 'action': {'action': 'click', **({'id': 'e1'} if mode == 'dom' else {'x': 500, 'y': 500})},
        'action_succeeded': False, 'action_error': 'Covered by #PRIVATE_SELECTOR; dismiss the hidden blocker',
        'action_context': {'name': 'PRIVATE_TARGET_MEMORY', 'role': 'button'},
        'progress': {'observation_changed': False, 'task_progress': None}}]
    payload, _, prompt = runner.ModelClient('unused', 'gemini-3.8-flash', 'https://offline.test')._actor_request(
        'Inspect visible controls.', 2, 200, bundle, '', recent, tmp_path, (1365, 768), 10000)
    assert 'PRIVATE_TARGET_MEMORY' not in prompt and 'PRIVATE_SELECTOR' not in prompt
    assert 'dismiss the hidden blocker' not in prompt and 'action_context' not in prompt
    assert 'current_document_language' not in prompt
    assert '"delivery_status": "failed"' in prompt
    assert recent[0]['action_context']['name'] == 'PRIVATE_TARGET_MEMORY'


@pytest.mark.parametrize('mode', ['dom', 'screenshot'])
def test_fairness_duplicate_matches_are_advisory_in_both_arms(mode):
    target = {'id': 'e2'} if mode == 'dom' else {'x': 500, 'y': 500}
    action = {'action': 'click', **target, 'thought': 'Activate the control'}
    history = [{'action': action, 'action_succeeded': True,
        'progress': {'observation_changed': False, 'task_progress': None}}]
    assert runner.action_rejection_reason(action, frozenset({'e2'}), history, observation_mode=mode) == ''
    assert runner._stalled_action_advisory(action, 'click', history)


@pytest.mark.parametrize('resolution', ['HIGH', 'ULTRA_HIGH'])
def test_fairness_media_resolution_is_explicit_and_guarded(actor_observation, tmp_path, monkeypatch, resolution):
    from dataclasses import replace
    monkeypatch.setenv('ACTOR_MODEL', 'gemini-3.8-flash')
    monkeypatch.setenv('ACTOR_MEDIA_RESOLUTION', resolution)
    image = tmp_path/'actor_image.png'
    Image.new('RGB', (1365, 768)).save(image)
    bundle = replace(actor_observation, observation_mode='screenshot', screenshot_path=image)
    payload, _, _ = runner.ModelClient('unused', 'gemini-3.8-flash', 'https://offline.test')._actor_request(
        'Read visible text.', 1, 200, bundle, '', [], tmp_path, (1365, 768), 10000)
    part = payload['contents'][0]['parts'][1]
    if resolution == 'ULTRA_HIGH': assert part['mediaResolution']['level'] == 'MEDIA_RESOLUTION_ULTRA_HIGH'
    else: assert payload['generationConfig']['mediaResolution'] == 'MEDIA_RESOLUTION_HIGH'
    configured = settings.actor_settings({'model': 'gemini-3.8-flash', 'media_resolution': resolution})
    assert configured['media_resolution'] == resolution
    other = 'HIGH' if resolution == 'ULTRA_HIGH' else 'ULTRA_HIGH'
    assert configured != settings.actor_settings({'model': 'gemini-3.8-flash', 'media_resolution': other})


@pytest.mark.parametrize('total,allowed', [(950, True), (951, False)])
def test_fairness_input_preflight_prevents_dispatch_without_truncation(monkeypatch, tmp_path, total, allowed):
    seen = []
    payload = {'model': 'gemini-3.8-flash', 'contents': [{'parts': [{'text': 'Keep every source fact.' * 30}]}],
        'generationConfig': {'maxOutputTokens': 10000}}
    original = json.loads(json.dumps(payload))
    def respond(request, **kwargs):
        seen.append(request.full_url)
        if request.full_url.endswith(':countTokens'):
            body = json.loads(request.data)
            assert body['generateContentRequest']['contents'] == original['contents']
            return io.BytesIO(json.dumps({'totalTokens': total}).encode())
        if request.get_method() == 'GET':
            return io.BytesIO(json.dumps({'name': 'models/gemini-3.8-flash', 'inputTokenLimit': 1000}).encode())
        assert allowed, 'oversized input reached generation'
        return io.BytesIO(json.dumps({'modelVersion': 'gemini-3.8-flash', 'candidates': [
            {'finishReason': 'STOP', 'content': {'parts': [{'text': '{}'}]}}]}).encode())
    monkeypatch.setattr(runner.urllib.request, 'urlopen', respond)
    client = runner.ModelClient('never-save-this-key', 'gemini-3.8-flash', 'https://offline.test')
    client.turn_dir = tmp_path
    client.last_input_report = {'api_call_started': True}
    if allowed:
        assert client._post(payload)['model'] == 'gemini-3.8-flash'
    else:
        with pytest.raises(RunnerError) as error: client._post(payload)
        assert error.value.technical_failure_class == 'actor_input_limit'
        assert client.last_input_report['api_call_started'] is False
        assert not (tmp_path/'transport_attempts.jsonl').exists()
    receipt = json.loads((tmp_path/'input_preflight.json').read_text())
    assert receipt['input_tokens'] == total and receipt['safe_input_limit'] == 950
    assert payload == original and 'never-save-this-key' not in (tmp_path/'input_preflight.json').read_text()
    assert sum(url.endswith(':generateContent') for url in seen) == int(allowed)


def test_fairness_flash_accepts_only_configured_identity_or_version_suffix(monkeypatch):
    monkeypatch.setenv('ACTOR_MODEL', 'gemini-3.8-flash')
    client = runner.ModelClient('unused', 'gemini-3.8-flash', 'https://offline.test')
    for returned in ['gemini-3.8-flash', 'gemini-3.8-flash-001', 'gemini-3.8-flash-2026-11-01']:
        assert client._validated_action({'model': returned, 'status': 'completed', 'output_text': '{"action":"wait"}'})['action'] == 'wait'
    for returned in ['gemini-3.1-pro-preview', 'gemini-3.8-flash-lite', None]:
        with pytest.raises(runner.ModelProtocolError): client._validated_action({'model': returned, 'output_text': '{"action":"wait"}'})


def test_fairness_raw_runner_is_never_attested_fresh(monkeypatch):
    monkeypatch.delenv('RUNNER_BROWSER_PROFILE_PROVENANCE', raising=False)
    profile = runner.browser_profile_provenance_from_environment()
    assert profile['profile_fresh_at_run_start'] is False and profile['launch_mode'] == 'raw'


@pytest.mark.parametrize('blocked_stage', ['metadata', 'count'])
def test_fairness_cancelled_preflight_cannot_write_late_receipts(monkeypatch, tmp_path, blocked_stage):
    client = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')
    client.last_input_report = {'api_call_started': True}
    client.turn_dir = tmp_path
    pending = tmp_path/'input_preflight.json'
    preserved = {'status': 'cancelled', 'input_tokens': None, 'generation_attempted': False}
    calls = []
    def respond(request, **kwargs):
        stage = 'count' if request.full_url.endswith(':countTokens') else 'metadata' if request.get_method() == 'GET' else 'generation'
        calls.append(stage)
        if stage == blocked_stage:
            client.transport_cancelled = True
            client.last_input_report['input_preflight'] = preserved.copy()
            write_json(pending, preserved)
        assert stage != 'generation'
        return io.BytesIO(json.dumps({'name': 'models/gemini-3.8-flash', 'inputTokenLimit': 1000}
            if stage == 'metadata' else {'totalTokens': 20}).encode())
    monkeypatch.setattr(runner.urllib.request, 'urlopen', respond)
    with pytest.raises(asyncio.CancelledError): client._post({'contents': [{'parts': [{'text': 'a' * 600}]}]})
    assert json.loads(pending.read_text()) == preserved
    assert client.last_input_report['input_preflight'] == preserved
    assert calls == (['metadata'] if blocked_stage == 'metadata' else ['metadata', 'count'])


@pytest.mark.parametrize('name', ['task_2026-11-18', 'task_20261118', 'task_12-34-56'])
def test_fairness_task_names_refuse_dates_and_times(name):
    with pytest.raises(RunnerError, match='dates or times'): runner.safe_task_id(name)


def test_fairness_inherited_launcher_claim_does_not_attest_a_raw_runner(monkeypatch):
    profile = {'container_id': 'fixture-container', 'container_created_at': 'fixture',
        'profile_fresh_at_run_start': True, 'tasks_previously_run_in_container': 0,
        'freshly_recreated_by_launcher': True, 'launch_mode': 'fresh', 'launcher_pid': os.getppid()+1,
        'browser_environment': {'CHROMIUM_RESET_PROFILE': '1'}}
    monkeypatch.setenv('RUNNER_BROWSER_PROFILE_PROVENANCE', json.dumps(profile))
    actual = runner.browser_profile_provenance_from_environment()
    assert actual['profile_fresh_at_run_start'] is False
    assert actual['launch_mode'] == 'raw'


@pytest.mark.parametrize('estimate,counted', [(499, False), (500, False), (501, True)])
def test_input_preflight_counts_only_above_half_limit(monkeypatch, tmp_path, estimate, counted):
    payload = {'contents': [{'parts': [{'text': ''}]}]}
    overhead = len(json.dumps(payload).encode())
    payload['contents'][0]['parts'][0]['text'] = 'a' * (estimate - overhead)
    calls = []
    def respond(request, **kwargs):
        calls.append(request.full_url)
        if request.full_url.endswith(':countTokens'):
            return io.BytesIO(b'{"totalTokens":450}')
        return io.BytesIO(b'{"modelVersion":"gemini-3.8-flash","candidates":[]}')
    monkeypatch.setattr(runner.urllib.request, 'urlopen', respond)
    client = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')
    client.model_input_limit = 1000
    client.turn_dir = tmp_path
    client.last_input_report = {'api_call_started': True}
    client._post(payload)
    receipt = client.last_input_report['input_preflight']
    assert receipt['estimated_input_tokens'] == estimate
    assert sum(url.endswith(':countTokens') for url in calls) == int(counted)
    assert receipt['status'] == ('within_limit' if counted else 'local_within_limit')
    assert receipt['input_tokens'] == (450 if counted else None)
    assert receipt['generation_attempted'] is True


@pytest.mark.parametrize('resolution,image_tokens', [('HIGH', 1100), ('ULTRA_HIGH', 2205)])
def test_input_preflight_fixed_image_cost_excludes_base64(monkeypatch, resolution, image_tokens):
    payload = {'contents': [{'parts': [{'text': 'é'}, {'inlineData': {'mimeType': 'image/png', 'data': 'a' * 10000},
        'mediaResolution': {'level': 'MEDIA_RESOLUTION_' + resolution}}]}]}
    client = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')
    client.model_input_limit = 1048576
    client.last_input_report = {'api_call_started': True}
    seen = []
    def respond(request, **kwargs):
        seen.append(request.full_url)
        assert request.full_url.endswith(':generateContent')
        assert json.loads(request.data)['contents'][0]['parts'][1]['inlineData']['data'] == 'a' * 10000
        return io.BytesIO(b'{}')
    monkeypatch.setattr(runner.urllib.request, 'urlopen', respond)
    client._post(payload)
    receipt = client.last_input_report['input_preflight']
    assert receipt['image_tokens'] == image_tokens
    assert receipt['text_utf8_bytes'] == receipt['text_characters'] + 1
    assert receipt['estimated_input_tokens'] == receipt['text_utf8_bytes'] + image_tokens < 3000
    assert len(seen) == 1


@pytest.mark.parametrize('estimate,recover,allowed', [(700, True, True), (700, False, True), (951, False, False)])
def test_count_tokens_retries_then_uses_confirmed_or_estimated_size(monkeypatch, tmp_path, estimate, recover, allowed):
    import urllib.error
    payload = {'contents': [{'parts': [{'text': ''}]}]}
    payload['contents'][0]['parts'][0]['text'] = 'a' * (estimate - len(json.dumps(payload)))
    client = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')
    client.model_input_limit = 1000
    client.last_input_report = {'api_call_started': True}
    client.turn_dir = tmp_path
    counts, generated, delays = [], [], []
    def respond(request, **kwargs):
        if request.full_url.endswith(':countTokens'):
            counts.append(request)
            if recover and len(counts) == 3: return io.BytesIO(b'{"totalTokens":600}')
            if len(counts) == 1: raise TimeoutError('temporary')
            raise urllib.error.HTTPError(request.full_url, 503, 'temporary', {}, io.BytesIO(b'{}'))
        generated.append(request)
        return io.BytesIO(b'{}')
    monkeypatch.setattr(runner.urllib.request, 'urlopen', respond)
    monkeypatch.setattr(runner.time, 'sleep', delays.append)
    monkeypatch.setattr(runner.random, 'uniform', lambda *args: 0)
    if allowed: client._post(payload)
    else:
        with pytest.raises(RunnerError) as error: client._post(payload)
        assert error.value.technical_failure_class == 'actor_input_limit'
    receipt = json.loads((tmp_path/'input_preflight.json').read_text())
    assert len(counts) == 3 and delays == [2, 8]
    assert len(generated) == int(allowed)
    assert receipt['input_tokens'] == (600 if recover else None)
    assert receipt['status'] == ('within_limit' if recover else 'local_fallback' if allowed else 'input_limit')
    assert len(receipt['transport_attempts']) == 3
    if not allowed: assert not (tmp_path/'transport_attempts.jsonl').exists()


@pytest.mark.parametrize('status,body,kind', [(401, '{}', 'provider_auth'),
    (429, '{"error":"credit_balance_exhausted"}', 'provider_quota'),
    (429, '{"error":"billing"}', 'provider_billing')])
def test_count_tokens_permanent_provider_errors_never_retry_or_generate(monkeypatch, status, body, kind):
    import urllib.error
    client = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')
    client.model_input_limit = 1000
    client.last_input_report = {'api_call_started': True}
    seen = []
    def respond(request, **kwargs):
        seen.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, 'permanent', {}, io.BytesIO(body.encode()))
    monkeypatch.setattr(runner.urllib.request, 'urlopen', respond)
    with pytest.raises(RunnerError) as error: client._post({'contents': [{'parts': [{'text': 'a'*600}]}]})
    assert error.value.provider_failure_kind == kind
    assert len(seen) == 1 and seen[0].endswith(':countTokens')
    assert client.last_input_report['api_call_started'] is False


def test_preflight_metadata_failure_keeps_small_request_local(monkeypatch):
    client = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')
    client.last_input_report = {'api_call_started': True}
    seen, delays = [], []
    def respond(request, **kwargs):
        seen.append(request.full_url)
        if request.get_method() == 'GET': raise TimeoutError('temporary metadata failure')
        assert request.full_url.endswith(':generateContent')
        return io.BytesIO(b'{}')
    monkeypatch.setattr(runner.urllib.request, 'urlopen', respond)
    monkeypatch.setattr(runner.time, 'sleep', delays.append)
    monkeypatch.setattr(runner.random, 'uniform', lambda *args: 0)
    client._post({'contents': [{'parts': [{'text': 'Small request'}]}]})
    receipt = client.last_input_report['input_preflight']
    assert receipt['status'] == 'local_within_limit'
    assert receipt['input_limit_source'] == 'configured_model_limit'
    assert receipt['estimated_input_tokens'] < receipt['model_input_limit'] // 2
    assert len(seen) == 4 and delays == [2, 8]
    assert not any(url.endswith(':countTokens') for url in seen)
    assert receipt['generation_attempted'] is True


@pytest.mark.parametrize('mode', ['dom', 'screenshot'])
@pytest.mark.parametrize('rule', ['duplicate', 'cycle', 'recent'])
def test_all_stall_rules_are_private_advisories_in_both_arms(actor_observation, tmp_path, monkeypatch, mode, rule):
    from dataclasses import replace
    a = {'action': 'click', **({'id': 'e2'} if mode == 'dom' else {'x': 500, 'y': 500}), 'thought': 'Click'}
    b = {'action': 'click', **({'id': 'e3'} if mode == 'dom' else {'x': 600, 'y': 500}), 'thought': 'Click'}
    actions = [a] if rule == 'duplicate' else [a, b, a] if rule == 'cycle' else [a, b]
    candidate = b if rule == 'cycle' else a
    history = [{'action': action, 'action_succeeded': True, 'progress': {'observation_changed': False},
        'stall_advisory': 'PRIVATE_LOOP_MARKER'} for action in actions]
    assert runner.action_rejection_reason(candidate, frozenset({'e2','e3'}), history, observation_mode=mode) == ''
    assert runner._stalled_action_advisory(candidate, 'click', history)
    image = tmp_path/'private_loop.png'
    Image.new('RGB', (1365, 768)).save(image)
    bundle = replace(actor_observation, observation_mode=mode, screenshot_path=image)
    payload, _, _ = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')._actor_request(
        'Read the page.', 4, 200, bundle, '', history, tmp_path, (1365, 768), 10000)
    assert 'PRIVATE_LOOP_MARKER' not in json.dumps(payload)
    assert 'stall_advisory' not in json.dumps(payload)


def test_screenshot_default_uses_ultra_high(actor_observation, tmp_path, monkeypatch):
    from dataclasses import replace
    monkeypatch.delenv('ACTOR_MEDIA_RESOLUTION', raising=False)
    client = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')
    args = runner.parse_args(['--env-file', str(tmp_path / 'absent.env')])
    assert client.media_resolution == args.media_resolution == 'ULTRA_HIGH'
    configured = settings.actor_settings({})
    assert configured['media_resolution'] == 'ULTRA_HIGH'
    assert configured['technical_retry_policy']['browser_failure_checks'] == [
        'before_actor_request', 'after_actor_response', 'before_terminal_acceptance']
    image = tmp_path / 'observation.png'
    Image.new('RGB', (1365, 768)).save(image)
    bundle = replace(actor_observation, observation_mode='screenshot', screenshot_path=image)
    payload, _, _ = client._actor_request('Read the text.', 1, 200, bundle, '', [], tmp_path, (1365, 768), 10000)
    assert payload['contents'][0]['parts'][1]['mediaResolution']['level'] == 'MEDIA_RESOLUTION_ULTRA_HIGH'
    assert payload['generationConfig']['thinkingConfig'] == {'thinkingLevel': 'MEDIUM'}
    assert payload['generationConfig']['maxOutputTokens'] == 10000
