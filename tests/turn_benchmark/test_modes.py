"""Small offline contract suite. No browser, network, or model service is used."""
import asyncio
import ast
import statistics
import subprocess
import time
import base64
import io
import json
import hashlib
import os
from pathlib import Path
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from w8bench.task_recorder import capture, runner, task_cli
from w8bench.task_recorder.agent_browser import AgentBrowserClient, AgentBrowserObservation
from w8bench.task_recorder.agent_browser.client import AgentBrowserError
from w8bench.task_recorder.prepare_verifier_data import inspect_recording, prepare_recording
from w8bench.task_recorder.recorder_support import RunnerError, write_json, write_json_lines
from w8bench.verifier.compare_results import compare, summarize
from w8bench.verifier.run_comparison import grade_run
from w8bench.verifier.run_full_comparison import aggregate, main as compare_main


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-terra")
    def forbidden(*args, **kwargs):
        raise AssertionError("offline tests must never access the network")
    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    # All worker functions are mocked; run them inline to keep this suite
    # independent of sandbox restrictions on asyncio thread wakeup sockets.
    async def immediate(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(asyncio, "to_thread", immediate)


class FakeCDP:
    instances = []

    def __init__(self, *args, observation_mode="dom", **kwargs):
        self.observation_mode = observation_mode
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
def run_pair(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNER_BROWSER_PROFILE_PROVENANCE", json.dumps({
        "container_id":"offline-browser", "container_created_at":"fixture", "profile_fresh_at_run_start":True,
        "tasks_previously_run_in_container":0, "browser_build":{"image_id":"offline-image"},
        "browser_environment":{"LANG":"en_US.UTF-8"}}))
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
            return {"id": f"response-{len(payloads[selected])}", "model": "gpt-6.1-terra",
                "output_text": item if isinstance(item, str) else json.dumps(item),
                "usage": {"input_tokens": 20, "output_tokens": 10,
                    "input_tokens_details": {"cached_tokens": 5}, "output_tokens_details": {"reasoning_tokens": 3}}}
        monkeypatch.setattr(runner.ModelClient, "_post", post)
        root = tmp_path / mode
        args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"),
            "--observation-mode", mode, "--task", "Report done.", "--task-id", "task_01",
            "--source-task-id", "task_01", "--start-url", "https://example.test",
            "--output-dir", str(root), "--model", "gpt-6.1-terra", "--api-key", "offline-placeholder",
            "--max-turns", "6", "--settle-seconds", "0"])
        assert asyncio.run(runner.run(args)) == 0
        paths[mode] = root / "task_01"
    return paths, payloads, connect, snapshot


def test_modes_capture_and_send_only_their_channel(run_pair):
    paths, payloads, connect, snapshot = run_pair
    dom, ss = (inspect_recording(paths[mode]) for mode in ("dom", "screenshot"))
    assert list(paths["dom"].rglob("*.png"))
    assert list(paths["screenshot"].rglob("dom*"))
    assert not list(paths["screenshot"].rglob("agent_browser*"))
    assert connect.await_count == 1  # Screenshot mode never connects the DOM action tool.
    assert snapshot.await_count == 2  # One interactive reference snapshot per DOM state.
    for payload in payloads["dom"]:
        content = payload["input"][0]["content"]
        assert [c["type"] for c in content] == ["input_text"]
        assert "DOM_ONLY_SECRET" in content[0]["text"]
    for payload in payloads["screenshot"]:
        content = payload["input"][0]["content"]
        assert [c["type"] for c in content] == ["input_text", "input_image"]
        assert content[1]["image_url"].startswith("data:image/png;base64,")
        assert "DOM_ONLY_SECRET" not in json.dumps(payload)
        assert "[ref=e1]" not in json.dumps(payload)
        assert "current_agent_browser_snapshot:" not in json.dumps(payload)
        assert "current_chromiumrl_evidence:" not in json.dumps(payload)
    for mode in ("dom", "screenshot"):
        for state in inspect_recording(paths[mode])["manifest"]["states"]:
            assert {"screenshot.png", "dom.json", "dom_full.txt", "dom_model.json", "dom_model.txt"} <= state["artifacts"].keys()
    for payload, row in zip(payloads["screenshot"], ss["decisions"]):
        actual = base64.b64decode(payload["input"][0]["content"][1]["image_url"].split(",", 1)[1])
        saved = paths["screenshot"] / ss["manifest"]["states"][row["state"]-1]["observation"]
        assert hashlib.sha256(actual).hexdigest() == hashlib.sha256(saved.read_bytes()).hexdigest()


def test_turn_counts_include_rejections_parse_failure_and_termination(capsys, run_pair):
    paths, *_ = run_pair
    dom, ss = [inspect_recording(paths[m]) for m in ("dom", "screenshot")]
    assert [r["model_turn"] for r in dom["decisions"]] == [1, 2, 3, 4]
    receipt, _ = compare(dom, ss)
    assert receipt["dom"]["model_turns"] == 4
    assert receipt["screenshot"]["model_turns"] == 5
    assert receipt["dom"]["action_attempts"] == 1
    assert receipt["screenshot"]["action_attempts"] == 2
    assert receipt["dom"]["rejected_turns"] == 2
    assert receipt["dom"]["termination_turns"] == 1
    assert receipt["dom"]["token_usage"]["total_tokens"] == 120
    assert receipt["successful_pair_turn_delta"] is None
    assert receipt["dom"]["completion"]["verdict"] == "ungraded"
    output = capsys.readouterr().out
    assert "[turn 4/6] terminate" in output
    assert "actor status: success; model turns: 4/6; action attempts: 1" in output
    assert "Final answer: done" in output


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


def test_reference_grading_reports_success_without_judge_calls(run_pair, tmp_path, monkeypatch):
    paths, *_ = run_pair
    def forbidden(*args, **kwargs):
        raise AssertionError("reference grading must be offline")
    monkeypatch.setattr(runner.ModelClient, "_post", forbidden)
    rubric = tmp_path / "rubric.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.",
        "start_url": "https://example.test", "expected_answer": "done"})
    for path in paths.values():
        grade = asyncio.run(grade_run(path, rubric))
        assert grade["verdict"] == "success" and grade["judge_calls"] == 0
    receipt, _ = compare(*(inspect_recording(paths[m]) for m in ("dom", "screenshot")))
    assert receipt["successful_pair_turn_delta"] == 1
    summary = aggregate([receipt])
    assert summary["both_successful_tasks"] == 1
    assert summary["mean_successful_pair_turn_delta"] == 1
    output = tmp_path / "report"
    ledger = tmp_path / "ledger.jsonl"
    write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    assert compare_main(["--ledger", str(ledger), "--output", str(output)]) == 0
    assert (output / "summary.json").is_file()
    exported = prepare_recording(inspect_recording(paths["screenshot"]), tmp_path / "export")
    receipt = json.loads((Path(exported["output"]) / "input_receipt.json").read_text())
    assert exported["recording_sha256"] == inspect_recording(paths["screenshot"])["recording_sha256"]
    assert receipt["recording_sha256"] == exported["recording_sha256"]
    assert Path(exported["screenshot_task"], "task_data.json").is_file()
    assert Path(exported["dom_task"], "task_data.json").is_file()


@pytest.mark.parametrize("mode,forbidden", [("dom", "extra.txt"), ("screenshot", "agent_browser_actions.txt")])
def test_inspector_rejects_forbidden_artifacts(run_pair, mode, forbidden):
    paths, *_ = run_pair
    (paths[mode] / "steps/step_001" / forbidden).write_text("contamination")
    with pytest.raises(ValueError, match="forbidden"):
        inspect_recording(paths[mode])


def test_screenshot_input_dispatch_has_no_dom_fallback():
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    client = FakeCDP(observation_mode="screenshot")
    for decision in [{"action": "click", "x": 10, "y": 20}, {"action": "type", "text": "example"},
                     {"action": "press", "key": "Control+A"}, {"action": "scroll", "pixels": 500}]:
        assert asyncio.run(driver.execute(decision, cdp=client))["success"]
    assert {method.split(".")[0] for method, _ in client.calls} == {"Input"}
    assert runner.action_rejection_reason({"action": "click", "id": "e1", "thought": "click"}, frozenset({"e1"}), [], observation_mode="screenshot")
    assert runner.action_rejection_reason({"action": "click", "x": -1, "y": 20, "thought": "click"}, frozenset(), [], observation_mode="screenshot")


def test_action_snapshot_filters_viewport_and_preserves_executable_refs(monkeypatch):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    names = ["Visible", "Below", "Right", "Above", "Left", "Partial", "Zero", "Duplicate", "Duplicate"]
    refs = {f"e{i}": {"role": "button", "name": name} for i, name in enumerate(names, 1)}
    text = "- heading Offscreen context\n" + "\n".join(
        f'- button "{target["name"]}" [ref={ref}]' for ref, target in refs.items())
    boxes = [(10, 10, 30, 20), (10, 768, 30, 20), (1365, 10, 30, 20),
        (10, -20, 30, 20), (-30, 10, 30, 20), (10, 760, 30, 20),
        (10, 10, 0, 20), (10, 1500, 30, 20), (100, 100, 30, 20)]
    async def invoke(arguments, **kwargs):
        if arguments[0] == "snapshot":
            return {"data": {"snapshot": text, "refs": refs, "origin": "fixture"}}
        assert arguments[0] == "batch"
        assert arguments[2:] == [f"get box @{ref}" for ref in refs]
        return [{"success": True, "result": {"result": {"width": 1365, "height": 768}}},
            *({"success": True, "result": dict(zip(("x", "y", "width", "height"), box))} for box in boxes)]
    monkeypatch.setattr(driver, "_invoke", invoke)
    observation = asyncio.run(driver.snapshot())
    assert observation.refs == {"e1", "e6", "e9"}
    assert set(observation.targets) == observation.refs
    assert observation.text.splitlines() == [text.splitlines()[i] for i in (1, 6, 9)]
    assert "Offscreen context" not in observation.text
    assert runner.action_rejection_reason({"action": "click", "id": "e8", "thought": "click"}, observation.refs, [])
    assert not runner.action_rejection_reason({"action": "click", "id": "e9", "thought": "click"}, observation.refs, [])


@pytest.mark.parametrize("geometry", [None, {"x": 0, "y": 0, "width": float("nan"), "height": 20}])
def test_action_snapshot_fails_closed_when_geometry_is_unavailable(monkeypatch, geometry):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    invoke = AsyncMock(side_effect=[
        {"data": {"snapshot": '- button "Hidden" [ref=e1]', "refs": {"e1": {"role": "button", "name": "Hidden"}}}},
        [{"success": True, "result": {"result": {"width": 1365, "height": 768}}},
         {"success": geometry is not None, "result": geometry}]])
    monkeypatch.setattr(driver, "_invoke", invoke)
    with pytest.raises(AgentBrowserError, match="viewport geometry"):
        asyncio.run(driver.snapshot())


def test_empty_action_snapshot_never_falls_back_to_full_page(monkeypatch):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    invoke = AsyncMock(return_value={"data": {"snapshot": "- heading Full page secret", "refs": {}}})
    monkeypatch.setattr(driver, "_invoke", invoke)
    observation = asyncio.run(driver.snapshot())
    assert not observation.refs and not observation.targets
    assert "Full page secret" not in observation.text
    bundle = capture.CaptureBundle(snapshot_path=Path("dom.json"))
    assert bundle.executable_agent_browser_text() == ""


def test_arbitrary_trial_count_pass_k_unknowns_and_criterion_identity(run_pair):
    import copy
    paths, *_ = run_pair
    receipt, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    pairs = []
    for index, verdict in enumerate(("success", "failure", "uncertain", "failure", "success"), 1):
        pair = copy.deepcopy(receipt)
        pair['trial_id'] = f'repeat_{index}'
        for mode in ('dom', 'screenshot'):
            pair[mode]['completion'] = {'method':'model_judge','verdict':verdict,'rubric_sha256':'frozen',
                'criteria':[{'id':'c01','verdict':'success' if index==1 else 'failure'}]}
        pair['both_successful'] = verdict=='success'
        pair['successful_pair_turn_delta'] = 1 if verdict=='success' else None
        pairs.append(pair)
    summary = aggregate(pairs)
    assert summary['paired_tasks']==1 and summary['paired_attempts']==5
    assert summary['evaluated_k']==[1,2,3,4,5]
    result=summary['modes']['dom']
    assert result['attempted_runs']==5 and result['tokens']==600
    assert result['pass_at_k']['1']['confirmed_lower']==pytest.approx(2/5)
    assert result['pass_at_k']['1']['possible_upper']==pytest.approx(3/5)
    assert result['pass_at_k']['1']['estimate'] is None
    assert result['pass_at_k']['2']['confirmed_lower']==pytest.approx(0.7)
    assert result['pass_at_k']['2']['possible_upper']==pytest.approx(0.9)
    assert result['pass_at_k']['5']['estimate']==1
    criterion=summary['per_task']['task_01']['dom']['criteria']['c01']
    assert criterion['pass_at_k']['2']['estimate']==pytest.approx(2/5)
    assert summary['both_successful_pairs']==2 and summary['both_successful_tasks']==1
    assert result['all_trials_success_rate_confirmed']==0
    with pytest.raises(ValueError,match='at least k'):
        aggregate(pairs,pass_k=[6])
    broken=copy.deepcopy(pairs);broken[1]['dom']['completion']['rubric_sha256']='changed'
    with pytest.raises(ValueError,match='frozen rubric'):
        aggregate(broken)
    with pytest.raises(ValueError,match='duplicate trial'):
        aggregate(pairs+[pairs[0]])
    extra=copy.deepcopy(pairs[1]);extra['task_id']='another_task'
    uneven=aggregate(pairs+[extra])
    assert uneven['evaluated_k']==[1] and not uneven['balanced_trial_counts']
    assert uneven['modes']['dom']['pass_at_k']['1']['confirmed_lower']==pytest.approx(0.2)
    assert uneven['modes']['dom']['pass_at_k']['1']['possible_upper']==pytest.approx(0.3)


def test_ledger_comparison_uses_every_scheduled_trial_and_rejects_omissions(run_pair, tmp_path):
    import shutil
    paths, *_ = run_pair
    rubric = tmp_path / "frozen.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.",
        "start_url": "https://example.test", "expected_answer": "done"})
    recordings = {}
    for trial in range(1, 3):
        run_name = f"trial_{trial:04d}"
        for mode in ("dom", "screenshot"):
            run = tmp_path / "repeated" / run_name / mode / "task_01"
            shutil.copytree(paths[mode], run)
            for filename in ("task.json", "manifest.json"):
                value = json.loads((run / filename).read_text())
                value["run_name"] = run_name
                write_json(run / filename, value)
            asyncio.run(grade_run(run, rubric))
            recordings[trial, mode] = run
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, recordings, 2)
    output = tmp_path / "multi-report"
    assert compare_main(["--ledger", str(ledger), "--output", str(output)]) == 0
    summary = json.loads((output / "summary.json").read_text())
    assert summary["paired_tasks"] == 1 and summary["paired_attempts"] == 2
    assert summary["scheduled_attempts"] == 4
    assert summary["trial_ids"] == ["1", "2"]
    assert summary["modes"]["dom"]["pass_at_k"]["2"]["estimate"] == 1
    assert summary["unmatched_arms"] == []
    assert (output / "per_task.json").is_file()
    write_json_lines(ledger, rows[:-1])
    with pytest.raises(ValueError, match="omits a scheduled"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "missing-row")])
    write_json_lines(ledger, rows + rows[:1])
    with pytest.raises(ValueError, match="duplicate ledger"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "duplicate-row")])


def test_ledger_keeps_missing_recording_and_ungraded_in_denominator(run_pair, tmp_path, capsys):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    write_attempt_ledger(ledger, {(1, "dom"): paths["dom"]}, 1)
    output = tmp_path / "unmatched-report"
    capsys.readouterr()
    assert compare_main(["--ledger", str(ledger), "--output", str(output)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["paired_attempts"] == 0 and printed["paired_tasks"] == 0
    summary = json.loads((output / "summary.json").read_text())
    assert summary["scheduled_attempts"] == 2
    assert summary["paired_attempts"] == 0
    assert summary["scheduled_pairs"] == 1
    assert summary["unmatched_arms"] == [{"task_id": "task_01", "trial": 1,
        "arm": "screenshot", "technical_outcome": "startup_failure"}]
    for mode in ("dom", "screenshot"):
        result = summary["modes"][mode]
        assert result["attempted_runs"] == 1
        assert result["completion_counts"] == {"ungraded": 1}
        assert result["success_rate_definitively_graded"] is None
        assert result["pass_at_k"]["1"]["confirmed_lower"] == 0
        assert result["pass_at_k"]["1"]["possible_upper"] == 1
    assert summary["modes"]["dom"]["actor_turns"] == 4
    assert summary["modes"]["screenshot"]["actor_turns"] == 0


def test_action_snapshot_clips_frame_local_targets_to_frame_and_viewport(monkeypatch):
    driver = AgentBrowserClient("unused", session="fixture", cdp_url="http://localhost:9222", timeout=1)
    refs = {"e1": {"role": "Iframe"}, "e2": {"role": "button", "name": "Hidden frame child"},
        "e3": {"role": "Iframe"}, "e4": {"role": "button", "name": "Visible frame child"},
        "e5": {"role": "button", "name": "Outside frame"}}
    text = '- Iframe [ref=e1]\n  - button "Hidden frame child" [ref=e2]\n- Iframe [ref=e3]\n  - button "Visible frame child" [ref=e4]\n  - button "Outside frame" [ref=e5]'
    boxes = [(10, 1200, 200, 100), (8, 8, 30, 20), (400, 50, 200, 100),
        (8, 8, 30, 20), (8, 200, 30, 20)]
    invoke = AsyncMock(side_effect=[{"data": {"snapshot": text, "refs": refs}},
        [{"success": True, "result": {"result": {"width": 1365, "height": 768}}},
         *({"success": True, "result": dict(zip(("x", "y", "width", "height"), box))} for box in boxes)]])
    monkeypatch.setattr(driver, "_invoke", invoke)
    observation = asyncio.run(driver.snapshot())
    assert observation.refs == {"e3", "e4"}
    assert "Hidden frame child" not in observation.text and "Outside frame" not in observation.text


def test_shared_controls_must_match_and_cli_passes_mode(run_pair, tmp_path):
    paths, *_ = run_pair
    dom, ss = [inspect_recording(paths[m]) for m in ("dom", "screenshot")]
    ss["manifest"]["controls"]["max_turns"] += 1
    with pytest.raises(ValueError, match="shared controls"):
        compare(dom, ss)
    command = task_cli.build_runner_command({"instruction": "Report done.", "start_url": "https://example.test"},
        task_id="task_01", task_name="fixture", run_id="task_01", output_dir=tmp_path,
        env_file=tmp_path / "absent.env",
        observation_mode="screenshot", max_steps=4)
    args = runner.parse_args(command[3:])
    assert args.observation_mode == "screenshot" and args.max_steps == 4


@pytest.mark.parametrize("failure", ["after_capture", "model_transport"])
def test_failed_runs_retain_attempt_counts(run_pair, tmp_path, monkeypatch, failure):
    # Reuse the isolated browser/model fixture, then inject one technical fault.
    def post(self, payload):
        if failure == "model_transport":
            raise RunnerError("offline injected transport error")
        return {"output_text": json.dumps({"action": "click", "x": 10, "y": 20, "thought": "click"}),
                "model": "gpt-6.1-terra", "usage": {"input_tokens": 2, "output_tokens": 1}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    original = FakeCDP.call
    async def call(self, method, params=None, **kwargs):
        if failure == "after_capture" and method == "Page.captureScreenshot" and any(
                m == "Page.captureScreenshot" for m, _ in self.calls):
            raise RunnerError("offline injected capture error")
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeCDP, "call", call)
    root = tmp_path / "failure"
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", "screenshot",
        "--task", "Report done.", "--task-id", "failed", "--output-dir", str(root),
        "--model", "gpt-6.1-terra", "--api-key", "offline-placeholder", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root / "failed")
    assert recording["final"]["run_status"] == "error"
    assert recording["manifest"]["model_turns"] == 1
    assert len(recording["manifest"]["steps"]) == (1 if failure == "after_capture" else 0)
    assert recording["manifest"]["trajectory_export"]["status"] == ("incomplete" if failure == "after_capture" else "complete")


def test_optional_judge_uses_only_its_runs_channel(run_pair, tmp_path, monkeypatch):
    paths, *_ = run_pair
    rubric = tmp_path / "criteria.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.", "start_url": "https://example.test",
        "criteria": [{"id": "C1", "description": "The requested result is established."}]})
    payloads = []
    def post(self, payload):
        payloads.append(payload)
        return {"model": "gpt-5.6-sol", "output_text": json.dumps({"criteria": [
            {"id": "C1", "verdict": "uncertain", "reason": "insufficient support", "states": [1]}]})}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    for mode, path in paths.items():
        grade = asyncio.run(grade_run(path, rubric, judge_model="gpt-5.6-sol", api_key="offline-placeholder", execute=True, evidence_policy="actor_native"))
        assert grade["verdict"] == "uncertain" and grade["judge_calls"] == 1
        content = payloads[-1]["input"][0]["content"]
        assert any(c["type"] == "input_image" for c in content) == (mode == "screenshot")
        assert ("DOM_ONLY_SECRET" in json.dumps(content)) == (mode == "dom")
    receipt, _ = compare(*(inspect_recording(paths[m]) for m in ("dom", "screenshot")))
    assert receipt["successful_pair_turn_delta"] is None
    assert receipt["dom"]["model_turns"] == 4  # Judge calls are not actor turns.


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


@pytest.mark.parametrize("changed_field", [None, "container_id", "source_directory", "target_directory", "compose_project", "service"])
def test_checkout_relocation_receipt_is_bound_to_exact_browser(tmp_path, monkeypatch, changed_field):
    from types import SimpleNamespace
    root = tmp_path / "renamed-checkout"
    runtime = root / ".runtime"
    runtime.mkdir(parents=True)
    source = str(tmp_path / "previous-checkout")
    receipt = {"container_id": "owned-id", "source_directory": source,
        "target_directory": str(root), "compose_project": "owned-project", "service": "w8-core"}
    if changed_field is not None:
        receipt[changed_field] = "mismatch"
    path = runtime / "browser-relocation.json"
    write_json(path, receipt)
    monkeypatch.setattr(task_cli, "ROOT", root)
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", runtime)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if "config" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"name": "owned-project",
                "services": {"w8-core": {"container_name": "owned-browser"}}}), stderr="")
        if command[1:3] == ["ps", "-aq"]:
            return SimpleNamespace(returncode=0, stdout="owned-id\n", stderr="")
        if command[1] == "inspect":
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"Id": "owned-id", "Config": {"Labels": {
                "com.docker.compose.project.working_dir": source,
                "com.docker.compose.project": "owned-project", "com.docker.compose.service": "w8-core"}}}]), stderr="")
        assert "up" in command and changed_field is None
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(task_cli.subprocess, "run", run)
    if changed_field is None:
        task_cli.restart_browser_service(root / ".env")
        assert not path.exists()
        assert sum("up" in command for command in calls) == 1
    else:
        with pytest.raises(RunnerError, match="another checkout"):
            task_cli.restart_browser_service(root / ".env")
        assert path.exists()
        assert not any("up" in command for command in calls)


@pytest.mark.parametrize('shape', ['final_with_commentary', 'multiple_finals', 'commentary_only', 'incomplete'])
def test_actor_reads_one_final_json_message(run_pair, tmp_path, monkeypatch, shape):
    paths, *_ = run_pair
    source = paths['dom'] / 'steps/step_001'
    bundle = capture.CaptureBundle(snapshot_path=source / 'dom.json',
        model_text=(source / 'dom_model.txt').read_text(),
        agent_browser_action_text=(source / 'agent_browser_actions.txt').read_text())
    click = {'action': 'click', 'id': 'e1', 'thought': 'activate the current control'}
    fake_termination = {'action': 'terminate', 'status': 'failure', 'termination_reason': 'budget_exhausted',
        'final_answer': 'budget exhausted', 'thought': 'stop prematurely'}
    commentary = {'type': 'message', 'phase': 'commentary', 'content': [
        {'type': 'output_text', 'text': json.dumps(fake_termination)}]}
    final = {'type': 'message', 'phase': 'final_answer', 'content': [
        {'type': 'output_text', 'text': json.dumps(click)}]}
    sent = []
    def post(self, payload):
        sent.append(payload)
        earlier_final = {**commentary, 'phase': 'final_answer'}
        output = [commentary] if shape == 'commentary_only' else [earlier_final, final] if shape == 'multiple_finals' else [commentary, final]
        return {'model': 'gpt-6.1-terra', 'status': 'incomplete' if shape == 'incomplete' else 'completed', 'output': output,
            'output_text': json.dumps(fake_termination) + '\n' + json.dumps(click)}
    monkeypatch.setattr(runner.ModelClient, '_post', post)
    client = runner.ModelClient('offline-placeholder', 'gpt-6.1-terra', 'https://offline.test')
    pending = client.decide(task='Activate the control.', step=8, max_steps=80, bundle=bundle,
        task_memory='', recent_actions=[], turn_dir=tmp_path / 'protocol-turn', viewport=(1365,768))
    if shape in {'final_with_commentary', 'multiple_finals'}:
        decision, _ = asyncio.run(pending)
        assert decision == click
    else:
        with pytest.raises(runner.ModelProtocolError):
            asyncio.run(pending)
    request = sent[0]
    assert not {'tools', 'tool_choice', 'parallel_tool_calls'} & request.keys()
    assert request['text']['format']['type'] == 'json_schema'
    assert request['text']['format']['strict'] is True
    assert request['text']['format']['schema'] == runner.ACTION_SCHEMA
    assert 'step: 8 of 80' in request['input'][0]['content'][0]['text']
    assert 'turns_remaining_after_this_call: 72' in request['input'][0]['content'][0]['text']


@pytest.mark.parametrize('mode', ['dom', 'screenshot'])
def test_false_budget_exhaustion_is_rejected_but_real_blockers_are_allowed(mode):
    decision = {'action': 'terminate', 'status': 'failure', 'termination_reason': 'budget_exhausted',
        'final_answer': 'Unable to complete within the available browser turns.',
        'thought': 'The turn budget shown at the start has been exhausted.'}
    reason = runner.action_rejection_reason(decision, frozenset(), [], observation_mode=mode,
        model_turn=8, max_turns=80)
    assert '72 calls remain' in reason
    assert runner.action_rejection_reason(decision, frozenset(), [], observation_mode=mode,
        model_turn=80, max_turns=80) == ''
    blocked = {**decision, 'termination_reason': 'blocked', 'final_answer': 'The page requires sign-in.'}
    assert runner.action_rejection_reason(blocked, frozenset(), [], observation_mode=mode,
        model_turn=8, max_turns=80) == ''
    legacy = {k:v for k,v in decision.items() if k != 'termination_reason'}
    assert 'termination_reason' in runner.action_rejection_reason(legacy, frozenset(), [],
        observation_mode=mode, model_turn=8, max_turns=80)


def test_rejected_termination_and_failed_action_do_not_commit_memory(run_pair, tmp_path, monkeypatch):
    queue = [
        {'action': 'wait', 'seconds': 0, 'thought': 'Observe the page.', 'memory': 'established fact'},
        {'action': 'terminate', 'status': 'failure', 'termination_reason': 'budget_exhausted',
         'final_answer': 'No turns remain.', 'thought': 'Out of turns.', 'memory': 'invented budget fact'},
        {'action': 'wait', 'seconds': 0, 'thought': 'Observe again.', 'memory': 'unconfirmed action fact'},
        {'action': 'terminate', 'status': 'failure', 'termination_reason': 'blocked',
         'final_answer': 'A visible access blocker prevents continuation.', 'thought': 'Record the blocker.'},
    ]
    inputs = []
    def post(self, payload):
        inputs.append(payload)
        return {'model': 'gpt-6.1-terra', 'output_text': json.dumps(queue.pop(0)), 'usage': {'input_tokens': 1, 'output_tokens': 1}}
    attempts = []
    async def execute(self, decision, **kwargs):
        attempts.append(decision)
        if len(attempts) == 2:
            raise RunnerError('injected failed action')
        return {'success': True}
    monkeypatch.setattr(runner.ModelClient, '_post', post)
    monkeypatch.setattr(AgentBrowserClient, 'execute', execute)
    root = tmp_path / 'budget-check'
    args = runner.parse_args(['--env-file', str(tmp_path/'absent.env'), '--observation-mode', 'screenshot',
        '--task', 'Inspect the page.', '--task-id', 'sample', '--output-dir', str(root),
        '--model', 'gpt-6.1-terra', '--api-key', 'offline-placeholder', '--max-turns', '80', '--settle-seconds', '0'])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root/'sample')
    assert recording['manifest']['model_turns'] == 4
    assert len(recording['manifest']['steps']) == 2
    assert recording['final']['termination_reason'] == 'blocked'
    assert recording['decisions'][1]['accepted'] is False
    assert '78 calls remain' in recording['decisions'][1]['rejection_reason']
    assert recording['decisions'][2]['task_memory_before'] == 'established fact'
    assert recording['decisions'][3]['task_memory_before'] == 'established fact'
    assert 'unconfirmed action fact' not in inputs[3]['input'][0]['content'][0]['text']


def test_baseline_stall_and_success_checks():
    recent = [{'action': {'action': 'click', 'id': 'e1'}, 'action_succeeded': True,
        'progress': {'made_progress': False}}]
    assert 'duplicate activation' in runner.action_rejection_reason(
        {'action': 'click', 'id': 'e1', 'thought': 'click again'}, frozenset({'e1'}), recent)
    assert 'confirmed browser action' in runner.action_rejection_reason(
        {'action': 'terminate', 'status': 'success', 'termination_reason': 'completed',
         'final_answer': 'done', 'thought': 'finished'}, frozenset(), [])
    with pytest.raises(RunnerError, match='exactly one JSON'):
        runner.parse_decision('{"action":"wait"}{"action":"terminate"}')


def test_passive_capture_failure_never_enters_actor_or_progress(run_pair, tmp_path, monkeypatch):
    original = FakeCDP.call
    async def call(self, method, params=None, **kwargs):
        if method == "ChromiumRL.captureStructuredSnapshot":
            raise RunnerError("PASSIVE_DOM_ERROR_SECRET")
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeCDP, "call", call)
    client = FakeCDP(observation_mode="screenshot")
    before = asyncio.run(capture.capture_bundle(client, tmp_path/"one", max_nodes=100, max_text_chars=1000,
        observation_mode="screenshot"))
    after = asyncio.run(capture.capture_bundle(client, tmp_path/"two", max_nodes=100, max_text_chars=1000,
        observation_mode="screenshot"))
    assert before.capture_metadata["paired_complete"] is False
    assert "PASSIVE_DOM_ERROR_SECRET" in json.dumps(before.capture_metadata)
    assert set(capture.action_progress(before, after)) == {"made_progress", "screenshot_changed"}
    seen = []
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self,payload: seen.append(payload) or
        {"model": "gpt-6.1-terra", "output_text": '{"action":"wait","seconds":0,"thought":"observe"}'})
    asyncio.run(runner.ModelClient("unused", "gpt-6.1-terra", "unused").decide(task="Inspect page", step=1,
        max_steps=5, bundle=before, task_memory="", recent_actions=[], turn_dir=tmp_path,
        viewport=(1365,768)))
    assert "PASSIVE_DOM_ERROR_SECRET" not in json.dumps(seen)
    assert "DOM_ONLY_SECRET" not in json.dumps(seen)


@pytest.mark.skipif(not os.environ.get("W8_CAPTURE_TEST_CDP"), reason="requires the isolated browser")
def test_live_capture_preserves_scroll_and_focus(tmp_path):
    runner.load_env(Path(".env"))
    args = runner.parse_args(["--observation-mode", "dom", "--capture-only"])
    async def check():
        async with capture.CDPClient(os.environ["W8_CAPTURE_TEST_CDP"], viewport=(1365,768)) as cdp:
            await cdp.call("Runtime.evaluate", {"expression":
                "document.body.innerHTML='<input id=focusme style=position:fixed><div style=height:5000px>capture fixture</div>';"
                "document.getElementById('focusme').focus();window.scrollTo(0,400)"})
            before = await cdp.call("Runtime.evaluate", {"expression":
                "JSON.stringify([scrollX,scrollY,document.activeElement.id])", "returnByValue": True})
            for mode in ("dom", "screenshot"):
                bundle = await capture.capture_bundle(cdp, tmp_path/mode/"steps"/"step_001", max_nodes=7000,
                    max_text_chars=200000, observation_mode=mode)
                if mode == "dom":
                    driver = AgentBrowserClient(args.agent_browser_command, session="paired-capture-test",
                        cdp_url=args.agent_browser_cdp_url, timeout=args.agent_browser_timeout)
                    await driver.connect()
                    try:
                        bundle = await capture.attach_agent_browser_observation(bundle, driver, cdp)
                    finally:
                        await driver.close()
                assert bundle.capture_metadata["paired_complete"]
                after = await cdp.call("Runtime.evaluate", {"expression":
                    "JSON.stringify([scrollX,scrollY,document.activeElement.id])", "returnByValue": True})
                assert before["result"]["value"] == after["result"]["value"]
                if os.environ.get("W8_CAPTURE_REPORT_DIR"):
                    report_dir = Path(os.environ["W8_CAPTURE_REPORT_DIR"])
                    report_dir.mkdir(parents=True, exist_ok=True)
                    write_json(report_dir / f"browser_{mode}_state.json", {
                        "source": "live browser fixture; zero actor or judge model calls",
                        "manifest_state": runner.state_manifest_record(1,bundle,tmp_path/mode),
                        "scroll_focus_before":json.loads(before["result"]["value"]),
                        "scroll_focus_after":json.loads(after["result"]["value"])})
            if os.environ.get("W8_CAPTURE_REPORT_DIR"):
                # Reuse the protected baseline's existing capture functions only in this test.
                # This measures capture-core overhead; refs, actors, network pages and grading are excluded.
                baseline = subprocess.check_output(["git","show",
                    "69df83ee:w8bench/task_recorder/capture.py"],text=True)
                tree = ast.parse(baseline)
                selected = ast.Module(body=[node for node in tree.body if isinstance(node,ast.AsyncFunctionDef)
                    and node.name in {"materialize_bundle","capture_bundle"}],type_ignores=[])
                namespace = dict(vars(capture))
                exec(compile(selected,"protected-baseline-capture","exec"),namespace)
                measurements = []
                for mode in ("dom","screenshot"):
                    for sample in range(5):
                        variants = ["before","paired"] if sample%2==0 else ["paired","before"]
                        for variant in variants:
                            started = time.perf_counter()
                            bundle = await (namespace["capture_bundle"] if variant=="before" else capture.capture_bundle)(
                                cdp,tmp_path/"timings"/f"{mode}_{sample}_{variant}",max_nodes=7000,
                                max_text_chars=200000,observation_mode=mode)
                            measurements.append({"arm":mode,"sample":sample,"variant":variant,
                                "duration_seconds":time.perf_counter()-started,
                                "capture":bundle.capture_metadata if variant=="paired" else None})
                summary = {}
                for mode in ("dom","screenshot"):
                    means = {variant:statistics.mean(row["duration_seconds"] for row in measurements
                        if row["arm"]==mode and row["variant"]==variant) for variant in ("before","paired")}
                    summary[mode] = {**means,"added_seconds":means["paired"]-means["before"]}
                write_json(Path(os.environ["W8_CAPTURE_REPORT_DIR"])/"capture_timings.json",{
                    "source":"live static fixture; no model calls", "baseline_commit":"69df83ee",
                    "scope":"capture core only; excludes executable refs, actor API, settle, navigation and grading",
                    "samples_per_arm_variant":5,"summary":summary,"per_state":measurements})

    asyncio.run(check())


def test_actor_settings_and_output_limit_metadata(run_pair):
    paths, payloads, *_ = run_pair
    for mode in ("dom", "screenshot"):
        recording = inspect_recording(paths[mode])
        assert recording["manifest"]["reasoning_effort"] == "medium"
        assert recording["manifest"]["returned_actor_models"] == ["gpt-6.1-terra"]
        assert recording["manifest"]["configured_actor_model"] == "gpt-6.1-terra"
        for payload, row in zip(payloads[mode], recording["decisions"]):
            assert payload["max_output_tokens"] == 10000
            assert payload["reasoning"] == {"effort": "medium"}
            assert payload["text"]["format"]["schema"]["properties"]["memory"]["maxLength"] == 8000
            assert row["output_limit_hit"] is False
            assert row["configured_model"] == "gpt-6.1-terra"
            assert row["max_output_tokens"] == 10000
            assert row["requested_reasoning_effort"] == "medium"


def test_current_url_is_shared_but_language_is_dom_only(run_pair):
    _, payloads, *_ = run_pair
    for mode in ("dom", "screenshot"):
        text = payloads[mode][0]["input"][0]["content"][0]["text"]
        assert "current_document_url: https://example.test" in text
        assert ("current_document_language:" in text) == (mode == "dom")


def test_common_judge_evidence_and_secondary_policy(run_pair, tmp_path, monkeypatch):
    paths, *_ = run_pair
    rubric = tmp_path / "criteria.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.",
        "start_url": "https://example.test", "criteria": [{"id": "result", "description": "Report done."}]})
    seen = []
    def post(self, payload):
        seen.append(payload)
        return {"model": "gpt-5.6-sol", "output_text": json.dumps({"criteria": [
            {"id": "result", "verdict": "success", "reason": "Observed", "states": [1]}]}),
            "usage": {"input_tokens": 100, "output_tokens": 10}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    for mode in ("dom", "screenshot"):
        grade = asyncio.run(grade_run(paths[mode], rubric, judge_model="gpt-5.6-sol", api_key="test", execute=True))
        content = seen[-1]["input"][0]["content"]
        assert grade["evidence_policy"] == "paired"
        assert any(item["type"] == "input_image" for item in content)
        assert "DOM_ONLY_SECRET" in json.dumps(content)
        assert "[ref=e1]" not in json.dumps(content)
    primary = (paths["dom"] / "completion.json").read_bytes()
    grade = asyncio.run(grade_run(paths["dom"], rubric, judge_model="gpt-5.6-sol", api_key="test", execute=True,
        evidence_policy="actor_native"))
    assert grade["evidence_policy"] == "actor_native"
    assert (paths["dom"] / "completion_actor_native.json").exists()
    assert (paths["dom"] / "completion.json").read_bytes() == primary
    # Mixing policies is rejected even if every other grading control matches.
    write_json(paths["dom"] / "completion.json", grade)
    with pytest.raises(ValueError, match="evidence_policy"):
        compare(*(inspect_recording(paths[m]) for m in ("dom", "screenshot")))


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
        "--judge-model", "gpt-5.6-sol", "--output-dir", str(output),
        "--run-name", "batch", "--env-file", str(tmp_path / "absent.env"), "--model", "gpt-6.1-terra"]
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


@pytest.mark.parametrize("trials", [0, -1])
def test_batch_rejects_nonpositive_trial_count(tmp_path, trials):
    with pytest.raises(RunnerError, match="positive --trials"):
        task_cli.main(["--trials", str(trials), "--catalog-file", str(tmp_path / "missing.jsonl"),
            "--output-dir", str(tmp_path / "recordings"), "--env-file", str(tmp_path / "absent.env")])


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
        "--judge-model", "gpt-5.6-sol", "--output-dir", str(output),
        "--run-name", "resumed", "--env-file", str(tmp_path / "absent.env"), "--model", "gpt-6.1-terra"]
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


@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_inspector_rejects_passive_observation_text_in_actor_request(run_pair, mode):
    paths, *_ = run_pair
    request = paths[mode] / "turns/turn_000001/request.json"
    payload = json.loads(request.read_text())
    payload["input"][0]["content"][0]["text"] += "\nPASSIVE_OBSERVATION_SECRET"
    write_json(request, payload)
    with pytest.raises(ValueError, match="unapproved|prompt|actor text"):
        inspect_recording(paths[mode])


def test_passive_screenshot_failure_does_not_change_dom_actor_or_progress(run_pair, tmp_path, monkeypatch):
    original = FakeCDP.call
    async def call(self, method, params=None, **kwargs):
        if method == "Page.captureScreenshot":
            raise RunnerError("PASSIVE_SCREENSHOT_ERROR_SECRET")
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeCDP, "call", call)
    client = FakeCDP(observation_mode="dom")
    before = asyncio.run(capture.capture_bundle(client, tmp_path / "before", max_nodes=100,
        max_text_chars=1000, observation_mode="dom"))
    after = asyncio.run(capture.capture_bundle(client, tmp_path / "after", max_nodes=100,
        max_text_chars=1000, observation_mode="dom"))
    assert before.capture_metadata["paired_complete"] is False
    assert before.snapshot_path.is_file() and (before.directory / "dom_model.txt").is_file()
    assert before.screenshot_path is None
    assert "PASSIVE_SCREENSHOT_ERROR_SECRET" in json.dumps(before.capture_metadata)
    assert capture.action_progress(before, after)["made_progress"] is False
    seen = []
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self, payload: seen.append(payload) or
        {"model": "gpt-6.1-terra", "output_text": '{"action":"wait","seconds":0,"thought":"observe"}'})
    asyncio.run(runner.ModelClient("unused", "gpt-6.1-terra", "unused").decide(task="Inspect page", step=1,
        max_steps=5, bundle=before, task_memory="", recent_actions=[], turn_dir=tmp_path,
        viewport=(1365, 768)))
    assert "PASSIVE_SCREENSHOT_ERROR_SECRET" not in json.dumps(seen)
    assert "DOM_ONLY_SECRET" in json.dumps(seen)
    assert all(item["type"] == "input_text" for item in seen[0]["input"][0]["content"])


@pytest.mark.parametrize("navigation_kind", ["same_url", "different_url"])
def test_capture_records_navigation_inside_interval(tmp_path, monkeypatch, navigation_kind):
    original = FakeCDP.call
    frame_calls = []
    async def call(self, method, params=None, **kwargs):
        if method == "Page.getFrameTree":
            frame_calls.append(method)
            url = ("https://example.test/changed" if navigation_kind == "different_url" and len(frame_calls) > 1
                else "https://example.test")
            return {"frameTree": {"frame": {"id": "main", "url": url, "loaderId": "loader"}}}
        result = await original(self, method, params, **kwargs)
        if method == "ChromiumRL.captureStructuredSnapshot":
            self.navigation_events.append({"method": "Page.frameNavigated", "params": {"frame": {
                "id": "main", "url": "https://example.test", "loaderId": "loader"}},
                "session_id": "fixture", "recorded_at": "9999-01-01T00:00:00Z"})
        return result
    monkeypatch.setattr(FakeCDP, "call", call)
    bundle = asyncio.run(capture.capture_bundle(FakeCDP(), tmp_path / "state", max_nodes=100,
        max_text_chars=1000, observation_mode="dom"))
    metadata = bundle.capture_metadata
    assert metadata["navigation_during_capture"] is True
    assert metadata["url_before"] == "https://example.test"
    assert metadata["url_after"] == ("https://example.test/changed" if navigation_kind == "different_url"
        else "https://example.test")
    assert len(metadata["navigation_events"]) == 1
    assert metadata["capture_order"] == ["structured_dom", "dom_model_artifacts", "screenshot"]
    assert all(item["started_at"] <= item["ended_at"] and item["duration_seconds"] >= 0
        for item in metadata["captures"])


@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_incomplete_actor_records_limit_hit_and_reasoning_usage(run_pair, tmp_path, monkeypatch, mode):
    calls = []
    def post(self, payload):
        calls.append(payload)
        return {"id": "limited-response", "model": "gpt-6.1-terra", "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "reasoning": {"effort": "medium"}, "output": [],
            "usage": {"input_tokens": 23, "output_tokens": 10000,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 9000}}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    root = tmp_path / f"limit_{mode}"
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
        "--task", "Inspect the page.", "--task-id", "limited", "--start-url", "https://example.test",
        "--output-dir", str(root), "--model", "gpt-6.1-terra", "--api-key", "offline-placeholder",
        "--max-turns", "2", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root / "limited")
    assert len(calls) == 1
    assert recording["manifest"]["model_turns"] == 1
    assert recording["manifest"]["steps"] == []
    assert recording["manifest"]["returned_actor_models"] == ["gpt-6.1-terra"]
    row = recording["decisions"][0]
    assert row["response_status"] == "incomplete"
    assert row["incomplete_details"] == {"reason": "max_output_tokens"}
    assert row["output_limit_hit"] is True
    assert row["accepted"] is False
    assert row["usage"]["output_tokens_details"]["reasoning_tokens"] == 9000
    assert row["usage"]["output_tokens"] == 10000


@pytest.mark.parametrize("failure", ["parse", "incomplete"])
def test_judge_failure_is_ungraded_and_keeps_its_usage_separate(run_pair, tmp_path, monkeypatch, failure):
    paths, *_ = run_pair
    rubric = tmp_path / "criteria.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.", "start_url": "https://example.test",
        "criteria": [{"id": "result", "description": "The result is established."}]})
    def post(self, payload):
        return {"id": "failed-judge-response", "model": "gpt-5.6-sol", "status": "incomplete" if failure == "incomplete" else "completed",
            "incomplete_details": {"reason": "max_output_tokens"} if failure == "incomplete" else None,
            "output_text": "malformed judge JSON", "usage": {"input_tokens": 101, "output_tokens": 17,
                "output_tokens_details": {"reasoning_tokens": 11}}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    grade = asyncio.run(grade_run(paths["dom"], rubric, judge_model="gpt-5.6-sol", api_key="test", execute=True))
    assert grade["method"] == "ungraded" and grade["verdict"] == "ungraded"
    assert grade["judge_calls"] == 1 and grade["judge_error"]
    assert grade["usage"]["input_tokens"] == 101 and grade["usage"]["output_tokens"] == 17
    assert grade["returned_judge_model"] == "gpt-5.6-sol"
    assert grade["evidence_policy"] == "paired"
    assert json.loads((paths["dom"] / "completion.json").read_text()) == grade
    receipt, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    summary = aggregate([receipt])
    assert summary["modes"]["dom"]["actor_turns"] == 4
    assert summary["modes"]["dom"]["tokens"] == 120
    assert summary["modes"]["dom"]["judge_calls"] == 1
    assert summary["modes"]["dom"]["judge_usage"]["input_tokens"] == 101
    assert summary["modes"]["dom"]["judge_usage"]["output_tokens"] == 17
    assert summary["modes"]["dom"]["completion_counts"] == {"ungraded": 1}


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
        "--rubric-dir", str(rubrics), "--judge-model", "gpt-5.6-sol", "--output-dir", str(output),
        "--run-name", "judging", "--env-file", str(tmp_path / "absent.env"), "--model", "gpt-6.1-terra"]) == 0
    rows = [json.loads(line) for line in (output / "judging" / "ledger.jsonl").read_text().splitlines()]
    assert actors == ["dom", "screenshot"]
    assert len(judges) == 2
    assert events == ["actor", "actor", "judge", "judge"]
    assert all(row["completed"] and row["technical_outcome"] == "completed" for row in rows)
    assert all(row["grade_outcome"] == "grading_error" for row in rows)



def test_passive_dom_renderer_failure_removes_partial_artifacts(tmp_path, monkeypatch):
    def render(path):
        path.with_name("dom_full.txt").write_text("partial passive evidence")
        path.with_name(".dom_full.txt.tmp").write_text("temporary passive evidence")
        raise RunnerError("PASSIVE_RENDERER_ERROR")
    monkeypatch.setattr(capture, "render_full_stored_snapshot", render)
    bundle = asyncio.run(capture.capture_bundle(FakeCDP(observation_mode="screenshot"), tmp_path / "state",
        max_nodes=100, max_text_chars=1000, observation_mode="screenshot"))
    assert bundle.screenshot_path.is_file()
    assert bundle.snapshot_path is None
    assert not list(bundle.directory.glob("dom*"))
    assert not list(bundle.directory.glob(".dom*"))
    assert not bundle.capture_metadata["paired_complete"]
    assert "PASSIVE_RENDERER_ERROR" in json.dumps(bundle.capture_metadata)


def test_capture_retry_preserves_passive_failure_metadata(tmp_path, monkeypatch):
    original = FakeCDP.call
    counters = {"dom": 0, "screenshot": 0}
    async def call(self, method, params=None, **kwargs):
        if method == "ChromiumRL.captureStructuredSnapshot":
            counters["dom"] += 1
            if counters["dom"] == 1:
                raise RunnerError("PASSIVE_FIRST_CAPTURE_SECRET")
        if method == "Page.captureScreenshot":
            counters["screenshot"] += 1
            if counters["screenshot"] == 1:
                raise RunnerError("CDP websocket closed")
        return await original(self, method, params, **kwargs)
    monkeypatch.setattr(FakeCDP, "call", call)
    synchronize = AsyncMock(return_value={"switched": False})
    monkeypatch.setattr(capture, "synchronize_recorder_target", synchronize)
    run = tmp_path / "run"
    bundle, reconnects = asyncio.run(capture.capture_after_action_bundle(
        FakeCDP(observation_mode="screenshot"), None, run / "steps" / "step_001", max_nodes=100,
        max_text_chars=1000, observation_mode="screenshot", attempts=2))
    assert bundle.capture_metadata["paired_complete"]
    assert len(reconnects) == 1 and synchronize.await_count == 1
    failures = [json.loads(line) for line in (run / "capture_failures.jsonl").read_text().splitlines()]
    assert len(failures) == 1
    assert failures[0]["attempt"] == 1
    assert failures[0]["directory"] == "steps/step_001"
    assert "PASSIVE_FIRST_CAPTURE_SECRET" in json.dumps(failures[0]["capture"])
    assert "CDP websocket closed" in failures[0]["error"]


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
            "--judge-model", "gpt-5.6-sol", "--output-dir", str(output), "--run-name", "interrupted_judge",
            "--env-file", str(tmp_path / "absent.env"), "--model", "gpt-6.1-terra"])
    assert events == ["actor", "actor", "judge"]
    rows = [json.loads(line) for line in (output / "interrupted_judge" / "ledger.jsonl").read_text().splitlines()]
    assert all(row["technical_outcome"] == "completed" for row in rows)
    assert rows[0]["grade_outcome"] == "interrupted"
    assert rows[0]["completed"] is True


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
        "--judge-model", "gpt-5.6-sol", "--output-dir", str(output),
        "--run-name", "live", "--env-file", str(tmp_path / "absent.env"), "--model", "gpt-6.1-terra"]
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


@pytest.mark.parametrize("use_alias", [False, True])
def test_comparison_rejects_recording_reused_across_trials(run_pair, tmp_path, use_alias):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    recordings = {(1, mode): path for mode, path in paths.items()}
    for mode, path in paths.items():
        alias = tmp_path / f"alias_{mode}"
        if use_alias:
            alias.symlink_to(path, target_is_directory=True)
        recordings[2, mode] = alias if use_alias else path
    write_attempt_ledger(ledger, recordings, 2)
    with pytest.raises(ValueError, match="recording.*path|reused|duplicate.*recording"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")])


def test_comparison_rejects_scheduled_run_name_mismatch(run_pair, tmp_path):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    rows[0]["run_name"] = "different_scheduled_trial"
    write_json_lines(ledger, rows)
    with pytest.raises(ValueError, match="run_name|run name|scheduled.*task|scheduled.*trial"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")])


@pytest.mark.parametrize("key,value", [("model", "different-model"), ("max_turns", 99),
    ("max_output_tokens", 6000), ("viewport", [800, 600]), ("reasoning_effort", "low")])
def test_comparison_rejects_uniform_schedule_that_differs_from_actual_controls(run_pair, tmp_path, key, value):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    for row in rows:
        row["configuration"][key] = value
    write_json_lines(ledger, rows)
    with pytest.raises(ValueError, match="schedule|configuration|model|budget|control"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")])


@pytest.mark.parametrize("binding", ["rubric_sha256", "judge_model"])
def test_comparison_rejects_grade_not_bound_to_schedule(run_pair, tmp_path, monkeypatch, binding):
    paths, *_ = run_pair
    rubric = tmp_path / "rubric.json"
    write_json(rubric, {"task_id": "task_01", "instruction": "Report done.", "start_url": "https://example.test",
        "criteria": [{"id": "result", "description": "The result is established."}]})
    monkeypatch.setattr(runner.ModelClient, "_post", lambda self, payload: {
        "model": "gpt-5.6-sol", "output_text": json.dumps({"criteria": [{"id": "result", "verdict": "success",
            "reason": "Observed", "states": [1]}]}), "usage": {"input_tokens": 100, "output_tokens": 10}})
    for path in paths.values():
        asyncio.run(grade_run(path, rubric, judge_model="gpt-5.6-sol", api_key="test", execute=True))
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    for row in rows:
        row.update(rubric=str(rubric), rubric_sha256=hashlib.sha256(rubric.read_bytes()).hexdigest(),
            judge_model="gpt-5.6-sol")
        row[binding] = "0" * 64 if binding == "rubric_sha256" else "different-judge"
    write_json_lines(ledger, rows)
    with pytest.raises(ValueError, match="rubric|judge|grading"):
        compare_main(["--ledger", str(ledger), "--output", str(tmp_path / "report")])



def test_partial_recording_keeps_known_cost_and_discloses_unknown_coverage(run_pair, tmp_path):
    paths, *_ = run_pair
    ledger = tmp_path / "ledger.jsonl"
    rows = write_attempt_ledger(ledger, {(1, mode): path for mode, path in paths.items()}, 1)
    (paths["dom"] / "final.json").unlink()
    rows[0]["technical_outcome"] = "interrupted"
    write_json_lines(ledger, rows)
    output = tmp_path / "partial-report"
    assert compare_main(["--ledger", str(ledger), "--output", str(output)]) == 0
    summary = json.loads((output / "summary.json").read_text())
    pairs = json.loads((output / "pairs.json").read_text())
    dom = pairs[0]["dom"]
    assert summary["scheduled_attempts"] == 2 and summary["paired_attempts"] == 0
    assert dom["run_status"] == "interrupted"
    assert dom["partial_recording"] is True
    assert dom["cost_coverage"] == "partial"
    assert dom["turns_complete"] is False
    assert dom["model_turns"] == 4
    assert dom["token_usage"]["input_tokens"] == 80
    assert dom["token_usage"]["output_tokens"] == 40
    assert dom["token_usage"]["total_tokens"] == 120
    assert dom["completion"]["verdict"] == "ungraded"
    result = summary["modes"]["dom"]
    assert result["attempted_runs"] == 1
    assert result["cost_coverage"] == {"partial": 1}
    assert result["tokens_complete"] is False and result["turns_complete"] is False
    assert result["mean_tokens_all_attempts"] is None
    assert result["mean_tokens_all_attempts_lower_bound"] == 120
    assert summary["technical_outcomes"]["interrupted"] == 1



def test_batch_partial_recording_is_not_zero_cost_startup_failure(tmp_path, monkeypatch):
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
    def run(command, **kwargs):
        mode = command[command.index("--observation-mode") + 1]
        name = command[command.index("--run-name") + 1]
        root = Path(command[command.index("--output-dir") + 1])
        directory = root / name / mode / "custom"
        write_json(directory / "manifest.json", {"status": "running", "model_turns": 1})
        write_json_lines(directory / "decisions.jsonl", [{"model_turn": 1,
            "usage": {"input_tokens": 7, "output_tokens": 5}, "latency_seconds": 0.1}])
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(task_cli.subprocess, "run", run)
    assert task_cli.main(["custom", "--trials", "1", "--catalog-file", str(catalog), "--rubric-dir", str(rubrics),
        "--judge-model", "gpt-5.6-sol", "--output-dir", str(output),
        "--run-name", "partial", "--env-file", str(tmp_path / "absent.env"), "--model", "gpt-6.1-terra"]) == 0
    ledger = output / "partial" / "ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert all(row["completed"] and row["technical_outcome"] == "incomplete_recording" for row in rows)
    report = tmp_path / "partial-report"
    assert compare_main(["--ledger", str(ledger), "--output", str(report)]) == 0
    summary = json.loads((report / "summary.json").read_text())
    for mode in ("dom", "screenshot"):
        result = summary["modes"][mode]
        assert result["tokens"] == 12
        assert result["cost_coverage"] == {"partial": 1}
        assert result["tokens_complete"] is False
        assert result["turns_complete"] is False
        assert result["mean_tokens_all_attempts"] is None
        assert result["mean_tokens_all_attempts_lower_bound"] == 12


def test_comparison_rejects_unverified_profiles_and_changed_runtime(run_pair):
    import copy
    paths, *_ = run_pair
    dom, ss = [inspect_recording(paths[m]) for m in ("dom","screenshot")]
    bad = copy.deepcopy(ss)
    bad["manifest"]["browser_profile_provenance"]["profile_fresh_at_run_start"] = None
    with pytest.raises(ValueError, match="freshness"):
        compare(dom,bad)
    bad = copy.deepcopy(ss)
    bad["manifest"]["browser_profile_provenance"]["browser_environment"]["LANG"] = "different"
    with pytest.raises(ValueError, match="environments"):
        compare(dom,bad)


def test_local_request_preparation_failure_is_not_a_model_call(run_pair, tmp_path, monkeypatch):
    monkeypatch.setattr(runner.Path, "read_bytes", lambda self: (_ for _ in ()).throw(OSError("unreadable observation")))
    # Read failure occurs before ModelClient starts an API request.
    client = runner.ModelClient("unused","gpt-6.1-terra","unused")
    bundle = capture.CaptureBundle(observation_mode="screenshot", screenshot_path=tmp_path/"missing.png")
    with pytest.raises(OSError):
        asyncio.run(client.decide(task="inspect",step=1,max_steps=5,bundle=bundle,task_memory="",
            recent_actions=[],turn_dir=tmp_path,viewport=(1365,768)))
    assert not client.last_input_report.get("api_call_started")


def test_ungraded_primary_policy_cannot_be_mixed(run_pair):
    paths, *_ = run_pair
    for mode, policy in (("dom","paired"),("screenshot","actor_native")):
        recording = inspect_recording(paths[mode])
        write_json(paths[mode]/"completion.json", {"task_id":"task_01", "observation_mode":mode,
            "recording_sha256":recording["recording_sha256"], "method":"ungraded", "verdict":"ungraded",
            "evidence_policy":policy})
    with pytest.raises(ValueError, match="evidence_policy"):
        compare(*(inspect_recording(paths[m]) for m in ("dom","screenshot")))


@pytest.mark.parametrize("change",["environment","missing_environment","missing_build","capture","renderer"])
def test_ledger_requires_shared_capture_and_environment_across_all_trials(run_pair,tmp_path,change):
    import shutil
    paths, *_ = run_pair
    recordings = {}
    for trial in (1,2):
        for mode in ("dom","screenshot"):
            path = tmp_path/f"trial_{trial:04d}"/mode/"task_01"
            shutil.copytree(paths[mode],path)
            for filename in ("task.json","manifest.json"):
                value = json.loads((path/filename).read_text())
                value["run_name"] = f"trial_{trial:04d}"
                if filename=="manifest.json":
                    profile = value["browser_profile_provenance"]
                    if change=="environment" and trial==2:
                        profile["browser_environment"]["LANG"] = "changed-in-both-arms"
                    if change=="missing_environment" and trial==1 and mode=="dom":
                        profile["browser_environment"] = {}
                    if change=="missing_build" and trial==1 and mode=="dom":
                        profile["browser_build"].pop("image_id")
                    if change=="capture" and mode=="screenshot":
                        value["dom_capture_parameters"]["max_nodes"] += 1
                    if change=="renderer" and mode=="screenshot":
                        value["renderer_versions"]["full"]["sha256"] = "changed"
                write_json(path/filename,value)
            recordings[(trial,mode)] = path
    ledger = tmp_path/"schedule.jsonl"
    write_attempt_ledger(ledger,recordings,2)
    with pytest.raises(ValueError,match="environment|build|capture|renderer"):
        compare_main(["--ledger",str(ledger),"--output",str(tmp_path/"report")])


def test_actor_default_limits_and_single_model_configuration(tmp_path, monkeypatch):
    args = runner.parse_args(["--env-file", str(tmp_path/"absent.env")])
    assert args.model == "gpt-6.1-terra"
    assert args.max_steps == 200 and args.max_output_tokens == 10000
    launched = task_cli.parse_args(["sample", "--output-dir", str(tmp_path)])
    assert launched.max_steps == 200 and launched.max_output_tokens == 10000
    assert runner.MAX_TASK_MEMORY_CHARS == 8000
    definition = {"instruction": "Read heading", "start_url": "https://example.test", "model": "gpt-5.6-sol"}
    command = task_cli.build_runner_command(definition, task_id="sample", task_name="sample",
        run_id="sample", output_dir=tmp_path, env_file=tmp_path/"absent.env", model="",
        max_steps=200, observation_mode="dom")
    assert command[command.index("--model")+1] == "gpt-6.1-terra"
    assert command[command.index("--max-output-tokens")+1] == "10000"
    assert "gpt-5.6-sol" not in command  # Catalog metadata cannot select a second actor.


@pytest.mark.parametrize("configured,override", [("", None), ("gpt-5.6-sol", None),
    ("gpt-6.1-terra", "gpt-6.1-sol")])
def test_actor_startup_rejects_missing_wrong_or_overridden_model(tmp_path, monkeypatch, configured, override):
    monkeypatch.setenv("OPENAI_MODEL", configured)
    monkeypatch.setattr(runner, "CDPClient", lambda *a,**k: pytest.fail("invalid model opened a browser"))
    common = ["--env-file", str(tmp_path/"absent.env"), "--observation-mode", "dom",
        "--task", "Read heading", "--start-url", "https://example.test", "--output-dir", str(tmp_path/"run")]
    options = ["--model", override] if override is not None else []
    args = runner.parse_args(common+options)
    with pytest.raises(RunnerError, match="OPENAI_MODEL=gpt-6.1-terra"):
        asyncio.run(runner.run(args))
    with pytest.raises(RunnerError, match="OPENAI_MODEL=gpt-6.1-terra"):
        task_cli.main(["sample", *common, "--dry-run", *options])
    assert not (tmp_path/"run").exists()


def test_actor_env_rejects_duplicate_or_conflicting_model_values(tmp_path, monkeypatch):
    envfile = tmp_path/"models.env"
    envfile.write_text("OPENAI_MODEL=gpt-6.1-terra\nOPENAI_MODEL=gpt-6.1-terra\n")
    with pytest.raises(RunnerError, match="exactly one"):
        runner.load_env(envfile)
    envfile.write_text("OPENAI_MODEL=gpt-5.6-sol\n")
    with pytest.raises(RunnerError, match="conflicts"):
        runner.load_env(envfile)


@pytest.mark.parametrize("returned", ["gpt-6.1-sol", "gpt-5.6-sol", "gpt-6.1-terra-mini", None])
@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_non_terra_actor_response_stops_before_any_action(run_pair, tmp_path, monkeypatch, mode, returned):
    calls = []
    def post(self,payload):
        calls.append(payload)
        return {"model": returned, "status": "completed", "output_text": json.dumps({
            "action": "wait", "seconds": 0, "thought": "observe"}),
            "usage": {"input_tokens": 10, "output_tokens": 5}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    monkeypatch.setattr(AgentBrowserClient, "execute", AsyncMock(side_effect=AssertionError("wrong actor executed")))
    root = tmp_path/f"mismatch_{mode}"
    args = runner.parse_args(["--env-file", str(tmp_path/"absent.env"), "--observation-mode", mode,
        "--task", "Read heading", "--task-id", "mismatch", "--start-url", "https://example.test",
        "--output-dir", str(root), "--api-key", "test", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 2
    recording = inspect_recording(root/"mismatch")
    assert len(calls) == 1 and recording["manifest"]["model_turns"] == 1
    assert recording["manifest"]["steps"] == []
    assert recording["manifest"]["configured_actor_model"] == "gpt-6.1-terra"
    assert recording["decisions"][0]["returned_model"] == returned
    assert "actor model mismatch" in recording["final"]["error"]


@pytest.mark.parametrize("judge", [None, "gpt-6.1-terra", "gpt-5.6"])
def test_batch_completion_judge_is_explicit_and_cannot_fall_back_to_actor(tmp_path, monkeypatch, judge):
    arguments = ["--trials", "1", "--rubric-dir", str(tmp_path/"rubrics"),
        "--output-dir", str(tmp_path/"out"), "--env-file", str(tmp_path/"absent.env"), "--dry-run"]
    if judge is not None:arguments += ["--judge-model", judge]
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *a,**k: pytest.fail("invalid judge started a child"))
    with pytest.raises(RunnerError, match="completion.*judge|completion grading"):
        task_cli.main(arguments)
    assert not (tmp_path/"out").exists()


@pytest.mark.parametrize("option,value,error", [("--max-output-tokens", "9000", "exactly 10000"),
    ("--max-output-tokens", "12000", "exactly 10000"), ("--max-turns", "201", "no greater than 200")])
def test_actor_rejects_output_override_and_turns_above_cap(tmp_path, monkeypatch, option, value, error):
    arguments = ["--env-file", str(tmp_path/"absent.env"), "--observation-mode", "dom",
        "--task", "Read heading", "--start-url", "https://example.test", "--output-dir", str(tmp_path/"out")]
    monkeypatch.setattr(runner, "CDPClient", lambda *a,**k: pytest.fail("invalid limits opened browser"))
    with pytest.raises(RunnerError, match=error):
        asyncio.run(runner.run(runner.parse_args(arguments+[option,value])))
    with pytest.raises(RunnerError, match=error):
        task_cli.main(["sample", *arguments, "--dry-run", option,value])
    kwargs = {"max_output_tokens": int(value)} if option=="--max-output-tokens" else {"max_steps": int(value)}
    with pytest.raises(RunnerError, match=error):
        task_cli.build_runner_command({"instruction":"Read heading", "start_url":"https://example.test"},
            task_id="sample", task_name="sample", run_id="sample", output_dir=tmp_path,
            env_file=tmp_path/"absent.env", **kwargs)
    client = runner.ModelClient("test", "gpt-6.1-terra", "https://unused.test")
    bundle = capture.CaptureBundle(snapshot_path=tmp_path/"dom.json")
    with pytest.raises(RunnerError, match=error):
        asyncio.run(client.decide(task="Read heading", step=1, max_steps=kwargs.get("max_steps", 200),
            max_output_tokens=kwargs.get("max_output_tokens", 10000), bundle=bundle,
            task_memory="", recent_actions=[], turn_dir=tmp_path, viewport=(1365,768)))
    assert not client.last_input_report.get("api_call_started")
    assert not (tmp_path/"out").exists()


def test_actor_tpt_uses_separate_known_call_denominators_and_preserves_missing_usage(run_pair):
    import copy
    paths, *_ = run_pair
    recording = copy.deepcopy(inspect_recording(paths["dom"]))
    recording["decisions"][0]["usage"] = {"input_tokens": 100, "output_tokens": 40,
        "input_tokens_details": {"cached_tokens": 60}, "output_tokens_details": {"reasoning_tokens": 30}}
    recording["decisions"][1]["usage"] = {"input_tokens": 200}
    recording["decisions"][2]["usage"] = {}
    recording["decisions"][3]["usage"] = {"input_tokens": 300, "output_tokens": 60}
    result = summarize(recording)
    assert result["model_turns"] == 4 and result["rejected_turns"] == 2
    assert result["termination_turns"] == 1
    assert result["token_usage"]["input_tokens"] == 600
    assert result["token_usage"]["output_tokens"] == 100
    assert result["token_usage"]["total_tokens"] == 700
    assert result["token_usage"]["reasoning_tokens"] == 30
    assert result["token_usage"]["cached_input_tokens"] == 60
    assert result["token_usage"]["cache_write_input_tokens"] is None
    assert result["tokens_per_turn"]["input_tokens"]["known_calls"] == 3
    assert result["tokens_per_turn"]["input_tokens"]["known_usage_mean"] == 200
    assert result["tokens_per_turn"]["output_tokens"]["known_calls"] == 2
    assert result["tokens_per_turn"]["output_tokens"]["known_usage_mean"] == 50
    assert result["tokens_per_turn"]["input_tokens"]["mean"] is None
    assert result["turns_missing_usage"] == 2


def test_evaluation_join_checks_identity_and_keeps_four_directional_metrics(run_pair):
    paths, *_ = run_pair
    recording = inspect_recording(paths["dom"])
    task = recording["task"]
    root = paths["dom"].parent.parent / "evaluations" / str(task["run_name"]) / "dom" / task["source_task_id"] / recording["recording_sha256"]
    metrics = {name: {"count": index, "denominator": 4, "rate": index/4} for index, name in enumerate((
        "screenshot_evidence_loss", "dom_model_evidence_loss", "screenshot_verifier_misses", "dom_model_verifier_misses"))}
    evaluation = {"recording_sha256": recording["recording_sha256"], "task_id": task["source_task_id"],
        "actor_arm": "dom", "trial_id": str(task["run_name"]), "rubric_sha256": "frozen",
        "coverage": {"audit_eligible_states": [1]}, "stages": {"audit": {"status": "complete", "metrics": metrics,
        "calls": [{"stage": "inventory", "requested_model": "gpt-5.6-sol", "usage": {"prompt_tokens": 11, "completion_tokens": 7,
            "completion_tokens_details": {"reasoning_tokens": 5}}}]}}}
    root.mkdir(parents=True)
    write_json(root / "evaluation.json", evaluation)
    result = summarize(recording)
    assert result["evidence_audit"] == metrics
    assert result["judge_usage_streams"]["audit:inventory"]["usage"]["total_tokens"] == 18
    assert result["judge_usage_streams"]["audit:inventory"]["usage"]["reasoning_tokens"] == 5
    assert result["judge_usage_streams"]["audit:adjudication"]["usage"]["input_tokens"] is None
    evaluation["trial_id"] = "another-trial"
    write_json(root / "evaluation.json", evaluation)
    with pytest.raises(ValueError, match="task, arm, trial"):
        summarize(recording)


def test_aggregate_distributions_categories_and_missing_audit_coverage(run_pair):
    import copy
    paths, *_ = run_pair
    pair, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    pair.update(task_id="medium_task", trial_id="1", difficulty="medium")
    other = copy.deepcopy(pair)
    other.update(task_id="hard_task", difficulty="hard")
    other["dom"]["token_usage"]["input_tokens"] = 120
    other["dom"]["tokens_per_turn"]["input_tokens"].update(tokens=120, known_usage_mean=30, mean=30)
    pair["dom"]["evidence_audit"] = {"screenshot_evidence_loss": {"count": 1, "denominator": 4, "rate": .25}}
    pair["dom"]["evidence_audit_status"] = "complete"
    result = aggregate([pair, other])
    assert result["modes"]["dom"]["tokens_per_turn"]["input_tokens"]["known_usage_mean"] == 25
    assert result["modes"]["dom"]["distributions"]["input_tokens"]["mean"] == 100
    assert result["modes"]["dom"]["distributions"]["input_tokens"]["median"] == 100
    assert result["categories"]["medium"]["dom"]["attempted_runs"] == 1
    assert result["categories"]["hard"]["dom"]["attempted_runs"] == 1
    assert result["modes"]["dom"]["evidence_audit"]["screenshot_evidence_loss"] == {
        "count": 1, "denominator": 4, "rate": .25, "audited_runs": 1, "attempted_runs": 2}
    assert result["modes"]["screenshot"]["evidence_audit"]["screenshot_evidence_loss"]["rate"] is None
    assert len(result["audit_by_task_trial"]) == 2


def test_actor_hard_cap_and_output_limit_rates_include_all_recorded_calls(run_pair):
    import copy
    paths, *_ = run_pair
    recording = copy.deepcopy(inspect_recording(paths["dom"]))
    recording["manifest"]["controls"]["max_turns"] = 200
    recording["final"]["run_status"] = "turn_limit"
    recording["decisions"] = [{"accepted": False, "usage": {"input_tokens": 10, "output_tokens": 5},
        "output_limit_hit": index < 2} for index in range(200)]
    dom = summarize(recording)
    assert dom["step_cap_hit"] is True and dom["model_turns"] == 200
    assert dom["tokens_per_turn"]["input_tokens"]["mean"] == 10
    screenshot = copy.deepcopy(dom)
    screenshot["step_cap_hit"] = False
    pair = {"task_id": "cap_task", "trial_id": "1", "shared_controls": {}, "dom": dom,
        "screenshot": screenshot, "both_successful": False, "successful_pair_turn_delta": None}
    result = aggregate([pair])
    assert result["modes"]["dom"]["hard_cap_200_rate"] == 1
    assert result["modes"]["screenshot"]["hard_cap_200_rate"] == 0
    assert result["modes"]["dom"]["output_limit_hit_rate"] == .01


def test_no_reported_actor_usage_remains_unknown_in_totals_and_tpt(run_pair):
    import copy
    paths, *_ = run_pair
    pair, _ = compare(*(inspect_recording(paths[mode]) for mode in ("dom", "screenshot")))
    for mode in ("dom", "screenshot"):
        recording = copy.deepcopy(inspect_recording(paths[mode]))
        for row in recording["decisions"]:
            row["usage"] = None
        pair[mode] = summarize(recording)
        assert pair[mode]["token_usage"]["input_tokens"] is None
        assert pair[mode]["tokens_per_turn"]["input_tokens"]["known_calls"] == 0
    result = aggregate([pair])
    assert result["modes"]["dom"]["token_usage"]["input_tokens"] is None
    assert result["modes"]["dom"]["tokens_per_turn"]["input_tokens"]["known_usage_mean"] is None
    assert result["modes"]["dom"]["mean_tokens_all_attempts"] is None
    assert result["modes"]["dom"]["distributions"]["input_tokens"]["known_runs"] == 0


@pytest.mark.parametrize("dry_run,judge", [(False, None), (False, "gpt-5.6-sol"), (True, None)])
def test_batch_execution_requires_frozen_rubrics_and_planning_requires_judge(tmp_path, judge, dry_run):
    arguments = ["--trials", "1", "--env-file", str(tmp_path / "absent.env"), "--output-dir", str(tmp_path / "recordings")]
    if judge is not None:
        arguments += ["--judge-model", judge]
    if dry_run:
        arguments.append("--dry-run")
    with pytest.raises(RunnerError, match="every batch trial requires.*rubric-dir"):
        task_cli.main(arguments)


def test_resumed_judge_attempt_costs_keep_known_history_and_unknown_coverage(run_pair):
    paths, *_ = run_pair
    recording = inspect_recording(paths["dom"])
    task = recording["task"]
    root = paths["dom"].parent.parent / "evaluations" / str(task["run_name"]) / "dom" / task["source_task_id"] / recording["recording_sha256"]
    root.mkdir(parents=True)
    grade = {"recording_sha256": recording["recording_sha256"], "task_id": task["source_task_id"],
        "observation_mode": "dom", "rubric_sha256": "frozen", "evidence_policy": "paired",
        "method": "model_judge", "verdict": "success", "judge_model": "gpt-5.6-sol", "judge_calls": 1,
        "returned_judge_model": "gpt-5.6-sol-2026-10-01",
        "usage": {"input_tokens": 30, "output_tokens": 10}}
    write_json(paths["dom"] / "completion.json", grade)
    evaluation = {"recording_sha256": recording["recording_sha256"], "task_id": task["source_task_id"],
        "actor_arm": "dom", "trial_id": str(task["run_name"]), "rubric_sha256": "frozen", "stages": {
        "paired_completion": {"status": "model_judge", "attempt_history": [
            {"status": "ungraded", "calls": 1, "usage": {"input_tokens": 20, "output_tokens": 5}, "usage_coverage": "complete",
                "model_settings": {"returned_model": "gpt-5.6-sol-2026-10-01"}},
            {"status": "interrupted", "usage_coverage": "unknown"}]},
        "dom_model": {"status": "complete", "usage_coverage": "complete", "calls": {"gpt-5.2": 2},
            "usage": {"gpt-5.2": {"input_tokens": 60, "output_tokens": 15}}, "attempt_history": [
            {"status": "failed", "calls": {"gpt-5.2": 1}, "usage": {"gpt-5.2": {"input_tokens": 10, "output_tokens": 2}}, "usage_coverage": "complete"}]}}}
    write_json(root / "evaluation.json", evaluation)
    result = summarize(recording)
    stream = result["judge_usage_streams"]["paired_completion"]
    assert stream["usage"]["input_tokens"] == 50 and stream["usage"]["output_tokens"] == 15
    assert stream["usage"]["total_tokens"] == 65
    assert stream["calls"] is None and stream["known_calls"] == 2
    assert stream["unknown_attempts"] == 1 and stream["usage_coverage"] == "partial"
    assert {row["returned_model"] for row in stream["call_records"]} == {"gpt-5.6-sol-2026-10-01"}
    auxiliary = result["judge_usage_streams"]["dom_model:gpt-5.2"]
    assert auxiliary["usage"]["input_tokens"] == 70 and auxiliary["usage"]["output_tokens"] == 17
    assert auxiliary["calls"] == 3 and auxiliary["usage_coverage"] == "complete"
    assert result["judge_usage"]["input_tokens"] == 50
    assert summarize(recording)["judge_usage_streams"] == result["judge_usage_streams"]


@pytest.mark.parametrize('large_context', [False, True])
def test_actor_list_price_estimate_uses_per_call_tiers_and_subsets(run_pair, large_context):
    from w8bench.verifier.compare_results import summarize
    paths, *_ = run_pair
    recording = inspect_recording(paths['dom'])
    for row in recording['decisions']:
        row['usage'] = {'input_tokens': 300000 if large_context else 100, 'output_tokens': 20,
            'input_tokens_details': {'cached_tokens': 40, 'cache_write_tokens': 20},
            'output_tokens_details': {'reasoning_tokens': 10}}
    priced = summarize(recording)['cost_streams']['actor']['cost']
    per_call = ((300000 - 60) * 2 + 40 * .1 + 20 * 2.5 + 20 * 7.5) / 1000000 if large_context else .000167
    assert priced['estimated_usd'] == pytest.approx(per_call * len(recording['decisions']))
    assert priced['priced_calls'] == len(recording['decisions'])
    assert priced['kind'] == 'estimated_from_list_prices'


def test_actor_cost_missing_usage_is_not_a_zero_price(run_pair):
    from w8bench.verifier.compare_results import summarize
    paths, *_ = run_pair
    recording = inspect_recording(paths['dom'])
    recording['decisions'][0]['usage'] = {}
    priced = summarize(recording)['cost_streams']['actor']['cost']
    assert priced['estimated_usd'] is None
    assert priced['known_usage_estimate_usd'] > 0
    assert priced['unpriced_calls'] == 1
    assert priced['coverage'] == 'partial'


def test_runtime_fresh_configuration_reads_actor_and_audit_defaults_from_template(tmp_path, monkeypatch, capsys):
    from w8bench.task_recorder import browser_runtime
    monkeypatch.setattr(browser_runtime, "ROOT", tmp_path)
    monkeypatch.setattr(browser_runtime, "choose_port", lambda preferred, used: preferred)
    monkeypatch.setattr(browser_runtime, "unique_container_name", lambda base: base)
    (tmp_path / ".env.example").write_text("OPENAI_MODEL=actor-from-template\n"
        "EVIDENCE_AUDIT_MODEL=inventory-from-template\nEVIDENCE_ADJUDICATOR_MODEL=adjudicator-from-template\n"
        "EVIDENCE_AUDIT_PROVIDER=openai\nEVIDENCE_ADJUDICATOR_PROVIDER=google\nGEMINI_API_KEY=\n"
        "TASK_CATALOG_FILE=tasks.jsonl\n")
    path = tmp_path / "fresh.env"
    assert browser_runtime.configure(path, False) == 0
    values = browser_runtime.read_env(path)
    assert values["OPENAI_MODEL"] == "actor-from-template"
    assert values["EVIDENCE_AUDIT_MODEL"] == "inventory-from-template"
    assert values["EVIDENCE_ADJUDICATOR_MODEL"] == "adjudicator-from-template"
    assert values["EVIDENCE_AUDIT_PROVIDER"] == "openai"
    assert values["EVIDENCE_ADJUDICATOR_PROVIDER"] == "google"
    assert values["GEMINI_API_KEY"] == ""
    assert values["TASK_CATALOG_FILE"] == "tasks.jsonl"
    output = capsys.readouterr().out
    assert "Set OPENAI_API_KEY and GEMINI_API_KEY credentials" in output
    assert "Edit OPENAI_API_KEY and OPENAI_MODEL" not in output


def test_runtime_port_refresh_preserves_audit_settings_and_fake_credentials(tmp_path, monkeypatch, capsys):
    from w8bench.task_recorder import browser_runtime
    monkeypatch.setattr(browser_runtime, "ROOT", tmp_path)
    monkeypatch.setattr(browser_runtime, "choose_port", lambda preferred, used: preferred)
    monkeypatch.setattr(browser_runtime, "unique_container_name", lambda base: base)
    (tmp_path / ".env.example").write_text("OPENAI_MODEL=gpt-6.1-terra\n"
        "EVIDENCE_AUDIT_MODEL=template-inventory\nEVIDENCE_ADJUDICATOR_MODEL=template-adjudicator\n"
        "TASK_CATALOG_FILE=tasks.jsonl\n")
    path = tmp_path / "existing.env"
    expected = {"OPENAI_MODEL": "gpt-6.1-terra", "OPENAI_API_KEY": "fake-openai-test-value",
        "GEMINI_API_KEY": "fake-google-test-value", "EVIDENCE_AUDIT_MODEL": "configured-inventory",
        "EVIDENCE_ADJUDICATOR_MODEL": "configured-adjudicator", "EVIDENCE_AUDIT_PROVIDER": "openai",
        "EVIDENCE_ADJUDICATOR_PROVIDER": "google", "CONTAINER_NAME": "owned-browser",
        "TASK_CATALOG_FILE": "existing-tasks.jsonl"}
    path.write_text("".join(f"{key}={value}\n" for key, value in expected.items()))
    assert browser_runtime.configure(path, True) == 0
    actual = browser_runtime.read_env(path)
    assert {key: actual[key] for key in expected} == expected
    output = capsys.readouterr().out
    assert expected["OPENAI_API_KEY"] not in output and expected["GEMINI_API_KEY"] not in output
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_compact_catalog_runs_in_both_arms_and_records_hash(run_pair, tmp_path, monkeypatch, mode):
    paths, *_ = run_pair
    for prior in paths.values():
        assert json.loads((prior / "manifest.json").read_text())["catalog_sha256"] is None
        assert json.loads((prior / "task.json").read_text())["catalog_sha256"] is None
    catalog = tmp_path / "catalog-with-crlf.jsonl"
    row = {"task_id": "task_08", "task_name": "Read café heading", "category": "research",
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
        "model": "gpt-6.1-terra", "output_text": json.dumps(proposals.pop(0)),
        "usage": {"input_tokens": 1, "output_tokens": 1}})
    output = tmp_path / "catalog-runs" / mode
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
        "--task", definition["instruction"], "--start-url", row["start_url"], "--task-id", "task_08",
        "--source-task-id", "task_08", "--source-catalog", str(catalog), "--output-dir", str(output),
        "--model", "gpt-6.1-terra", "--api-key", "offline-placeholder", "--max-turns", "2", "--settle-seconds", "0"])
    assert asyncio.run(runner.run(args)) == 0
    recording = inspect_recording(output / "task_08")
    for item in (recording["task"], recording["manifest"]):
        assert item["catalog_sha256"] == expected_hash
        assert item["difficulty"] == row["difficulty"] and item["category"] == row["category"]
        assert item["source_task_id"] == row["task_id"]
        assert item["source_catalog"] == str(catalog.resolve())
        assert "attribution" not in item
    request = json.loads((output / "task_08" / "turns/turn_000001/request.json").read_text())
    assert expected_hash not in json.dumps(request)
    assert "ATTRIBUTION.md" not in json.dumps(request)


@pytest.fixture
def curated_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(task_cli, "ROOT", tmp_path)
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    row = {"task_id": "task_12", "task_name": "Public heading", "category": "research",
        "instruction": "Read the heading.", "start_url": "https://example.test",
        "stopping_condition": "Report the heading.", "constraints": ["Remain read-only."], "difficulty": "medium"}
    catalog = tmp_path / "data" / "tasks.jsonl"
    catalog.parent.mkdir()
    catalog.write_bytes((json.dumps(row) + "\r\n").encode())
    write_json(tmp_path / "internal" / "task_validity.json", {"catalog": "data/tasks.jsonl",
        "tasks": {"task_12": {"valid_until": "2000-12-31"}}})
    return catalog, row


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


@pytest.mark.parametrize("batch", [False, True])
def test_launcher_refuses_expired_before_scheduling_and_allows_explicit_override(curated_catalog, tmp_path, batch, capsys):
    catalog, row = curated_catalog
    output = tmp_path / "recordings"
    args = [row["task_id"], "--catalog-file", str(catalog), "--output-dir", str(output),
        "--run-name", "expiry", "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    args += ["--trials", "2", "--judge-model", "gpt-5.6-sol"] if batch else ["--observation-mode", "dom"]
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


@pytest.mark.parametrize("mode", ["dom", "screenshot"])
def test_runner_expiry_refusal_override_and_inclusive_utc_date(run_pair, curated_catalog, tmp_path, monkeypatch, mode):
    catalog, row = curated_catalog
    definition = task_cli.fetch_catalog_task(str(catalog), row["task_id"])
    calls = []
    def post(self, payload):
        calls.append(payload)
        decision = ({"action": "wait", "seconds": 0, "thought": "Observe the current page."} if len(calls) % 2 else
            {"action": "terminate", "status": "success", "termination_reason": "completed", "final_answer": "done", "thought": "Observed heading."})
        return {"model": "gpt-6.1-terra", "output_text": json.dumps(decision),
            "usage": {"input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr(runner.ModelClient, "_post", post)
    output = tmp_path / "expired-run"
    args = ["--env-file", str(tmp_path / "absent.env"), "--observation-mode", mode,
        "--task", definition["instruction"], "--start-url", row["start_url"], "--task-id", row["task_id"],
        "--source-task-id", row["task_id"], "--source-catalog", str(catalog), "--output-dir", str(output),
        "--model", "gpt-6.1-terra", "--api-key", "offline-placeholder", "--settle-seconds", "0"]
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


def test_pre_rubric_planning_is_separate_and_cannot_resume_as_execution(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(task_cli, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(task_cli, "read_active_run", lambda: None)
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({"task_id": "custom", "instruction": "Read heading.", "start_url": "https://example.test"}) + "\n")
    args = ["--trials", "2", "--catalog-file", str(catalog), "--judge-model", "gpt-5.6-sol",
        "--env-file", str(tmp_path / "absent.env"), "--output-dir", str(tmp_path / "recordings"), "--run-name", "plan"]
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: pytest.fail("planning launched a child"))
    assert task_cli.main(args + ["--dry-run"]) == 0
    root = tmp_path / "recordings" / "plan"
    rows = [json.loads(line) for line in (root / "schedule_preview.jsonl").read_text().splitlines()]
    assert len(rows) == 4 and all(row["planning_only"] and row["rubric"] is None for row in rows)
    assert not (root / "ledger.jsonl").exists()
    with pytest.raises(RunnerError, match="execution requires --rubric-dir"):
        task_cli.main(args)
    rubrics = tmp_path / "rubrics"
    write_json(rubrics / "custom.json", {"task_id": "custom", "criteria": [{"id": "heading", "description": "Read heading."}]})
    # A renamed preview must not become an executable resume ledger.
    write_json_lines(root / "ledger.jsonl", rows)
    with pytest.raises(RunnerError, match="planning-only"):
        task_cli.main(args + ["--rubric-dir", str(rubrics)])
    (root / "ledger.jsonl").unlink()
    monkeypatch.setattr(task_cli.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    assert task_cli.main(args + ["--rubric-dir", str(rubrics)]) == 0
    executed = [json.loads(line) for line in (root / "ledger.jsonl").read_text().splitlines()]
    assert all(not row["planning_only"] and row["completed"] for row in executed)
    assert (root / "schedule_preview.jsonl").is_file()




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
        "--judge-model", "gpt-5.6-sol", "--output-dir", str(output), "--run-name", "hash-check",
        "--env-file", str(tmp_path / "absent.env"), "--dry-run"]
    assert task_cli.main(arguments) == 0
    frozen = output / "hash-check/catalog.jsonl"
    assert frozen.read_bytes() == original
    frozen.write_bytes(original.replace(b"\r\n", b"\n"))
    with pytest.raises(RunnerError, match="saved batch catalog differs"):
        task_cli.main(arguments)


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


def test_comparison_rejects_selected_catalog_hash_mismatch(run_pair):
    import copy
    paths, *_ = run_pair
    dom, screenshot = [inspect_recording(paths[mode]) for mode in ("dom", "screenshot")]
    dom["manifest"]["catalog_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="catalog hashes differ"):
        compare(dom, screenshot)
    dom["task"]["catalog_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="catalog hash differs between arms"):
        compare(dom, screenshot)
    screenshot["task"]["catalog_sha256"] = screenshot["manifest"]["catalog_sha256"] = "f" * 64
    first, _ = compare(dom, screenshot)
    first["trial_id"] = "1"
    second = copy.deepcopy(first)
    second.update(trial_id="2", catalog_sha256="e" * 64)
    with pytest.raises(ValueError, match="catalog hashes differ across"):
        aggregate([first, second])
