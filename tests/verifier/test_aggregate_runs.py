import csv
import json
from pathlib import Path

import pytest

from w8bench.verifier import aggregate_runs as aggregate
from .test_combine_audit_passes import _sets


def runs(tmp_path, k=3, flagged=None):
    roots = _sets(tmp_path / "evaluations", k=k, flagged=flagged)
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
    subset, subset_categories = aggregate.aggregate_runs(
        roots, expected_tasks=2, resamples=100, excluded_tasks=("task_01",))
    assert subset["tasks_per_run"] == 1 and subset["criteria_per_run"] == 2
    assert subset["mean"][aggregate.LOSS_FLAGS[0]]["count"] == 0
    assert subset_categories == []
    with pytest.raises(ValueError, match="unknown catalog"):
        aggregate.aggregate_runs(roots, expected_tasks=2, excluded_tasks=("task_03",))


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
    roots = runs(tmp_path, flagged={(0, 1, 0, aggregate.LOSS_FLAGS[0])})
    with pytest.raises(ValueError, match="distinct"):
        aggregate.aggregate_runs([roots[0], roots[0]], expected_tasks=2)
    with pytest.raises(ValueError, match="distinct run names"):
        aggregate.aggregate_runs([roots[0], tmp_path / "other" / roots[0].name], expected_tasks=2)
    (roots[1] / "task_02/evidence_audit.json").unlink()
    with pytest.raises(ValueError, match="Expected 2"):
        aggregate.aggregate_runs(roots, expected_tasks=2)
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    reference = {f"task_{number:02d}": json.loads(
        (roots[0] / f"task_{number:02d}/evidence_audit.json").read_text())["frozen_rubric_sha256"]
        for number in (1, 2)}
    for index, root in enumerate(roots):
        entries = [{"task_alias": alias, "frozen_rubric_sha256": digest,
                    "evaluation_status": "not_scored" if index == 1 and alias == "task_02" else "complete",
                    "captured_states": 0 if index == 1 and alias == "task_02" else 1,
                    "audit": None if index == 1 and alias == "task_02" else "evidence_audit.json",
                    "unscored_reason": "no_captured_state" if index == 1 and alias == "task_02" else None}
                   for alias, digest in reference.items()]
        (manifests / f"{root.name}.json").write_text(json.dumps({"run_name": root.name, "entries": entries}))
    value, categories = aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    assert value["catalog_tasks"] == 2 and value["tasks_per_run"] == 1
    assert value["criteria_per_run"] == 2
    assert value["coverage"]["outside_common_panel"] == ["task_02"]
    assert [run["available_tasks"] for run in value["per_run"]] == [2, 1, 2]
    assert value["per_run"][0]["available_metrics"][aggregate.LOSS_FLAGS[0]]["count"] == 1
    assert value["mean"][aggregate.LOSS_FLAGS[0]]["count"] == 0 and categories == []
    assert "Available audited tasks" in aggregate.render_table(value)
    path = manifests / f"{roots[1].name}.json"
    manifest = json.loads(path.read_text())
    manifest["entries"][1]["frozen_rubric_sha256"] = "a" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="hashes differ"):
        aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    manifest["entries"][1]["frozen_rubric_sha256"] = reference["task_02"]
    manifest["entries"][1]["unscored_reason"] = None
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unexplained missing"):
        aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)


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
    recordings = tmp_path / "recordings"
    for index, root in enumerate(roots, 1):
        for alias in ("task_01", "task_02"):
            state = recordings / root.name / alias / "steps/step_001"
            state.mkdir(parents=True)
            (state.parent.parent / "task.json").write_text("{}")
            (state.parent.parent / "manifest.json").write_text('{"status": "success"}')
            for name in ("screenshot.png", "dom_model.txt", "dom_full.txt", "dom.json"):
                (state / name).write_bytes(b"x" * index)
    readme = tmp_path / "README.md"
    readme.write_text("Keep intro\n<!-- recorded-runs:start -->\nold\n<!-- recorded-runs:end -->\nKeep rest\n")
    assert aggregate.main([*map(str, roots), "--expected-tasks", "2", "--resamples", "100",
                           "--output-dir", str(output), "--figures-dir", str(figures),
                           "--recordings-root", str(recordings),
                           "--exploratory-exclusions", "task_01",
                           "--readme", str(readme)]) == 0
    result = json.loads((output / "summary.json").read_text())
    assert result["k"] == 3
    assert result["unclassified_losses"] == 1
    assert result["exploratory_subset"]["pre_specified"] is False
    assert result["exploratory_subset"]["criteria_per_run"] == 2
    assert result["recorded_file_sizes"]["recordings"] == 6
    assert all(value == {"success": 2} for value in result["recorded_outcomes"].values())
    sizes = result["recorded_file_sizes"]["pooled"]["dom_model.txt"]
    assert sizes == {"files": 6, "bytes": 12, "mean_kib": 2 / 1024, "mean_kb": 2 / 1000}
    assert readme.read_text().startswith("Keep intro") and readme.read_text().endswith("Keep rest\n")
    with (output / "evidence_categories.tsv").open() as stream:
        assert len(list(csv.DictReader(stream, delimiter="\t"))) == 1
    assert b"\r\n" not in (output / "evidence_categories.tsv").read_bytes()
    assert (figures / "evidence-loss-rates.svg").is_file()
