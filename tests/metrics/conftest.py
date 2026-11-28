"""Shared metrics fixtures."""

import json
import hashlib
import os
from pathlib import Path
from w8bench.run_paths import run_directory

import pytest

from tests.conftest import _write_json
from w8bench.task_recorder import task_cli
from w8bench.task_recorder.recorder_support import write_json


@pytest.fixture
def metric_recording_factory(tmp_path):
    """Build independent actor receipts for offline accounting contracts."""
    counter = 0

    def make(*, arm="dom", usage=None, task_id="custom", trial="trial_0001"):
        nonlocal counter
        counter += 1
        source = tmp_path / f"source_{counter}" / "recordings" / trial / arm / task_id
        source.mkdir(parents=True)
        return {
            "source": str(source),
            "recording_sha256": str(counter).zfill(64),
            "task": {
                "source_task_id": task_id,
                "observation_mode": arm,
                "run_name": trial,
                "model": "gemini-3.8-flash",
            },
            "manifest": {"controls": {"max_turns": 200}, "states": [], "steps": []},
            "decisions": [
                {"accepted": False, "returned_model": "gemini-3.8-flash", "usage": usage,
                 "latency_seconds": 0.1, "output_limit_hit": False}
            ],
            "final": {"run_status": "completed", "status": "failure"},
        }

    return make

@pytest.fixture
def metric_evaluation_factory():
    """Bind synthetic evaluation and grade receipts to one actor recording."""
    def make(recording, *, stages=None, grade_usage=None):
        source = Path(recording["source"])
        task = recording["task"]
        root = run_directory(source, area="evaluations") / "primary"
        root.mkdir(parents=True, exist_ok=True)
        evaluation = {
            "recording_sha256": recording["recording_sha256"],
            "task_id": task["source_task_id"], "actor_arm": task["observation_mode"],
            "trial_id": task["run_name"], "rubric_sha256": "frozen-rubric",
            "stages": stages or {},
        }
        _write_json(root / "evaluation.json", evaluation)
        if grade_usage is not None:
            _write_json(root.parent / "completion.json", {
                "recording_sha256": recording["recording_sha256"],
                "task_id": task["source_task_id"], "observation_mode": task["observation_mode"],
                "rubric_sha256": "frozen-rubric", "evidence_policy": "paired",
                "method": "model_judge", "verdict": "success", "criteria": [],
                "judge_model": "gemini-3.6-flash", "returned_judge_model": "gemini-3.6-flash",
                "judge_calls": 1, "usage": grade_usage,
            })
            evaluation["stages"].setdefault("paired_completion", {})["result"] = str(root.parent / "completion.json")
            _write_json(root / "evaluation.json", evaluation)
        return root, evaluation

    return make

@pytest.fixture
def settings_comparison_case(tmp_path, monkeypatch, metric_recording_factory, metric_evaluation_factory):
    """Provide finalized synthetic runs and a full scheduled settings contract."""
    from copy import deepcopy
    from types import SimpleNamespace
    from w8bench.verifier import run_full_comparison

    actor = {"schema_version": "effective-settings/v1", "model": "gemini-3.8-flash",
             "base_url": "https://actor.example:443/v1", "max_turns": 200, "max_output_tokens": 10000,
             "reasoning_effort": "medium", "memory_max_chars": 8000,
             "browser_source": {"overlay_revision": "overlay-one", "protocol_sha256": "protocol-one"}}
    contract = {"schema_version": "effective-settings/v1", "actor": actor,
                "browser_source": deepcopy(actor["browser_source"]), "rubric_sha256": "rubric-custom",
                "stages": {"completion": {"models": ["gemini-3.6-flash"], "reasoning_effort": "medium", "max_output_tokens": 10000},
                           "dom_model": {"models": ["gemini-3.1-pro-preview"], "reasoning_effort": "medium", "max_output_tokens": None,
                                         "config_sha256": "config-content", "base_url": "https://judge.example:443/v1"},
                           "inventory": {"prompt_sha256": "inventory-prompt", "validation_attempts": 3}}}
    recordings, rows = {}, []
    for arm in ("dom", "screenshot"):
        recording = metric_recording_factory(arm=arm, usage={"input_tokens": 4, "output_tokens": 2})
        recording["task"].update(instruction="Read title.", start_url="https://example.test", category=None, difficulty=None)
        manifest = recording["manifest"]
        manifest.update(run_name="trial_0001", status="completed", effective_settings=deepcopy(actor),
                        dom_capture_parameters={"max_nodes": 7000}, renderer_versions={"model": {"sha256": "renderer"}},
                        browser_profile_provenance={"profile_fresh_at_run_start": True,
                            "freshly_recreated_by_launcher": True, "launch_mode": "fresh", "tasks_previously_run_in_container": 0,
                            "browser_build": {"image_id": "immutable-image", "overlay_revision": "overlay-one", "protocol_sha256": "protocol-one"},
                            "browser_environment": {"CHROMIUM_RESET_PROFILE": "1", "LANG": "en_US.UTF-8", "CDP_PORT": "9222", "CHROMIUM_CDP_PORT": "9223"}})
        manifest["controls"].update(model="gemini-3.8-flash", base_url=actor["base_url"], max_output_tokens=10000, reasoning_effort="medium")
        from w8bench.task_recorder.runner import ACTION_SCHEMA, SCREENSHOT_ACTION_SCHEMA
        manifest["controls"]["action_schema_sha256"] = hashlib.sha256(json.dumps(
            ACTION_SCHEMA if arm == "dom" else SCREENSHOT_ACTION_SCHEMA, sort_keys=True).encode()).hexdigest()
        source = Path(recording["source"])
        _write_json(source / "final.json", recording["final"])
        root, evaluation = metric_evaluation_factory(recording)
        evaluation.update(effective_settings=deepcopy(contract), status="complete")
        _write_json(root / "evaluation.json", evaluation)
        recordings[str(source.resolve())] = recording
        rows.append({"task_id": "custom", "trial": 1, "trials": 1, "arm": arm, "run_name": "trial_0001",
                     "recording": str(source), "technical_outcome": "completed", "catalog_sha256": None,
                     "configuration": deepcopy(manifest["controls"]), "task": deepcopy(recording["task"]),
                     "effective_settings": deepcopy(contract)})
    monkeypatch.setattr(run_full_comparison, "inspect_recording", lambda path: recordings[str(Path(path).resolve())])
    return SimpleNamespace(rows=rows, recordings=recordings, contract=contract, actor=actor,
                           ledger=tmp_path / "ledger.jsonl", output=tmp_path / "report")
