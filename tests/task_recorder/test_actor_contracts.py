"""Actor validation, response preservation and cancellation contracts."""

import asyncio
import json
import signal
import urllib.error

import pytest

from w8bench.task_recorder import runner
from w8bench.task_recorder.recorder_support import RunnerError


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
