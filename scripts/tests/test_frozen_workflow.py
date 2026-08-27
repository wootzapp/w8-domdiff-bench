from pathlib import Path

import pytest

from scripts.generate_frozen_rubric import main as generate_main
from scripts.run_comparison import commands
from scripts.validate_inputs import validate_pair


def test_generator_dry_run_has_zero_writes(pair_factory, capsys, tmp_path):
    pair = pair_factory(sidecars=False, metrics=False)
    experiment = Path(__file__).resolve().parents[2]
    rubric = experiment / "rubrics" / "__offline_dry_run_rubric.json"
    metrics = experiment / "rubrics" / "__offline_dry_run_metrics.json"
    rc = generate_main(
        [
            "--screenshot-task", str(pair["screenshot"]),
            "--dom-task", str(pair["dom"]),
            "--staged-root", str(pair["staged"]),
            "--rubric-file", str(rubric),
            "--metrics-file", str(metrics),
            "--eval-config", str(pair["config"]),
        ]
    )
    assert rc == 0
    assert '"paid_calls_authorized": false' in capsys.readouterr().out
    assert not rubric.exists() and not metrics.exists()
    assert not (pair["screenshot"] / "task_data_with_canonical_rubric.json").exists()
    assert not (pair["dom"] / "task_data_with_canonical_rubric.json").exists()


def test_phase_b_requires_matching_sidecars_metrics_and_rubric(pair_factory):
    pair = pair_factory()
    receipt = validate_pair(
        pair["screenshot"], pair["dom"], rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"], eval_config=pair["config"],
    )
    assert receipt["screenshot_sidecar_validated"] is True
    assert receipt["dom_model_sidecar_validated"] is True
    assert receipt["rubric_generation_calls_during_scoring"] == 0
    assert receipt["maximum_points"] == [7.0, 3.0]


def test_both_commands_share_exact_rubric_and_redo_eval(tmp_path):
    rubric = tmp_path / "frozen.json"
    built = commands(
        screenshot_task=tmp_path / "s", dom_task=tmp_path / "d", rubric_file=rubric,
        generation_metrics=tmp_path / "metrics.json", eval_config=tmp_path / "config",
        run_root=tmp_path / "run",
    )
    values = []
    for command in built.values():
        values.append(command[command.index("--rubric-file") + 1])
        assert "--redo-eval" in command
    assert values == [str(rubric), str(rubric)]


def test_phase_a_rejects_protected_source_tree_as_staging_root():
    experiment = Path(__file__).resolve().parents[2]
    protected = experiment.parent / "benchmarks"
    with pytest.raises(ValueError, match="protected source tree"):
        generate_main(
            [
                "--screenshot-task", str(protected / "unused-screenshot"),
                "--dom-task", str(protected / "unused-dom"),
                "--staged-root", str(protected),
                "--eval-config", str(experiment / "config/endpoints/openai/canonical"),
            ]
        )
