import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from w8bench.dom_model.runner import parse_args as parse_dom_args, run as run_dom
from w8bench.verifier.run_comparison import main as comparison_main, prepare_isolated_inputs
from w8bench.verifier import run_comparison as comparison, run_full_comparison as workflow
from .conftest import tree_digest


def test_dom_runner_dry_preflight_constructs_no_clients_or_outputs(pair_factory, tmp_path):
    pair = pair_factory()
    output = tmp_path / "must-not-exist"
    result = run_dom(
        parse_dom_args(
            [
                "--input", str(pair["dom"]),
                "--rubric-file", str(pair["rubric"]),
                "--generation-metrics", str(pair["metrics"]),
                "--eval-config", str(pair["config"]),
                "--output", str(output),
                "--redo-eval",
                "--dry-run",
            ]
        )
    )
    assert result["status"] == "preflight_passed"
    assert result["paid_calls_authorized"] is False
    assert not output.exists()


def test_phase_b_cli_dry_preflight_writes_nothing(pair_factory, capsys):
    pair = pair_factory()
    repository = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(dir=repository) as staged_name, tempfile.TemporaryDirectory(dir=repository) as output_name:
        staged = Path(staged_name)
        screenshot = staged / "data-ss" / "task1"
        dom = staged / "data-dom" / "task1"
        shutil.copytree(pair["screenshot"], screenshot)
        shutil.copytree(pair["dom"], dom)
        output_files = Path(output_name)
        rubric = output_files / "task1.json"
        metrics = output_files / "task1_generation_metrics.json"
        shutil.copy2(pair["rubric"], rubric)
        shutil.copy2(pair["metrics"], metrics)
        run_id = "offline-dry-preflight-must-not-exist"
        output = repository / "evaluation" / "task1" / run_id
        assert not output.exists()
        rc = comparison_main(
            [
                "--task", "task1",
                "--staged-root", str(staged),
                "--rubric-file", str(rubric),
                "--generation-metrics", str(metrics),
                "--eval-config", str(pair["config"]),
                "--results-root", str(repository / "evaluation"),
                "--run-id", run_id,
            ]
        )
        assert rc == 0
        receipt = json.loads(capsys.readouterr().out)
        assert receipt["paid_calls_authorized"] is False
        assert receipt["evaluation_started_at"] is None
        assert receipt["evaluation_completed_at"] is None
        assert receipt["evidence_audit"]["started_at"] is None
        assert str(repository) not in json.dumps(receipt)
        for command in receipt["commands"].values():
            assert not any(Path(argument).is_absolute() for argument in command)
        assert (repository / receipt["run_root"]).resolve() == output
        assert not output.exists()


@pytest.mark.parametrize("outcome", ["complete", "audit_failed", "scoring_failed"])
def test_execution_times_are_independent_of_output_group_id(pair_factory, tmp_path, monkeypatch, outcome):
    pair = pair_factory()
    source_digest = tree_digest(pair["staged"])
    old_group_id = "20000101T000000Z"
    run_root = tmp_path / "evaluation/task1" / old_group_id
    monkeypatch.setattr(comparison, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(comparison, "require_local_packages", lambda: {})
    monkeypatch.setattr(comparison, "load_env_file", lambda path: None)
    monkeypatch.setattr(comparison, "require_openai_key", lambda: None)
    calls = []

    def execute_mocked(command, log_path):
        calls.append(command)
        if outcome == "scoring_failed":
            raise RuntimeError("fixture scoring error")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("mocked verifier output\n")
        (log_path.parent / "result.json").write_text("{}")

    def audit_mocked(**kwargs):
        assert len(calls) == 2
        if outcome == "audit_failed":
            raise ValueError("fixture audit validation error")
        return {"metrics": {"total_criteria": 2}}

    monkeypatch.setattr(comparison, "_run_logged", execute_mocked)
    monkeypatch.setattr(comparison, "normalize_screenshot", lambda *a, **kw: {})
    monkeypatch.setattr(comparison, "normalize_dom_model", lambda *a, **kw: {})
    monkeypatch.setattr(comparison, "compare", lambda *a: ({}, "Comparison\n"))
    monkeypatch.setattr(comparison, "run_evidence_audit", audit_mocked)
    monkeypatch.setattr(comparison, "render_evidence_audit", lambda audit: "Audit\n")
    monkeypatch.setattr(comparison, "append_audit_to_comparison", lambda **kw: None)
    arguments = [
        "--task", "task1", "--staged-root", str(pair["staged"]),
        "--rubric-file", str(pair["rubric"]), "--generation-metrics", str(pair["metrics"]),
        "--eval-config", str(pair["config"]), "--results-root", str(tmp_path / "evaluation"),
        "--run-id", old_group_id, "--execute",
    ]
    if outcome == "scoring_failed":
        with pytest.raises(RuntimeError, match="fixture scoring error"):
            comparison.main(arguments)
    else:
        assert comparison.main(arguments) == 0
    manifest = json.loads((run_root / "run_manifest.json").read_text())
    assert manifest["run_id"] == old_group_id
    assert manifest["source_task_id"] == pair["task"]["task_id"]
    start = datetime.fromisoformat(manifest["evaluation_started_at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(manifest["evaluation_completed_at"].replace("Z", "+00:00"))
    assert start.year > 2000
    assert start <= end
    assert manifest["evaluation_started_at"].endswith("Z")
    if outcome == "scoring_failed":
        assert manifest["status"] == "error"
        assert manifest["evidence_audit"]["started_at"] is None
    else:
        audit_start = datetime.fromisoformat(manifest["evidence_audit"]["started_at"].replace("Z", "+00:00"))
        audit_end = datetime.fromisoformat(manifest["evidence_audit"]["completed_at"].replace("Z", "+00:00"))
        assert end <= audit_start <= audit_end
        assert manifest["status"] == ("complete" if outcome == "complete" else "complete_with_audit_error")
    assert tree_digest(pair["staged"]) == source_digest


def test_batch_records_actual_times_separately_from_group_id(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "_paired_tasks", lambda root: ["task1"])
    monkeypatch.setattr(workflow, "_validate_task", lambda *a: None)
    monkeypatch.setattr(workflow, "_verify_local_preparation", lambda *a: None)
    monkeypatch.setattr(workflow, "aggregate_audits", lambda *a: {"tasks": 1})
    monkeypatch.setattr(workflow, "render_aggregate_markdown", lambda summary: "Summary\n")

    def execute_mocked(args, data_root):
        root = Path(args.results_root) / args.task / args.run_id
        root.mkdir(parents=True)
        (root / "evidence_audit.json").write_text("{}")
        return 0

    monkeypatch.setattr(workflow, "_run_task", execute_mocked)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    args = SimpleNamespace(
        data_source="local", execute=True, run_id="20000101T000000Z",
        results_root=str(tmp_path / "evaluation"), audit_model="unchanged-model",
    )
    assert workflow._run_all(args, inputs) == 0
    summary = json.loads((tmp_path / "evaluation/batches" / args.run_id / "evidence_loss_summary.json").read_text())
    start = datetime.fromisoformat(summary["batch_started_at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(summary["batch_completed_at"].replace("Z", "+00:00"))
    assert summary["run_id"] == args.run_id
    assert start.year > 2000
    assert start <= end


def test_isolated_screenshot_input_declares_all_n_plus_one_states(
    pair_factory, tmp_path
):
    pair = pair_factory()
    source_answer_path = pair["screenshot"] / "final_answer.json"
    source_answer_before = source_answer_path.read_bytes()

    screenshot_copy, _, _, _ = prepare_isolated_inputs(
        screenshot_task=pair["screenshot"],
        dom_task=pair["dom"],
        rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"],
        run_root=tmp_path / "run",
        action_count=1,
    )

    isolated_answer = json.loads(
        (screenshot_copy / "final_answer.json").read_text(encoding="utf-8")
    )
    assert isolated_answer["screenshots"] == ["screenshot0.png", "screenshot1.png"]
    assert (screenshot_copy / "screenshot0.png").is_file()
    assert (screenshot_copy / "screenshot1.png").is_file()
    assert source_answer_path.read_bytes() == source_answer_before
