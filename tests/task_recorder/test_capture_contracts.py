"""Offline browser transport, renderer and input delivery contracts."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from w8bench.task_recorder import browser_runtime, capture
from w8bench.task_recorder.agent_browser import AgentBrowserBaseError, AgentBrowserClient, AgentBrowserError
from w8bench.task_recorder.recorder_support import RunnerError
from w8bench.task_recorder.renderers import render_chromiumrl_model_dom as model_renderer
from w8bench.task_recorder.renderers import render_chromiumrl_snapshot_full as full_renderer
from w8bench.task_recorder.runtime import status as runtime_status
from w8bench.task_recorder.runtime import wait as runtime_wait


@pytest.mark.parametrize(
    "sections",
    [
        [],
        ["header"],
        [{"name": "content", "lines": ["Saved"]}],
        [{"name": "header", "lines": []}],
        [{"name": "header", "lines": [1]}],
        [{"name": "header", "lines": "URL"}],
        [{"name": "header", "lines": ["URL"], "unknown": True}],
        [{"name": "unknown", "lines": ["URL"]}],
        [{"name": "header", "lines": ["URL"]}, {"name": "header", "lines": ["Again"]}],
        [{"name": "header", "lines": ["URL"]}, {"name": "actions", "lines": ["Save"]},
         {"name": "tables", "lines": ["Table"]}],
    ],
)
def test_model_dom_rejects_ambiguous_or_malformed_sections(sections):
    with pytest.raises(model_renderer.ModelDOMRenderError):
        model_renderer.render_model_dom({"rendererName": "chromiumrl-model-dom", "sections": sections})


def test_model_dom_projection_preserves_browser_order_and_long_unicode_text(tmp_path):
    content = "Café " + "x" * 9000
    source, output = tmp_path / "source.json", tmp_path / "output.txt"
    source.write_text(json.dumps({"result": {"modelDOM": {
        "rendererName": "chromiumrl-model-dom",
        "sections": [{"name": "header", "lines": ["URL: https://example.test/", "Title: Example"]},
                     {"name": "content", "lines": [content, "Status: Saved"]}],
    }}}), encoding="utf-8")
    before = source.read_bytes()
    assert model_renderer.main([str(source), "--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == "URL: https://example.test/\nTitle: Example\n\n" + content + "\nStatus: Saved\n"
    assert source.read_bytes() == before


@pytest.mark.parametrize("payload", [[], {}, {"result": {}}, {"result": {"modelDOM": []}},
    {"result": {"modelDOM": {}}, "unknown": True}, {"result": {"modelDOM": {}, "unknown": True}}])
def test_model_dom_rejects_missing_or_ambiguous_capture_envelopes(payload):
    with pytest.raises(model_renderer.ModelDOMRenderError):
        model_renderer.model_dom_from_envelope(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_attempts", [0, 1, 2, 3])
async def test_populated_empty_dom_snapshots_have_a_bounded_read_retry(monkeypatch, empty_attempts):
    empty = {"snapshot": {"nodes": [], "stats": {"rawNodes": 5, "returnedNodes": 0}}}
    populated = {"snapshot": {"nodes": [{"ref": "1"}], "stats": {"rawNodes": 5, "returnedNodes": 1}}}
    call = AsyncMock(side_effect=[empty] * empty_attempts + [populated])
    monkeypatch.setattr(capture.asyncio, "sleep", AsyncMock())
    operation = capture.capture_structured_snapshot(SimpleNamespace(call=call), max_nodes=7000, max_text_chars=200000)
    if empty_attempts == 3:
        with pytest.raises(RunnerError, match="zero nodes.*after 3 attempts"):
            await operation
    else:
        assert await operation == populated["snapshot"]
    assert call.await_count == min(empty_attempts + 1, 3)
    assert all(entry.args == ("ChromiumRL.captureStructuredSnapshot", {
        "inViewportOnly": True, "maxNodes": 7000, "maxTextChars": 200000, "includeOffscreen": False,
    }) for entry in call.await_args_list)


@pytest.mark.asyncio
async def test_genuinely_empty_dom_snapshot_does_not_consume_retry_budget():
    empty = {"nodes": [], "stats": {"rawNodes": 0, "returnedNodes": 0}}
    call = AsyncMock(return_value={"snapshot": empty})
    assert await capture.capture_structured_snapshot(SimpleNamespace(call=call), max_nodes=1, max_text_chars=1) == empty
    assert call.await_count == 1


@pytest.mark.parametrize("envelope", ["bare", "snapshot", "result"])
def test_full_snapshot_cli_exposes_captured_facts_without_changing_source(tmp_path, envelope):
    snapshot = {
        "url": "https://example.test/",
        "roots": ["root"],
        "stats": {"rawNodes": 4, "returnedNodes": 4, "truncated": True},
        "nodes": [
            {"ref": "root", "tag": "main", "childRefs": ["wrapper"]},
            {"ref": "wrapper", "tag": "div", "parentRef": "root"},
            {"ref": "button", "tag": "button", "role": "button", "index": 3,
             "parentRef": "wrapper", "accessibleName": "Save café", "directText": "Save café",
             "actionTypes": ["click"], "visible": True, "inViewport": True,
             "bounds": {"x": 1, "y": 2, "width": 100, "height": 20},
             "states": [{"name": "disabled", "value": "false"}]},
            {"ref": "orphan", "tag": "p", "parentRef": "absent", "directText": "Saved"},
        ],
    }
    value = snapshot if envelope == "bare" else {"snapshot": snapshot} if envelope == "snapshot" else {"result": {"snapshot": snapshot}}
    source, output = tmp_path / "dom.json", tmp_path / "dom_full.txt"
    source.write_text(json.dumps(value), encoding="utf-8")
    before = source.read_bytes()
    assert full_renderer.main([str(source), "--output", str(output), "--include-action-index", "--include-child-refs"]) == 0
    text = output.read_text(encoding="utf-8")
    assert "rawNodes=4 returnedNodes=4 truncated=True" in text
    assert '[3] ref=button <button> role=button actions=click visible=true viewport=true' in text
    assert "name: Save café" in text and "direct_text: Save café" not in text
    assert "bounds=(x=1.0 y=2.0 width=100.0 height=20.0)" in text
    assert "states: disabled=false" in text and "child_refs: wrapper" in text
    assert "=== UNREACHED NODES ===" in text and "direct_text: Saved" in text
    assert "- ref=wrapper" not in text
    assert source.read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("mode, enabled", [("dom", True), ("screenshot", True), ("screenshot", False)])
async def test_cdp_connection_creates_a_fresh_page_and_establishes_capture_policy(monkeypatch, mode, enabled):
    client = capture.CDPClient("http://localhost:49335", observation_mode=mode,
        viewport=(1365, 768), browser_language="en-US", browser_accept_language="en-US,en;q=0.9")
    pages = [{"targetId": "stale", "type": "page", "url": "https://example.test/prior"},
             {"targetId": "devtools", "type": "page", "url": "devtools://inspector"}]
    events = []
    async def command(method, params=None, **kwargs):
        events.append((method, params))
        if method == "Target.getTargets":
            return {"targetInfos": list(pages)}
        if method == "Target.createTarget":
            pages.append({"targetId": "fresh", "type": "page", "url": "about:blank"})
            return {"targetId": "fresh"}
        if method == "Target.closeTarget":
            pages[:] = [page for page in pages if page["targetId"] != params["targetId"]]
            return {"success": True}
        if method == "Target.attachToTarget":
            return {"sessionId": "fixture-session"}
        if method == "ChromiumRL.enable" and not enabled:
            raise capture.CDPError(method, {"code": -32601, "message": "not available"})
        return {}
    monkeypatch.setattr(client, "_open_browser_transport", AsyncMock())
    monkeypatch.setattr(client, "call", command)
    monkeypatch.setattr(capture.asyncio, "sleep", AsyncMock())
    await client.connect()
    assert [page["targetId"] for page in pages] == ["devtools", "fresh"]
    assert client.target["targetId"] == "fresh"
    assert ("Target.createTarget", {"url": "about:blank"}) in events
    assert ("Target.closeTarget", {"targetId": "devtools"}) not in events
    assert ("Emulation.setDeviceMetricsOverride", {"width": 1365, "height": 768,
        "deviceScaleFactor": 1, "mobile": False}) in events
    assert ("Network.setExtraHTTPHeaders", {"headers": {"Accept-Language": "en-US,en;q=0.9"}}) in events
    assert client.connection_report["locale_setup"]["locale_override"]["status"] == "ok"
    assert bool(client.capture_setup_errors) is not enabled


@pytest.mark.asyncio
async def test_dom_connection_refuses_unavailable_active_capture(monkeypatch):
    client = capture.CDPClient("http://localhost:49335", observation_mode="dom", keep_existing_tabs=True)
    events = []
    async def command(method, params=None, **kwargs):
        events.append(method)
        if method == "Target.getTargets":
            return {"targetInfos": [{"targetId": "one", "type": "page", "url": "https://example.test"}]}
        if method == "Target.attachToTarget":
            return {"sessionId": "one"}
        if method == "ChromiumRL.enable":
            raise capture.CDPError(method, {"message": "unavailable"})
        return {}
    monkeypatch.setattr(client, "_open_browser_transport", AsyncMock())
    monkeypatch.setattr(client, "call", command)
    with pytest.raises(capture.CDPError):
        await client.connect()
    assert "Emulation.setDeviceMetricsOverride" not in events


@pytest.mark.asyncio
@pytest.mark.parametrize("action, expected", [
    ({"action": "navigate", "url": "https://example.test/next"},
     [("Page.navigate", {"url": "https://example.test/next"})]),
    ({"action": "back"}, [("Page.getNavigationHistory", None), ("Page.navigateToHistoryEntry", {"entryId": 10})]),
    ({"action": "type", "text": "café"}, [("Input.insertText", {"text": "café"})]),
    ({"action": "press", "key": "Control+Shift+A"}, [
        ("Input.dispatchKeyEvent", {"type": "keyDown", "key": "A", "windowsVirtualKeyCode": 65, "modifiers": 10}),
        ("Input.dispatchKeyEvent", {"type": "keyUp", "key": "A", "windowsVirtualKeyCode": 65, "modifiers": 10})]),
    ({"action": "press", "key": "Enter"}, [
        ("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "windowsVirtualKeyCode": 13, "modifiers": 0, "text": "\r"}),
        ("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "windowsVirtualKeyCode": 13, "modifiers": 0})]),
])
async def test_shared_browser_inputs_use_cdp_and_confirm_delivery(action, expected):
    client = AgentBrowserClient("fixture", session="one", cdp_url="http://localhost:9222", timeout=1)
    events = []
    async def command(method, params=None):
        events.append((method, params))
        return {"currentIndex": 1, "entries": [{"id": 10}, {"id": 20}]} if method == "Page.getNavigationHistory" else {}
    result = await client.execute(action, cdp=SimpleNamespace(call=command))
    assert events == expected
    assert result == {"success": True, "status": "input_dispatched"}


@pytest.mark.asyncio
@pytest.mark.parametrize("action, error", [
    ({"action": "navigate", "url": "https://example.test/next"}, "net::ERR_NAME_NOT_RESOLVED"),
    ({"action": "back"}, "no previous navigation entry"),
    ({"action": "press", "key": "Unknown+A"}, "unsupported key modifier"),
    ({"action": "press", "key": "F999"}, "unsupported key"),
])
async def test_input_failure_never_claims_delivery(action, error):
    client = AgentBrowserClient("fixture", session="one", cdp_url="http://localhost:9222", timeout=1)
    cdp = SimpleNamespace(call=AsyncMock(return_value={"errorText": "net::ERR_NAME_NOT_RESOLVED", "currentIndex": 0, "entries": [{"id": 10}]}))
    with pytest.raises(AgentBrowserBaseError, match=error):
        await client.execute(action, cdp=cdp)
    assert not any(call.args[0].startswith("Input.") for call in cdp.call.await_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("returncode, stdout, stderr, success", [
    (0, '{"success":true,"data":{}}', "", True),
    (0, '{"success":false,"error":"target unavailable"}', "", False),
    (0, '{"success":false,"error":{"message":"target unavailable"}}', "", False),
    (0, "invalid json", "", False),
    (0, "[]", "", False),
    (1, "", "driver unavailable", False),
])
async def test_reference_action_respects_cli_exit_and_json_delivery_contract(
    monkeypatch, returncode, stdout, stderr, success
):
    commands = []
    def command(argv, **kwargs):
        commands.append(argv)
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    from w8bench.task_recorder.agent_browser import client as adapter
    monkeypatch.setattr(adapter.subprocess, "run", command)
    monkeypatch.setattr(adapter.asyncio, "to_thread", inline)
    driver = AgentBrowserClient("fixture-driver", session="one", cdp_url="http://localhost:9222", timeout=1)
    operation = driver.execute({"action": "click", "id": "e1"}, cdp=None)
    if success:
        assert await operation == {"success": True, "data": {}}
    else:
        with pytest.raises(AgentBrowserError):
            await operation
    assert commands == [["fixture-driver", "--session", "one", "click", "@e1", "--json"]]


@pytest.mark.parametrize("failure", [None, "container", "stopped", "health", "novnc", "driver"])
def test_runtime_status_checks_each_service_without_launching_a_browser(
    runtime_configuration, monkeypatch, capsys, failure
):
    commands, urls = [], []
    def command(argv):
        commands.append(argv)
        if argv[:2] == ["docker", "inspect"]:
            return SimpleNamespace(returncode=int(failure == "container"), stdout=json.dumps([{
                "State": {"Running": failure != "stopped", "Health": {"Status": "starting" if failure == "health" else "healthy"}}
            }]), stderr="")
        return SimpleNamespace(returncode=int(failure == "driver"), stdout="agent-browser 0.27.3", stderr="driver unavailable")
    monkeypatch.setattr(browser_runtime, "run", command)
    monkeypatch.setattr(browser_runtime, "get_json", lambda url: urls.append(url) or {"Browser": "Fixture Chromium"})
    monkeypatch.setattr(browser_runtime, "get_page", lambda url: urls.append(url) or (503 if failure == "novnc" else 200))
    code = browser_runtime.main(["--env-file", str(runtime_configuration), "status"])
    assert code == int(failure is not None)
    output = capsys.readouterr()
    assert bool(output.err) is (failure is not None)
    assert all(argv[:2] in [["docker", "inspect"], ["docker", "exec"]] for argv in commands)
    if failure in {None, "driver"}:
        assert commands[-1] == ["docker", "exec", "fixture-browser", "agent-browser", "--version"]
        assert urls[0] == "http://127.0.0.1:49335/json/version"
        assert urls[1].startswith("http://127.0.0.1:16191/vnc.html?")


@pytest.mark.parametrize("port", ["0", "65536", "not-a-port"])
def test_runtime_refuses_invalid_ports_before_container_access(runtime_configuration, monkeypatch, port):
    runtime_configuration.write_text(f"CONTAINER_NAME=fixture\nCDP_HOST_PORT={port}\nNOVNC_HOST_PORT=16191\n")
    monkeypatch.setattr(browser_runtime, "run", lambda command: pytest.fail("invalid port reached Docker"))
    assert browser_runtime.main(["--env-file", str(runtime_configuration), "status"]) == 1


@pytest.mark.parametrize("occupied", [False, True])
def test_runtime_configuration_uses_project_defaults_and_distinct_available_ports(tmp_path, monkeypatch, occupied):
    monkeypatch.setattr(browser_runtime, "runtime_identity", lambda: "fixture")
    monkeypatch.setattr(browser_runtime, "port_is_available", lambda port: not occupied or port != 49335)
    monkeypatch.setattr(browser_runtime, "docker_container_exists", lambda name: name in {
        "w8-core-browser-fixture", "w8-core-browser-fixture-2",
    })
    class Listener:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def bind(self, address):
            assert address == ("127.0.0.1", 0)
        def getsockname(self):
            return ("127.0.0.1", 49100)
    monkeypatch.setattr(browser_runtime.socket, "socket", lambda *args: Listener())
    path = tmp_path / "runtime.env"
    assert browser_runtime.configure(path, False) == 0
    values = browser_runtime.read_env(path)
    assert values["IMAGE"] == "w8-core:domdiff-bench"
    assert values["COMPOSE_PROJECT_NAME"] == "w8-recorder-fixture"
    assert values["CONTAINER_NAME"] == "w8-core-browser-fixture-3"
    assert [values[name] for name in ("CDP_HOST_PORT", "NOVNC_HOST_PORT", "VNC_HOST_PORT")] == [
        "49100" if occupied else "49335", "16191", "15911",
    ]
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("code, body, healthy", [
    (200, b'{"Browser":"Fixture Chromium","Protocol-Version":"1.3"}', True),
    (503, b"not ready", False),
    (200, b"not json", False),
    (200, b"[]", False),
])
def test_container_healthcheck_reports_cdp_errors_and_closes_transport(monkeypatch, capsys, code, body, healthy):
    calls = []
    class Connection:
        def __init__(self, host, port, timeout):
            calls.append((host, port, timeout))
        def request(self, method, path):
            calls.append((method, path))
        def getresponse(self):
            return SimpleNamespace(status=code, read=lambda: body)
        def close(self):
            calls.append("closed")
    monkeypatch.setattr(runtime_status.http.client, "HTTPConnection", Connection)
    monkeypatch.setenv("CDP_PROBE_HOST", "fixture-browser")
    monkeypatch.setenv("CDP_PORT", "9222")
    monkeypatch.setenv("CHROMIUM_HEADLESS", "1")
    monkeypatch.setattr(runtime_status.sys, "argv", ["status.py", "--timeout", "0.5"])
    assert runtime_status.main() == int(not healthy)
    report = json.loads(capsys.readouterr().out)
    assert report["cdp_ready"] is healthy and report["novnc_url"] is None
    assert calls == [("fixture-browser", 9222, 0.5), ("GET", "/json/version"), "closed"]
    if healthy:
        assert report["browser"] == "Fixture Chromium"
    else:
        assert report["error"]


@pytest.mark.parametrize("ready", [True, False])
def test_container_wait_stops_on_readiness_or_its_deadline(monkeypatch, ready):
    times = iter([0, 0.1, 0.2, 0.3, 1.1])
    monkeypatch.setattr(runtime_wait.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(runtime_wait.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(runtime_wait.sys, "argv", ["wait.py", "--timeout", "1"])
    checks = []
    def check(command, **kwargs):
        checks.append(command)
        return SimpleNamespace(returncode=0 if ready and len(checks) >= 2 else 1)
    monkeypatch.setattr(runtime_wait.subprocess, "run", check)
    assert runtime_wait.main() == int(not ready)
    assert checks[-1] == ["python3", "/opt/chromium-runtime/status.py"]
    assert all(command[-3:] == ["--quiet", "--timeout", "2"] for command in checks[:-1])
    assert len(checks) == (3 if ready else 4)
