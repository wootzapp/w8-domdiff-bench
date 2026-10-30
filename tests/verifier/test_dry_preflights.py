import json
import shutil
import tempfile
from pathlib import Path

from w8bench.dom_model.runner import parse_args as parse_dom_args, run as run_dom
from w8bench.verifier.run_comparison import main as comparison_main, prepare_isolated_inputs


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
        assert str(repository) not in json.dumps(receipt)
        for command in receipt["commands"].values():
            assert not any(Path(argument).is_absolute() for argument in command)
        assert (repository / receipt["run_root"]).resolve() == output
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
