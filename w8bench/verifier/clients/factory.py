"""Construct completion clients and retry pools from endpoint configuration."""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from .providers import ChatCompletionClient, GeminiClientWrapper

ENVIRON_KEY_CHAT_COMPLETION_PROVIDER = "CHAT_COMPLETION_PROVIDER"
ENVIRON_KEY_CHAT_COMPLETION_KWARGS_JSON = "CHAT_COMPLETION_KWARGS_JSON"
_KWARGS_JSON_KEY = ENVIRON_KEY_CHAT_COMPLETION_KWARGS_JSON
_PROVIDER_KEY = ENVIRON_KEY_CHAT_COMPLETION_PROVIDER


def _chat_client(provider, kwargs, evidence_mode):
    if provider != "google":
        raise ValueError("Completion provider must be google")
    kwargs.setdefault("api_key", os.environ.get("GEMINI_API_KEY"))
    if not kwargs["api_key"]:
        raise ValueError("GEMINI_API_KEY is required for Google verifier models")
    kwargs.setdefault("base_url", os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"))
    return GeminiClientWrapper(evidence_mode, **kwargs)


def _pool_configs(kwargs):
    """Yield ordered configurations and their model-filter requirement."""
    for config in kwargs.get("client_configs", []):
        yield config, True
    for path in kwargs.get("config_paths", []):
        with open(path) as stream:
            config = json.load(stream)
        yield config, True
    if kwargs.get("config_dir"):
        path = Path(kwargs["config_dir"]).resolve()
        if path.is_dir():
            for source in path.iterdir():
                if source.suffix == ".json":
                    with open(source) as stream:
                        config = json.load(stream)
                    yield config, True
        elif path.is_file():
            yield path, False


def _retry_pool(kwargs, logger, evidence_mode):
    from .retry import GracefulRetryClient

    log = logger or logging.getLogger(f"w8bench.verifier.{evidence_mode}.clients.create_utils")
    clients = []
    eval_model = kwargs.get("eval_model", "*")
    for config, filter_model in _pool_configs(kwargs):
        if not filter_model:
            with open(config) as stream:
                clients.append(create_client_from_config(json.load(stream),
                    evidence_mode=evidence_mode))
            continue
        model = config.get(_KWARGS_JSON_KEY, {}).get("model", "")
        if eval_model != "*" and not GracefulRetryClient._should_include_model(model, eval_model):
            continue
        clients.append(create_client_from_config(config, evidence_mode=evidence_mode))
    if not clients:
        raise ValueError(f"No clients for graceful_retry. Check config or eval_model: {eval_model}")
    return GracefulRetryClient(clients=clients, logger=log,
        max_retries=kwargs.get("max_retries", 8), max_tokens=kwargs.get("max_tokens", 115000),
        timeout=kwargs.get("timeout"), support_json=kwargs.get("support_json", True),
        evidence_mode=evidence_mode)


def create_client_from_config(
    config: Dict, logger: Optional[logging.Logger] = None,
    *, evidence_mode="screenshot_verifier",
) -> ChatCompletionClient:
    env = copy.deepcopy(config)
    raw_kwargs = env.get(_KWARGS_JSON_KEY, {})
    if isinstance(raw_kwargs, str):
        raw_kwargs = json.loads(raw_kwargs)
    kwargs = dict(raw_kwargs)
    provider = env.get(_PROVIDER_KEY, "google").lower().strip()
    if provider == "google":
        return _chat_client(provider, kwargs, evidence_mode)
    if provider == "graceful_retry":
        return _retry_pool(kwargs, logger, evidence_mode)
    raise ValueError(f"Unknown provider {provider!r}")




def create_client_from_file(
    path: str, logger: Optional[logging.Logger] = None,
    *, evidence_mode="screenshot_verifier",
) -> ChatCompletionClient:
    with open(path, "r") as stream:
        config = json.load(stream)
    return create_client_from_config(config, logger=logger,
        evidence_mode=evidence_mode)
