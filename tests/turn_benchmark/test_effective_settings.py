"""Actor scheduling binds the effective request policy before resume."""

import json
import copy
import shutil
from types import SimpleNamespace

import pytest

from w8bench import settings
from w8bench.task_recorder import task_cli
from w8bench.task_recorder.recorder_support import RunnerError, write_json_lines
from w8bench.verifier.common import canonical_sha256


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
        task_cli.main(batch.arguments)
    assert field in str(caught.value)
    assert batch.ledger.read_bytes() == before


def test_resume_refuses_changed_endpoint_request_settings(effective_settings_batch):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    endpoint = batch.config_root / "config/google_gemini3_1_pro_preview.json"
    value = json.loads(endpoint.read_text())
    value["CHAT_COMPLETION_KWARGS_JSON"]["reasoning_effort"] = "low"
    endpoint.write_text(json.dumps(value))
    with pytest.raises(RunnerError, match="effective settings differ") as caught:
        task_cli.main(batch.arguments)
    assert "endpoints" in str(caught.value)


def test_resume_ignores_deployment_and_credential_changes(effective_settings_batch, monkeypatch):
    batch = effective_settings_batch
    assert task_cli.main(batch.arguments) == 0
    for key, value in {"IMAGE": "w8-core:another-tag", "CONTAINER_NAME": "another-container",
        "COMPOSE_PROJECT_NAME": "another-project", "CDP_HOST_PORT": "49101", "NOVNC_HOST_PORT": "49102",
        "VNC_HOST_PORT": "49103", "OPENAI_API_KEY": "another-offline-key", "GEMINI_API_KEY": "another-offline-key"}.items():
        monkeypatch.setenv(key, value)
    assert task_cli.main(batch.arguments) == 0


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
    assert task_cli.main(arguments) == 0
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
        task_cli.main(batch.arguments)
    assert "rubric_sha256" in str(caught.value)


def test_resume_ignores_recorder_source_hash_when_policy_is_unchanged(effective_settings_batch, tmp_path, monkeypatch):
    batch = effective_settings_batch
    monkeypatch.setattr(task_cli, "ROOT", tmp_path)
    source = tmp_path / "w8bench/example.py"
    source.parent.mkdir()
    source.write_text('"""Module documentation."""\n')
    assert task_cli.main(batch.arguments) == 0
    source.write_text('"""Another module description."""\n')
    assert task_cli.main(batch.arguments) == 0


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
            task_cli.main(batch.arguments)
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
    assert task_cli.main(batch.arguments) == 0


def test_resume_ignores_model_endpoint_port_changes(effective_settings_batch, monkeypatch):
    batch = effective_settings_batch
    monkeypatch.setenv("GEMINI_BASE_URL", "https://actor.example.test:49101/v1beta")
    assert task_cli.main(batch.arguments) == 0
    monkeypatch.setenv("GEMINI_BASE_URL", "https://actor.example.test:49102/v1beta")
    assert task_cli.main(batch.arguments) == 0
