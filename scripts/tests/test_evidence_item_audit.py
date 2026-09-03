from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.evidence_item_audit import (
    ADVANTAGE_BY_CLASSIFICATION,
    build_item_review_template,
    calculate_item_metrics,
    finalize_item_review,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _result(*, dom: bool) -> dict:
    evidence = (
        "The Published by label is present, but the publisher value is unavailable."
        if dom
        else "Published by Electronic Arts is clearly visible."
    )
    analysis = {
        "screenshot_evidence": evidence,
        "criterion_analysis": evidence,
        "discrepancies": "Publisher missed." if dom else "None.",
        "environment_issues_confirmed": False,
        "screenshot_idx": 1,
    }
    if dom:
        analysis["dom_model_state_idx"] = 1
    return {
        "task_id": "task-item-fixture",
        "rubric_sha256": "item-rubric-hash",
        "intermediate_mm_rubric_steps": {
            "step2_relevance_scores": {
                "screenshot_0": {"0": 1, "screenshot_idx": 0},
                "screenshot_1": {"0": 10, "screenshot_idx": 1},
            },
            "step3_grouped_screenshots": {"0": [1]},
            "step4_evidence_by_criterion": {"0": [analysis]},
            "step6_rescoring_summary": [
                {
                    "criterion": "Report the publisher",
                    "earned_points": 0,
                    "post_image_earned_points": 0 if dom else 2,
                    "max_points": 2,
                    "justification": "Action-only output.",
                    "applicable_evidence": evidence,
                    "post_image_justification": evidence,
                    "reality_notes": evidence,
                }
            ],
        },
    }


@pytest.fixture
def item_run(tmp_path: Path) -> Path:
    run = tmp_path / "results" / "task1" / "run-item"
    _write(run / "microsoft_verifier" / "result.json", _result(dom=False))
    _write(run / "dom_model" / "result.json", _result(dom=True))
    screenshot = run / "_inputs" / "screenshot"
    dom = run / "_inputs" / "dom_model"
    screenshot.mkdir(parents=True)
    dom.mkdir(parents=True)
    (screenshot / "screenshot0.png").write_bytes(b"initial")
    (screenshot / "screenshot1.png").write_bytes(b"publisher pixels")
    (screenshot / "screenshot_1.png").symlink_to("screenshot0.png")
    (dom / "dom_model0.txt").write_text("URL: https://example.test\nInitial\n", encoding="utf-8")
    (dom / "dom_model1.txt").write_text(
        "URL: https://example.test/product\n"
        "Title: Product\n"
        "Published by\n"
        "Electronic Arts\n",
        encoding="utf-8",
    )
    _write(
        run / "_inputs" / "frozen_rubric.json",
        {
            "task_id": "task-item-fixture",
            "precomputed_rubric": {
                "items": [
                    {
                        "criterion": "Report the publisher",
                        "description": "Report the publisher shown on the product page.",
                        "max_points": 2,
                        "justification": "",
                        "earned_points": "",
                    }
                ]
            },
        },
    )
    return run


def _publisher_item() -> dict:
    return {
        "evidence_id": "C0-E1",
        "evidence_requirement": "Publisher shown on product page",
        "expected_value": "Electronic Arts",
        "review_status": "confirmed",
        "screenshot": {
            "source_present": True,
            "source_citations": [
                {
                    "file": "screenshot1.png",
                    "visible_text": "Published by Electronic Arts",
                    "locator": "publisher metadata row",
                }
            ],
            "verifier_caught": True,
            "verifier_evidence_excerpt": "Published by Electronic Arts is clearly visible.",
            "review_note": "Visible and recovered.",
        },
        "dom_model": {
            "source_present": True,
            "source_citations": [
                {
                    "file": "dom_model1.txt",
                    "line_range": "m1:L3-L4",
                    "quoted_text": "Published by\nElectronic Arts",
                }
            ],
            "verifier_caught": False,
            "verifier_evidence_excerpt": (
                "The Published by label is present, but the publisher value is unavailable."
            ),
            "review_note": "Value exists in source but verifier missed it.",
        },
    }


def test_template_preserves_context_and_ignores_compatibility_symlink(item_run: Path):
    audit, review = build_item_review_template(item_run)
    assert [Path(row["file"]).name for row in audit["source_inventory"]["screenshot"]] == [
        "screenshot0.png",
        "screenshot1.png",
    ]
    criterion = review["criteria"][0]
    assert criterion["description"] == "Report the publisher shown on the product page."
    assert criterion["screenshot_context"]["verifier_evidence"].startswith("Published by")
    assert criterion["dom_model_context"]["selected_indices"] == [1]
    assert criterion["evidence_items"] == []


def test_finalizes_exact_evidence_item_and_advantage(item_run: Path):
    audit, review = build_item_review_template(item_run)
    review["criteria"][0]["evidence_items"] = [_publisher_item()]
    result = finalize_item_review(audit, review)
    item = result["criteria"][0]["evidence_items"][0]
    assert item["classification"] == "DOM_MISSED_SCREENSHOT_CAUGHT"
    assert item["advantage"] == "SCREENSHOT"
    assert item["dom_model"]["source_citations"][0]["line_range"] == "m1:L3-L4"
    metrics = calculate_item_metrics(result)
    assert metrics["present_in_both_count"] == 1
    assert metrics["screenshot_common_evidence_catch_rate"]["percentage"] == 100.0
    assert metrics["dom_common_evidence_catch_rate"]["percentage"] == 0.0
    assert metrics["screenshot_recovery_of_confirmed_dom_misses"]["percentage"] == 100.0


def test_rejects_dom_quote_outside_cited_lines(item_run: Path):
    audit, review = build_item_review_template(item_run)
    item = _publisher_item()
    item["dom_model"]["source_citations"][0]["quoted_text"] = "Wrong Publisher"
    review["criteria"][0]["evidence_items"] = [item]
    with pytest.raises(ValueError, match="quote does not occur"):
        finalize_item_review(audit, review)


def test_rejects_non_verbatim_verifier_excerpt(item_run: Path):
    audit, review = build_item_review_template(item_run)
    item = _publisher_item()
    item["screenshot"]["verifier_evidence_excerpt"] = "Rewritten reviewer interpretation"
    review["criteria"][0]["evidence_items"] = [item]
    with pytest.raises(ValueError, match="not verbatim"):
        finalize_item_review(audit, review)


def test_rejects_caught_when_source_missing(item_run: Path):
    audit, review = build_item_review_template(item_run)
    item = _publisher_item()
    item["screenshot"]["source_present"] = False
    item["screenshot"]["source_citations"] = []
    review["criteria"][0]["evidence_items"] = [item]
    with pytest.raises(ValueError, match="cannot be caught"):
        finalize_item_review(audit, review)


def test_all_six_classes_have_explicit_advantage_semantics():
    assert ADVANTAGE_BY_CLASSIFICATION == {
        "BOTH_CAUGHT": "TIE",
        "SCREENSHOT_MISSED_DOM_CAUGHT": "DOM",
        "DOM_MISSED_SCREENSHOT_CAUGHT": "SCREENSHOT",
        "BOTH_MISSED": "NEITHER",
        "SCREENSHOT_EVIDENCE_MISSING": "NOT_COMPARABLE",
        "DOM_EVIDENCE_MISSING": "NOT_COMPARABLE",
    }


def test_pending_items_do_not_enter_metrics(item_run: Path):
    audit, review = build_item_review_template(item_run)
    item = _publisher_item()
    item["review_status"] = "pending"
    review["criteria"][0]["evidence_items"] = [item]
    result = finalize_item_review(audit, review)
    metrics = calculate_item_metrics(result)
    assert metrics["evidence_item_count"] == 1
    assert metrics["confirmed_count"] == 0
    assert metrics["pending_count"] == 1
    assert metrics["present_in_both_count"] == 0


def test_item_audit_has_no_verifier_or_llm_imports():
    source = Path(__file__).parents[1] / "evidence_item_audit.py"
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
