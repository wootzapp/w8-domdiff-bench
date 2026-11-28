"""Browser input, paired capture, runtime readiness and evidence rendering."""
import asyncio
import ast
import base64
import io
import json
import os
import statistics
import subprocess
import time
from pathlib import Path

from w8bench.run_paths import run_directory
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from tests.conftest import FakeCDP
from w8bench.task_recorder import browser_runtime, capture, runner, task_cli
from w8bench.task_recorder.agent_browser import AgentBrowserBaseError, AgentBrowserClient
from w8bench.task_recorder.agent_browser.client import AgentBrowserError
from w8bench.task_recorder.recorder_support import RunnerError, write_json
from w8bench.task_recorder.renderers import render_chromiumrl_model_dom as model_renderer
from w8bench.task_recorder.renderers import render_chromiumrl_snapshot_full as full_renderer
from w8bench.task_recorder.renderers.render_chromiumrl_snapshot_full import FullSnapshotRenderer
from w8bench.task_recorder.runtime import status, wait

runtime_status = container_status = status
runtime_wait = wait
OPTIONS = {"max_text_chars": 1200, "text_mode": "deduped", "include_suppressed_text_notes": False,
    "include_action_index": True, "include_child_refs": True, "include_text_nodes": False,
    "include_inert_wrappers": False, "include_diff": False}

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
@pytest.mark.parametrize("raw_nodes", [0, 5, 7000])
async def test_empty_dom_export_is_accepted_without_retry(monkeypatch, raw_nodes):
    empty = {"nodes": [], "stats": {"rawNodes": raw_nodes, "returnedNodes": 0}}
    call = AsyncMock(return_value={"snapshot": empty})
    sleep = AsyncMock()
    monkeypatch.setattr(capture.asyncio, "sleep", sleep)
    assert await capture.capture_structured_snapshot(SimpleNamespace(call=call),
        max_nodes=7000, max_text_chars=200000) == empty
    assert call.await_count == 1
    sleep.assert_not_awaited()

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
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "main-frame"}}}
        if method == "Page.createIsolatedWorld":
            return {"executionContextId": 42}
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
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "main-frame"}}}
        if method == "Page.createIsolatedWorld":
            return {"executionContextId": 42}
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
    class Process:
        def __init__(self): self.returncode = returncode
        def communicate(self, **kwargs): return stdout, stderr
    def command(argv, **kwargs):
        commands.append(argv)
        return Process()
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    from w8bench.task_recorder.agent_browser import client as adapter
    monkeypatch.setattr(adapter.subprocess, "Popen", command)
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
    monkeypatch.setattr(browser_runtime, "get_json", lambda url: urls.append(url) or {
        "Browser": "Fixture Chromium", "domains": [{"domain": "ChromiumRL", "commands": [
            {"name": name} for name in ("enable", "captureStructuredSnapshot", "getModelDOM")]}]})
    monkeypatch.setattr(browser_runtime, "get_page", lambda url: urls.append(url) or (503 if failure == "novnc" else 200))
    code = browser_runtime.main(["--env-file", str(runtime_configuration), "status"])
    assert code == int(failure is not None)
    output = capsys.readouterr()
    assert bool(output.err) is (failure is not None)
    assert all(argv[:2] in [["docker", "inspect"], ["docker", "exec"]] for argv in commands)
    if failure in {None, "driver"}:
        assert commands[-1] == ["docker", "exec", "fixture-browser", "agent-browser", "--version"]
        assert urls[0] == "http://127.0.0.1:49335/json/version"
        assert urls[1] == "http://127.0.0.1:49335/json/protocol"
        assert urls[2].startswith("http://127.0.0.1:16191/vnc.html?")

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
    assert "EVIDENCE_AUDIT_PROVIDER" not in values
    assert "EVIDENCE_ADJUDICATOR_PROVIDER" not in values
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
            self.path = path
            calls.append((method, path))
        def getresponse(self):
            payload = json.dumps({"domains": [{"domain": "ChromiumRL", "commands": [
                {"name": name} for name in ("enable", "captureStructuredSnapshot", "getModelDOM")]}]}).encode()
            return SimpleNamespace(status=code, read=lambda: payload if self.path == "/json/protocol" else body)
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
    expected = [("fixture-browser", 9222, 0.5), ("GET", "/json/version"), "closed"]
    if healthy:
        expected += [("fixture-browser", 9222, 0.5), ("GET", "/json/protocol"), "closed"]
    assert calls == expected
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

def test_snapshot_chain_below_capture_node_limit_renders_every_node():
    nodes = [{"ref": str(index), "tag": "section", "directText": f"Node {index}",
        **({"parentRef": str(index - 1)} if index else {})} for index in range(1100)]
    text = FullSnapshotRenderer({"nodes": nodes, "roots": ["0"]}, **OPTIONS).render()
    assert text.count("- ref=") == 1100
    assert "direct_text: Node 1099" in text
    assert text.index("direct_text: Node 0") < text.index("direct_text: Node 1099")

def test_cycle_and_repeated_roots_keep_the_original_depth_first_text():
    snapshot = {"roots": ["a", "b"], "nodes": [
        {"ref": "a", "parentRef": "b", "tag": "section", "sourceOrder": 0},
        {"ref": "b", "parentRef": "a", "tag": "section", "sourceOrder": 1},
    ]}
    expected = ["=== NODE TREE ===",
        "- ref=a <section> visible=? viewport=? hit=? occluded=? scroll=?",
        "  - ref=b <section> visible=? viewport=? hit=? occluded=? scroll=?",
        "    - ref=a [already shown]", "- ref=b [already shown]"]
    assert FullSnapshotRenderer(snapshot, **OPTIONS).render_tree() == expected

def test_wrapper_collapse_keeps_child_source_order_and_depth():
    snapshot = {"roots": ["root"], "nodes": [
        {"ref": "root", "tag": "div"},
        {"ref": "later", "parentRef": "root", "tag": "button", "sourceOrder": 2, "directText": "Second"},
        {"ref": "first", "parentRef": "root", "tag": "button", "sourceOrder": 1, "directText": "First"},
    ]}
    assert FullSnapshotRenderer(snapshot, **OPTIONS).render_tree() == ["=== NODE TREE ===",
        "- ref=first <button> visible=? viewport=? hit=? occluded=? scroll=?", "  direct_text: First",
        "- ref=later <button> visible=? viewport=? hit=? occluded=? scroll=?", "  direct_text: Second"]

@pytest.mark.parametrize("headless", ["1", "true", "TRUE", "yes", "YES", "on", "ON"])
def test_headless_status_needs_no_novnc_port_or_service(tmp_path, monkeypatch, headless):
    env = tmp_path / "browser.env"
    env.write_text("CONTAINER_NAME=fixture\nCDP_HOST_PORT=49335\nCHROMIUM_HEADLESS=0\n")
    commands = []
    def command(argv):
        commands.append(argv)
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps([{
            "State": {"Running": True, "Health": {"Status": "healthy"}},
            "Config": {"Env": [f"CHROMIUM_HEADLESS={headless}"]},
        }]) if argv[1] == "inspect" else "agent-browser fixture")
    monkeypatch.setattr(browser_runtime, "run", command)
    monkeypatch.setattr(browser_runtime, "get_json", lambda url: {
        "Browser": "Fixture Chromium", "domains": [{"domain": "ChromiumRL", "commands": [
            {"name": name} for name in ("enable", "captureStructuredSnapshot", "getModelDOM")]}]})
    monkeypatch.setattr(browser_runtime, "get_page", lambda url: pytest.fail("headless mode has no noVNC service"))
    assert browser_runtime.main(["--env-file", str(env), "status"]) == 0
    assert commands[-1] == ["docker", "exec", "fixture", "agent-browser", "--version"]

def test_inspected_headed_mode_requires_novnc_despite_host_override(runtime_configuration, monkeypatch):
    monkeypatch.setenv("CHROMIUM_HEADLESS", "1")
    def command(argv):
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps([{
            "State": {"Running": True}, "Config": {"Env": ["CHROMIUM_HEADLESS=0"]},
        }]) if argv[1] == "inspect" else "agent-browser fixture")
    checked = []
    monkeypatch.setattr(browser_runtime, "run", command)
    monkeypatch.setattr(browser_runtime, "get_json", lambda url: {
        "domains": [{"domain": "ChromiumRL", "commands": [
            {"name": name} for name in ("enable", "captureStructuredSnapshot", "getModelDOM")]}]})
    monkeypatch.setattr(browser_runtime, "get_page", lambda url: checked.append(url) or 503)
    assert browser_runtime.main(["--env-file", str(runtime_configuration), "status"]) == 1
    assert len(checked) == 1

@pytest.mark.parametrize("headless", ["1", "true", "TRUE", "yes", "YES", "on", "ON"])
def test_container_status_reports_disabled_display_without_a_novnc_url(monkeypatch, capsys, headless):
    monkeypatch.setenv("CHROMIUM_HEADLESS", headless)
    monkeypatch.setattr(container_status.sys, "argv", ["status.py"])
    monkeypatch.setattr(container_status, "request_version", lambda timeout: {"Browser": "Fixture Chromium"})
    assert container_status.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["headless"] == headless and report["novnc_url"] is None

@pytest.mark.parametrize("option", ["--settle-seconds", "--agent-browser-timeout"])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-0.1", "not-a-number"])
def test_recorder_timing_options_fail_during_argument_parsing(tmp_path, capsys, option, value):
    with pytest.raises(SystemExit) as caught:
        runner.parse_args(["--env-file", str(tmp_path / "absent.env"), f"{option}={value}"])
    assert caught.value.code == 2
    assert option in capsys.readouterr().err

@pytest.mark.parametrize("key", ["STEP_SETTLE_SECONDS", "AGENT_BROWSER_TIMEOUT"])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-1", "not-a-number"])
def test_recorder_environment_timing_defaults_have_the_same_validation(tmp_path, monkeypatch, capsys, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(SystemExit) as caught:
        runner.parse_args(["--env-file", str(tmp_path / "absent.env")])
    assert caught.value.code == 2
    assert "error:" in capsys.readouterr().err

@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-1", "0"])
def test_launcher_stop_timeout_is_finite_and_strictly_positive(tmp_path, capsys, value):
    with pytest.raises(SystemExit) as caught:
        task_cli.parse_args(["--output-dir", str(tmp_path), f"--previous-run-stop-timeout={value}"])
    assert caught.value.code == 2
    assert "--previous-run-stop-timeout" in capsys.readouterr().err

@pytest.mark.parametrize("module", [status, wait])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-1", "0"])
def test_container_timeout_is_rejected_before_transport_or_subprocess(monkeypatch, capsys, module, value):
    monkeypatch.setattr(module.sys, "argv", ["runtime", f"--timeout={value}"])
    if module is status:
        monkeypatch.setattr(module, "request_version", lambda *args: pytest.fail("invalid timeout reached CDP"))
    else:
        monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: pytest.fail("invalid timeout started a check"))
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
    assert "--timeout" in capsys.readouterr().err

def test_zero_settle_delay_and_small_positive_timeouts_are_valid(tmp_path):
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--settle-seconds=0", "--agent-browser-timeout=0.001"])
    assert args.settle_seconds == 0 and args.agent_browser_timeout == 0.001
    args = task_cli.parse_args(["--output-dir", str(tmp_path), "--previous-run-stop-timeout=0.001"])
    assert args.previous_run_stop_timeout == 0.001

def test_zero_action_driver_timeout_is_rejected(tmp_path):
    with pytest.raises(SystemExit) as caught:
        runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--agent-browser-timeout=0"])
    assert caught.value.code == 2

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
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(runner.ModelClient, "_post", lambda *args: pytest.fail("capture failure dispatched an actor request"))
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", "screenshot",
        "--task", "Read the heading.", "--start-url", "https://example.test/", "--task-id", "failure",
        "--output-dir", str(tmp_path / "recordings"), "--api-key", "offline", "--settle-seconds", "0"])
    assert await runner.run(args) == 2
    final = json.loads((tmp_path / "recordings/failure/final.json").read_text())
    assert final["run_status"] == "technical_failure" and final["model_turns"] == 0
    assert "CDP websocket closed" in final["error"]
    assert socket.closed and http.close.await_count == 1

@pytest.mark.usefixtures("no_network")
def test_action_snapshot_filters_viewport_and_preserves_executable_refs(monkeypatch):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    names = ["Visible", "Below", "Right", "Above", "Left", "Partial", "Zero", "Duplicate", "Duplicate"]
    refs = {f"e{i}": {"role": "button", "name": name} for i, name in enumerate(names, 1)}
    text = "- heading Offscreen context\n" + "\n".join(
        f'- button "{target["name"]}" [ref={ref}]' for ref, target in refs.items())
    boxes = [(10, 10, 30, 20), (10, 768, 30, 20), (1365, 10, 30, 20),
        (10, -20, 30, 20), (-30, 10, 30, 20), (10, 760, 30, 20),
        (10, 10, 0, 20), (10, 1500, 30, 20), (100, 100, 30, 20)]
    async def invoke(arguments, **kwargs):
        if arguments[0] == "snapshot":
            return {"data": {"snapshot": text, "refs": refs, "origin": "fixture"}}
        assert arguments[0] == "batch"
        assert arguments[2:] == [f"get box @{ref}" for ref in refs]
        return [{"success": True, "result": {"result": {"width": 1365, "height": 768}}},
            *({"success": True, "result": dict(zip(("x", "y", "width", "height"), box))} for box in boxes)]
    monkeypatch.setattr(driver, "_invoke", invoke)
    observation = asyncio.run(driver.snapshot())
    assert observation.refs == {"e1", "e6", "e9"}
    assert set(observation.targets) == observation.refs
    assert observation.text.splitlines() == [text.splitlines()[i] for i in (1, 6, 9)]
    assert "Offscreen context" not in observation.text
    assert runner.action_rejection_reason({"action": "click", "id": "e8", "thought": "click"}, observation.refs, [])
    assert not runner.action_rejection_reason({"action": "click", "id": "e9", "thought": "click"}, observation.refs, [])

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("geometry", [None, {"x": 0, "y": 0, "width": float("nan"), "height": 20}])
def test_action_snapshot_fails_closed_when_geometry_is_unavailable(monkeypatch, geometry):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    invoke = AsyncMock(side_effect=[
        {"data": {"snapshot": '- button "Hidden" [ref=e1]', "refs": {"e1": {"role": "button", "name": "Hidden"}}}},
        [{"success": True, "result": {"result": {"width": 1365, "height": 768}}},
         {"success": geometry is not None, "result": geometry}]])
    monkeypatch.setattr(driver, "_invoke", invoke)
    with pytest.raises(AgentBrowserError, match="viewport geometry"):
        asyncio.run(driver.snapshot())

@pytest.mark.usefixtures("no_network")
def test_empty_action_snapshot_never_falls_back_to_full_page(monkeypatch):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    invoke = AsyncMock(return_value={"data": {"snapshot": "- heading Full page secret", "refs": {}}})
    monkeypatch.setattr(driver, "_invoke", invoke)
    observation = asyncio.run(driver.snapshot())
    assert not observation.refs and not observation.targets
    assert "Full page secret" not in observation.text
    bundle = capture.CaptureBundle(snapshot_path=Path("dom.json"))
    assert bundle.agent_browser_action_text == ""

@pytest.mark.usefixtures("no_network")
def test_action_snapshot_clips_frame_local_targets_to_frame_and_viewport(monkeypatch):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    refs = {"e1": {"role": "Iframe"}, "e2": {"role": "button", "name": "Hidden frame child"},
        "e3": {"role": "Iframe"}, "e4": {"role": "button", "name": "Visible frame child"},
        "e5": {"role": "button", "name": "Outside frame"}}
    text = '- Iframe [ref=e1]\n  - button "Hidden frame child" [ref=e2]\n- Iframe [ref=e3]\n  - button "Visible frame child" [ref=e4]\n  - button "Outside frame" [ref=e5]'
    boxes = [(10, 1200, 200, 100), (8, 8, 30, 20), (400, 50, 200, 100),
        (8, 8, 30, 20), (8, 200, 30, 20)]
    invoke = AsyncMock(side_effect=[{"data": {"snapshot": text, "refs": refs}},
        [{"success": True, "result": {"result": {"width": 1365, "height": 768}}},
         *({"success": True, "result": dict(zip(("x", "y", "width", "height"), box))} for box in boxes)]])
    monkeypatch.setattr(driver, "_invoke", invoke)
    observation = asyncio.run(driver.snapshot())
    assert observation.refs == {"e3", "e4"}
    assert "Hidden frame child" not in observation.text and "Outside frame" not in observation.text

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("changed_field", [None, "container_id", "source_directory", "target_directory", "compose_project", "service"])
def test_checkout_relocation_receipt_is_bound_to_exact_browser(tmp_path, monkeypatch, changed_field):
    from types import SimpleNamespace
    root = tmp_path / "renamed-checkout"
    runtime = root / ".runtime"
    runtime.mkdir(parents=True)
    source = str(tmp_path / "previous-checkout")
    receipt = {"container_id": "owned-id", "source_directory": source,
        "target_directory": str(root), "compose_project": "owned-project", "service": "w8-core"}
    if changed_field is not None:
        receipt[changed_field] = "mismatch"
    path = runtime / "browser-relocation.json"
    write_json(path, receipt)
    monkeypatch.setattr(task_cli, "ROOT", root)
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", runtime)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if "config" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"name": "owned-project",
                "services": {"w8-core": {"container_name": "owned-browser"}}}), stderr="")
        if command[1:3] == ["ps", "-aq"]:
            return SimpleNamespace(returncode=0, stdout="owned-id\n", stderr="")
        if command[1] == "inspect":
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"Id": "owned-id", "Config": {"Labels": {
                "com.docker.compose.project.working_dir": source,
                "com.docker.compose.project": "owned-project", "com.docker.compose.service": "w8-core"}}}]), stderr="")
        assert "up" in command and changed_field is None
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(task_cli.subprocess, "run", run)
    if changed_field is None:
        task_cli.restart_browser_service(root / ".env")
        assert not path.exists()
        assert sum("up" in command for command in calls) == 1
    else:
        with pytest.raises(RunnerError, match="another checkout"):
            task_cli.restart_browser_service(root / ".env")
        assert path.exists()
        assert not any("up" in command for command in calls)

@pytest.mark.usefixtures("no_network")
def test_passive_capture_failure_never_enters_actor_or_progress(run_pair, tmp_path, monkeypatch):
    original = FakeCDP.call
    async def call(self, method, params=None, **kwargs):
        if method == "ChromiumRL.captureStructuredSnapshot":
            raise RunnerError("PASSIVE_DOM_ERROR_SECRET")
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeCDP, "call", call)
    client = FakeCDP(observation_mode="screenshot")
    before = asyncio.run(capture.capture_bundle(client, tmp_path/"one", max_nodes=100, max_text_chars=1000,
        observation_mode="screenshot"))
    after = asyncio.run(capture.capture_bundle(client, tmp_path/"two", max_nodes=100, max_text_chars=1000,
        observation_mode="screenshot"))
    assert before.capture_metadata["paired_complete"] is False
    assert "PASSIVE_DOM_ERROR_SECRET" in json.dumps(before.capture_metadata)
    assert set(capture.action_progress(before, after)) == {"url_changed", "observation_changed", "task_progress", "screenshot_changed"}
    seen = []
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self,payload: seen.append(payload) or
        {"model": "gemini-3.8-flash", "output_text": '{"action":"wait","seconds":0,"thought":"observe"}'})
    asyncio.run(runner.ModelClient("unused", "gemini-3.8-flash", "unused").decide(task="Inspect page", step=1,
        max_steps=5, bundle=before, task_memory="", recent_actions=[], turn_dir=tmp_path,
        viewport=(1365,768)))
    assert "PASSIVE_DOM_ERROR_SECRET" not in json.dumps(seen)
    assert "DOM_ONLY_SECRET" not in json.dumps(seen)

@pytest.mark.usefixtures("no_network")
@pytest.mark.live_browser
@pytest.mark.skipif(not os.environ.get("W8_CAPTURE_TEST_CDP"), reason="requires the isolated browser")
def test_live_capture_preserves_scroll_and_focus(tmp_path):
    runner.load_env(Path(".env"))
    args = runner.parse_args(["--observation-mode", "dom", "--capture-only"])
    async def check():
        async with capture.CDPClient(os.environ["W8_CAPTURE_TEST_CDP"], viewport=(1365,768)) as cdp:
            await cdp.call("Runtime.evaluate", {"expression":
                "document.body.innerHTML='<input id=focusme style=position:fixed><div style=height:5000px>capture fixture</div>';"
                "document.getElementById('focusme').focus();window.scrollTo(0,400)"})
            before = await cdp.call("Runtime.evaluate", {"expression":
                "JSON.stringify([scrollX,scrollY,document.activeElement.id])", "returnByValue": True})
            for mode in ("dom", "screenshot"):
                bundle = await capture.capture_bundle(cdp, tmp_path/mode/"steps"/"step_001", max_nodes=7000,
                    max_text_chars=200000, observation_mode=mode)
                if mode == "dom":
                    driver = AgentBrowserClient(args.agent_browser_command, session="w8-domdiff-bench-test",
                        cdp_url=args.agent_browser_cdp_url, timeout=args.agent_browser_timeout)
                    await driver.connect()
                    try:
                        await capture.synchronize_recorder_target(cdp, driver)
                        page = await driver.active_page(cdp)
                        assert page.target_id == cdp.target["targetId"]
                        main = await cdp.call("Runtime.evaluate", {"expression":
                            "typeof globalThis.__w8_recorder_target_identity__", "returnByValue": True})
                        assert main["result"]["value"] == "undefined"
                        await cdp.call("Runtime.evaluate", {"expression":
                            "globalThis.__w8_recorder_target_identity__='page-forgery'"})
                        frame = (await cdp.call("Page.getFrameTree"))["frameTree"]["frame"]["id"]
                        world = await cdp.call("Page.createIsolatedWorld", {"frameId": frame,
                            "worldName": capture.TARGET_IDENTITY_WORLD, "grantUniveralAccess": False})
                        private = await cdp.call("Runtime.evaluate", {"expression":
                            "globalThis.__w8_recorder_target_identity__", "contextId": world["executionContextId"],
                            "returnByValue": True})
                        assert private["result"]["value"] == page.identity_marker
                        assert (await driver.active_page(cdp)).target_id == page.target_id
                        bundle = await capture.capture_bundle(cdp, tmp_path/mode/"joint"/"step_001", max_nodes=7000,
                            max_text_chars=200000, observation_mode=mode, agent_browser=driver)
                    finally:
                        await driver.close()
                assert bundle.capture_metadata["paired_complete"]
                after = await cdp.call("Runtime.evaluate", {"expression":
                    "JSON.stringify([scrollX,scrollY,document.activeElement.id])", "returnByValue": True})
                assert before["result"]["value"] == after["result"]["value"]
                if os.environ.get("W8_CAPTURE_REPORT_DIR"):
                    report_dir = Path(os.environ["W8_CAPTURE_REPORT_DIR"])
                    report_dir.mkdir(parents=True, exist_ok=True)
                    write_json(report_dir / f"browser_{mode}_state.json", {
                        "source": "live browser fixture; zero actor or judge model calls",
                        "manifest_state": runner.state_manifest_record(1,bundle,tmp_path/mode),
                        "scroll_focus_before":json.loads(before["result"]["value"]),
                        "scroll_focus_after":json.loads(after["result"]["value"])})
            if os.environ.get("W8_CAPTURE_REPORT_DIR"):
                # Reuse the protected baseline's existing capture functions only in this test.
                # This measures capture-core overhead; refs, actors, network pages and grading are excluded.
                baseline = subprocess.check_output(["git","show",
                    "69df83ee:w8bench/task_recorder/capture.py"],text=True)
                tree = ast.parse(baseline)
                selected = ast.Module(body=[node for node in tree.body if isinstance(node,ast.AsyncFunctionDef)
                    and node.name in {"materialize_bundle","capture_bundle"}],type_ignores=[])
                namespace = dict(vars(capture))
                exec(compile(selected,"protected-baseline-capture","exec"),namespace)
                measurements = []
                for mode in ("dom","screenshot"):
                    for sample in range(5):
                        variants = ["before","paired"] if sample%2==0 else ["paired","before"]
                        for variant in variants:
                            started = time.perf_counter()
                            bundle = await (namespace["capture_bundle"] if variant=="before" else capture.capture_bundle)(
                                cdp,tmp_path/"timings"/f"{mode}_{sample}_{variant}",max_nodes=7000,
                                max_text_chars=200000,observation_mode=mode)
                            measurements.append({"arm":mode,"sample":sample,"variant":variant,
                                "duration_seconds":time.perf_counter()-started,
                                "capture":bundle.capture_metadata if variant=="paired" else None})
                summary = {}
                for mode in ("dom","screenshot"):
                    means = {variant:statistics.mean(row["duration_seconds"] for row in measurements
                        if row["arm"]==mode and row["variant"]==variant) for variant in ("before","paired")}
                    summary[mode] = {**means,"added_seconds":means["paired"]-means["before"]}
                write_json(Path(os.environ["W8_CAPTURE_REPORT_DIR"])/"capture_timings.json",{
                    "source":"live static fixture; no model calls", "baseline_commit":"69df83ee",
                    "scope":"capture core only; excludes executable refs, actor API, settle, navigation and grading",
                    "samples_per_arm_variant":5,"summary":summary,"per_state":measurements})

    asyncio.run(check())

@pytest.mark.usefixtures("no_network")
def test_passive_screenshot_failure_does_not_change_dom_actor_or_progress(run_pair, tmp_path, monkeypatch):
    original = FakeCDP.call
    async def call(self, method, params=None, **kwargs):
        if method == "Page.captureScreenshot":
            raise RunnerError("PASSIVE_SCREENSHOT_ERROR_SECRET")
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeCDP, "call", call)
    client = FakeCDP(observation_mode="dom")
    before = asyncio.run(capture.capture_bundle(client, tmp_path / "before", max_nodes=100,
        max_text_chars=1000, observation_mode="dom"))
    after = asyncio.run(capture.capture_bundle(client, tmp_path / "after", max_nodes=100,
        max_text_chars=1000, observation_mode="dom"))
    assert before.capture_metadata["paired_complete"] is False
    assert before.snapshot_path.is_file() and (before.directory / "dom_model.txt").is_file()
    assert before.screenshot_path is None
    assert "PASSIVE_SCREENSHOT_ERROR_SECRET" in json.dumps(before.capture_metadata)
    assert capture.action_progress(before, after)["observation_changed"] is False
    seen = []
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self, payload: seen.append(payload) or
        {"model": "gemini-3.8-flash", "output_text": '{"action":"wait","seconds":0,"thought":"observe"}'})
    asyncio.run(runner.ModelClient("unused", "gemini-3.8-flash", "unused").decide(task="Inspect page", step=1,
        max_steps=5, bundle=before, task_memory="", recent_actions=[], turn_dir=tmp_path,
        viewport=(1365, 768)))
    assert "PASSIVE_SCREENSHOT_ERROR_SECRET" not in json.dumps(seen)
    assert "DOM_ONLY_SECRET" in json.dumps(seen)
    assert all(set(item) == {"text"} for item in seen[0]["contents"][0]["parts"])

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("navigation_kind", ["same_url", "different_url"])
def test_capture_records_navigation_inside_interval(tmp_path, monkeypatch, navigation_kind):
    original = FakeCDP.call
    frame_calls = []
    async def call(self, method, params=None, **kwargs):
        if method == "Page.getFrameTree":
            frame_calls.append(method)
            url = ("https://example.test/changed" if navigation_kind == "different_url" and bool(self.navigation_events)
                else "https://example.test")
            return {"frameTree": {"frame": {"id": "main", "url": url, "loaderId": "loader"}}}
        result = await original(self, method, params, **kwargs)
        if method == "ChromiumRL.captureStructuredSnapshot":
            self.navigation_events.append({"method": "Page.frameNavigated", "params": {"frame": {
                "id": "main", "url": "https://example.test", "loaderId": "loader"}},
                "session_id": "fixture", "recorded_at": "9999-01-01T00:00:00Z"})
        return result
    monkeypatch.setattr(FakeCDP, "call", call)
    bundle = asyncio.run(capture.capture_bundle(FakeCDP(), tmp_path / "state", max_nodes=100,
        max_text_chars=1000, observation_mode="dom"))
    metadata = bundle.capture_metadata
    assert metadata["navigation_during_capture"] is True
    assert metadata["url_before"] == "https://example.test"
    assert metadata["url_after"] == ("https://example.test/changed" if navigation_kind == "different_url"
        else "https://example.test")
    assert len(metadata["navigation_events"]) == 1
    assert metadata["capture_order"] == ["structured_dom", "screenshot", "dom_model_artifacts"]
    assert all(item["started_at"] <= item["ended_at"] and item["duration_seconds"] >= 0
        for item in metadata["captures"])

@pytest.mark.usefixtures("no_network")
def test_passive_dom_renderer_failure_removes_partial_artifacts(tmp_path, monkeypatch):
    def render(path):
        path.with_name("dom_full.txt").write_text("partial passive evidence")
        path.with_name(".dom_full.txt.tmp").write_text("temporary passive evidence")
        raise RunnerError("PASSIVE_RENDERER_ERROR")
    monkeypatch.setattr(capture, "render_full_stored_snapshot", render)
    bundle = asyncio.run(capture.capture_bundle(FakeCDP(observation_mode="screenshot"), tmp_path / "state",
        max_nodes=100, max_text_chars=1000, observation_mode="screenshot"))
    assert bundle.screenshot_path.is_file()
    assert bundle.snapshot_path is None
    assert not list(bundle.directory.glob("dom*"))
    assert not list(bundle.directory.glob(".dom*"))
    assert not bundle.capture_metadata["paired_complete"]
    assert "PASSIVE_RENDERER_ERROR" in json.dumps(bundle.capture_metadata)

@pytest.mark.usefixtures("no_network")
def test_capture_retry_preserves_passive_failure_metadata(tmp_path, monkeypatch):
    original = FakeCDP.call
    counters = {"dom": 0, "screenshot": 0}
    async def call(self, method, params=None, **kwargs):
        if method == "ChromiumRL.captureStructuredSnapshot":
            counters["dom"] += 1
            if counters["dom"] == 1:
                raise RunnerError("PASSIVE_FIRST_CAPTURE_SECRET")
        if method == "Page.captureScreenshot":
            counters["screenshot"] += 1
            if counters["screenshot"] == 1:
                raise RunnerError("CDP websocket closed")
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeCDP, "call", call)
    synchronize = AsyncMock(return_value={"switched": False})
    monkeypatch.setattr(capture, "synchronize_recorder_target", synchronize)
    run = tmp_path / "recordings/run1/screenshot/task"
    bundle, reconnects = asyncio.run(capture.capture_after_action_bundle(
        FakeCDP(observation_mode="screenshot"), None, run / "steps" / "step_001", max_nodes=100,
        max_text_chars=1000, observation_mode="screenshot", attempts=2))
    assert bundle.capture_metadata["paired_complete"]
    assert len(reconnects) == 1 and synchronize.await_count == 1
    failures = [json.loads(line) for line in (run_directory(run, area="logs") / "capture_failures.jsonl").read_text().splitlines()]
    assert len(failures) == 1
    assert failures[0]["attempt"] == 1
    assert failures[0]["directory"] == "steps/step_001"
    assert "PASSIVE_FIRST_CAPTURE_SECRET" in json.dumps(failures[0]["capture"])
    assert "CDP websocket closed" in failures[0]["error"]

@pytest.mark.usefixtures("no_network")
def test_runtime_fresh_configuration_reads_actor_and_audit_defaults_from_template(tmp_path, monkeypatch, capsys):
    from w8bench.task_recorder import browser_runtime
    monkeypatch.setattr(browser_runtime, "ROOT", tmp_path)
    monkeypatch.setattr(browser_runtime, "choose_port", lambda preferred, used: preferred)
    monkeypatch.setattr(browser_runtime, "unique_container_name", lambda base: base)
    (tmp_path / ".env.example").write_text("ACTOR_MODEL=actor-from-template\n"
        "EVIDENCE_AUDIT_MODEL=inventory-from-template\nEVIDENCE_ADJUDICATOR_MODEL=adjudicator-from-template\n"
        "EVIDENCE_AUDIT_PROVIDER=google\nEVIDENCE_ADJUDICATOR_PROVIDER=google\nGEMINI_API_KEY=\n"
        "TASK_CATALOG_FILE=tasks.jsonl\n")
    path = tmp_path / "fresh.env"
    assert browser_runtime.configure(path, False) == 0
    values = browser_runtime.read_env(path)
    assert values["ACTOR_MODEL"] == "actor-from-template"
    assert values["EVIDENCE_AUDIT_MODEL"] == "inventory-from-template"
    assert values["EVIDENCE_ADJUDICATOR_MODEL"] == "adjudicator-from-template"
    assert values["EVIDENCE_AUDIT_PROVIDER"] == "google"
    assert values["EVIDENCE_ADJUDICATOR_PROVIDER"] == "google"
    assert values["GEMINI_API_KEY"] == ""
    assert values["TASK_CATALOG_FILE"] == "tasks.jsonl"
    output = capsys.readouterr().out
    assert "Set GEMINI_API_KEY credentials" in output
    assert "Edit GEMINI_API_KEY and ACTOR_MODEL" not in output

@pytest.mark.usefixtures("no_network")
def test_runtime_port_refresh_preserves_audit_settings_and_fake_credentials(tmp_path, monkeypatch, capsys):
    from w8bench.task_recorder import browser_runtime
    monkeypatch.setattr(browser_runtime, "ROOT", tmp_path)
    monkeypatch.setattr(browser_runtime, "choose_port", lambda preferred, used: preferred)
    monkeypatch.setattr(browser_runtime, "unique_container_name", lambda base: base)
    (tmp_path / ".env.example").write_text("ACTOR_MODEL=gemini-3.8-flash\n"
        "EVIDENCE_AUDIT_MODEL=template-inventory\nEVIDENCE_ADJUDICATOR_MODEL=template-adjudicator\n"
        "TASK_CATALOG_FILE=tasks.jsonl\n")
    path = tmp_path / "existing.env"
    expected = {"ACTOR_MODEL": "gemini-3.8-flash", "GEMINI_API_KEY": "fake-google-test-value", "EVIDENCE_AUDIT_MODEL": "configured-inventory",
        "EVIDENCE_ADJUDICATOR_MODEL": "configured-adjudicator", "EVIDENCE_AUDIT_PROVIDER": "google",
        "EVIDENCE_ADJUDICATOR_PROVIDER": "google", "CONTAINER_NAME": "owned-browser",
        "TASK_CATALOG_FILE": "existing-tasks.jsonl"}
    path.write_text("".join(f"{key}={value}\n" for key, value in expected.items()))
    assert browser_runtime.configure(path, True) == 0
    actual = browser_runtime.read_env(path)
    assert {key: actual[key] for key in expected} == expected
    output = capsys.readouterr().out
    assert expected["GEMINI_API_KEY"] not in output
    assert path.stat().st_mode & 0o777 == 0o600

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("failure", [None, "version", "attach"])
def test_action_session_connection_preserves_version_and_attachment(monkeypatch, failure):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    error = AgentBrowserError(["connect"], "fixture failure")
    replies = ([error] if failure == "version" else
               ["agent-browser fixture", error if failure == "attach" else {"success": True}])
    invoke = AsyncMock(side_effect=replies)
    monkeypatch.setattr(driver, "_invoke", invoke)
    if failure:
        with pytest.raises(AgentBrowserError, match="fixture failure"):
            asyncio.run(driver.connect())
    else:
        asyncio.run(driver.connect())
    assert driver.connected is (failure is None)
    assert driver.version == ("" if failure == "version" else "agent-browser fixture")
    assert invoke.await_args_list[0].args == (["--version"],)
    assert invoke.await_args_list[0].kwargs == {"json_output": False, "use_session": False}
    if failure != "version":
        assert invoke.await_args_list[1].args == (["connect", "9222"],)
        assert invoke.await_args_list[1].kwargs == {}

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("failures", [0, 1, 2])
def test_capture_command_retries_only_read_timeouts(monkeypatch, failures):
    from types import SimpleNamespace
    cdp = SimpleNamespace(call=AsyncMock(side_effect=[TimeoutError()] * failures + [{"captured": True}]),
        recover_observation=AsyncMock(return_value={"alive": True}))
    sleep = AsyncMock()
    monkeypatch.setattr(capture.asyncio, "sleep", sleep)
    pending = capture.capture_call(cdp, "Read.fixture", {"viewport": True})
    if failures == 2:
        with pytest.raises(RunnerError, match="Read.fixture failed after 2 read-only attempts") as caught:
            asyncio.run(pending)
        assert isinstance(caught.value.__cause__, TimeoutError)
    else:
        assert asyncio.run(pending) == {"captured": True}
    assert cdp.call.await_count == min(failures + 1, 2)
    assert all(call.args == ("Read.fixture", {"viewport": True}) for call in cdp.call.await_args_list)
    assert sleep.await_count == int(failures > 0)
    if failures:
        assert sleep.await_args.args == (0.5,)

@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("outcome", ["success", "protocol_error", "disconnect", "timeout", "send_error"])
def test_cdp_requests_preserve_responses_and_transport_failures(outcome):
    from types import SimpleNamespace
    cdp = capture.CDPClient("http://localhost:9222", timeout=0.001)
    cdp.session_id = "fixture-session"
    requests = []
    class Socket:
        async def send_json(self, request):
            requests.append(request)
            if outcome == "send_error":
                raise RuntimeError("CDP websocket is not connected")
            if outcome != "timeout":
                await cdp._read_messages()
        async def __aiter__(self):
            if outcome != "disconnect":
                yield SimpleNamespace(type=capture.aiohttp.WSMsgType.TEXT, data=json.dumps({
                    "method": "Page.navigatedWithinDocument", "sessionId": "fixture-session",
                    "params": {"url": "https://example.test/next"}}))
                payload = {"id": 1, "error": {"message": "fixture protocol error"}} if outcome == "protocol_error" else {
                    "id": 1, "result": {"captured": True}}
                yield SimpleNamespace(type=capture.aiohttp.WSMsgType.TEXT, data=json.dumps(payload))
    cdp.ws = Socket()
    pending = cdp.call("Page.getFrameTree", {"viewport": True})
    if outcome == "success":
        assert asyncio.run(pending) == {"captured": True}
    elif outcome == "protocol_error":
        with pytest.raises(capture.CDPError) as caught:
            asyncio.run(pending)
        assert caught.value.method == "Page.getFrameTree"
        assert caught.value.error == {"message": "fixture protocol error"}
    elif outcome == "timeout":
        with pytest.raises(TimeoutError):
            asyncio.run(pending)
    else:
        expected = ("CDP websocket closed while sending Page.getFrameTree: CDP websocket is not connected"
                    if outcome == "send_error" else "CDP websocket closed")
        with pytest.raises(RunnerError) as caught:
            asyncio.run(pending)
        assert str(caught.value) == expected
    assert requests == [{"id": 1, "method": "Page.getFrameTree", "params": {"viewport": True}, "sessionId": "fixture-session"}]
    assert cdp.pending == {}
    assert [row["params"]["url"] for row in cdp.navigation_events] == (
        ["https://example.test/next"] if outcome in {"success", "protocol_error"} else [])

@pytest.mark.asyncio
@pytest.mark.parametrize("crash_method, params", [
    ("Inspector.targetCrashed", {}),
    ("Target.targetCrashed", {"targetId": "page-one"}),
    ("Inspector.detached", {"reason": "Render process gone."}),
])
async def test_renderer_crash_fails_pending_calls_and_blocks_further_capture(tmp_path, crash_method, params):
    cdp = capture.CDPClient('http://localhost:9222')
    cdp.target = {'targetId': 'page-one'}
    cdp.session_id = 'session-one'
    cdp.recording_dir = tmp_path / "recordings/run1/dom/task"
    class Socket:
        def __init__(self):
            self.requests = []
        async def send_json(self, request):
            self.requests.append(request)
        async def __aiter__(self):
            yield SimpleNamespace(type=capture.aiohttp.WSMsgType.TEXT, data=json.dumps({
                'method': crash_method, 'sessionId': 'session-one', 'params': params}))
    cdp.ws = Socket()
    pending = asyncio.create_task(cdp.call('Page.captureScreenshot'))
    await asyncio.sleep(0)
    await cdp._read_messages()
    with pytest.raises(RunnerError) as error:
        await pending
    assert error.value.technical_failure_class == 'browser_crash'
    count = len(cdp.ws.requests)
    with pytest.raises(RunnerError):
        await cdp.call('Page.getFrameTree')
    assert len(cdp.ws.requests) == count
    records = [json.loads(line) for line in (run_directory(cdp.recording_dir, area="logs") / 'browser_events.jsonl').read_text().splitlines()]
    assert records[0]['method'] == crash_method
    assert records[0]['target_id'] == 'page-one'

@pytest.mark.asyncio
@pytest.mark.parametrize('first_error', [TimeoutError(), capture.CDPError('Page.captureScreenshot', {'code': -32603, 'message': 'Internal error'})])
async def test_read_only_failure_probes_and_reattaches_once_without_replaying_action(first_error):
    cdp = SimpleNamespace(call=AsyncMock(side_effect=[first_error, {'captured': True}]),
        recover_observation=AsyncMock(return_value={'alive': True}))
    assert await capture.capture_call(cdp, 'Page.captureScreenshot', {'format': 'png'}) == {'captured': True}
    cdp.recover_observation.assert_awaited_once()
    assert cdp.call.await_count == 2
    assert all(row.args[0] == 'Page.captureScreenshot' for row in cdp.call.await_args_list)

@pytest.mark.asyncio
async def test_dead_target_ends_read_only_recovery_without_second_capture():
    failure = RunnerError('target liveness probe failed')
    failure.technical_failure_class = 'cdp_stall'
    cdp = SimpleNamespace(call=AsyncMock(side_effect=TimeoutError()),
        recover_observation=AsyncMock(side_effect=failure))
    with pytest.raises(RunnerError, match='liveness'):
        await capture.capture_call(cdp, 'Page.captureScreenshot', {})
    assert cdp.call.await_count == 1

@pytest.mark.asyncio
async def test_target_identity_never_falls_back_to_matching_url_or_title():
    from w8bench.task_recorder.agent_browser.client import AgentBrowserPage
    cdp = capture.CDPClient('http://localhost:9222')
    page = AgentBrowserPage('t2', 'https://same.test/', 'Same', target_id='exact-two')
    pages = [{'targetId': 'exact-one', 'url': page.url, 'title': page.title},
             {'targetId': 'exact-two', 'url': page.url, 'title': page.title}]
    assert cdp._select_active_target(page, pages)['targetId'] == 'exact-two'
    with pytest.raises(RunnerError, match='target'):
        cdp._select_active_target(page, pages[:1])

@pytest.mark.asyncio
async def test_cdp_call_receipt_contains_timing_but_not_request_secret(tmp_path):
    cdp = capture.CDPClient('http://localhost:9222')
    cdp.recording_dir = tmp_path / "recordings/run1/dom/task"
    cdp.session_id = 'session'
    class Socket:
        async def send_json(self, request):
            cdp.pending[request['id']].set_result({'id': request['id'], 'result': {'ok': True}})
    cdp.ws = Socket()
    assert await cdp.call('Network.setExtraHTTPHeaders', {'headers': {'Authorization': 'secret'}}) == {'ok': True}
    text = (run_directory(cdp.recording_dir, area="logs") / 'cdp_calls.jsonl').read_text()
    row = json.loads(text)
    assert row['method'] == 'Network.setExtraHTTPHeaders'
    assert row['duration_seconds'] >= 0
    assert row['status'] == 'completed'
    assert 'secret' not in text and 'Authorization' not in text

@pytest.mark.asyncio
@pytest.mark.parametrize("race,matches", [(False, {"exact-target"}), (True, {"exact-target"}),
    (False, set()), (False, {"exact-target", "other-target"})])
async def test_cli_page_identity_uses_inspector_metadata_and_detects_tab_race(monkeypatch, race, matches):
    driver = AgentBrowserClient('unused', session='fixture', cdp_url='http://localhost:9222', timeout=90)
    tab = {'tabId': 't2', 'url': 'https://same.test/', 'title': 'Same', 'active': True}
    cdp = capture.CDPClient('http://localhost:9222')
    cdp.target_registry = {'exact-target': {'identity_marker': 'isolated-identity'}}
    command = AsyncMock(return_value={'sessionId': 'binding-session'})
    monkeypatch.setattr(cdp, 'call', command)
    calls = []
    async def invoke(arguments):
        calls.append(arguments)
        if arguments[0] == 'eval':
            assert arguments[1].startswith('void 0\n//# sourceURL=')
            assert capture.TARGET_IDENTITY_PROPERTY not in arguments[1]
            assert 'isolated-identity' not in arguments[1]
            cdp.identity_reads[arguments[1].split('sourceURL=')[1]].update(matches)
            return {'data': {'result': None}}
        current = {**tab, 'tabId': 't3'} if race and len(calls) > 1 else tab
        return {'data': {'tabs': [current]}}
    monkeypatch.setattr(driver, '_invoke', invoke)
    if race or len(matches) != 1:
        with pytest.raises(AgentBrowserError, match='changed during exact target binding' if race else 'unique exact'):
            await driver.active_page(cdp)
    else:
        page = await driver.active_page(cdp)
        assert page.identity_marker == 'isolated-identity' and page.target_id == 'exact-target'
    assert not cdp.identity_reads
    assert any(call.args[0] == 'Debugger.disable' for call in command.await_args_list)
    assert any(call.args[0] == 'Target.detachFromTarget' for call in command.await_args_list)

@pytest.mark.asyncio
async def test_identity_registry_refreshes_after_navigation_and_binds_popup_by_exact_id(tmp_path, monkeypatch):
    from w8bench.task_recorder.agent_browser.client import AgentBrowserPage
    cdp = capture.CDPClient('http://localhost:9222')
    cdp.target = {'targetId': 'parent', 'url': 'https://same.test/'}
    cdp.session_id = 'parent-session'
    cdp.recording_dir = tmp_path / "recordings/run1/dom/task"
    pages = [{**cdp.target, 'type': 'page'}, {'targetId': 'popup', 'type': 'page',
        'openerId': 'parent', 'url': 'https://same.test/'}]
    calls = []
    async def command(method, params=None, **kwargs):
        calls.append((method, params, kwargs))
        if method == 'Target.getTargets': return {'targetInfos': pages}
        if method == 'Page.getFrameTree': return {'frameTree': {'frame': {'id': 'main-frame'}}}
        if method == 'Page.createIsolatedWorld': return {'executionContextId': 42}
        if method == 'Target.attachToTarget': return {'sessionId': params['targetId']+'-session'}
        return {}
    monkeypatch.setattr(cdp, 'call', command)
    await cdp.synchronize_target()
    marker = cdp.target_registry['popup']['identity_marker']
    assert cdp.target_registry['popup']['opener_id'] == 'parent'
    first = len([x for x in calls if x[0] == 'Runtime.evaluate'])
    await cdp.synchronize_target()
    assert cdp.target_registry['popup']['identity_marker'] == marker
    assert len([x for x in calls if x[0] == 'Runtime.evaluate']) == first * 2
    report = await cdp.synchronize_target(AgentBrowserPage('t2', 'https://same.test/', 'Same', identity_marker=marker))
    assert report['selected_target_id'] == 'popup'
    assert cdp.target['targetId'] == 'popup'
    worlds = [x for x in calls if x[0] == 'Page.createIsolatedWorld']
    assert worlds and all(x[1]['worldName'] == capture.TARGET_IDENTITY_WORLD for x in worlds)
    assert all(x[1]['grantUniveralAccess'] is False for x in worlds)
    writes = [x for x in calls if x[0] == 'Runtime.evaluate']
    assert writes and all(x[1]['contextId'] == 42 for x in writes)
    assert not any(x[0] == 'Page.addScriptToEvaluateOnNewDocument' for x in calls)
    assert (run_directory(cdp.recording_dir, area="logs") / 'target_registry.json').is_file()
    cdp.target_registry['parent']['identity_marker'] = marker
    with pytest.raises(RunnerError, match='unique exact'):
        cdp._select_active_target(AgentBrowserPage('t2', 'https://same.test/', 'Same', identity_marker=marker), pages)

@pytest.mark.asyncio
async def test_renderer_crash_interrupts_pending_cli_snapshot_without_retry(monkeypatch):
    cdp = capture.CDPClient('http://localhost:9222')
    started = asyncio.Event()
    cancelled = asyncio.Event()
    async def snapshot():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    driver = SimpleNamespace(snapshot=AsyncMock(side_effect=snapshot), reconnect=AsyncMock())
    task = asyncio.create_task(capture._snapshot_action_refs(driver, 3, cdp))
    await started.wait()
    cdp._page_failure = RunnerError('renderer crashed')
    cdp._page_failure.technical_failure_class = 'browser_crash'
    cdp.page_failure_event.set()
    with pytest.raises(RunnerError, match='renderer crashed'):
        await task
    assert cancelled.is_set()
    assert driver.snapshot.await_count == 1 and driver.reconnect.await_count == 0

@pytest.mark.asyncio
async def test_liveness_probe_reattaches_only_existing_target_and_never_replays_input(monkeypatch):
    cdp = capture.CDPClient('http://localhost:9222')
    cdp.target = {'targetId': 'one'}
    cdp.session_id = 'old'
    calls = []
    async def command(method, params=None, **kwargs):
        calls.append((method, params, kwargs))
        if method == 'Target.getTargets': return {'targetInfos': [{'targetId': 'one'}]}
        if method == 'Target.attachToTarget': return {'sessionId': 'probe'}
        if method == 'Runtime.evaluate': return {'result': {'value': 1}}
        return {}
    monkeypatch.setattr(cdp, 'call', command)
    monkeypatch.setattr(cdp, '_enable_attached_target', AsyncMock())
    result = await cdp.recover_observation()
    assert result['alive'] and result['reattached']
    assert cdp.session_id == 'probe'
    assert [x[0] for x in calls] == ['Target.getTargets', 'Target.attachToTarget', 'Runtime.evaluate', 'Target.detachFromTarget']
    assert calls[2][1]['expression'] == '1'
    assert all(not x[0].startswith('Input.') and x[0] != 'Page.navigate' for x in calls)

@pytest.mark.asyncio
async def test_liveness_probe_dead_target_does_not_attach_or_continue(monkeypatch):
    cdp = capture.CDPClient('http://localhost:9222')
    cdp.target = {'targetId': 'gone'}
    cdp.call = AsyncMock(return_value={'targetInfos': []})
    with pytest.raises(RunnerError) as error:
        await cdp.recover_observation()
    assert error.value.technical_failure_class == 'cdp_stall'
    assert cdp.call.await_count == 1
    assert cdp.page_failure_event.is_set()

@pytest.mark.asyncio
async def test_cli_call_receipts_do_not_persist_arguments_or_credentials(tmp_path, monkeypatch):
    driver = AgentBrowserClient('unused', session='fixture', cdp_url='http://localhost:9222', timeout=90)
    driver.recording_dir = tmp_path / "recordings/run1/dom/task"
    class Process:
        returncode = 0
        args = ['unused']
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def communicate(self, *args, **kwargs):return ('{"success":true,"data":{}}', '')
        def poll(self): return self.returncode
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **kw: Process())
    driver._invoke_sync(['fill', '@e1', 'fake-credential'])
    text = (run_directory(driver.recording_dir, area="logs") / 'agent_browser_calls.jsonl').read_text()
    row = json.loads(text)
    assert row['command'] == 'fill' and row['duration_seconds'] >= 0
    assert 'fake-credential' not in text and '@e1' not in text

@pytest.mark.asyncio
async def test_passive_capture_stops_immediately_after_confirmed_renderer_crash(tmp_path, monkeypatch):
    cdp = capture.CDPClient('http://localhost:9222', observation_mode='screenshot')
    cdp.target = {'targetId': 'one'}
    cdp.call = AsyncMock(return_value={'frameTree': {'frame': {'url': 'https://example.test/'}}})
    phases = []
    async def phase(client, directory, name, state, max_nodes, max_text_chars, agent_browser=None):
        phases.append(name)
        failure = RunnerError('page target crashed')
        failure.technical_failure_class = 'browser_crash'
        raise failure
    monkeypatch.setattr(capture, '_capture_phase', phase)
    directory = tmp_path/'step_001'
    with pytest.raises(RunnerError, match='crashed'):
        await capture.capture_bundle(cdp, directory, max_nodes=7000, max_text_chars=200000, observation_mode='screenshot')
    assert phases == ['structured_dom']
    assert cdp.call.await_count == 2  # Frame identity and paint monitor are established before raw capture.
    assert json.loads((directory/'capture.json').read_text())['captures'][0]['status'] == 'error'

@pytest.mark.asyncio
async def test_liveness_probe_has_one_short_overall_deadline(monkeypatch):
    cdp = capture.CDPClient('http://localhost:9222')
    cdp.target = {'targetId': 'one'}
    async def stalled(*args, **kwargs): await asyncio.Event().wait()
    monkeypatch.setattr(cdp, 'call', stalled)
    monkeypatch.setattr(capture, 'LIVENESS_PROBE_SECONDS', 0.01)
    started = time.monotonic()
    with pytest.raises(RunnerError, match='liveness probe'):
        await cdp.recover_observation()
    assert time.monotonic() - started < 0.2
    assert cdp._page_failure.technical_failure_class == 'cdp_stall'

@pytest.mark.asyncio
async def test_unexpected_session_detach_is_recorded_without_false_crash(tmp_path):
    cdp = capture.CDPClient('http://localhost:9222')
    cdp.target = {'targetId': 'one'}
    cdp.session_id = 'current'
    cdp.recording_dir = tmp_path / "recordings/run1/dom/task"
    class Socket:
        async def __aiter__(self):
            yield SimpleNamespace(type=capture.aiohttp.WSMsgType.TEXT, data=json.dumps({
                'method': 'Target.detachedFromTarget', 'params': {'targetId': 'one', 'sessionId': 'current'}}))
            yield SimpleNamespace(type=capture.aiohttp.WSMsgType.TEXT, data=json.dumps({
                'method': 'Page.javascriptDialogOpening', 'sessionId': 'current',
                'params': {'type': 'alert', 'message': 'credential-not-for-logs', 'defaultPrompt': 'also-secret'}}))
    cdp.ws = Socket()
    await cdp._read_messages()
    assert cdp._session_detached and cdp._page_failure is None
    text = (run_directory(cdp.recording_dir, area="logs") / 'browser_events.jsonl').read_text()
    assert 'javascriptDialogOpening' in text
    assert 'credential-not-for-logs' not in text and 'also-secret' not in text

@pytest.mark.parametrize('attributes', ['ref=e1 selected', 'selected ref=e1', 'disabled ref=e1 selected=true', 'ref=@e1 selected'])
def test_fairness_reference_bracket_attributes_preserve_one_ref(attributes):
    driver = AgentBrowserClient('unused', session='fixture', cdp_url='http://localhost:9222', timeout=1)
    text = f'- combobox "Choice" [{attributes}]'
    emitted, targets = driver._visible_snapshot(text, {'e1': {'role': 'combobox', 'name': 'Choice'}},
        {'e1': {'x': 20, 'y': 20, 'width': 100, 'height': 30}}, {'width': 1365, 'height': 768})
    assert emitted == text and set(targets) == {'e1'}

@pytest.mark.parametrize('attributes', ['ref=e1 ref=e2', 'ref=e1 ref=e1', 'selected', 'ref=e1junk'])
def test_fairness_reference_brackets_reject_missing_or_ambiguous_refs(attributes):
    driver = AgentBrowserClient('unused', session='fixture', cdp_url='http://localhost:9222', timeout=1)
    emitted, targets = driver._visible_snapshot(f'- button "Choice" [{attributes}]',
        {'e1': {'role': 'button', 'name': 'Choice'}, 'e2': {'role': 'button', 'name': 'Choice'}},
        {ref: {'x': 20, 'y': 20, 'width': 100, 'height': 30} for ref in ('e1', 'e2')}, {'width': 1365, 'height': 768})
    assert not targets and 'ref=' not in emitted

@pytest.mark.parametrize('mode', ['dom', 'screenshot'])
def test_fairness_url_changes_are_shared_observation_changes(tmp_path, mode):
    left, right = tmp_path/'left.png', tmp_path/'right.png'
    Image.new('RGB', (4,4), 'white').save(left);Image.new('RGB', (4,4), 'white').save(right)
    before = capture.CaptureBundle(observation_mode=mode, document_url='https://one.test/', screenshot_path=left)
    after = capture.CaptureBundle(observation_mode=mode, document_url='https://two.test/', screenshot_path=right)
    result = capture.action_progress(before,after)
    assert result['url_changed'] is True and result['observation_changed'] is True
    assert result['task_progress'] is None and 'made_progress' not in result


def test_fairness_screenshot_progress_compares_decoded_pixels(tmp_path):
    left, right = tmp_path/'left.png',tmp_path/'right.png'
    image = Image.new('RGB',(4,4),'white');image.save(left,compress_level=0);image.save(right,compress_level=9)
    assert left.read_bytes() != right.read_bytes()
    result = capture.action_progress(capture.CaptureBundle(observation_mode='screenshot', screenshot_path=left),
        capture.CaptureBundle(observation_mode='screenshot',screenshot_path=right))
    assert result['screenshot_changed'] is False and result['observation_changed'] is False
    assert result['task_progress'] is None


def test_fairness_dom_progress_ignores_ref_only_renumbering():
    before = capture.CaptureBundle(model_text='Content is unchanged',agent_browser_action_text='- button "Save" [ref=e1 selected]')
    after = capture.CaptureBundle(model_text='Content is unchanged',agent_browser_action_text='- button "Save" [ref=e67 selected]')
    result = capture.action_progress(before,after)
    assert result['agent_browser_observation_changed'] is False and result['observation_changed'] is False
    assert result['task_progress'] is None

@pytest.mark.asyncio
async def test_fairness_identity_binding_ignores_unrelated_target_failure(tmp_path,monkeypatch):
    driver = AgentBrowserClient('unused', session='fixture', cdp_url='http://localhost:9222',timeout=90)
    cdp = capture.CDPClient('http://localhost:9222');cdp.recording_dir=tmp_path / "recordings/run1/dom/task"
    cdp.target_registry={'active':{'identity_marker':'private'},'background':{'identity_marker':'other'}}
    commands=[]
    async def command(method,params=None,**kwargs):
        commands.append((method,params,kwargs))
        if method=='Target.attachToTarget':return {'sessionId':params['targetId']+'-session'}
        if method=='Debugger.enable' and kwargs.get('session_id')=='background-session':
            raise capture.CDPError(method,{'code':-32603,'message':'background cannot answer'})
        return {}
    async def invoke(arguments):
        if arguments[0]=='eval':cdp.identity_reads[arguments[1].split('sourceURL=')[1]].add('active');return {'data':{'result':None}}
        return {'data':{'tabs':[{'tabId':'t1','url':'https://same.test/','active':True}]}}
    monkeypatch.setattr(cdp,'call',command);monkeypatch.setattr(driver,'_invoke',invoke)
    page=await driver.active_page(cdp)
    assert page.target_id=='active'
    detached={params['sessionId'] for method,params,kwargs in commands if method=='Target.detachFromTarget'}
    assert detached=={'active-session','background-session'}
    assert not cdp.identity_reads
    receipts=(run_directory(cdp.recording_dir, area="logs") / 'target_identity.jsonl').read_text()
    assert 'background' in receipts and 'error' in receipts

@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['dom','screenshot'])
@pytest.mark.parametrize('children',[0,1,2])
async def test_fairness_exact_popup_policy_is_shared(monkeypatch,mode,children):
    cdp=capture.CDPClient('http://localhost:9222',observation_mode=mode);cdp.target={'targetId':'parent'}
    pages=[{'targetId':'parent','type':'page','url':'https://same.test/'}]+[
        {'targetId':f'popup-{i}','type':'page','openerId':'parent','url':'https://same.test/'} for i in range(children)]
    async def command(method,params=None,**kwargs):
        if method=='Target.getTargets':return {'targetInfos':pages}
        if method=='Target.attachToTarget':return {'sessionId':'capture-session'}
        return {}
    monkeypatch.setattr(cdp,'call',command);monkeypatch.setattr(cdp,'_enable_attached_target',AsyncMock())
    if children>1:
        with pytest.raises(RunnerError,match='ambiguous'):await capture._synchronize_capture_tab(cdp)
    else:
        result=await capture._synchronize_capture_tab(cdp)
        assert result['selected_target_id']==('popup-0' if children else 'parent')

@pytest.mark.asyncio
async def test_fairness_raw_observations_precede_projection_and_writing(tmp_path,monkeypatch):
    events=[];original=FakeCDP.call
    original_json=capture.write_json
    original_bytes=Path.write_bytes
    writes=[]
    def write_json(path,value):
        if path.parent==tmp_path/'state':
            assert 'executable_refs' in events, f'{path.name} written before raw observations ended'
            writes.append(path.name)
        return original_json(path,value)
    def write_bytes(path,value):
        if path.parent==tmp_path/'state':
            assert 'executable_refs' in events, f'{path.name} written before raw observations ended'
            writes.append(path.name)
        return original_bytes(path,value)
    monkeypatch.setattr(capture,'write_json',write_json)
    monkeypatch.setattr(Path,'write_bytes',write_bytes)
    async def command(self,method,params=None,**kwargs):
        if method in {'ChromiumRL.captureStructuredSnapshot','Page.captureScreenshot','ChromiumRL.getModelDOM'}:
            events.append(method)
        return await original(self,method,params,**kwargs)
    monkeypatch.setattr(FakeCDP,'call',command)
    from w8bench.task_recorder.agent_browser import AgentBrowserObservation
    observation=AgentBrowserObservation(text='- button "Save" [ref=e1]\n',refs=frozenset({'e1'}),
        origin='fixture',command=('snapshot','-i'),targets={'e1':{'role':'button','name':'Save'}})
    async def snapshot():
        assert not list((tmp_path/'state').iterdir())
        events.append('executable_refs');return observation
    driver=SimpleNamespace(snapshot=snapshot)
    bundle=await capture.capture_bundle(FakeCDP(),tmp_path/'state',max_nodes=7000,max_text_chars=200000,
        observation_mode='dom',agent_browser=driver)
    assert events[:4]==['ChromiumRL.captureStructuredSnapshot','Page.captureScreenshot','executable_refs','ChromiumRL.getModelDOM']
    assert bundle.agent_browser_refs==frozenset({'e1'}) and bundle.agent_browser_action_path.is_file()
    assert bundle.snapshot_path.is_file() and bundle.screenshot_path.is_file()
    assert bundle.capture_metadata['raw_capture_ended_at']<=bundle.capture_metadata['ended_at']
    assert {'dom.json','dom_model.json','screenshot.png','capture.json'}<=set(writes)

@pytest.mark.asyncio
async def test_fairness_capture_change_counters_are_private_and_do_not_recapture(tmp_path,monkeypatch):
    cdp=FakeCDP();cdp.paint_events=[]
    original=FakeCDP.call;reads=0;raw_calls=[]
    async def command(self,method,params=None,**kwargs):
        nonlocal reads
        if method=='Page.getFrameTree':return {'frameTree':{'frame':{'id':'main','url':'https://example.test/','loaderId':'stable'}}}
        if method=='Page.createIsolatedWorld':return {'executionContextId':37}
        if method=='Runtime.evaluate' and 'document.readyState' in params.get('expression', ''):
            return {'result':{'value':{'ready_state':'complete','mime_type':'text/html'}}}
        if method=='Runtime.evaluate':
            assert params['contextId']==37
            assert '__w8CaptureChanges' in params['expression']
            reads+=1;return {'result':{'value':{'count':0 if reads==1 else 2,'openShadowRoots':0}}}
        if method in {'ChromiumRL.captureStructuredSnapshot','Page.captureScreenshot'}:
            raw_calls.append(method)
        if method=='Page.captureScreenshot':self.paint_events.append({'target_id':'one','method':'LayerTree.layerPainted'})
        return await original(self,method,params,**kwargs)
    monkeypatch.setattr(FakeCDP,'call',command)
    bundle=await capture.capture_bundle(cdp,tmp_path/'state',max_nodes=7000,max_text_chars=200000)
    metadata=bundle.capture_metadata
    assert metadata['content_changed_during_capture'] is True
    assert metadata['paint_changed_during_capture'] is True
    assert metadata['content_change_monitor']['mutations_during_capture']==2
    assert metadata['content_change_monitor']['subframes_observed'] is False
    assert raw_calls==['ChromiumRL.captureStructuredSnapshot','Page.captureScreenshot']
    assert '__w8CaptureChanges' not in bundle.model_text
    assert bundle.agent_browser_action_text==''

@pytest.mark.asyncio
async def test_fairness_capture_monitor_failure_is_unknown_and_passive(tmp_path,monkeypatch):
    original=FakeCDP.call
    async def command(self,method,params=None,**kwargs):
        if method=='LayerTree.enable':raise RunnerError('paint monitor unavailable')
        return await original(self,method,params,**kwargs)
    monkeypatch.setattr(FakeCDP,'call',command)
    bundle=await capture.capture_bundle(FakeCDP(observation_mode='screenshot'),tmp_path/'state',
        max_nodes=7000,max_text_chars=200000,observation_mode='screenshot')
    assert bundle.capture_metadata['paint_changed_during_capture'] is None
    assert bundle.capture_metadata['content_changed_during_capture'] is None
    assert bundle.screenshot_path.is_file() and bundle.capture_metadata['paired_complete']

@pytest.mark.asyncio
async def test_fairness_reference_cli_aligns_to_the_shared_exact_target(tmp_path,monkeypatch):
    from w8bench.task_recorder.agent_browser import AgentBrowserPage
    cdp=capture.CDPClient('http://localhost:9222',observation_mode='dom');cdp.target={'targetId':'parent'}
    cdp.target_registry={'popup':{'target_id':'popup'}};cdp.recording_dir=tmp_path / "recordings/run1/dom/task"
    async def shared(client):
        client.target={'targetId':'popup'};return {'selected_target_id':'popup','switched':True}
    common=AsyncMock(side_effect=shared)
    monkeypatch.setattr(capture,'_synchronize_capture_tab',common)
    monkeypatch.setattr(cdp,'synchronize_target',AsyncMock(return_value={}))
    driver=SimpleNamespace(active_page=AsyncMock(return_value=AgentBrowserPage('t2','https://same.test/','',target_id='popup')))
    result=await capture.synchronize_recorder_target(cdp,driver)
    assert result['selected_target_id']=='popup' and result['switched'] is True
    assert driver.active_page.await_args.kwargs=={'target_id':'popup'}
    assert cdp.target_registry['popup']['tab_id']=='t2'
    assert json.loads((run_directory(cdp.recording_dir, area="logs") / 'target_registry.json').read_text())['targets'][0]['tab_id']=='t2'
    assert common.await_count==1

@pytest.mark.asyncio
async def test_fairness_passive_model_projection_failure_keeps_screenshot(tmp_path,monkeypatch):
    cdp=FakeCDP(observation_mode='screenshot');original=FakeCDP.call;calls=[]
    async def command(self,method,params=None,**kwargs):
        if method=='ChromiumRL.getModelDOM':raise RunnerError('passive projection unavailable')
        if method=='Page.captureScreenshot':calls.append('screenshot')
        return await original(self,method,params,**kwargs)
    monkeypatch.setattr(FakeCDP,'call',command)
    bundle=await capture.capture_bundle(cdp,tmp_path/'state',max_nodes=7000,max_text_chars=200000,observation_mode='screenshot')
    assert bundle.screenshot_path.is_file() and bundle.snapshot_path is None
    assert not bundle.model_text and not bundle.agent_browser_action_text
    assert bundle.capture_metadata['paired_complete'] is False and calls==['screenshot']
    assert bundle.capture_metadata['capture_order']==['structured_dom','screenshot','dom_model_artifacts']

@pytest.mark.asyncio
async def test_fairness_capture_retry_preserves_prior_raw_files_in_next_free_attempt(tmp_path,monkeypatch):
    parent=tmp_path/'recordings/run1/dom/task/steps';parent.mkdir(parents=True)
    (parent/'step_001_capture_attempt_01').mkdir()
    (parent/'step_001_capture_attempt_01/keep.txt').write_text('existing diagnostic')
    (parent/'step_001_capture_attempt_02').symlink_to('missing-diagnostic')
    calls=0
    async def bundle(client,directory,**kwargs):
        nonlocal calls
        calls+=1;directory.mkdir()
        (directory/'raw.txt').write_text('first capture' if calls==1 else 'second capture')
        write_json(directory/'capture.json',{'capture_attempt':calls})
        if calls==1:raise RunnerError('CDP websocket closed')
        return capture.CaptureBundle(snapshot_path=directory/'raw.txt')
    monkeypatch.setattr(capture,'capture_bundle',bundle)
    monkeypatch.setattr(capture,'synchronize_recorder_target',AsyncMock(return_value={}))
    monkeypatch.setattr(capture.asyncio,'sleep',AsyncMock())
    result,reconnects=await capture.capture_after_action_bundle(FakeCDP(),None,parent/'step_001',
        max_nodes=7000,max_text_chars=200000,attempts=2)
    assert result.snapshot_path.read_text()=='second capture'
    assert (parent/'step_001_capture_attempt_03/raw.txt').read_text()=='first capture'
    assert (parent/'step_001_capture_attempt_02').is_symlink()
    assert (parent/'step_001_capture_attempt_01/keep.txt').read_text()=='existing diagnostic'
    receipt=json.loads((run_directory(parent.parent, area="logs") / 'capture_failures.jsonl').read_text())
    assert receipt['preserved_capture']=='steps/step_001_capture_attempt_03'
    assert calls==2 and len(reconnects)==1

@pytest.mark.asyncio
async def test_fairness_raw_capture_failure_preserves_acquired_evidence_without_later_calls(tmp_path,monkeypatch):
    cdp=FakeCDP(observation_mode='screenshot');original=FakeCDP.call;observations=[]
    async def command(self,method,params=None,**kwargs):
        if method in {'ChromiumRL.captureStructuredSnapshot','Page.captureScreenshot','ChromiumRL.getModelDOM'}:
            observations.append(method)
        if method=='Page.captureScreenshot':raise RunnerError('screenshot observation unavailable')
        return await original(self,method,params,**kwargs)
    monkeypatch.setattr(FakeCDP,'call',command)
    with pytest.raises(RunnerError,match='unavailable'):
        await capture.capture_bundle(cdp,tmp_path/'state',max_nodes=7000,max_text_chars=200000,observation_mode='screenshot')
    assert (tmp_path/'state/dom.json').is_file()
    assert observations==['ChromiumRL.captureStructuredSnapshot','Page.captureScreenshot']
    assert not (tmp_path/'state/dom_model.json').exists()
    metadata=json.loads((tmp_path/'state/capture.json').read_text())
    assert set(metadata['preserved_raw_artifacts'])=={'dom.json'}

@pytest.mark.asyncio
async def test_fairness_capture_observes_known_frames_and_open_shadow_roots_with_partial_coverage(tmp_path,monkeypatch):
    original=FakeCDP.call;reads={}
    frame={'frame':{'id':'main','url':'https://example.test/','loaderId':'main-loader'},'childFrames':[
        {'frame':{'id':'child','loaderId':'child-loader'}},{'frame':{'id':'remote','loaderId':'remote-loader'}}]}
    async def command(self,method,params=None,**kwargs):
        if method=='Page.getFrameTree':return {'frameTree':frame}
        if method=='Page.createIsolatedWorld':
            if params['frameId']=='remote':raise RunnerError('unavailable remote context')
            return {'executionContextId':1 if params['frameId']=='main' else 2}
        if method=='Runtime.evaluate' and 'document.readyState' in params.get('expression', ''):
            return {'result':{'value':{'ready_state':'complete','mime_type':'text/html'}}}
        if method=='Runtime.evaluate':
            assert "element.shadowRoot" in params['expression'] and "observer.observe(root" in params['expression']
            context=params['contextId'];reads[context]=reads.get(context,0)+1
            return {'result':{'value':{'count':3 if context==2 and reads[context]>1 else 0,'openShadowRoots':1 if context==2 else 0}}}
        return await original(self,method,params,**kwargs)
    monkeypatch.setattr(FakeCDP,'call',command)
    bundle=await capture.capture_bundle(FakeCDP(),tmp_path/'state',max_nodes=7000,max_text_chars=200000)
    monitor=bundle.capture_metadata['content_change_monitor']
    assert {row['frame_id']:row['status'] for row in monitor['frames']}=={'main':'observed','child':'observed','remote':'unavailable'}
    assert monitor['mutations_during_capture']==3 and monitor['observed_frame_count']==2
    assert monitor['scope']=='known_frames_and_open_shadow_roots' and monitor['closed_shadow_roots_observed'] is False
    assert monitor['coverage_complete'] is False and monitor['status']=='partial'
    assert bundle.capture_metadata['content_changed_during_capture'] is True
    assert reads=={1:2,2:2}

@pytest.mark.asyncio
async def test_fairness_quiet_partial_monitors_never_claim_no_global_change(tmp_path,monkeypatch):
    original=FakeCDP.call
    async def command(self,method,params=None,**kwargs):
        if method=='Page.getFrameTree':return {'frameTree':{'frame':{'id':'main','url':'https://example.test/','loaderId':'stable'}}}
        if method=='Page.createIsolatedWorld':return {'executionContextId':10}
        if method=='Runtime.evaluate':return {'result':{'value':{'count':0,'openShadowRoots':1}}}
        return await original(self,method,params,**kwargs)
    monkeypatch.setattr(FakeCDP,'call',command)
    bundle=await capture.capture_bundle(FakeCDP(),tmp_path/'state',max_nodes=7000,max_text_chars=200000)
    metadata=bundle.capture_metadata
    assert metadata['content_change_monitor']['observed_content_changed'] is False
    assert metadata['content_change_monitor']['coverage_complete'] is False
    assert metadata['content_changed_during_capture'] is None
    assert metadata['paint_changed_during_capture'] is None
    assert metadata['paint_change_monitor']['reported_paint_changed'] is False

@pytest.mark.asyncio
async def test_fairness_known_target_is_selected_before_querying_unrelated_cli_tab(monkeypatch):
    driver=AgentBrowserClient('unused',session='fixture',cdp_url='http://localhost:9222',timeout=90)
    cdp=capture.CDPClient('http://localhost:9222')
    cdp.target_registry={'desired':{'identity_marker':'private','tab_id':'t1'},'background':{'identity_marker':'other','tab_id':'t2'}}
    selected='t2';commands=[]
    async def command(method,params=None,**kwargs):
        if method=='Target.attachToTarget':return {'sessionId':params['targetId']+'-session'}
        return {}
    async def invoke(arguments):
        nonlocal selected
        commands.append(arguments)
        if arguments[0]=='tab' and arguments[1]!='list':selected=arguments[1];return {'data':{}}
        if arguments[0]=='eval':
            assert selected=='t1','unrelated background tab must not be queried before selecting the known exact target'
            cdp.identity_reads[arguments[1].split('sourceURL=')[1]].add('desired')
            return {'data':{'result':None}}
        return {'data':{'tabs':[{'tabId':tab,'url':'https://same.test/','active':tab==selected} for tab in ('t1','t2')]}}
    monkeypatch.setattr(cdp,'call',command);monkeypatch.setattr(driver,'_invoke',invoke)
    page=await driver.active_page(cdp,target_id='desired')
    assert page.target_id=='desired' and page.tab_id=='t1'
    assert commands[1]==['tab','t1']


@pytest.mark.parametrize('binary', [b'reference-build', b'recompiled-browser'])
@pytest.mark.parametrize('payload_matches_source', [True, False])
@pytest.mark.parametrize('overlay_matches_pin', [True, False])
def test_browser_image_preflight_enforces_source_pins_and_payload_integrity(tmp_path, monkeypatch, binary, payload_matches_source, overlay_matches_pin):
    """Require source integrity and functional capture from the staged executable."""
    import hashlib
    root, chromium, overlay = (tmp_path / name for name in ('bench', 'chromium', 'overlay'))
    protocol = b'domain ChromiumRL\n'
    settings = {'chromium_version': '152.0.7948.0', 'overlay_revision': 'a' * 40,
        'protocol_sha256': hashlib.sha256(protocol).hexdigest()}
    for path, content in {
        root / 'protocol/browser-build.json': json.dumps(settings).encode(),
        root / 'protocol/ChromiumRL.pdl': protocol,
        root / 'build/chrome': binary if payload_matches_source else b'different-staged-browser',
        chromium / 'out/Release/chrome': binary,
        chromium / 'chrome/VERSION': b'MAJOR=152\nMINOR=0\nBUILD=7948\nPATCH=0\n',
        chromium / 'third_party/blink/public/devtools_protocol/domains/ChromiumRL.pdl': protocol,
        overlay / 'src/overlay.cc': b'local-overlay', chromium / 'overlay.cc': b'local-overlay',
    }.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    def local_git(command, **kwargs):
        assert command[:2] == ['git', '-C']
        if 'rev-parse' in command:
            return ('a' if overlay_matches_pin else 'c') * 40 if Path(command[2]) == overlay else 'b' * 40
        if 'status' in command:
            return ''
        if 'ls-files' in command:
            return b'src/overlay.cc\0'
        raise AssertionError(f'Unexpected source operation: {command}')
    monkeypatch.setattr(subprocess, 'check_output', local_git)
    def staged_browser(command, **kwargs):
        assert '--remote-debugging-pipe' in command and '--headless' in command
        assert kwargs['start_new_session'] is True
        assert str(root / 'build/chrome') in command
        reader = os.dup(kwargs['pass_fds'][0])
        snapshot = {'nodes': [{'directText': 'ChromiumRL build check'}]}
        replies = [{'result': {'targetId': 'fixture'}}, {'result': {'sessionId': 'session'}},
            {'result': {'result': {'value': True}}}, {'result': {'sessionId': 'trace'}},
            {'result': {'snapshot': snapshot}}, {'result': {'modelDOM': {
                'sections': [{'name': 'content', 'lines': ['ChromiumRL build check']}]}}},
            {'result': {'data': base64.b64encode(b'\x89PNG\r\n\x1a\n').decode()}}]
        if binary == b'reference-build':
            replies[3] = {'error': {'code': -32601, 'message': "'ChromiumRL.enable' wasn't found"}}
        os.write(kwargs['pass_fds'][1], b''.join(
            json.dumps({'id': index, **reply}).encode() + b'\0' for index, reply in enumerate(replies, 1)))
        def stop_group(pid, action):
            import signal
            assert pid == 987654321 and action == signal.SIGKILL
            requests = [json.loads(row) for row in os.read(reader, 65536).split(b'\0') if row]
            assert requests[-1]['method'] == 'Browser.close'
            os.close(reader)
        monkeypatch.setattr(os, 'killpg', stop_group)
        return SimpleNamespace(pid=987654321, wait=lambda timeout: 0)
    monkeypatch.setattr(subprocess, 'Popen', staged_browser)
    monkeypatch.setattr('sys.argv', ['preflight', str(root), str(chromium), str(overlay)])
    script = (Path(__file__).resolve().parents[2] / 'scripts/build-browser-image').read_text()
    program = script.split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
    if not overlay_matches_pin:
        with pytest.raises(SystemExit, match='Browser overlay revision differs from protocol/browser-build.json'):
            exec(compile(program, 'browser-image-preflight', 'exec'), {})
        assert not (root / 'build/browser-build.json').exists()
    elif not payload_matches_source:
        with pytest.raises(SystemExit, match='Copied browser differs from the Chromium Release binary'):
            exec(compile(program, 'browser-image-preflight', 'exec'), {})
        assert not (root / 'build/browser-build.json').exists()
    elif binary == b'reference-build':
        with pytest.raises(SystemExit, match='Staged browser ChromiumRL.enable failed'):
            exec(compile(program, 'browser-image-preflight', 'exec'), {})
        assert not (root / 'build/browser-build.json').exists()
    else:
        exec(compile(program, 'browser-image-preflight', 'exec'), {})
        receipt = json.loads((root / 'build/browser-build.json').read_text())
        assert receipt['binary_sha256'] == hashlib.sha256(binary).hexdigest()
        assert receipt['overlay_revision'] == settings['overlay_revision']
        assert receipt['capability_check'] == {'methods': ['ChromiumRL.enable',
            'ChromiumRL.captureStructuredSnapshot', 'ChromiumRL.getModelDOM', 'Page.captureScreenshot'],
            'local_fixture': 'passed'}

@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_empty_pdf_export_is_paired_and_actor_continues(empty_dom_pair, mode):
    from w8bench.task_recorder.prepare_verifier_data import inspect_recording
    paths, payloads, *_ = empty_dom_pair
    recording = inspect_recording(paths[mode])
    assert recording["final"]["run_status"] == "completed"
    assert len(payloads[mode]) > 1
    assert recording["coverage"]["eligible_fraction"] == 1
    assert recording["coverage"]["format_gaps"] == {"screenshot": [], "dom_model": []}
    for state in recording["manifest"]["states"]:
        info = state["capture"]
        assert info["paired_complete"]
        assert info["document_mime_type"] == "application/pdf"
        assert info["document_ready_state"] == "complete"
        assert info["dom_export"] == {"status": "empty", "marker": capture.EMPTY_DOM_MARKER,
            "stats": {"rawNodes": 10, "returnedNodes": 0, "textChars": 0,
                "droppedHidden": 9, "truncated": False}}
        assert capture.EMPTY_DOM_MARKER in (paths[mode]/state["directory"]/"dom_model.txt").read_text()
    wire = json.dumps(payloads[mode])
    assert "application/pdf" not in wire and "readiness" not in wire
    assert (capture.EMPTY_DOM_MARKER in wire) == (mode == "dom")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
@pytest.mark.parametrize("condition", ["pdf", "slow", "never", "same_document", "reload", "redirect"])
async def test_document_readiness_before_both_capture_paths(tmp_path, monkeypatch, mode, condition):
    client = capture.CDPClient("http://unused", timeout=.02, observation_mode=mode, viewport=(1365, 768))
    client.target = {"targetId": "exact-target"}
    calls, waited = [], []
    state = {"ready": "loading" if condition in {"slow", "never"} else "complete", "loader": "first"}
    original = FakeCDP(observation_mode=mode)
    async def call(method, params=None, **kwargs):
        calls.append((method, params))
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "exact-frame", "loaderId": state["loader"],
                "url": "https://example.test", "mimeType": "application/pdf" if condition == "pdf" else "text/html"}}}
        if method == "Page.createIsolatedWorld":
            assert params["frameId"] == "exact-frame"
            return {"executionContextId": 42}
        if method == "Runtime.evaluate":
            if "document.readyState" not in params["expression"]:
                return {"result": {"value": {"count": 0, "openShadowRoots": 0}}}
            if params.get("awaitPromise"):
                assert params["contextId"] == 42
                assert "DOMContentLoaded" in params["expression"]
                assert params["expression"].count("requestAnimationFrame") == 2
                waited.append(state["loader"])
                if condition == "never":
                    await asyncio.Event().wait()
                if condition == "slow":
                    await asyncio.sleep(.001)
                    state["ready"] = "interactive"
                if condition == "redirect" and state["loader"] == "first":
                    state["loader"] = "redirected"
                    raise capture.CDPError(method, {"code": -32000, "message": "Execution context was destroyed"})
            return {"result": {"value": {"ready_state": state["ready"],
                "mime_type": "application/pdf" if condition == "pdf" else "text/html"}}}
        if method == "ChromiumRL.captureStructuredSnapshot":
            assert waited  # nothing is acquired until readiness completes or expires
            return {"snapshot": {"url": "https://example.test", "nodes": [] if condition in {"pdf", "never"} else [{"ref": "n1"}],
                "stats": {"rawNodes": 10, "returnedNodes": 0 if condition in {"pdf", "never"} else 1}}}
        return await original.call(method, params, **kwargs)
    monkeypatch.setattr(client, "call", call)
    bundle = await capture.capture_bundle(client, tmp_path/"first", max_nodes=7000, max_text_chars=200000,
        observation_mode=mode)
    info = bundle.capture_metadata
    assert info["paired_complete"]
    assert info["readiness"]["timeout_seconds"] == client.timeout
    assert info["readiness"]["status"] == ("timeout" if condition == "never" else "ready")
    assert info["readiness"]["wait_seconds"] >= 0
    assert info["document_ready_state"] == state["ready"]
    assert info["dom_export"]["status"] == ("empty" if condition in {"pdf", "never"} else "content")
    if condition in {"same_document", "reload", "never"}:
        before = len(waited)
        if condition == "reload":
            state["loader"] = "second"
        else:
            client.navigation_events.append({"method": "Page.navigatedWithinDocument"})
        following = await capture.capture_bundle(client, tmp_path/"following", max_nodes=7000,
            max_text_chars=200000, observation_mode=mode)
        assert len(waited) == before + (condition == "reload")
        assert following.capture_metadata["readiness"]["status"] == ("ready" if condition == "reload" else "same_document")
    if condition == "redirect":
        assert waited == ["first", "redirected"]
        assert info["readiness"]["loader_id"] == "redirected"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
@pytest.mark.parametrize("failure", ["internal", "crash", "transport", "destroyed"])
async def test_readiness_never_swallows_real_browser_failures(tmp_path, monkeypatch, mode, failure):
    client = capture.CDPClient("http://unused", observation_mode=mode)
    client.target = {"targetId": "one"}
    async def call(method, params=None, **kwargs):
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "one", "loaderId": "doc"}}}
        if method == "Page.createIsolatedWorld":
            return {"executionContextId": 7}
        if method == "Runtime.evaluate":
            if failure == "internal":
                raise capture.CDPError(method, {"code": -32603, "message": "internal failure"})
            error = RunnerError({"crash": "page target crashed", "transport": "CDP websocket closed",
                "destroyed": "page target destroyed"}[failure])
            error.technical_failure_class = "browser_crash" if failure == "crash" else "cdp_stall"
            raise error
        return {}
    monkeypatch.setattr(client, "call", call)
    with pytest.raises((RunnerError, capture.CDPError)):
        await capture.capture_bundle(client, tmp_path/"failed", max_nodes=7000, max_text_chars=200000,
            observation_mode=mode)
    assert not (tmp_path/"failed/screenshot.png").exists()

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
async def test_readiness_deadline_navigation_records_current_loader_without_waiting_again(tmp_path, monkeypatch, mode):
    client = capture.CDPClient("http://unused", timeout=.01, observation_mode=mode)
    client.target = {"targetId": "one"}
    current = {"loader": "first", "waits": 0}
    fallback = FakeCDP(observation_mode=mode)
    async def call(method, params=None, **kwargs):
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "main", "loaderId": current["loader"],
                "mimeType": "text/html", "url": "https://example.test"}}}
        if method == "Runtime.evaluate" and "document.readyState" in params.get("expression", ""):
            if params.get("awaitPromise"):
                current.update(loader="second", waits=current["waits"]+1)
                await asyncio.Event().wait()
            return {"result": {"value": {"ready_state": "loading", "mime_type": "text/html"}}}
        return await fallback.call(method, params, **kwargs)
    monkeypatch.setattr(client, "call", call)
    first = await capture.capture_bundle(client, tmp_path/"first", max_nodes=7000,
        max_text_chars=200000, observation_mode=mode)
    assert first.capture_metadata["readiness"]["status"] == "timeout"
    assert first.capture_metadata["readiness"]["loader_id"] == "second"
    assert first.capture_metadata["paired_complete"]
    again = await capture.capture_bundle(client, tmp_path/"again", max_nodes=7000,
        max_text_chars=200000, observation_mode=mode)
    assert again.capture_metadata["readiness"]["status"] == "same_document"
    assert current["waits"] == 1
