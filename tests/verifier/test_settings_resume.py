"""Evaluation resume checks effective settings before reusing judge results."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from tests.verifier.test_dry_preflights import full_evaluation, run_pair, no_network
from w8bench.verifier import completion, package_manifests, run_comparison as comparison


def evaluation_args(paths, rubric, config):
    return ["--run", str(paths["dom"]), "--rubric", str(rubric), "--judge-model", "gpt-6.1-sol",
        "--eval-config", str(config), "--execute"]


@pytest.mark.parametrize("field,value", [("reasoning_effort", "high"), ("max_tokens", 9000),
    ("base_url", "https://another.test/v1")])
def test_evaluation_resume_refuses_judge_config_drift_before_cached_stages(full_evaluation, tmp_path, monkeypatch, field, value):
    paths, rubric, calls = full_evaluation
    monkeypatch.setattr(package_manifests, "require_local_packages", lambda: {})
    config = tmp_path / "config"
    shutil.copytree(comparison.DEFAULT_CONFIG, config)
    args = evaluation_args(paths, rubric, config)
    assert comparison.main(args) == 0
    receipt = next(tmp_path.rglob("evaluation.json"))
    before = receipt.read_bytes()
    counts = {name: len(rows) for name, rows in calls.items()}
    path = config / "google_gemini3_1_pro_preview.json"
    changed = json.loads(path.read_text())
    changed["CHAT_COMPLETION_KWARGS_JSON"][field] = value
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="effective settings differ"):
        comparison.main(args)
    assert {name: len(rows) for name, rows in calls.items()} == counts
    assert receipt.read_bytes() == before


def test_evaluation_resume_accepts_identical_config_at_another_location(full_evaluation, tmp_path, monkeypatch):
    paths, rubric, calls = full_evaluation
    monkeypatch.setattr(package_manifests, "require_local_packages", lambda: {})
    first, second = tmp_path / "first-config", tmp_path / "second-config"
    shutil.copytree(comparison.DEFAULT_CONFIG, first)
    assert comparison.main(evaluation_args(paths, rubric, first)) == 0
    counts = {name: len(rows) for name, rows in calls.items()}
    shutil.copytree(first, second)
    assert comparison.main(evaluation_args(paths, rubric, second)) == 0
    assert {name: len(rows) for name, rows in calls.items()} == counts


def test_completion_refusal_resumes_without_turning_unknown_into_failure(full_evaluation, tmp_path, monkeypatch):
    paths, rubric, calls = full_evaluation
    monkeypatch.setattr(package_manifests, "require_local_packages", lambda: {})
    original = completion.ModelClient._post
    def mismatch(self, payload):
        response = original(self, payload)
        return {**response, "model": "gpt-5.2"}
    monkeypatch.setattr(completion.ModelClient, "_post", mismatch)
    args = evaluation_args(paths, rubric, comparison.DEFAULT_CONFIG)
    assert comparison.main(args) == 1
    receipt = next(tmp_path.rglob("evaluation.json"))
    first = json.loads(receipt.read_text())["stages"]["paired_completion"]
    assert first["status"] == first["verdict"] == "ungraded"
    assert first["usage"]["total_tokens"] == 70
    monkeypatch.setattr(completion.ModelClient, "_post", original)
    assert comparison.main(args) == 0
    stage = json.loads(receipt.read_text())["stages"]["paired_completion"]
    assert stage["verdict"] == "success"
    assert stage["attempt_history"][0]["verdict"] == "ungraded"
    assert stage["attempt_history"][0]["usage"]["total_tokens"] == 70


def test_audit_refusal_is_ungraded_and_has_no_directional_values(full_evaluation, tmp_path, monkeypatch):
    from w8bench.verifier import evidence_audit
    from w8bench.verifier.audit_requests import AuditValidationError
    paths, rubric, calls = full_evaluation
    monkeypatch.setattr(package_manifests, "require_local_packages", lambda: {})
    def refused(**kwargs):
        kwargs["call_records"].append({"stage": "inventory", "model": "gemini-3.1-pro-preview",
            "response_model": "other", "refusal_reason": "returned model mismatch", "usage": {"prompt_tokens": 8, "completion_tokens": 2}})
        raise AuditValidationError("inventory", [{"refusal_reason": "returned model mismatch"}], ValueError("returned model mismatch"))
    monkeypatch.setattr(evidence_audit, "run_evidence_audit", refused)
    assert comparison.main(evaluation_args(paths, rubric, comparison.DEFAULT_CONFIG)) == 1
    receipt = next(tmp_path.rglob("evaluation.json"))
    stage = json.loads(receipt.read_text())["stages"]["audit"]
    assert stage["status"] == "ungraded" and stage["reason"]
    assert "metrics" not in stage
    assert stage["calls"][0]["usage"]["prompt_tokens"] == 8
