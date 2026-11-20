"""Catalog, settings and task-selection contracts."""

import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from w8bench import settings
from w8bench.task_recorder import runner, task_cli
from w8bench.task_recorder.prepare_verifier_data import inspect_recording
from w8bench.task_recorder.recorder_support import RunnerError, write_json, write_json_lines
from w8bench.verifier import completion, package_manifests, run_comparison as comparison
from w8bench.verifier.common import canonical_sha256


def evaluation_args(paths, rubric, config):
    return ["--run", str(paths["dom"]), "--rubric", str(rubric), "--judge-model", "gpt-6.1-sol",
        "--eval-config", str(config), "--execute"]

def test_each_actor_reads_the_frozen_catalog_when_the_original_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    original_iterdir = Path.iterdir
    monkeypatch.setattr(Path, "iterdir", lambda path: iter(()) if path == Path("/proc") else original_iterdir(path))
    catalog = tmp_path / "source.jsonl"
    row = {"task_id": "custom", "instruction": "Read the heading.", "start_url": "https://example.test/"}
    original = (json.dumps(row) + "\n").encode()
    catalog.write_bytes(original)
    rubrics = tmp_path / "rubrics"
    write_json(rubrics / "custom.json", {"task_id": "custom", "criteria": [{"id": "heading", "description": "Report the heading."}]})
    output = tmp_path / "recordings"
    launches = []
    def launch(command, **kwargs):
        selected = Path(command[command.index("--catalog-file") + 1])
        definition = task_cli.fetch_catalog_task(str(selected), "custom")
        launches.append((selected, definition["instruction"], definition["catalog_sha256"]))
        catalog.write_text(json.dumps({**row, "instruction": "A different task."}) + "\n")
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(task_cli.subprocess, "run", launch)
    assert task_cli.main(["custom", "--trials", "1", "--catalog-file", str(catalog),
        "--rubric-dir", str(rubrics), "--judge-model", "gpt-6.1-sol", "--output-dir", str(output),
        "--run-name", "collection", "--env-file", str(tmp_path / "absent.env")]) == 0
    frozen = output / "collection" / "catalog.jsonl"
    ledger = [json.loads(line) for line in (frozen.parent / "ledger.jsonl").read_text().splitlines()]
    assert frozen.read_bytes() == original
    assert [selected for selected, _, _ in launches] == [frozen, frozen]
    assert [instruction for _, instruction, _ in launches] == [row["instruction"], row["instruction"]]
    assert [digest for _, _, digest in launches] == [entry["catalog_sha256"] for entry in ledger]

def test_scheduled_rows_include_full_stage_and_actor_policy(effective_settings_batch):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    rows = [json.loads(line) for line in batch.ledger.read_text().splitlines()]
    for row in rows:
        contract = row["effective_settings"]
        assert contract["actor"]["max_turns"] == 200
        assert contract["actor"]["agent_browser_timeout"] == 90
        assert contract["actor"]["transport_timeout"] == 180
        assert contract["actor"]["cdp_timeout"] == 90
        assert contract["actor"]["snapshot_max_nodes"] == 7000
        assert contract["actor"]["snapshot_max_text_chars"] == 200000
        assert set(contract["stages"]) == {"completion", "dom_model", "screenshot_verifier", "inventory", "adjudication", "rubric_preparation"}
        assert contract["rubric_sha256"] == canonical_sha256({"items": [{"criterion": "heading",
            "description": "Report the heading.", "max_points": 1, "earned_points": None, "justification": None}]})
        assert "recorder_code_sha256" not in json.dumps(contract)
        assert "image" not in contract["actor"]
    assert rows[0]["effective_settings"] == rows[1]["effective_settings"]

@pytest.mark.parametrize("key,value,field", [
    ("STEP_SETTLE_SECONDS", "0.25", "actor.settle_seconds"),
    ("SNAPSHOT_MAX_NODES", "123", "actor.snapshot_max_nodes"),
    ("SNAPSHOT_MAX_TEXT_CHARS", "54321", "actor.snapshot_max_text_chars"),
    ("AGENT_BROWSER_TIMEOUT", "45", "actor.agent_browser_timeout"),
    ("BROWSER_LANG", "fr", "actor.browser_lang"),
    ("GEMINI_BASE_URL", "https://actor.example.test/another-api", "actor.base_url"),
    ("OPENAI_BASE_URL", "https://judge.example.test/another-api", "base_url"),
    ("EVIDENCE_AUDIT_MODEL", "gemini-3.1-pro-preview-2026-11-17", "stages.inventory.models"),
    ("EVIDENCE_ADJUDICATOR_MODEL", "gpt-6.1-sol-2026-11-17", "stages.adjudication.models"),
])
def test_resume_checks_effective_policy_even_when_every_actor_is_completed(
    effective_settings_batch, monkeypatch, key, value, field
):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    rows = [json.loads(line) for line in batch.ledger.read_text().splitlines()]
    for row in rows:
        row.update(completed=True, technical_outcome="completed", grade_completed=True, grade_outcome="success")
    write_json_lines(batch.ledger, rows)
    before = batch.ledger.read_bytes()
    monkeypatch.setenv(key, value)
    with pytest.raises(RunnerError, match="effective settings differ") as caught:
        task_cli.main((batch.arguments) + ["--resume"])
    assert field in str(caught.value)
    assert batch.ledger.read_bytes() == before

def test_resume_refuses_changed_endpoint_request_settings(effective_settings_batch):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    endpoint = batch.config_root / "config/google_gemini3_5_flash_lite.json"
    value = json.loads(endpoint.read_text())
    value["CHAT_COMPLETION_KWARGS_JSON"]["reasoning_effort"] = "low"
    endpoint.write_text(json.dumps(value))
    with pytest.raises(RunnerError, match="effective settings differ") as caught:
        task_cli.main((batch.arguments) + ["--resume"])
    assert "endpoints" in str(caught.value)

def test_resume_ignores_deployment_and_credential_changes(effective_settings_batch, monkeypatch):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    for key, value in {"IMAGE": "w8-core:another-tag", "CONTAINER_NAME": "another-container",
        "COMPOSE_PROJECT_NAME": "another-project", "CDP_HOST_PORT": "49101", "NOVNC_HOST_PORT": "49102",
        "VNC_HOST_PORT": "49103", "OPENAI_API_KEY": "another-offline-key", "GEMINI_API_KEY": "another-offline-key"}.items():
        monkeypatch.setenv(key, value)
    assert task_cli.main((batch.arguments) + ["--resume"]) == 0

def test_resume_accepts_identical_rubric_and_catalog_at_new_locations(effective_settings_batch, tmp_path):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    catalog = tmp_path / "relocated.jsonl"
    shutil.copyfile(batch.catalog, catalog)
    rubrics = tmp_path / "relocated-rubrics"
    shutil.copytree(batch.rubric_dir, rubrics)
    arguments = list(batch.arguments)
    arguments[arguments.index("--catalog-file") + 1] = str(catalog)
    arguments[arguments.index("--rubric-dir") + 1] = str(rubrics)
    assert task_cli.main((arguments) + ["--resume"]) == 0
    rows = [json.loads(line) for line in batch.ledger.read_text().splitlines()]
    assert all(row["rubric"] == str(rubrics / "custom.json") for row in rows)

def test_resume_keeps_catalog_and_rubric_content_binding(effective_settings_batch):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    rubric = batch.rubric_dir / "custom.json"
    value = json.loads(rubric.read_text())
    value["criteria"][0]["description"] = "Report a different result."
    rubric.write_text(json.dumps(value))
    with pytest.raises(RunnerError, match="effective settings differ") as caught:
        task_cli.main((batch.arguments) + ["--resume"])
    assert "rubric_sha256" in str(caught.value)

def test_resume_ignores_recorder_source_hash_when_policy_is_unchanged(effective_settings_batch, tmp_path, monkeypatch):
    batch = effective_settings_batch
    monkeypatch.setattr(task_cli, "ROOT", tmp_path)
    source = tmp_path / "w8bench/example.py"
    source.parent.mkdir()
    source.write_text('"""Module documentation."""\n')
    assert task_cli.main(batch.arguments) == 0
    source.write_text('"""Another module description."""\n')
    assert task_cli.main((batch.arguments) + ["--resume"]) == 0

def test_actor_child_receives_the_scheduled_effective_contract(effective_settings_batch, monkeypatch):
    batch = effective_settings_batch
    dispatched = []
    def launch(command, **kwargs):
        raw = kwargs.get("env", {}).get("W8_EXPECTED_ACTOR_SETTINGS")
        dispatched.append(json.loads(raw) if raw else None)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(task_cli.subprocess, "run", launch)
    assert task_cli.main([arg for arg in batch.arguments if arg != "--dry-run"]) == 0
    rows = [json.loads(line) for line in batch.ledger.read_text().splitlines()]
    assert dispatched == [row["effective_settings"]["actor"] for row in rows]

def test_every_recorded_effective_field_is_checked_before_completed_resume(effective_settings_batch):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    original = [json.loads(line) for line in batch.ledger.read_text().splitlines()]
    for row in original:
        row.update(completed=True, technical_outcome="completed", grade_completed=True)
    def leaves(value, path=()):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                yield from leaves(child, (*path, key))
        elif isinstance(value, list) and value:
            for index, child in enumerate(value):
                yield from leaves(child, (*path, index))
        else:
            yield path, value
    checked = []
    for path, value in leaves(original[0]["effective_settings"]):
        rows = copy.deepcopy(original)
        target = rows[0]["effective_settings"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = not value if isinstance(value, bool) else value + 1 if isinstance(value, (int, float)) else "different"
        write_json_lines(batch.ledger, rows)
        before = batch.ledger.read_bytes()
        with pytest.raises(RunnerError, match="effective settings differ"):
            task_cli.main((batch.arguments) + ["--resume"])
        assert batch.ledger.read_bytes() == before
        checked.append(path)
    assert checked and any(path[0] == "actor" for path in checked) and any(path[0] == "stages" for path in checked)

def test_resume_accepts_same_endpoint_config_in_another_directory(effective_settings_batch, tmp_path, monkeypatch):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    destination = tmp_path / "relocated-settings"
    shutil.copytree(batch.config_root, destination)
    for endpoint in (destination / "config").glob("*.json"):
        value = json.loads(endpoint.read_text())
        value["CHAT_COMPLETION_KWARGS_JSON"]["api_key"] = "another-offline-key"
        endpoint.write_text(json.dumps(value))
    monkeypatch.setattr(settings, "ROOT", destination)
    assert task_cli.main((batch.arguments) + ["--resume"]) == 0

def test_resume_ignores_model_endpoint_port_changes(effective_settings_batch, monkeypatch):
    batch = effective_settings_batch
    monkeypatch.setenv("GEMINI_BASE_URL", "https://actor.example.test:49101/v1beta")
    assert task_cli.main(batch.arguments) == 0
    monkeypatch.setenv("GEMINI_BASE_URL", "https://actor.example.test:49102/v1beta")
    assert task_cli.main((batch.arguments) + ["--resume"]) == 0

@pytest.mark.usefixtures('no_network')
def test_local_catalog_keeps_the_launcher_generic(tmp_path, capsys):
    catalog = tmp_path / "arbitrary-catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "browser_task_042", "task_name": "arbitrary task",
        "instruction": "Read the heading.", "start_url": "https://example.test",
        "stopping_condition": "Stop after recording the heading.", "constraints": ["Do not sign in."]}) + "\n")
    definition = task_cli.fetch_catalog_task(str(catalog), "42")
    assert definition["source_task_id"] == "browser_task_042"
    assert "Stopping condition: Stop after recording the heading." in definition["instruction"]
    assert "- Do not sign in." in definition["instruction"]
    assert definition["source_catalog"] == str(catalog.resolve())
    assert definition["catalog_sha256"] == hashlib.sha256(catalog.read_bytes()).hexdigest()
    assert task_cli.main(["task_42", "--catalog-file", str(catalog), "--observation-mode", "dom",
        "--output-dir", str(tmp_path / "recordings"), "--env-file", str(tmp_path / "absent.env"), "--dry-run"]) == 0
    assert "arbitrary task" in capsys.readouterr().out

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_compact_catalog_runs_in_both_arms_and_records_hash(run_pair, tmp_path, monkeypatch, mode):
    paths, *_ = run_pair
    for prior in paths.values():
        assert json.loads((prior / "manifest.json").read_text())["catalog_sha256"] is None
        assert json.loads((prior / "task.json").read_text())["catalog_sha256"] is None
    catalog = tmp_path / "catalog-with-crlf.jsonl"
    row = {"task_id": "task_02", "task_name": "Read café heading", "category": "research",
        "instruction": "Read café heading.", "start_url": "https://example.test",
        "stopping_condition": "Report the heading.", "constraints": ["Remain read-only."],
        "difficulty": "medium"}
    assert set(row) == {"task_id", "task_name", "category", "instruction", "start_url",
        "stopping_condition", "constraints", "difficulty"}
    original = (json.dumps(row, ensure_ascii=False) + "\r\n").encode("utf-8")
    catalog.write_bytes(original)
    expected_hash = hashlib.sha256(original).hexdigest()
    assert expected_hash != hashlib.sha256(catalog.read_text().encode()).hexdigest()
    definition = task_cli.fetch_catalog_task(str(catalog), row["task_id"])
    assert definition["difficulty"] == "medium" and definition["catalog_sha256"] == expected_hash
    assert "attribution" not in definition
    proposals = [{"action": "wait", "seconds": 0, "thought": "Read the current heading."},
        {"action": "terminate", "status": "success", "termination_reason": "completed",
         "final_answer": "done", "thought": "Observed heading."}]
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self, payload: {
        "model": "gemini-3.8-flash", "output_text": json.dumps(proposals.pop(0)),
        "usage": {"input_tokens": 1, "output_tokens": 1}})
    output = tmp_path / "catalog-runs" / mode
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
        "--task", definition["instruction"], "--start-url", row["start_url"], "--task-id", "task_02",
        "--source-task-id", "task_02", "--source-catalog", str(catalog), "--output-dir", str(output),
        "--model", "gemini-3.8-flash", "--api-key", "offline-placeholder", "--max-turns", "2", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 0
    recording = inspect_recording(output / "task_02")
    for item in (recording["task"], recording["manifest"]):
        assert item["catalog_sha256"] == expected_hash
        assert item["difficulty"] == row["difficulty"] and item["category"] == row["category"]
        assert item["source_task_id"] == row["task_id"]
        assert item["source_catalog"] == str(catalog.resolve())
        assert "attribution" not in item
    request = json.loads((output / "task_02" / "turns/turn_000001/request.json").read_text())
    assert expected_hash not in json.dumps(request)
    assert "ATTRIBUTION.md" not in json.dumps(request)

@pytest.mark.usefixtures('no_network')
def test_task_validity_binds_catalog_bytes_including_frozen_copy(curated_catalog, tmp_path):
    catalog, row = curated_catalog
    assert not (tmp_path / "internal/curation_notes.json").exists()
    assert not (tmp_path / "internal/alternatives.jsonl").exists()
    assert task_cli.fetch_catalog_task(str(catalog), row["task_id"])["valid_until"] == "2000-12-31"
    frozen = tmp_path / "frozen-copy.jsonl"
    frozen.write_bytes(catalog.read_bytes())
    assert task_cli.fetch_catalog_task(str(frozen), row["task_id"])["valid_until"] == "2000-12-31"
    # Even line-ending changes produce different catalog bytes, not an ID match.
    frozen.write_bytes(catalog.read_bytes().replace(b"\r\n", b"\n"))
    assert task_cli.fetch_catalog_task(str(frozen), row["task_id"])["valid_until"] is None
    external = tmp_path / "external.jsonl"
    external.write_text(json.dumps({**row, "instruction": "A different task with the same ID."}) + "\n")
    assert task_cli.fetch_catalog_task(str(external), row["task_id"])["valid_until"] is None

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("batch", [False, True])
def test_launcher_refuses_expired_before_scheduling_and_allows_explicit_override(curated_catalog, tmp_path, batch, capsys):
    catalog, row = curated_catalog
    output = tmp_path / "recordings"
    args = [row["task_id"], "--catalog-file", str(catalog), "--output-dir", str(output),
        "--run-name", "expiry", "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    args += ["--trials", "2", "--judge-model", "gpt-6.1-sol"] if batch else ["--observation-mode", "dom"]
    with pytest.raises(RunnerError, match="expired catalog task"):
        task_cli.main(args)
    assert not output.exists()
    assert "2000-12-31 UTC" in capsys.readouterr().err
    assert task_cli.main(args + ["--allow-expired"]) == 0
    if batch:
        preview = output / "expiry" / "schedule_preview.jsonl"
        rows = [json.loads(line) for line in preview.read_text().splitlines()]
        assert len(rows) == 4 and all(item["planning_only"] for item in rows)
        assert all(item["task"]["valid_until"] == "2000-12-31" for item in rows)
        assert all(item["configuration"]["allow_expired"] is True for item in rows)
        assert not (output / "expiry" / "ledger.jsonl").exists()

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_runner_expiry_refusal_override_and_inclusive_utc_date(run_pair, curated_catalog, tmp_path, monkeypatch, mode):
    catalog, row = curated_catalog
    definition = task_cli.fetch_catalog_task(str(catalog), row["task_id"])
    calls = []
    def post(self, payload):
        calls.append(payload)
        decision = ({"action": "wait", "seconds": 0, "thought": "Observe the current page."} if len(calls) % 2 else
            {"action": "terminate", "status": "success", "termination_reason": "completed", "final_answer": "done", "thought": "Observed heading."})
        return {"model": "gemini-3.8-flash", "output_text": json.dumps(decision),
            "usage": {"input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    output = tmp_path / "expired-run"
    args = ["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
        "--task", definition["instruction"], "--start-url", row["start_url"], "--task-id", row["task_id"],
        "--source-task-id", row["task_id"], "--source-catalog", str(catalog), "--output-dir", str(output),
        "--model", "gemini-3.8-flash", "--api-key", "offline-placeholder", "--settle-seconds", "0"]
    with pytest.raises(RunnerError, match="expired catalog task"):
        asyncio.run(runner.run(runner.parse_args(args)))
    assert calls == [] and not output.exists()
    assert asyncio.run(runner.run(runner.parse_args(args + ["--allow-expired"]))) == 0
    manifest = json.loads((output / row["task_id"] / "manifest.json").read_text())
    assert manifest["valid_until"] == "2000-12-31" and manifest["expiry_override"] is True
    assert manifest["expiry_checked_at"].endswith("+00:00")
    assert "expiry_" not in json.dumps(calls) and "valid_until" not in json.dumps(calls)
    today = runner.datetime.now(runner.timezone.utc).date().isoformat()
    write_json(tmp_path / "internal" / "task_validity.json", {"catalog": "data/tasks.jsonl",
        "tasks": {row["task_id"]: {"valid_until": today}}})
    args[args.index("--output-dir") + 1] = str(tmp_path / "inclusive-date-run")
    assert asyncio.run(runner.run(runner.parse_args(args))) == 0
    current = json.loads((tmp_path / "inclusive-date-run" / row["task_id"] / "manifest.json").read_text())
    assert current["valid_until"] == today and current["expiry_override"] is False

@pytest.mark.usefixtures('no_network')
def test_pre_rubric_planning_is_separate_and_cannot_resume_as_execution(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.", "start_url": "https://example.test"}) + "\n")
    args = ["--trials", "2", "--catalog-file", str(catalog), "--judge-model", "gpt-6.1-sol",
        "--env-file", str(tmp_path / "absent.env"), "--output-dir", str(tmp_path / "recordings"), "--run-name", "plan"]
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: pytest.fail("planning launched a child"))
    assert task_cli.main(args + ["--dry-run"]) == 0
    root = tmp_path / "recordings" / "plan"
    rows = [json.loads(line) for line in (root / "schedule_preview.jsonl").read_text().splitlines()]
    assert len(rows) == 4 and all(row["planning_only"] and row["rubric"] is None for row in rows)
    assert not (root / "ledger.jsonl").exists()
    with pytest.raises(RunnerError, match="execution requires --rubric-dir"):
        task_cli.main((args) + ["--resume"])
    rubrics = tmp_path / "rubrics"
    write_json(rubrics / "custom.json", {"task_id": "custom", "criteria": [{"id": "heading", "description": "Read heading."}]})
    # A renamed preview must not become an executable resume ledger.
    write_json_lines(root / "ledger.jsonl", rows)
    with pytest.raises(RunnerError, match="planning-only"):
        task_cli.main((args + ["--rubric-dir", str(rubrics)]) + ["--resume"])
    (root / "ledger.jsonl").unlink()
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    assert task_cli.main((args + ["--rubric-dir", str(rubrics)]) + ["--resume"]) == 0
    executed = [json.loads(line) for line in (root / "ledger.jsonl").read_text().splitlines()]
    assert all(not row["planning_only"] and row["completed"] for row in executed)
    assert (root / "schedule_preview.jsonl").is_file()

@pytest.mark.usefixtures('no_network')
def test_published_catalog_has_exact_compact_schema():
    root = Path(__file__).resolve().parents[2]
    expected = {"task_id", "task_name", "category", "instruction", "start_url", "stopping_condition", "constraints", "difficulty"}
    first_constraint = ("Only use the browser actions available to you. Do not open API endpoints, raw data files, "
        "view-source pages or downloads, and do not use external programs.")
    rows = [json.loads(line) for line in (root / "data/tasks.jsonl").read_text().splitlines()]
    assert len(rows) == 40
    assert all(set(row) == expected and row["constraints"][0] == first_constraint for row in rows)
    validity = json.loads((root / "internal/task_validity.json").read_text())
    assert set(validity) == {"catalog", "tasks"}
    assert validity["catalog"] == "data/tasks.jsonl"
    assert set(validity["tasks"]) == {row["task_id"] for row in rows}
    assert all(set(item) == {"valid_until"} for item in validity["tasks"].values())
    pilot = {row["task_id"]: row["difficulty"] for row in rows
             if row["task_id"] in {"task_26", "task_02", "task_19", "task_25"}}
    assert pilot == {"task_26": "easy", "task_02": "medium", "task_19": "hard", "task_25": "complex"}

@pytest.mark.usefixtures('no_network')
def test_batch_resume_rejects_byte_changes_to_frozen_catalog(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.jsonl"
    original = (json.dumps({"task_id": "custom", "instruction": "Read heading.", "start_url": "https://example.test"}) + "\r\n").encode()
    catalog.write_bytes(original)
    rubrics = tmp_path / "rubrics"
    write_json(rubrics / "custom.json", {"task_id": "custom", "criteria": [{"id": "heading", "description": "Read heading."}]})
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    output = tmp_path / "output"
    arguments = ["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gpt-6.1-sol", "--output-dir", str(output), "--run-name", "hash-check",
        "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    assert task_cli.main(arguments) == 0
    frozen = output / "hash-check/catalog.jsonl"
    assert frozen.read_bytes() == original
    frozen.write_bytes(original.replace(b"\r\n", b"\n"))
    with pytest.raises(RunnerError, match="saved batch catalog differs"):
        task_cli.main((arguments) + ["--resume"])

@pytest.mark.usefixtures('no_network')
def test_remote_catalog_hash_uses_one_download_and_forwards_frozen_bytes(tmp_path, monkeypatch):
    payload = (json.dumps({"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test"}) + "\r\n").encode()
    downloads = []
    def downloaded(request, **kwargs):
        downloads.append(request.full_url)
        return io.BytesIO(payload)
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli.urllib.request, "urlopen", downloaded)
    definition = task_cli.fetch_catalog_task("https://catalog.example.invalid/tasks.jsonl", "custom")
    expected = hashlib.sha256(payload).hexdigest()
    assert downloads == ["https://catalog.example.invalid/tasks.jsonl"]
    assert definition["catalog_sha256"] == expected
    assert Path(definition["source_catalog"]).name == f"{expected}.jsonl"
    assert Path(definition["source_catalog"]).read_bytes() == payload
    assert task_cli.fetch_catalog_task(definition["source_catalog"], "custom")["catalog_sha256"] == expected
    assert len(downloads) == 1

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("selectors,options,message", [
    ([], [], "one task needs --observation-mode"),
    (["one", "two"], ["--observation-mode", "dom"], "one task needs --observation-mode"),
    (["one"], ["--observation-mode", "dom", "--task", "Read heading."], "manual tasks require both"),
    (["one"], ["--observation-mode", "dom", "--start-url", "https://example.test"], "manual tasks require both"),
    (["one"], ["--observation-mode", "dom"], "task selection requires"),
    (["one"], ["--observation-mode", "dom", "--judge-model", "gpt-6.1-sol"], "batch grading options require --trials"),
    (["one"], ["--observation-mode", "dom", "--rubric-dir", "rubrics", "--judge-model", "gpt-6.1-sol"], "batch grading options require --trials"),
    (["one"], ["--previous-run-stop-timeout", "-1"], "must be finite and positive"),
])
def test_launcher_validates_selection_before_launch(tmp_path, monkeypatch, capsys, selectors, options, message):
    monkeypatch.delenv("TASK_CATALOG_FILE", raising=False)
    monkeypatch.delenv("TASK_CATALOG_URL", raising=False)
    monkeypatch.setattr(task_cli.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("invalid selection launched a process"))
    output = tmp_path / "recordings"
    argument_error = "--previous-run-stop-timeout" in options
    with pytest.raises(SystemExit if argument_error else RunnerError) as caught:
        task_cli.main([*selectors, "--env-file", str(tmp_path / "absent.env"), "--output-dir", str(output), *options])
    assert message in (capsys.readouterr().err if argument_error else str(caught.value))
    if argument_error:
        assert caught.value.code == 2
    assert not output.exists()

@pytest.mark.usefixtures('no_network')
def test_batch_rechecks_catalog_before_actor_start(launcher_batch, monkeypatch):
    args, ledger, *_ = launcher_batch
    writer = task_cli.write_json_lines
    def scheduled(path, rows):
        writer(path, rows)
        if path == ledger:
            (ledger.parent / "catalog.jsonl").write_text("changed while scheduling\n")
    monkeypatch.setattr(task_cli, "write_json_lines", scheduled)
    with pytest.raises(RunnerError, match="frozen batch catalog changed after scheduling"):
        task_cli.main(args)
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert all(row["technical_outcome"] == "not_started" and not row["completed"] for row in rows)

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

def test_catalog_alias_dry_run_resolves_expanded_contract_without_launch(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
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
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
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
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
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
        task_cli.main(args + ["--resume"])
    assert ledger.read_bytes() == original

def test_settings_diff_lists_nested_fields_and_refuses_drift():
    from w8bench.settings import require_same_settings
    before = {"actor": {"model": "one", "max_turns": 200}}
    after = {"actor": {"model": "two", "max_turns": 199}}
    with pytest.raises(ValueError, match=r"actor.max_turns.*actor.model"):
        require_same_settings(before, after, label="scheduled actor")

@pytest.mark.parametrize("excluded", ["api_key", "password", "token", "port", "container_name", "compose_project_name", "image", "image_tag", "path", "file", "directory"])
def test_settings_guard_excludes_credentials_and_deployment_fields(excluded):
    from w8bench.settings import normalized_settings, require_same_settings
    before = {"model": "one", excluded: "first"}
    after = {"model": "one", excluded: "second"}
    assert normalized_settings(before) == {"model": "one"}
    require_same_settings(before, after, label="judge")

def test_effective_config_hash_depends_on_content_not_location_or_credentials(tmp_path):
    from w8bench.settings import endpoint_settings
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir(); second.mkdir()
    config = {"CHAT_COMPLETION_PROVIDER": "openai", "CHAT_COMPLETION_KWARGS_JSON": {
        "model": "gpt-5.2", "reasoning_effort": "medium", "api_key": "first-secret"}}
    (first / "model.json").write_text(json.dumps(config))
    config["CHAT_COMPLETION_KWARGS_JSON"]["api_key"] = "second-secret"
    (second / "another-name.json").write_text(json.dumps(config, indent=2))
    assert endpoint_settings(first) == endpoint_settings(second)
    config["CHAT_COMPLETION_KWARGS_JSON"]["reasoning_effort"] = "high"
    (second / "another-name.json").write_text(json.dumps(config))
    assert endpoint_settings(first) != endpoint_settings(second)
    assert "secret" not in json.dumps(endpoint_settings(first))

@pytest.mark.parametrize("field,value", [("reasoning_effort", "high"), ("max_output_tokens", 9999),
    ("max_turns", 100), ("memory_max_chars", 7000), ("base_url", "https://other.test/v1")])
def test_actor_settings_guard_protects_effective_request_controls(field, value):
    from w8bench.settings import actor_settings, require_same_settings
    controls = {"model": "gemini-3.8-flash", "reasoning_effort": "medium", "max_output_tokens": 10000,
        "max_turns": 200, "memory_max_chars": 8000, "base_url": "https://example.test/v1"}
    changed = {**controls, field: value}
    with pytest.raises(ValueError, match=field):
        require_same_settings(actor_settings(controls), actor_settings(changed), label="actor")

def test_actor_settings_include_both_observation_policies_and_exclude_resource_names():
    from w8bench.settings import actor_settings
    controls = {"model": "gemini-3.8-flash", "max_turns": 200, "image": "first:tag",
        "container_name": "first", "port": 9999}
    settings = actor_settings(controls)
    assert set(settings["prompt_sha256"]) == {"dom", "screenshot"}
    assert settings["memory_max_chars"] == 8000
    assert "container_name" not in settings and "image" not in settings and "port" not in settings

def test_judge_settings_bind_rubric_prompts_schema_and_each_stage(monkeypatch):
    from w8bench.settings import evaluation_settings
    monkeypatch.setenv("EVIDENCE_AUDIT_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_MODEL", "gpt-6.1-sol")
    recording = {"manifest": {"controls": {"model": "gemini-3.8-flash"}}, "task": {}}
    settings = evaluation_settings(recording, eval_config="config", rubric_hash="one", judge_model="gpt-6.1-sol")
    assert settings["rubric_sha256"] == "one"
    assert set(settings["stages"]) == {"completion", "screenshot_verifier", "dom_model", "inventory", "adjudication", "rubric_preparation"}
    for stage in settings["stages"].values():
        assert stage["models"] and stage["prompt_sha256"]
    assert settings["stages"]["completion"]["schema_sha256"]
    assert "base_url" in settings["stages"]["inventory"]

@pytest.mark.usefixtures('no_network')
@pytest.mark.parametrize("field,value", [("reasoning_effort", "high"), ("max_tokens", 9000),
    ("base_url", "https://another.test/v1")])
def test_evaluation_resume_refuses_judge_config_drift_before_cached_stages(full_evaluation, tmp_path, monkeypatch, field, value):
    paths, rubric, calls = full_evaluation
    monkeypatch.setattr(package_manifests, "require_local_packages", lambda: {})
    config = tmp_path / "config"
    shutil.copytree(comparison.DEFAULT_CONFIG, config)
    args = evaluation_args(paths, rubric, config)
    assert comparison.main(args) == 0
    receipt = next(tmp_path.rglob("evaluation.json"))
    before = receipt.read_bytes()
    counts = {name: len(rows) for name, rows in calls.items()}
    path = config / "google_gemini3_5_flash_lite.json"
    changed = json.loads(path.read_text())
    changed["CHAT_COMPLETION_KWARGS_JSON"][field] = value
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="effective settings differ"):
        comparison.main(args)
    assert {name: len(rows) for name, rows in calls.items()} == counts
    assert receipt.read_bytes() == before

@pytest.mark.usefixtures('no_network')
def test_evaluation_resume_accepts_identical_config_at_another_location(full_evaluation, tmp_path, monkeypatch):
    paths, rubric, calls = full_evaluation
    monkeypatch.setattr(package_manifests, "require_local_packages", lambda: {})
    first, second = tmp_path / "first-config", tmp_path / "second-config"
    shutil.copytree(comparison.DEFAULT_CONFIG, first)
    assert comparison.main(evaluation_args(paths, rubric, first)) == 0
    counts = {name: len(rows) for name, rows in calls.items()}
    shutil.copytree(first, second)
    assert comparison.main(evaluation_args(paths, rubric, second)) == 0
    assert {name: len(rows) for name, rows in calls.items()} == counts

@pytest.mark.usefixtures('no_network')
def test_completion_refusal_resumes_without_turning_unknown_into_failure(full_evaluation, tmp_path, monkeypatch):
    paths, rubric, calls = full_evaluation
    monkeypatch.setattr(package_manifests, "require_local_packages", lambda: {})
    original = completion.ModelClient._post
    def mismatch(self, payload):
        response = original(self, payload)
        return {**response, "model": "gpt-5.2"}
    monkeypatch.setattr(completion.ModelClient, "_post", mismatch)
    args = evaluation_args(paths, rubric, comparison.DEFAULT_CONFIG)
    assert comparison.main(args) == 1
    receipt = next(tmp_path.rglob("evaluation.json"))
    first = json.loads(receipt.read_text())["stages"]["paired_completion"]
    assert first["status"] == first["verdict"] == "ungraded"
    assert first["usage"]["total_tokens"] == 70
    monkeypatch.setattr(completion.ModelClient, "_post", original)
    assert comparison.main(args) == 0
    stage = json.loads(receipt.read_text())["stages"]["paired_completion"]
    assert stage["verdict"] == "success"
    assert stage["attempt_history"][0]["verdict"] == "ungraded"
    assert stage["attempt_history"][0]["usage"]["total_tokens"] == 70

@pytest.mark.usefixtures('no_network')
def test_audit_refusal_is_ungraded_and_has_no_directional_values(full_evaluation, tmp_path, monkeypatch):
    from w8bench.verifier import evidence_audit
    from w8bench.verifier.audit_requests import AuditValidationError
    paths, rubric, calls = full_evaluation
    monkeypatch.setattr(package_manifests, "require_local_packages", lambda: {})
    def refused(**kwargs):
        kwargs["call_records"].append({"stage": "inventory", "model": "gemini-3.1-pro-preview",
            "response_model": "other", "refusal_reason": "returned model mismatch", "usage": {"prompt_tokens": 8, "completion_tokens": 2}})
        raise AuditValidationError("inventory", [{"refusal_reason": "returned model mismatch"}], ValueError("returned model mismatch"))
    monkeypatch.setattr(evidence_audit, "run_evidence_audit", refused)
    assert comparison.main(evaluation_args(paths, rubric, comparison.DEFAULT_CONFIG)) == 1
    receipt = next(tmp_path.rglob("evaluation.json"))
    stage = json.loads(receipt.read_text())["stages"]["audit"]
    assert stage["status"] == "ungraded" and stage["reason"]
    assert "metrics" not in stage
    assert stage["calls"][0]["usage"]["prompt_tokens"] == 8
