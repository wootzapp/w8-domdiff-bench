"""Keep the complete contract suite offline and independent of local credentials."""
import json
from pathlib import Path
import socket

import pytest
import pytest_asyncio


@pytest.fixture(autouse=True)
def offline_model_access(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test-key")
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(Path(__file__).resolve().parents[1] / ".runtime" / "tiktoken_cache"))
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError("offline tests cannot connect to model providers or external services")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)


@pytest.fixture
def actor_observation(tmp_path):
    from w8bench.task_recorder.capture import CaptureBundle

    state = tmp_path / "steps" / "step_001"
    state.mkdir(parents=True)
    snapshot = state / "dom.json"
    snapshot.write_text(json.dumps({"nodes": []}))
    (state / "dom_model.txt").write_text("Status: Ready\n", encoding="utf-8")
    return CaptureBundle(
        snapshot={"url": "https://example.test/"},
        snapshot_path=snapshot,
        model_text="Status: Ready\n",
        agent_browser_action_text='- button "Save" [ref=e1]\n',
        agent_browser_refs=frozenset({"e1"}),
        document_url="https://example.test/",
    )


@pytest.fixture
def actor_request_args(actor_observation, tmp_path, monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
    return {
        "task": "Inspect the example page.",
        "step": 1,
        "max_steps": 2,
        "bundle": actor_observation,
        "task_memory": "",
        "recent_actions": [],
        "turn_dir": tmp_path / "turns" / "turn_000001",
        "viewport": (1365, 768),
    }


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
def effective_settings_batch(tmp_path, monkeypatch):
    import shutil
    from types import SimpleNamespace

    from w8bench import settings
    from w8bench.task_recorder import task_cli
    from w8bench.task_recorder.recorder_support import write_json

    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("EVIDENCE_AUDIT_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_MODEL", "gpt-6.1-sol")
    monkeypatch.setenv("EVIDENCE_AUDIT_PROVIDER", "google")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_PROVIDER", "openai")
    config_root = tmp_path / "settings"
    shutil.copytree(settings.ROOT / "config", config_root / "config")
    shutil.copytree(settings.ROOT / "protocol", config_root / "protocol")
    monkeypatch.setattr(settings, "ROOT", config_root)
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    original_iterdir = Path.iterdir
    monkeypatch.setattr(Path, "iterdir", lambda path: iter(()) if path == Path("/proc") else original_iterdir(path))
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: pytest.fail("settings preflight launched a process"))
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read the heading.", "start_url": "https://example.test/"}) + "\n")
    rubrics = tmp_path / "rubrics"
    write_json(rubrics / "custom.json", {"task_id": "custom", "criteria": [{"id": "heading", "description": "Report the heading."}]})
    output = tmp_path / "recordings"
    arguments = ["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gpt-6.1-sol", "--output-dir", str(output), "--run-name", "settings",
        "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    return SimpleNamespace(arguments=arguments, ledger=output / "settings/ledger.jsonl", catalog=catalog,
        rubric_dir=rubrics, config_root=config_root)
