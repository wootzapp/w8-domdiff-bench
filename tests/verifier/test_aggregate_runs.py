import csv
import json
from pathlib import Path

import pytest

from w8bench.verifier import aggregate_runs as aggregate
from copy import deepcopy
from w8bench.verifier import evidence_audit as audit
from w8bench.verifier.common import canonical_sha256
from .test_automated_evidence_audit import _audit, _row


def runs(tmp_path, *, k, flagged=None):
    counts = (2, 2)
    tmp_path = tmp_path / "evaluations"
    flagged = flagged or {}
    roots = []
    for pass_index in range(k):
        root = tmp_path / f"pass{pass_index + 1}"
        roots.append(root)
        for task_index, count in enumerate(counts):
            task_id = f"task_{task_index + 1:02d}"
            rows = []
            for index in range(count):
                values = {key: (pass_index, task_index, index, key) in flagged for key in (*aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")}
                row = _row(screen_loss=values[(*aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")[0]], dom_loss=values[(*aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")[1]],
                           screen_caught=not values[(*aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")[2]], dom_caught=not values[(*aggregate.LOSS_FLAGS, "screenshot_verifier_miss", "dom_model_verifier_miss")[3]])
                row.update(criterion_index=index, criterion=f"Criterion {index}", description="Evidence requirement",
                           max_points=1, adjudication={key: {"confirmed": value, "explanation": "Saved evidence requirement."} for key, value in values.items()})
                rows.append(row)
            value = _audit(task_id, rows)
            value["task_alias"] = task_id
            value["shared_trajectory"] = {"task_id": task_id, "initial_url": "https://example.test", "recording_id": root.name}
            value["frozen_rubric_sha256"] = canonical_sha256([
                {key: row[key] for key in ("criterion_index", "criterion", "description", "max_points")}
                for row in rows])
            value["input_fingerprints"] = {
                "frozen_rubric": value["frozen_rubric_sha256"],
                "shared_trajectory": canonical_sha256(value["shared_trajectory"]),
                "screenshot_verifier_result": "1" * 64, "dom_verifier_result": "2" * 64,
                "screenshot_sources": {"screenshot0.png": "3" * 64},
                "dom_sources": {"dom_model0.txt": "4" * 64},
            }
            value["generation_settings"] = {
                stage: {"provider": provider, "api_version": version, "requested": deepcopy(settings),
                        "actual": [deepcopy(settings)], "injected_complete": False}
                for stage, provider, version, settings in (
                    ("inventory", "openai", None, audit.OPENAI_GENERATION_SETTINGS),
                    ("adjudication", "google", "v1beta", audit.GEMINI_GENERATION_SETTINGS))
            }
            evidence = tmp_path / "evidence" / task_id
            evidence.mkdir(parents=True, exist_ok=True)
            for filename in ("screenshot0.png", "dom_model0.txt", "ss-web_surfer.log", "dom-web_surfer.log"):
                (evidence / filename).write_bytes(filename.encode())
            value["evidence_paths"] = {
                "screenshots": [str(evidence / "screenshot0.png")],
                "dom_states": [str(evidence / "dom_model0.txt")],
                "action_history": {"screenshot": str(evidence / "ss-web_surfer.log"),
                                   "dom_model": str(evidence / "dom-web_surfer.log")},
            }
            value["calls"] = [
                {"stage": "inventory", "response_model": "inventory-response"},
                {"stage": "adjudication", "response_model": "adjudication-response"},
            ]
            path = root / task_id / "evidence_audit.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
    return roots

@pytest.mark.parametrize("k", [1, 2, 5])
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
    roots = runs(tmp_path, k=2)
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
    roots = runs(tmp_path, k=2, flagged={(0, 1, 0, aggregate.LOSS_FLAGS[0])})
    with pytest.raises(ValueError, match="distinct"):
        aggregate.aggregate_runs([roots[0], roots[0]], expected_tasks=2)
    with pytest.raises(FileNotFoundError):
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
                    "audit": None if index == 1 and alias == "task_02" else
                             f"evaluations/{root.name}/{alias}/evidence_audit.json",
                    "unscored_reason": "no_captured_state" if index == 1 and alias == "task_02" else None}
                   for alias, digest in reference.items()]
        (manifests / f"{root.name}.json").write_text(json.dumps({"run_name": root.name, "entries": entries}))
    value, categories = aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    assert value["catalog_tasks"] == 2 and value["tasks_per_run"] == 1
    assert value["criteria_per_run"] == 2
    assert value["coverage"]["outside_common_panel"] == ["task_02"]
    assert [run["available_tasks"] for run in value["per_run"]] == [2, 1]
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
    assert first["statuses"]["relative_reduction"] == "degenerate"
    assert first["undefined_relative_reduction_resamples"] > 0
    zero = aggregate.hierarchical_intervals([[(3, 0, 0)]], resamples=100)
    assert zero["relative_reduction"] is None
    assert zero["undefined_relative_reduction_resamples"] == 0
    assert zero["statuses"]["relative_reduction"] == "insufficient_tasks"
    assert zero["performed_resamples"] == 0


def test_recording_provenance_and_returned_models_are_checked(tmp_path):
    roots = runs(tmp_path, k=2)
    original_path = roots[0] / "task_01/evidence_audit.json"
    path = roots[1] / "task_01/evidence_audit.json"
    original = json.loads(original_path.read_text())
    value = json.loads(path.read_text())
    value["input_fingerprints"] = original["input_fingerprints"]
    value["shared_trajectory"] = original["shared_trajectory"]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="distinct recording provenance"):
        aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    for index, root in enumerate(roots[:2], 1):
        recording = tmp_path / "recordings" / root.name / "task_01"
        recording.mkdir(parents=True)
        (recording / "manifest.json").write_text(json.dumps(
            {"task_id": "task_01", "started_at": f"2026-01-0{index}T00:00:00Z"}))
    aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    value["calls"][0]["response_model"] = "different-returned-model"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Returned model versions differ"):
        aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    value["calls"][0]["response_model"] = original["calls"][0]["response_model"]
    path.write_text(json.dumps(value))
    first = tmp_path / "recordings" / roots[0].name / "task_01/manifest.json"
    second = tmp_path / "recordings" / roots[1].name / "task_01/manifest.json"
    second.write_bytes(first.read_bytes())
    with pytest.raises(ValueError, match="Recording identity reused"):
        aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)


def test_run_manifest_selects_the_audit_batch(tmp_path):
    roots = runs(tmp_path, k=2)
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    for root in roots:
        entries = []
        for alias in ("task_01", "task_02"):
            path = root / alias / "evidence_audit.json"
            value = json.loads(path.read_text())
            entries.append({"task_alias": alias, "evaluation_status": "complete",
                            "frozen_rubric_sha256": value["frozen_rubric_sha256"],
                            "audit": path.relative_to(tmp_path).as_posix()})
        (manifests / f"{root.name}.json").write_text(json.dumps(
            {"run_name": root.name, "entries": entries}))
    duplicate = roots[0] / "task_01/batch_02/evidence_audit.json"
    duplicate.parent.mkdir()
    duplicate.write_bytes((roots[0] / "task_01/evidence_audit.json").read_bytes())
    result, _ = aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)
    assert result["tasks_per_run"] == 2
    (manifests / f"{roots[0].name}.json").unlink()
    with pytest.raises(ValueError, match="duplicate task alias"):
        aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)


@pytest.mark.parametrize("field", ["input_fingerprints", "calls"])
def test_missing_source_or_model_provenance_is_rejected(tmp_path, field):
    roots = runs(tmp_path, k=2)
    path = roots[0] / "task_01/evidence_audit.json"
    value = json.loads(path.read_text())
    value.pop(field)
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="fingerprints missing|returned-model provenance"):
        aggregate.aggregate_runs(roots, expected_tasks=2, resamples=100)


def test_outputs_and_figures_are_written_without_model_calls(tmp_path):
    roots = runs(tmp_path, k=2, flagged={(0, 0, 0, aggregate.LOSS_FLAGS[0])})
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
    assert result["k"] == 2
    assert result["unclassified_losses"] == 1
    assert result["exploratory_subset"]["pre_specified"] is False
    assert result["exploratory_subset"]["criteria_per_run"] == 2
    assert result["recorded_file_sizes"]["recordings"] == 4
    assert all(value == {"success": 2} for value in result["recorded_outcomes"].values())
    sizes = result["recorded_file_sizes"]["pooled"]["dom_model.txt"]
    assert sizes == {"files": 4, "bytes": 6, "mean_kib": 1.5 / 1024, "mean_kb": 1.5 / 1000}
    assert readme.read_text().startswith("Keep intro") and readme.read_text().endswith("Keep rest\n")
    with (output / "evidence_categories.tsv").open() as stream:
        assert len(list(csv.DictReader(stream, delimiter="\t"))) == 1
    assert b"\r\n" not in (output / "evidence_categories.tsv").read_bytes()
    assert (figures / "evidence-loss-rates.svg").is_file()
    for svg in figures.glob("*.svg"):
        assert svg.with_suffix(".png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_generic_task_names_and_current_trial_arm_receipts(tmp_path):
    import hashlib
    original = runs(tmp_path, k=2)
    selected = []
    for trial, source in enumerate(original, 1):
        root = tmp_path / "current" / f"trial_{trial:04d}" / "dom"
        selected.append(root)
        for old_alias, alias in (("task_01", "news-medium-a"), ("task_02", "catalog_x")):
            value = json.loads((source / old_alias / "evidence_audit.json").read_text())
            value["task_alias"] = value["task_id"] = alias
            recording = hashlib.sha256(f"{trial}:{alias}".encode()).hexdigest()
            value["shared_trajectory"].update(task_id=alias, evaluation_context={
                "actor_arm": "dom", "trial_id": f"trial_{trial:04d}", "task_id": alias, "recording_sha256": recording})
            value["input_fingerprints"]["shared_trajectory"] = aggregate.canonical_sha256(value["shared_trajectory"])
            folder = root / alias / recording
            folder.mkdir(parents=True)
            path = folder / "evidence_audit.json"
            path.write_text(json.dumps(value))
            (folder / "evaluation.json").write_text(json.dumps({"trial_id": f"trial_{trial:04d}", "actor_arm": "dom",
                "task_id": alias, "rubric_sha256": value["frozen_rubric_sha256"], "recording_sha256": recording,
                "coverage": {"states": [{"state": 1}]}, "stages": {"audit": {"status": "complete",
                    "result_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}}))
    summary, _ = aggregate.aggregate_runs(selected, expected_tasks=2, resamples=100)
    assert summary["k"] == 2 and summary["actor_arm"] == "dom"
    assert summary["run_names"] == ["trial_0001", "trial_0002"]
    assert summary["coverage"]["compared_tasks"] == ["catalog_x", "news-medium-a"]
    # A declared ungraded task remains visible without being a zero-loss audit.
    path = next(selected[1].rglob("news-medium-a/*/evaluation.json"))
    value = json.loads(path.read_text())
    value["stages"]["audit"] = {"status": "not_eligible", "reason": "no_eligible_paired_states"}
    path.write_text(json.dumps(value)); (path.parent / "evidence_audit.json").unlink()
    summary, _ = aggregate.aggregate_runs(selected, expected_tasks=2, resamples=100)
    assert summary["tasks_per_run"] == 1
    assert summary["coverage"]["unscored_tasks"]["trial_0002"] == {"news-medium-a": "no_eligible_paired_states"}
    # Different actor policies may not be pooled into the same within-run audit mean.
    for path in selected[1].rglob("evaluation.json"):
        value = json.loads(path.read_text()); value["actor_arm"] = "screenshot"; path.write_text(json.dumps(value))
        audit_path = path.parent / "evidence_audit.json"
        if audit_path.is_file():
            value = json.loads(audit_path.read_text()); value["shared_trajectory"]["evaluation_context"]["actor_arm"] = "screenshot"
            value["input_fingerprints"]["shared_trajectory"] = aggregate.canonical_sha256(value["shared_trajectory"])
            audit_path.write_text(json.dumps(value))
            evaluation = json.loads(path.read_text()); evaluation["stages"]["audit"]["result_sha256"] = hashlib.sha256(audit_path.read_bytes()).hexdigest(); path.write_text(json.dumps(evaluation))
    with pytest.raises(ValueError, match="different actor arms"):
        aggregate.aggregate_runs(selected, expected_tasks=2, resamples=100)
