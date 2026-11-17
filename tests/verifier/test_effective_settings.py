"""Settings identity without credentials or deployment-specific values."""
from copy import deepcopy
import json

import pytest


def test_settings_diff_lists_nested_fields_and_refuses_drift():
    from w8bench.settings import require_same_settings
    before = {"actor": {"model": "one", "max_turns": 200}}
    after = {"actor": {"model": "two", "max_turns": 199}}
    with pytest.raises(ValueError, match=r"actor.max_turns.*actor.model"):
        require_same_settings(before, after, label="scheduled actor")


@pytest.mark.parametrize("excluded", ["api_key", "password", "token", "port", "container_name", "compose_project_name", "image", "image_tag", "path", "file", "directory"])
def test_settings_guard_excludes_credentials_and_deployment_fields(excluded):
    from w8bench.settings import normalized_settings, require_same_settings
    before = {"model": "one", excluded: "first"}
    after = {"model": "one", excluded: "second"}
    assert normalized_settings(before) == {"model": "one"}
    require_same_settings(before, after, label="judge")


def test_effective_config_hash_depends_on_content_not_location_or_credentials(tmp_path):
    from w8bench.settings import endpoint_settings
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir(); second.mkdir()
    config = {"CHAT_COMPLETION_PROVIDER": "openai", "CHAT_COMPLETION_KWARGS_JSON": {
        "model": "gpt-5.2", "reasoning_effort": "medium", "api_key": "first-secret"}}
    (first / "model.json").write_text(json.dumps(config))
    config["CHAT_COMPLETION_KWARGS_JSON"]["api_key"] = "second-secret"
    (second / "another-name.json").write_text(json.dumps(config, indent=2))
    assert endpoint_settings(first) == endpoint_settings(second)
    config["CHAT_COMPLETION_KWARGS_JSON"]["reasoning_effort"] = "high"
    (second / "another-name.json").write_text(json.dumps(config))
    assert endpoint_settings(first) != endpoint_settings(second)
    assert "secret" not in json.dumps(endpoint_settings(first))


@pytest.mark.parametrize("field,value", [("reasoning_effort", "high"), ("max_output_tokens", 9999),
    ("max_turns", 100), ("memory_max_chars", 7000), ("base_url", "https://other.test/v1")])
def test_actor_settings_guard_protects_effective_request_controls(field, value):
    from w8bench.settings import actor_settings, require_same_settings
    controls = {"model": "gemini-3.1-pro-preview", "reasoning_effort": "medium", "max_output_tokens": 10000,
        "max_turns": 200, "memory_max_chars": 8000, "base_url": "https://example.test/v1"}
    changed = {**controls, field: value}
    with pytest.raises(ValueError, match=field):
        require_same_settings(actor_settings(controls), actor_settings(changed), label="actor")


def test_actor_settings_include_both_observation_policies_and_exclude_resource_names():
    from w8bench.settings import actor_settings
    controls = {"model": "gemini-3.1-pro-preview", "max_turns": 200, "image": "first:tag",
        "container_name": "first", "port": 9999}
    settings = actor_settings(controls)
    assert set(settings["prompt_sha256"]) == {"dom", "screenshot"}
    assert settings["memory_max_chars"] == 8000
    assert "container_name" not in settings and "image" not in settings and "port" not in settings


def test_judge_settings_bind_rubric_prompts_schema_and_each_stage(monkeypatch):
    from w8bench.settings import evaluation_settings
    monkeypatch.setenv("EVIDENCE_AUDIT_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("EVIDENCE_ADJUDICATOR_MODEL", "gpt-6.1-sol")
    recording = {"manifest": {"controls": {"model": "gemini-3.1-pro-preview"}}, "task": {}}
    settings = evaluation_settings(recording, eval_config="config", rubric_hash="one", judge_model="gpt-6.1-sol")
    assert settings["rubric_sha256"] == "one"
    assert set(settings["stages"]) == {"completion", "screenshot_verifier", "dom_model", "inventory", "adjudication", "rubric_preparation"}
    for stage in settings["stages"].values():
        assert stage["models"] and stage["prompt_sha256"]
    assert settings["stages"]["completion"]["schema_sha256"]
    assert "base_url" in settings["stages"]["inventory"]
