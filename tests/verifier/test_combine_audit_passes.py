from copy import deepcopy
import csv
import json
from pathlib import Path

import pytest

from w8bench.verifier import combine_audit_passes as combine
from w8bench.verifier import evidence_audit as audit
from w8bench.verifier.common import canonical_sha256
from .test_automated_evidence_audit import _audit, _row


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sets(tmp_path, k=3, counts=(2, 2), flagged=None):
    flagged = flagged or {}
    roots = []
    for pass_index in range(k):
        root = tmp_path / f"pass{pass_index + 1}"
        roots.append(root)
        for task_index, count in enumerate(counts):
            task_id = f"task{task_index + 1}"
            rows = []
            for index in range(count):
                values = {key: (pass_index, task_index, index, key) in flagged for key in combine.FLAGS}
                row = _row(screen_loss=values[combine.FLAGS[0]], dom_loss=values[combine.FLAGS[1]],
                           screen_caught=not values[combine.FLAGS[2]], dom_caught=not values[combine.FLAGS[3]])
                row.update(criterion_index=index, criterion=f"Criterion {index}", description="Evidence requirement",
                           max_points=1, adjudication={key: {"confirmed": value} for key, value in values.items()})
                rows.append(row)
            value = _audit(task_id, rows)
            value["shared_trajectory"] = {"task_id": task_id, "initial_url": "https://example.test"}
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
            _write(root / task_id / "evidence_audit.json", value)
    return roots


def _change(roots, modify, pass_index=1, task_id="task1"):
    path = roots[pass_index] / task_id / "evidence_audit.json"
    value = json.loads(path.read_text())
    modify(value)
    _write(path, value)


def test_majority_votes_include_minority_flags_and_misses_in_review(tmp_path):
    flagged = {(0, 0, 0, combine.FLAGS[0]), (1, 0, 0, combine.FLAGS[0]),
               (2, 1, 1, combine.FLAGS[1]), (0, 0, 1, combine.FLAGS[2])}
    roots = _sets(tmp_path, flagged=flagged)
    result, blind, review = combine.combine_passes(roots, expected_tasks=2)
    first = result["tasks"][0]["criteria"][0]["votes"][combine.FLAGS[0]]
    assert first == {"flagged_passes": 2, "passes": 3, "pass_flags": [True, True, False], "majority": True, "tie": False}
    assert result["tasks"][1]["criteria"][1]["votes"][combine.FLAGS[1]]["majority"] is False
    assert result["majority_vote_totals"]["screenshot_evidence_loss"]["count"] == 1
    assert result["majority_vote_totals"]["dom_model_evidence_loss"]["count"] == 0
    assert result["majority_vote_totals"]["relative_reduction"]["estimate"] == 1
    assert result["human_review"]["flagged_criteria"] == 3
    assert result["human_review"]["sampled_unflagged"] == 1
    assert len(review) == 4 and result["human_review"]["review_completed"] is False
    assert len(blind) == 4
    assert result["human_review"]["source_loss_flagged_rows"] == 2
    assert result["human_review"]["verifier_miss_only_rows"] == 1
    assert result["human_review"]["sampled_unflagged_rows"] == 1
    agreement = result["pass_to_pass_agreement"][combine.FLAGS[0]]
    assert agreement["agreements"] == 10 and agreement["comparisons"] == 12
    assert agreement["rate"] == pytest.approx(10 / 12)
    assert agreement["unanimous_criteria"] == 3


def test_sample_is_seeded_has_75_unflagged_and_keeps_all_flagged(tmp_path):
    flagged = {(0, 0, 0, combine.FLAGS[0]), (1, 1, 1, combine.FLAGS[1])}
    roots = _sets(tmp_path, counts=(50, 50), flagged=flagged)
    first, blind, review = combine.combine_passes(roots, sample_seed=42)
    second, repeated_blind, repeated = combine.combine_passes(roots, sample_seed=42)
    _, _, changed = combine.combine_passes(roots, sample_seed=43)
    assert review == repeated and review != changed
    assert blind == repeated_blind
    assert len(review) == 77
    assert sum(row["selection"] == "seeded_unflagged_sample" for row in review) == 75
    assert {(row["task_id"], row["criterion_index"]) for row in review if row["selection"] == "flagged_in_any_pass"} == {("task1", 0), ("task2", 1)}
    assert first["human_review"] == second["human_review"]
    assert first["human_review"]["sample_shortfall"] == 0


def test_even_pass_ties_are_explicit_and_not_counted_as_false(tmp_path):
    roots = _sets(tmp_path, k=2, flagged={(0, 0, 0, combine.FLAGS[0])})
    result, _, review = combine.combine_passes(roots)
    vote = result["tasks"][0]["criteria"][0]["votes"][combine.FLAGS[0]]
    assert vote["tie"] is True and vote["majority"] is None
    assert result["majority_vote_totals"]["status"] == "unresolved_ties"
    assert result["majority_vote_totals"]["screenshot_evidence_loss"] is None
    assert next(row for row in review if row["task_id"] == "task1" and row["criterion_index"] == 0)["screenshot_evidence_loss_majority"] is None


def test_single_pass_agreement_is_undefined_not_perfect(tmp_path):
    result, _, _ = combine.combine_passes(_sets(tmp_path, k=1, counts=(1,)))
    assert result["pass_to_pass_agreement"][combine.FLAGS[0]]["rate"] is None
    assert result["majority_vote_totals"]["screenshot_evidence_loss"]["ci95"] is None


@pytest.mark.parametrize("field", combine.PROTOCOL_FIELDS)
def test_mixed_protocol_is_rejected(tmp_path, field):
    roots = _sets(tmp_path)
    _change(roots, lambda value: value.__setitem__(field, value[field] + "-different"))
    with pytest.raises(ValueError, match="protocol|schema"):
        combine.combine_passes(roots)


def test_changed_settings_or_unrecorded_settings_are_rejected(tmp_path):
    roots = _sets(tmp_path)
    def alter(value):
        setting = value["generation_settings"]["adjudication"]
        setting["requested"]["media_resolution"] = "MEDIA_RESOLUTION_LOW"
        setting["actual"] = [deepcopy(setting["requested"])]
    _change(roots, alter)
    with pytest.raises(ValueError, match="protocol mismatch"):
        combine.combine_passes(roots)
    _change(roots, lambda value: value["generation_settings"]["adjudication"].__setitem__("actual", []))
    with pytest.raises(ValueError, match="Actual generation settings"):
        combine.combine_passes(roots)


@pytest.mark.parametrize("kind", ["rubric", "criteria", "inputs", "shared", "boolean", "adjudication", "indices"])
def test_frozen_input_or_label_drift_is_rejected(tmp_path, kind):
    roots = _sets(tmp_path)
    def alter(value):
        if kind == "rubric":
            value["frozen_rubric_sha256"] = "5" * 64
            value["input_fingerprints"]["frozen_rubric"] = "5" * 64
        elif kind == "criteria":
            value["criteria"][0]["criterion"] = "Changed criterion"
        elif kind == "inputs":
            value["input_fingerprints"]["dom_sources"]["dom_model0.txt"] = "6" * 64
        elif kind == "shared":
            value["shared_trajectory"]["initial_url"] = "https://different.test"
        elif kind == "boolean":
            value["criteria"][0]["screenshot_evidence_loss"] = 1
        elif kind == "adjudication":
            value["criteria"][0]["adjudication"][combine.FLAGS[0]]["confirmed"] = True
        elif kind == "indices":
            value["criteria"][1]["criterion_index"] = 0
    _change(roots, alter)
    with pytest.raises(ValueError):
        combine.combine_passes(roots)


def test_missing_and_duplicate_tasks_or_repeated_passes_are_rejected(tmp_path):
    roots = _sets(tmp_path)
    with pytest.raises(ValueError, match="distinct"):
        combine.combine_passes([roots[0], roots[0]])
    with pytest.raises(ValueError, match="task count"):
        combine.combine_passes(roots, expected_tasks=3)
    _change(roots, lambda value: value.__setitem__("task_id", "task3"))
    with pytest.raises(ValueError, match="identical complete task set"):
        combine.combine_passes(roots)
    _change(roots, lambda value: value.__setitem__("task_id", "task2"))
    with pytest.raises(ValueError, match="duplicate task"):
        combine.combine_passes(roots)


def test_bootstrap_matches_existing_task_cluster_implementation(tmp_path):
    flagged = {(p, 0, 0, combine.FLAGS[0]) for p in range(3)}
    flagged |= {(p, 1, 0, combine.FLAGS[1]) for p in range(3)}
    result, _, _ = combine.combine_passes(_sets(tmp_path, counts=(1, 3), flagged=flagged))
    existing = audit.aggregate_audits([
        _audit("task1", [_row(screen_loss=True)]),
        _audit("task2", [_row(dom_loss=True), _row(), _row()]),
    ])["confidence_intervals"]
    for key in (*combine.FLAGS[:2], "screenshot_minus_dom_loss_rate", "relative_reduction"):
        assert result["majority_vote_totals"][key]["ci95"] == existing[key]["ci95"]
        assert result["majority_vote_totals"][key]["estimate"] == existing[key]["estimate"]
    ratio = result["majority_vote_totals"]["relative_reduction"]
    assert ratio["undefined_resamples"] == existing["relative_reduction"]["undefined_resamples"]
    assert ratio["undefined_resamples"] > 0


def test_zero_screenshot_losses_keep_all_undefined_samples(tmp_path):
    result, _, _ = combine.combine_passes(_sets(tmp_path))
    ratio = result["majority_vote_totals"]["relative_reduction"]
    assert ratio["estimate"] is None and ratio["ci95"] is None
    assert ratio["undefined_resamples"] == 20000


def test_cli_writes_json_and_csv_without_changing_inputs(tmp_path):
    roots = _sets(tmp_path, counts=(40, 40), flagged={(0, 0, 0, combine.FLAGS[1])})
    before = {path: path.read_bytes() for root in roots for path in root.rglob("*.json")}
    output = tmp_path / "combined"
    args = [*[str(root) for root in roots], "--output-dir", str(output), "--expected-tasks", "2"]
    assert combine.main(args) == 0
    result = json.loads((output / "combined_audit.json").read_text())
    with (output / "review_blind.csv").open(newline="") as stream:
        review = list(csv.DictReader(stream))
    with (output / "review_key.csv").open(newline="") as stream:
        key = list(csv.DictReader(stream))
    assert len(review) == 76 and result["human_review"]["total_rows"] == 76
    assert not (output / "human_review.csv").exists()
    assert len(key) == len(review)
    assert [(row["task_id"], row["criterion_index"]) for row in review] == [(row["task_id"], row["criterion_index"]) for row in key]
    assert set(review[0]) == {"task_id", "task_alias", "criterion_index", "criterion", "screenshots", "dom_states",
                             "action_history", "review_screenshot_loss", "review_dom_loss", "review_screenshot_miss",
                             "review_dom_miss", "review_notes"}
    assert before == {path: path.read_bytes() for path in before}
    saved = (output / "combined_audit.json").read_bytes()
    with pytest.raises(SystemExit):
        combine.main(args)
    assert (output / "combined_audit.json").read_bytes() == saved


def test_blind_rows_have_evidence_and_blank_reviews_but_no_votes(tmp_path):
    roots = _sets(tmp_path, counts=(45, 45), flagged={(0, 0, 0, combine.FLAGS[0])})
    result, blind, key = combine.combine_passes(roots)
    _, repeated, repeated_key = combine.combine_passes(roots)
    _, shuffled, shuffled_key = combine.combine_passes(roots, review_order_seed=2)
    assert blind == repeated and key == repeated_key
    assert blind != shuffled
    identities = lambda rows: {(row["task_id"], row["criterion_index"]) for row in rows}
    assert identities(blind) == identities(key) == identities(shuffled) == identities(shuffled_key)
    assert len(identities(blind)) == len(blind)
    assert result["human_review"]["review_order_seed"] == 1
    for row in blind:
        assert not any("passes" in field or "majority" in field or "selection" in field for field in row)
        assert all(row[field] == "" for field in row if field.startswith("review_"))
        assert json.loads(row["screenshots"])[0].endswith("screenshot0.png")
        assert json.loads(row["dom_states"])[0].endswith("dom_model0.txt")
        assert set(json.loads(row["action_history"])) == {"screenshot", "dom_model"}


def test_workload_is_disjoint_when_criteria_have_several_flags(tmp_path):
    flagged = {(0, 0, 0, key) for key in combine.FLAGS}
    flagged |= {(1, 0, 1, combine.FLAGS[2]), (2, 0, 1, combine.FLAGS[3])}
    result, blind, _ = combine.combine_passes(_sets(tmp_path, flagged=flagged))
    workload = result["human_review"]
    assert workload["source_loss_flagged_rows"] == 1
    assert workload["verifier_miss_only_rows"] == 1
    assert workload["sampled_unflagged_rows"] == 2
    assert sum(workload[key] for key in ("source_loss_flagged_rows", "verifier_miss_only_rows", "sampled_unflagged_rows")) == len(blind)


def test_returned_model_drift_is_reported_not_rejected(tmp_path):
    roots = _sets(tmp_path)
    result, _, _ = combine.combine_passes(roots)
    assert result["response_model_drift"] is False
    assert result["response_models"] == {"inventory": ["inventory-response"], "adjudication": ["adjudication-response"]}
    _change(roots, lambda value: value["calls"].extend([
        {"stage": "adjudication", "response_model": "adjudication-changed"},
        {"stage": "inventory", "response_model": "inventory-changed"},
        {"stage": "adjudication", "response_model": None},
    ]))
    changed, _, _ = combine.combine_passes(roots)
    assert changed["response_model_drift"] is True
    assert changed["response_models"]["inventory"] == ["inventory-changed", "inventory-response"]
    assert changed["response_models"]["adjudication"] == ["adjudication-changed", "adjudication-response"]


def test_review_bundle_is_self_contained_and_uses_relative_paths(tmp_path):
    roots = _sets(tmp_path, counts=(2, 2))
    output = tmp_path / "bundled"
    assert combine.main([*[str(root) for root in roots], "--output-dir", str(output), "--review-bundle"]) == 0
    with (output / "review_blind.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        paths = json.loads(row["screenshots"]) + json.loads(row["dom_states"]) + list(json.loads(row["action_history"]).values())
        for path in paths:
            assert not Path(path).is_absolute()
            assert Path(path).parts[:2] == ("review_bundle", row["task_id"])
            assert (output / path).is_file()
        assert (output / json.loads(row["screenshots"])[0]).read_bytes() == b"screenshot0.png"
    assert len(list((output / "review_bundle").glob("*"))) == 2
