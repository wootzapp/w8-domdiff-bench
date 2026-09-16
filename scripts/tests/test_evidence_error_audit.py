from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.evidence_error_audit import (
    CLASSIFICATIONS,
    apply_reviews,
    calculate_metrics,
    classify,
    extract_run,
    review_template,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _result(*, dom: bool, final_points: float) -> dict:
    state_key = "dom_model_state_idx" if dom else "screenshot_idx"
    evidence_key = "dom_model_evidence" if dom else "screenshot_evidence"
    evidence = "DOM says Saved" if dom else "Screenshot says no readable value"
    return {
        "task_id": "task-fixture",
        "rubric_sha256": "rubric-hash",
        "intermediate_mm_rubric_steps": {
            "step2_relevance_scores": {
                ("dom_state_0" if dom else "screenshot_0"): {"0": 2, state_key: 0},
                ("dom_state_1" if dom else "screenshot_1"): {"0": 9, state_key: 1},
            },
            ("step3_grouped_dom_states" if dom else "step3_grouped_screenshots"): {"0": [1]},
            "step4_evidence_by_criterion": {
                "0": [
                    {
                        evidence_key: evidence,
                        "criterion_analysis": (
                            "EVIDENCE_STATUS: SUPPORTED" if dom else "The value cannot be verified"
                        ),
                        "discrepancies": "none" if dom else "value unreadable",
                        "environment_issues_confirmed": False,
                        state_key: 1,
                    }
                ]
            },
            "step6_rescoring_summary": [
                {
                    "criterion": "The saved value is visible",
                    "earned_points": 0,
                    "post_image_earned_points": final_points,
                    "max_points": 2,
                    "justification": "action-only justification",
                    "applicable_evidence": evidence,
                    "post_image_justification": f"final justification {evidence}",
                    "reality_notes": f"reality {evidence}",
                }
            ],
        },
    }


@pytest.fixture
def completed_run(tmp_path: Path) -> Path:
    run = tmp_path / "results" / "task1" / "run-1"
    _write(run / "microsoft_verifier" / "result.json", _result(dom=False, final_points=0))
    _write(run / "dom_model" / "result.json", _result(dom=True, final_points=2))
    screenshot_dir = run / "_inputs" / "screenshot"
    dom_dir = run / "_inputs" / "dom_model"
    screenshot_dir.mkdir(parents=True)
    dom_dir.mkdir(parents=True)
    (screenshot_dir / "screenshot0.png").write_bytes(b"zero")
    (screenshot_dir / "screenshot1.png").write_bytes(b"one")
    (screenshot_dir / "screenshot_1.png").symlink_to("screenshot0.png")
    (dom_dir / "dom_model0.txt").write_text("initial", encoding="utf-8")
    (dom_dir / "dom_model1.txt").write_text("Status: Saved", encoding="utf-8")
    return run


def test_extracts_existing_fields_verbatim_and_flags_disagreement(completed_run: Path):
    audit = extract_run(completed_run)
    row = audit["criteria"][0]
    assert audit["task_id"] == "task-fixture"
    assert audit["rubric_sha256"] == "rubric-hash"
    assert [item["index"] for item in audit["source_inventory"]["screenshot"]] == [0, 1]
    assert [item["index"] for item in audit["source_inventory"]["dom_model"]] == [0, 1]
    assert row["screenshot"]["verifier_evidence"] == "Screenshot says no readable value"
    assert row["dom_model"]["verifier_evidence"] == "DOM says Saved"
    assert row["screenshot"]["selected_indices"] == [1]
    assert row["dom_model"]["selected_indices"] == [1]
    assert row["screenshot"]["evidence_analyses"][0]["criterion_analysis"] == "The value cannot be verified"
    assert row["dom_model"]["evidence_analyses"][0]["criterion_analysis"] == "EVIDENCE_STATUS: SUPPORTED"
    assert row["screenshot"]["action_only_points"] == 0
    assert row["dom_model"]["final_points"] == 2
    assert row["disagreement_flag"] is True
    assert "final_criterion_score_mismatch" in row["disagreement_reasons"]
    assert row["classification"] is None


def test_review_template_contains_only_flagged_rows(completed_run: Path):
    audit = extract_run(completed_run)
    template = review_template(audit)
    assert len(template["reviews"]) == 1
    assert template["reviews"][0]["review_status"] == "pending"
    assert template["reviews"][0]["screenshot"]["evidence_available"] is None


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((True, True, True, True), "BOTH_CAUGHT"),
        ((True, False, True, True), "SCREENSHOT_MISSED_DOM_CAUGHT"),
        ((True, True, True, False), "DOM_MISSED_SCREENSHOT_CAUGHT"),
        ((True, False, True, False), "BOTH_MISSED"),
        ((False, False, True, True), "SCREENSHOT_EVIDENCE_MISSING"),
        ((True, True, False, False), "DOM_EVIDENCE_MISSING"),
    ],
)
def test_exact_six_classifications(values, expected):
    assert classify(
        screenshot_available=values[0],
        screenshot_caught=values[1],
        dom_available=values[2],
        dom_caught=values[3],
    ) == expected
    assert expected in CLASSIFICATIONS


def test_missing_evidence_cannot_be_marked_caught():
    with pytest.raises(ValueError, match="cannot be caught"):
        classify(
            screenshot_available=False,
            screenshot_caught=True,
            dom_available=True,
            dom_caught=True,
        )


def test_confirmed_review_applies_classification(completed_run: Path):
    audit = extract_run(completed_run)
    review = review_template(audit)
    decision = review["reviews"][0]
    decision["review_status"] = "confirmed"
    decision["screenshot"] = {
        "evidence_available": True,
        "caught_correctly": False,
        "review_note": "Visible in screenshot1.png but missed.",
    }
    decision["dom_model"] = {
        "evidence_available": True,
        "caught_correctly": True,
        "review_note": "Present and caught in dom_model1.txt.",
    }
    reviewed = apply_reviews(audit, review)
    row = reviewed["criteria"][0]
    assert row["classification"] == "SCREENSHOT_MISSED_DOM_CAUGHT"
    assert row["manual_review_status"] == "confirmed"
    assert row["screenshot"]["manual_review"]["review_note"].startswith("Visible")


def test_recovery_metrics_use_only_confirmed_miss_classes(completed_run: Path):
    base = extract_run(completed_run)
    row = base["criteria"][0]
    rows = []
    for classification in (
        "SCREENSHOT_MISSED_DOM_CAUGHT",
        "SCREENSHOT_MISSED_DOM_CAUGHT",
        "DOM_MISSED_SCREENSHOT_CAUGHT",
        "BOTH_MISSED",
        "SCREENSHOT_EVIDENCE_MISSING",
        "DOM_EVIDENCE_MISSING",
        None,
    ):
        item = deepcopy(row)
        item["classification"] = classification
        rows.append(item)
    base["criteria"] = rows
    metrics = calculate_metrics(base)
    assert metrics["dom_recovery_of_confirmed_screenshot_misses"] == {
        "numerator": 2,
        "denominator": 3,
        "rate": 2 / 3,
        "percentage": 66.67,
    }
    assert metrics["screenshot_recovery_of_confirmed_dom_misses"] == {
        "numerator": 1,
        "denominator": 2,
        "rate": 0.5,
        "percentage": 50.0,
    }
    assert metrics["pending_or_unreviewed_count"] == 1


def test_pair_must_have_same_rubric(completed_run: Path):
    dom_path = completed_run / "dom_model" / "result.json"
    dom = json.loads(dom_path.read_text(encoding="utf-8"))
    dom["rubric_sha256"] = "different"
    _write(dom_path, dom)
    with pytest.raises(ValueError, match="rubric_sha256"):
        extract_run(completed_run)


def test_audit_module_has_no_llm_or_verifier_imports():
    source = Path(__file__).parents[1] / "evidence_error_audit.py"
    text = source.read_text(encoding="utf-8")
    assert "openai" not in text.casefold()
    imported: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "microsoft_verifier" not in imported
    assert "dom_model" not in imported
