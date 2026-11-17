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
    monkeypatch.setattr(browser_runtime, "get_json", lambda url: {"Browser": "Fixture Chromium"})
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
    monkeypatch.setattr(browser_runtime, "get_json", lambda url: {})
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
    assert set(capture.action_progress(before, after)) == {"made_progress", "screenshot_changed"}
    seen = []
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self,payload: seen.append(payload) or
        {"model": "gemini-3.1-pro-preview", "output_text": '{"action":"wait","seconds":0,"thought":"observe"}'})
    asyncio.run(runner.ModelClient("unused", "gemini-3.1-pro-preview", "unused").decide(task="Inspect page", step=1,
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
                        bundle = await capture.attach_agent_browser_observation(bundle, driver, cdp)
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
    assert capture.action_progress(before, after)["made_progress"] is False
    seen = []
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self, payload: seen.append(payload) or
        {"model": "gemini-3.1-pro-preview", "output_text": '{"action":"wait","seconds":0,"thought":"observe"}'})
    asyncio.run(runner.ModelClient("unused", "gemini-3.1-pro-preview", "unused").decide(task="Inspect page", step=1,
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
            url = ("https://example.test/changed" if navigation_kind == "different_url" and len(frame_calls) > 1
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
    assert metadata["capture_order"] == ["structured_dom", "dom_model_artifacts", "screenshot"]
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
    run = tmp_path / "run"
    bundle, reconnects = asyncio.run(capture.capture_after_action_bundle(
        FakeCDP(observation_mode="screenshot"), None, run / "steps" / "step_001", max_nodes=100,
        max_text_chars=1000, observation_mode="screenshot", attempts=2))
    assert bundle.capture_metadata["paired_complete"]
    assert len(reconnects) == 1 and synchronize.await_count == 1
    failures = [json.loads(line) for line in (run / "capture_failures.jsonl").read_text().splitlines()]
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
        "EVIDENCE_AUDIT_PROVIDER=openai\nEVIDENCE_ADJUDICATOR_PROVIDER=google\nGEMINI_API_KEY=\n"
        "TASK_CATALOG_FILE=tasks.jsonl\n")
    path = tmp_path / "fresh.env"
    assert browser_runtime.configure(path, False) == 0
    values = browser_runtime.read_env(path)
    assert values["ACTOR_MODEL"] == "actor-from-template"
    assert values["EVIDENCE_AUDIT_MODEL"] == "inventory-from-template"
    assert values["EVIDENCE_ADJUDICATOR_MODEL"] == "adjudicator-from-template"
    assert values["EVIDENCE_AUDIT_PROVIDER"] == "openai"
    assert values["EVIDENCE_ADJUDICATOR_PROVIDER"] == "google"
    assert values["GEMINI_API_KEY"] == ""
    assert values["TASK_CATALOG_FILE"] == "tasks.jsonl"
    output = capsys.readouterr().out
    assert "Set OPENAI_API_KEY and GEMINI_API_KEY credentials" in output
    assert "Edit OPENAI_API_KEY and ACTOR_MODEL" not in output

@pytest.mark.usefixtures("no_network")
def test_runtime_port_refresh_preserves_audit_settings_and_fake_credentials(tmp_path, monkeypatch, capsys):
    from w8bench.task_recorder import browser_runtime
    monkeypatch.setattr(browser_runtime, "ROOT", tmp_path)
    monkeypatch.setattr(browser_runtime, "choose_port", lambda preferred, used: preferred)
    monkeypatch.setattr(browser_runtime, "unique_container_name", lambda base: base)
    (tmp_path / ".env.example").write_text("ACTOR_MODEL=gemini-3.1-pro-preview\n"
        "EVIDENCE_AUDIT_MODEL=template-inventory\nEVIDENCE_ADJUDICATOR_MODEL=template-adjudicator\n"
        "TASK_CATALOG_FILE=tasks.jsonl\n")
    path = tmp_path / "existing.env"
    expected = {"ACTOR_MODEL": "gemini-3.1-pro-preview", "OPENAI_API_KEY": "fake-openai-test-value",
        "GEMINI_API_KEY": "fake-google-test-value", "EVIDENCE_AUDIT_MODEL": "configured-inventory",
        "EVIDENCE_ADJUDICATOR_MODEL": "configured-adjudicator", "EVIDENCE_AUDIT_PROVIDER": "openai",
        "EVIDENCE_ADJUDICATOR_PROVIDER": "google", "CONTAINER_NAME": "owned-browser",
        "TASK_CATALOG_FILE": "existing-tasks.jsonl"}
    path.write_text("".join(f"{key}={value}\n" for key, value in expected.items()))
    assert browser_runtime.configure(path, True) == 0
    actual = browser_runtime.read_env(path)
    assert {key: actual[key] for key in expected} == expected
    output = capsys.readouterr().out
    assert expected["OPENAI_API_KEY"] not in output and expected["GEMINI_API_KEY"] not in output
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
    cdp = SimpleNamespace(call=AsyncMock(side_effect=[TimeoutError()] * failures + [{"captured": True}]))
    sleep = AsyncMock()
    monkeypatch.setattr(capture.asyncio, "sleep", sleep)
    pending = capture.capture_call(cdp, "Read.fixture", {"viewport": True})
    if failures == 2:
        with pytest.raises(RunnerError, match="Read.fixture timed out after 2 attempts") as caught:
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
