"""Shared offline fixtures for browser benchmark divisions."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import socket

from PIL import Image
import pytest

from w8bench.task_recorder import capture, runner, task_cli
from w8bench.task_recorder.agent_browser import AgentBrowserClient, AgentBrowserObservation
from w8bench.task_recorder.recorder_support import write_json, write_json_lines
from w8bench.verifier import completion, evidence_audit, run_comparison as comparison
from w8bench.verifier.audit_requests import ADJUDICATION_SYSTEM_PROMPT
from w8bench.verifier.common import canonical_sha256
from w8bench.verifier.evidence_audit import SCHEMA_VERSION, PROMPT_VERSION, calculate_metrics



@pytest.fixture(autouse=True)
def offline_model_access(monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("ACTOR_MEDIA_RESOLUTION", "HIGH")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test-key")
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(Path(__file__).resolve().parents[1] / ".runtime" / "tiktoken_cache"))
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError("offline tests cannot connect to model providers or external services")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)


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
def pair_factory(tmp_path):
    def make(*, sidecars: bool = True, metrics: bool = True, include_screenshot: bool = True):
        staged = tmp_path / "staged"
        screenshot = staged / "data-ss" / "task1"
        dom = staged / "data-dom" / "task1"
        if include_screenshot:
            screenshot.mkdir(parents=True)
        dom.mkdir(parents=True)
        task = {
            "task_id": "internal-task-1",
            "confirmed_task": "Set the example value and save it.",
            "website": "https://example.test/start",
        }
        if include_screenshot:
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
        if include_screenshot:
            (screenshot / "web_surfer.log").write_text(json.dumps(screenshot_event) + "\n", encoding="utf-8")
        if not include_screenshot:
            screenshot_event["arguments"].pop("coordinate")
        (dom / "web_surfer.log").write_text(json.dumps(screenshot_event) + "\n", encoding="utf-8")
        if include_screenshot:
            (screenshot / "screenshot0.png").write_bytes(b"offline-placeholder-0")
        if include_screenshot:
            (screenshot / "screenshot1.png").write_bytes(b"offline-placeholder-1")
        if include_screenshot:
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
            if include_screenshot:
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
            {"CHAT_COMPLETION_PROVIDER": "google", "CHAT_COMPLETION_KWARGS_JSON": {"model": "gemini-3.1-pro-preview", "reasoning_effort": "medium"}},
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


@pytest.fixture
def dom_pair_factory(pair_factory):
    def make(**kwargs):
        result = pair_factory(include_screenshot=False, **kwargs)
        result.pop("screenshot")
        return result
    return make


@pytest.fixture
def no_network(monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
    def forbidden(*args, **kwargs):
        raise AssertionError("offline tests must never access the network")
    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    # All worker functions are mocked; run them inline to keep this suite
    # independent of sandbox restrictions on asyncio thread wakeup sockets.
    async def immediate(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(asyncio, "to_thread", immediate)


@pytest.fixture
def inline_sdk_header_initialization(monkeypatch):
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(asyncio, "to_thread", inline)


class FakeCDP:
    instances = []

    def __init__(self, *args, observation_mode="dom", **kwargs):
        self.observation_mode = observation_mode
        self._page_failure = None
        self.page_failure_event = asyncio.Event()
        self.calls = []
        self.viewport = (1365, 768)
        self.navigation_events = []
        self.connection_report = {}
        self.target = {"targetId": "one", "url": "https://example.test"}
        self.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def call(self, method, params=None, **kwargs):
        self.calls.append((method, params))
        if method == "ChromiumRL.captureStructuredSnapshot":
            return {"snapshot": {"url": "https://example.test", "nodes": []}}
        if method == "ChromiumRL.getModelDOM":
            return {"modelDOM": {"rendererName": "chromiumrl-model-dom", "sections": [
                {"name": "header", "lines": ["URL: https://example.test", "DOM_ONLY_SECRET"]}]}}
        if method == "Page.captureScreenshot":
            buffer = io.BytesIO()
            Image.new("RGB", (1365, 768), color=(len(self.calls), 0, 0)).save(buffer, format="PNG")
            return {"data": base64.b64encode(buffer.getvalue()).decode()}
        return {}


@pytest.fixture
def run_pair(tmp_path, monkeypatch, no_network):
    monkeypatch.setenv("RUNNER_BROWSER_PROFILE_PROVENANCE", json.dumps({
        "container_id":"offline-browser", "container_created_at":"fixture", "profile_fresh_at_run_start":True,
        "tasks_previously_run_in_container":0, "freshly_recreated_by_launcher":True, "launch_mode":"fresh", "launcher_pid":os.getppid(), "browser_build":{"image_id":"offline-image"},
        "browser_environment":{"LANG":"en_US.UTF-8", "CHROMIUM_RESET_PROFILE":"1"}}))
    monkeypatch.setattr(runner, "CDPClient", FakeCDP)
    monkeypatch.setattr(runner, "synchronize_recorder_target", AsyncMock(return_value={}))
    connect = AsyncMock()
    monkeypatch.setattr(AgentBrowserClient, "connect", connect)
    monkeypatch.setattr(AgentBrowserClient, "close", AsyncMock())
    monkeypatch.setattr(AgentBrowserClient, "_invoke", AsyncMock(return_value={"success": True}))
    snapshot = AsyncMock(return_value=AgentBrowserObservation(
        text='- button "Go" [ref=e1]', refs=frozenset({"e1"}), origin="fixture",
        command=("snapshot", "-i"), targets={"e1": {"role": "button", "name": "Go"}}))
    monkeypatch.setattr(AgentBrowserClient, "snapshot", snapshot)
    payloads = {}
    paths = {}
    for mode in ("dom", "screenshot"):
        sequence = [
            {"action": "click", "id": "e999", "thought": "invalid target"},
            "malformed output",
            {"action": "click", **({"id": "e1"} if mode == "dom" else {"x": 30, "y": 40}), "thought": "click the control"},
        ]
        if mode == "screenshot":
            sequence.append({"action": "wait", "seconds": 0, "thought": "observe completion"})
        sequence.append({"action": "terminate", "status": "success", "termination_reason": "completed", "final_answer": "done", "thought": "finished"})
        payloads[mode] = []
        def post(self, payload, queue=sequence, selected=mode):
            payloads[selected].append(payload)
            item = queue.pop(0)
            return {"id": f"response-{len(payloads[selected])}", "model": "gemini-3.8-flash",
                "output_text": item if isinstance(item, str) else json.dumps(item),
                "usage": {"input_tokens": 20, "output_tokens": 10,
                    "input_tokens_details": {"cached_tokens": 5}, "output_tokens_details": {"reasoning_tokens": 3}}}
        monkeypatch.setattr(runner.ModelClient, "_post", post)
        root = tmp_path / mode
        args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"),
            "--observation-mode", mode, "--task", "Report done.", "--task-id", "task_01",
            "--source-task-id", "task_01", "--start-url", "https://example.test",
            "--output-dir", str(root), "--model", "gemini-3.8-flash", "--api-key", "offline-placeholder",
            "--max-turns", "6", "--settle-seconds", "0"])
        assert asyncio.run(runner.run(args)) == 0
        paths[mode] = root / "task_01"
    return paths, payloads, connect, snapshot


def write_attempt_ledger(path, recordings, trials):
    """Write a complete denominator, including scheduled arms with no recording."""
    first = next(iter(recordings.values()))
    task = json.loads((first / "task.json").read_text())
    controls = json.loads((first / "manifest.json").read_text())["controls"]
    configuration = {key: value for key, value in controls.items() if key != "prompt_sha256"}
    rows = []
    for trial in range(1, trials + 1):
        modes = ("dom", "screenshot") if trial % 2 else ("screenshot", "dom")
        for order, mode in enumerate(modes, 1):
            source = recordings.get((trial, mode))
            manifest = json.loads((source / "manifest.json").read_text()) if source else None
            rows.append({"sequence": len(rows) + 1, "task_id": task["source_task_id"],
                "arm": mode, "trial": trial, "trials": trials, "arm_order": order,
                "run_name": manifest.get("run_name") if manifest else f"trial_{trial:04d}",
                "task": {"instruction": task["instruction"], "start_url": task["start_url"]},
                "configuration": configuration,
                "recording": str(source or path.parent / f"absent_{trial}_{mode}"),
                "completed": True, "technical_outcome": manifest["status"] if manifest else "startup_failure",
                "grade_outcome": "ungraded"})
    write_json_lines(path, rows)
    return rows


@pytest.fixture
def full_evaluation(run_pair, tmp_path, monkeypatch):
    paths, *_ = run_pair
    rubric = tmp_path / "criteria.json"
    rubric.write_text(json.dumps({"task_id": "task_01", "instruction": "Report done.", "start_url": "https://example.test",
        "criteria": [{"id": "done", "description": "The requested result is visibly established."}]}))
    calls = {"primary": [], "scorers": [], "audit": []}
    monkeypatch.setattr(comparison, "load_env", lambda path: None)
    def grade_post(self, payload):
        calls["primary"].append(payload)
        return {"id": "grade-response", "model": "gpt-6.1-sol", "status": "completed",
            "output_text": json.dumps({"criteria": [{"id": "done", "verdict": "success", "reason": "Mock established result", "states": [1]}]}),
            "usage": {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}}
    monkeypatch.setattr(completion.ModelClient, "_post", grade_post)
    def score(command, log_path):
        calls["scorers"].append(command)
        frozen = json.loads(Path(command[command.index("--rubric-file") + 1]).read_text())["precomputed_rubric"]
        rows = [{**item, "earned_points": item["max_points"], "post_image_earned_points": item["max_points"],
                 "post_dom_earned_points": item["max_points"]} for item in frozen["items"]]
        result = {"task_id": "task_01", "rubric_sha256": canonical_sha256(frozen), "criterion_denominator": 1,
            "rubric_total_max_points": 1, "rubric_total_earned_points": 1, "rubric_score": 1, "rubric_is_success": True,
            "outcome": {"output_success": True}, "intermediate_mm_rubric_steps": {"step6_rescoring_summary": rows},
            "token_usage": {"judge": {"prompt_tokens": 10, "completion_tokens": 6, "reasoning_tokens": 2, "total_tokens": 16}},
            "call_metrics": {"judge": {"logical_calls": 1, "api_attempts": 1}}}
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Mock verifier complete\n")
        (log_path.parent / "result.json").write_text(json.dumps(result))
    monkeypatch.setattr(comparison, "_run_logged", score)
    original_audit = evidence_audit.run_evidence_audit
    def audit(**kwargs):
        calls["audit"].append(kwargs)
        def complete(model, messages):
            final = messages[0]["content"] == ADJUDICATION_SYSTEM_PROMPT
            kwargs["call_records"].append({"stage": "adjudication" if final else "inventory", "response_model": model,
                "usage": {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20}})
            if final:
                false = {"confirmed": False, "decisive_evidence": "", "citations": [], "explanation": "Mock no loss"}
                return {"criteria": [{"criterion_index": 0, "explanation": "Mock paired conclusion",
                    **{field: dict(false) for field in ("screenshot_evidence_loss", "dom_model_evidence_loss", "screenshot_verifier_miss", "dom_model_verifier_miss")}}]}
            dom = next(Path(kwargs["dom_dir"]).glob("dom_model*.txt"))
            lines = dom.read_text().splitlines()
            line = next(index for index, text in enumerate(lines, 1) if text.strip())
            return {"criteria": [{"criterion_index": 0, "required_evidence": "Requested result",
                "screenshot": {"coverage": "COMPLETE", "available_evidence": ["Mock recorded page"], "missing_required_evidence": [],
                    "verifier_caught": True, "citations": [{"source": "screenshot1.png", "location": "viewport", "quote": "Mock recorded page"}]},
                "dom_model": {"coverage": "COMPLETE", "available_evidence": [lines[line - 1]], "missing_required_evidence": [],
                    "verifier_caught": True, "citations": [{"source": dom.name, "location": f"L{line}", "quote": lines[line - 1]}]},
                "screenshot_evidence_loss": False, "dom_model_evidence_loss": False, "explanation": "Mock complete evidence"}]}
        return original_audit(**kwargs, complete=complete)
    monkeypatch.setattr(evidence_audit, "run_evidence_audit", audit)
    return paths, rubric, calls


def judge_response(verdicts, *, states=None):
    return {"id": "offline-grade", "model": "gpt-6.1-sol", "status": "completed",
        "usage": {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28},
        "output_text": json.dumps({"criteria": [
            {"id": identity, "verdict": verdict, "reason": "Recorded marker evidence.",
                "states": [1] if states is None else states}
            for identity, verdict in zip(("saved", "source"), verdicts)]})}


def native_agent(mode, *, responses=(), max_iters=2):
    module = import_module(f"w8bench.verifier.{mode}.rubric_agent")
    client = SimpleNamespace(create=AsyncMock(side_effect=[
        SimpleNamespace(content=json.dumps(value)) for value in responses]),
        supports_json=lambda: True)
    return module.MMRubricAgent(config=module.MMRubricAgentConfig(
        action_client=client, judge_client=client, max_iters=max_iters)), client


def _modality(coverage="COMPLETE", caught=True):
    return {"coverage": coverage, "verifier_caught": caught}


def _row(*, screen_loss=False, dom_loss=False, screen_caught=True, dom_caught=True):
    return {
        "screenshot": _modality("PARTIAL" if screen_loss else "COMPLETE", screen_caught),
        "dom_model": _modality("PARTIAL" if dom_loss else "COMPLETE", dom_caught),
        "screenshot_evidence_loss": screen_loss,
        "dom_model_evidence_loss": dom_loss,
    }


def _audit(task_id, rows):
    return {"task_id": task_id, "criteria": rows, "metrics": calculate_metrics(rows),
            "schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION,
            "audit_model": "gemini-3.1-pro-preview", "adjudicator_model": "gpt-6.1-sol"}


def _paired_capture_context(pair, *, dom_gaps=(), screenshot_gaps=(), navigation=()):
    """Create real same-run origin receipts around the offline paired fixture."""
    import hashlib
    for key, prefix, extension in (("screenshot", "screenshot", "png"), ("dom", "dom_model", "txt")):
        root = pair[key]
        for old in (1, 0):
            (root / f"{prefix}{old}.{extension}").rename(root / f"{prefix}{old + 1}.{extension}")
    if dom_gaps:
        for state in dom_gaps:
            (pair["dom"] / f"dom_model{state}.txt").unlink()
    for state in screenshot_gaps:
        (pair["screenshot"] / f"screenshot{state}.png").unlink()
    context = {"recording_sha256": "a" * 64, "task_id": pair["task"]["task_id"],
        "actor_arm": "screenshot", "trial_id": "trial_09", "validity_date": "2026-11-01",
        "expected_state_ids": [1, 2], "format_gaps": {"screenshot": list(screenshot_gaps), "dom_model": list(dom_gaps)},
        "navigation_states": list(navigation),
        "audit_eligible_states": [index for index in (1, 2) if index not in set(dom_gaps) | set(screenshot_gaps) | set(navigation)],
        "observed_url_timeline": [
            {"state": 1, "url": "https://example.test/start?full=query#fragment", "verified": True},
            {"state": 2, "url": "https://unverified.test/SECRET", "verified": False}],
        "source_files_sha256": {"manifest.json": "b" * 64}, "states": []}
    for state in (1, 2):
        artifacts = {}
        for key, artifact, filename in (("screenshot", "screenshot.png", f"screenshot{state}.png"), ("dom", "dom_model.txt", f"dom_model{state}.txt")):
            path = pair[key] / filename
            if path.exists():
                artifacts[artifact] = {"path": f"states/{state}/{artifact}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        context["states"].append({"state": state, "source_index": state, "eligible": state in context["audit_eligible_states"], "reason": "navigation" if state in navigation else "capture_failed" if state in dom_gaps else "paired", "artifacts": artifacts})
    for key in ("screenshot", "dom"):
        root = pair[key]
        task = json.loads((root / "task_data.json").read_text())
        task["evaluation_context"] = context
        (root / "task_data.json").write_text(json.dumps(task))
    answer_path = pair["screenshot"] / "final_answer.json"
    answer = json.loads(answer_path.read_text())
    answer["screenshots"] = [f"screenshot{index}.png" for index in (1, 2) if index not in screenshot_gaps]
    answer_path.write_text(json.dumps(answer))
    return context


def actor_preflight_response(request):
    if request.full_url.endswith(':countTokens'):
        return io.BytesIO(json.dumps({'totalTokens': 20}).encode())
    if request.get_method() == 'GET' and '/models/' in request.full_url:
        return io.BytesIO(json.dumps({'name': 'models/gemini-3.8-flash', 'inputTokenLimit': 1048576}).encode())
    return None
