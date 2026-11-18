"""Paired recorder capture with isolated actor observations and target synchronization."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from .agent_browser import (
    AgentBrowserBaseError,
    AgentBrowserClient,
    AgentBrowserPage,
)
from .recorder_support import (
    RunnerError,
    clean_dom_text,
    normalized_http_url,
    write_json,
    append_json_line,
    utc_now,
    write_text,
)


PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
FULL_RENDERER = PACKAGE_ROOT / "renderers" / "render_chromiumrl_snapshot_full.py"
MODEL_DOM_TEXT_RENDERER = PACKAGE_ROOT / "renderers" / "render_chromiumrl_model_dom.py"
MODEL_DOM_COMMAND = "ChromiumRL.getModelDOM"
MODEL_DOM_RENDERER_NAME = "chromiumrl-model-dom"
LIVENESS_PROBE_SECONDS = 3.0
TARGET_IDENTITY_PROPERTY = "__w8_recorder_target_identity__"
TARGET_IDENTITY_WORLD = "w8-recorder-identity"

class CDPError(RunnerError):
    def __init__(self, method: str, error: Any):
        """Attach the failed protocol method and raw CDP error to the exception."""
        super().__init__(f"CDP command {method} failed: {error}")
        self.method = method
        self.error = error


def is_cdp_transport_error(error: BaseException) -> bool:
    """Recognize connection-loss messages that are safe to reconnect around."""
    detail = str(error).lower()
    return any(
        marker in detail
        for marker in (
            "cdp websocket closed",
            "cdp websocket is not connected",
            "cannot write to closing transport",
        )
    )


def action_observation_context(
    decision: dict[str, Any],
    bundle: CaptureBundle,
) -> dict[str, str]:
    """Describe an action target using the observation in which its ref exists.

    Agent-browser refs are regenerated for every snapshot. A bare ref therefore
    cannot identify a control across page changes. Pair it with the current
    document URL and the control's generic role/name signature so action-history
    checks compare observed controls rather than coincidentally equal ref strings.
    """
    ref = AgentBrowserClient.action_ref(decision.get("id"))
    line = agent_browser_ref_line(bundle.agent_browser_action_text, ref) if ref else ""
    target = agent_browser_target_identity(decision, bundle)
    return {
        "document_url": clean_dom_text(
            bundle.snapshot.get("url") or bundle.document_url
        ),
        "control_signature": agent_browser_control_signature(line) if line else "",
        "ref": target["ref"] if target else "",
        "role": target["role"] if target else "",
        "name": target["name"] if target else "",
    }


def action_progress(before: CaptureBundle, after: CaptureBundle) -> dict[str, bool]:
    """Report changes using only the selected observation channel."""
    if before.observation_mode != after.observation_mode:
        raise RunnerError("cannot compare progress across observation modes")
    if before.observation_mode == "screenshot":
        changed = before.screenshot_path.read_bytes() != after.screenshot_path.read_bytes()
        return {"screenshot_changed": changed, "made_progress": changed}
    result = {
        "url_changed": before.document_url != after.document_url,
        "dom_changed": before.model_text != after.model_text,
        "agent_browser_observation_changed": (
            before.agent_browser_action_text != after.agent_browser_action_text
        ),
    }
    return {**result, "made_progress": any(result.values())}


def normalized_observation_text(value: Any) -> str:
    """Normalize observation labels for conservative semantic comparisons."""
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip().casefold()


def agent_browser_ref_line(observation: str, ref: str) -> str:
    """Find the exact observation line that defines an agent-browser ref."""
    marker = re.compile(rf"\bref={re.escape(ref)}(?=[,\]\s]|$)")
    return next((line.strip() for line in observation.splitlines() if marker.search(line)), "")


def agent_browser_control_signature(line: str) -> str:
    """Role/name portion of a snapshot line, excluding volatile ref and value."""
    prefix = line.strip().lstrip("- ").split("[", 1)[0]
    return normalized_observation_text(prefix)


def agent_browser_line_identity(line: str) -> dict[str, str]:
    """Parse the generic role/name shown on one agent-browser snapshot line."""
    match = re.match(
        r'^\s*-\s*(?P<role>\S+)(?:\s+(?P<name>"(?:\\.|[^"\\])*"))?\s+\[',
        line,
    )
    if not match:
        return {"role": "", "name": ""}
    raw_name = match.group("name")
    name = ""
    if raw_name:
        try:
            parsed_name = json.loads(raw_name)
        except (TypeError, ValueError):
            parsed_name = ""
        if isinstance(parsed_name, str):
            name = parsed_name
    return {"role": match.group("role"), "name": name}


def agent_browser_target_identity(
    decision: dict[str, Any],
    bundle: CaptureBundle,
) -> dict[str, str] | None:
    """Return the semantic identity attached to the exact executable ref.

    The role and name come from the same official agent-browser interactive
    snapshot response whose ref is passed to the action. ChromiumRL refs are a
    separate namespace and are deliberately not used for this mapping.
    """
    ref = AgentBrowserClient.action_ref(decision.get("id"))
    if not ref:
        return None
    target = bundle.agent_browser_targets.get(ref, {})
    role = str(target.get("role", ""))
    name = str(target.get("name", ""))
    if not clean_dom_text(role) or not clean_dom_text(name):
        line = agent_browser_ref_line(bundle.agent_browser_action_text, ref)
        line_identity = agent_browser_line_identity(line)
        if not clean_dom_text(role):
            role = line_identity["role"]
        if not clean_dom_text(name):
            name = line_identity["name"]
    return {
        "ref": ref,
        "role": role,
        "name": name,
    }


def run_renderer(arguments: list[str]) -> None:
    """Run a renderer as a checked subprocess and surface its stderr on failure."""
    try:
        completed = subprocess.run(
            [sys.executable, *arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        renderer_path = arguments[0] if arguments else "<unknown renderer>"
        raise RunnerError(
            f"renderer timed out after 300 seconds: {renderer_path}"
        ) from error
    if completed.returncode != 0:
        raise RunnerError(f"renderer failed: {completed.stderr.strip()}")


def render_full_stored_snapshot(snapshot_path: Path) -> None:
    """Render only the audit/full text projection from stored dom.json."""
    run_renderer(
        [
            str(FULL_RENDERER),
            str(snapshot_path),
            "--output",
            str(snapshot_path.with_name("dom_full.txt")),
            "--include-action-index",
            "--include-child-refs",
        ]
    )


def render_model_dom_stored_projection(model_dom_path: Path) -> None:
    """Render only the browser-produced structured model-DOM JSON."""
    run_renderer(
        [
            str(MODEL_DOM_TEXT_RENDERER),
            str(model_dom_path),
            "--output",
            str(model_dom_path.with_suffix(".txt")),
        ]
    )


def file_version(path: Path) -> dict[str, str]:
    """Return a content hash so artifacts identify the exact renderer source."""
    return {
        "file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def renderer_versions() -> dict[str, dict[str, str]]:
    """Content-addressed renderer version used for model and audit text."""
    return {
        "full": file_version(FULL_RENDERER),
        "model": {
            "command": MODEL_DOM_COMMAND,
            "renderer_name": MODEL_DOM_RENDERER_NAME,
            "text_renderer": file_version(MODEL_DOM_TEXT_RENDERER),
        },
    }


async def capture_call(
    cdp: CDPClient,
    method: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Recover one read-only observation after checking its exact page target."""
    for attempt in range(1, 3):
        try:
            return await cdp.call(method, params)
        except (asyncio.TimeoutError, TimeoutError, CDPError) as error:
            internal = isinstance(error, CDPError) and isinstance(error.error, dict) and error.error.get("code") == -32603
            if isinstance(error, CDPError) and not internal:
                raise
            if attempt == 2:
                failure = RunnerError(f"{method} failed after 2 read-only attempts: {type(error).__name__}: {error}")
                failure.technical_failure_class = "cdp_stall"
                raise failure from error
            await cdp.recover_observation()
            await asyncio.sleep(0.5 * attempt)


async def capture_structured_snapshot(
    cdp: CDPClient,
    *,
    max_nodes: int,
    max_text_chars: int,
) -> dict[str, Any]:
    """Capture viewport DOM, retrying empty snapshots of populated documents."""
    params: dict[str, Any] = {
        "inViewportOnly": True,
        "maxNodes": max_nodes,
        "maxTextChars": max_text_chars,
        "includeOffscreen": False,
    }
    for capture_attempt in range(1, 4):
        result = await capture_call(
            cdp,
            "ChromiumRL.captureStructuredSnapshot",
            params,
        )
        snapshot = result.get("snapshot")
        if not isinstance(snapshot, dict):
            raise RunnerError(f"unexpected ChromiumRL snapshot response: {result}")

        stats = snapshot.get("stats")
        raw_nodes = stats.get("rawNodes") if isinstance(stats, dict) else None
        returned_nodes = stats.get("returnedNodes") if isinstance(stats, dict) else None
        if not (
            isinstance(raw_nodes, int)
            and raw_nodes > 0
            and isinstance(returned_nodes, int)
            and returned_nodes == 0
        ):
            return snapshot
        if capture_attempt < 3:
            await asyncio.sleep(0.25 * capture_attempt)

    raise RunnerError(
        "ChromiumRL.captureStructuredSnapshot returned zero nodes for a "
        "non-empty document after 3 attempts"
    )


async def model_dom_from_snapshot(
    cdp: CDPClient,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Build structured model-facing DOM JSON inside Chromium."""
    result = await capture_call(cdp, MODEL_DOM_COMMAND, {"snapshot": snapshot})
    model_dom = result.get("modelDOM")
    if not isinstance(model_dom, dict):
        raise RunnerError(f"unexpected {MODEL_DOM_COMMAND} response: {result}")
    renderer_name = model_dom.get("rendererName")
    if renderer_name != MODEL_DOM_RENDERER_NAME:
        raise RunnerError(
            f"unexpected {MODEL_DOM_COMMAND} rendererName: "
            f"{renderer_name!r}"
        )
    sections = model_dom.get("sections")
    if not isinstance(sections, list) or not sections:
        raise RunnerError(f"unexpected {MODEL_DOM_COMMAND} sections: {sections!r}")
    return model_dom


async def capture_after_action_bundle(
    cdp: CDPClient,
    agent_browser: AgentBrowserClient | None,
    directory: Path,
    *,
    max_nodes: int,
    max_text_chars: int,
    observation_mode: str = "dom",
    attempts: int = 3,
) -> tuple[CaptureBundle, list[dict[str, Any]]]:
    """Retry observation transport only; never replay an executed action."""
    reconnects = []
    for attempt in range(1, max(1, attempts) + 1):
        try:
            bundle = await capture_bundle(cdp, directory, max_nodes=max_nodes,
                max_text_chars=max_text_chars, observation_mode=observation_mode)
            return bundle, reconnects
        except RunnerError as error:
            if not is_cdp_transport_error(error) or attempt >= attempts:
                raise
            failed_metadata = directory / "capture.json"
            append_json_line(directory.parent.parent / "capture_failures.jsonl", {
                "directory": str(directory.relative_to(directory.parent.parent)), "attempt": attempt,
                "recorded_at": utc_now(), "error": f"{type(error).__name__}: {error}",
                "capture": json.loads(failed_metadata.read_text()) if failed_metadata.is_file() else None})
            shutil.rmtree(directory, ignore_errors=True)
            reconnects.append(await synchronize_recorder_target(cdp, agent_browser))
            await asyncio.sleep(0.75 * attempt)
    raise AssertionError("unreachable")


@dataclass
class _CaptureState:
    snapshot: dict[str, Any] = field(default_factory=dict)
    snapshot_path: Path | None = None
    model_text: str = ""
    screenshot_path: Path | None = None
    dom_error: Exception | None = None


async def _capture_frame(cdp: CDPClient, metadata: dict[str, Any], kind: str) -> dict[str, Any]:
    try:
        response = await capture_call(cdp, "Page.getFrameTree", {})
        return response.get("frameTree", {}).get("frame", {})
    except Exception as error:
        if getattr(error, "technical_failure_class", None):
            raise
        metadata["metadata_errors"].append({"kind": kind, "error": f"{type(error).__name__}: {error}"})
        return {}


async def _capture_screenshot(cdp: CDPClient, directory: Path) -> Path:
    result = await capture_call(cdp, "Page.captureScreenshot", {
        "format": "png", "fromSurface": True, "captureBeyondViewport": False})
    data = base64.b64decode(result["data"], validate=True)
    import io
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        if cdp.viewport is not None and image.size != cdp.viewport:
            raise RunnerError("screenshot dimensions differ from the coordinate viewport")
        image.verify()
    path = directory / "screenshot.png"
    path.write_bytes(data)
    return path


async def _capture_phase(cdp: CDPClient, directory: Path, phase: str, state: _CaptureState,
    max_nodes: int, max_text_chars: int) -> None:
    if phase == "structured_dom":
        state.snapshot = await capture_structured_snapshot(cdp, max_nodes=max_nodes,
            max_text_chars=max_text_chars)
        state.snapshot_path = directory / "dom.json"
        write_json(state.snapshot_path, {"result": {"snapshot": state.snapshot}})
        render_full_stored_snapshot(state.snapshot_path)
    elif phase == "dom_model_artifacts":
        if state.dom_error is not None:
            raise RunnerError("structured DOM capture unavailable")
        model_dom = await model_dom_from_snapshot(cdp, state.snapshot)
        model_path = directory / "dom_model.json"
        write_json(model_path, {"result": {"modelDOM": model_dom}})
        render_model_dom_stored_projection(model_path)
        state.model_text = model_path.with_suffix(".txt").read_text(encoding="utf-8")
    else:
        state.screenshot_path = await _capture_screenshot(cdp, directory)


def _invalidate_capture(directory: Path, phase: str, state: _CaptureState,
    record: dict[str, Any], error: Exception) -> None:
    names = {"structured_dom": ("dom.json", "dom_full.txt"),
        "dom_model_artifacts": ("dom_model.json", "dom_model.txt"),
        "screenshot": ("screenshot.png",)}[phase]
    for name in names:
        for path in (directory / name, directory / f".{name}.tmp"):
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                record.setdefault("cleanup_errors", []).append(str(cleanup_error))
    if phase == "structured_dom":
        state.snapshot_path = None
    elif phase == "dom_model_artifacts":
        state.model_text = ""
    else:
        state.screenshot_path = None
    if phase != "screenshot":
        state.dom_error = error


async def _record_capture_phase(cdp: CDPClient, directory: Path, phase: str,
    state: _CaptureState, metadata: dict[str, Any], interval_started: float,
    observation_mode: str, max_nodes: int, max_text_chars: int) -> None:
    record = {"kind": phase, "started_at": utc_now()}
    started = time.monotonic()
    try:
        await _capture_phase(cdp, directory, phase, state, max_nodes, max_text_chars)
        record["status"] = "captured"
    except Exception as error:
        record.update(status="error", error=f"{type(error).__name__}: {error}")
        metadata["paired_complete"] = False
        _invalidate_capture(directory, phase, state, record, error)
        if getattr(error, "technical_failure_class", None) in {"browser_crash", "cdp_stall"} or (phase == "screenshot") == (observation_mode == "screenshot"):
            if not getattr(error, "technical_failure_class", None):
                error.technical_failure_class = "capture_failure"
            raise
    finally:
        record.update(ended_at=utc_now(), duration_seconds=time.monotonic() - started)
        metadata["captures"].append(record)
        metadata.update(ended_at=utc_now(), duration_seconds=time.monotonic() - interval_started)
        write_json(directory / "capture.json", metadata)


async def _finish_capture(cdp: CDPClient, directory: Path, state: _CaptureState,
    metadata: dict[str, Any], interval_started: float, navigation_start: int,
    observation_mode: str) -> CaptureBundle:
    frame = await _capture_frame(cdp, metadata, "url_after")
    metadata["url_after"] = str(frame.get("url", metadata["url_before"]))
    metadata["loader_id_after"] = frame.get("loaderId", "")
    metadata["navigation_during_capture"] = (metadata["url_before"] != metadata["url_after"]
        or metadata["loader_id_before"] != metadata["loader_id_after"]
        or len(cdp.navigation_events) != navigation_start)
    metadata["navigation_events"] = cdp.navigation_events[navigation_start:]
    metadata.update(ended_at=utc_now(), duration_seconds=time.monotonic() - interval_started,
        url_metadata_complete=not metadata["metadata_errors"],
        document_language=str(state.snapshot.get("documentLanguage") or state.snapshot.get("language") or "")
            if observation_mode == "dom" else None)
    write_json(directory / "capture.json", metadata)
    return CaptureBundle(snapshot=state.snapshot, snapshot_path=state.snapshot_path, model_text=state.model_text,
        screenshot_path=state.screenshot_path, observation_mode=observation_mode,
        document_url=metadata["url_after"], capture_metadata=metadata,
        document_language=str(state.snapshot.get("documentLanguage") or state.snapshot.get("language") or ""))


async def capture_bundle(cdp: CDPClient, directory: Path, *, max_nodes: int,
    max_text_chars: int, observation_mode: str = "dom") -> CaptureBundle:
    """Record paired evidence, with only the selected channel driving the actor."""
    if observation_mode not in {"dom", "screenshot"}:
        raise RunnerError("unknown observation mode")
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {"started_at": utc_now(), "target_id": str(cdp.target.get("targetId", "")),
        "session_id": getattr(cdp, "session_id", ""), "captures": [],
        "capture_order": ["structured_dom", "dom_model_artifacts", "screenshot"],
        "paired_complete": True, "navigation_during_capture": False,
        "setup_errors": list(getattr(cdp, "capture_setup_errors", [])), "metadata_errors": []}
    interval_started = time.monotonic()
    navigation_start = len(cdp.navigation_events)
    frame = await _capture_frame(cdp, metadata, "url_before")
    metadata["url_before"] = str(frame.get("url", cdp.target.get("url", "")))
    metadata["loader_id_before"] = frame.get("loaderId", "")
    state = _CaptureState()
    for phase in metadata["capture_order"]:
        await _record_capture_phase(cdp, directory, phase, state, metadata,
            interval_started, observation_mode, max_nodes, max_text_chars)
    return await _finish_capture(cdp, directory, state, metadata, interval_started,
        navigation_start, observation_mode)


async def _snapshot_action_refs(agent_browser: AgentBrowserClient, attempts: int, cdp: CDPClient) -> Any:
    recovered = False
    for attempt in range(1, max(1, attempts) + 1):
        snapshot_task = None
        crash_wait = None
        try:
            if cdp._page_failure is not None:
                raise cdp._page_failure
            snapshot_task = asyncio.create_task(agent_browser.snapshot())
            crash_wait = asyncio.create_task(cdp.page_failure_event.wait())
            done, _ = await asyncio.wait({snapshot_task, crash_wait}, return_when=asyncio.FIRST_COMPLETED)
            if crash_wait in done:
                raise cdp._page_failure or RunnerError("page target failed during reference capture")
            return await snapshot_task
        except Exception as error:
            if cdp._page_failure is error or getattr(error, "technical_failure_class", None) == "browser_crash":
                raise
            if attempt >= max(1, attempts):
                error.technical_failure_class = "snapshot_exhaustion"
                raise
            detail = str(error).lower()
            if "timed out" in detail or "internal error" in detail or isinstance(error, TimeoutError):
                if recovered:
                    error.technical_failure_class = "snapshot_exhaustion"
                    raise
                await cdp.recover_observation()
                recovered = True
            await agent_browser.reconnect()
            await cdp.synchronize_target()
            active_page = await agent_browser.active_page(cdp)
            selected = cdp._select_active_target(active_page, [
                {"targetId": key} for key in cdp.target_registry])
            if selected["targetId"] != cdp.target.get("targetId"):
                failure = RunnerError("reference session rebound to a different captured page")
                failure.technical_failure_class = "snapshot_exhaustion"
                raise failure
            await asyncio.sleep(0.75 * attempt)
        finally:
            for task in (snapshot_task, crash_wait):
                if task is not None and not task.done():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
    raise AssertionError("unreachable")


async def _finish_reference_capture(bundle: CaptureBundle, cdp: CDPClient,
    refs_started: float) -> None:
    try:
        frame = (await capture_call(cdp, "Page.getFrameTree", {})).get("frameTree", {}).get("frame", {})
    except Exception as error:
        if getattr(error, "technical_failure_class", None):
            raise
        frame = {}
        bundle.capture_metadata["metadata_errors"].append(
            {"kind": "url_after_refs", "error": f"{type(error).__name__}: {error}"})
        bundle.capture_metadata["url_metadata_complete"] = False
    bundle.capture_metadata["url_after"] = str(frame.get("url", bundle.capture_metadata["url_after"]))
    bundle.capture_metadata["loader_id_after"] = frame.get("loaderId", bundle.capture_metadata["loader_id_after"])
    bundle.capture_metadata["navigation_events"] = [event for event in cdp.navigation_events
        if event["recorded_at"] >= bundle.capture_metadata["started_at"]]
    bundle.capture_metadata["navigation_during_capture"] = bool(
        bundle.capture_metadata["navigation_events"]
        or bundle.capture_metadata["url_before"] != bundle.capture_metadata["url_after"]
        or bundle.capture_metadata["loader_id_before"] != bundle.capture_metadata["loader_id_after"])
    bundle.document_url = bundle.capture_metadata["url_after"]
    bundle.capture_metadata["ended_at"] = utc_now()
    bundle.capture_metadata["duration_seconds"] += time.monotonic() - refs_started
    write_json(bundle.directory / "capture.json", bundle.capture_metadata)


async def attach_agent_browser_observation(bundle: CaptureBundle,
    agent_browser: AgentBrowserClient, cdp: CDPClient, *, attempts: int = 3) -> CaptureBundle:
    """Store the exact agent-browser ref snapshot supplied to the model."""
    if bundle.observation_mode != "dom":
        raise RunnerError("accessibility observations are forbidden in screenshot mode")
    refs_started_at, refs_started = utc_now(), time.monotonic()
    action_observation = await _snapshot_action_refs(agent_browser, attempts, cdp)
    action_path = bundle.snapshot_path.with_name("agent_browser_actions.txt")
    write_text(action_path, action_observation.text)
    bundle.agent_browser_action_text = action_observation.text
    bundle.agent_browser_refs = action_observation.refs
    bundle.agent_browser_targets = action_observation.targets
    bundle.agent_browser_action_path = action_path
    bundle.capture_metadata["capture_order"].append("executable_refs")
    bundle.capture_metadata["captures"].append({"kind": "executable_refs", "status": "captured",
        "started_at": refs_started_at, "ended_at": utc_now(),
        "duration_seconds": time.monotonic() - refs_started})
    await _finish_reference_capture(bundle, cdp, refs_started)
    return bundle


async def _synchronize_capture_tab(cdp: CDPClient) -> dict[str, Any]:
    # Target metadata identifies tabs without reading page content.
    try:
        targets = (await cdp.call("Target.getTargets", attached=False)).get("targetInfos", [])
    except RunnerError as error:
        if not is_cdp_transport_error(error):
            raise
        target = cdp.target
        return await cdp.reconnect_active_page(AgentBrowserPage(
            str(target.get("targetId", "")), str(target.get("url", "")), ""))
    children = [item for item in targets if item.get("type") == "page"
        and item.get("openerId") == cdp.target.get("targetId")]
    if len(children) > 1:
        raise RunnerError("multiple popup tabs opened; target is ambiguous")
    selected = children[0] if children else next((item for item in targets
        if item.get("targetId") == cdp.target.get("targetId")), None)
    if selected is None:
        raise RunnerError("the task tab closed without a unique popup")
    return await cdp.synchronize_target(AgentBrowserPage(
        str(selected["targetId"]), str(selected.get("url", "")), ""))


async def synchronize_recorder_target(
    cdp: CDPClient,
    agent_browser: AgentBrowserClient | None,
    *,
    attempts: int = 6,
) -> dict[str, Any]:
    """Synchronize capture with the active action tab, with bounded reconnects."""
    if agent_browser is None:
        return await _synchronize_capture_tab(cdp)
    last_error: BaseException | None = None
    observation_recovered = False
    for attempt in range(1, max(1, attempts) + 1):
        try:
            await cdp.synchronize_target()
            active_page = await agent_browser.active_page(cdp)
            return await cdp.synchronize_target(active_page)
        except AgentBrowserBaseError as error:
            last_error = error
            if cdp._page_failure is not None:
                raise cdp._page_failure
            if getattr(error, "technical_failure_class", None) == "cdp_stall":
                if observation_recovered:
                    raise
                await cdp.recover_observation()
                observation_recovered = True
            if attempt < attempts:
                await agent_browser.reconnect()
                await asyncio.sleep(0.5 * attempt)
        except RunnerError as error:
            last_error = error
            if getattr(error, "technical_failure_class", None) in {"browser_crash", "cdp_stall"}:
                raise
            transport_lost = is_cdp_transport_error(error)
            if transport_lost:
                try:
                    # Restore the browser transport before the CLI identity
                    # handshake; its target comes from CDP, never page globals.
                    report = await cdp.reconnect_active_page(AgentBrowserPage("", "", "",
                        target_id=str(cdp.target.get("targetId", ""))))
                    await cdp.synchronize_target()
                    active_page = await agent_browser.active_page(cdp)
                    report.update(await cdp.synchronize_target(active_page))
                    report["synchronization_attempt"] = attempt
                    return report
                except (AgentBrowserBaseError, RunnerError, OSError) as reconnect_error:
                    last_error = reconnect_error
            if attempt < attempts:
                await asyncio.sleep(0.5 * attempt)
    assert last_error is not None
    raise RunnerError(
        f"could not synchronize recorder to agent-browser active tab after "
        f"{max(1, attempts)} attempts: {last_error}"
    ) from last_error


@dataclass
class CaptureBundle:
    snapshot: dict[str, Any] = field(default_factory=dict)
    snapshot_path: Path | None = None
    model_text: str = ""
    screenshot_path: Path | None = None
    observation_mode: str = "dom"
    agent_browser_action_text: str = ""
    agent_browser_refs: frozenset[str] = field(default_factory=frozenset)
    agent_browser_targets: dict[str, dict[str, str]] = field(default_factory=dict)
    agent_browser_action_path: Path | None = None
    document_language: str = ""
    document_url: str = ""
    capture_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        path = self.snapshot_path if self.observation_mode == "dom" else self.screenshot_path
        if path is None:
            raise RunnerError("capture has no active observation artifact")
        return path.parent

    @property
    def observation_path(self) -> Path:
        path = self.snapshot_path.with_name("dom_model.txt") if self.observation_mode == "dom" else self.screenshot_path
        if path is None:
            raise RunnerError("capture has no active observation artifact")
        return path



class CDPClient:
    def __init__(
        self,
        http_url: str,
        timeout: float = 90.0,
        *,
        keep_existing_tabs: bool = False,
        browser_language: str = "",
        browser_accept_language: str = "",
        observation_mode: str = "dom",
        viewport: tuple[int, int] | None = None,
    ):
        """Configure one flattened CDP session and its tab/locale policy."""
        if observation_mode not in {"dom", "screenshot"}:
            raise RunnerError("unknown observation mode")
        self.observation_mode = observation_mode
        self.viewport = viewport
        self.http_url = normalized_http_url(http_url)
        self.timeout = timeout
        self.keep_existing_tabs = keep_existing_tabs
        self.browser_language = browser_language
        self.browser_accept_language = browser_accept_language
        self.browser_version = ""
        self.http: aiohttp.ClientSession | None = None
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self.reader: asyncio.Task[None] | None = None
        self._transport_error: RunnerError | None = None
        self.next_id = 0
        self.pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.session_id = ""
        self.navigation_events: list[dict[str, Any]] = []
        self.capture_setup_errors: list[dict[str, Any]] = []
        self.target: dict[str, Any] = {}
        self.connection_report: dict[str, Any] = {}
        self._failure_target_cleanup_attempted = False
        self.recording_dir: Path | None = None
        self._page_failure: RunnerError | None = None
        self._expected_detaches: set[str] = set()
        self._session_detached = False
        self.page_failure_event = asyncio.Event()
        self._expected_target_closures: set[str] = set()
        self.target_registry: dict[str, dict[str, Any]] = {}
        self.session_targets: dict[str, str] = {}
        self.identity_reads: dict[str, set[str]] = {}

    async def _enable_attached_target(self) -> dict[str, Any]:
        """Enable capture domains, the coordinate viewport and configured locales."""
        await self.call("Page.enable")
        await self.call("Inspector.enable")
        target_id = str(self.target.get("targetId", ""))
        entry = self.target_registry.setdefault(target_id, {"target_id": target_id})
        entry["identity_world"] = TARGET_IDENTITY_WORLD
        marker = entry.setdefault("identity_marker", secrets.token_hex(16))
        expression = f"Object.defineProperty(globalThis,{json.dumps(TARGET_IDENTITY_PROPERTY)},{{value:{json.dumps(marker)},configurable:true}});void 0"
        frame = (await self.call("Page.getFrameTree"))["frameTree"]["frame"]["id"]
        world = await self.call("Page.createIsolatedWorld", {"frameId": frame,
            "worldName": TARGET_IDENTITY_WORLD, "grantUniveralAccess": False})
        await self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True,
            "contextId": world["executionContextId"]})
        try:
            await self.call("ChromiumRL.enable")
        except Exception as error:
            if self.observation_mode == "dom":
                raise
            self.capture_setup_errors.append({"method": "ChromiumRL.enable", "recorded_at": utc_now(),
                "error": f"{type(error).__name__}: {error}"})
        if self.viewport is not None:
            await self.call("Emulation.setDeviceMetricsOverride", {"width": self.viewport[0],
                "height": self.viewport[1], "deviceScaleFactor": 1, "mobile": False})
        return await self._configure_locales()

    async def _configure_locales(self) -> dict[str, Any]:
        locale_setup: dict[str, Any] = {}
        for label, method, params in (
            ("network_enable", "Network.enable", {}),
            ("accept_language_header", "Network.setExtraHTTPHeaders",
                {"headers": {"Accept-Language": self.browser_accept_language}}),
            ("locale_override", "Emulation.setLocaleOverride", {"locale": self.browser_language}),
        ):
            if label == "accept_language_header" and not self.browser_accept_language:
                locale_setup[label] = {"status": "skipped", "reason": "empty configuration"}
                continue
            if label == "locale_override" and not self.browser_language:
                locale_setup[label] = {"status": "skipped", "reason": "empty configuration"}
                continue
            try:
                await self.call(method, params)
                locale_setup[label] = {"status": "ok", "value": next(iter(params.values()), None)}
            except Exception as error:
                locale_setup[label] = {"status": "error", "error": f"{type(error).__name__}: {error}"}
        return locale_setup

    async def __aenter__(self) -> "CDPClient":
        """Connect on context entry and clean up if connection setup fails."""
        try:
            await self.connect()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        """Release resources, closing this run's page only after an exception."""
        if exc_type is not None:
            await self.close_owned_target_on_failure()
        await self.close()

    async def close_owned_target_on_failure(self) -> None:
        """Best-effort close of the page owned by an unsuccessful run."""
        if self._failure_target_cleanup_attempted:
            return
        self._failure_target_cleanup_attempted = True
        target_id = str(self.target.get("targetId", ""))
        report: dict[str, Any] = {"target_id": target_id, "status": "skipped"}
        self.connection_report["failure_target_cleanup"] = report
        if not target_id:
            return
        try:
            if self.session_id:
                self._expected_detaches.add(self.session_id)
                await self.call(
                    "Target.detachFromTarget",
                    {"sessionId": self.session_id},
                    attached=False,
                )
                self.session_id = ""
            self._expected_target_closures.add(target_id)
            result = await self.call(
                "Target.closeTarget", {"targetId": target_id}, attached=False
            )
            if result.get("success") is False:
                raise RunnerError("Target.closeTarget returned success=false")
            for _ in range(8):
                targets = (await self.call("Target.getTargets", attached=False)).get(
                    "targetInfos", []
                )
                if not any(
                    str(item.get("targetId", "")) == target_id for item in targets
                ):
                    report["status"] = "closed"
                    return
                await asyncio.sleep(0.1)
            raise RunnerError("Target.closeTarget did not remove the owned target")
        except Exception as error:
            report.update(status="error", error=f"{type(error).__name__}: {error}")

    async def _open_browser_transport(self) -> None:
        """Open the browser-level CDP websocket used to enumerate/attach targets."""
        self._transport_error = None
        self.http = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        async with self.http.get(
            self.http_url + "/json/version", headers={"Host": "localhost"}
        ) as response:
            if response.status != 200:
                raise RunnerError(f"CDP /json/version returned HTTP {response.status}")
            version = await response.json()
        self.browser_version = str(version.get("Browser", ""))
        ws_value = version.get("webSocketDebuggerUrl")
        if not ws_value:
            raise RunnerError("CDP did not expose webSocketDebuggerUrl")
        # ChromiumRL may return complete multi-megabyte snapshots and diffs. The
        # default aiohttp receive ceiling is 4 MiB, so leave protocol payload
        # sizing to ChromiumRL and the caller rather than truncating transport.
        self.ws = await self.http.ws_connect(
            rewrite_ws_url(str(ws_value), self.http_url),
            max_msg_size=0,
        )
        self.reader = asyncio.create_task(self._read_messages())

    async def connect(self) -> None:
        """Select the task page, attach capture and establish its locale policy."""
        await self._open_browser_transport()
        await self.call("Target.setDiscoverTargets", {"discover": True}, attached=False)
        targets = (await self.call("Target.getTargets", attached=False)).get("targetInfos", [])
        pages = self._page_targets(targets)
        pages.sort(key=lambda item: 0 if str(item.get("url", "")).startswith(("http://", "https://")) else 1)
        cleanup = self._tab_cleanup_report(pages)
        if self.keep_existing_tabs:
            if not pages:
                raise RunnerError("browser exposes no page target")
            self.target = pages[0]
        else:
            await self._create_task_target(cleanup)
        cleanup["selected_target_id"] = self.target.get("targetId")
        cleanup["selected_target_url"] = str(self.target.get("url", ""))
        attached = await self.call("Target.attachToTarget",
            {"targetId": self.target["targetId"], "flatten": True}, attached=False)
        self.session_id = str(attached["sessionId"])
        locale_setup = await self._enable_attached_target()
        self.connection_report = {"browser_version": self.browser_version, "tab_cleanup": cleanup,
            "locale_setup": locale_setup, "target_switches": []}

    @staticmethod
    def _page_targets(targets: list[dict[str, Any]], except_id: str | None = None) -> list[dict[str, Any]]:
        return [item for item in targets if item.get("type") == "page"
            and (except_id is None or str(item.get("targetId", "")) != except_id)
            and not str(item.get("url", "")).startswith("devtools://")]

    def _tab_cleanup_report(self, pages: list[dict[str, Any]]) -> dict[str, Any]:
        cleanup = {"page_targets_found": len(pages),
            "page_target_urls": [str(item.get("url", "")) for item in pages],
            "keep_existing_tabs": self.keep_existing_tabs, "fresh_target_created": False,
            "closed_count": 0, "closed_targets": [], "close_errors": [], "warnings": []}
        if len(pages) > 10:
            cleanup["warnings"].append(
                f"found {len(pages)} live page targets; prior runs may have left browser state behind")
        return cleanup

    async def _create_task_target(self, cleanup: dict[str, Any]) -> None:
        created = await self.call("Target.createTarget", {"url": "about:blank"}, attached=False)
        fresh_target_id = str(created.get("targetId", ""))
        if not fresh_target_id:
            raise RunnerError("Target.createTarget returned no targetId")
        refreshed = (await self.call("Target.getTargets", attached=False)).get("targetInfos", [])
        self.target = next((item for item in refreshed if str(item.get("targetId", "")) == fresh_target_id),
            {"targetId": fresh_target_id, "type": "page", "title": "", "url": "about:blank"})
        cleanup["fresh_target_created"] = True
        cleanup["fresh_target_id"] = fresh_target_id
        await self._close_stale_targets(refreshed, fresh_target_id, cleanup)
        await self.call("Target.activateTarget", {"targetId": fresh_target_id}, attached=False)

    async def _close_stale_page(self, page: dict[str, Any], cleanup: dict[str, Any],
        closed_target_ids: set[str]) -> None:
        target_id = str(page.get("targetId", ""))
        url = str(page.get("url", ""))
        try:
            result = await self.call("Target.closeTarget", {"targetId": target_id}, attached=False)
            if result.get("success") is False:
                raise RunnerError("Target.closeTarget returned success=false")
            if target_id not in closed_target_ids:
                cleanup["closed_targets"].append({"target_id": target_id, "url": url})
                closed_target_ids.add(target_id)
        except Exception as error:
            cleanup["close_errors"].append({"target_id": target_id, "url": url,
                "error": f"{type(error).__name__}: {error}"})

    async def _close_stale_targets(self, refreshed: list[dict[str, Any]],
        fresh_target_id: str, cleanup: dict[str, Any]) -> None:
        stale_pages = self._page_targets(refreshed, fresh_target_id)
        closed_target_ids: set[str] = set()
        cleanup_passes = 0
        cleanup_timeout_seconds = 5.0
        cleanup_deadline = time.monotonic() + cleanup_timeout_seconds
        while stale_pages and time.monotonic() < cleanup_deadline:
            cleanup_passes += 1
            for page in stale_pages:
                await self._close_stale_page(page, cleanup, closed_target_ids)
            await asyncio.sleep(0.25)
            remaining = (await self.call("Target.getTargets", attached=False)).get("targetInfos", [])
            stale_pages = self._page_targets(remaining, fresh_target_id)
        cleanup["cleanup_passes"] = cleanup_passes
        cleanup["cleanup_timeout_seconds"] = cleanup_timeout_seconds
        cleanup["closed_count"] = len(cleanup["closed_targets"])
        cleanup["remaining_page_targets"] = [{"target_id": str(item.get("targetId", "")),
            "url": str(item.get("url", ""))} for item in stale_pages]
        if stale_pages:
            remaining_ids = ", ".join(str(item.get("targetId", "")) for item in stale_pages)
            raise RunnerError("could not close all previous task page targets: " + remaining_ids)

    async def reconnect_active_page(
        self, active_page: AgentBrowserPage
    ) -> dict[str, Any]:
        """Reopen only the browser transport and reattach to the active task tab."""
        previous_target_id = str(self.target.get("targetId", ""))
        previous_target_url = str(self.target.get("url", ""))
        await self.close()
        self.session_id = ""
        self.target = {}
        await self._open_browser_transport()
        report = await self.synchronize_target(active_page)
        report.update(
            transport_reconnected=True,
            disconnected_target_id=previous_target_id,
            disconnected_target_url=previous_target_url,
        )
        self.connection_report.setdefault("transport_reconnects", []).append(dict(report))
        return report

    async def synchronize_target(self, active_page: AgentBrowserPage | None = None) -> dict[str, Any]:
        """Bind the CLI's page identity to an exact browser target and record its opener."""
        targets = (await self.call("Target.getTargets", attached=False)).get("targetInfos", [])
        pages = self._page_targets(targets)
        present_ids = {str(page["targetId"]) for page in pages}
        self.target_registry = {key: value for key, value in self.target_registry.items() if key in present_ids}
        for page in pages:
            target_id = str(page["targetId"])
            self.target_registry.setdefault(target_id, {}).update(target_id=target_id,
                opener_id=page.get("openerId"), type=page.get("type"))
        if active_page is None:
            # Keep target identity outside the page's main world. Recreate the
            # isolated main-frame context after navigation without touching DOM,
            # scroll, focus, or the page's JavaScript globals.
            for page in pages:
                target_id = str(page["targetId"])
                entry = self.target_registry.setdefault(target_id, {})
                entry.update(target_id=target_id, opener_id=page.get("openerId"), type=page.get("type"),
                    identity_world=TARGET_IDENTITY_WORLD)
                marker = entry.setdefault("identity_marker", secrets.token_hex(16))
                temporary_session = target_id != str(self.target.get("targetId", ""))
                session_id = self.session_id
                deadline = time.monotonic() + LIVENESS_PROBE_SECONDS
                try:
                    if temporary_session:
                        session_id = str((await asyncio.wait_for(self.call("Target.attachToTarget", {
                            "targetId": target_id, "flatten": True}, attached=False),
                            timeout=max(0.0, deadline - time.monotonic())))["sessionId"])
                    expression = f"Object.defineProperty(globalThis,{json.dumps(TARGET_IDENTITY_PROPERTY)},{{value:{json.dumps(marker)},configurable:true}});void 0"
                    try:
                        frame = (await asyncio.wait_for(self.call("Page.getFrameTree", session_id=session_id),
                            timeout=max(0.0, deadline - time.monotonic())))["frameTree"]["frame"]["id"]
                        world = await asyncio.wait_for(self.call("Page.createIsolatedWorld", {"frameId": frame,
                            "worldName": TARGET_IDENTITY_WORLD, "grantUniveralAccess": False}, session_id=session_id),
                            timeout=max(0.0, deadline - time.monotonic()))
                        await asyncio.wait_for(self.call("Runtime.evaluate", {"expression": expression,
                            "contextId": world["executionContextId"], "returnByValue": True}, session_id=session_id),
                            timeout=max(0.0, deadline - time.monotonic()))
                        entry.pop("identity_error", None)
                    finally:
                        if temporary_session:
                            self._expected_detaches.add(session_id)
                            await asyncio.wait_for(self.call("Target.detachFromTarget", {"sessionId": session_id}, attached=False),
                                timeout=max(0.0, deadline - time.monotonic()))
                except (TimeoutError, CDPError, RunnerError) as error:
                    entry["identity_error"] = type(error).__name__
                    if self._page_failure is not None:
                        raise self._page_failure
                    if not temporary_session:
                        await self.recover_observation()
                    # An unrelated unresponsive background page cannot determine
                    # the actor's target. Missing active identity still fails closed.
            registry = list(self.target_registry.values())
            self.connection_report["target_registry"] = registry
            if self.recording_dir is not None:
                write_json(self.recording_dir / "target_registry.json", {"recorded_at": utc_now(), "targets": registry})
            return {"target_registry": registry}
        selected = self._select_active_target(active_page, pages)
        selected_id = str(selected["targetId"])
        for key, entry in self.target_registry.items():
            entry["active"] = key == selected_id
        self.target_registry[selected_id]["tab_id"] = active_page.tab_id
        self.connection_report["target_registry"] = list(self.target_registry.values())
        if self.recording_dir is not None:
            write_json(self.recording_dir / "target_registry.json", {
                "recorded_at": utc_now(), "targets": self.connection_report["target_registry"]})
        old_target_id = str(self.target.get("targetId", ""))
        new_target_id = str(selected.get("targetId", ""))
        report = self._target_switch_report(active_page, selected, old_target_id, new_target_id)
        if new_target_id == old_target_id:
            self.target = selected
            return report
        old_session_id = self.session_id
        if old_session_id:
            try:
                self._expected_detaches.add(old_session_id)
                await self.call("Target.detachFromTarget", {"sessionId": old_session_id}, attached=False)
            except Exception as error:
                report["detach_error"] = f"{type(error).__name__}: {error}"
        attached = await self.call("Target.attachToTarget",
            {"targetId": new_target_id, "flatten": True}, attached=False)
        self.session_id = str(attached["sessionId"])
        self._session_detached = False
        self.target = selected
        report["locale_setup"] = await self._enable_attached_target()
        self.connection_report.setdefault("target_switches", []).append(report)
        return report

    def _select_active_target(self, active_page: AgentBrowserPage,
        pages: list[dict[str, Any]]) -> dict[str, Any]:
        target_id = active_page.target_id or (active_page.tab_id if self.observation_mode == "screenshot" else "")
        if not target_id and active_page.identity_marker:
            matched = [key for key, value in self.target_registry.items()
                if value.get("identity_marker") == active_page.identity_marker]
            if len(matched) == 1:
                target_id = matched[0]
        candidates = [item for item in pages if str(item.get("targetId", "")) == target_id] if target_id else []
        if len(candidates) != 1:
            failure = RunnerError("active page has no unique exact CDP target ID; refusing ambiguous capture")
            failure.technical_failure_class = "recorder_harness_error"
            raise failure
        return candidates[0]

    def _target_switch_report(self, active_page: AgentBrowserPage, selected: dict[str, Any],
        old_target_id: str, new_target_id: str) -> dict[str, Any]:
        report = {"agent_browser_tab_id": active_page.tab_id, "agent_browser_url": active_page.url,
            "agent_browser_title": active_page.title, "previous_target_id": old_target_id,
            "previous_target_url": str(self.target.get("url", "")), "selected_target_id": new_target_id,
            "selected_target_url": str(selected.get("url", "")), "switched": new_target_id != old_target_id}
        if self.observation_mode == "screenshot":
            report = {"previous_target_id": old_target_id, "selected_target_id": new_target_id,
                      "switched": new_target_id != old_target_id}
        return report

    async def recover_observation(self) -> dict[str, Any]:
        """Probe the exact target on a fresh session, then recover read-only capture."""
        if self._page_failure is not None:
            raise self._page_failure
        target_id = str(self.target.get("targetId", ""))
        old_session = self.session_id
        probe_session = ""
        started = time.monotonic()
        report = {"target_id": target_id, "started_at": utc_now(), "timeout_seconds": LIVENESS_PROBE_SECONDS}
        try:
            deadline = time.monotonic() + LIVENESS_PROBE_SECONDS
            targets = (await asyncio.wait_for(self.call("Target.getTargets", attached=False),
                timeout=max(0.0, deadline - time.monotonic()))).get("targetInfos", [])
            if not target_id or not any(str(row.get("targetId", "")) == target_id for row in targets):
                raise RunnerError("exact page target no longer exists")
            probe_session = str((await asyncio.wait_for(self.call("Target.attachToTarget", {
                "targetId": target_id, "flatten": True}, attached=False),
                timeout=max(0.0, deadline - time.monotonic())))["sessionId"])
            # Pure evaluation checks renderer responsiveness without reading DOM,
            # replaying input, or changing the page. Each wait shares one deadline.
            self.session_id = probe_session
            self._session_detached = False
            result = await asyncio.wait_for(self.call("Runtime.evaluate", {"expression": "1", "returnByValue": True,
                "timeout": int(LIVENESS_PROBE_SECONDS * 1000)}), timeout=max(0.0, deadline - time.monotonic()))
            if result.get("result", {}).get("value") != 1:
                raise RunnerError("renderer did not answer the liveness probe")
            report["alive"] = True
            await asyncio.wait_for(self._enable_attached_target(), timeout=max(0.0, deadline - time.monotonic()))
            if old_session:
                self._expected_detaches.add(old_session)
                await asyncio.wait_for(self.call("Target.detachFromTarget", {"sessionId": old_session}, attached=False),
                    timeout=max(0.0, deadline - time.monotonic()))
            report.update(alive=True, reattached=True, session_id=probe_session)
            return report
        except BaseException as error:
            self.session_id = old_session
            if isinstance(error, asyncio.CancelledError):
                raise
            failure = self._page_failure or RunnerError("read-only session reattachment failed" if report.get("alive") else "target liveness probe failed within 3 seconds")
            failure.technical_failure_class = getattr(failure, "technical_failure_class", "cdp_stall")
            self._page_failure = failure
            self.page_failure_event.set()
            report.update(alive=report.get("alive", False), error_type=type(error).__name__)
            raise failure from error
        finally:
            report.update(ended_at=utc_now(), duration_seconds=time.monotonic() - started)
            self.connection_report.setdefault("observation_recovery", []).append(report)
            if self.recording_dir is not None:
                append_json_line(self.recording_dir / "observation_recovery.jsonl", report)

    async def close(self) -> None:
        """Cancel the reader and close both CDP transport resources idempotently."""
        if self.reader is not None:
            reader, self.reader = self.reader, None
            reader.cancel()
            try:
                await reader
            except (asyncio.CancelledError, Exception):
                pass
        socket, self.ws = self.ws, None
        http, self.http = self.http, None
        try:
            if socket is not None:
                await socket.close()
        finally:
            if http is not None:
                await http.close()

    async def _read_messages(self) -> None:
        """Route CDP responses to pending calls and fail them if transport closes."""
        assert self.ws is not None
        error = RunnerError("CDP websocket closed")
        try:
            async for message in self.ws:
                if message.type != aiohttp.WSMsgType.TEXT:
                    if message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                        break
                    continue
                payload = json.loads(message.data)
                if not isinstance(payload, dict):
                    raise ValueError("CDP message must be a JSON object")
                method = payload.get("method", "")
                params = payload.get("params", {})
                event_session = payload.get("sessionId") or params.get("sessionId")
                if method == "Debugger.scriptParsed" and params.get("url") in self.identity_reads:
                    target_id = self.session_targets.get(str(event_session), "")
                    if target_id:
                        self.identity_reads[params["url"]].add(target_id)
                if method in {"Target.targetCreated", "Target.targetInfoChanged", "Target.targetDestroyed", "Target.targetCrashed",
                    "Target.attachedToTarget", "Target.detachedFromTarget", "Inspector.targetCrashed", "Inspector.detached",
                    "Page.frameDetached", "Page.javascriptDialogOpening", "Page.javascriptDialogClosed"}:
                    info = params.get("targetInfo", {})
                    target_id = str(params.get("targetId") or info.get("targetId") or self.session_targets.get(str(event_session)) or self.target.get("targetId", ""))
                    if method == "Target.attachedToTarget" and event_session:
                        self.session_targets[str(event_session)] = target_id
                    event = {"method": method, "recorded_at": utc_now(), "target_id": target_id,
                        "session_id": event_session, "type": params.get("type"), "reason": params.get("reason"),
                        "status": params.get("status"), "error_code": params.get("errorCode")}
                    if info:
                        self.target_registry.setdefault(target_id, {}).update(target_id=target_id,
                            type=info.get("type"), opener_id=info.get("openerId"), browser_context_id=info.get("browserContextId"))
                    if method == "Target.targetDestroyed":
                        self.target_registry.pop(target_id, None)
                    if self.recording_dir is not None:
                        append_json_line(self.recording_dir / "browser_events.jsonl", event)
                    relevant = target_id == str(self.target.get("targetId", "")) and (not event_session or event_session == self.session_id)
                    detached = method in {"Target.detachedFromTarget", "Inspector.detached"}
                    event_failure = None
                    crash_event = "Crashed" in method or (method == "Inspector.detached" and any(
                        word in str(params.get("reason", "")).lower() for word in ("crash", "render process gone", "renderer process gone")))
                    if relevant and (crash_event or method == "Target.targetDestroyed") and target_id not in self._expected_target_closures:
                        self._page_failure = RunnerError("page target crashed" if crash_event else "page target destroyed")
                        self._page_failure.technical_failure_class = "browser_crash" if crash_event else "cdp_stall"
                        self.page_failure_event.set()
                        event_failure = self._page_failure
                    elif relevant and detached and event_session not in self._expected_detaches:
                        self._session_detached = True
                        event_failure = CDPError(method, {"code": -32603, "message": "capture session detached"})
                    if event_failure is not None:
                        for future in self.pending.values():
                            if not future.done():
                                future.set_exception(event_failure)
                    self._expected_detaches.discard(str(event_session))
                    if method == "Target.targetDestroyed":
                        self._expected_target_closures.discard(target_id)
                if payload.get("method") in {"Page.frameNavigated", "Page.navigatedWithinDocument"}:
                    self.navigation_events.append({"method": payload["method"],
                        "params": payload.get("params", {}), "session_id": payload.get("sessionId"),
                        "recorded_at": utc_now()})
                message_id = payload.get("id")
                if isinstance(message_id, int) and message_id in self.pending:
                    future = self.pending.pop(message_id)
                    if not future.done():
                        future.set_result(payload)
        except Exception as cause:
            error = RunnerError(f"CDP websocket closed: reader failed ({type(cause).__name__}: {cause})")
        finally:
            self._transport_error = self._page_failure or error
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(self._page_failure or error)
            self.pending.clear()

    async def call(
        self, method: str, params: dict[str, Any] | None = None, *, attached: bool = True,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Send one protocol command and record its timing without request values."""
        started = time.monotonic()
        receipt = {"method": method, "started_at": utc_now(), "target_id": self.target.get("targetId"),
            "session_id": (session_id or self.session_id) if attached else None, "status": "started"}
        if session_id is not None:
            receipt["target_id"] = self.session_targets.get(session_id, receipt["target_id"])
        message_id = None
        try:
            if attached and self._page_failure is not None:
                raise self._page_failure
            if attached and self._session_detached and session_id is None:
                raise CDPError(method, {"code": -32603, "message": "capture session detached"})
            if self._transport_error is not None:
                raise self._transport_error
            if self.ws is None:
                raise RunnerError("CDP websocket is not connected")
            self.next_id += 1
            message_id = self.next_id
            request = {"id": message_id, "method": method, "params": params or {}}
            if attached and (session_id or self.session_id):
                request["sessionId"] = session_id or self.session_id
            future = asyncio.get_running_loop().create_future()
            self.pending[message_id] = future
            try:
                await self.ws.send_json(request)
            except (aiohttp.ClientError, ConnectionError, RuntimeError) as error:
                if is_cdp_transport_error(error):
                    raise RunnerError(f"CDP websocket closed while sending {method}: {error}") from error
                raise
            response = await asyncio.wait_for(future, timeout=self.timeout)
            if "error" in response:
                raise CDPError(method, response["error"])
            receipt["status"] = "completed"
            result = response.get("result", {})
            if method == "Target.attachToTarget" and isinstance(result, dict) and result.get("sessionId"):
                self.session_targets[str(result["sessionId"])] = str((params or {}).get("targetId", ""))
            return result if isinstance(result, dict) else {}
        except BaseException as error:
            receipt.update(status="cancelled" if isinstance(error, asyncio.CancelledError) else "error",
                error_type=type(error).__name__, technical_failure_class=getattr(error, "technical_failure_class", None))
            if isinstance(error, CDPError) and isinstance(error.error, dict):
                receipt["error_code"] = error.error.get("code")
            raise
        finally:
            if message_id is not None:
                self.pending.pop(message_id, None)
            receipt.update(ended_at=utc_now(), duration_seconds=time.monotonic() - started)
            if self.recording_dir is not None:
                append_json_line(self.recording_dir / "cdp_calls.jsonl", receipt)


def rewrite_ws_url(value: str, http_url: str) -> str:
    """Keep CDP's websocket path while replacing its externally unusable host."""
    source = urlsplit(value)
    target = urlsplit(http_url)
    scheme = "wss" if target.scheme == "https" else "ws"
    return urlunsplit((scheme, target.netloc, source.path, source.query, ""))
