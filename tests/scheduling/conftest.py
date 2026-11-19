"""Shared scheduling fixtures."""

import json
import os
from pathlib import Path

import pytest

from w8bench.task_recorder import task_cli
from w8bench.task_recorder.recorder_support import write_json


@pytest.fixture
def curated_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(task_cli, "ROOT", tmp_path)
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    row = {"task_id": "task_19", "task_name": "Public heading", "category": "research",
        "instruction": "Read the heading.", "start_url": "https://example.test",
        "stopping_condition": "Report the heading.", "constraints": ["Remain read-only."], "difficulty": "medium"}
    catalog = tmp_path / "data" / "tasks.jsonl"
    catalog.parent.mkdir()
    catalog.write_bytes((json.dumps(row) + "\r\n").encode())
    write_json(tmp_path / "internal" / "task_validity.json", {"catalog": "data/tasks.jsonl",
        "tasks": {"task_19": {"valid_until": "2000-12-31"}}})
    return catalog, row

@pytest.fixture
def launcher_batch(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.",
        "start_url": "https://example.test"}) + "\n")
    rubrics = tmp_path / "rubrics"
    write_json(rubrics / "custom.json", {"task_id": "custom", "criteria": [{"id": "heading", "description": "Read heading."}]})
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    original_iterdir = Path.iterdir
    monkeypatch.setattr(Path, "iterdir", lambda path: iter(()) if path == Path("/proc") else original_iterdir(path))
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: pytest.fail("unexpected batch process"))
    output = tmp_path / "recordings"
    args = ["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gpt-6.1-sol", "--output-dir", str(output), "--run-name", "collection",
        "--env-file", str(tmp_path / "absent.env")]
    return args, output / "collection" / "ledger.jsonl", catalog, rubrics

@pytest.fixture
def effective_settings_batch(tmp_path, monkeypatch):
    import shutil
    from types import SimpleNamespace

    from w8bench import settings
    from w8bench.task_recorder import task_cli
    from w8bench.task_recorder.recorder_support import write_json

    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("EVIDENCE_AUDIT_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_MODEL", "gpt-6.1-sol")
    monkeypatch.setenv("EVIDENCE_AUDIT_PROVIDER", "google")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_PROVIDER", "openai")
    config_root = tmp_path / "settings"
    shutil.copytree(settings.ROOT / "config", config_root / "config")
    shutil.copytree(settings.ROOT / "protocol", config_root / "protocol")
    monkeypatch.setattr(settings, "ROOT", config_root)
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    original_iterdir = Path.iterdir
    monkeypatch.setattr(Path, "iterdir", lambda path: iter(()) if path == Path("/proc") else original_iterdir(path))
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: pytest.fail("settings preflight launched a process"))
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read the heading.", "start_url": "https://example.test/"}) + "\n")
    rubrics = tmp_path / "rubrics"
    write_json(rubrics / "custom.json", {"task_id": "custom", "criteria": [{"id": "heading", "description": "Report the heading."}]})
    output = tmp_path / "recordings"
    arguments = ["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gpt-6.1-sol", "--output-dir", str(output), "--run-name", "settings",
        "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    return SimpleNamespace(arguments=arguments, ledger=output / "settings/ledger.jsonl", catalog=catalog,
        rubric_dir=rubrics, config_root=config_root)
