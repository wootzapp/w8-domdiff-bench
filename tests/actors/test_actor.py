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

from tests.conftest import FakeCDP
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
    [(0, 0, True), (1364.9, 767.9, True), (1365, 0, False), (0, 768, False),
     (-0.01, 0, False), (True, 0, False), (float("inf"), 0, False),
     (0, float("nan"), False), (0, None, False)],
)
def test_coordinate_bounds_use_css_pixels_and_exclude_the_upper_edge(x, y, accepted):
    decision = {"action": "click", "x": x, "y": y, "thought": "Inspect the control"}
    reason = runner.action_rejection_reason(
        decision, frozenset(), [], observation_mode="screenshot", viewport=(1365, 768)
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
        if failure == "http":
            raise urllib.error.HTTPError("https://example.test", 403, "forbidden", {}, None)
        if failure == "timeout":
            raise TimeoutError("transport timeout")
        from io import BytesIO
        return BytesIO(b"invalid" if failure == "invalid_json" else b"[]")

    monkeypatch.setattr(runner.urllib.request, "urlopen", respond)
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(runner.asyncio, "to_thread", inline)
    client = runner.ModelClient("secret-never-in-receipt", "gemini-3.1-pro-preview", "https://example.test")
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
    client = runner.ModelClient("offline", "gemini-3.1-pro-preview", "https://example.test")
    monkeypatch.setattr(client, "_post", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await client.decide(**actor_request_args)
    assert client.last_input_report["api_call_started"] is True
    assert client.last_response is None
    assert len(dispatched) == 1
    assert json.loads((actor_request_args["turn_dir"] / "request.json").read_text())["model"] == "gemini-3.1-pro-preview"

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
        assert contract["model"] == "gemini-3.1-pro-preview"
    assert contracts[0] == contracts[1]

@pytest.mark.usefixtures("no_network")
@pytest.mark.asyncio
async def test_actor_refuses_changed_scheduled_policy_before_browser_or_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
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
        assert [list(c) for c in content] == [["text"], ["inlineData"]]
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
                "model": "gemini-3.1-pro-preview", "usage": {"input_tokens": 2, "output_tokens": 1}}
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
        "--model", "gemini-3.1-pro-preview", "--api-key", "offline-placeholder", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root / "failed")
    assert recording["final"]["run_status"] == "error"
    assert recording["manifest"]["model_turns"] == 1
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
        return {'model': 'gemini-3.1-pro-preview', 'status': 'incomplete' if shape == 'incomplete' else 'completed', 'output': output,
            'output_text': json.dumps(fake_termination) + '\n' + json.dumps(click)}
    monkeypatch.setattr(runner.ModelClient, '_post', post)
    client = runner.ModelClient('offline-placeholder', 'gemini-3.1-pro-preview', 'https://offline.test')
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
        return {'model': 'gemini-3.1-pro-preview', 'output_text': json.dumps(queue.pop(0)), 'usage': {'input_tokens': 1, 'output_tokens': 1}}
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
        '--model', 'gemini-3.1-pro-preview', '--api-key', 'offline-placeholder', '--max-turns', '80', '--settle-seconds', '0'])
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
def test_stalled_actions_and_unconfirmed_success_are_rejected():
    recent = [{'action': {'action': 'click', 'id': 'e1'}, 'action_succeeded': True,
        'progress': {'made_progress': False}}]
    assert 'duplicate activation' in runner.action_rejection_reason(
        {'action': 'click', 'id': 'e1', 'thought': 'click again'}, frozenset({'e1'}), recent)
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
        assert recording["manifest"]["returned_actor_models"] == ["gemini-3.1-pro-preview"]
        assert recording["manifest"]["configured_actor_model"] == "gemini-3.1-pro-preview"
        for payload, row in zip(payloads[mode], recording["decisions"]):
            assert payload["generationConfig"]["maxOutputTokens"] == 10000
            assert payload["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MEDIUM"}
            assert payload["generationConfig"]["responseJsonSchema"]["properties"]["memory"]["maxLength"] == 8000
            assert row["output_limit_hit"] is False
            assert row["configured_model"] == "gemini-3.1-pro-preview"
            assert row["max_output_tokens"] == 10000
            assert row["requested_reasoning_effort"] == "medium"

@pytest.mark.usefixtures("no_network")
def test_current_url_is_shared_but_language_is_dom_only(run_pair):
    _, payloads, *_ = run_pair
    for mode in ("dom", "screenshot"):
        text = payloads[mode][0]["contents"][0]["parts"][0]["text"]
        assert "current_document_url: https://example.test" in text
        assert ("current_document_language:" in text) == (mode == "dom")

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_incomplete_actor_records_limit_hit_and_reasoning_usage(run_pair, tmp_path, monkeypatch, mode):
    calls = []
    def post(self, payload):
        calls.append(payload)
        return {"id": "limited-response", "model": "gemini-3.1-pro-preview", "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "reasoning": {"effort": "medium"}, "output": [],
            "usage": {"input_tokens": 23, "output_tokens": 10000,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 9000}}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    root = tmp_path / f"limit_{mode}"
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
        "--task", "Inspect the page.", "--task-id", "limited", "--start-url", "https://example.test",
        "--output-dir", str(root), "--model", "gemini-3.1-pro-preview", "--api-key", "offline-placeholder",
        "--max-turns", "2", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root / "limited")
    assert len(calls) == 1
    assert recording["manifest"]["model_turns"] == 1
    assert recording["manifest"]["steps"] == []
    assert recording["manifest"]["returned_actor_models"] == ["gemini-3.1-pro-preview"]
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
    client = runner.ModelClient("unused","gemini-3.1-pro-preview","unused")
    bundle = capture.CaptureBundle(observation_mode="screenshot", screenshot_path=tmp_path/"missing.png")
    with pytest.raises(OSError):
        asyncio.run(client.decide(task="inspect",step=1,max_steps=5,bundle=bundle,task_memory="",
            recent_actions=[],turn_dir=tmp_path,viewport=(1365,768)))
    assert not client.last_input_report.get("api_call_started")

@pytest.mark.usefixtures("no_network")
def test_actor_default_limits_and_single_model_configuration(tmp_path, monkeypatch):
    args = runner.parse_args(["--env-file", str(tmp_path/"absent.env")])
    assert args.model == "gemini-3.1-pro-preview"
    assert args.max_steps == 200 and args.max_output_tokens == 10000
    launched = task_cli.parse_args(["sample", "--output-dir", str(tmp_path)])
    assert launched.max_steps == 200 and launched.max_output_tokens == 10000
    assert runner.MAX_TASK_MEMORY_CHARS == 8000
    definition = {"instruction": "Read heading", "start_url": "https://example.test", "model": "gpt-6.1-sol"}
    command = task_cli.build_runner_command(definition, task_id="sample", task_name="sample",
        run_id="sample", output_dir=tmp_path, env_file=tmp_path/"absent.env", model="",
        max_steps=200, observation_mode="dom")
    assert command[command.index("--model")+1] == "gemini-3.1-pro-preview"
    assert command[command.index("--max-output-tokens")+1] == "10000"
    assert "gpt-6.1-sol" not in command  # Catalog metadata cannot select a second actor.

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("configured,override", [("", None), ("gpt-6.1-sol", None),
    ("gemini-3.1-pro-preview", "gpt-6.1-sol")])
def test_actor_startup_rejects_missing_wrong_or_overridden_model(tmp_path, monkeypatch, configured, override):
    monkeypatch.setenv("ACTOR_MODEL", configured)
    monkeypatch.setattr(runner, "CDPClient", lambda *a,**k: pytest.fail("invalid model opened a browser"))
    common = ["--env-file", str(tmp_path/"absent.env"), "--observation-mode", "dom",
        "--task", "Read heading", "--start-url", "https://example.test", "--output-dir", str(tmp_path/"run")]
    options = ["--model", override] if override is not None else []
    args = runner.parse_args(common+options)
    with pytest.raises(RunnerError, match="ACTOR_MODEL=gemini-3.1-pro-preview"):
        asyncio.run(runner.run(args))
    with pytest.raises(RunnerError, match="ACTOR_MODEL=gemini-3.1-pro-preview"):
        task_cli.main(["sample", *common, "--dry-run", *options])
    assert not (tmp_path/"run").exists()

@pytest.mark.usefixtures("no_network")
def test_actor_env_rejects_duplicate_or_conflicting_model_values(tmp_path, monkeypatch):
    envfile = tmp_path/"models.env"
    envfile.write_text("ACTOR_MODEL=gemini-3.1-pro-preview\nACTOR_MODEL=gemini-3.1-pro-preview\n")
    with pytest.raises(RunnerError, match="exactly one"):
        runner.load_env(envfile)
    envfile.write_text("ACTOR_MODEL=gpt-6.1-sol\n")
    with pytest.raises(RunnerError, match="conflicts"):
        runner.load_env(envfile)

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("returned", ["gpt-6.1-sol", "gemini-3.1-pro-preview-mini", None])
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
    assert recording["manifest"]["configured_actor_model"] == "gemini-3.1-pro-preview"
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
    client = runner.ModelClient("test", "gemini-3.1-pro-preview", "https://unused.test")
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
    native = {"responseId": "google-response", "modelVersion": "gemini-3.1-pro-preview",
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
    payload = {"model": "gemini-3.1-pro-preview", "systemInstruction": {"parts": [{"text": "Act"}]},
        "contents": [{"role": "user", "parts": [{"text": "Task"},
            {"inlineData": {"mimeType": "image/png", "data": png}}]}],
        "generationConfig": {"maxOutputTokens": 10000, "thinkingConfig": {"thinkingLevel": "MEDIUM"},
            "mediaResolution": "MEDIA_RESOLUTION_HIGH", "responseMimeType": "application/json",
            "responseJsonSchema": runner.ACTION_SCHEMA}}
    result = runner.ModelClient("fake-google-key", "gemini-3.1-pro-preview",
        "https://generativelanguage.googleapis.com/v1beta")._post(payload)
    request = requests[0]
    assert request.full_url.endswith("/models/gemini-3.1-pro-preview:generateContent")
    assert request.get_header("X-goog-api-key") == "fake-google-key"
    assert request.get_header("Authorization") is None
    wire = json.loads(request.data)
    assert wire == {key: value for key, value in payload.items() if key != "model"}
    assert base64.b64decode(wire["contents"][0]["parts"][1]["inlineData"]["data"]) == b"exact screenshot bytes"
    assert result["model"] == "gemini-3.1-pro-preview" and result["provider_response"] == native
    assert result["usage"] == {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
        "input_tokens_details": {"cached_tokens": 40}, "output_tokens_details": {"reasoning_tokens": 30}}
    assert "private thought" not in result["output_text"]
    assert result["status"] == ("completed" if finish_reason == "STOP" else "incomplete")
    if finish_reason == "MAX_TOKENS":
        assert result["incomplete_details"] == {"reason": "max_output_tokens"}

@pytest.mark.usefixtures("no_network")
def test_gemini_actor_missing_usage_remains_unknown(monkeypatch):
    native = {"modelVersion": "gemini-3.1-pro-preview", "candidates": [
        {"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(json.dumps(native).encode()))
    result = runner.ModelClient("fake-google-key", "gemini-3.1-pro-preview", "https://offline.test")._post({})
    assert result["usage"] == {}
