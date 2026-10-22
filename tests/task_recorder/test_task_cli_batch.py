import io
import json
import signal
import subprocess
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from w8bench.task_recorder import task_cli


CATALOG_URL = "https://catalog.example/tasks.jsonl"
ROWS = [
    {
        "task_id": task_id,
        "category": f"lookup {index}",
        "instruction": f"Read page {index}.",
        "start_url": f"https://example.test/{index}",
        "stopping_condition": "Stop after recording the heading.",
        "constraints": ["Do not sign in."],
    }
    for index, task_id in enumerate(("browser_task_009", "browser_task_002", "custom-check"))
]


def _argv(tmp_path, *extra):
    return [
        "--all", "--output-dir", str(tmp_path / "recordings"),
        "--env-file", str(tmp_path / "empty.env"),
        "--catalog-url", CATALOG_URL, *extra,
    ]


def _summary(capsys):
    output = capsys.readouterr()
    return json.loads(output.out[output.out.index("{\n"):])


def test_batch_downloads_once_and_dry_run_has_no_browser_or_file_writes(tmp_path, monkeypatch, capsys):
    requests = []

    def download(request, *, timeout):
        requests.append(request)
        assert timeout == 30
        return io.BytesIO("\n".join(json.dumps(row) for row in ROWS).encode())

    def unexpected_browser(*args, **kwargs):
        pytest.fail("--dry-run must not start or stop browser processes")

    monkeypatch.setattr(task_cli.urllib.request, "urlopen", download)
    monkeypatch.setattr(task_cli.subprocess, "Popen", unexpected_browser)
    monkeypatch.setattr(task_cli, "task_transition_lock", unexpected_browser)
    monkeypatch.setenv("TASK_CATALOG_TOKEN", "fixture-token")
    assert task_cli.main(_argv(tmp_path, "--dry-run")) == 0
    assert len(requests) == 1
    assert requests[0].full_url == CATALOG_URL
    assert requests[0].get_header("Authorization") == "Bearer fixture-token"
    summary = _summary(capsys)
    assert summary["mode"] == "dry_run"
    assert summary["selected_tasks"] == 3
    assert summary["failed_tasks"] == 0
    assert [item["task_id"] for item in summary["results"]] == [row["task_id"] for row in ROWS]
    assert not list(tmp_path.iterdir())


def test_batch_waits_between_tasks_and_preserves_options_and_provenance(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(task_cli, "fetch_task_catalog", lambda *a, **kw: ROWS)
    monkeypatch.setattr(task_cli, "task_transition_lock", nullcontext)
    monkeypatch.setattr(task_cli, "stop_previous_run", lambda **kw: {"status": "none"})
    monkeypatch.setattr(task_cli, "claim_browser_profile_provenance", lambda name: {})
    monkeypatch.setattr(task_cli, "browser_container_cdp_url", lambda name: "http://127.0.0.1:9222")
    monkeypatch.setattr(task_cli, "process_start_ticks", lambda pid: 1)
    monkeypatch.setattr(task_cli, "write_active_run", lambda record: None)
    monkeypatch.setattr(task_cli, "clear_active_run", lambda pid: None)
    sequence, commands = [], []

    def restart(env_file):
        # Each preceding runner must have finished before the next restart.
        assert len(commands) == sequence.count("wait")
        sequence.append("restart")

    def launch(command, **kwargs):
        assert len(commands) == sequence.count("wait")
        index = len(commands)
        commands.append(command)
        sequence.append("launch")
        assert kwargs["start_new_session"] is True

        def wait():
            sequence.append("wait")
            return (0, 2, 0)[index]

        return SimpleNamespace(pid=100 + index, wait=wait)

    monkeypatch.setattr(task_cli, "restart_browser_service", restart)
    monkeypatch.setattr(task_cli.subprocess, "Popen", launch)
    assert task_cli.main(_argv(
        tmp_path, "--no-human-intervention", "--max-steps", "17", "--model", "fixture-model",
    )) == 1
    assert sequence == ["restart", "launch", "wait"] * 3
    for command, row in zip(commands, ROWS):
        assert command[command.index("--source-task-id") + 1] == row["task_id"]
        assert command[command.index("--source-catalog") + 1] == CATALOG_URL
        assert command[command.index("--output-dir") + 1] == str(tmp_path / "recordings")
        assert command[command.index("--max-steps") + 1] == "17"
        assert command[command.index("--model") + 1] == "fixture-model"
        assert "--allow-human-intervention" not in command
        instruction = command[command.index("--task") + 1]
        assert row["instruction"] in instruction
        assert row["stopping_condition"] in instruction
        assert row["constraints"][0] in instruction
    summary = _summary(capsys)
    assert summary["successful_tasks"] == 2
    assert summary["failed_tasks"] == 1
    assert summary["attempted_tasks"] == 3
    assert summary["interrupted"] is False


def test_batch_continues_after_setup_and_definition_errors(tmp_path, monkeypatch, capsys):
    rows = [dict(row) for row in ROWS]
    rows[0]["start_url"] = "invalid-url"
    monkeypatch.setattr(task_cli, "fetch_task_catalog", lambda *a, **kw: rows)
    attempted = []

    def run(args, definition, *, task_id):
        attempted.append(task_id)
        if len(attempted) == 1:
            raise OSError("fixture browser startup failed")
        return 0

    monkeypatch.setattr(task_cli, "run_task", run)
    assert task_cli.main(_argv(tmp_path)) == 1
    assert attempted == [row["task_id"] for row in ROWS[1:]]
    summary = _summary(capsys)
    assert summary["failed_tasks"] == 2
    assert summary["successful_tasks"] == 1
    assert "absolute HTTP(S) URL" in summary["results"][0]["error"]
    assert "startup failed" in summary["results"][1]["error"]


@pytest.mark.parametrize("stop", [KeyboardInterrupt(), 130, -signal.SIGINT, -signal.SIGTERM])
def test_batch_stops_after_interruption(tmp_path, monkeypatch, capsys, stop):
    monkeypatch.setattr(task_cli, "fetch_task_catalog", lambda *a, **kw: ROWS)
    attempted = []

    def run(args, definition, *, task_id):
        attempted.append(task_id)
        if isinstance(stop, BaseException):
            raise stop
        return stop

    monkeypatch.setattr(task_cli, "run_task", run)
    assert task_cli.main(_argv(tmp_path)) == 130
    assert attempted == [ROWS[0]["task_id"]]
    summary = _summary(capsys)
    assert summary["interrupted"] is True
    assert summary["attempted_tasks"] == 1


@pytest.mark.parametrize("timeout", [False, True])
def test_interrupt_stops_current_runner_and_clears_ownership(tmp_path, monkeypatch, timeout):
    args = task_cli.parse_args(_argv(tmp_path))
    monkeypatch.setattr(task_cli, "task_transition_lock", nullcontext)
    monkeypatch.setattr(task_cli, "stop_previous_run", lambda **kw: {"status": "none"})
    monkeypatch.setattr(task_cli, "restart_browser_service", lambda path: None)
    monkeypatch.setattr(task_cli, "claim_browser_profile_provenance", lambda name: {})
    monkeypatch.setattr(task_cli, "browser_container_cdp_url", lambda name: "http://127.0.0.1:9222")
    monkeypatch.setattr(task_cli, "process_start_ticks", lambda pid: 1)
    monkeypatch.setattr(task_cli, "write_active_run", lambda record: None)
    waits, signals, cleared = [], [], []

    def wait(**kwargs):
        waits.append(kwargs)
        if len(waits) == 1:
            raise KeyboardInterrupt
        if timeout and len(waits) == 2:
            raise subprocess.TimeoutExpired("fixture", 15)
        return -signal.SIGTERM

    process = SimpleNamespace(pid=101, wait=wait)
    monkeypatch.setattr(task_cli.subprocess, "Popen", lambda *a, **kw: process)
    monkeypatch.setattr(task_cli.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(task_cli, "clear_active_run", cleared.append)
    with pytest.raises(KeyboardInterrupt):
        task_cli.run_task(args, task_cli.catalog_task_definition(ROWS[0], CATALOG_URL), task_id="task1")
    assert signals == [(101, signal.SIGTERM)] + ([(101, signal.SIGKILL)] if timeout else [])
    assert cleared == [101]


@pytest.mark.parametrize("selection", [
    [], ["--all", "task1"], ["--all", "task1", "custom name"],
    ["--all", "--task", "manual instruction"],
    ["--all", "--start-url", "https://example.test"],
])
def test_selector_is_required_and_all_rejects_single_task_overrides(tmp_path, selection):
    with pytest.raises(SystemExit) as error:
        task_cli.parse_args([*selection, "--output-dir", str(tmp_path)])
    assert error.value.code == 2
