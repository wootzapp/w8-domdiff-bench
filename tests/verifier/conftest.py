from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from w8bench.verifier.common import canonical_sha256


@pytest.fixture(autouse=True)
def audit_test_configuration(monkeypatch):
    monkeypatch.setenv("EVIDENCE_AUDIT_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_MODEL", "gpt-6.1-sol")
    monkeypatch.setenv("EVIDENCE_AUDIT_PROVIDER", "google")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_PROVIDER", "openai")



RUBRIC = {
    "items": [
        {
            "criterion": "The saved value is visible in the final state",
            "description": "The UI explicitly shows the value Saved.",
            "max_points": 7,
            "justification": "",
            "earned_points": "",
        },
        {
            "criterion": "No page error is shown",
            "description": "The final browser state has no explicit error.",
            "max_points": 3,
            "justification": "",
            "earned_points": "",
        },
    ]
}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def pair_factory(tmp_path):
    def make(*, sidecars: bool = True, metrics: bool = True):
        staged = tmp_path / "staged"
        screenshot = staged / "data-ss" / "task1"
        dom = staged / "data-dom" / "task1"
        screenshot.mkdir(parents=True)
        dom.mkdir(parents=True)
        task = {
            "task_id": "internal-task-1",
            "confirmed_task": "Set the example value and save it.",
            "website": "https://example.test/start",
        }
        _write_json(screenshot / "task_data.json", task)
        _write_json(dom / "task_data.json", task)
        screenshot_event = {
            "action": "left_click",
            "url": "https://example.test/done",
            "arguments": {
                "action": "left_click",
                "coordinate": [10, 20],
                "ref": "save-button",
                "target": {"role": "button", "name": "Save"},
                "thoughts": "Save the value",
            },
        }
        (screenshot / "web_surfer.log").write_text(json.dumps(screenshot_event) + "\n", encoding="utf-8")
        (dom / "web_surfer.log").write_text(json.dumps(screenshot_event) + "\n", encoding="utf-8")
        (screenshot / "screenshot0.png").write_bytes(b"offline-placeholder-0")
        (screenshot / "screenshot1.png").write_bytes(b"offline-placeholder-1")
        _write_json(
            screenshot / "final_answer.json",
            {
                "final_answer": "Saved",
                "is_aborted": False,
                "screenshots": ["screenshot0.png", "screenshot1.png"],
                "token_usage": {},
            },
        )
        _write_json(
            dom / "final_answer.json",
            {"final_answer": "Saved", "is_aborted": False, "token_usage": {}},
        )
        (dom / "dom_model0.txt").write_text(
            "URL: https://example.test/start\n"
            "Title: Example\n"
            "Snapshot: returnedNodes=2 groups=1 truncated=false\n"
            "=== VISIBLE CONTENT ===\n"
            "[save-button] role=button name=Save value=Ready\n"
            "Dialog: none\n",
            encoding="utf-8",
        )
        (dom / "dom_model1.txt").write_text(
            "URL: https://example.test/done\n"
            "Title: Example Saved\n"
            "Snapshot: returnedNodes=3 groups=1 truncated=false\n"
            "=== VISIBLE CONTENT ===\n"
            "Status: Saved\n"
            "[save-button] role=button name=Save value=Saved\n"
            "Error: none\n",
            encoding="utf-8",
        )
        rubric_path = tmp_path / "experiment" / "rubrics" / "task1.json"
        _write_json(rubric_path, {"task_id": task["task_id"], "precomputed_rubric": RUBRIC})
        if sidecars:
            _write_json(screenshot / "task_data_with_canonical_rubric.json", {**task, "precomputed_rubric": RUBRIC})
            _write_json(dom / "task_data_with_canonical_rubric.json", {**task, "precomputed_rubric": RUBRIC})
        metrics_path = tmp_path / "experiment" / "rubrics" / "task1_generation_metrics.json"
        if metrics:
            _write_json(
                metrics_path,
                {
                    "phase": "A",
                    "origin": "validated_import",
                    "task_id": task["task_id"],
                    "frozen_rubric_sha256": canonical_sha256(RUBRIC),
                    "criterion_count": 2,
                    "criterion_denominator": 10.0,
                    "criteria": [item["criterion"] for item in RUBRIC["items"]],
                    "maximum_points": [7.0, 3.0],
                    "rubric_generation_calls": 0,
                    "token_usage": {"combined": {"total_tokens": 0}},
                },
            )
        config = tmp_path / "endpoints"
        _write_json(
            config / "gpt.json",
            {"CHAT_COMPLETION_PROVIDER": "openai", "CHAT_COMPLETION_KWARGS_JSON": {"model": "gpt-5.2"}},
        )
        _write_json(
            config / "action_judge.json",
            {"CHAT_COMPLETION_PROVIDER": "google", "CHAT_COMPLETION_KWARGS_JSON": {"model": "gemini-3.8-flash", "reasoning_effort": "medium"}},
        )
        _write_json(
            config / "judge.json",
            {"CHAT_COMPLETION_PROVIDER": "google", "CHAT_COMPLETION_KWARGS_JSON": {
                "model": "gemini-3.1-pro-preview", "reasoning_effort": "medium"}},
        )
        return {
            "staged": staged,
            "screenshot": screenshot,
            "dom": dom,
            "rubric": rubric_path,
            "metrics": metrics_path,
            "config": config,
            "task": task,
        }

    return make


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in {".venv", "__pycache__", ".pytest_cache", ".git"} for part in path.parts):
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture
def metric_recording_factory(tmp_path):
    """Build independent actor receipts for offline accounting contracts."""
    counter = 0

    def make(*, arm="dom", usage=None, task_id="custom", trial="trial_0001"):
        nonlocal counter
        counter += 1
        source = tmp_path / f"source_{counter}" / trial / arm / task_id
        source.mkdir(parents=True)
        return {
            "source": str(source),
            "recording_sha256": str(counter).zfill(64),
            "task": {
                "source_task_id": task_id,
                "observation_mode": arm,
                "run_name": trial,
                "model": "gemini-3.1-pro-preview",
            },
            "manifest": {"controls": {"max_turns": 200}, "states": [], "steps": []},
            "decisions": [
                {"accepted": False, "returned_model": "gemini-3.1-pro-preview", "usage": usage,
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
        root = (source.parent.parent / "evaluations" / task["run_name"] /
                task["observation_mode"] / task["source_task_id"] / recording["recording_sha256"])
        root.mkdir(parents=True, exist_ok=True)
        evaluation = {
            "recording_sha256": recording["recording_sha256"],
            "task_id": task["source_task_id"], "actor_arm": task["observation_mode"],
            "trial_id": task["run_name"], "rubric_sha256": "frozen-rubric",
            "stages": stages or {},
        }
        _write_json(root / "evaluation.json", evaluation)
        if grade_usage is not None:
            _write_json(source / "completion.json", {
                "recording_sha256": recording["recording_sha256"],
                "task_id": task["source_task_id"], "observation_mode": task["observation_mode"],
                "rubric_sha256": "frozen-rubric", "evidence_policy": "paired",
                "method": "model_judge", "verdict": "success", "criteria": [],
                "judge_model": "gpt-6.1-sol", "returned_judge_model": "gpt-6.1-sol",
                "judge_calls": 1, "usage": grade_usage,
            })
        return root, evaluation

    return make


@pytest.fixture
def settings_comparison_case(tmp_path, monkeypatch, metric_recording_factory, metric_evaluation_factory):
    """Provide finalized synthetic runs and a full scheduled settings contract."""
    from copy import deepcopy
    from types import SimpleNamespace
    from w8bench.verifier import run_full_comparison

    actor = {"schema_version": "effective-settings/v1", "model": "gemini-3.1-pro-preview",
             "base_url": "https://actor.example:443/v1", "max_turns": 200, "max_output_tokens": 10000,
             "reasoning_effort": "medium", "memory_max_chars": 8000,
             "browser_source": {"overlay_revision": "overlay-one", "protocol_sha256": "protocol-one"}}
    contract = {"schema_version": "effective-settings/v1", "actor": actor,
                "browser_source": deepcopy(actor["browser_source"]), "rubric_sha256": "rubric-custom",
                "stages": {"completion": {"models": ["gpt-6.1-sol"], "reasoning_effort": "medium", "max_output_tokens": 10000},
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
                            "browser_build": {"image_id": "immutable-image", "overlay_revision": "overlay-one", "protocol_sha256": "protocol-one"},
                            "browser_environment": {"LANG": "en_US.UTF-8", "CDP_PORT": "9222", "CHROMIUM_CDP_PORT": "9223"}})
        manifest["controls"].update(model="gemini-3.1-pro-preview", base_url=actor["base_url"], max_output_tokens=10000, reasoning_effort="medium")
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



@pytest.fixture
def completion_case(tmp_path, monkeypatch):
    """One validated recording, its task rubric and a transport response queue."""
    from copy import deepcopy
    from types import SimpleNamespace
    from w8bench.verifier import completion
    run = tmp_path / "attempt"
    run.mkdir()
    dom = run / "dom_model.txt"
    dom.write_text("Marker: SAVED\n", encoding="utf-8")
    image = run / "screenshot.png"
    image.write_bytes(b"same-run-screenshot")
    references = run / "agent_browser_actions.txt"
    references.write_text('- button "Save" [ref=e1]\n', encoding="utf-8")
    recording = {
        "task": {"source_task_id": "marker", "instruction": "Read the saved marker.",
            "start_url": "https://example.test/marker", "observation_mode": "dom"},
        "recording_sha256": "a" * 64,
        "manifest": {"model_turns": 3, "steps": [], "states": [{"state": 1,
            "artifacts": {name: {"path": name} for name in
                ("dom_model.txt", "screenshot.png", "agent_browser_actions.txt")}}]},
        "final": {"final_answer": "SAVED", "run_status": "completed"},
        "coverage": {"observed_url_timeline": [{"state": 1, "url": "https://example.test/marker"}]},
    }
    rubric = {"task_id": "marker", "instruction": "Read the saved marker.",
        "start_url": "https://example.test/marker", "criteria": [
            {"id": "saved", "description": "The saved marker is visible."},
            {"id": "source", "description": "The marker source is established."}]}
    rubric_path = tmp_path / "rubric.json"
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")
    monkeypatch.setattr(completion, "inspect_recording", lambda path: deepcopy(recording))
    responses, requests = [], []
    def post(self, payload):
        requests.append(deepcopy(payload))
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(completion.ModelClient, "_post", post)
    monkeypatch.setattr(completion.asyncio, "to_thread", inline)
    return SimpleNamespace(run=run, recording=recording, rubric=rubric,
        rubric_path=rubric_path, responses=responses, requests=requests)



@pytest.fixture
def isolated_verifier_package(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from w8bench.verifier import package_manifests
    root = tmp_path / "distribution"
    package = root / "w8bench" / "verifier" / "dom_model"
    package.mkdir(parents=True)
    (package / "runner.py").write_text('"""Offline runner fixture."""\n')
    clients = package.parent / "clients"
    clients.mkdir()
    (clients / "messages.py").write_text('"""Offline message fixture."""\n')
    (package.parent / "models.py").write_text('"""Offline type fixture."""\n')
    manifests = root / "manifests"
    manifests.mkdir()
    monkeypatch.setattr(package_manifests, "__file__", str(package.parent / "package_manifests.py"))
    monkeypatch.setattr(package_manifests, "REPOSITORY_ROOT", root)
    monkeypatch.setattr(package_manifests, "MANIFEST_ROOT", manifests)
    monkeypatch.setattr(package_manifests, "PACKAGE_ROOTS", {"dom_model": package})
    receipt = package_manifests.tree_receipt("dom_model")
    manifest = manifests / "dom_model.json"
    manifest.write_text(json.dumps(receipt))
    return SimpleNamespace(root=root, package=package, manifest=manifest, receipt=receipt)

