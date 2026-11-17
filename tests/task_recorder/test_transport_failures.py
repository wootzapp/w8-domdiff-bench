"""Malformed CDP frames release pending calls and recorder resources."""

import json
from unittest.mock import AsyncMock

import pytest

from w8bench.task_recorder import runner
from w8bench.task_recorder.recorder_support import RunnerError


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid_json", "non_object", "transport"])
async def test_reader_failure_fails_pending_calls_and_closes_resources(interrupted_cdp_transport, failure):
    cdp, socket, http = interrupted_cdp_transport(failure)
    with pytest.raises(RunnerError, match="CDP websocket closed"):
        await cdp.call("Page.getFrameTree")
    assert cdp.pending == {}
    await cdp.close()
    assert socket.closed and http.close.await_count == 1
    await cdp.close()
    assert http.close.await_count == 1


@pytest.mark.asyncio
async def test_malformed_reader_records_a_technical_failure_without_actor_calls(
    interrupted_cdp_transport, tmp_path, monkeypatch
):
    cdp, socket, http = interrupted_cdp_transport()
    monkeypatch.setattr(cdp, "connect", AsyncMock())
    monkeypatch.setattr(runner, "CDPClient", lambda *args, **kwargs: cdp)
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setattr(runner.ModelClient, "_post", lambda *args: pytest.fail("capture failure dispatched an actor request"))
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", "screenshot",
        "--task", "Read the heading.", "--start-url", "https://example.test/", "--task-id", "failure",
        "--output-dir", str(tmp_path / "recordings"), "--api-key", "offline", "--settle-seconds", "0"])
    assert await runner.run(args) == 2
    final = json.loads((tmp_path / "recordings/failure/final.json").read_text())
    assert final["run_status"] == "error" and final["model_turns"] == 0
    assert "CDP websocket closed" in final["error"]
    assert socket.closed and http.close.await_count == 1
