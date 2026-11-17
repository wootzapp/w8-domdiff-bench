from functools import partial
import json

import pytest

from w8bench.verifier.common import canonical_sha256
from w8bench.verifier.audit_requests import ADJUDICATION_SYSTEM_PROMPT, SYSTEM_PROMPT, AuditValidationError, _request_validated_audit, _source_instructions
from w8bench.verifier.evidence_audit import SCHEMA_VERSION, PROMPT_VERSION, calculate_metrics, run_evidence_audit
from w8bench.verifier.audit_validation import CITATION_KEYS, _resolve_source_name, _validate_finding, _validate_modality_decision, classification, validate_audit_response, validate_adjudication_response
from w8bench.verifier.audit_evidence import ordered_audit_screenshots, verifier_action_history


def _modality(coverage="COMPLETE", caught=True):
    return {"coverage": coverage, "verifier_caught": caught}


def _row(*, screen_loss=False, dom_loss=False, screen_caught=True, dom_caught=True):
    return {
        "screenshot": _modality("PARTIAL" if screen_loss else "COMPLETE", screen_caught),
        "dom_model": _modality("PARTIAL" if dom_loss else "COMPLETE", dom_caught),
        "screenshot_evidence_loss": screen_loss,
        "dom_model_evidence_loss": dom_loss,
    }


def _audit(task_id, rows):
    return {"task_id": task_id, "criteria": rows, "metrics": calculate_metrics(rows),
            "schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION,
            "audit_model": "gemini-3.1-pro-preview", "adjudicator_model": "gpt-6.1-sol"}


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
    assert "formatted action history count for both verifiers" in ADJUDICATION_SYSTEM_PROMPT
    assert "absence from screenshot pixels or DOM text alone is not a loss" in ADJUDICATION_SYSTEM_PROMPT
    assert "earlier selected control or state remains evidence" in ADJUDICATION_SYSTEM_PROMPT
    for prompt in (SYSTEM_PROMPT, ADJUDICATION_SYSTEM_PROMPT):
        assert "shared context" in prompt
        assert "initial URL alone" in prompt or "initial\nURL alone" in prompt
        assert "corroborating" in prompt
        assert "absent from all allowed inputs" in prompt or "absent\nfrom all allowed inputs" in prompt


def test_source_instructions_declare_the_complete_citation_contract(pair_factory):
    pair = pair_factory()
    instructions = _source_instructions(pair["screenshot"], pair["dom"])
    assert "all required, no extra keys" in instructions
    assert json.dumps(CITATION_KEYS) in instructions
    assert "Lx or Lx-Ly for DOM/history" in instructions
    assert "visible image region for screenshots" in instructions


def test_incomplete_citation_feedback_names_the_missing_contract(pair_factory):
    pair = pair_factory()
    decision = _source_decision("dom_model")
    del decision["citations"][0]["location"]
    with pytest.raises(ValueError) as caught:
        _validate_modality_decision(
            decision, modality="dom_model", allowed_sources={"dom_model1.txt"},
            source_root=pair["dom"],
        )
    assert "expected exactly ['source', 'location', 'quote']" in str(caught.value)
    assert "received ['quote', 'source']" in str(caught.value)


def test_shared_history_matches_the_existing_judge_projection(pair_factory):
    from w8bench.verifier.screenshot_verifier.adapter import create_datapoint
    from w8bench.verifier.screenshot_verifier.models import Trajectory
    from w8bench.verifier.screenshot_verifier.rubric_agent import MMRubricAgent

    pair = pair_factory()
    event_path = pair["screenshot"] / "web_surfer.log"
    event = json.loads(event_path.read_text().splitlines()[0])
    event["url"] = "https://example.test/" + "x" * 180 + "?query=value#section"
    event["arguments"] = {"action": "visit_url", "url": "https://example.test/request?query=value", "thoughts": ""}
    event["action"] = "visit_url"
    event_path.write_text(json.dumps(event) + "\n")
    candidate = Trajectory(pair["screenshot"])
    datapoint = create_datapoint(pair["task"], candidate)
    expected = MMRubricAgent._format_action_history(datapoint.solver_log.get_step_summaries())
    actual = verifier_action_history(pair["screenshot"])
    assert actual == expected
    assert actual.splitlines()[0] == "State 1: " + event["url"].split("?")[0][:150] + "..., state_description: "
    assert '"url": "https://example.test/request?query=value"' in actual


def test_shared_url_can_support_both_modalities_without_pixel_or_dom_citations(pair_factory):
    pair = pair_factory()
    history = verifier_action_history(pair["screenshot"]).splitlines()
    citation = {"source": "action_history", "location": "L1", "quote": history[0]}
    shared = {
        "coverage": "COMPLETE", "available_evidence": [history[0]],
        "missing_required_evidence": [], "verifier_caught": True, "citations": [citation],
    }
    response = {"criteria": [{
        "criterion_index": 0, "required_evidence": "Observed page identity",
        "screenshot": shared, "dom_model": shared,
        "screenshot_evidence_loss": False, "dom_model_evidence_loss": False,
        "explanation": "The formatted history supplies the same observed URL.",
    }]}
    checked = validate_audit_response(
        response, criteria=[{"criterion_index": 0}],
        screenshot_sources={"screenshot0.png", "screenshot1.png"},
        dom_sources={"dom_model0.txt", "dom_model1.txt"},
        screenshot_root=pair["screenshot"], dom_root=pair["dom"],
    )
    assert checked[0]["screenshot"]["coverage"] == "COMPLETE"
    assert checked[0]["dom_model"]["coverage"] == "COMPLETE"
    citation["quote"] = "https://example.test/not-in-history?missing=value"
    with pytest.raises(ValueError, match="quote is not present"):
        validate_audit_response(
            response, criteria=[{"criterion_index": 0}],
            screenshot_sources={"screenshot0.png", "screenshot1.png"},
            dom_sources={"dom_model0.txt", "dom_model1.txt"},
            screenshot_root=pair["screenshot"], dom_root=pair["dom"],
        )


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


def test_citation_feedback_identifies_the_invalid_quote_without_accepting_it(pair_factory):
    pair = pair_factory()
    decision = _source_decision("dom_model")
    decision["citations"][0]["quote"] = "Invented ... excerpt"
    with pytest.raises(ValueError, match="quote is not present") as caught:
        _validate_modality_decision(
            decision, modality="dom_model", allowed_sources={"dom_model1.txt"},
            source_root=pair["dom"],
        )
    assert "dom_model1.txt" in str(caught.value)
    assert "L0005-L0007" in str(caught.value)
    assert "Invented ... excerpt" in str(caught.value)


def test_finding_feedback_identifies_the_required_evidence_mode(pair_factory):
    pair = pair_factory()
    finding = _finding(True, modality="screenshot")
    with pytest.raises(ValueError, match="screenshot evidence loss requires dom_model evidence"):
        _validate_finding(
            finding, label="screenshot evidence loss", citation_modality="dom_model",
            allowed_sources={"dom_model0.txt", "dom_model1.txt"}, source_root=pair["dom"],
        )


def test_counterpart_citations_are_checked_without_replacing_decisive_evidence(pair_factory):
    pair = pair_factory()
    finding = _finding(True, modality="dom_model")
    supporting = _finding(True, modality="screenshot")["citations"][0]
    finding["citations"].append(supporting)
    options = dict(
        label="screenshot evidence loss", citation_modality="dom_model",
        allowed_sources={"dom_model1.txt"}, source_root=pair["dom"],
        counterpart_sources={"screenshot1.png"}, counterpart_root=pair["screenshot"],
    )
    checked = _validate_finding(finding, **options)
    assert [c["source"] for c in checked["citations"]] == ["dom_model1.txt", "screenshot1.png"]
    finding["citations"] = [supporting]
    with pytest.raises(ValueError, match="requires decisive dom_model evidence"):
        _validate_finding(finding, **options)


def test_bad_supporting_quotes_are_rejected_even_with_valid_decisive_evidence(pair_factory):
    pair = pair_factory()
    finding = _finding(True, modality="screenshot")
    supporting = _finding(True, evidence="Invented value", modality="dom_model")["citations"][0]
    finding["citations"].append(supporting)
    with pytest.raises(ValueError, match="quote is not present"):
        _validate_finding(
            finding, label="DOM evidence loss", citation_modality="screenshot",
            allowed_sources={"screenshot1.png"}, source_root=pair["screenshot"],
            counterpart_sources={"dom_model1.txt"}, counterpart_root=pair["dom"],
        )


def test_counterpart_evidence_cannot_prove_a_verifier_miss(pair_factory):
    pair = pair_factory()
    finding = _finding(True, modality="screenshot")
    with pytest.raises(ValueError, match="requires decisive dom_model evidence"):
        _validate_finding(
            finding, label="DOM verifier miss", citation_modality="dom_model",
            allowed_sources={"dom_model1.txt"}, source_root=pair["dom"],
            counterpart_sources={"screenshot1.png"}, counterpart_root=pair["screenshot"],
        )


def test_citation_feedback_reports_every_bad_quote_without_accepting_any(pair_factory):
    pair = pair_factory()
    decision = _source_decision("dom_model")
    decision["citations"] = [
        {"source": "dom_model1.txt", "location": "L0005-L0007", "quote": quote}
        for quote in ("invented first value", "invented second value")
    ]
    with pytest.raises(ValueError) as caught:
        _validate_modality_decision(
            decision, modality="dom_model", allowed_sources={"dom_model1.txt"},
            source_root=pair["dom"],
        )
    assert "invented first value" in str(caught.value)
    assert "invented second value" in str(caught.value)


def test_inventory_feedback_reports_errors_in_every_criterion(pair_factory):
    pair = pair_factory()
    rows = []
    for index in range(2):
        decision = _source_decision("dom_model")
        decision["citations"][0]["quote"] = f"invented value {index}"
        rows.append({
            "criterion_index": index, "required_evidence": "Saved status",
            "screenshot": _source_decision("screenshot"), "dom_model": decision,
            "screenshot_evidence_loss": False, "dom_model_evidence_loss": False,
            "explanation": "Evidence check",
        })
    with pytest.raises(ValueError) as caught:
        validate_audit_response(
            {"criteria": rows}, criteria=[{}, {}],
            screenshot_sources={"screenshot1.png"}, dom_sources={"dom_model1.txt"},
            screenshot_root=pair["screenshot"], dom_root=pair["dom"],
        )
    assert "criterion 0" in str(caught.value)
    assert "criterion 1" in str(caught.value)


def test_adjudication_feedback_reports_all_invalid_findings(pair_factory):
    pair = pair_factory()
    row = {"criterion_index": 0, "explanation": "Evidence check"}
    for field in ("screenshot_evidence_loss", "dom_model_verifier_miss"):
        row[field] = _finding(True, evidence=f"invented {field}")
    for field in ("dom_model_evidence_loss", "screenshot_verifier_miss"):
        row[field] = _finding(False)
    with pytest.raises(ValueError) as caught:
        validate_adjudication_response(
            {"criteria": [row]}, criteria=[{}],
            screenshot_sources={"screenshot1.png"}, dom_sources={"dom_model1.txt"},
            screenshot_root=pair["screenshot"], dom_root=pair["dom"],
        )
    assert "invented screenshot_evidence_loss" in str(caught.value)
    assert "invented dom_model_verifier_miss" in str(caught.value)


@pytest.mark.parametrize("requester", [_request_validated_audit, partial(_request_validated_audit, inventory=False)])
def test_validation_correction_retains_the_previous_response(requester, tmp_path):
    messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": "evidence"}]
    invalid = {"criteria": []}
    calls = []

    def complete(model, current):
        calls.append(current)
        return invalid

    with pytest.raises(AuditValidationError):
        requester(
            model="configured-model", messages=messages, criteria=[{"criterion_index": 0}],
            screenshot_sources=set(), dom_sources=set(), screenshot_root=tmp_path, dom_root=tmp_path,
            complete=complete, max_attempts=2,
        )
    assert len(calls) == 2
    assert calls[1][:2] == messages
    assert calls[1][-2] == {"role": "assistant", "content": json.dumps(invalid)}
    assert calls[1][-1]["role"] == "user"


def test_audit_ignores_screenshot_compatibility_screenshot_symlinks(pair_factory):
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
    assert calls[0][0] == "gemini-3.1-pro-preview"
    assert calls[1][0] == "gpt-6.1-sol"
    assert audit["adjudicator_model"] == "gpt-6.1-sol"
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


def _paired_capture_context(pair, *, dom_gaps=(), screenshot_gaps=(), navigation=()):
    """Create real same-run origin receipts around the offline paired fixture."""
    import hashlib
    for key, prefix, extension in (("screenshot", "screenshot", "png"), ("dom", "dom_model", "txt")):
        root = pair[key]
        for old in (1, 0):
            (root / f"{prefix}{old}.{extension}").rename(root / f"{prefix}{old + 1}.{extension}")
    if dom_gaps:
        for state in dom_gaps:
            (pair["dom"] / f"dom_model{state}.txt").unlink()
    for state in screenshot_gaps:
        (pair["screenshot"] / f"screenshot{state}.png").unlink()
    context = {"recording_sha256": "a" * 64, "task_id": pair["task"]["task_id"],
        "actor_arm": "screenshot", "trial_id": "trial_09", "validity_date": "2026-11-01",
        "expected_state_ids": [1, 2], "format_gaps": {"screenshot": list(screenshot_gaps), "dom_model": list(dom_gaps)},
        "navigation_states": list(navigation),
        "audit_eligible_states": [index for index in (1, 2) if index not in set(dom_gaps) | set(screenshot_gaps) | set(navigation)],
        "observed_url_timeline": [
            {"state": 1, "url": "https://example.test/start?full=query#fragment", "verified": True},
            {"state": 2, "url": "https://unverified.test/SECRET", "verified": False}],
        "source_files_sha256": {"manifest.json": "b" * 64}, "states": []}
    for state in (1, 2):
        artifacts = {}
        for key, artifact, filename in (("screenshot", "screenshot.png", f"screenshot{state}.png"), ("dom", "dom_model.txt", f"dom_model{state}.txt")):
            path = pair[key] / filename
            if path.exists():
                artifacts[artifact] = {"path": f"states/{state}/{artifact}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        context["states"].append({"state": state, "source_index": state, "eligible": state in context["audit_eligible_states"], "reason": "navigation" if state in navigation else "capture_failed" if state in dom_gaps else "paired", "artifacts": artifacts})
    for key in ("screenshot", "dom"):
        root = pair[key]
        task = json.loads((root / "task_data.json").read_text())
        task["evaluation_context"] = context
        (root / "task_data.json").write_text(json.dumps(task))
    answer_path = pair["screenshot"] / "final_answer.json"
    answer = json.loads(answer_path.read_text())
    answer["screenshots"] = [f"screenshot{index}.png" for index in (1, 2) if index not in screenshot_gaps]
    answer_path.write_text(json.dumps(answer))
    return context


def test_audit_origin_binding_and_verified_url_context(pair_factory):
    from w8bench.verifier.audit_evidence import shared_trajectory_payload
    pair = pair_factory()
    context = _paired_capture_context(pair)
    payload = shared_trajectory_payload(pair["screenshot"], pair["dom"])
    assert payload["evaluation_context"] == context
    history = payload["verifier_action_history"]["screenshot"]
    assert "https://example.test/start?full=query#fragment" in history
    assert "unavailable (not verified)" in history
    assert "SECRET" not in history
    assert history == payload["verifier_action_history"]["dom_model"]
    from w8bench.verifier.audit_requests import pairwise_messages
    messages = json.dumps(pairwise_messages(screenshot_dir=pair["screenshot"], dom_dir=pair["dom"],
        criteria=[], screenshot_context=[], dom_context=[], shared_trajectory=payload))
    assert "actor_arm" not in messages and "source_files_sha256" not in messages
    assert "SAME original state IDs" in messages
    (pair["dom"] / "dom_model1.txt").write_text("modified")
    with pytest.raises(ValueError, match="same-run receipt"):
        shared_trajectory_payload(pair["screenshot"], pair["dom"])


def test_audit_gaps_do_not_drop_available_opposite_format_states(pair_factory):
    from w8bench.verifier.audit_evidence import ordered_dom_states, shared_trajectory_payload
    pair = pair_factory()
    _paired_capture_context(pair, dom_gaps=(2,))
    assert [path.name for path in ordered_audit_screenshots(pair["screenshot"])] == ["screenshot1.png", "screenshot2.png"]
    assert [path.name for path in ordered_dom_states(pair["dom"])] == ["dom_model1.txt"]
    context = shared_trajectory_payload(pair["screenshot"], pair["dom"])["evaluation_context"]
    assert context["audit_eligible_states"] == [1]
    assert context["format_gaps"] == {"screenshot": [], "dom_model": [2]}


def test_navigation_state_is_available_for_miss_but_not_directional_loss(pair_factory):
    pair = pair_factory()
    _paired_capture_context(pair, navigation=(2,))
    criteria = [{"criterion_index": 0}]
    false = _finding()
    citation = {"source": "dom_model2.txt", "location": "L5-L7", "quote": "Saved"}
    positive = {**_finding(True), "citations": [citation]}
    row = {"criterion_index": 0, "screenshot_evidence_loss": false,
        "dom_model_evidence_loss": false, "screenshot_verifier_miss": false,
        "dom_model_verifier_miss": positive, "explanation": "miss in own available navigation state"}
    kwargs = {"criteria": criteria, "screenshot_sources": {"screenshot1.png", "screenshot2.png"},
        "dom_sources": {"dom_model1.txt", "dom_model2.txt"}, "screenshot_root": pair["screenshot"], "dom_root": pair["dom"]}
    result = validate_adjudication_response({"criteria": [row]}, **kwargs)
    assert result[0]["dom_model_verifier_miss"]["confirmed"] is True
    row["dom_model_verifier_miss"] = false
    row["screenshot_evidence_loss"] = positive
    with pytest.raises(ValueError, match="Unknown dom_model citation"):
        validate_adjudication_response({"criteria": [row]}, **kwargs)


def _validated_request_case(pair, stage):
    if stage == "inventory":
        response = {"criteria": [{
            "criterion_index": 0, "required_evidence": "Saved status",
            "screenshot": _source_decision("screenshot"),
            "dom_model": _source_decision("dom_model"),
            "screenshot_evidence_loss": False, "dom_model_evidence_loss": False,
            "explanation": "Both sources show Saved.",
        }]}
        requester = _request_validated_audit
        validation_error = "Evidence auditor returned an incomplete criteria list"
        error_stage = "primary evidence inventory"
        feedback = (
            "Your JSON failed validation: Evidence auditor returned an incomplete criteria list. "
            "Return a corrected complete JSON object using the required schema and the same supplied evidence."
        )
    else:
        response = {"criteria": [{
            "criterion_index": 0,
            **{field: _finding() for field in (
                "screenshot_evidence_loss", "dom_model_evidence_loss",
                "screenshot_verifier_miss", "dom_model_verifier_miss",
            )},
            "explanation": "Both sources show Saved.",
        }]}
        requester = partial(_request_validated_audit, inventory=False)
        validation_error = "Adjudicator returned an incomplete criteria list"
        error_stage = "final evidence adjudication"
        feedback = (
            "Your adjudication JSON failed validation: Adjudicator returned an incomplete criteria list. "
            "Return a corrected complete JSON object using the required schema and same evidence."
        )
    options = {
        "model": "configured-model",
        "messages": [{"role": "system", "content": "policy"}, {"role": "user", "content": "evidence"}],
        "criteria": [{"criterion_index": 0}],
        "screenshot_sources": {"screenshot1.png"}, "dom_sources": {"dom_model1.txt"},
        "screenshot_root": pair["screenshot"], "dom_root": pair["dom"],
    }
    return requester, response, options, validation_error, error_stage, feedback


@pytest.mark.parametrize("stage", ["inventory", "adjudication"])
def test_validated_request_accepts_one_response_without_mutating_messages(pair_factory, stage):
    pair = pair_factory()
    requester, response, options, _, _, _ = _validated_request_case(pair, stage)
    messages = json.loads(json.dumps(options["messages"]))
    calls, receipts = [], []

    def complete(model, current):
        calls.append((model, current))
        return response

    decisions, raw, attempts = requester(**options, complete=complete, invalid_receipts=receipts)
    assert calls == [("configured-model", messages)]
    assert options["messages"] == messages
    assert raw is response
    assert attempts == 1 and receipts == []
    assert decisions[0]["criterion_index"] == 0
    assert decisions[0]["explanation"] == "Both sources show Saved."
    if stage == "inventory":
        assert decisions[0]["classification"] == "BOTH_CAUGHT"
        assert decisions[0]["dom_model"]["citations"] == response["criteria"][0]["dom_model"]["citations"]
    else:
        assert decisions[0] == response["criteria"][0]


@pytest.mark.parametrize("stage", ["inventory", "adjudication"])
def test_validated_request_retry_preserves_exact_feedback_and_receipt(pair_factory, stage):
    pair = pair_factory()
    requester, response, options, validation_error, _, feedback = _validated_request_case(pair, stage)
    original_messages = json.loads(json.dumps(options["messages"]))
    invalid = {"criteria": []}
    calls, receipts = [], []

    def complete(model, current):
        calls.append((model, current))
        return invalid if len(calls) == 1 else response

    decisions, raw, attempts = requester(**options, complete=complete, invalid_receipts=receipts)
    assert attempts == 2 and raw is response
    assert decisions[0]["criterion_index"] == 0
    assert options["messages"] == original_messages
    assert calls == [
        ("configured-model", original_messages),
        ("configured-model", [*original_messages,
            {"role": "assistant", "content": '{"criteria": []}'},
            {"role": "user", "content": feedback}]),
    ]
    assert receipts == [{
        "attempt": 1, "validation_error": validation_error, "raw_response": invalid,
        "flag_flips_detected": False, "flag_flips": [],
        "uncomparable_flags": [{"criterion_index": 0, "flag": field} for field in (
            "screenshot_evidence_loss", "dom_model_evidence_loss",
            "screenshot_verifier_miss", "dom_model_verifier_miss",
        )],
    }]


@pytest.mark.parametrize("stage", ["inventory", "adjudication"])
def test_validated_request_exhaustion_retains_every_response_and_stage(pair_factory, stage):
    pair = pair_factory()
    requester, _, options, validation_error, error_stage, feedback = _validated_request_case(pair, stage)
    original_messages = json.loads(json.dumps(options["messages"]))
    invalid = {"criteria": []}
    calls, receipts = [], []

    def complete(model, current):
        calls.append((model, current))
        return invalid

    with pytest.raises(AuditValidationError) as caught:
        requester(**options, complete=complete, max_attempts=3, invalid_receipts=receipts)
    repair = [{"role": "assistant", "content": '{"criteria": []}'}, {"role": "user", "content": feedback}]
    assert calls == [("configured-model", [*original_messages, *(repair * count)]) for count in range(3)]
    assert options["messages"] == original_messages
    assert caught.value.attempts is receipts
    assert caught.value.receipt() == {
        "stage": error_stage, "attempt_count": 3, "last_validation_error": validation_error,
        "attempts": [{"attempt": attempt, "validation_error": validation_error, "raw_response": invalid}
            for attempt in (1, 2, 3)],
    }
    assert str(caught.value) == f"{error_stage} remained invalid after 3 attempts: {validation_error}"


@pytest.mark.parametrize("stage", ["inventory", "adjudication"])
def test_validated_request_with_zero_attempts_has_no_completion_call(pair_factory, stage):
    requester, _, options, _, error_stage, _ = _validated_request_case(pair_factory(), stage)
    receipts = []

    def complete(model, current):
        pytest.fail("A zero-attempt request reached the completion function")

    with pytest.raises(AuditValidationError) as caught:
        requester(**options, complete=complete, max_attempts=0, invalid_receipts=receipts)
    assert caught.value.attempts is receipts
    assert caught.value.receipt() == {
        "stage": error_stage, "attempt_count": 0,
        "last_validation_error": "unknown validation error", "attempts": [],
    }


@pytest.mark.parametrize("stage", ["inventory", "adjudication"])
def test_validated_request_updates_the_supplied_prior_receipt(pair_factory, stage):
    requester, response, options, _, _, _ = _validated_request_case(pair_factory(), stage)
    field = "screenshot_evidence_loss"
    prior_value = True if stage == "inventory" else {"confirmed": True}
    prior = {"attempt": 0, "validation_error": "prior issue",
        "raw_response": {"criteria": [{"criterion_index": 0, field: prior_value}]}}
    receipts = [prior]
    _, raw, attempts = requester(**options, complete=lambda model, messages: response, invalid_receipts=receipts)
    assert raw is response and attempts == 1
    assert receipts == [prior] and receipts[0] is prior
    assert prior["flag_flips_detected"] is True
    assert prior["flag_flips"] == [{"criterion_index": 0, "flag": field, "failed_value": True, "accepted_value": False}]
    assert prior["uncomparable_flags"] == [{"criterion_index": 0, "flag": field} for field in (
        "dom_model_evidence_loss", "screenshot_verifier_miss", "dom_model_verifier_miss",
    )]


@pytest.mark.parametrize("stage", ["inventory", "adjudication"])
def test_completion_errors_propagate_without_validation_retry(pair_factory, stage):
    requester, _, options, _, _, _ = _validated_request_case(pair_factory(), stage)
    calls, receipts = [], []

    def complete(model, current):
        calls.append((model, current))
        raise ValueError("completion unavailable")

    with pytest.raises(ValueError, match="^completion unavailable$"):
        requester(**options, complete=complete, invalid_receipts=receipts)
    assert calls == [("configured-model", options["messages"])]
    assert receipts == []


def test_finding_feedback_preserves_nested_citation_errors(pair_factory):
    pair = pair_factory()
    finding = _finding(True, modality="dom_model")
    finding["citations"][0]["location"] = "L9999"
    with pytest.raises(ValueError) as caught:
        _validate_finding(finding, label="screenshot evidence loss", citation_modality="dom_model",
            allowed_sources={"dom_model1.txt"}, source_root=pair["dom"])
    assert str(caught.value) == (
        "screenshot evidence loss requires dom_model evidence: citation 1: citation 1: "
        "DOM citation line range is outside its source file: dom_model1.txt, "
        "'L9999'; source has 7 lines"
    )
