"""Host status follows the display stack in the inspected container."""

import json
from types import SimpleNamespace

import pytest

from w8bench.task_recorder import browser_runtime
from w8bench.task_recorder.runtime import status as container_status


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
