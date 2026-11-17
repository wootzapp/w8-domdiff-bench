"""Settings compatibility in scheduled and recorded result aggregation."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from w8bench.task_recorder.recorder_support import write_json, write_json_lines
from w8bench.verifier.run_full_comparison import main as compare_main
from w8bench.verifier.run_metrics import summarize
from w8bench.verifier.paired_metrics import aggregate


def compare_case(case):
    write_json_lines(case.ledger, case.rows)
    return compare_main(["--ledger", str(case.ledger), "--output", str(case.output)])


@pytest.mark.parametrize("path,value", [
    (("actor", "memory_max_chars"), 7999),
    (("stages", "completion", "max_output_tokens"), 9999),
    (("stages", "dom_model", "reasoning_effort"), "high"),
    (("stages", "inventory", "prompt_sha256"), "another-prompt"),
    (("browser_source", "protocol_sha256"), "another-protocol"),
    (("rubric_sha256",), "another-rubric"),
])
def test_every_scheduled_contract_is_checked_even_without_recordings(settings_comparison_case, path, value):
    case = settings_comparison_case
    for row in case.rows:
        row.update(technical_outcome="startup_failure", recording=str(Path(row["recording"]).parent / "absent"))
    target = case.rows[1]["effective_settings"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="effective settings differ"):
        compare_case(case)


def test_schedule_refuses_mixed_settings_versions_for_startup_placeholders(settings_comparison_case):
    case = settings_comparison_case
    for row in case.rows:
        row.update(technical_outcome="startup_failure", recording=str(Path(row["recording"]).parent / "absent"))
    case.rows[1].pop("effective_settings")
    with pytest.raises(ValueError, match="effective settings differ|missing.*settings"):
        compare_case(case)


def test_deployment_names_credentials_paths_and_endpoint_ports_do_not_change_settings(settings_comparison_case):
    case = settings_comparison_case
    row = case.rows[1]
    row["configuration"].update(image="another-tag", api_key="fictional-new-key", base_url="https://user:secret@actor.example:9000/v1")
    row["effective_settings"]["actor"]["base_url"] = row["configuration"]["base_url"]
    row["effective_settings"]["stages"]["dom_model"].update(base_url="https://judge.example:9010/v1",
        config_file="/another/config.json", api_key="fictional-key", container_name="another-container")
    recording = case.recordings[row["recording"]]
    recording["manifest"]["controls"]["base_url"] = "https://actor.example:9001/v1"
    recording["manifest"]["browser_profile_provenance"]["browser_environment"].update(CDP_PORT="9333", CHROMIUM_CDP_PORT="9334")
    assert compare_case(case) == 0


@pytest.mark.parametrize("kind", ["actor", "evaluation", "missing_actor", "missing_evaluation", "actual_browser"])
def test_recorded_contracts_and_actual_browser_labels_match_the_schedule(settings_comparison_case, kind):
    case = settings_comparison_case
    recording = case.recordings[case.rows[1]["recording"]]
    if kind == "actor":
        recording["manifest"]["effective_settings"]["memory_max_chars"] = 7999
    elif kind == "missing_actor":
        recording["manifest"].pop("effective_settings")
    elif kind == "actual_browser":
        recording["manifest"]["browser_profile_provenance"]["browser_build"]["overlay_revision"] = "another-overlay"
    else:
        source = Path(recording["source"])
        path = source.parent.parent / "evaluations/trial_0001/screenshot/custom" / recording["recording_sha256"] / "evaluation.json"
        value = json.loads(path.read_text())
        if kind == "missing_evaluation":
            value.pop("effective_settings")
        else:
            value["effective_settings"]["stages"]["dom_model"]["reasoning_effort"] = "high"
        write_json(path, value)
    with pytest.raises(ValueError, match="effective settings differ"):
        compare_case(case)


def test_no_receipt_rows_retain_the_scheduled_contract_and_denominator(settings_comparison_case):
    case = settings_comparison_case
    for row in case.rows:
        row.update(technical_outcome="startup_failure", recording=str(Path(row["recording"]).parent / "absent"))
    assert compare_case(case) == 0
    pair = json.loads((case.output / "pairs.json").read_text())[0]
    for arm in ("dom", "screenshot"):
        assert pair[arm]["scheduled_effective_settings"] == case.contract
        assert pair[arm]["actor_effective_settings"] is None
    summary = json.loads((case.output / "summary.json").read_text())
    assert summary["scheduled_attempts"] == 2


@pytest.mark.parametrize("kind", ["actor", "evaluation"])
def test_aggregation_refuses_new_and_unversioned_actual_contracts(settings_comparison_case, kind):
    case = settings_comparison_case
    for row in case.rows:
        row.pop("effective_settings")
    recording = case.recordings[case.rows[1]["recording"]]
    if kind == "actor":
        recording["manifest"].pop("effective_settings")
    else:
        source = Path(recording["source"])
        path = source.parent.parent / "evaluations/trial_0001/screenshot/custom" / recording["recording_sha256"] / "evaluation.json"
        value = json.loads(path.read_text()); value.pop("effective_settings"); write_json(path, value)
    with pytest.raises(ValueError, match="effective settings differ"):
        compare_case(case)


def test_all_unversioned_synthetic_contracts_still_aggregate(settings_comparison_case):
    case = settings_comparison_case
    for row in case.rows:
        row.pop("effective_settings")
        recording = case.recordings[row["recording"]]
        recording["manifest"].pop("effective_settings")
        source = Path(recording["source"])
        path = source.parent.parent / "evaluations/trial_0001" / row["arm"] / "custom" / recording["recording_sha256"] / "evaluation.json"
        value = json.loads(path.read_text()); value.pop("effective_settings"); write_json(path, value)
    assert compare_case(case) == 0


def test_direct_trial_aggregation_checks_effective_fields(settings_comparison_case):
    case = settings_comparison_case
    summaries = {row["arm"]: summarize(case.recordings[row["recording"]]) for row in case.rows}
    summaries["screenshot"]["actor_effective_settings"]["memory_max_chars"] = 7999
    with pytest.raises(ValueError, match="effective settings differ"):
        aggregate([{"task_id": "custom", "trial_id": "trial_0001", "shared_controls": {},
                    "both_successful": False, "successful_pair_turn_delta": None, **summaries}])


def test_different_tasks_can_have_distinct_rubrics_with_shared_policies(settings_comparison_case):
    case = settings_comparison_case
    summaries = {row["arm"]: summarize(case.recordings[row["recording"]]) for row in case.rows}
    first = {"task_id": "custom", "trial_id": "trial_0001", "shared_controls": {},
             "both_successful": False, "successful_pair_turn_delta": None, **summaries}
    other = deepcopy(first); other["task_id"] = "another-task"
    for arm in ("dom", "screenshot"):
        other[arm]["evaluation_effective_settings"]["rubric_sha256"] = "rubric-another-task"
        other[arm]["evaluation"]["rubric_sha256"] = "rubric-another-task"
    assert aggregate([first, other])["paired_tasks"] == 2


def test_identical_actual_browser_labels_still_match_the_declared_source_pin(settings_comparison_case):
    case = settings_comparison_case
    for recording in case.recordings.values():
        recording["manifest"]["browser_profile_provenance"]["browser_build"]["overlay_revision"] = "another-overlay"
    with pytest.raises(ValueError, match="effective settings differ"):
        compare_case(case)


@pytest.mark.parametrize("change", ["stage", "missing", "rubric", "browser_source", "deployment_only", None])
def test_audit_aggregation_compares_effective_stage_contracts(tmp_path, change):
    from .test_aggregate_runs import runs
    from w8bench.verifier.aggregate_runs import aggregate_runs

    roots = runs(tmp_path, k=2)
    for root in roots:
        for path in root.rglob("evidence_audit.json"):
            value = json.loads(path.read_text())
            value["effective_settings"] = {
                "schema_version": "effective-settings/v1", "rubric_sha256": value["frozen_rubric_sha256"],
                "browser_source": {"overlay_revision": "overlay-one"},
                "stages": {"inventory": {"model": "gemini-3.1-pro-preview", "prompt_sha256": "prompt-one", "base_url": "https://judge.example:443/v1"},
                           "adjudication": {"model": "gpt-6.1-sol", "max_output_tokens": None}},
            }
            write_json(path, value)
    selected = roots[1] / "task_01" / "evidence_audit.json"
    value = json.loads(selected.read_text())
    if change == "stage":
        value["effective_settings"]["stages"]["inventory"]["prompt_sha256"] = "another-prompt"
    elif change == "missing":
        value.pop("effective_settings")
    elif change == "rubric":
        value["effective_settings"]["rubric_sha256"] = "another-rubric"
    elif change == "browser_source":
        value["effective_settings"]["browser_source"]["overlay_revision"] = "another-overlay"
    elif change == "deployment_only":
        value["effective_settings"]["stages"]["inventory"].update(base_url="https://user:secret@judge.example:9011/v1",
            api_key="fictional-key", config_file="/another/config.json")
    write_json(selected, value)
    if change in {"stage", "missing", "rubric", "browser_source"}:
        with pytest.raises(ValueError, match="effective settings differ"):
            aggregate_runs(roots, expected_tasks=2, resamples=10)
    else:
        assert aggregate_runs(roots, expected_tasks=2, resamples=10)[0]["k"] == 2
