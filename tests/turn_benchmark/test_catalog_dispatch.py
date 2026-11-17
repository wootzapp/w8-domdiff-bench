"""Scheduled actors consume the catalog bytes frozen in their ledger."""

import json
from pathlib import Path
from types import SimpleNamespace

from w8bench.task_recorder import task_cli
from w8bench.task_recorder.recorder_support import write_json


def test_each_actor_reads_the_frozen_catalog_when_the_original_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
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
