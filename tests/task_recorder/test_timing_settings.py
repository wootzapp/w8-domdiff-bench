"""CLI timing settings have finite bounds before any browser or process work."""

import pytest

from w8bench.task_recorder import runner, task_cli
from w8bench.task_recorder.runtime import status, wait


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
