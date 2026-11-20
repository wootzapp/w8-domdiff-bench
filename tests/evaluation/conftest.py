"""Evaluation-only evidence, rubric and package fixtures."""
from __future__ import annotations

from copy import deepcopy
from functools import partial
from pathlib import Path
from tests.conftest import RUBRIC
from types import ModuleType, SimpleNamespace
from types import SimpleNamespace
from unittest.mock import Mock
from w8bench.verifier import completion
from w8bench.verifier import completion, package_manifests
from w8bench.verifier import generate_frozen_rubric as generator
from w8bench.verifier.audit_requests import _request_validated_audit
from w8bench.verifier.common import canonical_sha256
from w8bench.verifier.dom_model.states import DomModelState
from w8bench.verifier.evidence_audit import run_evidence_audit
import copy
import json
import pytest
import sys


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


def _state() -> DomModelState:
    return DomModelState(
        index=1,
        path=Path("dom_model1.txt"),
        raw_text="URL: https://example.test\nLabel: Account\nValue: Active\n",
        sha256="0" * 64,
        byte_count=58,
        line_count=3,
        estimated_tokens=15,
        url="https://example.test",
        title="Example",
    )


def _source_decision(modality, *, coverage="COMPLETE", caught=True):
    if coverage == "ABSENT":
        return {
            "coverage": coverage,
            "available_evidence": [],
            "missing_required_evidence": ["criterion evidence"],
            "verifier_caught": caught,
            "citations": [],
        }
    return {
        "coverage": coverage,
        "available_evidence": ["Saved"],
        "missing_required_evidence": [] if coverage == "COMPLETE" else ["associated value"],
        "verifier_caught": caught,
        "citations": [{
            "source": "screenshot1.png" if modality == "screenshot" else "dom_model1.txt",
            "location": "status area" if modality == "screenshot" else "L0005-L0007",
            "quote": "Saved",
        }],
    }


def _finding(confirmed=False, *, evidence="", modality="dom_model"):
    if not confirmed:
        return {
            "confirmed": False,
            "decisive_evidence": "",
            "citations": [],
            "explanation": "The strict confirmation gates are not met.",
        }
    return {
        "confirmed": True,
        "decisive_evidence": evidence or "Saved",
        "citations": [{
            "source": "screenshot1.png" if modality == "screenshot" else "dom_model1.txt",
            "location": "status area" if modality == "screenshot" else "L0005-L0007",
            "quote": evidence or "Saved",
        }],
        "explanation": "The cited decisive evidence is available and was materially missed.",
    }


def _validated_request_case(pair, stage):
    if stage == "inventory":
        response = {"criteria": [{
            "criterion_index": 0, "required_evidence": "Saved status",
            "screenshot": _source_decision("screenshot"),
            "dom_model": _source_decision("dom_model"),
            "screenshot_evidence_loss": False, "dom_model_evidence_loss": False,
            "explanation": "Both sources show Saved.",
        }]}
        requester = _request_validated_audit
        validation_error = "Evidence auditor returned an incomplete criteria list"
        error_stage = "primary evidence inventory"
        feedback = (
            "Your JSON failed validation: Evidence auditor returned an incomplete criteria list. "
            "Return a corrected complete JSON object using the required schema and the same supplied evidence."
        )
    else:
        response = {"criteria": [{
            "criterion_index": 0,
            **{field: _finding() for field in (
                "screenshot_evidence_loss", "dom_model_evidence_loss",
                "screenshot_verifier_miss", "dom_model_verifier_miss",
            )},
            "explanation": "Both sources show Saved.",
        }]}
        requester = partial(_request_validated_audit, inventory=False)
        validation_error = "Adjudicator returned an incomplete criteria list"
        error_stage = "final evidence adjudication"
        feedback = (
            "Your adjudication JSON failed validation: Adjudicator returned an incomplete criteria list. "
            "Return a corrected complete JSON object using the required schema and same evidence."
        )
    options = {
        "model": "configured-model",
        "messages": [{"role": "system", "content": "policy"}, {"role": "user", "content": "evidence"}],
        "criteria": [{"criterion_index": 0}],
        "screenshot_sources": {"screenshot1.png"}, "dom_sources": {"dom_model1.txt"},
        "screenshot_root": pair["screenshot"], "dom_root": pair["dom"],
    }
    return requester, response, options, validation_error, error_stage, feedback


def _responses():
    inventory, adjudication = {"criteria": []}, {"criteria": []}
    for index in range(2):
        inventory["criteria"].append({
            "criterion_index": index, "required_evidence": "Saved status",
            "screenshot": _source_decision("screenshot"),
            "dom_model": _source_decision("dom_model"),
            "screenshot_evidence_loss": False, "dom_model_evidence_loss": False,
            "explanation": "Both sources preserve the status.",
        })
        adjudication["criteria"].append({
            "criterion_index": index, "screenshot_evidence_loss": _finding(),
            "dom_model_evidence_loss": _finding(), "screenshot_verifier_miss": _finding(),
            "dom_model_verifier_miss": _finding(), "explanation": "No confirmed gap.",
        })
    return inventory, adjudication


def _run(pair, complete):
    frozen = json.loads(pair["rubric"].read_text())
    result = {"task_id": pair["task"]["task_id"],
              "rubric_sha256": canonical_sha256(frozen["precomputed_rubric"]),
              "intermediate_mm_rubric_steps": {"step6_rescoring_summary": [
                  {"earned_points": 7, "max_points": 7}, {"earned_points": 3, "max_points": 3}]}}
    ss, dom = pair["staged"] / "ss-result.json", pair["staged"] / "dom-result.json"
    ss.write_text(json.dumps(result)); dom.write_text(json.dumps(result))
    return run_evidence_audit(screenshot_dir=pair["screenshot"], dom_dir=pair["dom"],
        rubric_file=pair["rubric"], screenshot_result=ss, dom_result=dom, complete=complete)


def _complete(inventory, adjudication):
    return lambda model, messages: deepcopy(inventory if model.startswith("gemini-") else adjudication)


def _fake_google(monkeypatch, text='{"ok":true}'):
    google, genai, types = ModuleType("google"), ModuleType("google.genai"), ModuleType("google.genai.types")
    types.Part = SimpleNamespace(from_text=lambda **k: k, from_bytes=lambda **k: k)
    types.Content = lambda **k: k
    types.GenerateContentConfig = lambda **k: k
    types.HttpOptions = lambda **k: k
    usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=3, thoughts_token_count=2, cached_content_token_count=4,
                            model_dump=lambda: {"prompt_token_count": 10, "candidates_token_count": 3, "thoughts_token_count": 2, "cached_content_token_count": 4})
    generate = Mock(side_effect=lambda **kwargs: SimpleNamespace(text=text, response_id="gemini-id",
        model_version=kwargs["model"] + "-001", usage_metadata=usage))
    client = Mock()
    client.__enter__ = Mock(return_value=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    client.__exit__ = Mock(return_value=False)
    constructor = Mock(return_value=client)
    genai.Client, genai.types, google.genai = constructor, types, genai
    for name, module in (("google", google), ("google.genai", genai), ("google.genai.types", types)):
        monkeypatch.setitem(sys.modules, name, module)
    return constructor, generate


class _Response:
    content = "{}"


class _Usage:
    def __init__(self, calls):
        self.prompt_tokens = 3 * calls
        self.completion_tokens = 2 * calls
        self.reasoning_tokens = calls


class _Endpoint:
    def __init__(self):
        self.calls = 0

    async def create(self, *args, **kwargs):
        self.calls += 1
        return _Response()

    def total_usage(self):
        return _Usage(self.calls)


class _Client:
    def __init__(self):
        self._clients = [_Endpoint()]

    async def create(self, *args, **kwargs):
        return await self._clients[0].create(*args, **kwargs)

    def supports_json(self):
        return True


@pytest.fixture
def catalog_case(tmp_path, monkeypatch):
    catalog = tmp_path / "tasks.jsonl"
    catalog.write_text("".join(json.dumps({"task_id": f"task_{number:02d}",
        "instruction": f"Inspect public page {number}.", "start_url": "https://example.test",
        "stopping_condition": "Report the visible fact.",
        "constraints": ["Use run-time evidence."]}) + "\n" for number in (1, 2)))
    monkeypatch.setattr(generator, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(generator, "require_local_packages", lambda: {})
    monkeypatch.setattr(generator, "validate_endpoint_configs", lambda path: {})
    monkeypatch.setattr(generator, "load_env_file", lambda path: None)
    monkeypatch.setattr(generator, "require_openai_key", lambda: None)
    def rubric_client(*args, **kwargs):
        assert kwargs["eval_model"] == "gpt-5.2"
        return _Client()
    monkeypatch.setattr(generator.GracefulRetryClient, "from_path", rubric_client)

    async def generate(self, task, context):
        assert "Stopping condition: Report the visible fact." in task
        assert "Constraints:\n- Use run-time evidence." in task
        await self._call_llm([{"role": "user", "content": "generation"}], self._judge_client)
        await self._call_llm([{"role": "user", "content": "dependency"}], self._judge_client)
        return copy.deepcopy(RUBRIC)

    monkeypatch.setattr(generator.MMRubricAgent, "_generate_rubric", generate)
    return {"root": tmp_path, "catalog": catalog, "drafts": tmp_path / "internal/rubrics/drafts",
        "frozen": tmp_path / "data/rubrics", "review": tmp_path / "internal/rubrics/review.json",
        "args": ["--catalog-file", str(catalog), "--draft-dir", str(tmp_path / "internal/rubrics/drafts"),
            "--rubric-dir", str(tmp_path / "data/rubrics")]}


@pytest.fixture
def batch_providers():
    """In-memory official SDK surfaces; no provider requests are possible."""
    class Dump:
        def __init__(self, value):
            self.value = value
        def model_dump(self, **kwargs):
            return self.value
    class Files:
        def __init__(self):
            self.data = {}
        def upload(self, *, file, config):
            key = f"files/input_{len(self.data) + 1}"
            self.data[key] = Path(file).read_bytes()
            return SimpleNamespace(name=key)
        def create(self, *, file, purpose):
            result = self.upload(file=file.name, config={})
            return SimpleNamespace(id=result.name)
        def download(self, *, file):
            return self.data[file]
        def content(self, key):
            return SimpleNamespace(content=self.data[key])
    files = Files()
    class Batches:
        def __init__(self):
            self.created, self.jobs, self.cancelled = [], {}, []
        def create(self, **kwargs):
            key = f"batches/job_{len(self.created) + 1}"
            source = kwargs.get("src", kwargs.get("input_file_id"))
            rows = [json.loads(line) for line in files.data[source].decode().splitlines()]
            self.created.append({"id": key, "kwargs": kwargs, "rows": rows})
            self.jobs[key] = {"id": key, "status": "in_progress", "state": "JOB_STATE_RUNNING"}
            return SimpleNamespace(id=key, name=key)
        def retrieve(self, key):
            return Dump(self.jobs[key])
        def get(self, *, name):
            return self.retrieve(name)
        def cancel(self, key=None, *, name=None):
            self.cancelled.append(key or name)
        def finish(self, number, *, status="completed", results=None):
            created = self.created[number]
            key = f"files/output_{number + 1}"
            if results is None:
                results = []
                for row in created['rows']:
                    ident = row.get('key', row.get('custom_id'))
                    body = {"model": "gemini-3.5-flash-lite", "value": ident}
                    results.append({"key": ident, "response": body} if 'key' in row else
                        {"custom_id": ident, "response": {"status_code": 200, "body": body}})
            files.data[key] = b''.join((json.dumps(row) + '\n').encode() for row in results)
            native = 'src' in created['kwargs']
            self.jobs[created['id']] = ({"state": {"completed": "JOB_STATE_SUCCEEDED", "expired": "JOB_STATE_EXPIRED", "failed": "JOB_STATE_FAILED"}[status],
                "dest": {"file_name": key}} if native else {"status": status, "output_file_id": key})
    batches = Batches()
    client = SimpleNamespace(files=files, batches=batches)
    return SimpleNamespace(clients={(p,n):client for p in ('google','openai') for n in (False,True)}, files=files, batches=batches)
