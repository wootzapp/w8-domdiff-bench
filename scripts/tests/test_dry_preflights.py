import json
import shutil
import tempfile
from pathlib import Path

from dom_model.runner import parse_args as parse_dom_args, run as run_dom
from scripts.run_comparison import main as comparison_main, prepare_isolated_inputs


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
    experiment = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(dir=experiment / "data") as staged_name, tempfile.TemporaryDirectory(dir=experiment / "rubrics") as rubric_name:
        staged = Path(staged_name)
        screenshot = staged / "data-new-screenshot" / "task1"
        dom = staged / "data-new-dom-model" / "task1"
        shutil.copytree(pair["screenshot"], screenshot)
        shutil.copytree(pair["dom"], dom)
        rubric = Path(rubric_name) / "task1.json"
        metrics = Path(rubric_name) / "task1_generation_metrics.json"
        shutil.copy2(pair["rubric"], rubric)
        shutil.copy2(pair["metrics"], metrics)
        run_id = "offline-dry-preflight-must-not-exist"
        output = experiment / "results" / "task1" / run_id
        assert not output.exists()
        rc = comparison_main(
            [
                "--task", "task1",
                "--staged-root", str(staged),
                "--rubric-file", str(rubric),
                "--generation-metrics", str(metrics),
                "--eval-config", str(pair["config"]),
                "--results-root", str(experiment / "results"),
                "--run-id", run_id,
            ]
        )
        assert rc == 0
        assert '"paid_calls_authorized": false' in capsys.readouterr().out
        assert not output.exists()


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
