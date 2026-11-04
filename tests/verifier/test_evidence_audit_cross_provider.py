from copy import deepcopy
import importlib
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from w8bench.verifier import evidence_audit as audit
from w8bench.verifier.common import canonical_sha256
from .test_automated_evidence_audit import _audit, _row, _source_decision, _finding


def _responses():
    inventory, adjudication = {"criteria": []}, {"criteria": []}
    for index in range(2):
        inventory["criteria"].append({
            "criterion_index": index, "required_evidence": "Saved status",
            "screenshot": _source_decision("screenshot"),
            "dom_model": _source_decision("dom_model"),
            "screenshot_evidence_loss": False, "dom_model_evidence_loss": False,
            "explanation": "Both sources preserve the status.",
        })
        adjudication["criteria"].append({
            "criterion_index": index, "screenshot_evidence_loss": _finding(),
            "dom_model_evidence_loss": _finding(), "screenshot_verifier_miss": _finding(),
            "dom_model_verifier_miss": _finding(), "explanation": "No confirmed gap.",
        })
    return inventory, adjudication


def _run(pair, complete):
    frozen = json.loads(pair["rubric"].read_text())
    result = {"task_id": pair["task"]["task_id"],
              "rubric_sha256": canonical_sha256(frozen["precomputed_rubric"]),
              "intermediate_mm_rubric_steps": {"step6_rescoring_summary": [
                  {"earned_points": 7, "max_points": 7}, {"earned_points": 3, "max_points": 3}]}}
    ss, dom = pair["staged"] / "ss-result.json", pair["staged"] / "dom-result.json"
    ss.write_text(json.dumps(result)); dom.write_text(json.dumps(result))
    return audit.run_evidence_audit(screenshot_dir=pair["screenshot"], dom_dir=pair["dom"],
        rubric_file=pair["rubric"], screenshot_result=ss, dom_result=dom, complete=complete)


def _complete(inventory, adjudication):
    return lambda model, messages: deepcopy(adjudication if model.startswith("gemini-") else inventory)


@pytest.mark.parametrize("model", ["gpt-5", "gpt-5.1", "gpt-5.6-sol", "gpt-4.1"])
def test_openai_routing_records_actual_request_settings(monkeypatch, model):
    create = Mock(return_value=SimpleNamespace(id="openai-id", model="resolved-openai",
        usage=None, system_fingerprint="fingerprint",
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))]))
    client = Mock()
    client.__enter__ = Mock(return_value=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    client.__exit__ = Mock(return_value=False)
    constructor = Mock(return_value=client)
    monkeypatch.setattr(audit, "OpenAI", constructor)
    monkeypatch.setattr(audit, "DefaultHttpxClient", Mock())
    records = []
    assert audit._completion(model, [{"role": "system", "content": audit.SYSTEM_PROMPT}], records=records) == {"ok": True}
    args = create.call_args.kwargs
    assert "temperature" not in args and "seed" not in args
    assert args["response_format"] == {"type": "json_object"}
    assert records[0]["provider"] == "openai"
    assert records[0]["requested_model"] == model
    assert records[0]["response_model"] == "resolved-openai"
    assert "temperature" not in records[0]["generation_settings"]
    assert "seed" not in records[0]["generation_settings"]
    assert records[0]["completed_at"] >= records[0]["started_at"]
    assert constructor.call_args.kwargs["max_retries"] == 0
    hook = audit.DefaultHttpxClient.call_args.kwargs["event_hooks"]["request"][0]
    hook(SimpleNamespace(content=json.dumps({"model": model, "messages": ["private prompt"],
                                            "response_format": {"type": "json_object"}}).encode()))
    assert records[0]["api_attempts"][0]["request_settings"] == {"model": model, "response_format": {"type": "json_object"}}


def _fake_google(monkeypatch, text='{"ok":true}'):
    google, genai, types = ModuleType("google"), ModuleType("google.genai"), ModuleType("google.genai.types")
    types.Part = SimpleNamespace(from_text=lambda **k: k, from_bytes=lambda **k: k)
    types.Content = lambda **k: k
    types.GenerateContentConfig = lambda **k: k
    types.HttpOptions = lambda **k: k
    usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=3, thoughts_token_count=2,
                            model_dump=lambda: {"prompt_token_count": 10, "candidates_token_count": 3, "thoughts_token_count": 2})
    generate = Mock(return_value=SimpleNamespace(text=text, response_id="gemini-id",
                                               model_version="resolved-gemini", usage_metadata=usage))
    client = Mock()
    client.__enter__ = Mock(return_value=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    client.__exit__ = Mock(return_value=False)
    constructor = Mock(return_value=client)
    genai.Client, genai.types, google.genai = constructor, types, genai
    for name, module in (("google", google), ("google.genai", genai), ("google.genai.types", types)):
        monkeypatch.setitem(sys.modules, name, module)
    return constructor, generate


def test_gemini_native_routing_preserves_base64_and_retry_roles(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    constructor, generate = _fake_google(monkeypatch)
    openai = Mock(side_effect=AssertionError("Gemini must not reach OpenAI"))
    monkeypatch.setattr(audit, "OpenAI", openai)
    messages = [{"role": "system", "content": audit.ADJUDICATION_SYSTEM_PROMPT},
                {"role": "user", "content": [{"type": "text", "text": "Saved"},
                 {"type": "image_url", "image_url": {"url": "data:image/png;base64,YWJj", "detail": "high"}}]},
                {"role": "assistant", "content": '{"invalid":true}'},
                {"role": "user", "content": "Repair the JSON."}]
    before = deepcopy(messages)
    records = []
    assert audit._completion("gemini-3.1-pro-preview", messages, records=records) == {"ok": True}
    assert messages == before
    assert constructor.call_args.kwargs["api_key"] == "fake-gemini-key"
    args = generate.call_args.kwargs
    assert args["model"] == "gemini-3.1-pro-preview"
    assert args["contents"][0]["parts"][1] == {"data": b"abc", "mime_type": "image/png"}
    assert [c["role"] for c in args["contents"]] == ["user", "model", "user"]
    assert args["config"]["system_instruction"] == audit.ADJUDICATION_SYSTEM_PROMPT
    assert "temperature" not in args["config"] and "seed" not in args["config"]
    assert "thinking_config" not in args["config"]
    assert args["config"]["media_resolution"] == "MEDIA_RESOLUTION_HIGH"
    assert constructor.call_args.kwargs["http_options"]["api_version"] == "v1beta"
    assert constructor.call_args.kwargs["http_options"]["retry_options"] == {"attempts": 1}
    hook = constructor.call_args.kwargs["http_options"]["client_args"]["event_hooks"]["request"][0]
    config = {"responseMimeType": "application/json", "mediaResolution": "MEDIA_RESOLUTION_HIGH"}
    hook(SimpleNamespace(content=json.dumps({"generationConfig": config, "contents": ["private image"]}).encode()))
    assert records[0]["api_attempts"][0]["request_settings"] == config
    assert records[0]["api_version"] == "v1beta"
    assert args["config"]["response_mime_type"] == "application/json"
    assert records[0]["provider"] == "google" and records[0]["response_model"] == "resolved-gemini"
    assert records[0]["usage"] == {"prompt_tokens": 10, "completion_tokens": 5,
                                    "reasoning_tokens": 2, "total_tokens": 15}
    openai.assert_not_called()


@pytest.mark.parametrize("model, key", [("gemini-pro-latest", "fake-key"), ("gemini-3.1-pro-preview", "")])
def test_gemini_missing_key_and_alias_never_fall_back(monkeypatch, model, key):
    monkeypatch.setenv("GEMINI_API_KEY", key)
    client = Mock(side_effect=AssertionError("No OpenAI fallback"))
    monkeypatch.setattr(audit, "OpenAI", client)
    records = []
    with pytest.raises(ValueError):
        audit._completion(model, [{"role": "system", "content": audit.ADJUDICATION_SYSTEM_PROMPT}], records=records)
    if model.endswith("-latest"):
        assert records == []
        return
    assert records[0]["generation_settings"] is None
    assert records[0]["error_type"] == "ValueError"
    client.assert_not_called()


def test_gemini_empty_and_non_json_responses_fail_loudly(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    for text in ("", "not JSON", "[]"):
        _fake_google(monkeypatch, text)
        with pytest.raises(ValueError):
            audit._completion("gemini-3.1-pro-preview", [{"role": "system", "content": audit.ADJUDICATION_SYSTEM_PROMPT}])


def test_gemini_rejects_non_inline_image_before_request(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    constructor, generate = _fake_google(monkeypatch)
    with pytest.raises(ValueError, match="base64 image data URLs"):
        audit._completion("gemini-3.1-pro-preview", [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "https://example.test/private.png"}}]}])
    constructor.assert_not_called(); generate.assert_not_called()


def test_every_audit_records_the_settings_sent_by_both_providers(pair_factory, monkeypatch):
    inventory, final = _responses()
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    _fake_google(monkeypatch, json.dumps(final))
    response = SimpleNamespace(
        id="inventory-id", model="resolved-inventory", usage=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(inventory)))],
    )
    client = Mock()
    client.__enter__ = Mock(return_value=SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(return_value=response))),
    ))
    client.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(audit, "OpenAI", Mock(return_value=client))
    monkeypatch.setattr(audit, "DefaultHttpxClient", Mock())
    monkeypatch.setattr(audit, "check_audit_models", lambda config: {
        "stages": {stage: {**value, "model_listed": True, "listed_at": "2026-01-01T00:00:00Z"}
                   for stage, value in config.items()}})
    result = _run(pair_factory(), None)
    assert [(call["provider"], call["response_model"]) for call in result["calls"]] == [
        ("openai", "resolved-inventory"), ("google", "resolved-gemini"),
    ]
    for stage in ("inventory", "adjudication"):
        settings = result["generation_settings"][stage]
        assert settings["injected_complete"] is False
        assert len(settings["actual"]) == 1
        assert "temperature" not in settings["actual"][0]
        assert "seed" not in settings["actual"][0]
        assert settings["requested"] == settings["actual"][0]
    assert result["generation_settings"]["inventory"]["actual"][0]["response_format"] == {"type": "json_object"}
    assert result["generation_settings"]["adjudication"]["actual"][0]["response_mime_type"] == "application/json"
    assert "thinking_config" not in result["generation_settings"]["adjudication"]["actual"][0]
    assert result["generation_settings"]["adjudication"]["actual"][0]["media_resolution"] == "MEDIA_RESOLUTION_HIGH"
    assert result["input_fingerprints"]["frozen_rubric"] == result["frozen_rubric_sha256"]
    assert result["input_fingerprints"]["screenshot_sources"].keys() == {"screenshot0.png", "screenshot1.png"}
    assert result["input_fingerprints"]["dom_sources"].keys() == {"dom_model0.txt", "dom_model1.txt"}


def test_post_adjudication_conflicts_are_recorded_not_overridden(pair_factory):
    pair = pair_factory()
    inventory, final = _responses()
    inventory["criteria"][0]["dom_model"] = _source_decision("dom_model", coverage="ABSENT")
    inventory["criteria"][1]["screenshot"] = _source_decision("screenshot", coverage="ABSENT")
    final["criteria"][0]["screenshot_evidence_loss"] = _finding(True, modality="dom_model")
    final["criteria"][1]["dom_model_evidence_loss"] = _finding(True, modality="screenshot")
    result = _run(pair, _complete(inventory, final))
    assert result["schema_version"] == "automated-evidence-audit/v5"
    assert result["prompt_version"].endswith("/v5")
    assert result["criteria"][0]["screenshot_evidence_loss"] is True
    assert result["criteria"][1]["dom_model_evidence_loss"] is True
    assert all(r["coverage_conflict"] for r in result["criteria"])
    assert result["metrics"]["coverage_conflicts"] == {"criteria": 2, "flags": 2, "details": 4}
    assert result["criteria"][1]["requires_human_review"] is True
    assert result["criteria"][0]["requires_human_review"] is True
    aggregate = audit.aggregate_audits([result])
    assert aggregate["requires_human_review"]["count"] == 2
    assert {item["criterion_index"] for item in aggregate["requires_human_review"]["items"]} == {0, 1}
    assert len(aggregate["coverage_conflict_list"]) == 2
    for side in ("screenshot", "dom_model"):
        agreement = aggregate["metrics"]["inventory_adjudication_agreement"][side]
        assert agreement["added"] == 1 and agreement["not_proposed"] == 1
    assert result["generation_settings"]["inventory"]["actual"] == []
    assert result["generation_settings"]["adjudication"]["injected_complete"] is True


@pytest.mark.parametrize("side", ["screenshot", "dom_model"])
@pytest.mark.parametrize("proposal,confirmed,status", [(True, True, "confirmed"), (True, False, "rejected"), (False, True, "added"), (False, False, "not_proposed")])
def test_agreement_covers_all_four_states_with_complete_hook(pair_factory, side, proposal, confirmed, status):
    pair = pair_factory()
    inventory, final = _responses()
    counterpart = "dom_model" if side == "screenshot" else "screenshot"
    inventory["criteria"][0][side + "_evidence_loss"] = proposal
    if proposal:
        inventory["criteria"][0][side] = _source_decision(side, coverage="PARTIAL")
    final["criteria"][0][side + "_evidence_loss"] = _finding(confirmed, modality=counterpart)
    result = _run(pair, _complete(inventory, final))
    decision = result["criteria"][0]["loss_agreement"][side]
    assert decision == {"inventory_proposed": proposal, "adjudicator_confirmed": confirmed, "status": status}
    totals = result["metrics"]["inventory_adjudication_agreement"][side]
    assert totals[status] == (2 if status == "not_proposed" else 1)
    assert totals["compared"] == 2
    assert totals["disagreement_count"] == int(proposal != confirmed)


@pytest.mark.parametrize("stage", ["inventory", "adjudication"])
def test_validation_retry_logs_loss_and_miss_flips_without_overriding(pair_factory, stage):
    pair = pair_factory()
    inventory, final = _responses()
    inventory["criteria"][0]["screenshot"] = _source_decision("screenshot", coverage="PARTIAL")
    inventory["criteria"][0]["screenshot_evidence_loss"] = True
    final["criteria"][0]["screenshot_evidence_loss"] = _finding(True, modality="dom_model")
    invalid = deepcopy(inventory if stage == "inventory" else final)
    if stage == "inventory":
        invalid["criteria"][0]["screenshot_evidence_loss"] = False
        invalid["criteria"][0]["screenshot"]["verifier_caught"] = False
        invalid["criteria"][0]["dom_model"]["citations"][0]["quote"] = "not in source"
    else:
        invalid["criteria"][0]["screenshot_evidence_loss"] = {**_finding(), "bad": "schema"}
        invalid["criteria"][0]["screenshot_verifier_miss"] = _finding(True, modality="screenshot")
    seen = {"inventory": 0, "adjudication": 0}
    def complete(model, messages):
        current = "adjudication" if model.startswith("gemini-") else "inventory"
        seen[current] += 1
        if current == stage and seen[current] == 1:
            return deepcopy(invalid)
        return deepcopy(final if current == "adjudication" else inventory)
    result = _run(pair, complete)
    output = result["primary_auditor_output" if stage == "inventory" else "adjudicator_output"]
    receipt = output["invalid_attempts"][0]
    assert receipt["raw_response"] == invalid
    assert receipt["flag_flips_detected"] is True
    assert {f["flag"] for f in receipt["flag_flips"]} == {"screenshot_evidence_loss", "screenshot_verifier_miss"}
    assert result["criteria"][0]["screenshot_evidence_loss"] is True
    assert result["metrics"]["retry_flag_flips"] == 2


def test_retry_missing_flags_remain_unknown_not_false():
    receipts = [{"raw_response": {"criteria": []}}]
    inventory, _ = _responses()
    inventory["criteria"][0]["screenshot_evidence_loss"] = True
    audit._record_retry_flag_changes(receipts, inventory, inventory=True)
    assert receipts[0]["flag_flips"] == []
    assert len(receipts[0]["uncomparable_flags"]) == 8
    audit._record_retry_flag_changes([{"raw_response": {"criteria": [{"criterion_index": 0, "screenshot": "bad"}]}}], inventory, inventory=True)


@pytest.mark.parametrize("field", ["schema_version", "prompt_version", "audit_model", "adjudicator_model"])
def test_aggregation_rejects_each_protocol_mismatch(field):
    first, second = _audit("a", [_row()]), _audit("b", [_row()])
    second[field] += "-different"
    with pytest.raises(ValueError, match=field):
        audit.aggregate_audits([first, second])
    del second[field]
    with pytest.raises(ValueError, match=field):
        audit.aggregate_audits([first, second])


def test_relative_reduction_reports_undefined_resamples_without_dropping_other_intervals():
    values = [_audit("a", [_row(screen_loss=True)]), _audit("b", [_row(dom_loss=True)])]
    summary = audit.aggregate_audits(values)
    ratio = summary["confidence_intervals"]["relative_reduction"]
    assert ratio["estimate"] == 0
    assert ratio["ci95"] == [0, 1]
    assert 0 < ratio["undefined_resamples"] < 20000
    assert ratio["defined_resamples"] + ratio["undefined_resamples"] == 20000
    assert summary["confidence_intervals"]["screenshot_evidence_loss"]["ci95"] == [0, 1]
    assert ratio == audit.aggregate_audits(list(reversed(values)))["confidence_intervals"]["relative_reduction"]


def test_relative_reduction_all_zero_screenshot_and_negative_values():
    zero = audit.aggregate_audits([_audit("a", [_row()]), _audit("b", [_row()])])
    ratio = zero["confidence_intervals"]["relative_reduction"]
    assert ratio["estimate"] is None and ratio["ci95"] is None
    assert ratio["undefined_resamples"] == 20000
    assert ratio["status"] == "all_resamples_undefined"
    negative = audit.aggregate_audits([_audit(task, [_row(screen_loss=True, dom_loss=True), _row(dom_loss=True)]) for task in ("a", "b")])
    assert negative["confidence_intervals"]["relative_reduction"]["estimate"] == -1
    assert negative["confidence_intervals"]["relative_reduction"]["ci95"] == [-1, -1]
