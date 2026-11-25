"""Multi-endpoint chat completion clients with graceful retry."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx
from google.genai import errors

from .factory import create_client_from_config
from .messages import CreateResult, LLMMessage, Tool, ToolSchema
from .providers import ChatCompletionClient


_KWARGS_JSON_KEY = "CHAT_COMPLETION_KWARGS_JSON"


def _sanitize_extra_args_for_log(extra_create_args: Mapping[str, Any]) -> dict:
    sanitized: dict[str, Any] = {}
    for k, v in extra_create_args.items():
        if k == "input" and isinstance(v, list):
            sanitized[k] = f"[{len(v)} items]"
        else:
            sanitized[k] = v
    return sanitized


@dataclass
class _RetryState:
    client: ChatCompletionClient
    tries: int
    last_error: Exception | None = None


class GracefulRetryClient(ChatCompletionClient):
    """Run completion requests through an endpoint pool and its retry policies."""

    def __init__(
        self,
        clients: list[ChatCompletionClient],
        support_json: bool = True,
        logger: logging.Logger | None = None,
        max_retries: int = 8,
        max_tokens: int = 115000,
        timeout: float | None = None,
        *, evidence_mode: str = "screenshot_verifier",
    ):
        super().__init__(max_tokens=max_tokens, evidence_mode=evidence_mode)
        if not clients:
            raise ValueError("GracefulRetryClient requires at least one client")
        self._clients = clients
        self.logger = logger or logging.getLogger(f"w8bench.verifier.{evidence_mode}.clients.graceful_client")
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.support_json = support_json
        self.blocklist: set = set()
        self._client_idx = random.randint(0, len(clients) - 1)

    def convert_client_type(self, new_client_type: type[ChatCompletionClient]) -> None:
        for client in self._clients:
            convert = getattr(client, "convert_client_type", None)
            if callable(convert):
                convert(new_client_type)

    @staticmethod
    def _should_include_model(
        model_name: str, model_name_filter: str | list[str]
    ) -> bool:
        """Match an endpoint model against exact names or a wildcard."""
        if isinstance(model_name_filter, str):
            model_name_filter = [model_name_filter]
        return any(f == "*" or model_name == f for f in model_name_filter)

    @staticmethod
    def from_files(
        files: Sequence[os.PathLike],
        logger: logging.Logger,
        eval_model: str | list[str],
        *, evidence_mode: str = "screenshot_verifier",
    ) -> "GracefulRetryClient":
        client_jsons = []
        for client_config in files:
            with open(client_config) as f:
                endpoint_config = json.load(f)
            model_name = endpoint_config[_KWARGS_JSON_KEY]["model"]
            if GracefulRetryClient._should_include_model(model_name, eval_model):
                client_jsons.append(endpoint_config)

        clients = [create_client_from_config(config=cfg, evidence_mode=evidence_mode) for cfg in client_jsons]
        if not clients:
            raise ValueError(
                f"Error! None of the models in the input judge config files match "
                f"--eval_model={eval_model} in {list(files)}"
            )
        return GracefulRetryClient(clients=clients, logger=logger, evidence_mode=evidence_mode)

    @staticmethod
    def from_path(
        path: os.PathLike,
        logger: logging.Logger,
        eval_model: str | list[str],
        *, evidence_mode: str = "screenshot_verifier",
    ) -> "GracefulRetryClient":
        endpoint_config = Path(path).resolve()
        if not endpoint_config.exists():
            raise ValueError(f"Endpoint config file {endpoint_config} does not exist.")

        if endpoint_config.is_dir():
            files: list[Path] = [
                p for p in endpoint_config.iterdir() if p.suffix == ".json"
            ]
        else:
            files = [endpoint_config]

        logger.info(f"loaded {len(files)} endpoint configuration files: {path}")
        client_group = GracefulRetryClient.from_files(
            files=files, logger=logger, eval_model=eval_model, evidence_mode=evidence_mode
        )
        logger.info(
            f"Instantiated {len(client_group._clients)} clients for the {eval_model} endpoints"
        )
        return client_group

    def supports_json(self) -> bool:
        return self.support_json

    @staticmethod
    def _is_reasoning_model(description: str) -> bool:
        return any(tag in description for tag in ("gemini-",))

    def _remove_reasoning_effort_if_needed(
        self, client: ChatCompletionClient, extra_create_args: Mapping[str, Any]
    ) -> None:
        if (
            not self._is_reasoning_model(client.description)
            and "reasoning_effort" in extra_create_args
        ):
            del extra_create_args["reasoning_effort"]

    def _validate_token_limit(self, request_tokens: int) -> None:
        if request_tokens and request_tokens > self.max_tokens:
            error_msg = (
                f"PromptTooLargeError: Requesting {request_tokens} tokens exceeding "
                f"{self.max_tokens} is forbidden -- abandoning request"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

    def next_client(self, no_increment: bool = False) -> ChatCompletionClient:
        valid_clients = [c for c in self._clients if c.endpoint not in self.blocklist]
        if not valid_clients:
            raise RuntimeError(
                f"All {len(self._clients)} endpoints are blocked/down. "
                f"Blocklist: {self.blocklist}"
            )
        client = valid_clients[self._client_idx % len(valid_clients)]
        if not no_increment:
            self._client_idx = (self._client_idx + 1) % len(valid_clients)
        return client

    async def close(self) -> None:
        for client in self._clients:
            await client.close()

    async def create(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[Tool | ToolSchema] = (),
        json_output: bool | None = None,
        extra_create_args: Mapping[str, Any] = {},
    ) -> CreateResult:
        tries = self.max_retries
        state = _RetryState(self.next_client(no_increment=True), tries)
        extra = dict(extra_create_args)
        while state.tries > 0:
            request_tokens = state.client.count_tokens(messages=messages)
            self._remove_reasoning_effort_if_needed(state.client, extra)
            self.logger.info(
                f"GracefulRetryClient.create(): {state.client.description}, "
                f"request_tokens: {request_tokens}, "
                f"extra_create_args={_sanitize_extra_args_for_log(extra)}"
            )
            self._validate_token_limit(request_tokens)
            try:
                return await self._call_endpoint(state.client, messages, tools, json_output, extra)
            except Exception as error:
                if not await self._handle_failure(error, state, request_tokens):
                    raise
        self._raise_exhausted(state)

    async def _call_endpoint(self, client, messages, tools, json_output, extra):
        if self.timeout is not None:
            return await asyncio.wait_for(
                client.create(messages=messages, tools=tools, json_output=json_output,
                    extra_create_args=extra),
                timeout=self.timeout,
            )
        return await client.create(messages=messages, tools=tools,
            json_output=json_output, extra_create_args=extra)

    async def _handle_failure(self, error, state, request_tokens):
        code = getattr(error, "code", getattr(error, "status_code", None))
        if isinstance(error, httpx.HTTPStatusError):
            code = error.response.status_code
        if isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException)):
            await self._transient_failure(error, state)
        elif code == 400:
            return await self._bad_request_failure(error, state)
        elif code == 429 or isinstance(code, int) and code >= 500:
            await self._transient_failure(error, state)
        elif code in {403, 404}:
            await self._block_endpoint(error, state, f"HTTP{code}")
        elif isinstance(error, httpx.ConnectError):
            await self._block_endpoint(error, state, "ConnectionError")
        elif code == 401:
            self._authentication_failure(error, state)
        elif isinstance(error, (errors.APIError, httpx.HTTPStatusError)):
            return await self._api_status_failure(error, state, request_tokens)
        else:
            return await self._generic_failure(error, state)
        return True

    async def _switch_client_and_wait(self, state, delay):
        state.client = self.next_client()
        await asyncio.sleep(delay)

    async def _transient_failure(self, error, state):
        if isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException)):
            state.tries -= 1
            self.logger.error(
                f"GracefulRetryClient.create() TimeoutError: {state.client.description} "
                f"timed out after {self.timeout}s, switching client"
            )
            delay = 1
        elif isinstance(getattr(error, "code", None), int) and error.code >= 500:
            self.logger.error(
                f"GracefulRetryClient.create() InternalServerError: {state.client.description}, switching client: {error}"
            )
            state.tries -= 1
            delay = 2
        else:
            state.tries -= 1
            delay = 2 ** (self.max_retries - state.tries)
            self.logger.error(
                f"GracefulRetryClient.create() RateLimitError: {state.client.description}, sleeping {delay}s: {error}"
            )
        await self._switch_client_and_wait(state, delay)

    async def _bad_request_failure(self, error, state):
        if "previous_response_not_found" in str(error):
            self.logger.warning(
                f"GracefulRetryClient.create() previous_response_not_found: {state.client.description}\n{error}"
            )
        elif ("Invalid prompt" in str(error)
                or "content management policy" in str(error)
                or "Please try again with a different prompt" in str(error)):
            self.logger.error(
                f"GracefulRetryClient.create() Invalid prompt: {state.client.description}\n{error}"
            )
        else:
            self.logger.error(
                f"GracefulRetryClient.create() {state.client.description} Raising BadRequestError: {error}"
            )
            return False
        state.tries -= 1
        state.last_error = error
        await self._switch_client_and_wait(state, 0.5)
        return True

    async def _block_endpoint(self, error, state, kind):
        self.logger.error(
            f"GracefulRetryClient.create() {kind}: {state.client.description}, BLOCKING {state.client.endpoint}: {error}"
        )
        self.blocklist.add(state.client.endpoint)
        await self._switch_client_and_wait(state, 1)

    def _authentication_failure(self, error, state):
        state.tries -= 1
        state.last_error = error
        self.logger.error(
            f"GracefulRetryClient.create() AuthenticationError: {state.client.description}: {error}"
        )
        if state.tries <= 0:
            return
        if hasattr(state.client, "refresh_credentials"):
            state.client.refresh_credentials()
        state.client = self.next_client()

    async def _api_status_failure(self, error, state, request_tokens):
        if "Prompt is too large" in str(error):
            self.logger.error(
                f"GracefulRetryClient.create() PromptTooLargeError: ({request_tokens} tokens) is too big\n{error}"
            )
        if "Request body too large" in str(error):
            self.logger.error(
                f"GracefulRetryClient.create() Request body too large: {state.client.description}\n{error}"
            )
            state.tries -= 1
            await self._switch_client_and_wait(state, 1)
            return True
        return False

    async def _generic_failure(self, error, state):
        if "please try again" in str(error).lower():
            state.tries -= 1
            self.logger.error(
                f"GracefulRetryClient.create() Generic Exception: {state.client.description}: {error}"
            )
            state.client = self.next_client()
            delay = 2 ** (self.max_retries - state.tries)
            await asyncio.sleep(delay)
            return True
        self.logger.error(
            f"GracefulRetryClient.create() {state.client.description} Raising Exception: {error}"
        )
        return False

    def _raise_exhausted(self, state):
        if state.last_error:
            raise state.last_error
        valid_clients = [client for client in self._clients if client.endpoint not in self.blocklist]
        raise Exception(
            f"GracefulRetryClient.create(): all clients exhausted after {self.max_retries} attempts; "
            f"{len(valid_clients)}/{len(self._clients)} clients reachable. Blocklist size: {len(self.blocklist)}"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"LlmClient": self._clients[0].description}
