"""Offline recordings, CDP transport and browser runtime fixtures."""
import asyncio
import json
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
from tests.conftest import FakeCDP
from w8bench.task_recorder import runner
from w8bench.task_recorder.agent_browser import AgentBrowserClient, AgentBrowserObservation
from w8bench.task_recorder.recorder_support import write_json


def digest(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()}

@pytest.fixture
def runtime_configuration(tmp_path):
    path = tmp_path / "browser.env"
    path.write_text(
        "CONTAINER_NAME=fixture-browser\nCDP_HOST_PORT=49335\nNOVNC_HOST_PORT=16191\n",
        encoding="utf-8",
    )
    return path

@pytest_asyncio.fixture
async def interrupted_cdp_transport():
    import asyncio
    from contextlib import suppress
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from w8bench.task_recorder import capture

    transports = []
    def make(failure="invalid_json"):
        class Socket:
            def __init__(self):
                self.sent = asyncio.Event()
                self.closed = False
            async def send_json(self, request):
                self.sent.set()
            async def __aiter__(self):
                await self.sent.wait()
                if failure == "transport":
                    raise ConnectionError("offline transport ended")
                yield SimpleNamespace(type=capture.aiohttp.WSMsgType.TEXT,
                    data="not-json" if failure == "invalid_json" else "[]")
            async def close(self):
                self.closed = True
        cdp = capture.CDPClient("http://localhost:9222", timeout=0.02)
        socket = Socket()
        http = SimpleNamespace(close=AsyncMock())
        cdp.ws, cdp.http = socket, http
        cdp.reader = asyncio.create_task(cdp._read_messages())
        transports.append((cdp, socket, http))
        return cdp, socket, http
    yield make
    for cdp, socket, http in transports:
        if cdp.reader is not None:
            cdp.reader.cancel()
            with suppress(BaseException):
                await cdp.reader
        if not socket.closed:
            await socket.close()
        if not http.close.await_count:
            await http.close()

@pytest.fixture
def recording_factory(tmp_path, monkeypatch, no_network):
    monkeypatch.setenv("RUNNER_BROWSER_PROFILE_PROVENANCE", json.dumps({
        "container_id": "offline", "container_created_at": "fixture", "profile_fresh_at_run_start": True,
        "tasks_previously_run_in_container": 0, "browser_build": {"image_id": "offline"},
        "browser_environment": {"LANG": "en_US.UTF-8"}}))
    monkeypatch.setattr(runner, "CDPClient", FakeCDP)
    monkeypatch.setattr(runner, "synchronize_recorder_target", AsyncMock(return_value={}))
    monkeypatch.setattr(AgentBrowserClient, "connect", AsyncMock())
    monkeypatch.setattr(AgentBrowserClient, "close", AsyncMock())
    monkeypatch.setattr(AgentBrowserClient, "_invoke", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(AgentBrowserClient, "snapshot", AsyncMock(return_value=AgentBrowserObservation(
        text='- button "Save" [ref=e1]', refs=frozenset({"e1"}), origin="fixture", command=("snapshot", "-i"),
        targets={"e1": {"role": "button", "name": "Save"}})))
    def make(name="run", *, status="success", actions=1, keyboard=False, mode="dom"):
        queue = [{"action": "type", "text": "recorded", "thought": "Type into focused control"} if keyboard else
                 {"action": "click", **({"id": "e1"} if mode == "dom" else {"x": 10, "y": 20}), "thought": "Inspect"}
                 for _ in range(actions)]
        status = status if actions else "failure"
        queue.append({"action": "terminate", "status": status, "termination_reason": "completed" if status == "success" else "blocked",
            "final_answer": "The recorded answer.", "thought": "Finished"})
        def post(self, payload):
            return {"model": "gemini-3.8-flash", "output_text": json.dumps(queue.pop(0)),
                "usage": {"input_tokens": 20, "output_tokens": 10}}
        monkeypatch.setattr(runner.ModelClient, "_post", post)
        output = tmp_path / "recordings" / name
        args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
            "--task", "Inspect the example page.", "--task-id", name, "--source-task-id", "task1",
            "--start-url", "https://example.test/", "--output-dir", str(output), "--run-name", name,
            "--model", "gemini-3.8-flash", "--api-key", "offline", "--max-turns", str(actions + 2), "--settle-seconds", "0"])
        assert asyncio.run(runner.run(args)) in {0, 2}
        return output / name
    return make

def make_trajectory_dir(root: Path, n_actions: int = 2, *, screenshots: bool = False) -> Path:
    directory = root / "sample_traj"
    directory.mkdir(parents=True, exist_ok=True)
    events = [{"source": "WebSurfer", "action": "click" if index < n_actions - 1 else "stop_execution",
        "url": f"https://example.com/step_{index}", "arguments": {
            "action": "click" if index < n_actions - 1 else "stop_execution",
            "thoughts": f"thinking at step {index}", "screen_description": f"screen at step {index}",
            "target": f"button_{index}" if index < n_actions - 1 else None}} for index in range(n_actions)]
    (directory / "web_surfer.log").write_text("\n".join(json.dumps(event) for event in events) + "\n")
    answer = {"final_answer": "done", "env_state_json": "{}", "env_state_raw": "", "is_aborted": False,
        "is_rel_paths": True, "token_usage": {}}
    if screenshots:
        names = []
        for index in range(n_actions + 1):
            image = directory / f"screenshot_{index}.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            names.append(image.name)
        answer["screenshots"] = names
    (directory / "_answer.json").write_text(json.dumps(answer))
    return directory
