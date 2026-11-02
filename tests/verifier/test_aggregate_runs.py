import csv
import json
from pathlib import Path

import pytest

from w8bench.verifier import aggregate_runs as aggregate
from .test_combine_audit_passes import _sets


def runs(tmp_path, k=3, flagged=None):
    roots = _sets(tmp_path, k=k, flagged=flagged)
    for root in roots:
        for index, source in enumerate(sorted(root.iterdir()), 1):
            alias = f"task_{index:02d}"
            source.rename(root / alias)
            path = root / alias / "evidence_audit.json"
            value = json.loads(path.read_text())
            value["task_alias"] = alias
            for row in value["criteria"]:
                for finding in row["adjudication"].values():
                    finding["explanation"] = "Saved evidence requirement."
            path.write_text(json.dumps(value))
    return roots


@pytest.mark.parametrize("k", [1, 2, 3, 5])
def test_k_runs_means_are_not_majority_votes(tmp_path, k):
    roots = runs(tmp_path, k=k, flagged={(0, 0, 0, aggregate.LOSS_FLAGS[0])})
    value, categories = aggregate.aggregate_runs(roots, expected_tasks=2, resamples=200)
    assert value["k"] == k
    assert value["criteria_per_run"] == 4
    assert value["mean"][aggregate.LOSS_FLAGS[0]]["count"] == pytest.approx(1 / k)
    assert value["mean"][aggregate.LOSS_FLAGS[0]]["rate"] == pytest.approx(1 / (4 * k))
    assert value["relative_reduction"] == 1
    assert len(categories) == 1
    assert value["confidence_intervals"]["method"] == "paired_task_then_run_percentile_bootstrap"


@pytest.mark.parametrize("field", ["frozen_rubric_sha256", "prompt_version", "criterion"])
def test_mismatched_protocol_or_rubric_rejected(tmp_path, field):
    roots = runs(tmp_path)
    path = roots[1] / "task_01/evidence_audit.json"
    value = json.loads(path.read_text())
    if field == "criterion":
        value["criteria"][0][field] = "Different criterion"
    else:
        value[field] = "a" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="mismatch|differ"):
        aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)


def test_task_set_mismatch_and_duplicates_rejected(tmp_path):
    roots = runs(tmp_path)
    with pytest.raises(ValueError, match="distinct"):
        aggregate.aggregate_runs([roots[0], roots[0]], expected_tasks=2)
    (roots[1] / "task_02/evidence_audit.json").unlink()
    with pytest.raises(ValueError, match="Expected 2"):
        aggregate.aggregate_runs(roots, expected_tasks=2)


def test_paired_hierarchical_intervals_are_seeded_and_keep_sides_together():
    clusters = [[(5, 2, 1), (5, 0, 0)], [(5, 4, 2), (5, 2, 1)]]
    first = aggregate.hierarchical_intervals(clusters, resamples=1000, seed=1)
    assert first == aggregate.hierarchical_intervals(clusters, resamples=1000, seed=1)
    assert first["relative_reduction"] == [0.5, 0.5]
    assert first["undefined_relative_reduction_resamples"] > 0
    zero = aggregate.hierarchical_intervals([[(3, 0, 0)]], resamples=100)
    assert zero["relative_reduction"] is None
    assert zero["undefined_relative_reduction_resamples"] == 100


def test_outputs_and_figures_are_written_without_model_calls(tmp_path):
    roots = runs(tmp_path, flagged={(0, 0, 0, aggregate.LOSS_FLAGS[0])})
    output, figures = tmp_path / "out", tmp_path / "figures"
    readme = tmp_path / "README.md"
    readme.write_text("Keep intro\n<!-- recorded-runs:start -->\nold\n<!-- recorded-runs:end -->\nKeep rest\n")
    assert aggregate.main([*map(str, roots), "--expected-tasks", "2", "--resamples", "100",
                           "--output-dir", str(output), "--figures-dir", str(figures),
                           "--readme", str(readme)]) == 0
    result = json.loads((output / "summary.json").read_text())
    assert result["k"] == 3
    assert result["unclassified_losses"] == 1
    assert readme.read_text().startswith("Keep intro") and readme.read_text().endswith("Keep rest\n")
    with (output / "evidence_categories.tsv").open() as stream:
        assert len(list(csv.DictReader(stream, delimiter="\t"))) == 1
    assert (figures / "evidence-loss-rates.svg").is_file()
