"""Scheduled execution, ownership and interruption contracts."""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace

import pytest

from w8bench.task_recorder import runner, task_cli
from w8bench.task_recorder.recorder_support import RunnerError, write_json, write_json_lines
from w8bench.verifier.run_full_comparison import main as compare_main


@pytest.mark.usefixtures('no_network')
def test_launcher_refuses_to_recreate_another_checkouts_service(tmp_path, monkeypatch):
    from types import SimpleNamespace
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if 'config' in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"name": "copied-project",
                "services": {"w8-core": {"container_name": "new-name"}}}), stderr="")
        if command[1:3] == ['ps', '-aq']:
            return SimpleNamespace(returncode=0, stdout='existing-service-id\n', stderr="")
        if command[1] == 'inspect':
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"Config": {"Labels": {
                "com.docker.compose.project.working_dir": "/another/checkout",
                "com.docker.compose.project": "copied-project",
                "com.docker.compose.service": "w8-core"}}}]), stderr="")
        raise AssertionError("a foreign service must never reach a Docker mutation")
    monkeypatch.setattr(task_cli.subprocess, 'run', run)
    with pytest.raises(RunnerError, match='another checkout'):
        task_cli.restart_browser_service(tmp_path / '.env')
    assert not any('up' in command for command in calls)

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("trials", [1, 2, 5])
def test_batch_schedules_arbitrary_trials_before_start_and_resumes(tmp_path, monkeypatch, trials):
    from types import SimpleNamespace
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text("\n".join(json.dumps({"task_id": identity, "instruction": "Read the heading.",
        "start_url": "https://example.test"}) for identity in ("custom_a", "custom_b")) + "\n")
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", runtime)
    monkeypatch.setattr(task_cli, "ACTIVE_RUN_PATH", runtime / "active-run.json")
    # read_active_run's default path is bound when the module is imported.
    monkeypatch.setattr(task_cli, "read_active_run", lambda: {"pid": 999999, "run_id": "stale"})
    monkeypatch.setattr(task_cli, "owned_process_group", lambda record: None)
    runtime.mkdir()
    (runtime / "active-run.json").write_text("{}")
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    for raw in catalog.read_text().splitlines():
        row = json.loads(raw)
        write_json(rubrics / f"{row['task_id']}.json", {**row,
            "criteria": [{"id": "heading", "description": "Read the heading."}]})
    output = tmp_path / "recordings"
    arguments = ["--trials", str(trials), "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gpt-6.1-sol", "--output-dir", str(output),
        "--run-name", "batch", "--env-file", str(tmp_path / "absent.env"), "--model", "gemini-3.1-pro-preview"]
    ledger = output / "batch" / "ledger.jsonl"
    calls = []
    def run(command, **kwargs):
        rows = [json.loads(line) for line in ledger.read_text().splitlines()]
        assert len(rows) == 2 * 2 * trials  # Full denominator exists before the first subprocess.
        current = rows[len(calls)]
        assert current["catalog_sha256"] == hashlib.sha256(catalog.read_bytes()).hexdigest()
        assert current["task"]["catalog_sha256"] == current["catalog_sha256"]
        assert Path(current["task"]["source_catalog"]).read_bytes() == catalog.read_bytes()
        assert current["technical_outcome"] == "running"
        assert command[2] == "w8bench.task_recorder.task_cli"
        assert command[3] == current["task_id"]
        assert command[command.index("--observation-mode") + 1] == current["arm"]
        calls.append(current)
        return SimpleNamespace(returncode=1)  # Startup failure: no recording created.
    monkeypatch.setattr(task_cli.subprocess, "run", run)
    assert task_cli.main(arguments + ["--dry-run"]) == 0
    assert calls == []
    assert not (runtime / "active-run.json").exists()
    assert task_cli.main(arguments) == 0
    assert len(calls) == 4 * trials
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    for index in range(0, len(rows), 2):
        first, second = rows[index:index + 2]
        assert (first["task_id"], first["trial"]) == (second["task_id"], second["trial"])
        assert {first["arm"], second["arm"]} == {"dom", "screenshot"}
        assert [first["arm_order"], second["arm_order"]] == [1, 2]
        expected = "dom" if (index // 2 % 2 + first["trial"] - 1) % 2 == 0 else "screenshot"
        assert first["arm"] == expected
    assert all(row["completed"] and row["technical_outcome"] == "startup_failure" for row in rows)
    assert task_cli.main(arguments) == 0
    assert len(calls) == 4 * trials  # Finished failures are outcomes, not implicit retries.
    report = tmp_path / "empty-recordings-report"
    assert compare_main(["--ledger", str(ledger), "--output", str(report)]) == 0
    summary = json.loads((report / "summary.json").read_text())
    assert summary["scheduled_attempts"] == 4 * trials
    assert summary["paired_attempts"] == 0
    assert len(summary["unmatched_arms"]) == 4 * trials
    for mode in ("dom", "screenshot"):
        assert summary["modes"][mode]["attempted_runs"] == 2 * trials
        assert summary["modes"][mode]["completion_counts"] == {"ungraded": 2 * trials}
    with pytest.raises(RunnerError, match="configuration differs"):
        task_cli.main(arguments + ["--max-turns", "17"])

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("trials", [0, -1])
def test_batch_rejects_nonpositive_trial_count(tmp_path, trials):
    with pytest.raises(RunnerError, match="positive --trials"):
        task_cli.main(["--trials", str(trials), "--catalog-file", str(tmp_path / "missing.jsonl"),
            "--output-dir", str(tmp_path / "recordings"), "--env-file", str(tmp_path / "absent.env")])

@pytest.mark.usefixtures('no_network')
def test_batch_resume_retains_dead_started_attempt_and_runs_pending_rows(tmp_path, monkeypatch):
    from types import SimpleNamespace
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test"}) + "\n")
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    for raw in catalog.read_text().splitlines():
        row = json.loads(raw)
        write_json(rubrics / f"{row['task_id']}.json", {**row,
            "criteria": [{"id": "heading", "description": "Read the heading."}]})
    output = tmp_path / "recordings"
    arguments = ["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gpt-6.1-sol", "--output-dir", str(output),
        "--run-name", "resumed", "--env-file", str(tmp_path / "absent.env"), "--model", "gemini-3.1-pro-preview"]
    assert task_cli.main(arguments + ["--dry-run"]) == 0
    ledger = output / "resumed" / "ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    rows[0]["technical_outcome"] = "running"
    rows[0]["launcher_pid"] = 999999
    write_json_lines(ledger, rows)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(task_cli.subprocess, "run", run)
    assert task_cli.main(arguments) == 0
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(calls) == 1
    assert rows[0]["completed"] and rows[0]["technical_outcome"] == "interrupted"
    assert rows[1]["completed"] and rows[1]["technical_outcome"] == "startup_failure"

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("option,value", [("--max-turns", "0"), ("--max-output-tokens", "0"),
    ("--viewport-width", "-1")])
def test_batch_rejects_invalid_shared_controls_before_scheduling(tmp_path, option, value):
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test"}) + "\n")
    output = tmp_path / "recordings"
    with pytest.raises(RunnerError, match="positive"):
        task_cli.main(["--trials", "1", "--catalog-file", str(catalog), "--output-dir", str(output),
            "--run-name", "bad", "--dry-run", "--env-file", str(tmp_path / "absent.env"), option, value])
    assert not (output / "bad" / "ledger.jsonl").exists()

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("failure", ["exception", "nonzero_exit"])
def test_batch_grading_error_does_not_abort_or_replace_actor_outcome(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test"}) + "\n")
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    write_json(rubrics / "custom.json", {"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test", "criteria": [{"id": "heading", "description": "Read heading."}]})
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    output = tmp_path / "recordings"
    actors, judges, events = [], [], []
    def run(command, **kwargs):
        if command[2] == "w8bench.task_recorder.task_cli":
            mode = command[command.index("--observation-mode") + 1]
            run_name = command[command.index("--run-name") + 1]
            root = Path(command[command.index("--output-dir") + 1])
            directory = root / run_name / mode / "custom"
            write_json(directory / "final.json", {"run_status": "completed"})
            actors.append(mode)
            events.append("actor")
            return SimpleNamespace(returncode=0)
        assert command[2] == "w8bench.verifier.run_comparison"
        judges.append(command)
        events.append("judge")
        if failure == "exception":
            raise OSError("injected judge startup error")
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(task_cli.subprocess, "run", run)
    assert task_cli.main(["custom", "--trials", "1", "--catalog-file", str(catalog),
        "--rubric-dir", str(rubrics), "--judge-model", "gpt-6.1-sol", "--output-dir", str(output),
        "--run-name", "judging", "--env-file", str(tmp_path / "absent.env"), "--model", "gemini-3.1-pro-preview"]) == 0
    rows = [json.loads(line) for line in (output / "judging" / "ledger.jsonl").read_text().splitlines()]
    assert actors == ["dom", "screenshot"]
    assert len(judges) == 2
    assert events == ["actor", "actor", "judge", "judge"]
    assert all(row["completed"] and row["technical_outcome"] == "completed" for row in rows)
    assert all(row["grade_outcome"] == "grading_error" for row in rows)

@pytest.mark.usefixtures('no_network')
def test_batch_keyboard_interrupt_during_judge_preserves_actor_outcome(tmp_path, monkeypatch):
    from types import SimpleNamespace
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test"}) + "\n")
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    write_json(rubrics / "custom.json", {"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test", "criteria": [{"id": "heading", "description": "Read heading."}]})
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    output = tmp_path / "recordings"
    events = []
    def run(command, **kwargs):
        if command[2] == "w8bench.task_recorder.task_cli":
            mode = command[command.index("--observation-mode") + 1]
            name = command[command.index("--run-name") + 1]
            root = Path(command[command.index("--output-dir") + 1])
            write_json(root / name / mode / "custom" / "final.json", {"run_status": "completed"})
            events.append("actor")
            return SimpleNamespace(returncode=0)
        events.append("judge")
        raise KeyboardInterrupt()
    monkeypatch.setattr(task_cli.subprocess, "run", run)
    with pytest.raises(KeyboardInterrupt):
        task_cli.main(["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
            "--judge-model", "gpt-6.1-sol", "--output-dir", str(output), "--run-name", "interrupted_judge",
            "--env-file", str(tmp_path / "absent.env"), "--model", "gemini-3.1-pro-preview"])
    assert events == ["actor", "actor", "judge"]
    rows = [json.loads(line) for line in (output / "interrupted_judge" / "ledger.jsonl").read_text().splitlines()]
    assert all(row["technical_outcome"] == "completed" for row in rows)
    assert rows[0]["grade_outcome"] == "interrupted"
    assert rows[0]["completed"] is True

@pytest.mark.usefixtures('no_network')
def test_batch_resume_refuses_live_owned_recorder(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test"}) + "\n")
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    for raw in catalog.read_text().splitlines():
        row = json.loads(raw)
        write_json(rubrics / f"{row['task_id']}.json", {**row,
            "criteria": [{"id": "heading", "description": "Read the heading."}]})
    output = tmp_path / "recordings"
    arguments = ["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gpt-6.1-sol", "--output-dir", str(output),
        "--run-name", "live", "--env-file", str(tmp_path / "absent.env"), "--model", "gemini-3.1-pro-preview"]
    assert task_cli.main(arguments + ["--dry-run"]) == 0
    ledger = output / "live" / "ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    rows[0].update(technical_outcome="running", started_at="2026-11-12T00:00:00Z")
    write_json_lines(ledger, rows)
    original = ledger.read_bytes()
    monkeypatch.setattr(task_cli, "read_active_run", lambda: {"pid": 12345})
    monkeypatch.setattr(task_cli, "owned_process_group", lambda record: (12345, 12345))
    def forbidden(*args, **kwargs):
        raise AssertionError("resume must not launch while the owned recorder is live")
    monkeypatch.setattr(task_cli.subprocess, "run", forbidden)
    with pytest.raises(RunnerError, match="live|active|running"):
        task_cli.main(arguments)
    assert ledger.read_bytes() == original

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("judge", [None, "gemini-3.1-pro-preview", "gpt-5.6"])
def test_batch_completion_judge_is_explicit_and_cannot_fall_back_to_actor(tmp_path, monkeypatch, judge):
    arguments = ["--trials", "1", "--rubric-dir", str(tmp_path/"rubrics"),
        "--output-dir", str(tmp_path/"out"), "--env-file", str(tmp_path/"absent.env"), "--dry-run"]
    if judge is not None:arguments += ["--judge-model", judge]
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *a,**k: pytest.fail("invalid judge started a child"))
    with pytest.raises(RunnerError, match="completion.*judge|completion grading"):
        task_cli.main(arguments)
    assert not (tmp_path/"out").exists()

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("dry_run,judge", [(False, None), (False, "gpt-6.1-sol"), (True, None)])
def test_batch_execution_requires_frozen_rubrics_and_planning_requires_judge(tmp_path, judge, dry_run):
    arguments = ["--trials", "1", "--env-file", str(tmp_path / "absent.env"), "--output-dir", str(tmp_path / "recordings")]
    if judge is not None:
        arguments += ["--judge-model", judge]
    if dry_run:
        arguments.append("--dry-run")
    with pytest.raises(RunnerError, match="every batch trial requires.*rubric-dir"):
        task_cli.main(arguments)

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("outcome", ["success", "interrupt", "interrupt_gone", "missing_owner"])
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
@pytest.mark.parametrize("no_browser_start", [False, True])
def test_single_task_launcher_preserves_ownership_and_shutdown(tmp_path, monkeypatch, capsys, outcome, mode, no_browser_start):
    from contextlib import nullcontext
    events, launches, markers = [], [], []
    monkeypatch.delenv("AGENT_BROWSER_CDP_URL", raising=False)
    if no_browser_start:
        monkeypatch.setenv("AGENT_BROWSER_CDP_URL", "http://browser.fixture:9222")
    monkeypatch.setattr(task_cli, "task_transition_lock", lambda: nullcontext())
    monkeypatch.setattr(task_cli, "stop_previous_run", lambda **kwargs: events.append("handoff") or ({"status": "stopped", "run_id": "prior", "pid": 27182} if no_browser_start else {"status": "none"}))
    monkeypatch.setattr(task_cli, "restart_browser_service", lambda path: events.append("browser"))
    monkeypatch.setattr(task_cli, "claim_browser_profile_provenance", lambda name: events.append("profile") or {"fixture": True})
    monkeypatch.setattr(task_cli, "browser_container_cdp_url", lambda name: events.append("cdp_url") or "http://127.0.0.1:9222")
    monkeypatch.setattr(task_cli, "process_start_ticks", lambda pid: None if outcome == "missing_owner" else 42)
    monkeypatch.setattr(task_cli, "write_active_run", lambda record: markers.append(record) or events.append("publish"))
    monkeypatch.setattr(task_cli, "clear_active_run", lambda pid: events.append(("clear", pid)))
    def signal_group(pid, sig):
        events.append(("signal", pid, sig))
        if outcome == "interrupt_gone":
            raise ProcessLookupError(pid)
    monkeypatch.setattr(task_cli.os, "killpg", signal_group)
    class Process:
        pid = 31415
        waits = 0
        def wait(self, timeout=None):
            self.waits += 1
            events.append(("wait", timeout))
            if outcome.startswith("interrupt") and self.waits == 1:
                raise KeyboardInterrupt()
            if outcome.startswith("interrupt") and self.waits == 2:
                raise subprocess.TimeoutExpired("fixture", timeout)
            return -9 if outcome.startswith("interrupt") else 0
        def terminate(self):
            events.append("terminate")
    def launch(command, **kwargs):
        launches.append((command, kwargs))
        events.append("launch")
        return Process()
    monkeypatch.setattr(task_cli.subprocess, "Popen", launch)
    args = ["fixture", "--task", "Read the heading.", "--start-url", "https://example.test",
        "--observation-mode", mode, "--output-dir", str(tmp_path / "recordings"), "--run-name", "collection",
        "--env-file", str(tmp_path / "absent.env")]
    if no_browser_start:
        args.append("--no-browser-start")
    startup = ["handoff", *([] if no_browser_start else ["browser"]), "profile",
        *([] if no_browser_start else ["cdp_url"]), "launch"]
    if outcome == "missing_owner":
        with pytest.raises(RunnerError, match="runner process exited before ownership could be recorded"):
            task_cli.main(args)
        assert events == [*startup, "terminate"]
        assert markers == []
    else:
        assert task_cli.main(args) == (-9 if outcome.startswith("interrupt") else 0)
        assert events[:len(startup) + 1] == [*startup, "publish"]
        assert events[-1] == ("clear", 31415)
        assert markers[0]["pid"] == markers[0]["pgid"] == 31415
        assert markers[0]["process_start_ticks"] == 42
        if outcome.startswith("interrupt"):
            assert [event for event in events if isinstance(event, tuple) and event[0] == "signal"] == [
                ("signal", 31415, task_cli.signal.SIGTERM), ("signal", 31415, task_cli.signal.SIGKILL)]
    command, kwargs = launches[0]
    parsed = runner.parse_args(command[3:])
    assert parsed.observation_mode == mode and parsed.task == "Read the heading."
    assert parsed.task_id == parsed.source_task_id == "fixture" and parsed.run_name == "collection"
    assert parsed.max_steps == 200 and parsed.max_output_tokens == 10000 and parsed.model == "gemini-3.1-pro-preview"
    assert kwargs["start_new_session"] is True
    assert json.loads(kwargs["env"]["RUNNER_BROWSER_PROFILE_PROVENANCE"]) == {"fixture": True}
    assert kwargs["env"]["AGENT_BROWSER_CDP_URL"] == ("http://browser.fixture:9222" if no_browser_start else "http://127.0.0.1:9222")
    output = capsys.readouterr().out
    assert ("Previous task process: stopped (run=prior, pid=27182)" in output) is no_browser_start

@pytest.mark.usefixtures('no_network')
def test_single_launcher_preserves_existing_attempt(tmp_path, monkeypatch):
    directory = tmp_path / "recordings" / "collection" / "dom" / "fixture"
    write_json(directory / "final.json", {"run_status": "completed"})
    original = (directory / "final.json").read_bytes()
    monkeypatch.setattr(task_cli.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("existing attempt launched a process"))
    with pytest.raises(RunnerError, match="attempt directory already exists"):
        task_cli.main(["fixture", "--task", "Read heading.", "--start-url", "https://example.test",
            "--observation-mode", "dom", "--output-dir", str(tmp_path / "recordings"),
            "--run-name", "collection", "--env-file", str(tmp_path / "absent.env")])
    assert (directory / "final.json").read_bytes() == original

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("case", ["missing_catalog", "changed_catalog", "duplicate_ids", "empty_catalog", "missing_rubric"])
def test_batch_requires_bound_unique_tasks_and_rubrics(launcher_batch, monkeypatch, case):
    args, ledger, catalog, rubrics = launcher_batch
    if case == "missing_catalog":
        catalog.unlink()
        message = "needs a frozen local --catalog-file"
    elif case == "changed_catalog":
        fetch = task_cli.fetch_catalog_task
        def selected(*args, **kwargs):
            return {**fetch(*args, **kwargs), "catalog_sha256": "0" * 64}
        monkeypatch.setattr(task_cli, "fetch_catalog_task", selected)
        message = "catalog changed while selecting"
    elif case == "duplicate_ids":
        args.insert(0, "custom")
        message = "identities must be nonempty and unique"
    elif case == "empty_catalog":
        args.pop(0)
        catalog.write_text("")
        message = "identities must be nonempty and unique"
    else:
        (rubrics / "custom.json").unlink()
        message = "missing frozen rubric"
    with pytest.raises(RunnerError, match=message):
        task_cli.main(args)
    assert not ledger.exists()

@pytest.mark.usefixtures('no_network')
def test_batch_resume_requires_complete_schedule(launcher_batch):
    args, ledger, *_ = launcher_batch
    assert task_cli.main(args + ["--dry-run"]) == 0
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    write_json_lines(ledger, rows[:1])
    original = ledger.read_bytes()
    with pytest.raises(RunnerError, match="saved schedule differs from requested task/arm/trial set"):
        task_cli.main(args)
    assert ledger.read_bytes() == original

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("role", ["launcher", "judge"])
def test_batch_resume_refuses_live_scheduled_process(launcher_batch, monkeypatch, role):
    args, ledger, *_ = launcher_batch
    assert task_cli.main(args + ["--dry-run"]) == 0
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    original = ledger.read_bytes()
    command = (["python", "-m", "w8bench.task_recorder.task_cli", str(ledger.parent)] if role == "launcher" else
               ["python", "-m", "w8bench.verifier.run_comparison", "--run", rows[0]["recording"]])
    original_iterdir = Path.iterdir
    monkeypatch.setattr(Path, "iterdir", lambda path: iter([Path("/proc/self"), Path(f"/proc/{os.getpid()}"), Path("/proc/654321")])
        if path == Path("/proc") else original_iterdir(path))
    monkeypatch.setattr(task_cli, "process_command", lambda pid: command)
    with pytest.raises(RunnerError, match="scheduled launcher or judge is still running: pid 654321"):
        task_cli.main(args)
    assert ledger.read_bytes() == original

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("failure", ["interrupt", "os_error"])
def test_batch_actor_failure_preserves_attempt_state(launcher_batch, monkeypatch, partial, failure):
    args, ledger, *_ = launcher_batch
    args.append("--allow-expired")
    launches = []
    def launch(command, **kwargs):
        assert command[2] == "w8bench.task_recorder.task_cli"
        assert "--allow-expired" in command
        rows = [json.loads(line) for line in ledger.read_text().splitlines()]
        row = rows[len(launches)]
        launches.append(row["arm"])
        if partial:
            write_json(Path(row["recording"]) / "task.json", {"instruction": "Read heading."})
        if failure == "interrupt":
            raise KeyboardInterrupt()
        raise OSError("actor executable unavailable")
    monkeypatch.setattr(task_cli.subprocess, "run", launch)
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            task_cli.main(args)
    else:
        assert task_cli.main(args) == 0
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert rows[0]["completed"] is True and rows[0]["ended_at"]
    if failure == "interrupt":
        assert launches == ["dom"]
        assert rows[0]["technical_outcome"] == "interrupted"
        assert rows[1]["completed"] is False and rows[1]["technical_outcome"] == "not_started"
    else:
        assert launches == ["dom", "screenshot"]
        assert all(row["technical_outcome"] == ("incomplete_recording" if partial else "startup_failure") for row in rows)
        assert all(row["error"] == "OSError: actor executable unavailable" for row in rows)
        assert all(row["grade_completed"] and row["evaluation_reason"] == "recording_not_finalized" for row in rows)

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("judge_running", [False, True])
def test_batch_resume_uses_final_recording_and_tracks_judge_interruption(launcher_batch, monkeypatch, judge_running):
    from types import SimpleNamespace
    from w8bench.task_recorder import prepare_verifier_data
    args, ledger, *_ = launcher_batch
    assert task_cli.main(args + ["--dry-run"]) == 0
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    first, second = rows
    first.update(technical_outcome="completed" if judge_running else "running", completed=judge_running,
        started_at="2026-11-12T00:00:00Z", grade_outcome="running" if judge_running else "ungraded")
    second.update(technical_outcome="completed", completed=True, grade_completed=True, grade_outcome="success")
    write_json(Path(first["recording"]) / "final.json", {"run_status": "completed"})
    write_json_lines(ledger, rows)
    monkeypatch.setattr(prepare_verifier_data, "inspect_recording", lambda path: {"recording_sha256": "r" * 64})
    judges = []
    def judge(command, **kwargs):
        assert command[2] == "w8bench.verifier.run_comparison"
        judges.append(command)
        recording = Path(command[command.index("--run") + 1])
        write_json(recording / "completion.json", {"verdict": "success"})
        evaluation = recording.parent.parent / "evaluations" / first["run_name"] / first["arm"] / first["task_id"] / ("r" * 64) / "evaluation.json"
        write_json(evaluation, {"status": "complete"})
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(task_cli.subprocess, "run", judge)
    assert task_cli.main(args) == 0
    resumed = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(judges) == 1
    assert resumed[0]["technical_outcome"] == "completed" and resumed[0]["completed"] is True
    assert resumed[0]["grade_outcome"] == "success" and resumed[0]["grade_completed"] is True
    assert resumed[0]["evaluation_outcome"] == "complete" and Path(resumed[0]["evaluation_path"]).is_file()
    assert resumed[0].get("evaluation_previous_interruption", False) is judge_running
    assert resumed[1] == second

@pytest.mark.parametrize(
    "fault",
    ["missing_fields", "invalid_pid", "init_pid", "different_group", "reused_pid", "wrong_group", "other_command", "exited"],
)
def test_process_ownership_refuses_stale_and_unrelated_processes(monkeypatch, fault):
    record = {"pid": 4242, "pgid": 4242, "process_start_ticks": 99}
    if fault == "missing_fields":
        record.pop("process_start_ticks")
    elif fault == "invalid_pid":
        record["pid"] = "invalid"
    elif fault == "init_pid":
        record.update(pid=1, pgid=1)
    elif fault == "different_group":
        record["pgid"] = 4243
    monkeypatch.setattr(task_cli, "process_start_ticks", lambda pid: 100 if fault == "reused_pid" else 99)

    def group(pid):
        if fault == "exited":
            raise ProcessLookupError()
        return 4243 if fault == "wrong_group" else 4242

    monkeypatch.setattr(task_cli.os, "getpgid", group)
    monkeypatch.setattr(
        task_cli,
        "process_command",
        lambda pid: ["python", "-m", "unrelated.module" if fault == "other_command" else task_cli.RUNNER_MODULE],
    )
    assert task_cli.owned_process_group(record) is None

def test_process_ownership_requires_matching_start_token_group_and_runner(monkeypatch):
    monkeypatch.setattr(task_cli, "process_start_ticks", lambda pid: 99)
    monkeypatch.setattr(task_cli.os, "getpgid", lambda pid: 4242)
    monkeypatch.setattr(task_cli, "process_command", lambda pid: ["python", "-m", task_cli.RUNNER_MODULE])
    assert task_cli.owned_process_group({"pid": 4242, "pgid": 4242, "process_start_ticks": 99}) == (4242, 4242)

@pytest.mark.parametrize("payload", [None, "{broken", "[]", '{"pid": 4242}'])
def test_handoff_does_not_signal_missing_malformed_or_unowned_markers(tmp_path, monkeypatch, payload):
    marker = tmp_path / "active-run.json"
    if payload is not None:
        marker.write_text(payload)
    monkeypatch.setattr(task_cli, "owned_process_group", lambda record: None)
    monkeypatch.setattr(task_cli.os, "killpg", lambda *args: pytest.fail("an unowned process was signalled"))
    result = task_cli.stop_previous_run(marker)
    assert result["status"] in {"none", "stale_record_removed"}
    if payload == '{"pid": 4242}':
        assert not marker.exists()

@pytest.mark.parametrize("exits_after_term", [True, False])
def test_handoff_signals_only_the_owned_group_and_bounds_shutdown(tmp_path, monkeypatch, exits_after_term):
    marker = tmp_path / "active-run.json"
    marker.write_text(json.dumps({"pid": 4242, "run_id": "owned"}))
    monkeypatch.setattr(task_cli, "owned_process_group", lambda record: (4242, 4242))
    signals, waits = [], []
    monkeypatch.setattr(task_cli.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    def wait(pid, timeout):
        waits.append((pid, timeout))
        return exits_after_term if len(waits) == 1 else True

    monkeypatch.setattr(task_cli, "wait_for_process_exit", wait)
    result = task_cli.stop_previous_run(marker, timeout=0.5)
    assert signals == [(4242, signal.SIGTERM)] + ([] if exits_after_term else [(4242, signal.SIGKILL)])
    assert waits == [(4242, 0.5)] + ([] if exits_after_term else [(4242, 2.0)])
    assert result["status"] == ("stopped" if exits_after_term else "killed_after_timeout")
    assert result["pid"] == 4242 and result["run_id"] == "owned"
    assert not marker.exists()

@pytest.mark.parametrize("recorded_pid", [4242, 4243, "invalid", None])
def test_finishing_runner_can_clear_only_its_own_marker(tmp_path, recorded_pid):
    marker = tmp_path / "active-run.json"
    task_cli.write_active_run({"pid": recorded_pid, "run_id": "attempt"}, marker)
    task_cli.clear_active_run(4242, marker)
    assert marker.exists() is (recorded_pid != 4242)
    if marker.exists():
        assert task_cli.read_active_run(marker) == {"pid": recorded_pid, "run_id": "attempt"}

@pytest.mark.parametrize("prior_tasks", [0, 1])
@pytest.mark.parametrize("image_metadata_available", [False, True])
def test_profile_claim_tracks_container_lifetime_and_exact_image(tmp_path, monkeypatch, prior_tasks, image_metadata_available):
    monkeypatch.setattr(task_cli, "ROOT", tmp_path)
    monkeypatch.setenv("BROWSER_PROFILE_TASK_COUNT_PATH", "/home/browser/task-count")
    image_id = "sha256:" + "a" * 64
    commands = []
    container = {
        "Id": "container-one",
        "Created": "2026-11-17T00:00:00Z",
        "Image": image_id,
        "Config": {
            "Image": "browser:mutable-tag",
            "Labels": {"com.docker.compose.project.working_dir": str(tmp_path)},
            "Env": ["LANG=en_US.UTF-8", "TZ=UTC", "OPENAI_API_KEY=do-not-record"],
        },
    }
    image = {"Id": image_id, "RepoDigests": ["browser@" + image_id], "Config": {"Labels": {"org.opencontainers.image.revision": "b" * 40}}}

    def docker(command, **kwargs):
        commands.append(command)
        if command[:2] == ["docker", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([container]), stderr="")
        if command[:3] == ["docker", "image", "inspect"]:
            assert command[-1] == image_id
            return SimpleNamespace(returncode=0 if image_metadata_available else 1, stdout=json.dumps([image]), stderr="image metadata unavailable")
        if command[-2:] == ["task-recorder-profile-counter", "/home/browser/task-count"]:
            return SimpleNamespace(returncode=0, stdout=str(prior_tasks), stderr="")
        assert command[-3:] == ["task-recorder-profile-counter", "/home/browser/task-count", str(prior_tasks + 1)]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(task_cli.subprocess, "run", docker)
    result = task_cli.claim_browser_profile_provenance("browser-fixture")
    assert result["container_id"] == "container-one"
    assert result["container_created_at"] == "2026-11-17T00:00:00Z"
    assert result["tasks_previously_run_in_container"] == prior_tasks
    assert result["profile_fresh_at_run_start"] is (prior_tasks == 0)
    assert result["browser_build"]["image_id"] == image_id
    assert result["browser_build"]["image_reference"] == "browser:mutable-tag"
    assert result["browser_build"]["repo_digests"] == (["browser@" + image_id] if image_metadata_available else [])
    assert result["browser_build"]["image_source_revision"] == ("b" * 40 if image_metadata_available else None)
    assert bool(result["browser_build"]["inspection_error"]) is (not image_metadata_available)
    assert result["browser_environment"] == {"LANG": "en_US.UTF-8", "TZ": "UTC"}
    assert "do-not-record" not in json.dumps(result)
    assert commands[0] == ["docker", "inspect", "browser-fixture"]
    assert len(commands) == 4

@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("inspect_error", "could not inspect"),
        ("invalid_json", "invalid container provenance"),
        ("empty_container_list", "invalid container provenance"),
        ("foreign_checkout", "another checkout"),
        ("counter_error", "could not read browser profile task count"),
        ("counter_text", "not an integer"),
        ("counter_negative", "must not be negative"),
        ("counter_write_error", "could not update browser profile task count"),
    ],
)
def test_profile_claim_refuses_unowned_or_unverifiable_task_counts(tmp_path, monkeypatch, fault, message):
    monkeypatch.setattr(task_cli, "ROOT", tmp_path)
    container = {"Id": "fixture", "Created": "2026-11-17T00:00:00Z", "Image": "image-id",
                 "Config": {"Labels": {"com.docker.compose.project.working_dir": str(tmp_path / "foreign" if fault == "foreign_checkout" else tmp_path)}}}

    def docker(command, **kwargs):
        if command[:2] == ["docker", "inspect"]:
            payload = "{broken" if fault == "invalid_json" else json.dumps([] if fault == "empty_container_list" else [container])
            return SimpleNamespace(returncode=int(fault == "inspect_error"), stdout=payload, stderr="container unavailable")
        if command[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"Id": "image-id"}]), stderr="")
        if "task-recorder-profile-counter" == command[-2]:
            payload = "not-a-count" if fault == "counter_text" else "-1" if fault == "counter_negative" else "0"
            return SimpleNamespace(returncode=int(fault == "counter_error"), stdout=payload, stderr="counter unavailable")
        assert fault == "counter_write_error"
        return SimpleNamespace(returncode=1, stdout="", stderr="counter write unavailable")

    monkeypatch.setattr(task_cli.subprocess, "run", docker)
    with pytest.raises(RunnerError, match=message):
        task_cli.claim_browser_profile_provenance("browser-fixture")

@pytest.mark.parametrize("raw", ["1", "9222\n", "65535", "0", "65536", "port", ""])
def test_container_cdp_port_is_validated_without_contacting_the_browser(monkeypatch, raw):
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=raw, stderr=""))
    if raw.strip().isdigit() and 1 <= int(raw) <= 65535:
        assert task_cli.browser_container_cdp_url("browser-fixture") == f"http://127.0.0.1:{int(raw)}"
    else:
        with pytest.raises(RunnerError, match="not an integer|outside the valid range"):
            task_cli.browser_container_cdp_url("browser-fixture")

def test_container_cdp_port_refuses_failed_container_inspection(monkeypatch):
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="container unavailable"))
    with pytest.raises(RunnerError, match="could not read w8-core container CDP port"):
        task_cli.browser_container_cdp_url("browser-fixture")
