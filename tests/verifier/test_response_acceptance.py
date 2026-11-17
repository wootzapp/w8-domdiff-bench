"""Completion and audit response identity, completeness and usage contracts."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from w8bench.verifier import audit_requests, completion, run_comparison


@pytest.mark.parametrize("returned", [None, "gpt-5.2", "gpt-6.1-sol-mini"])
def test_completion_refuses_other_or_missing_judge_ids_and_keeps_usage(completion_case, returned):
    case = completion_case
    case.responses.append({"model": returned, "status": "completed", "usage": {"input_tokens": 7, "output_tokens": 3},
        "output_text": json.dumps({"criteria": [{"id": name, "verdict": "success", "reason": "Visible marker", "states": [1]}
            for name in ("saved", "source")]})})
    grade = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gpt-6.1-sol", api_key="offline", execute=True))
    assert grade["verdict"] == grade["method"] == "ungraded"
    assert grade["usage"] == {"input_tokens": 7, "output_tokens": 3}
    assert grade["model_id_match"]["matched"] is False
    assert grade["refusal_reason"]


@pytest.mark.parametrize("returned,form", [("gpt-6.1-sol", "exact"),
    ("gpt-6.1-sol-2026-09-29", "suffix"), ("gpt-6.1-sol-001", "suffix")])
def test_completion_records_accepted_model_form(completion_case, returned, form):
    case = completion_case
    case.responses.append({"model": returned, "status": "completed", "usage": {"input_tokens": 7, "output_tokens": 3},
        "output_text": json.dumps({"criteria": [{"id": name, "verdict": "success", "reason": "Visible marker", "states": [1]}
            for name in ("saved", "source")]})})
    grade = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gpt-6.1-sol", api_key="offline", execute=True))
    assert grade["verdict"] == "success"
    assert grade["model_id_match"]["form"] == form
    assert grade["acceptance_policy_version"]


@pytest.mark.parametrize("metadata", [{"status": "incomplete"}, {"truncated": True},
    {"output_limit_hit": True}, {"usage": {"input_tokens": 7, "output_tokens": 10000}}])
def test_completion_refuses_incomplete_or_capped_output(completion_case, metadata):
    case = completion_case
    case.responses.append({"model": "gpt-6.1-sol", "status": "completed", "usage": {"input_tokens": 7, "output_tokens": 3},
        "output_text": json.dumps({"criteria": [{"id": name, "verdict": "success", "reason": "Visible marker", "states": [1]}
            for name in ("saved", "source")]}), **metadata})
    grade = asyncio.run(completion.grade_run(case.run, case.rubric_path,
        judge_model="gpt-6.1-sol", api_key="offline", execute=True))
    assert grade["verdict"] == "ungraded"
    assert grade["refusal_reason"] and grade["judge_calls"] == 1


@pytest.mark.parametrize("returned,incomplete", [(None, False), ("gpt-5.2", False), ("gpt-6.1-sol", True)])
def test_audit_refuses_response_metadata_and_retains_each_call(monkeypatch, returned, incomplete):
    def respond(model, messages, record, hooks):
        record.update(response_model=returned, incomplete=incomplete, usage={"prompt_tokens": 9, "completion_tokens": 2})
        return '{}'
    monkeypatch.setattr(audit_requests, "_openai_completion", respond)
    records = []
    with pytest.raises(ValueError, match="model|incomplete"):
        audit_requests._completion("gpt-6.1-sol", [{"role": "system", "content": audit_requests.ADJUDICATION_SYSTEM_PROMPT}], records=records)
    assert len(records) == 1 and records[0]["usage"]["prompt_tokens"] == 9
    assert records[0]["refusal_reason"]


@pytest.mark.parametrize("field", ["instruction", "start_url"])
def test_rubric_import_refuses_definition_drift_before_writing(tmp_path, field):
    task = {"source_task_id": "one", "instruction": "Read the marker", "start_url": "https://example.test"}
    supplied = {"task_id": "one", "instruction": task["instruction"], "start_url": task["start_url"],
        "criteria": [{"id": "marker", "description": "Marker visible"}]}
    supplied[field] = "Another task" if field == "instruction" else "https://other.test"
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps(supplied))
    root = tmp_path / "evaluation"
    with pytest.raises(ValueError, match=field):
        run_comparison._prepare_rubric(SimpleNamespace(rubric=path), root, task, Mock())
    assert not root.exists()


@pytest.mark.parametrize("prompt,candidates,thoughts,total", [(None, None, None, None),
    (7, 3, None, None), (None, 3, 2, None), (7, 3, 2, 12)])
def test_audit_usage_keeps_unknown_components_and_partial_lower_bounds(prompt, candidates, thoughts, total):
    from google.genai.types import GenerateContentResponseUsageMetadata
    usage = GenerateContentResponseUsageMetadata(prompt_token_count=prompt,
        candidates_token_count=candidates, thoughts_token_count=thoughts, total_token_count=total)
    response = SimpleNamespace(usage_metadata=usage, response_id="offline", model_version="gemini-3.1-pro-preview",
        candidates=[], text='{}')
    record = {}
    audit_requests._record_gemini_response(record, response, {})
    normalized = record["usage"]
    assert normalized["prompt_tokens"] is prompt
    assert normalized["completion_tokens"] == (candidates + thoughts if candidates is not None and thoughts is not None else None)
    assert normalized["total_tokens"] == total
    assert record["usage_coverage"] == ("complete" if prompt is not None and candidates is not None and thoughts is not None else "partial" if any(v is not None for v in (prompt,candidates,thoughts)) else "unknown")
    known = [v for v in (prompt,candidates,thoughts) if v is not None]
    assert record["usage_lower_bound"]["total_tokens"] == (sum(known) if known else None)


@pytest.mark.parametrize("inventory", [False, True])
@pytest.mark.parametrize("eventually_valid", [False, True])
def test_audit_refusals_consume_the_stage_budget_without_losing_usage(monkeypatch, tmp_path, inventory, eventually_valid):
    records, invalid = [], []
    def respond(model, messages, record, hooks):
        accepted = eventually_valid and len(records) == 3
        record.update(response_model=model if accepted else "gpt-5.2", incomplete=False,
            usage={"prompt_tokens": 9, "completion_tokens": 2})
        return '{"criteria":[]}'
    monkeypatch.setattr(audit_requests, "_openai_completion", respond)
    validator = Mock(return_value=[])
    monkeypatch.setattr(audit_requests, "validate_audit_response" if inventory else "validate_adjudication_response", validator)
    def complete(model, messages):
        return audit_requests._completion(model, messages, records=records)
    arguments = dict(model="gpt-6.1-sol", messages=[{"role": "system", "content": audit_requests.SYSTEM_PROMPT if inventory else audit_requests.ADJUDICATION_SYSTEM_PROMPT}],
        criteria=[], screenshot_sources=set(), dom_sources=set(), screenshot_root=tmp_path, dom_root=tmp_path,
        complete=complete, max_attempts=3, invalid_receipts=invalid, inventory=inventory)
    if eventually_valid:
        _, _, attempts = audit_requests._request_validated_audit(**arguments)
        assert attempts == 3 and validator.call_count == 1
    else:
        with pytest.raises(audit_requests.AuditValidationError, match="after 3 attempts"):
            audit_requests._request_validated_audit(**arguments)
        assert validator.call_count == 0
    assert len(records) == 3 and len(invalid) == (2 if eventually_valid else 3)
    assert sum(row["usage"]["prompt_tokens"] for row in records) == 27
    assert all(row["model_id_match"]["form"] == "refused" for row in records[:2])
