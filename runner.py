#!/usr/bin/env python3
"""Generic model-driven runner for a ChromiumRL desktop browser.

DOM evidence comes directly from ChromiumRL.captureStructuredSnapshot.
Each observed state is stored once and actions refer to the state from which they execute.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

import aiohttp

from recorder_support import (
    RunnerError,
    append_json_line,
    clean_dom_text,
    normalized_http_url,
    same_document_except_fragment,
    utc_now,
    write_json,
    write_json_lines,
    write_text,
)
from capture import (
    FULL_RENDERER,
    MODEL_DOM_TEXT_RENDERER,
    ROOT,
    CDPClient,
    CDPError,
    CaptureBundle,
    PageLanguageState,
    action_observation_context,
    action_progress,
    agent_browser_control_signature,
    agent_browser_ref_line,
    agent_browser_target_identity,
    attach_agent_browser_observation,
    attach_agent_browser_observation_error,
    capture_after_action_bundle,
    capture_bundle,
    capture_call,
    capture_structured_snapshot,
    chromiumrl_action_coordinate,
    comparable_page_url,
    english_locale_path_url,
    ensure_english_page,
    is_cdp_transport_error,
    is_english_language,
    is_recoverable_action_error,
    materialize_bundle,
    normalized_observation_text,
    page_language_state,
    recorded_action_coordinate,
    renderer_versions,
    rewrite_ws_url,
    structured_snapshot_action_coordinate,
    synchronize_recorder_target,
    verify_agent_browser_action,
)
# Local adapter: supplies the browser-facing observation and action interface.
# ChromiumRL capture and recorder artifacts remain owned by this module.
from agent_browser import (
    AgentBrowserBaseError,
    AgentBrowserClient,
    AgentBrowserError,
    AgentBrowserObservation,
    AgentBrowserPage,
    agent_browser_session_name,
)
# Local prompt module: keeps model policy text separate from orchestration code.
from prompts import SYSTEM_PROMPT
# Recorder-local exception; standalone adapter errors are caught separately.
from trajectory import (
    TRAJECTORY_SCHEMA_VERSION,
    WEBSURFER_ACTION_MAP,
    generate_trajectory_artifacts,
    step_directory_number,
    websurfer_action,
)


TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DEFAULT_NOVNC_URL = "http://[::1]:39084/vnc.html?resize=scale&autoconnect=1&path=websockify"
MAX_TASK_MEMORY_CHARS = 8000
MAX_ACTION_THOUGHT_CHARS = 1200
# These schema limits bound model-authored bookkeeping, not captured DOM evidence.
# They prevent an accidental full response from being copied into every action row.


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
    if not isinstance(value, dict) or set(value) != expected:
        raise RunnerError("RUNNER_BROWSER_PROFILE_PROVENANCE has invalid fields")
    if not isinstance(value["container_id"], str) or not value["container_id"]:
        raise RunnerError("browser container id is missing")
    if not isinstance(value["container_created_at"], str) or not value["container_created_at"]:
        raise RunnerError("browser container creation time is missing")
    if not isinstance(value["profile_fresh_at_run_start"], bool):
        raise RunnerError("browser profile freshness must be boolean")
    count = value["tasks_previously_run_in_container"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise RunnerError("browser prior task count must be a non-negative integer")
    return value



def state_manifest_record(
    state_number: int,
    bundle: CaptureBundle,
    run_dir: Path,
) -> dict[str, Any]:
    """Describe one captured browser state without copying its files."""
    state_dir = bundle.snapshot_path.parent
    relative = lambda path: str(path.relative_to(run_dir))
    return {
        "state": state_number,
        "directory": relative(state_dir),
        "snapshot": relative(bundle.snapshot_path),
        "dom_full": relative(bundle.snapshot_path.with_name("dom_full.txt")),
        "model_dom": relative(bundle.snapshot_path.with_name("dom_model.json")),
        "model_text": relative(bundle.snapshot_path.with_name("dom_model.txt")),
        "screenshot": relative(bundle.screenshot_path),
        "agent_browser_snapshot": (
            relative(bundle.agent_browser_path) if bundle.agent_browser_path else None
        ),
        "agent_browser_action_snapshot": (
            relative(bundle.agent_browser_action_path)
            if bundle.agent_browser_action_path
            else None
        ),
        "document_url": bundle.document_url or bundle.snapshot.get("url") or "",
        "document_language": bundle.document_language or None,
    }


def quarantine_uncommitted_steps(
    run_dir: Path,
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    """Move partial action directories out of the authoritative step sequence.

    A directory becomes a recorded state after its evidence paths have been
    appended to the manifest. If an exception happens earlier, retain the
    partial files for diagnosis without letting them create a gap.
    """
    steps_root = run_dir / "steps"
    if not steps_root.is_dir():
        return []
    committed_names: set[str] = set()
    manifest_states = manifest.get("states")
    if isinstance(manifest_states, list):
        for row in manifest_states:
            if not isinstance(row, dict):
                continue
            number = row.get("state")
            if isinstance(number, int) and number > 0:
                committed_names.add(f"step_{number:03d}")

    quarantined: list[dict[str, str]] = []
    for step_dir in sorted(steps_root.iterdir()):
        if (
            not step_dir.is_dir()
            or not re.fullmatch(r"step_\d+", step_dir.name)
            or step_dir.name in committed_names
        ):
            continue
        incomplete_root = run_dir / "incomplete_steps"
        incomplete_root.mkdir(parents=True, exist_ok=True)
        destination = incomplete_root / step_dir.name
        suffix = 2
        while destination.exists():
            destination = incomplete_root / f"{step_dir.name}-{suffix}"
            suffix += 1
        step_dir.replace(destination)
        quarantined.append(
            {
                "source": str(step_dir.relative_to(run_dir)),
                "preserved_as": str(destination.relative_to(run_dir)),
                "reason": "state capture failed before its manifest commit",
            }
        )
    return quarantined


def finalize_recording_artifacts(
    run_dir: Path,
    manifest: dict[str, Any],
    final: dict[str, Any],
    *,
    manifest_status: str | None = None,
    error: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Finalize every initialized live run from its committed action steps.

    The final step number, manifest step count, trajectory rows, and WebSurfer
    rows use the same committed-action sequence. Model turns remain available
    separately because rejected decisions are not executed browser actions.
    """
    quarantined = quarantine_uncommitted_steps(run_dir, manifest)
    if quarantined:
        manifest.setdefault("incomplete_steps", []).extend(quarantined)
        manifest.setdefault("warnings", []).append(
            f"preserved {len(quarantined)} uncommitted action step(s) outside steps/"
        )

    manifest_steps = manifest.get("steps")
    committed_count = len(manifest_steps) if isinstance(manifest_steps, list) else 0
    normalized_final = dict(final)
    model_turn = normalized_final.get("model_turn", normalized_final.get("step"))
    normalized_final["step"] = committed_count
    if model_turn is not None:
        normalized_final["model_turn"] = model_turn
    normalized_final["recorded_steps"] = committed_count
    write_json(run_dir / "final.json", normalized_final)

    manifest["status"] = manifest_status or str(
        normalized_final.get("status") or "failure"
    )
    manifest["completed_at"] = utc_now()
    manifest["final"] = normalized_final
    if error:
        manifest["error"] = error
    trajectory_export = generate_trajectory_artifacts(run_dir)
    manifest["trajectory_export"] = trajectory_export
    manifest["artifact_alignment"] = {
        "committed_steps": committed_count,
        "trajectory_actions": trajectory_export.get("exported_actions"),
        "web_surfer_actions": trajectory_export.get("exported_actions"),
        "human_intervention_steps_skipped": len(
            trajectory_export.get("skipped") or []
        ),
    }
    if trajectory_export.get("skipped"):
        manifest.setdefault("warnings", []).append(
            "verifier trajectory export skipped "
            f"{len(trajectory_export['skipped'])} human intervention step(s)"
        )
    if trajectory_export["status"] != "complete":
        manifest.setdefault("warnings", []).append(
            "verifier trajectory export is invalid; rerun the task "
            "before dataset generation"
        )
    write_json(run_dir / "manifest.json", manifest)
    return normalized_final, trajectory_export


ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "navigate",
                "back",
                "click",
                "fill",
                "type",
                "select",
                "press",
                "scroll",
                "wait",
                "request_human",
                "terminate",
            ],
        },
        "url": {"type": ["string", "null"]},
        "id": {"type": ["string", "number", "null"]},
        "text": {"type": ["string", "null"]},
        "key": {"type": ["string", "null"]},
        "pixels": {"type": ["number", "null"]},
        "seconds": {"type": ["number", "null"]},
        "status": {"type": ["string", "null"], "enum": ["success", "failure", None]},
        "final_answer": {"type": ["string", "null"]},
        "thought": {
            "type": "string",
            "minLength": 1,
            "maxLength": MAX_ACTION_THOUGHT_CHARS,
        },
        "memory": {"type": ["string", "null"], "maxLength": MAX_TASK_MEMORY_CHARS},
    },
    "required": [
        "action",
        "url",
        "id",
        "text",
        "key",
        "pixels",
        "seconds",
        "status",
        "final_answer",
        "thought",
        "memory",
    ],
    "additionalProperties": False,
}

def load_env(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding the caller's environment."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def safe_task_id(value: str) -> str:
    """Validate a task id before it is used as part of a filesystem path."""
    if not TASK_ID_RE.fullmatch(value):
        raise RunnerError("task id may contain only letters, digits, '.', '_' and '-'")
    return value


def default_task_id() -> str:
    """Create a collision-resistant UTC task id for callers that omit one."""
    return datetime.now(timezone.utc).strftime("task-%Y%m%dT%H%M%SZ")


def prompt_for_human_intervention(
    reason: str,
    novnc_url: str,
    *,
    input_fn: Callable[[str], str] = input,
    output: TextIO | None = None,
    require_tty: bool = True,
) -> dict[str, Any]:
    """Pause for a recorded, explicitly permitted manual browser action."""
    stream = output or sys.stdout
    if require_tty and not sys.stdin.isatty():
        raise RunnerError(
            "human intervention was requested, but the runner has no interactive terminal"
        )
    started_at = utc_now()
    print("", file=stream)
    print("=== HUMAN INTERVENTION REQUIRED ===", file=stream)
    print(reason or "A visible browser challenge requires manual intervention.", file=stream)
    print(f"Open the current browser in noVNC: {novnc_url}", file=stream)
    print(
        "Perform only the requested permitted action. Do not sign in, pay, purchase, "
        "or violate the task constraints.",
        file=stream,
    )
    print(
        "When finished, return here and press Enter. Type 'abort' to stop the task.",
        file=stream,
    )
    try:
        response = input_fn("resume> ").strip().lower()
    except EOFError as error:
        raise RunnerError(
            "human intervention was requested, but terminal input closed"
        ) from error
    status = "aborted" if response in {"abort", "a", "stop", "quit", "q"} else "resumed"
    return {
        "status": status,
        "reason": reason,
        "novnc_url": novnc_url,
        "started_at": started_at,
        "completed_at": utc_now(),
    }


def response_text(response: dict[str, Any]) -> str:
    """Extract output text from either convenience or structured Responses fields."""
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in response.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
    if not parts:
        raise RunnerError(f"model response has no output text: {response}")
    return "\n".join(parts).strip()


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


def compact_model_response(response: dict[str, Any]) -> dict[str, Any]:
    """Store auditable model output/usage while excluding unrelated API metadata."""
    return {
        "id": response.get("id"),
        "output_text": response_text(response),
        "usage": response.get("usage"),
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
    """Parse and validate one structured action decision."""
    decision = parse_model_json_object(text, context="action")
    allowed = set(ACTION_SCHEMA["properties"]["action"]["enum"])
    action = decision.get("action")
    if action not in allowed:
        raise RunnerError(f"unsupported model action: {action!r}")
    return decision


class ModelClient:
    def __init__(self, api_key: str, model: str, base_url: str):
        """Validate API configuration and retain the latest prompt-size report."""
        if not api_key:
            raise RunnerError("OPENAI_API_KEY is required for model-driven runs")
        if not model:
            raise RunnerError("OPENAI_MODEL is required for model-driven runs")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.last_input_report: dict[str, Any] = {}

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit one Responses API request with bounded timeout and error detail."""
        request = urllib.request.Request(
            self.base_url + "/responses",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RunnerError(f"OpenAI API returned HTTP {error.code}: {body[:2000]}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RunnerError(f"OpenAI API request failed: {error}") from error
        if not isinstance(result, dict):
            raise RunnerError("OpenAI API returned a non-object response")
        return result

    async def decide(
        self,
        *,
        task: str,
        step: int,
        max_steps: int,
        allow_human_intervention: bool,
        bundle: CaptureBundle,
        task_memory: str,
        recent_actions: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Ask for one schema-constrained action from current recorded evidence."""
        recent_text = json.dumps(recent_actions[-6:], ensure_ascii=False)
        action_text = bundle.executable_agent_browser_text()
        chromiumrl_text = chromiumrl_evidence_for_model(bundle.model_text)
        self.last_input_report = {
            "full_agent_browser_chars": len(bundle.agent_browser_text),
            "action_agent_browser_chars": len(action_text),
            "chromiumrl_chars": len(bundle.model_text),
            "chromiumrl_prompt_chars": len(chromiumrl_text),
            "task_memory_chars": len(task_memory),
            "recent_actions_chars": len(recent_text),
            "observation_truncated": False,
            "conversation_history_reused": False,
        }
        prompt = (
            f"task:\n{task}\n\n"
            f"step: {step} of {max_steps}\n\n"
            f"human_intervention_available: {str(allow_human_intervention).lower()}\n\n"
            f"task_memory_from_prior_steps:\n{task_memory or '(none)'}\n\n"
            f"current_document_language: {bundle.document_language or 'unknown'}\n"
            f"current_document_url: {bundle.document_url or bundle.snapshot.get('url', '')}\n\n"
            f"current_agent_browser_snapshot:\n{action_text}\n\n"
            f"current_chromiumrl_evidence:\n{chromiumrl_text}\n\n"
            f"recent_action_outcomes:\n{recent_text or '[]'}\n\n"
            "Use the recorded progress signals and writable-control verification in "
            "recent_action_outcomes. If an action made no observable progress or a requested "
            "control value was not verified, change strategy instead of assuming it worked. If "
            "current_document_language is known and is not English, the task is behind a "
            "language gate: switch the site to English before doing task work or terminating "
            "successfully."
        )
        payload = {
            "model": self.model,
            "instructions": SYSTEM_PROMPT,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
            "max_output_tokens": 6000,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "browser_action",
                    "strict": True,
                    "schema": ACTION_SCHEMA,
                }
            },
        }
        response = await asyncio.to_thread(self._post, payload)
        decision = parse_decision(response_text(response))
        return decision, response



def action_rejection_reason(
    decision: dict[str, Any],
    available_refs: frozenset[str],
    recent_actions: list[dict[str, Any]],
    document_language: str = "",
    allow_human_intervention: bool = False,
    action_context: dict[str, str] | None = None,
) -> str:
    """Reject unsafe, stale, non-English, or provably stalled action proposals."""
    action_value = decision.get("action")
    action = "" if action_value is None else str(action_value)
    identifier_value = decision.get("id")
    identifier = AgentBrowserClient.action_ref(identifier_value)
    requires_id = action in {"click", "fill", "select"}
    if action == "request_human":
        if not allow_human_intervention:
            return "human intervention is not enabled for this run"
        if not clean_dom_text(decision.get("final_answer")):
            return "request_human requires a visible blocker and requested manual action"
    if (
        document_language
        and not is_english_language(document_language)
        and action == "terminate"
        and str(decision.get("status", "")).lower() == "success"
    ):
        return (
            f"current document language {document_language!r} is not English; "
            "switch the visible site locale before terminating successfully"
        )
    if requires_id and not identifier:
        return f"{action} requires a ref from the current agent-browser snapshot"
    if identifier and action in {"click", "fill", "type", "select", "scroll"} and identifier not in available_refs:
        return f"ref {identifier!r} is not present in the current agent-browser snapshot"
    if (
        identifier
        and action in {"click", "fill", "type", "select", "scroll"}
        and action_context is not None
    ):
        if clean_dom_text(action_context.get("ref")) != identifier:
            return f"ref {identifier!r} has no matching target identity in the current snapshot"
        if not clean_dom_text(action_context.get("role")):
            return f"ref {identifier!r} has no DOM-derived role in the current snapshot"
        if not clean_dom_text(action_context.get("name")):
            return f"ref {identifier!r} has no DOM-derived name in the current snapshot"
    executable_decision = browser_decision(decision)
    completed = [
        item
        for item in recent_actions
        if isinstance(item.get("action"), dict)
        and isinstance(item.get("progress"), dict)
        and (
            item.get("action_succeeded", True) is True
            or (
                item["action"].get("action") == "request_human"
                and item.get("human_intervention_status") == "resumed"
            )
        )
    ]
    if (
        action == "terminate"
        and str(decision.get("status", "")).lower() == "success"
        and not completed
    ):
        return (
            "successful termination requires at least one confirmed browser action; "
            "execute one action that brings the requested evidence into the visible "
            "viewport, such as scrolling the relevant item into view, then propose "
            "termination again"
        )

    def signature(
        value: dict[str, Any],
        context: dict[str, str] | None = None,
    ) -> tuple[Any, ...]:
        """Compare strategies semantically despite regenerated observation refs."""
        if value.get("action") == "scroll":
            pixels_value = value.get("pixels")
            pixels = 0.0 if pixels_value is None else float(pixels_value)
            direction = 1 if pixels > 0 else -1 if pixels < 0 else 0
            return (
                "scroll",
                direction,
                value.get("id"),
                clean_dom_text((context or {}).get("document_url")),
            )
        ref = AgentBrowserClient.action_ref(value.get("id"))
        control = clean_dom_text((context or {}).get("control_signature"))
        document_url = clean_dom_text((context or {}).get("document_url"))
        if ref and (control or document_url):
            non_ref_arguments = {
                key: item
                for key, item in value.items()
                if key != "id"
            }
            return (
                json.dumps(non_ref_arguments, sort_keys=True, ensure_ascii=False),
                control or f"ref:{ref}",
                document_url,
            )
        return (json.dumps(value, sort_keys=True, ensure_ascii=False),)

    candidate = signature(executable_decision, action_context)
    if completed and action not in {"scroll", "wait", "terminate"}:
        last = completed[-1]
        if (
            last["progress"].get("made_progress") is False
            and signature(last["action"], last.get("action_context")) == candidate
        ):
            return "exact consecutive duplicate activation made no observable progress"
    if len(completed) >= 3:
        recent_cycle = completed[-3:]
        first = signature(recent_cycle[0]["action"], recent_cycle[0].get("action_context"))
        second = signature(recent_cycle[1]["action"], recent_cycle[1].get("action_context"))
        third = signature(recent_cycle[2]["action"], recent_cycle[2].get("action_context"))
        if (
            all(item["progress"].get("made_progress") is False for item in recent_cycle)
            and first == third
            and second == candidate
            and first != second
        ):
            return "action would repeat a two-action cycle without forward progress"
    if len(completed) >= 2 and all(
        item["progress"].get("made_progress") is False for item in completed[-2:]
    ):
        stalled_signatures = {
            signature(item["action"], item.get("action_context"))
            for item in completed[-2:]
        }
        if candidate in stalled_signatures:
            return "action would retry a recently stalled strategy without observable progress"
    return ""


async def run(args: argparse.Namespace) -> int:
    """Execute one task and record one contiguous evidence step per real action.

    A step is committed only after its action, after-snapshot, screenshot, diff,
    and metadata are available. A terminate decision creates no browser action,
    so it does not create a gap in the numbered verifier trajectory.
    """
    if not args.capture_only and not args.task:
        raise RunnerError("--task is required unless --capture-only is used")
    task_id = safe_task_id(args.task_id or default_task_id())
    run_dir = Path(args.output_dir).resolve() / task_id
    run_dir.mkdir(parents=True, exist_ok=False)
    agent_browser = AgentBrowserClient(
        args.agent_browser_command,
        session=agent_browser_session_name(task_id, os.getpid()),
        cdp_url=args.cdp_url,
        timeout=args.agent_browser_timeout,
    )
    write_json(
        run_dir / "task.json",
        {
            "task_id": task_id,
            "source_task_id": args.source_task_id,
            "source_catalog": args.source_catalog,
            "task_name": args.task_name,
            "instruction": args.task or "capture-only",
            "start_url": args.start_url,
            "model": None if args.capture_only else args.model,
            "action_driver": None if args.capture_only else "agent-browser",
        },
    )

    current_renderer_versions = renderer_versions()
    manifest: dict[str, Any] = {
        "task_id": task_id,
        "source_task_id": args.source_task_id,
        "source_catalog": args.source_catalog,
        "task_name": args.task_name,
        "task": args.task or "capture-only",
        "created_at": utc_now(),
        "browser_image": os.environ.get("IMAGE", "w8-core:chromium-desktop"),
        "browser_profile_provenance": browser_profile_provenance_from_environment(),
        "dom_capture_parameters": {
            "max_nodes": args.snapshot_max_nodes,
            "max_text_chars": args.snapshot_max_text_chars,
            "in_viewport_only": True,
            "include_offscreen": False,
        },
        "dom_capture_source": "ChromiumRL.captureStructuredSnapshot",
        "action_coordinate_capture": {
            "source": "ChromiumRL.getAgentObservation",
            "fallback_source": "existing ChromiumRL.captureStructuredSnapshot bounds",
            "purpose": "pre-action coordinates only",
            "stored_as_dom_evidence": False,
            "takes_additional_structured_snapshot": False,
            "fallback_requires": "one visible hit-testable semantic match",
            "in_viewport_only": False,
            "include_content": False,
            "include_diff": False,
            "update_baseline": False,
            "max_elements": 10000,
            "max_interactive_elements": 10000,
        },
        "renderer_files": [FULL_RENDERER.name, MODEL_DOM_TEXT_RENDERER.name],
        "model_renderer_command": "ChromiumRL.getModelDOM",
        "renderer_versions": current_renderer_versions,
        "model_input_renderer": current_renderer_versions["model"],
        "model_input_policy": "dom_only",
        "model_context": {
            "full_agent_browser_evidence": "stored unchanged in agent_browser.txt",
            "action_namespace": "official agent-browser snapshot --interactive",
            "chromiumrl_action_ids_executable": False,
            "observation_truncation": False,
            "conversation_history_reused": False,
            "task_memory_max_chars": MAX_TASK_MEMORY_CHARS,
            "action_thought_max_chars": MAX_ACTION_THOUGHT_CHARS,
            "decision_log": "decisions.jsonl",
            "executed_trajectory": "trajectory.jsonl",
            "web_surfer_log": "web_surfer.log",
            "ref_target_identity": (
                "exact agent-browser ref plus role/name from the same "
                "pre-action interactive snapshot"
            ),
        },
        "step_numbering": {
            "step_directories": "contiguous captured browser states",
            "action_file": "action.json is stored in the state from which it executes",
            "model_turn_field": "model_turn",
            "decision_log_step": "model turn",
        },
        "action_driver": {
            "name": "agent-browser",
            "implementation": "official vercel-labs/agent-browser",
            "command": agent_browser.command,
            "session": agent_browser.session,
            "cdp_target": agent_browser.cdp_target,
        },
        "states": [],
        "steps": [],
        "human_intervention": {
            "enabled": bool(args.allow_human_intervention),
            "novnc_url": args.novnc_url if args.allow_human_intervention else None,
            "count": 0,
        },
        "post_action_language_redirect": bool(
            args.post_action_language_redirect
        ),
        "status": "running",
    }
    write_json(run_dir / "manifest.json", manifest)
    active_model_turn: int | None = None

    try:
        async with CDPClient(
            args.cdp_url,
            keep_existing_tabs=args.keep_existing_tabs,
            browser_language=args.browser_lang,
            browser_accept_language=args.browser_accept_language,
        ) as cdp:
            if not args.capture_only:
                await agent_browser.connect()
                manifest["action_driver"].update(
                    {
                        "version": agent_browser.version,
                        "connection": agent_browser.connection_result,
                    }
                )
            manifest["browser_session"] = cdp.connection_report
            session_warnings = cdp.connection_report.get("tab_cleanup", {}).get("warnings", [])
            if session_warnings:
                manifest.setdefault("warnings", []).extend(session_warnings)
            write_json(run_dir / "manifest.json", manifest)
            if args.start_url:
                if not args.start_url.startswith(("http://", "https://")):
                    raise RunnerError("--start-url must be http(s)")
                if args.capture_only:
                    await cdp.call("Page.navigate", {"url": args.start_url})
                else:
                    await agent_browser.execute({"action": "navigate", "url": args.start_url})
                await asyncio.sleep(args.settle_seconds)

            initial_language_redirects: list[dict[str, str]] = []
            if not args.capture_only:
                initial_target_sync = await synchronize_recorder_target(
                    cdp,
                    agent_browser,
                )
                manifest["initial_target_sync"] = initial_target_sync
                initial_language_state, initial_language_redirects = await ensure_english_page(
                    cdp,
                    agent_browser,
                    settle_seconds=args.settle_seconds,
                )
                manifest["initial_page_language"] = {
                    "url": initial_language_state.url,
                    "language": initial_language_state.language,
                    "error": initial_language_state.error or None,
                    "automatic_redirects": initial_language_redirects,
                }
                write_json(run_dir / "manifest.json", manifest)

            if args.capture_only:
                captured = await capture_bundle(
                    cdp,
                    run_dir / "steps" / "step_001",
                    max_nodes=args.snapshot_max_nodes,
                    max_text_chars=args.snapshot_max_text_chars,
                )
                manifest["states"].append(state_manifest_record(1, captured, run_dir))
                manifest["status"] = "captured"
                manifest["completed_at"] = utc_now()
                write_json(run_dir / "manifest.json", manifest)
                print(run_dir)
                return 0

            initial_snapshot = await capture_structured_snapshot(
                cdp,
                max_nodes=args.snapshot_max_nodes,
                max_text_chars=args.snapshot_max_text_chars,
            )
            current = await materialize_bundle(
                cdp, run_dir / "steps" / "step_001", initial_snapshot
            )
            current = await attach_agent_browser_observation(current, agent_browser)
            manifest["states"].append(state_manifest_record(1, current, run_dir))
            write_json(run_dir / "manifest.json", manifest)
            model = ModelClient(args.api_key, args.model, args.openai_base_url)
            recent_actions: list[dict[str, Any]] = []
            task_memory = ""
            decision_log_path = run_dir / "decisions.jsonl"
            final: dict[str, Any] | None = None
            recorded_step = 1

            for step in range(1, args.max_steps + 1):
                active_model_turn = step
                for decision_attempt in range(1, 5):
                    memory_before = task_memory
                    decision, model_response = await model.decide(
                        task=args.task,
                        step=step,
                        max_steps=args.max_steps,
                        allow_human_intervention=args.allow_human_intervention,
                        bundle=current,
                        task_memory=task_memory,
                        recent_actions=recent_actions,
                    )
                    proposed_memory = decision.get("memory")
                    candidate_task_memory = task_memory
                    if isinstance(proposed_memory, str) and proposed_memory.strip():
                        candidate_task_memory = proposed_memory.strip()
                    rejection_reason = action_rejection_reason(
                        decision,
                        current.agent_browser_refs,
                        recent_actions,
                        current.document_language,
                        args.allow_human_intervention,
                        action_observation_context(decision, current),
                    )
                    append_json_line(
                        decision_log_path,
                        {
                            "kind": "action_decision",
                            "recorded_at": utc_now(),
                            "step": step,
                            "model_turn": step,
                            "proposed_recorded_step": (
                                None
                                if decision.get("action") == "terminate"
                                else recorded_step + 1
                            ),
                            "attempt": decision_attempt,
                            "decision": decision,
                            "rejection_reason": rejection_reason or None,
                            "task_memory_before": memory_before,
                            "proposed_task_memory": candidate_task_memory,
                            "task_memory_after": task_memory,
                            "task_memory_committed": False,
                            "model_input": dict(model.last_input_report),
                            "model_response": compact_model_response(model_response),
                        },
                    )
                    if not rejection_reason:
                        break
                    rejected_decision = browser_decision(decision)
                    rejected_entry: dict[str, Any] = {
                        "step": step,
                        "model_turn": step,
                        "rejected_action": rejected_decision,
                        "reason": rejection_reason,
                    }
                    if recent_actions:
                        previous_rejection = recent_actions[-1]
                        if (
                            previous_rejection.get("rejected_action")
                            == rejected_decision
                            and previous_rejection.get("reason") == rejection_reason
                        ):
                            rejected_entry["repetition_note"] = (
                                "This proposal and rejection reason are identical to "
                                "the immediately preceding attempt; choose a different "
                                "action that addresses the rejection reason."
                            )
                    recent_actions.append(rejected_entry)
                else:
                    final = {
                        "status": "failure",
                        "final_answer": "model did not produce an executable action after four generic retries",
                        "step": step,
                    }
                    break

                if decision["action"] == "terminate":
                    task_memory = candidate_task_memory
                    final = {
                        "status": decision.get("status") or "failure",
                        "final_answer": decision.get("final_answer") or "",
                        "step": step,
                        "model": args.model,
                        "model_response_id": model_response.get("id"),
                        "model_usage": model_response.get("usage"),
                        "task_memory": task_memory,
                        "thought": decision["thought"],
                    }
                    break

                executable_decision = browser_decision(decision)
                accepted_thought = decision["thought"]
                executable_action_context = action_observation_context(
                    executable_decision,
                    current,
                )
                executable_action_target = agent_browser_target_identity(
                    executable_decision,
                    current,
                )
                executable_coordinate_capture: dict[str, Any] | None = None
                if AgentBrowserClient.action_ref(executable_decision.get("id")):
                    try:
                        executable_coordinate_capture = (
                            await recorded_action_coordinate(
                                cdp,
                                current,
                                executable_action_target,
                            )
                        )
                        if isinstance(executable_coordinate_capture, dict):
                            executable_coordinate_capture["phase"] = "pre_action"
                    except Exception as error:
                        executable_coordinate_capture = {
                            "status": "error",
                            "source": "ChromiumRL.getAgentObservation",
                            "coordinate_source": "get_agent_observation",
                            "phase": "pre_action",
                            "error": f"{type(error).__name__}: {error}",
                        }

                step_dir = current.snapshot_path.parent
                expected_state_dir = run_dir / "steps" / f"step_{recorded_step:03d}"
                if step_dir != expected_state_dir:
                    raise RunnerError("current state directory is not in the recorded sequence")
                next_state_number = recorded_step + 1
                next_state_dir = run_dir / "steps" / f"step_{next_state_number:03d}"
                started_at = utc_now()
                started = time.monotonic()
                action_error = ""
                recoverable_action_error = False
                action_result: dict[str, Any] | str | None = None
                human_intervention_record: dict[str, Any] | None = None
                human_aborted = False
                language_redirects: list[dict[str, str]] = []
                language_guard_error = ""
                target_sync: dict[str, Any] = {}
                if executable_decision["action"] == "request_human":
                    reason = clean_dom_text(executable_decision.get("final_answer"))
                    intervention_path = step_dir / "human_intervention.json"
                    pending_intervention = {
                        "step": recorded_step,
                        "model_turn": step,
                        "status": "waiting",
                        "reason": reason,
                        "novnc_url": args.novnc_url,
                        "started_at": started_at,
                        "state_snapshot": str(current.snapshot_path.relative_to(run_dir)),
                        "state_screenshot": str(current.screenshot_path.relative_to(run_dir)),
                    }
                    write_json(intervention_path, pending_intervention)
                    manifest["status"] = "waiting_for_human"
                    manifest["pending_human_intervention"] = pending_intervention
                    write_json(run_dir / "manifest.json", manifest)
                    try:
                        human_intervention_record = await asyncio.to_thread(
                            prompt_for_human_intervention,
                            reason,
                            args.novnc_url,
                        )
                        action_result = human_intervention_record
                        human_aborted = human_intervention_record["status"] == "aborted"
                        if not human_aborted:
                            await asyncio.sleep(args.settle_seconds)
                    except asyncio.CancelledError:
                        human_intervention_record = {
                            **pending_intervention,
                            "status": "interrupted",
                            "completed_at": utc_now(),
                        }
                        action_result = human_intervention_record
                        raise
                    except Exception as error:
                        action_error = f"{type(error).__name__}: {error}"
                        human_intervention_record = {
                            **pending_intervention,
                            "status": "error",
                            "completed_at": utc_now(),
                            "error": action_error,
                        }
                        action_result = human_intervention_record
                    finally:
                        assert human_intervention_record is not None
                        write_json(intervention_path, human_intervention_record)
                        manifest["status"] = "running"
                        manifest.pop("pending_human_intervention", None)
                        manifest["human_intervention"]["count"] += 1
                        manifest["human_intervention"].setdefault("steps", []).append(
                            {
                                "step": recorded_step,
                                "model_turn": step,
                                "status": human_intervention_record["status"],
                                "record": str(intervention_path.relative_to(run_dir)),
                            }
                        )
                        write_json(run_dir / "manifest.json", manifest)
                else:
                    try:
                        action_result = await agent_browser.execute(executable_decision)
                        await asyncio.sleep(args.settle_seconds)
                    except Exception as error:
                        action_error = f"{type(error).__name__}: {error}"
                        recoverable_action_error = is_recoverable_action_error(error)
                target_sync = await synchronize_recorder_target(
                    cdp,
                    agent_browser,
                )
                coordinate_was_resolved = (
                    isinstance(executable_coordinate_capture, dict)
                    and executable_coordinate_capture.get("status") == "resolved"
                )
                action_completed = (
                    not action_error
                    and isinstance(action_result, dict)
                    and action_result.get("success") is True
                )
                current_url = clean_dom_text(
                    current.snapshot.get("url") or current.document_url
                )
                active_url = clean_dom_text(target_sync.get("agent_browser_url"))
                if (
                    not coordinate_was_resolved
                    and AgentBrowserClient.action_ref(executable_decision.get("id"))
                    and action_completed
                    and same_document_except_fragment(current_url, active_url)
                ):
                    previous_coordinate_capture = executable_coordinate_capture
                    try:
                        fallback_capture = structured_snapshot_action_coordinate(
                            current.snapshot,
                            executable_action_target,
                        )
                        if isinstance(fallback_capture, dict):
                            fallback_capture["coordinate_source"] = (
                                "structured_snapshot_bounds"
                            )
                            fallback_capture["phase"] = (
                                "same_document_fallback"
                            )
                            fallback_capture["prior_coordinate_capture"] = (
                                previous_coordinate_capture
                            )
                            executable_coordinate_capture = fallback_capture
                    except Exception as error:
                        if isinstance(executable_coordinate_capture, dict):
                            executable_coordinate_capture["post_action_error"] = (
                                f"{type(error).__name__}: {error}"
                            )
                if not action_error and args.post_action_language_redirect:
                    try:
                        _language_state, language_redirects = await ensure_english_page(
                            cdp,
                            agent_browser,
                            settle_seconds=args.settle_seconds,
                        )
                    except Exception as error:
                        language_guard_error = f"{type(error).__name__}: {error}"
                next_state, capture_reconnects = await capture_after_action_bundle(
                    cdp,
                    agent_browser,
                    next_state_dir,
                    max_nodes=args.snapshot_max_nodes,
                    max_text_chars=args.snapshot_max_text_chars,
                )
                if capture_reconnects:
                    target_sync["capture_reconnects"] = capture_reconnects
                agent_browser_snapshot_error = ""
                try:
                    next_state = await attach_agent_browser_observation(next_state, agent_browser)
                except Exception as error:
                    agent_browser_snapshot_error = f"{type(error).__name__}: {error}"
                    next_state = attach_agent_browser_observation_error(next_state, error)
                action_verification = verify_agent_browser_action(
                    executable_decision, current, next_state
                )
                if agent_browser_snapshot_error and action_verification.get("applicable"):
                    action_verification.update(
                        status="unavailable",
                        reason="post-action agent-browser observation is unavailable",
                    )
                progress = action_progress(current, next_state)
                action_succeeded = bool(
                    not action_error
                    and not human_aborted
                    and isinstance(action_result, dict)
                    and action_result.get("success") is True
                )
                if action_succeeded:
                    task_memory = candidate_task_memory
                step_record = {
                    "step": recorded_step,
                    "model_turn": step,
                    "started_at": started_at,
                    "completed_at": utc_now(),
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "action": executable_decision,
                    "thought": accepted_thought,
                    "target": executable_action_target,
                    "coordinate_capture": executable_coordinate_capture,
                    "action_context": executable_action_context,
                    "action_driver": (
                        "human"
                        if executable_decision["action"] == "request_human"
                        else "agent-browser"
                    ),
                    "action_result": action_result,
                    "action_error": action_error or None,
                    "action_succeeded": action_succeeded,
                    "recoverable_action_error": recoverable_action_error,
                    "agent_browser_snapshot_error": agent_browser_snapshot_error or None,
                    "agent_browser_reconnect_count": agent_browser.reconnect_count,
                    "target_sync": target_sync,
                    "action_verification": action_verification,
                    "progress": progress,
                    "language_guard_error": language_guard_error or None,
                    "automatic_language_redirects": language_redirects,
                    "model": {
                        "name": args.model,
                        "response_id": model_response.get("id"),
                        "output_text": response_text(model_response),
                        "usage": model_response.get("usage"),
                    },
                    "task_memory": task_memory,
                    "model_input": dict(model.last_input_report),
                    "model_input_renderer": current_renderer_versions["model"],
                    "model_input_agent_browser": {
                        "version": agent_browser.version,
                        "snapshot_command": list(
                            current.agent_browser_action_snapshot_command
                        ),
                        "snapshot": str(
                            current.agent_browser_action_path.relative_to(run_dir)
                            if current.agent_browser_action_path is not None
                            else ""
                        ),
                        "full_evidence_snapshot_command": list(
                            current.agent_browser_snapshot_command
                        ),
                        "full_evidence_snapshot": str(
                            current.agent_browser_path.relative_to(run_dir)
                            if current.agent_browser_path is not None
                            else ""
                        ),
                    },
                    "state": recorded_step,
                    "next_state": next_state_number,
                    "state_snapshot": str(current.snapshot_path.relative_to(run_dir)),
                    "next_state_snapshot": str(next_state.snapshot_path.relative_to(run_dir)),
                    "state_model_dom": str(
                        current.snapshot_path.with_name("dom_model.json").relative_to(run_dir)
                    ),
                    "next_state_model_dom": str(
                        next_state.snapshot_path.with_name("dom_model.json").relative_to(run_dir)
                    ),
                    "state_screenshot": str(current.screenshot_path.relative_to(run_dir)),
                    "next_state_screenshot": str(next_state.screenshot_path.relative_to(run_dir)),
                    "next_state_agent_browser_snapshot": str(
                        next_state.agent_browser_path.relative_to(run_dir)
                        if next_state.agent_browser_path is not None
                        else ""
                    ),
                    "next_state_agent_browser_snapshot_command": list(
                        next_state.agent_browser_snapshot_command
                    ),
                    "next_state_agent_browser_action_snapshot": str(
                        next_state.agent_browser_action_path.relative_to(run_dir)
                        if next_state.agent_browser_action_path is not None
                        else ""
                    ),
                    "next_state_agent_browser_action_snapshot_command": list(
                        next_state.agent_browser_action_snapshot_command
                    ),
                    "document_language": current.document_language,
                    "next_document_language": next_state.document_language,
                    "document_language_error": current.document_language_error or None,
                    "next_document_language_error": next_state.document_language_error or None,
                }
                if human_intervention_record is not None:
                    step_record["human_intervention"] = {
                        **human_intervention_record,
                        "record": str(
                            (step_dir / "human_intervention.json").relative_to(run_dir)
                        ),
                    }
                if language_redirects:
                    manifest.setdefault("warnings", []).append(
                        f"step {recorded_step}: compatibility-mode post-action "
                        "language redirect followed the executed navigation"
                    )
                if action_verification.get("status") == "mismatch":
                    manifest.setdefault("warnings", []).append(
                        f"step {recorded_step}: requested control value was not verified in the next-state observation"
                    )
                manifest["action_driver"]["reconnect_count"] = agent_browser.reconnect_count
                write_json(step_dir / "action.json", step_record)
                manifest["states"].append(
                    state_manifest_record(next_state_number, next_state, run_dir)
                )
                manifest["steps"].append(step_record)
                write_json(run_dir / "manifest.json", manifest)
                current = next_state
                recorded_step = next_state_number
                recent_action = {
                    "step": step_record["step"],
                    "model_turn": step,
                    "action": executable_decision,
                    "action_context": executable_action_context,
                    "action_error": action_error or None,
                    "action_succeeded": action_succeeded,
                    "action_verification": action_verification,
                    "progress": progress,
                }
                if (
                    executable_decision["action"] == "request_human"
                    and isinstance(action_result, dict)
                ):
                    recent_action["human_intervention_status"] = action_result.get(
                        "status"
                    )
                recent_actions.append(recent_action)
                if human_aborted:
                    final = {
                        "status": "failure",
                        "final_answer": "human intervention was aborted by the operator",
                        "step": step,
                    }
                    break
                if action_error and not recoverable_action_error:
                    final = {"status": "failure", "final_answer": action_error, "step": step}
                    break
                if language_guard_error:
                    final = {
                        "status": "failure",
                        "final_answer": language_guard_error,
                        "step": step,
                    }
                    break
                if agent_browser_snapshot_error:
                    final = {
                        "status": "failure",
                        "final_answer": agent_browser_snapshot_error,
                        "step": step,
                    }
                    break

            if final is None:
                final = {"status": "failure", "final_answer": "maximum step count reached", "step": args.max_steps}
            if final["status"] != "success":
                await cdp.close_owned_target_on_failure()
            final, _trajectory_export = finalize_recording_artifacts(
                run_dir,
                manifest,
                final,
            )
            print(run_dir)
            return 0 if final["status"] == "success" else 2
    except asyncio.CancelledError:
        manifest["interruption"] = {
            "reason": "runner received a shutdown signal",
            "trajectory_exported": True,
        }
        manifest.setdefault("warnings", []).append(
            "run interrupted before completion; do not use it for verifier dataset generation"
        )
        finalize_recording_artifacts(
            run_dir,
            manifest,
            {
                "status": "failure",
                "run_status": "interrupted",
                "final_answer": "runner received a shutdown signal",
                "model_turn": active_model_turn,
            },
            manifest_status="interrupted",
        )
        raise
    except BaseException as error:
        error_text = f"{type(error).__name__}: {error}"
        finalize_recording_artifacts(
            run_dir,
            manifest,
            {
                "status": "failure",
                "run_status": "error",
                "final_answer": error_text,
                "model_turn": active_model_turn,
            },
            manifest_status="error",
            error=error_text,
        )
        raise
    finally:
        await agent_browser.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Load environment defaults, then parse live-run and export CLI modes."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env-file", default=".env")
    known, _ = pre.parse_known_args(argv)
    load_env(Path(known.env_file))

    parser = argparse.ArgumentParser(description="Run browser tasks and diff stored ChromiumRL structured snapshots")
    parser.add_argument("--env-file", default=known.env_file)
    parser.add_argument(
        "--build-trajectory-run",
        type=Path,
        help=(
            "Validate an existing run and atomically generate trajectory.jsonl "
            "plus web_surfer.log from confirmed executed actions"
        ),
    )
    parser.add_argument("--task")
    parser.add_argument("--task-id")
    parser.add_argument("--source-task-id")
    parser.add_argument("--source-catalog")
    parser.add_argument("--task-name")
    parser.add_argument("--start-url")
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument(
        "--allow-human-intervention",
        action="store_true",
        help=(
            "Allow the model to pause for a recorded manual CAPTCHA, access "
            "verification, or browser-native challenge"
        ),
    )
    parser.add_argument(
        "--novnc-url",
        default=os.environ.get("RUNNER_NOVNC_URL", DEFAULT_NOVNC_URL),
        help="Local noVNC URL printed when human intervention is requested",
    )
    language_redirect_group = parser.add_mutually_exclusive_group()
    language_redirect_group.add_argument(
        "--post-action-language-redirect",
        dest="post_action_language_redirect",
        action="store_true",
        help=(
            "Compatibility mode: permit an automatic English redirect between "
            "an action and its after-state capture"
        ),
    )
    language_redirect_group.add_argument(
        "--no-post-action-language-redirect",
        dest="post_action_language_redirect",
        action="store_false",
        help="Keep each recorded after-state limited to the executed browser action",
    )
    parser.set_defaults(post_action_language_redirect=False)
    parser.add_argument(
        "--keep-existing-tabs",
        action="store_true",
        help="Do not close other existing non-DevTools page targets on connect",
    )
    parser.add_argument("--cdp-url", default=os.environ.get("RUNNER_CDP_URL", "http://127.0.0.1:49335"))
    parser.add_argument(
        "--agent-browser-command",
        default=os.environ.get(
            "AGENT_BROWSER_COMMAND",
            "npx --yes agent-browser@0.27.3",
        ),
        help="Official agent-browser command used for all task interactions",
    )
    parser.add_argument(
        "--agent-browser-timeout",
        type=float,
        default=float(os.environ.get("AGENT_BROWSER_TIMEOUT", "90")),
    )
    parser.add_argument("--output-dir")
    # 80 bounds autonomous action attempts; it does not cap captured nodes/diffs.
    parser.add_argument("--max-steps", type=int, default=int(os.environ.get("RUN_MAX_STEPS", "80")))
    parser.add_argument("--settle-seconds", type=float, default=float(os.environ.get("STEP_SETTLE_SECONDS", "1.0")))
    # Raw structured-snapshot budgets are explicit and independently adjustable.
    # A capture that reaches them reports ChromiumRL's own truncated statistics.
    parser.add_argument("--snapshot-max-nodes", type=int, default=int(os.environ.get("SNAPSHOT_MAX_NODES", "7000")))
    parser.add_argument("--snapshot-max-text-chars", type=int, default=int(os.environ.get("SNAPSHOT_MAX_TEXT_CHARS", "200000")))
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", ""))
    parser.add_argument("--openai-base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
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
                if report.get("skipped"):
                    warning = (
                        "verifier trajectory export skipped "
                        f"{len(report['skipped'])} human intervention step(s)"
                    )
                    if warning not in manifest.setdefault("warnings", []):
                        manifest["warnings"].append(warning)
                if report["status"] == "complete":
                    manifest["warnings"] = [
                        warning
                        for warning in manifest.get("warnings", [])
                        if "trajectory export is invalid" not in str(warning)
                    ]
                write_json(manifest_path, manifest)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["status"] == "complete" else 2
        if not args.output_dir:
            raise RunnerError("--output-dir is required for live and capture-only runs")
        return asyncio.run(run_with_interrupt_handlers(args))
    except (AgentBrowserBaseError, RunnerError, CDPError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
