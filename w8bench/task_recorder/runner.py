#!/usr/bin/env python3
"""Record independent DOM-only and screenshot-only acting-agent trajectories."""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import math
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .recorder_support import (
    RunnerError, append_json_line, utc_now, write_json,
    finite_nonnegative_float, finite_positive_float,
)
from .capture import (
    CDPClient, CDPError, CaptureBundle, action_progress, action_observation_context,
    agent_browser_target_identity, attach_agent_browser_observation,
    capture_bundle, capture_after_action_bundle, synchronize_recorder_target,
    renderer_versions,
)
from .agent_browser import (
    AgentBrowserBaseError, AgentBrowserClient, agent_browser_session_name,
    container_agent_browser_command,
)
from .prompts import DOM_PROMPT, SCREENSHOT_PROMPT
from .trajectory import generate_trajectory_artifacts

TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_TASK_MEMORY_CHARS = 8000
MAX_ACTION_THOUGHT_CHARS = 1200
ACTOR_PROTOCOL = {"type": "json_schema", "name": "browser_action", "strict": True,
                  "policy": "baseline_with_budget_validation_v2", "output_message": "single_candidate_text"}
MAX_CONSECUTIVE_REJECTIONS = 4


class ModelProtocolError(RunnerError):
    """A model response is ambiguous, incomplete, or has no usable final message."""


ACTION_SCHEMA = {
    "type": "object", "properties": {
        "action": {"type": "string", "enum": ["navigate", "back", "click", "type", "press", "scroll", "wait", "terminate"]},
        "url": {"type": ["string", "null"]},
        "id": {"type": ["string", "null"]},
        "x": {"type": ["number", "null"]}, "y": {"type": ["number", "null"]},
        "text": {"type": ["string", "null"]}, "key": {"type": ["string", "null"]},
        "pixels": {"type": ["number", "null"]}, "seconds": {"type": ["number", "null"]},
        "status": {"type": ["string", "null"], "enum": ["success", "failure", None]},
        "final_answer": {"type": ["string", "null"]},
        "termination_reason": {"type": ["string", "null"],
            "enum": ["completed", "blocked", "cannot_complete", "budget_exhausted", None]},
        "thought": {"type": "string", "minLength": 1, "maxLength": MAX_ACTION_THOUGHT_CHARS},
        "memory": {"type": ["string", "null"], "maxLength": MAX_TASK_MEMORY_CHARS},
    }, "additionalProperties": False,
}
ACTION_SCHEMA["required"] = list(ACTION_SCHEMA["properties"])

def browser_profile_provenance_from_environment() -> dict[str, Any]:
    """Load container-lifetime profile metadata claimed by task_cli."""
    raw = os.environ.get("RUNNER_BROWSER_PROFILE_PROVENANCE", "")
    if not raw:
        return {
            "container_id": None,
            "container_created_at": None,
            "profile_fresh_at_run_start": None,
            "tasks_previously_run_in_container": None,
        }
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RunnerError("RUNNER_BROWSER_PROFILE_PROVENANCE is invalid JSON") from error
    expected = {
        "container_id",
        "container_created_at",
        "profile_fresh_at_run_start",
        "tasks_previously_run_in_container",
    }
    if (not isinstance(value, dict) or not expected.issubset(value)
        or set(value) - expected - {"browser_build", "browser_environment"}):
        raise RunnerError("RUNNER_BROWSER_PROFILE_PROVENANCE has invalid fields")
    if not isinstance(value["container_id"], str) or not value["container_id"]:
        raise RunnerError("w8-core container id is missing")
    if not isinstance(value["container_created_at"], str) or not value["container_created_at"]:
        raise RunnerError("w8-core container creation time is missing")
    if not isinstance(value["profile_fresh_at_run_start"], bool):
        raise RunnerError("browser profile freshness must be boolean")
    count = value["tasks_previously_run_in_container"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise RunnerError("browser prior task count must be a non-negative integer")
    build = value.get("browser_build")
    if build is not None:
        if not isinstance(build, dict):
            raise RunnerError("browser build provenance must be an object")
        for key, item in build.items():
            if key == "repo_digests":
                if not isinstance(item, list) or any(not isinstance(part, str) for part in item):
                    raise RunnerError("browser image digests must be a list of strings")
            elif item is not None and not isinstance(item, str):
                raise RunnerError(f"browser build provenance {key} must be a string or null")
    return value

def load_env(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding the caller's environment."""
    if not path.exists():
        return
    model_seen = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "ACTOR_MODEL":
            if model_seen:
                raise RunnerError("ACTOR_MODEL must have exactly one configured value")
            model_seen = True
            if key in os.environ and os.environ[key] != value:
                raise RunnerError("ACTOR_MODEL in the environment conflicts with the selected env file")
        if key and key not in os.environ:
            os.environ[key] = value

def safe_task_id(value: str) -> str:
    """Validate a task id before it is used as part of a filesystem path."""
    if not TASK_ID_RE.fullmatch(value):
        raise RunnerError("task id may contain only letters, digits, '.', '_' and '-'")
    return value

def default_task_id(output_dir: Path) -> str:
    """Choose the first available numbered recording for an unnamed task."""
    number = 1
    while (output_dir / f"task_{number:02d}").exists():
        number += 1
    return f"task_{number:02d}"

def response_text(response: dict[str, Any]) -> str:
    """Read the final answer without merging simulated commentary actions."""
    messages = []
    for item in response.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        texts = [part["text"] for part in item.get("content", [])
                 if isinstance(part, dict) and part.get("type") == "output_text"
                 and isinstance(part.get("text"), str)]
        if texts:
            messages.append((item.get("phase"), "\n".join(texts).strip()))
    finals = [value for phase, value in messages if phase == "final_answer"]
    if finals:
        # The upstream recorder selects the last action. Preserve that behavior
        # when a provider emits multiple final messages, executing just one.
        return finals[-1]
    unphased = [value for phase, value in messages if phase is None]
    if len(unphased) == 1 and len(messages) == 1:
        return unphased[0]
    if messages:
        raise ModelProtocolError("model response has no unambiguous final answer; no action executed")
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    raise ModelProtocolError("model response has no final output text; no action executed")


def chromiumrl_evidence_for_model(text: str) -> str:
    """Hide ChromiumRL's non-executable action ids in the model prompt.

    The stored renderer output remains byte-for-byte intact. The action driver
    uses only the separate agent-browser e-ref snapshot, so retaining a second
    numeric action namespace in the prompt creates ambiguity without adding
    evidence.
    """
    blocked_prefixes = (
        "Use only ids from this observation.",
        'Use: scroll("down"',
        "Not currently clickable. To interact with these rows, scroll",
    )
    scroll_region_entry = re.compile(r"^\[[^\]]+\]\s+.+\s+—\s+")
    scroll_region_hidden = re.compile(r"^\[scrollable regions hidden:\s*\d+\s+more\]$")
    filtered_lines: list[str] = []
    in_scroll_regions = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped == "=== SCROLLABLE REGIONS ===":
            in_scroll_regions = True
            continue
        if in_scroll_regions:
            if not stripped:
                continue
            if stripped.startswith('Use: scroll("down"'):
                continue
            if scroll_region_entry.match(stripped) or scroll_region_hidden.match(stripped):
                continue
            in_scroll_regions = False
        if stripped.startswith(blocked_prefixes):
            continue
        filtered_lines.append(line)
    filtered = "\n".join(filtered_lines)
    if text.endswith("\n"):
        filtered += "\n"
    return re.sub(r"\[(?:A)?\d+\]", "[non-executable-dom-id]", filtered)

def browser_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """Return only the atomic browser command, excluding model-only fields."""
    return {
        key: value
        for key, value in decision.items()
        if key not in {"memory", "thought"}
    }

def parse_model_json_object(text: str, *, context: str) -> dict[str, Any]:
    """Return the final complete top-level JSON object from model output.

    Structured-output providers normally return one object. Some providers can
    concatenate a preliminary object and their final structured object in the
    convenience output-text field. The final object is the authoritative one;
    callers still validate its action schema immediately afterward.
    """
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    try:
        candidate = json.loads(value)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        candidates: list[dict[str, Any]] = []
        offset = 0
        while True:
            start = value.find("{", offset)
            if start < 0:
                break
            try:
                decoded, end = decoder.raw_decode(value[start:])
            except json.JSONDecodeError:
                offset = start + 1
                continue
            if isinstance(decoded, dict):
                candidates.append(decoded)
            offset = start + end
        if not candidates:
            raise RunnerError(f"model did not return a JSON {context}: {text}")
        candidate = candidates[-1]
    if not isinstance(candidate, dict):
        raise RunnerError(f"model {context} must be a JSON object")
    return candidate

def parse_decision(text: str) -> dict[str, Any]:
    """Parse exactly one action object; never select from concatenated actions."""
    try:
        decision = json.loads(text)
    except (json.JSONDecodeError, TypeError) as error:
        raise RunnerError("model action must contain exactly one JSON object") from error
    if not isinstance(decision, dict):
        raise RunnerError("model action must be a JSON object")
    allowed = set(ACTION_SCHEMA["properties"]["action"]["enum"])
    action = decision.get("action")
    if action not in allowed:
        raise RunnerError(f"unsupported model action: {action!r}")
    return decision

class ModelClient:
    def __init__(self, api_key: str, model: str, base_url: str):
        if not api_key or not model:
            raise RunnerError("model API key and model id are required")
        self.api_key, self.model, self.base_url = api_key, model, base_url.rstrip("/")
        self.last_input_report: dict[str, Any] = {}
        self.last_response: dict[str, Any] | None = None

    @staticmethod
    def _gemini_usage(usage: Any) -> dict[str, Any]:
        normalized_usage = {}
        if isinstance(usage, dict):
            # Gemini candidate tokens exclude thoughts. Our output total
            # includes them, with reasoning disclosed as a subset.
            if usage.get("promptTokenCount") is not None:
                normalized_usage["input_tokens"] = usage["promptTokenCount"]
            if usage.get("candidatesTokenCount") is not None and usage.get("thoughtsTokenCount") is not None:
                normalized_usage["output_tokens"] = usage["candidatesTokenCount"] + usage["thoughtsTokenCount"]
            elif usage.get("candidatesTokenCount") is not None:
                normalized_usage["output_tokens"] = usage["candidatesTokenCount"]
            if usage.get("cachedContentTokenCount") is not None:
                normalized_usage["input_tokens_details"] = {"cached_tokens": usage["cachedContentTokenCount"]}
            if usage.get("thoughtsTokenCount") is not None:
                normalized_usage["output_tokens_details"] = {"reasoning_tokens": usage["thoughtsTokenCount"]}
            if usage.get("totalTokenCount") is not None:
                normalized_usage["total_tokens"] = usage["totalTokenCount"]
        return normalized_usage

    @staticmethod
    def _gemini_response(result: dict[str, Any]) -> dict[str, Any]:
        candidates = result.get("candidates") or []
        candidate = candidates[0] if len(candidates) == 1 else {}
        finish_reason = candidate.get("finishReason")
        parts = (candidate.get("content") or {}).get("parts") or []
        usage = result.get("usageMetadata")
        normalized_usage = ModelClient._gemini_usage(usage)
        return {"provider": "google", "provider_response": result,
            "id": result.get("responseId"), "model": result.get("modelVersion"),
            "output_text": "".join(part["text"] for part in parts
                if isinstance(part.get("text"), str) and not part.get("thought")),
            "status": "completed" if finish_reason == "STOP" and not any("functionCall" in part for part in parts) else "incomplete",
            "incomplete_details": ({"reason": "max_output_tokens"} if finish_reason == "MAX_TOKENS"
                else {"reason": finish_reason or "missing_or_multiple_candidates"}) if finish_reason != "STOP" else None,
            "reasoning": {"effort": "medium"}, "usage": normalized_usage}

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        gemini = self.model.startswith("gemini-")
        native_payload = {key: value for key, value in payload.items() if key != "model"} if gemini else payload
        endpoint = (self.base_url + "/models/" + self.model + ":generateContent"
                    if gemini else self.base_url + "/responses")
        headers = {"Content-Type": "application/json"}
        headers["x-goog-api-key" if gemini else "Authorization"] = self.api_key if gemini else f"Bearer {self.api_key}"
        request = urllib.request.Request(endpoint,
            data=json.dumps(native_payload).encode(), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            # Never persist response bodies that may echo request credentials.
            raise RunnerError(f"model endpoint returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RunnerError(f"model request failed: {type(error).__name__}") from error
        if not isinstance(result, dict):
            raise RunnerError("model response is not an object")
        if gemini:
            result = self._gemini_response(result)
        return result

    def _actor_request(
        self, task, step, max_steps, bundle, task_memory, recent_actions,
        turn_dir, viewport, max_output_tokens,
    ):
        prompt = (f"task:\n{task}\n\nstep: {step} of {max_steps}\n"
            f"model_turn: {step}\n"
            f"turns_remaining_including_current: {max_steps - step + 1}\n"
            f"turns_remaining_after_this_call: {max_steps - step}\n"
            "human_intervention_available: false\n"
            f"viewport_css_pixels: {viewport[0]} x {viewport[1]}\n\n"
            f"task_memory_from_prior_steps:\n{task_memory or '(none)'}\n\n"
            f"current_document_url: {bundle.document_url}\n\n")
        content = []
        path = bundle.observation_path
        observation_bytes = path.read_bytes()
        artifact = {"path": os.path.relpath(path, turn_dir),
                    "sha256": hashlib.sha256(observation_bytes).hexdigest()}
        if bundle.observation_mode == "dom":
            prompt += (f"current_document_language: {bundle.document_language or 'unknown'}\n"
                f"current_agent_browser_snapshot:\n{bundle.agent_browser_action_text}\n\n"
                f"current_chromiumrl_evidence:\n{chromiumrl_evidence_for_model(bundle.model_text)}")
            instructions = DOM_PROMPT
        else:
            instructions = SCREENSHOT_PROMPT
            content.append({"inlineData": {"mimeType": "image/png", "data":
                base64.b64encode(observation_bytes).decode()}})
        prompt += (f"\n\nrecent_action_outcomes:\n{json.dumps(recent_actions[-6:], ensure_ascii=False)}\n\n"
            "Use the recorded progress signals. If an action made no observable progress, "
            "change strategy instead of assuming it worked. Return one JSON action and "
            "wait for the harness to execute it and supply the next observation.")
        content.insert(0, {"text": prompt})
        # model identifies the URL path; the remaining fields are the exact
        # generateContent request body sent by _post.
        payload = {"model": self.model, "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"role": "user", "parts": content}],
            "generationConfig": {"maxOutputTokens": max_output_tokens,
                "thinkingConfig": {"thinkingLevel": "MEDIUM"},
                "mediaResolution": "MEDIA_RESOLUTION_HIGH",
                "responseMimeType": "application/json", "responseJsonSchema": ACTION_SCHEMA}}
        return payload, artifact, prompt

    def _validated_action(self, response: dict[str, Any]) -> dict[str, Any]:
        returned_model = response.get("model")
        if not isinstance(returned_model, str) or not re.fullmatch(
                r"gemini-3\.1-pro-preview(?:-\d{2}-\d{2}|-\d{4}-\d{2}-\d{2})?", returned_model):
            raise ModelProtocolError(
                f"actor model mismatch: configured {self.model!r}, returned {returned_model!r}; "
                "expected Gemini 3.1 Pro Preview; no action executed")
        if response.get("status") not in {None, "completed"}:
            raise ModelProtocolError(f"model response status is {response.get('status')!r}; no action executed")
        if any(isinstance(item, dict) and item.get("type") == "function_call"
               for item in response.get("output", [])):
            raise ModelProtocolError("expected a JSON action, received a tool call; no action executed")
        return parse_decision(response_text(response))

    async def decide(self, *, task: str, step: int, max_steps: int,
                     bundle: CaptureBundle, task_memory: str,
                     recent_actions: list[dict[str, Any]], turn_dir: Path,
                     viewport: tuple[int, int], max_output_tokens: int = 10000,
                     ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.last_response = None
        self.last_input_report = {}
        configured_model = os.environ.get("ACTOR_MODEL", "").strip()
        if configured_model != "gemini-3.1-pro-preview" or self.model != configured_model:
            raise RunnerError("actor model must match the single ACTOR_MODEL=gemini-3.1-pro-preview configuration")
        if max_output_tokens != 10000:
            raise RunnerError("actor output limit must be exactly 10000 tokens")
        if not 1 <= max_steps <= 200:
            raise RunnerError("actor turn budget must be positive and no greater than 200")
        payload, artifact, prompt = self._actor_request(
            task, step, max_steps, bundle, task_memory, recent_actions,
            turn_dir, viewport, max_output_tokens,
        )
        # Persist the exact text and an immutable reference to the exact image
        # bytes sent, avoiding another base64 copy in every turn directory.
        stored = json.loads(json.dumps(payload))
        if bundle.observation_mode == "screenshot":
            stored["contents"][0]["parts"][1] = {"inlineData": {"mimeType": "image/png", "artifact": artifact}}
        write_json(turn_dir / "request.json", stored)
        self.last_input_report = {"observation_mode": bundle.observation_mode,
            "observation": artifact, "request": "request.json", "text_chars": len(prompt)}
        self.last_input_report["api_call_started"] = True
        response = await asyncio.to_thread(self._post, payload)
        self.last_response = response
        write_json(turn_dir / "response.json", response)
        return self._validated_action(response), response


def _action_schema_error(decision: dict[str, Any], action: Any) -> str:
    if action not in ACTION_SCHEMA["properties"]["action"]["enum"]:
        return "unsupported action"
    if set(decision) - set(ACTION_SCHEMA["properties"]):
        return "unexpected action fields"
    thought = decision.get("thought")
    if not isinstance(thought, str) or not thought.strip() or len(thought) > MAX_ACTION_THOUGHT_CHARS:
        return "thought must contain one bounded action rationale"
    memory = decision.get("memory")
    if memory is not None and (not isinstance(memory, str) or len(memory) > MAX_TASK_MEMORY_CHARS):
        return "memory must be null or bounded text"
    return ""


def _action_target_error(decision: dict[str, Any], action: str, available_refs: frozenset[str],
                         observation_mode: str, viewport: tuple[int, int]) -> str:
    ref = decision.get("id")
    if ref is not None and (not isinstance(ref, str) or ref.startswith("@")):
        return "id must be a current e-ref without @"
    x, y = decision.get("x"), decision.get("y")
    if observation_mode == "screenshot" and ref is not None:
        return "element refs are forbidden in screenshot mode; use coordinates"
    if observation_mode == "dom" and (x is not None or y is not None):
        return "coordinates are unavailable in DOM mode; use a current ref"
    if ref is not None and (action not in {"click", "scroll"} or ref not in available_refs):
        return "id is not a current executable ref for this action"
    if action == "click" and observation_mode == "dom" and not ref:
        return "click requires a current executable ref"
    if observation_mode == "screenshot":
        if (x is None) != (y is None) or (action == "click" and x is None):
            return "supply both x and y coordinates"
        if x is not None:
            if action not in {"click", "scroll"}:
                return "coordinates apply only to click or scroll"
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in (x, y)) or not (0 <= x < viewport[0] and 0 <= y < viewport[1]):
                return "coordinates must be finite and inside the viewport"
    return ""


def _action_value_error(decision: dict[str, Any], action: str) -> str:
    if action == "navigate" and (not isinstance(decision.get("url"), str) or
            not re.match(r"^https?://[^/\s]+", decision["url"])):
        return "navigate requires an HTTP(S) URL"
    if action in {"type", "press"}:
        value = decision.get("text" if action == "type" else "key")
        if not isinstance(value, str) or not value:
            return f"{action} requires nonempty input"
    if action in {"scroll", "wait"}:
        value = decision.get("pixels" if action == "scroll" else "seconds")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return "scroll/wait requires a finite numeric amount"
        if (action == "wait" and not 0 <= value <= 10) or (action == "scroll" and value == 0):
            return "wait must be 0–10 seconds; scroll must be nonzero"
    return ""


def _termination_error(decision: dict[str, Any], action: str,
                       model_turn: int | None, max_turns: int | None) -> str:
    if action == "terminate" and (decision.get("status") not in {"success", "failure"}
            or not isinstance(decision.get("final_answer"), str) or not decision["final_answer"].strip()):
        return "terminate requires status and a final answer"
    if action != "terminate" and decision.get("termination_reason") is not None:
        return "termination_reason applies only to terminate"
    if action == "terminate":
        reason = decision.get("termination_reason")
        if reason not in {"completed", "blocked", "cannot_complete", "budget_exhausted"}:
            return "terminate requires a termination_reason: completed, blocked, cannot_complete or budget_exhausted"
        if (decision["status"] == "success") != (reason == "completed"):
            return "successful termination requires reason completed; failure requires a failure reason"
        if reason == "budget_exhausted" and (model_turn is None or max_turns is None):
            return "turn budget is unavailable; do not claim budget exhaustion"
        if reason == "budget_exhausted" and model_turn < max_turns:
            return (f"turn budget is not exhausted: this is model turn {model_turn} of {max_turns}; "
                    f"{max_turns - model_turn} calls remain after this one. "
                    "Choose another permitted browser action and wait for its observation. "
                    "Use blocked or cannot_complete only for an actual task limitation, not an invented turn limit.")
    return ""


def _action_signature(value: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    command = {k: v for k, v in browser_decision(value).items() if v is not None}
    context = context or {}
    if command.get("action") == "scroll":
        pixels = command.get("pixels", 0)
        command["pixels"] = 1 if pixels > 0 else -1 if pixels < 0 else 0
    if command.get("id") and context.get("control_signature"):
        command.pop("id")
        command["control_signature"] = context["control_signature"]
        command["document_url"] = context.get("document_url", "")
    return json.dumps(command, sort_keys=True, ensure_ascii=False)


def _stalled_action_error(decision: dict[str, Any], action: str,
                          completed: list[dict[str, Any]],
                          action_context: dict[str, Any] | None) -> str:
    candidate = _action_signature(decision, action_context)
    if completed and action not in {"scroll", "wait", "terminate"}:
        last = completed[-1]
        if (last["progress"].get("made_progress") is False
                and _action_signature(last["action"], last.get("action_context")) == candidate):
            return "exact consecutive duplicate activation made no observable progress"
    if len(completed) >= 3:
        cycle = completed[-3:]
        first, second, third = [_action_signature(item["action"], item.get("action_context")) for item in cycle]
        if (all(item["progress"].get("made_progress") is False for item in cycle)
                and first == third and second == candidate and first != second):
            return "action would repeat a two-action cycle without forward progress"
    if len(completed) >= 2 and all(item["progress"].get("made_progress") is False for item in completed[-2:]):
        if candidate in {_action_signature(item["action"], item.get("action_context")) for item in completed[-2:]}:
            return "action would retry a recently stalled strategy without observable progress"
    return ""


def action_rejection_reason(decision: dict[str, Any], available_refs: frozenset[str],
                            recent_actions: list[dict[str, Any]], *,
                            observation_mode: str = "dom",
                            viewport: tuple[int, int] = (1365, 768),
                            model_turn: int | None = None, max_turns: int | None = None,
                            action_context: dict[str, Any] | None = None) -> str:
    action = decision.get("action")
    reason = _action_schema_error(decision, action)
    if reason:
        return reason
    reason = _action_target_error(decision, action, available_refs, observation_mode, viewport)
    if reason:
        return reason
    reason = _action_value_error(decision, action)
    if reason:
        return reason
    reason = _termination_error(decision, action, model_turn, max_turns)
    if reason:
        return reason
    completed = [item for item in recent_actions if isinstance(item.get("action"), dict)
                 and isinstance(item.get("progress"), dict) and item.get("action_succeeded") is True]
    if action == "terminate" and decision.get("status") == "success" and not completed:
        return "successful termination requires at least one confirmed browser action, as in the baseline recorder"
    return _stalled_action_error(decision, action, completed, action_context)


def state_manifest_record(state_number: int, bundle: CaptureBundle, run_dir: Path) -> dict[str, Any]:
    row = {"state": state_number, "directory": str(bundle.directory.relative_to(run_dir)),
        "observation": str(bundle.observation_path.relative_to(run_dir)),
        "observation_sha256": hashlib.sha256(bundle.observation_path.read_bytes()).hexdigest()}
    row["capture"] = bundle.capture_metadata
    row["artifacts"] = {}
    for name in ("dom.json", "dom_full.txt", "dom_model.json", "dom_model.txt", "screenshot.png",
                 "agent_browser_actions.txt", "capture.json"):
        path = bundle.directory / name
        if path.exists():
            row["artifacts"][name] = {"path": str(path.relative_to(run_dir)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if bundle.agent_browser_action_path is not None:
        row["agent_browser_action_snapshot"] = str(bundle.agent_browser_action_path.relative_to(run_dir))
    return row


def finalize_recording_artifacts(run_dir: Path, manifest: dict[str, Any], final: dict[str, Any],
                                 *, manifest_status: str | None = None,
                                 error: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    final = {**final, "recorded_steps": len(manifest["steps"]),
        "model_turns": manifest["model_turns"], "completion_grade": "ungraded"}
    manifest.update(status=manifest_status or final["run_status"], completed_at=utc_now(), final=final)
    if error:
        manifest["error"] = error
    # Commit the final manifest before exporting; the exporter reads its states.
    write_json(run_dir / "final.json", final)
    write_json(run_dir / "manifest.json", manifest)
    export = generate_trajectory_artifacts(run_dir)
    manifest["trajectory_export"] = export
    write_json(run_dir / "manifest.json", manifest)
    return final, export


@dataclass
class ActorState:
    """Mutable memory and control state carried across actor turns."""
    memory: str = ""
    recent: list[dict[str, Any]] = field(default_factory=list)
    consecutive_rejections: int = 0
    cancelled: bool = False


def _validate_run_args(args: argparse.Namespace, mode: str) -> None:
    if mode not in {"dom", "screenshot"}:
        raise RunnerError("an explicit observation mode is required")
    if args.max_steps <= 0 or args.viewport_width <= 0 or args.viewport_height <= 0 or args.max_output_tokens <= 0:
        raise RunnerError("turn budget, viewport dimensions, and output budget must be positive")
    if args.max_output_tokens != 10000:
        raise RunnerError("actor output limit must be exactly 10000 tokens")
    if args.max_steps > 200:
        raise RunnerError("actor turn budget must be positive and no greater than 200")
    if not math.isfinite(args.settle_seconds) or args.settle_seconds < 0:
        raise RunnerError("--settle-seconds must be finite and nonnegative")
    if not math.isfinite(args.agent_browser_timeout) or args.agent_browser_timeout <= 0:
        raise RunnerError("--agent-browser-timeout must be finite and positive")
    if args.snapshot_max_nodes <= 0 or args.snapshot_max_text_chars <= 0:
        raise RunnerError("invalid capture budget or settling delay")
    if not args.capture_only and not args.task:
        raise RunnerError("--task is required")
    if args.start_url and not re.match(r"^https?://[^/\s]+", args.start_url):
        raise RunnerError("--start-url must be HTTP(S)")
    if not args.capture_only:
        configured_model = os.environ.get("ACTOR_MODEL", "").strip()
        if configured_model != "gemini-3.1-pro-preview" or args.model != configured_model:
            raise RunnerError("actor model must match the single ACTOR_MODEL=gemini-3.1-pro-preview configuration")


def _recording_task(args, task_id, mode):
    task = {"task_id": task_id, "source_task_id": args.source_task_id or task_id,
        "run_name": args.run_name, "task_name": args.task_name, "instruction": args.task or "capture-only",
        "start_url": args.start_url, "observation_mode": mode, "model": args.model}
    source_catalog = Path(args.source_catalog).expanduser() if args.source_catalog else None
    if source_catalog is not None:
        if not source_catalog.is_file():
            raise RunnerError("--source-catalog must identify an available frozen local catalog")
        from .task_cli import fetch_catalog_task
        catalog_task = fetch_catalog_task(str(source_catalog), task["source_task_id"])
        if catalog_task["instruction"] != task["instruction"] or catalog_task["start_url"] != task["start_url"]:
            raise RunnerError("local source catalog does not match the requested task instruction and URL")
        task.update(category=catalog_task.get("category"), difficulty=catalog_task.get("difficulty"),
            source_catalog=catalog_task["source_catalog"], catalog_sha256=catalog_task["catalog_sha256"],
            valid_until=catalog_task.get("valid_until"))
    else:
        task.update(category=None, difficulty=None, source_catalog=None, catalog_sha256=None, valid_until=None)
    checked_at = datetime.now(timezone.utc)
    expired = bool(task["valid_until"] and checked_at.date() > date.fromisoformat(task["valid_until"]))
    if expired:
        print(f"Warning: task {task['source_task_id']} expired after {task['valid_until']} UTC.", file=sys.stderr)
        if not args.allow_expired:
            raise RunnerError("expired catalog task; review it or explicitly use --allow-expired")
    task.update(expiry_checked_at=checked_at.isoformat(), expiry_override=expired and args.allow_expired)
    return task


def _recording_manifest(args, task, profile, mode, viewport):
    manifest = {**task, "schema_version": "3.0", "created_at": utc_now(), "status": "running",
        "model_input_policy": f"{mode}_only", "states": [], "steps": [], "model_turns": 0,
        "browser_profile_provenance": profile,
        "configured_actor_model": args.model, "actor_provider": "google", "returned_actor_models": [], "reasoning_effort": "medium",
        "controls": {"model": args.model, "base_url": args.api_base_url,
            "reasoning_effort": "medium", "temperature": None, "memory_max_chars": MAX_TASK_MEMORY_CHARS,
            "max_turns": args.max_steps, "max_output_tokens": args.max_output_tokens,
            "viewport": list(viewport), "settle_seconds": args.settle_seconds,
            "snapshot_max_nodes": args.snapshot_max_nodes,
            "snapshot_max_text_chars": args.snapshot_max_text_chars,
            "agent_browser_timeout": args.agent_browser_timeout,
            "transport_timeout": 180.0, "cdp_timeout": 90.0,
            "browser_lang": args.browser_lang, "browser_accept_language": args.browser_accept_language,
            "action_vocabulary": ACTION_SCHEMA["properties"]["action"]["enum"],
            "actor_protocol": ACTOR_PROTOCOL,
            "max_consecutive_rejections": MAX_CONSECUTIVE_REJECTIONS,
            "recorder_code_sha256": hashlib.sha256(b"".join(
                f.read_bytes() for f in sorted(Path(__file__).resolve().parents[1].rglob("*.py")))).hexdigest(),
            "action_schema_sha256": hashlib.sha256(json.dumps(ACTION_SCHEMA, sort_keys=True).encode()).hexdigest(),
            "prompt_sha256": hashlib.sha256((DOM_PROMPT if mode == "dom" else SCREENSHOT_PROMPT).encode()).hexdigest(),
            "human_intervention": False, "automatic_redirects": False,
            "keep_existing_tabs": args.keep_existing_tabs},
        "turn_definition": "one actor API call, including rejected proposals, parse failures and termination",
        "action_driver": "agent-browser refs + CDP.Input" if mode == "dom" else "CDP.Input"}
    manifest["dom_capture_parameters"] = {"max_nodes": args.snapshot_max_nodes,
        "max_text_chars": args.snapshot_max_text_chars, "in_viewport_only": True,
        "action_snapshot_policy": "viewport_bbox_overlap_v1"}
    manifest["renderer_versions"] = renderer_versions()
    from w8bench.settings import actor_settings, browser_source_version, require_same_settings
    manifest["effective_settings"] = actor_settings(manifest["controls"], browser_source=browser_source_version())
    scheduled = os.environ.get("W8_EXPECTED_ACTOR_SETTINGS")
    if scheduled:
        try:
            require_same_settings(json.loads(scheduled), manifest["effective_settings"], label="scheduled actor")
        except (ValueError, TypeError) as error:
            raise RunnerError(str(error)) from error
    return manifest


async def _initial_capture(args, cdp, driver, manifest, run_dir, mode):
    manifest["browser_session"] = cdp.connection_report
    if mode == "dom" and not args.capture_only:
        await driver.connect()
        manifest["action_driver_version"] = driver.version
    if args.start_url:
        result = await cdp.call("Page.navigate", {"url": args.start_url})
        if result.get("errorText"):
            raise RunnerError(result["errorText"])
        await asyncio.sleep(args.settle_seconds)
    await synchronize_recorder_target(cdp, driver if mode == "dom" else None)
    current = await capture_bundle(cdp, run_dir / "steps" / "step_001",
        max_nodes=args.snapshot_max_nodes, max_text_chars=args.snapshot_max_text_chars,
        observation_mode=mode)
    if mode == "dom" and not args.capture_only:
        current = await attach_agent_browser_observation(current, driver, cdp)
    manifest["states"].append(state_manifest_record(1, current, run_dir))
    write_json(run_dir / "manifest.json", manifest)
    return current


def _finish_model_turn(
    args, model, row, manifest, run_dir, turn_dir, turn, started,
):
    row["latency_seconds"] = round(time.monotonic() - started, 6)
    row["model_input"] = model.last_input_report
    row["usage"] = (model.last_response or {}).get("usage", {})
    response = model.last_response or {}
    row["configured_model"] = model.model
    row["max_output_tokens"] = args.max_output_tokens
    row["requested_reasoning_effort"] = "medium"
    row["requested_temperature"] = None
    row["returned_temperature"] = response.get("temperature")
    row["response_id"] = response.get("id")
    row["returned_model"] = response.get("model")
    row["reasoning"] = response.get("reasoning")
    row["response_status"] = response.get("status")
    row["incomplete_details"] = response.get("incomplete_details")
    row["output_limit_hit"] = (bool(
        (response.get("incomplete_details") or {}).get("reason") == "max_output_tokens"
        or (response.get("usage") or {}).get("output_tokens", 0) >= args.max_output_tokens)
        if response else None)
    if response.get("model"):
        manifest["returned_actor_models"] = sorted(set(
            manifest["returned_actor_models"] + [response["model"]]))
    write_json(run_dir / "manifest.json", manifest)
    if (turn_dir / "response.json").exists():
        row["response"] = str((turn_dir / "response.json").relative_to(run_dir))
    if model.last_input_report.get("api_call_started"):
        write_json(turn_dir / "result.json", row)
        append_json_line(run_dir / "decisions.jsonl", row)
    else:
        manifest["model_turns"] = turn - 1
        write_json(run_dir / "manifest.json", manifest)


async def _model_turn(
    args, task, model, current, state, manifest, run_dir,
    turn_dir, turn, mode, viewport,
):
    started = time.monotonic()
    row = {"model_turn": turn, "state": len(manifest["states"]), "recorded_at": utc_now(),
        "request": str((turn_dir / "request.json").relative_to(run_dir)),
        "task_memory_before": state.memory}
    decision = None
    try:
        decision, response = await model.decide(task=task['instruction'], step=turn, max_steps=args.max_steps, bundle=current, task_memory=state.memory, recent_actions=state.recent, turn_dir=turn_dir, viewport=viewport, max_output_tokens=args.max_output_tokens)
        reason = action_rejection_reason(decision, current.agent_browser_refs, state.recent, observation_mode=mode, viewport=viewport, model_turn=turn, max_turns=args.max_steps, action_context=action_observation_context(decision, current) if mode == 'dom' else None)
        row.update(decision=decision, rejection_reason=reason or None, accepted=not reason)
    except BaseException as error:
        row.update(accepted=False, error=type(error).__name__ + ': ' + str(error))
        if model.last_response is None or isinstance(error, (asyncio.CancelledError, ModelProtocolError)):
            raise
    finally:
        _finish_model_turn(args, model, row, manifest, run_dir, turn_dir, turn, started)
    return decision, row


def _rejected_turn(args, state, row, decision, turn):
    print(f"[turn {turn}/{args.max_steps}] rejected: "
          f"{row.get('rejection_reason') or row.get('error')}", flush=True)
    state.recent.append({"model_turn": turn, "rejected_action": decision,
        "reason": row.get("rejection_reason") or row.get("error")})
    state.consecutive_rejections += 1
    if state.consecutive_rejections >= MAX_CONSECUTIVE_REJECTIONS:
        return {"status": "failure", "run_status": "invalid_action_limit",
            "termination_reason": "cannot_complete",
            "final_answer": f"Model produced {MAX_CONSECUTIVE_REJECTIONS} consecutive invalid proposals. "
                + str(row.get("rejection_reason") or row.get("error"))}
    return None


async def _deliver_action(
    decision, current, driver, cdp, viewport, manifest, run_dir, turn, mode,
):
    action = browser_decision(decision)
    action = {k: v for k, v in action.items() if v is not None}
    target = agent_browser_target_identity(action, current) if mode == "dom" else None
    action_record = {"model_turn": turn, "action": action, "thought": decision["thought"],
        "state": len(manifest["states"]), "started_at": utc_now()}
    if target:
        action_record["target"] = target
    if mode == "dom":
        action_record["action_context"] = action_observation_context(action, current)
    action_started = time.monotonic()
    action_error = None
    action_cancelled = False
    try:
        result = await driver.execute(action, cdp=cdp, viewport=viewport)
        if not isinstance(result, dict) or result.get("success") is not True:
            raise RunnerError("action tool did not confirm delivery")
        action_record["action_result"] = result
    except BaseException as error:
        action_cancelled = isinstance(error, asyncio.CancelledError)
        action_error = type(error).__name__ + ": " + str(error)
    action_record.update(action_error=action_error, action_succeeded=action_error is None,
        duration_seconds=round(time.monotonic() - action_started, 6))
    write_json(current.directory / "action.json", action_record)
    manifest["steps"].append(action_record)
    write_json(run_dir / "manifest.json", manifest)
    if action_cancelled:
        raise asyncio.CancelledError()
    return action_record


async def _observe_action(
    args, current, action_record, candidate_memory, state, cdp, driver,
    manifest, run_dir, mode,
):
    await asyncio.sleep(args.settle_seconds)
    await synchronize_recorder_target(cdp, driver if mode == "dom" else None)
    number = len(manifest["states"]) + 1
    next_state, reconnects = await capture_after_action_bundle(cdp,
        driver if mode == "dom" else None, run_dir / "steps" / f"step_{number:03d}",
        max_nodes=args.snapshot_max_nodes, max_text_chars=args.snapshot_max_text_chars,
        observation_mode=mode)
    if mode == "dom":
        next_state = await attach_agent_browser_observation(next_state, driver, cdp)
    if action_record["action_succeeded"]:
        state.memory = candidate_memory
    action_record.update(next_state=number, progress=action_progress(current, next_state))
    print(f"  action: {'error' if action_record['action_error'] else 'delivered'}; recorded state {number}", flush=True)
    if reconnects:
        action_record["capture_reconnects"] = reconnects
    write_json(current.directory / "action.json", action_record)
    manifest["states"].append(state_manifest_record(number, next_state, run_dir))
    write_json(run_dir / "manifest.json", manifest)
    state.recent.append({'model_turn': action_record['model_turn'], 'action': action_record['action'], 'action_succeeded': action_record['action_succeeded'], 'action_error': action_record['action_error'], 'progress': action_record['progress'], **({'action_context': action_record['action_context']} if mode == 'dom' else {})})
    return next_state


async def _accepted_turn(
    args, decision, current, state, driver, cdp, viewport, manifest,
    run_dir, turn, mode,
):
    state.consecutive_rejections = 0
    action_label = decision["action"]
    if decision.get("id"):
        action_label += f" id={decision['id']}"
    elif decision.get("x") is not None:
        action_label += f" x={decision['x']} y={decision['y']}"
    print(f"[turn {turn}/{args.max_steps}] {action_label}", flush=True)
    candidate_memory = decision.get("memory")
    candidate_memory = candidate_memory.strip() if isinstance(candidate_memory, str) and candidate_memory.strip() else state.memory
    if decision['action'] == 'terminate':
        state.memory = candidate_memory
        return current, {"status": decision["status"],
            "termination_reason": decision["termination_reason"],
            "run_status": "turn_limit" if decision["termination_reason"] == "budget_exhausted" else "completed",
            "final_answer": decision["final_answer"], "model_turn": turn, "task_memory": state.memory}
    action_record = await _deliver_action(
        decision, current, driver, cdp, viewport, manifest, run_dir, turn, mode,
    )
    next_state = await _observe_action(
        args, current, action_record, candidate_memory, state, cdp, driver,
        manifest, run_dir, mode,
    )
    return next_state, None


async def _actor_turns(
    args, task, model, current, state, driver, cdp, viewport,
    manifest, run_dir, mode, final,
):
    for turn in range(1, args.max_steps + 1):
        turn_dir = run_dir / "turns" / f"turn_{turn:06d}"
        turn_dir.mkdir(parents=True)
        manifest["model_turns"] = turn
        write_json(run_dir / "manifest.json", manifest)
        decision, row = await _model_turn(
            args, task, model, current, state, manifest, run_dir,
            turn_dir, turn, mode, viewport,
        )
        if not row["accepted"]:
            rejected = _rejected_turn(args, state, row, decision, turn)
            if rejected is not None:
                return rejected
            continue
        current, completed = await _accepted_turn(
            args, decision, current, state, driver, cdp, viewport, manifest,
            run_dir, turn, mode,
        )
        if completed is not None:
            return completed
    return final


def _print_run_summary(args, final, manifest, run_dir):
    print(f"Run status: {final['run_status']}; actor status: {final['status']}; "
          f"model turns: {manifest['model_turns']}/{args.max_steps}; action attempts: {len(manifest['steps'])}", flush=True)
    if final.get("error"):
        print(f"Error: {final['error']}", file=sys.stderr, flush=True)
    if final.get("final_answer"):
        print(f"Final answer: {final['final_answer']}", flush=True)
    print(f"Recording: {run_dir}", flush=True)


async def run(args: argparse.Namespace) -> int:
    mode = args.observation_mode
    _validate_run_args(args, mode)
    model = None if args.capture_only else ModelClient(args.api_key, args.model, args.api_base_url)
    task_id = safe_task_id(args.task_id or default_task_id(Path(args.output_dir)))
    run_dir = Path(args.output_dir).resolve() / task_id
    viewport = (args.viewport_width, args.viewport_height)
    task = _recording_task(args, task_id, mode)
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "task.json", task)
    driver = AgentBrowserClient(args.agent_browser_command,
        session=agent_browser_session_name(task_id, os.getpid()),
        cdp_url=args.agent_browser_cdp_url, timeout=args.agent_browser_timeout)
    profile = browser_profile_provenance_from_environment()
    manifest = _recording_manifest(args, task, profile, mode, viewport)
    write_json(run_dir / "manifest.json", manifest)
    print(f"Recorder: mode={mode}, model={args.model or '(capture only)'}, turn budget={args.max_steps}", flush=True)
    final = {"status": "failure", "run_status": "turn_limit", "termination_reason": "budget_exhausted", "final_answer": "Actor turn budget exhausted"}
    state = ActorState()
    try:
        async with CDPClient(args.cdp_url, keep_existing_tabs=args.keep_existing_tabs,
            browser_language=args.browser_lang, browser_accept_language=args.browser_accept_language,
            observation_mode=mode, viewport=viewport) as cdp:
            current = await _initial_capture(args, cdp, driver, manifest, run_dir, mode)
            if args.capture_only:
                final = {"status": "captured", "run_status": "captured", "final_answer": ""}
            else:
                final = await _actor_turns(
                    args, task, model, current, state, driver, cdp, viewport,
                    manifest, run_dir, mode, final,
                )
    except asyncio.CancelledError:
        state.cancelled = True
        final = {"status": "failure", "run_status": "interrupted", "final_answer": "Run interrupted"}
    except Exception as error:
        final = {"status": "failure", "run_status": "error", "final_answer": "Run ended with an execution error",
            "error": type(error).__name__ + ": " + str(error)}
    finally:
        if mode == "dom":
            await driver.close()
        final, export = finalize_recording_artifacts(run_dir, manifest, final)
    _print_run_summary(args, final, manifest, run_dir)
    if state.cancelled:
        raise asyncio.CancelledError()
    return 0 if final["status"] in {"success", "captured"} and export["status"] == "complete" else 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Load environment defaults, then parse live-run and export CLI modes."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env-file", default=".env")
    known, _ = pre.parse_known_args(argv)
    load_env(Path(known.env_file))

    parser = argparse.ArgumentParser(description="Record independent DOM-only or screenshot-only browser runs")
    parser.add_argument("--env-file", default=known.env_file)
    parser.add_argument(
        "--build-trajectory-run",
        type=Path,
        help=(
            "Validate an existing run and atomically generate trajectory.jsonl "
            "plus web_surfer.log from confirmed executed actions"
        ),
    )
    parser.add_argument("--observation-mode", choices=["dom", "screenshot"])
    parser.add_argument("--viewport-width", type=int, default=1365)
    parser.add_argument("--viewport-height", type=int, default=768)
    parser.add_argument("--max-output-tokens", type=int, default=10000,
        help="fixed actor output limit; only 10000 is accepted")
    parser.add_argument("--task")
    parser.add_argument("--task-id")
    parser.add_argument("--source-task-id")
    parser.add_argument("--source-catalog")
    parser.add_argument("--allow-expired", action="store_true",
        help="explicitly allow a catalog task past its inclusive UTC valid_until date")
    parser.add_argument("--task-name")
    parser.add_argument("--start-url")
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument(
        "--keep-existing-tabs",
        action="store_true",
        help="Do not close other existing non-DevTools page targets on connect",
    )
    # The runner is host-side: Compose publishes container port 9222 on host
    # port 49335. agent-browser runs inside the container and therefore uses a
    # separate container-local CDP URL below.
    default_host_cdp_url = (
        "http://127.0.0.1:"
        + os.environ.get("CDP_HOST_PORT", "49335")
    )
    parser.add_argument(
        "--cdp-url",
        default=os.environ.get("RUNNER_CDP_URL", default_host_cdp_url),
    )
    default_container_name = os.environ.get(
        "CONTAINER_NAME", "w8-core-browser-engine"
    )
    parser.add_argument(
        "--agent-browser-command",
        default=os.environ.get(
            "AGENT_BROWSER_COMMAND",
            container_agent_browser_command(default_container_name),
        ),
        help="w8-core agent-browser command used for DOM reference-targeted actions",
    )
    parser.add_argument(
        "--agent-browser-cdp-url",
        default=os.environ.get(
            "AGENT_BROWSER_CDP_URL",
            "http://127.0.0.1:9222",
        ),
        help="CDP endpoint visible to agent-browser inside the w8-core runtime",
    )
    parser.add_argument(
        "--agent-browser-timeout",
        type=finite_positive_float,
        default=os.environ.get("AGENT_BROWSER_TIMEOUT", "90"),
    )
    parser.add_argument("--output-dir")
    parser.add_argument("--run-name", help="Experiment name; otherwise W8_RUN_NAME or run_1")
    parser.add_argument("--max-turns", "--max-steps", dest="max_steps", type=int, default=200,
        help="positive actor turn budget, at most 200")
    parser.add_argument("--settle-seconds", type=finite_nonnegative_float, default=os.environ.get("STEP_SETTLE_SECONDS", "1.0"))
    # Raw structured-snapshot budgets are explicit and independently adjustable.
    # A capture that reaches them reports ChromiumRL's own truncated statistics.
    parser.add_argument("--snapshot-max-nodes", type=int, default=int(os.environ.get("SNAPSHOT_MAX_NODES", "7000")))
    parser.add_argument("--snapshot-max-text-chars", type=int, default=int(os.environ.get("SNAPSHOT_MAX_TEXT_CHARS", "200000")))
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY", ""))
    parser.add_argument("--model", default=os.environ.get("ACTOR_MODEL", ""),
        help="must repeat the single configured ACTOR_MODEL; model overrides are rejected")
    parser.add_argument("--api-base-url", default=os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"))
    parser.add_argument("--browser-lang", default=os.environ.get("BROWSER_LANG", "en-US"))
    parser.add_argument(
        "--browser-accept-language",
        default=os.environ.get("BROWSER_ACCEPT_LANGUAGE", "en-US,en;q=0.9"),
    )
    return parser.parse_args(argv)



async def run_with_interrupt_handlers(args: argparse.Namespace) -> int:
    """Cancel the active run cleanly on Ctrl+C or task takeover."""
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    installed: list[signal.Signals] = []
    if task is not None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(signum, task.cancel)
                installed.append(signum)
            except (NotImplementedError, RuntimeError):
                pass
    try:
        return await run(args)
    except asyncio.CancelledError:
        return 130
    finally:
        for signum in installed:
            loop.remove_signal_handler(signum)


def main(argv: list[str] | None = None) -> int:
    """Dispatch offline trajectory export or run one live browser task."""
    try:
        args = parse_args(argv)
        if args.build_trajectory_run is not None:
            run_dir = args.build_trajectory_run.resolve()
            report = generate_trajectory_artifacts(run_dir)
            manifest_path = run_dir / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    raise RunnerError(f"manifest is not a JSON object: {manifest_path}")
                manifest["trajectory_export"] = report
                write_json(manifest_path, manifest)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["status"] == "complete" else 2
        if not args.output_dir:
            raise RunnerError("--output-dir is required for live and capture-only runs")
        from w8bench.run_paths import run_directory, resolve_run_name
        args.run_name = resolve_run_name(args.run_name)
        if args.observation_mode not in {"dom", "screenshot"}:
            raise RunnerError("--observation-mode dom|screenshot is required")
        args.output_dir = str(run_directory(args.output_dir, args.run_name) / args.observation_mode)
        return asyncio.run(run_with_interrupt_handlers(args))
    except (AgentBrowserBaseError, RunnerError, CDPError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
