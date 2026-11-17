"""Catalog selection and process handoff contracts, without launching a browser."""

import json
import signal
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from w8bench.task_recorder import task_cli
from w8bench.task_recorder.recorder_support import RunnerError


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("", "no task rows"),
        (" \n\t\n", "no task rows"),
        ('{"task_id": "one"}\n\n{broken}', "line 3"),
        ("[]", "not a JSON object"),
        ("null", "not a JSON object"),
        ("{}", "no task_id"),
        ('{"task_id": "   "}', "no task_id"),
        ('{"task_id": "One"}\n{"task_id": "one"}', "duplicate task_id"),
    ],
)
def test_catalog_refuses_empty_malformed_and_ambiguous_rows(payload, message):
    with pytest.raises(RunnerError, match=message):
        task_cli.parse_task_catalog(payload, source="offline-catalog.jsonl")


def test_catalog_preserves_unicode_order_and_task_fields():
    rows = [
        {"task_id": "custom_b", "instruction": "Read café title.", "extra": [1, 2]},
        {"task_id": "custom_a", "instruction": "Read another title."},
    ]
    payload = "\r\n" + "\r\n\r\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\r\n"
    assert task_cli.parse_task_catalog(payload, source="offline") == rows


@pytest.mark.parametrize("selector", ["1", "001", "task1", "task_01", "browser-task-1"])
def test_catalog_numeric_alias_selects_the_only_matching_suffix(selector):
    rows = [{"task_id": "catalog_02"}, {"task_id": "research_01"}]
    assert task_cli.select_catalog_task(rows, selector) == {"task_id": "research_01"}


def test_exact_catalog_id_takes_precedence_over_numeric_aliases():
    rows = [{"task_id": "research_01"}, {"task_id": "TASK_01"}]
    assert task_cli.select_catalog_task(rows, " task_01 ") == rows[1]
    with pytest.raises(RunnerError, match="ambiguous"):
        task_cli.select_catalog_task(rows, "1")
    with pytest.raises(RunnerError, match="ambiguous"):
        task_cli.select_catalog_task(list(reversed(rows)), "1")


@pytest.mark.parametrize("selector", ["0", "task_00", "other", "-1", "task_3"])
def test_unknown_catalog_alias_never_selects_by_row_position(selector):
    with pytest.raises(RunnerError, match="no task matching"):
        task_cli.select_catalog_task([{"task_id": "one_1"}, {"task_id": "two_2"}], selector)


def test_catalog_instruction_keeps_stopping_condition_and_constraints_in_order():
    instruction = task_cli.catalog_task_instruction(
        {
            "instruction": " Read the heading. ",
            "stopping_condition": " Report its exact text. ",
            "constraints": [" Remain read-only. ", "", " Do not sign in. "],
        }
    )
    assert instruction == (
        "Read the heading.\n\nStopping condition: Report its exact text.\n\n"
        "Constraints:\n- Remain read-only.\n- Do not sign in."
    )
    assert task_cli.catalog_task_instruction({"instruction": "Read the heading."}) == "Read the heading."


@pytest.mark.parametrize(
    ("instruction", "url", "message"),
    [
        (" ", "https://example.test", "instruction"),
        ("Read", "/relative", "absolute HTTP"),
        ("Read", "file:///tmp/page", "absolute HTTP"),
        ("Read", "https:///missing-host", "absolute HTTP"),
    ],
)
def test_manual_definition_refuses_missing_instruction_and_non_web_urls(instruction, url, message):
    with pytest.raises(RunnerError, match=message):
        task_cli.validate_task_definition(instruction, url)


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_manual_definition_preserves_the_web_url_and_trims_outer_space(scheme):
    url = f"{scheme}://example.test/path?q=one#heading"
    assert task_cli.validate_task_definition(" Read the heading. ", f" {url} ") == {
        "instruction": "Read the heading.",
        "start_url": url,
    }


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


def test_catalog_alias_dry_run_resolves_expanded_contract_without_launch(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
    catalog = tmp_path / "catalog.jsonl"
    row = {
        "task_id": "research_07",
        "task_name": "Heading research",
        "instruction": "Read café title.",
        "start_url": "https://example.test/page",
        "stopping_condition": "Report its exact text.",
        "constraints": ["Remain read-only."],
    }
    catalog.write_text(json.dumps(row, ensure_ascii=False) + "\n")
    monkeypatch.setattr(task_cli.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("dry-run launched an actor"))
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: pytest.fail("dry-run launched a browser"))
    output = tmp_path / "recordings"
    assert task_cli.main(
        ["7", "--catalog-file", str(catalog), "--observation-mode", "screenshot",
         "--output-dir", str(output), "--run-name", "selection", "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    ) == 0
    printed = capsys.readouterr().out
    assert "Task name: Heading research" in printed
    assert "https://example.test/page" in printed
    assert str(output / "selection" / "screenshot" / "research_07") in printed
    assert not output.exists()


@pytest.mark.parametrize("day", [16, 17, 18])
@pytest.mark.parametrize("batch", [False, True])
def test_launcher_expiry_is_inclusive_and_checked_in_utc(tmp_path, monkeypatch, day, batch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz):
            assert tz == timezone.utc
            return cls(2026, 11, day, 23, 59, 59, tzinfo=tz)

    monkeypatch.setattr(task_cli, "datetime", Clock)
    monkeypatch.setattr(task_cli, "ROOT", tmp_path)
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: pytest.fail("expiry dry-run started a process"))
    catalog = tmp_path / "tasks.jsonl"
    catalog.write_text(json.dumps({"task_id": "dated", "instruction": "Read title.", "start_url": "https://example.test"}) + "\n")
    internal = tmp_path / "internal"
    internal.mkdir()
    (internal / "task_validity.json").write_text(json.dumps({"catalog": "tasks.jsonl", "tasks": {"dated": {"valid_until": "2026-11-17"}}}))
    output = tmp_path / "recordings"
    args = ["dated", "--catalog-file", str(catalog), "--output-dir", str(output), "--run-name", "expiry",
            "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    args += ["--trials", "1", "--judge-model", "gpt-6.1-sol"] if batch else ["--observation-mode", "dom"]
    if day > 17:
        with pytest.raises(RunnerError, match="expired catalog task"):
            task_cli.main(args)
        assert not output.exists()
        assert task_cli.main(args + ["--allow-expired"]) == 0
    else:
        assert task_cli.main(args) == 0


def test_schedule_binds_one_frozen_task_rubric_across_arms_and_trials(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: pytest.fail("schedule started a process"))
    catalog = tmp_path / "tasks.jsonl"
    tasks = [{"task_id": name, "instruction": f"Read {name} title.", "start_url": "https://example.test"}
             for name in ("alpha", "beta")]
    catalog.write_text("".join(json.dumps(row) + "\n" for row in tasks))
    rubric_dir = tmp_path / "rubrics"
    rubric_dir.mkdir()
    for row in tasks:
        (rubric_dir / f"{row['task_id']}.json").write_text(json.dumps({**row, "criteria": [{"id": "title", "description": row["instruction"]}]}))
    output = tmp_path / "recordings"
    args = ["--catalog-file", str(catalog), "--trials", "3", "--rubric-dir", str(rubric_dir),
            "--judge-model", "gpt-6.1-sol", "--output-dir", str(output), "--run-name", "frozen",
            "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    assert task_cli.main(args) == 0
    ledger = output / "frozen" / "ledger.jsonl"
    original = ledger.read_bytes()
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(rows) == 12 and len({row["recording"] for row in rows}) == 12
    for name in ("alpha", "beta"):
        selected = [row for row in rows if row["task_id"] == name]
        assert {(row["trial"], row["arm"]) for row in selected} == {
            (trial, arm) for trial in (1, 2, 3) for arm in ("dom", "screenshot")
        }
        assert len({row["rubric_sha256"] for row in selected}) == 1
        assert {row["rubric"] for row in selected} == {str(rubric_dir / f"{name}.json")}
    (rubric_dir / "alpha.json").write_text(json.dumps({**tasks[0], "criteria": [{"id": "title", "description": "A different requirement."}]}))
    with pytest.raises(RunnerError, match="saved schedule configuration differs"):
        task_cli.main(args)
    assert ledger.read_bytes() == original


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
