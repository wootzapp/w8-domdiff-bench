"""Native Google completion transport and per-call accounting."""
from __future__ import annotations

import base64
import json
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

import httpx
import tiktoken
from google import genai
from google.genai import types

from ..batch import judge_transport, http_transport
from .messages import CreateResult, ImageObj, LLMMessage, RequestUsage, ToolSchema, message_to_gemini_format


@dataclass
class ModelCapabilities:
    json_output: bool = True
    function_calling: bool = True
    vision: bool = False


@dataclass
class DomModelCapabilities:
    json_output: bool = True
    function_calling: bool = True


def _image_token_cost(width: int = 1920, height: int = 1080) -> int:
    """Local HIGH-resolution image allowance."""
    return 1100


class ChatCompletionClient:
    """Completion requests, token budgets and call accounting."""

    def __init__(self, max_tokens: Optional[int] = None, *, evidence_mode: str = "screenshot_verifier"):
        self._evidence_mode = evidence_mode
        self.metadata: Dict[str, Any] = {}
        self._last_usage = RequestUsage()
        self._total_usage = RequestUsage()
        self._max_tokens = max_tokens or 115000
        self._encoding = None
        self._call_records: list[dict[str, Any]] = []
        self._http_attempts = 0
        self._http_attempts_observed = False
        self._active_call = ContextVar(f"verifier_call_{id(self)}", default=None)
        self._logical_stage = ContextVar(f"verifier_stage_{id(self)}", default=())

    async def _record_http_request(self, request: httpx.Request) -> None:
        """Encode native thinking settings and record the wire attempt."""
        if request.method == "POST" and request.content:
            payload = json.loads(request.content)
            thinking = (payload.get("generationConfig") or {}).get("thinkingConfig")
            if isinstance(thinking, dict) and "thinking_level" in thinking:
                thinking["thinkingLevel"] = thinking.pop("thinking_level")
                request._content = json.dumps(payload).encode("utf-8")
                request.headers["Content-Length"] = str(len(request._content))
        self._http_attempts += 1
        record = self._active_call.get()
        if record is not None:
            record["http_attempts"] += 1
            record["http_attempts_scope"] = "batch_items_replayed_once_in_final_receipt" if record.get("transport") == "batch" else "provider_http_requests"

    def _start_call(self, record):
        stage_path = self._logical_stage.get()
        record.update(stage=stage_path[0] if stage_path else "unattributed", stage_call_path=list(stage_path))
        self._call_records.append(record)
        return self._active_call.set(record)

    async def create(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[ToolSchema] = (),
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
    ) -> CreateResult:
        raise NotImplementedError

    async def close(self) -> None:
        pass

    def supports_json(self) -> bool:
        return True

    def _get_encoding(self):
        if self._encoding is None:
            self._encoding = tiktoken.get_encoding("cl100k_base")
        return self._encoding

    def count_tokens(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[ToolSchema] = (),
    ) -> int:
        encoding = self._get_encoding()
        total = 0
        for msg in messages:
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if isinstance(content, str):
                total += len(encoding.encode(content))
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        total += len(encoding.encode(item))
                    elif self._evidence_mode == "screenshot_verifier" and isinstance(item, ImageObj):
                        total += _image_token_cost(item.image.width, item.image.height)
                    elif isinstance(item, dict):
                        item_type = item.get("type", "")
                        if self._evidence_mode == "screenshot_verifier" and item_type in ("image_url", "image"):
                            total += _image_token_cost()
                        elif item_type == "text":
                            total += len(encoding.encode(item.get("text", "")))
                        else:
                            total += len(encoding.encode(str(item)))
        for tool in tools:
            total += len(encoding.encode(str(tool)))
        return total

    def remaining_tokens(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[ToolSchema] = (),
    ) -> int:
        return self._max_tokens - self.count_tokens(messages, tools)

    def actual_usage(self) -> RequestUsage:
        return self._last_usage

    def total_usage(self) -> RequestUsage:
        return self._total_usage

    @property
    def capabilities(self) -> ModelCapabilities | DomModelCapabilities:
        return ModelCapabilities() if self._evidence_mode == "screenshot_verifier" else DomModelCapabilities()

    @property
    def endpoint(self) -> str:
        if "model" in self.metadata:
            return self.metadata["model"]
        return "unknown_endpoint"

    @property
    def description(self) -> str:
        if "model" in self.metadata:
            return self.metadata["model"]
        return "unknown_client"


def _to_gemini_messages(messages: Sequence[LLMMessage], *, evidence_mode="screenshot_verifier") -> list[dict]:
    return [message_to_gemini_format(message, evidence_mode=evidence_mode) for message in messages]


def _response_usage(response):
    raw = response if isinstance(response, dict) else (response.model_dump() if hasattr(response, "model_dump") else {})
    native = raw.get("usage_metadata", raw.get("usageMetadata")) or {}
    if not native:
        return raw, {}
    prompt = native.get("prompt_token_count", native.get("promptTokenCount"))
    candidates = native.get("candidates_token_count", native.get("candidatesTokenCount"))
    thoughts = native.get("thoughts_token_count", native.get("thoughtsTokenCount"))
    return raw, {"input_tokens": prompt, "output_tokens": candidates + thoughts
        if candidates is not None and thoughts is not None else None,
        "total_tokens": native.get("total_token_count", native.get("totalTokenCount")),
        "reasoning_tokens": thoughts, "cached_input_tokens": native.get("cached_content_token_count", native.get("cachedContentTokenCount"))}


def _record_usage(response, client, *, record=None):
    raw, values = _response_usage(response)
    usage = RequestUsage(prompt_tokens=values.get("input_tokens") or 0,
        completion_tokens=values.get("output_tokens") or 0, reasoning_tokens=values.get("reasoning_tokens") or 0)
    client._last_usage = usage
    client._total_usage += usage
    if record is not None:
        candidates = raw.get("candidates") or []
        finish = candidates[0].get("finish_reason", candidates[0].get("finishReason")) if candidates else None
        if hasattr(finish, "value"):
            finish = finish.value
        record.update(returned_model=raw.get("model_version", raw.get("modelVersion")),
            response_status=finish, finish_reason=finish, incomplete_details=None,
            output_limit_hit=finish == "MAX_TOKENS" or record.get("max_output_tokens") is not None
                and usage.completion_tokens >= record["max_output_tokens"],
            usage_reported=bool(values), **values, cache_write_input_tokens=None,
            usage_fields_reported={key: values.get(key) is not None for key in
                ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens")})
    return usage


class GeminiClientWrapper(ChatCompletionClient):
    """Native GenerateContent requests through normal or Batch transport."""

    def __init__(self, *mode, **kwargs):
        evidence_mode = mode[0] if mode else "screenshot_verifier"
        super().__init__(max_tokens=kwargs.pop("max_tokens", None), evidence_mode=evidence_mode)
        self.model = kwargs.pop("model")
        if not self.model.startswith("gemini-"):
            raise ValueError("Verifier models must be Gemini model IDs")
        self.metadata = {"model": self.model, "provider": "google"}
        self._api_key = kwargs.pop("api_key", None)
        self._base_url = kwargs.pop("base_url", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        if self._base_url.endswith("/v1beta"):
            self._base_url = self._base_url[:-len("/v1beta")]
        self._default_reasoning_effort = kwargs.pop("reasoning_effort", None)
        kwargs.pop("model_capabilities", None)
        kwargs.pop("max_retries", None)
        kwargs.pop("provider", None)
        timeout = kwargs.pop("timeout", None)
        options = kwargs.pop("http_options", {})
        if hasattr(options, "model_dump"):
            options = options.model_dump(exclude_none=True)
        self._generation_settings = kwargs
        self._http_options = {"api_version": "v1beta", "base_url": self._base_url,
            "retry_options": types.HttpRetryOptions(attempts=1),
            **options}
        asynchronous = dict(self._http_options.get("async_client_args") or {})
        asynchronous.setdefault("timeout", httpx.Timeout(600, connect=5))
        hooks = dict(asynchronous.get("event_hooks") or {})
        hooks["request"] = [*hooks.get("request", []), self._record_http_request]
        self._http_options["async_client_args"] = {**asynchronous, "event_hooks": hooks}
        if self._http_options.get("httpx_async_client") is None:
            self._http_options["httpx_async_client"] = httpx.AsyncClient(**self._http_options.pop("async_client_args"))
        else:
            self._http_options["httpx_async_client"].event_hooks["request"].append(self._record_http_request)
        self._http_options.setdefault("timeout", int(timeout * 1000) if timeout is not None else 600000)
        self.client = genai.Client(api_key=self._api_key, http_options=types.HttpOptions(**self._http_options))
        self._http_attempts_observed = True

    async def close(self):
        await self.client.aio.aclose()
        self.client.close()
        await self._http_options["httpx_async_client"].aclose()

    def _chat_request(self, messages, tools, json_output, extra_create_args):
        converted = _to_gemini_messages(messages, evidence_mode=self._evidence_mode)
        system = [part for message in converted if message["role"] == "system" for part in message["parts"]]
        config = {**self._generation_settings, "media_resolution": "MEDIA_RESOLUTION_HIGH"}
        if system:
            config["system_instruction"] = {"parts": system}
        if json_output:
            config["response_mime_type"] = "application/json"
        if tools:
            config["tools"] = [{"function_declarations": [tool.get("function", tool) for tool in tools]}]
        extra = dict(extra_create_args)
        effort = extra.pop("reasoning_effort", self._default_reasoning_effort)
        if effort is not None:
            config["thinking_config"] = {"thinking_level": str(effort).upper()}
        config.update(extra)
        return {"model": self.model, "contents": [message for message in converted if message["role"] != "system"],
            "config": types.GenerateContentConfig(**config)}

    async def create(self, messages: Sequence[LLMMessage], tools: Sequence[ToolSchema] = (),
            json_output: Optional[bool] = None, extra_create_args: Mapping[str, Any] = {}) -> CreateResult:
        request = self._chat_request(messages, tools, json_output, extra_create_args)
        config = request["config"]
        record = {"configured_model": self.model, "requested_model": self.model, "provider": "google",
            "transport": judge_transport(), "reasoning_effort": getattr(config.thinking_config, "thinking_level", None),
            "temperature": config.temperature, "max_output_tokens": config.max_output_tokens,
            "http_timeout_seconds": self._http_options["timeout"] / 1000,
            "http_attempts": 0, "http_attempts_observed": True,
            "usage_reported": False, "returned_model": None, "error_type": None}
        if hasattr(record["reasoning_effort"], "value"):
            record["reasoning_effort"] = record["reasoning_effort"].value
        token = self._start_call(record)
        try:
            if judge_transport() == "batch":
                options = {**self._http_options, "httpx_async_client": httpx.AsyncClient(
                    transport=http_transport("google", f"{self._evidence_mode}.{record['stage']}", record),
                    event_hooks={"request": [self._record_http_request]})}
                batch_client = genai.Client(api_key=self._api_key, http_options=types.HttpOptions(**options))
                try:
                    response = await batch_client.aio.models.generate_content(**request)
                finally:
                    await batch_client.aio.aclose()
                    batch_client.close()
                    await options["httpx_async_client"].aclose()
            else:
                response = await self.client.aio.models.generate_content(**request)
        except BaseException as error:
            record["error_type"] = type(error).__name__
            raise
        finally:
            self._active_call.reset(token)
        usage = _record_usage(response, self, record=record)
        raw = response.model_dump() if hasattr(response, "model_dump") else response
        candidates = raw.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
        content = "".join(part["text"] for part in parts if part.get("text") and not part.get("thought"))
        return CreateResult(content=content, usage=usage, finish_reason=record["finish_reason"], message=response,
            tool_calls=[part.get("function_call", part.get("functionCall")) for part in parts
                if part.get("function_call", part.get("functionCall"))] or None)
