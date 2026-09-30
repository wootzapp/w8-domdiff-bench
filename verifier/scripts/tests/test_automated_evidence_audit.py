import json

import pytest

from scripts.common import canonical_sha256
from scripts.evidence_audit import (
    ADJUDICATION_SYSTEM_PROMPT,
    AuditValidationError,
    _resolve_source_name,
    aggregate_audits,
    calculate_metrics,
    classification,
    ordered_audit_screenshots,
    run_evidence_audit,
    validate_audit_response,
)


def _modality(coverage="COMPLETE", caught=True):
    return {"coverage": coverage, "verifier_caught": caught}


def _row(*, screen_loss=False, dom_loss=False, screen_caught=True, dom_caught=True):
    return {
        "screenshot": _modality("PARTIAL" if screen_loss else "COMPLETE", screen_caught),
        "dom_model": _modality("PARTIAL" if dom_loss else "COMPLETE", dom_caught),
        "screenshot_evidence_loss": screen_loss,
        "dom_model_evidence_loss": dom_loss,
    }


def _source_decision(modality, *, coverage="COMPLETE", caught=True):
    if coverage == "ABSENT":
        return {
            "coverage": coverage,
            "available_evidence": [],
            "missing_required_evidence": ["criterion evidence"],
            "verifier_caught": caught,
            "citations": [],
        }
    return {
        "coverage": coverage,
        "available_evidence": ["Saved"],
        "missing_required_evidence": [] if coverage == "COMPLETE" else ["associated value"],
        "verifier_caught": caught,
        "citations": [{
            "source": "screenshot1.png" if modality == "screenshot" else "dom_model1.txt",
            "location": "status area" if modality == "screenshot" else "L0005-L0007",
            "quote": "Saved",
        }],
    }


def _finding(confirmed=False, *, evidence="", modality="dom_model"):
    if not confirmed:
        return {
            "confirmed": False,
            "decisive_evidence": "",
            "citations": [],
            "explanation": "The strict confirmation gates are not met.",
        }
    return {
        "confirmed": True,
        "decisive_evidence": evidence or "Saved",
        "citations": [{
            "source": "screenshot1.png" if modality == "screenshot" else "dom_model1.txt",
            "location": "status area" if modality == "screenshot" else "L0005-L0007",
            "quote": evidence or "Saved",
        }],
        "explanation": "The cited decisive evidence is available and was materially missed.",
    }


def test_classifications_keep_source_loss_separate_from_verifier_misses():
    complete = _modality()
    missed = _modality(caught=False)
    partial = _modality("PARTIAL")
    assert classification(complete, complete, False, False) == "BOTH_CAUGHT"
    assert classification(missed, complete, False, False) == "SCREENSHOT_MISSED_DOM_CAUGHT"
    assert classification(complete, missed, False, False) == "DOM_MISSED_SCREENSHOT_CAUGHT"
    assert classification(missed, missed, False, False) == "BOTH_MISSED"
    assert classification(partial, complete, True, False) == "SCREENSHOT_EVIDENCE_MISSING"
    assert classification(complete, partial, False, True) == "DOM_EVIDENCE_MISSING"
    assert classification(partial, partial, True, True) == "BOTH_EVIDENCE_INCOMPLETE"


def test_adjudication_policy_keeps_url_evidence_and_ordered_state_continuity():
    assert "exact URL present in DOM but absent from screenshots" in ADJUDICATION_SYSTEM_PROMPT
    assert "branding is not a substitute for URL evidence" in ADJUDICATION_SYSTEM_PROMPT
    assert "earlier selected control or state remains evidence" in ADJUDICATION_SYSTEM_PROMPT
    assert "does not replace URL evidence" in ADJUDICATION_SYSTEM_PROMPT


def test_validation_error_receipt_preserves_invalid_model_output():
    raw = {"criteria": [{"classification": "EVIDENCE_MATCH"}]}
    error = AuditValidationError(
        "primary evidence inventory",
        [{"attempt": 1, "validation_error": "invalid schema", "raw_response": raw}],
        ValueError("invalid schema"),
    )
    assert error.receipt() == {
        "stage": "primary evidence inventory",
        "attempt_count": 1,
        "last_validation_error": "invalid schema",
        "attempts": [
            {"attempt": 1, "validation_error": "invalid schema", "raw_response": raw}
        ],
    }


def test_audit_ignores_microsoft_compatibility_screenshot_symlinks(pair_factory):
    pair = pair_factory()
    (pair["screenshot"] / "screenshot_1.png").symlink_to("screenshot0.png")
    (pair["screenshot"] / "screenshot_2.png").symlink_to("screenshot1.png")

    assert [path.name for path in ordered_audit_screenshots(pair["screenshot"])] == [
        "screenshot0.png", "screenshot1.png"
    ]


def test_citation_source_normalization_is_safe_and_unambiguous():
    screenshots = {"screenshot0.png", "screenshot1.png", "screenshot2.png"}
    dom_states = {"dom_model0.txt", "dom_model1.txt", "dom_model2.txt"}
    assert _resolve_source_name("screenshot_2.png", screenshots, "screenshot") == "screenshot2.png"
    assert _resolve_source_name("DOM-MODEL-2.TXT", dom_states, "dom_model") == "dom_model2.txt"
    with pytest.raises(ValueError, match="Ambiguous screenshot citation source"):
        _resolve_source_name("Screenshot 1", screenshots, "screenshot")
    with pytest.raises(ValueError, match="Unknown dom_model citation source"):
        _resolve_source_name("unseen-state.txt", dom_states, "dom_model")


def test_metrics_use_all_criteria_as_denominator_and_measure_recovery_separately():
    rows = [
        _row(screen_loss=True),
        _row(dom_loss=True),
        _row(screen_caught=False),
        _row(screen_caught=False, dom_caught=False),
    ]
    metrics = calculate_metrics(rows)
    assert metrics["screenshot_evidence_loss"] == {"count": 1, "denominator": 4, "rate": 0.25}
    assert metrics["dom_model_evidence_loss"] == {"count": 1, "denominator": 4, "rate": 0.25}
    assert metrics["screenshot_verifier_misses"]["count"] == 2
    assert metrics["screenshot_misses_recovered_by_dom"] == {
        "count": 1, "denominator": 2, "rate": 0.5
    }


def test_recovery_requires_equivalent_evidence_between_modalities():
    rows = [
        _row(screen_loss=True, dom_caught=False),
    ]
    metrics = calculate_metrics(rows)
    assert metrics["dom_model_verifier_misses"] == {
        "count": 1, "denominator": 1, "rate": 1.0
    }
    assert metrics["dom_misses_recovered_by_screenshot"] == {
        "count": 0, "denominator": 1, "rate": 0.0
    }


def test_run_audit_uses_inventory_and_adjudication_calls(pair_factory):
    pair = pair_factory()
    rubric_hash = canonical_sha256(json.loads(pair["rubric"].read_text())["precomputed_rubric"])
    result = {
        "task_id": pair["task"]["task_id"],
        "rubric_sha256": rubric_hash,
        "intermediate_mm_rubric_steps": {
            "step4_evidence_by_criterion": {
                "0": [{"criterion_analysis": "Saved is visible"}],
                "1": [{"criterion_analysis": "No error was identified"}],
            },
            "step6_rescoring_summary": [
                {"earned_points": 7, "post_image_earned_points": 7, "max_points": 7},
                {"earned_points": 3, "post_image_earned_points": 3, "max_points": 3},
            ],
        },
    }
    screenshot_result = pair["staged"] / "screenshot-result.json"
    dom_result = pair["staged"] / "dom-result.json"
    screenshot_result.write_text(json.dumps(result), encoding="utf-8")
    dom_result.write_text(json.dumps(result), encoding="utf-8")
    calls = []

    def fake_complete(model, messages):
        calls.append((model, messages))
        if "final evidence-loss adjudicator" in messages[0]["content"]:
            return {
                "criteria": [
                    {
                        "criterion_index": 0,
                        "screenshot_evidence_loss": _finding(),
                        "dom_model_evidence_loss": _finding(),
                        "screenshot_verifier_miss": _finding(
                            True, evidence="Saved", modality="screenshot"
                        ),
                        "dom_model_verifier_miss": _finding(),
                        "explanation": "Both sources contain Saved, but screenshot analysis missed it.",
                    },
                    {
                        "criterion_index": 1,
                        "screenshot_evidence_loss": _finding(
                            True, evidence="Error: none", modality="dom_model"
                        ),
                        "dom_model_evidence_loss": _finding(),
                        "screenshot_verifier_miss": _finding(),
                        "dom_model_verifier_miss": _finding(),
                        "explanation": "Only DOM explicitly preserves the error state.",
                    },
                ]
            }
        return {
            "criteria": [
                {
                    "criterion_index": 0,
                    "required_evidence": "Saved value",
                    "screenshot": _source_decision("screenshot", caught=False),
                    "dom_model": _source_decision("dom_model"),
                    "screenshot_evidence_loss": False,
                    "dom_model_evidence_loss": False,
                    "classification": "EVIDENCE_MATCH",
                    "explanation": "Both sources contain Saved; only the DOM verifier used it.",
                },
                {
                    "criterion_index": 1,
                    "required_evidence": "No explicit error",
                    "screenshot": _source_decision("screenshot", coverage="ABSENT"),
                    "dom_model": {
                        "coverage": "COMPLETE",
                        "available_evidence": ["Error: none"],
                        "missing_required_evidence": [],
                        "verifier_caught": True,
                        "citations": [{
                            "source": "dom_model1.txt",
                            "location": "L0007",
                            "quote": "Error: none",
                        }],
                    },
                    "screenshot_evidence_loss": True,
                    "dom_model_evidence_loss": False,
                    "explanation": "Only the DOM explicitly reports the error state.",
                },
            ]
        }

    audit = run_evidence_audit(
        screenshot_dir=pair["screenshot"],
        dom_dir=pair["dom"],
        rubric_file=pair["rubric"],
        screenshot_result=screenshot_result,
        dom_result=dom_result,
        complete=fake_complete,
    )
    assert len(calls) == 2
    content = calls[0][1][1]["content"]
    text_parts = [part.get("text", "") for part in content]
    assert any("SCREENSHOT SOURCE FILE: screenshot0.png" in text for text in text_parts)
    assert any("SCREENSHOT SOURCE FILE: screenshot1.png" in text for text in text_parts)
    assert any("DOM SOURCE FILE: dom_model0.txt" in text for text in text_parts)
    assert any("DOM SOURCE FILE: dom_model1.txt" in text for text in text_parts)
    assert any("SHARED REPRESENTATION-NEUTRAL TRAJECTORY" in text for text in text_parts)
    assert audit["criteria"][0]["classification"] == "SCREENSHOT_MISSED_DOM_CAUGHT"
    assert audit["criteria"][1]["classification"] == "SCREENSHOT_EVIDENCE_MISSING"
    assert audit["metrics"]["screenshot_evidence_loss"]["count"] == 1
    assert audit["criteria"][0]["screenshot"]["verifier_output"]["evidence_analysis"]
    assert len(audit["shared_trajectory"]["actions"]) == 1
    assert set(audit["shared_trajectory"]["actions"][0]) == {
        "action_index", "action", "text", "intent", "url", "execution_status"
    }
    assert audit["primary_auditor_output"]["attempts"] == 1
    assert audit["adjudicator_output"]["attempts"] == 1


def test_validation_rejects_partial_relationship_reported_as_complete(pair_factory):
    pair = pair_factory()
    response = {
        "criteria": [{
            "criterion_index": 0,
            "required_evidence": "A label associated with its value",
            "screenshot": {
                **_source_decision("screenshot"),
                "missing_required_evidence": ["associated value"],
            },
            "dom_model": _source_decision("dom_model"),
            "screenshot_evidence_loss": False,
            "dom_model_evidence_loss": False,
            "explanation": "Invalid fixture intentionally contradicts COMPLETE coverage.",
        }]
    }
    with pytest.raises(ValueError, match="COMPLETE coverage has inconsistent detail"):
        validate_audit_response(
            response,
            criteria=[{"criterion_index": 0}],
            screenshot_sources={"screenshot0.png", "screenshot1.png"},
            dom_sources={"dom_model0.txt", "dom_model1.txt"},
            screenshot_root=pair["screenshot"],
            dom_root=pair["dom"],
        )


def test_aggregate_reports_failures_without_counting_them_as_evidence_loss():
    rows = [_row(screen_loss=True)]
    audit = {"task_id": "task-a", "criteria": rows, "metrics": calculate_metrics(rows)}
    summary = aggregate_audits([audit], [{"task": "task-b", "error": "infra"}])
    assert summary["completed_tasks"] == 1
    assert len(summary["failed_tasks"]) == 1
    assert summary["metrics"]["total_criteria"] == 1
