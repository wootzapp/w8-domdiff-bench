from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from w8bench.verifier import evidence_audit as audit
from w8bench.verifier import run_comparison, run_full_comparison
from .test_evidence_audit_cross_provider import _fake_google


def test_models_are_required_and_flags_override_environment(monkeypatch):
    monkeypatch.delenv("EVIDENCE_AUDIT_MODEL")
    with pytest.raises(ValueError, match="EVIDENCE_AUDIT_MODEL"):
        audit.resolve_audit_config()
    monkeypatch.setenv("EVIDENCE_AUDIT_MODEL", "gpt-env")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_MODEL", "gemini-env")
    assert audit.resolve_audit_config()["inventory"]["model"] == "gpt-env"
    selected = audit.resolve_audit_config("custom-inventory", "custom-judge", "google", "openai")
    assert selected == {"inventory": {"model": "custom-inventory", "provider": "google"},
                        "adjudication": {"model": "custom-judge", "provider": "openai"}}
    monkeypatch.delenv("EVIDENCE_ADJUDICATOR_MODEL")
    with pytest.raises(ValueError, match="EVIDENCE_ADJUDICATOR_MODEL"):
        audit.resolve_audit_config()


@pytest.mark.parametrize("entry", [run_comparison, run_full_comparison])
def test_cli_model_and_provider_flags(entry):
    args = ["--task", "task_01", "--audit-model", "custom-a", "--adjudicator-model", "custom-b",
            "--audit-provider", "google", "--adjudicator-provider", "openai"]
    if entry is run_comparison:
        args += ["--rubric-file", "rubric.json", "--generation-metrics", "metrics.json"]
    parsed = entry.parse_args(args)
    assert audit.resolve_audit_config(parsed.audit_model, parsed.adjudicator_model,
                                      parsed.audit_provider, parsed.adjudicator_provider)["adjudication"]["model"] == "custom-b"


@pytest.mark.parametrize("model,provider", [("gemini-test", "google"), ("gpt-test", "openai"), ("o3", "openai"), ("o4-mini", "openai")])
def test_provider_inference(model, provider):
    assert audit.resolve_provider(model) == provider


def test_unknown_and_latest_fail_clearly():
    with pytest.raises(ValueError, match="set EVIDENCE"):
        audit.resolve_provider("custom-model")
    assert audit.resolve_provider("custom-model", "google") == "google"
    with pytest.raises(ValueError, match="latest"):
        audit.resolve_provider("gpt-latest", "openai")


def test_model_checks_require_exact_id(monkeypatch):
    constructor = MagicMock()
    constructor.return_value.__enter__.return_value.models.list.return_value = [SimpleNamespace(id="custom-a"), SimpleNamespace(id="custom-b")]
    monkeypatch.setattr(audit, "OpenAI", constructor)
    config = audit.resolve_audit_config("custom-a", "custom-b", "openai", "openai")
    checked = audit.check_audit_models(config)
    assert checked["stages"]["inventory"]["model_listed"] is True
    assert checked["stages"]["inventory"]["listed_at"]
    assert constructor.call_count == 1
    config["inventory"]["model"] = "custom"
    with pytest.raises(ValueError, match="not listed exactly"):
        audit.check_audit_models(config)


@pytest.mark.parametrize("status,retry", [(429, True), (500, True), (503, True), (400, False), (401, False), (403, False), (404, False), (408, False)])
def test_transport_status_retry_policy(monkeypatch, status, retry):
    class Error(Exception):
        status_code = status
    sleeps, record = [], {}
    monkeypatch.setattr(audit.time, "sleep", sleeps.append)
    def fail():
        raise Error("technical error")
    with pytest.raises(Error):
        audit._transport_request(fail, record)
    assert len(record["transport_attempts"]) == (3 if retry else 1)
    assert sleeps == ([1, 2] if retry else [])


def test_connection_retries_are_logged_and_secrets_redacted(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-secret-for-test")
    monkeypatch.setattr(audit.time, "sleep", lambda value: None)
    seen, record = [], {}
    def call():
        seen.append(True)
        if len(seen) < 3:
            raise ConnectionError("fake-secret-for-test")
        return "ok"
    assert audit._transport_request(call, record) == "ok"
    assert len(record["transport_attempts"]) == 3
    assert "fake-secret-for-test" not in str(record)
    assert record["transport_attempts"][-1]["status"] == "accepted"


def test_explicit_google_provider_uses_google_settings_for_any_model_id(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    _, generate = _fake_google(monkeypatch)
    audit._completion("custom-model", [{"role": "system", "content": audit.SYSTEM_PROMPT}], provider="google")
    config = generate.call_args.kwargs["config"]
    assert config["media_resolution"] == "MEDIA_RESOLUTION_HIGH"
    assert "temperature" not in config and "seed" not in config and "thinking_config" not in config
