"""Effective request policies for resume and cross-run comparison."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from .verifier.batch import judge_transport, POLICY_VERSION as BATCH_POLICY_VERSION
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SETTINGS_VERSION = "effective-settings/v1"
ROOT = Path(__file__).resolve().parents[1]
_EXCLUDED = {"api_key", "api-key", "apikey", "key", "password", "secret", "secret_key", "token", "access_token", "api_token", "bearer_token", "azure_ad_token", "authorization",
    "credentials", "port", "container_name", "compose_project_name", "image", "image_name", "image_tag",
    "image_reference", "path", "file", "directory", "location", "source_catalog", "recorder_code_sha256"}


def _excluded(key):
    name = str(key).lower()
    return name in _EXCLUDED or name.endswith(("_api_key", "_password", "_secret", "_port", "_path", "_paths", "_file", "_files", "_directory", "_directories", "_dir"))


def _url(value):
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    query = urlencode([(key, val) for key, val in parse_qsl(parsed.query) if not _excluded(key)])
    return urlunsplit((parsed.scheme, host, parsed.path.rstrip("/"), query, ""))


def normalized_settings(value):
    if isinstance(value, dict):
        return {str(key): (_url(child) if str(key).endswith(("base_url", "endpoint")) and isinstance(child, str) else normalized_settings(child))
            for key, child in sorted(value.items()) if not _excluded(key)}
    if isinstance(value, (tuple, list)):
        return [normalized_settings(child) for child in value]
    if isinstance(value, (set, frozenset)):
        return sorted(normalized_settings(child) for child in value)
    return value


def settings_hash(value):
    return hashlib.sha256(json.dumps(normalized_settings(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8", errors="backslashreplace")).hexdigest()


def settings_differences(recorded, current, prefix=""):
    recorded, current = normalized_settings(recorded), normalized_settings(current)
    if isinstance(recorded, dict) and isinstance(current, dict):
        result = []
        for key in sorted(set(recorded) | set(current)):
            label = f"{prefix}.{key}" if prefix else key
            if key not in recorded or key not in current:
                result.append({"field": label, "recorded": recorded.get(key), "current": current.get(key)})
            else:
                result.extend(settings_differences(recorded[key], current[key], label))
        return result
    return [] if recorded == current else [{"field": prefix or "settings", "recorded": recorded, "current": current}]


def require_same_settings(recorded, current, *, label="run"):
    differences = settings_differences(recorded, current)
    if differences:
        raise ValueError(f"{label} effective settings differ: " + json.dumps(differences, sort_keys=True))


def comparison_settings(settings, *, include_rubric=False):
    result = normalized_settings(settings)
    if isinstance(result, dict) and not include_rubric:
        result = {key: value for key, value in result.items() if key != "rubric_sha256"}
    return result


def browser_source_version(manifest=None, *, root=ROOT):
    pin = json.loads((Path(root) / "protocol/browser-build.json").read_text())
    selected = {key: pin.get(key) for key in ("chromium_version", "overlay_revision", "protocol_sha256")}
    return selected


def actual_browser_source_version(manifest):
    build = (manifest.get("browser_profile_provenance") or {}).get("browser_build") or {}
    return {key: build[key] for key in ("image_source_revision", "overlay_revision", "chromium_revision", "protocol_sha256")
        if build.get(key) is not None}


def actor_settings(controls, *, browser_source=None):
    from .task_recorder.runner import ACTION_SCHEMA, SCREENSHOT_ACTION_SCHEMA, ACTOR_PROTOCOL, MAX_TASK_MEMORY_CHARS, ACTOR_INPUT_TOKEN_LIMIT, ACTOR_IMAGE_INPUT_TOKENS
    from .task_recorder.prompts import DOM_PROMPT, SCREENSHOT_PROMPT, SCREENSHOT_PROMPT_VERSION, DOM_PROMPT_VERSION
    defaults = {"model": controls.get("model") or os.environ.get("ACTOR_MODEL", ""), "provider": "google", "route": "models/{model}:generateContent",
        "base_url": "https://generativelanguage.googleapis.com/v1beta", "reasoning_effort": "medium",
        "max_output_tokens": 10000, "max_turns": 200, "memory_max_chars": MAX_TASK_MEMORY_CHARS,
        "temperature": None, "media_resolution": os.environ.get("ACTOR_MEDIA_RESOLUTION", "ULTRA_HIGH").strip().upper(), "viewport": [1365, 768], "settle_seconds": 1.0,
        "browser_lang": "en-US", "browser_accept_language": "en-US,en;q=0.9",
        "snapshot_max_nodes": 7000, "snapshot_max_text_chars": 200000,
        "agent_browser_timeout": 90.0, "cdp_timeout": 90.0, "transport_timeout": 180.0,
        "max_consecutive_rejections": 4, "human_intervention": False, "automatic_redirects": False,
        "keep_existing_tabs": False}
    selected = {key: controls.get(key, value) for key, value in defaults.items()}
    selected["media_resolution"] = str(selected["media_resolution"]).strip().upper()
    selected.update(schema_version=SETTINGS_VERSION, actor_protocol=ACTOR_PROTOCOL,
        schema_sha256=settings_hash(ACTION_SCHEMA),
        history_policy="actor-history/v2", progress_policy="observation-change/v2",
        stall_policy={"mode": "advisory", "symmetric": True},
        capture_policy={"raw_order": ["structured_dom", "screenshot", "executable_refs"],
            "refs_dom_only": True, "projection_after_raw": True, "recapture": False},
        input_size_policy={"method": "local_estimate_then_countTokens/v1", "input_limit_source": "models.get_or_configured",
            "model_input_limit": ACTOR_INPUT_TOKEN_LIMIT, "estimate": "utf8_bytes_plus_fixed_image/v1",
            "image_tokens": ACTOR_IMAGE_INPUT_TOKENS, "count_threshold_percent": 50,
            "count_retry_attempts": 3, "safe_input_percent": 95, "truncate": False},
        observation_contracts={"dom": {"schema_sha256": settings_hash(ACTION_SCHEMA), "prompt_version": DOM_PROMPT_VERSION},
            "screenshot": {"schema_sha256": settings_hash(SCREENSHOT_ACTION_SCHEMA),
                "prompt_version": SCREENSHOT_PROMPT_VERSION, "coordinate_units": "normalized_1000",
                "media_resolution": selected["media_resolution"]}},
        transport_retry_policy={"attempts": 3, "backoff_seconds": [2, 8], "jitter_seconds": [0, 0.5],
            "statuses": [429, 500, 502, 503, 504], "turn_policy": "actor-response-turn/v2"},
        technical_retry_policy={"attempts": 2, "fresh_browser": True, "observation_recovery_attempts": 1,
            "liveness_timeout_seconds": 3, "browser_failure_checks": [
                "before_actor_request", "after_actor_response", "before_terminal_acceptance"]},
        prompt_sha256={"dom": hashlib.sha256(DOM_PROMPT.encode()).hexdigest(),
            "screenshot": hashlib.sha256(SCREENSHOT_PROMPT.encode()).hexdigest()},
        browser_source=browser_source or browser_source_version())
    return normalized_settings(selected)


def endpoint_settings(path):
    path = Path(path)
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    result = {}
    for source in files:
        payload = json.loads(source.read_text())
        provider = payload.get("CHAT_COMPLETION_PROVIDER", "openai")
        kwargs = payload.get("CHAT_COMPLETION_KWARGS_JSON", {})
        if isinstance(kwargs, str):
            kwargs = json.loads(kwargs)
        model = kwargs.get("model", "")
        base = kwargs.get("base_url") or ("https://generativelanguage.googleapis.com/v1beta/openai/" if provider == "google"
            else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        row = normalized_settings({"model": model, "provider": provider, "route": "chat/completions", "base_url": base,
            "reasoning_effort": kwargs.get("reasoning_effort"), "temperature": kwargs.get("temperature"),
            "max_output_tokens": kwargs.get("max_completion_tokens", kwargs.get("max_tokens")),
            "config_sha256": settings_hash(payload), "request_settings": {key: value for key, value in kwargs.items()
                if key not in {"model", "max_retries", "model_capabilities", "api_key", "base_url"}}})
        result.setdefault(model, []).append(row)
    return {model: sorted(rows, key=lambda row: json.dumps(row, sort_keys=True)) for model, rows in sorted(result.items())}


def _native_prompts(mode):
    prompts = importlib.import_module(f"w8bench.verifier.{mode}.prompts")
    values = {name: value for name, value in vars(prompts).items() if name.isupper() and isinstance(value, str)}
    return settings_hash(values)


def completion_settings(recording, *, rubric_hash, judge_model, base_url, evidence_policy):
    from .model_identity import MODEL_ACCEPTANCE_POLICY
    from .verifier.completion import COMPLETION_POLICY_VERSION, GRADE_SCHEMA, JUDGE_PROMPT
    return normalized_settings({"schema_version": SETTINGS_VERSION, "rubric_sha256": rubric_hash,
        "browser_source": browser_source_version(), "models": [judge_model], "provider": "openai",
        "route": "responses", "base_url": base_url, "reasoning_effort": "medium", "temperature": None,
        "max_output_tokens": 10000, "max_attempts": 1, "evidence_policy": evidence_policy,
        "prompt_sha256": hashlib.sha256(JUDGE_PROMPT.encode()).hexdigest(), "schema_sha256": settings_hash(GRADE_SCHEMA),
        "transport": judge_transport(), "batch_policy_version": BATCH_POLICY_VERSION,
        "policy_version": COMPLETION_POLICY_VERSION, "acceptance_policy_version": MODEL_ACCEPTANCE_POLICY})


def evaluation_settings(recording, *, eval_config, rubric_hash, judge_model, evidence_policy="paired"):
    from .model_identity import MODEL_ACCEPTANCE_POLICY
    from .verifier.completion import COMPLETION_POLICY_VERSION, GRADE_SCHEMA, JUDGE_PROMPT
    from .verifier.audit_requests import (ADJUDICATION_SYSTEM_PROMPT, SYSTEM_PROMPT, GEMINI_GENERATION_SETTINGS,
        OPENAI_GENERATION_SETTINGS, resolve_audit_config)
    from .verifier.evidence_audit import SCHEMA_VERSION, PROMPT_VERSION
    from .verifier.common import native_judge_model, CANONICAL_RUBRIC_MODEL, CANONICAL_SETTINGS
    endpoints = endpoint_settings(eval_config)
    source = browser_source_version(recording.get("manifest"))
    stages = {"completion": {"models": [judge_model], "provider": "openai", "route": "responses",
        "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"), "reasoning_effort": "medium",
        "temperature": None, "max_output_tokens": 10000, "max_attempts": 1,
        "prompt_sha256": hashlib.sha256(JUDGE_PROMPT.encode()).hexdigest(), "schema_sha256": settings_hash(GRADE_SCHEMA),
        "transport": judge_transport(), "batch_policy_version": BATCH_POLICY_VERSION,
        "policy_version": COMPLETION_POLICY_VERSION, "acceptance_policy_version": MODEL_ACCEPTANCE_POLICY,
        "evidence_policy": evidence_policy}}
    native_model = native_judge_model()
    for mode in ("screenshot_verifier", "dom_model"):
        stages[mode] = {"models": [native_model, native_model],
            "endpoints": {model: endpoints.get(model, []) for model in (native_model,)},
            "prompt_sha256": _native_prompts(mode), "schema_version": "finite-earned-points/v2",
            "judge_profile": os.environ.get("NATIVE_JUDGE_PROFILE", "primary"),
            "transport": judge_transport(), "batch_policy_version": BATCH_POLICY_VERSION,
            "scoring_controls": CANONICAL_SETTINGS, "input_token_limit": 115000, "validation_attempts": 5,
            "max_output_tokens": None, "temperature": None, "dom_state_char_budget": 350000 if mode == "dom_model" else None,
            "evidence_policy": mode}
    audit = resolve_audit_config(model=os.environ.get("EVIDENCE_AUDIT_MODEL") or "gemini-3.1-pro-preview",
        adjudicator_model=os.environ.get("EVIDENCE_ADJUDICATOR_MODEL") or "gpt-6.1-sol",
        audit_provider=os.environ.get("EVIDENCE_AUDIT_PROVIDER") or "google",
        adjudicator_provider=os.environ.get("EVIDENCE_ADJUDICATOR_PROVIDER") or "openai")
    for stage in ("inventory", "adjudication"):
        selected = audit[stage];google = selected["provider"] == "google"
        stages[stage] = {"models": [selected["model"]], "provider": selected["provider"],
            "route": "models/{model}:generateContent" if google else "chat/completions",
            "base_url": "https://generativelanguage.googleapis.com/v1beta" if google else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "reasoning_effort": None, "max_output_tokens": None, "temperature": None,
            "generation_settings": GEMINI_GENERATION_SETTINGS if google else OPENAI_GENERATION_SETTINGS,
            "prompt_sha256": hashlib.sha256((SYSTEM_PROMPT if stage == "inventory" else ADJUDICATION_SYSTEM_PROMPT).encode()).hexdigest(),
            "schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION,
            "transport": judge_transport(), "batch_policy_version": BATCH_POLICY_VERSION,
            "acceptance_policy_version": MODEL_ACCEPTANCE_POLICY, "validation_attempts": 3, "evidence_policy": "eligible_same_run_paired"}
    stages["rubric_preparation"] = {"models": [CANONICAL_RUBRIC_MODEL], "endpoints": endpoints.get(CANONICAL_RUBRIC_MODEL, []),
        "prompt_sha256": _native_prompts("screenshot_verifier"), "schema_version": "frozen-rubric/v1",
        "transport": "normal", "max_output_tokens": None, "evidence_policy": "task_instruction_and_start_url"}
    return normalized_settings({"schema_version": SETTINGS_VERSION,
        "actor": actor_settings(recording.get("manifest", {}).get("controls", {}), browser_source=source),
        "browser_source": source, "rubric_sha256": rubric_hash, "stages": stages})


def stage_settings(settings, name):
    selected = (settings or {}).get("stages", {})
    stage = {key: selected[key] for key in ("inventory", "adjudication") if key in selected} if name == "audit" else selected.get("completion" if name == "paired_completion" else name, {})
    return {"schema_version": SETTINGS_VERSION, "rubric_sha256": (settings or {}).get("rubric_sha256"),
        "browser_source": (settings or {}).get("browser_source"), "stage": stage}


def preparation_settings(eval_config, *, task_hash=None):
    from .verifier.common import CANONICAL_RUBRIC_MODEL
    from .verifier.screenshot_verifier.prompts import RUBRIC_GENERATION_PROMPT_TEMPLATE, RUBRIC_DEPENDENCY_CHECKING_PROMPT, SCORING_PROMPT_VERSION
    endpoints = endpoint_settings(eval_config)
    return normalized_settings({"schema_version": SETTINGS_VERSION, "task_sha256": task_hash,
        "models": [CANONICAL_RUBRIC_MODEL], "endpoints": endpoints.get(CANONICAL_RUBRIC_MODEL, []),
        "prompt_sha256": settings_hash({"generation": RUBRIC_GENERATION_PROMPT_TEMPLATE, "dependency": RUBRIC_DEPENDENCY_CHECKING_PROMPT}),
        "prompt_version": SCORING_PROMPT_VERSION, "schema_version_policy": "frozen-rubric/v1",
        "max_output_tokens": None, "validation_attempts": 5, "input_token_limit": 115000,
        "evidence_policy": "task_instruction_and_start_url", "browser_source": browser_source_version()})


def native_stage_settings(args, mode, *, rubric_hash):
    from .verifier.common import CANONICAL_ACTION_MODEL, CANONICAL_JUDGE_MODEL
    endpoints = endpoint_settings(args.eval_config)
    models = [getattr(args, "action_model", CANONICAL_ACTION_MODEL), getattr(args, "judge_model", CANONICAL_JUDGE_MODEL)]
    controls = {name: getattr(args, name, default) for name, default in {
        "rubric_threshold": .8, "majority_vote_instances": 1, "success": "outcome",
        "max_evidence_items_per_criterion": getattr(args, "max_images_per_criterion", getattr(args, "max_evidence_per_criterion", 5)),
        "min_relevance_threshold": 0, "dom_model_state_char_budget": 350000}.items()}
    return normalized_settings({"schema_version": SETTINGS_VERSION, "rubric_sha256": rubric_hash,
        "models": models, "endpoints": {model: endpoints.get(model, []) for model in models},
        "prompt_sha256": _native_prompts(mode), "schema_version_policy": "finite-earned-points/v2",
        "judge_profile": os.environ.get("NATIVE_JUDGE_PROFILE", "primary"),
        "transport": judge_transport(), "batch_policy_version": BATCH_POLICY_VERSION,
        "scoring_controls": controls, "validation_attempts": 5, "input_token_limit": 115000,
        "evidence_policy": mode, "browser_source": browser_source_version()})


def guard_result_settings(path, current, *, label):
    path = Path(path)
    if path.is_file():
        previous = json.loads(path.read_text())
        require_same_settings(previous.get("effective_settings"), current, label=label)


def audit_settings(config, *, rubric_hash=None):
    from .model_identity import MODEL_ACCEPTANCE_POLICY
    from .verifier.audit_requests import SYSTEM_PROMPT, ADJUDICATION_SYSTEM_PROMPT, GEMINI_GENERATION_SETTINGS, OPENAI_GENERATION_SETTINGS
    from .verifier.evidence_audit import SCHEMA_VERSION, PROMPT_VERSION
    stages = {}
    for name, selected in config.items():
        google = selected["provider"] == "google"
        stages[name] = {"models": [selected["model"]], "provider": selected["provider"],
            "route": "models/{model}:generateContent" if google else "chat/completions",
            "base_url": "https://generativelanguage.googleapis.com/v1beta" if google else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "reasoning_effort": None, "max_output_tokens": None, "temperature": None,
            "generation_settings": GEMINI_GENERATION_SETTINGS if google else OPENAI_GENERATION_SETTINGS,
            "prompt_sha256": hashlib.sha256((SYSTEM_PROMPT if name == "inventory" else ADJUDICATION_SYSTEM_PROMPT).encode()).hexdigest(),
            "schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION,
            "transport": judge_transport(), "batch_policy_version": BATCH_POLICY_VERSION,
            "acceptance_policy_version": MODEL_ACCEPTANCE_POLICY, "validation_attempts": 3,
            "evidence_policy": "eligible_same_run_paired"}
    return normalized_settings({"schema_version": SETTINGS_VERSION, "rubric_sha256": rubric_hash,
        "browser_source": browser_source_version(), "stages": stages})
