"""Paired recorder capture with isolated actor observations and target synchronization."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
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
    """Retry a read-only capture command only when its response times out."""
    for attempt in range(1, 3):
        try:
            return await cdp.call(method, params)
        except (asyncio.TimeoutError, TimeoutError) as error:
            if attempt == 2:
                raise RunnerError(f"{method} timed out after 2 attempts") from error
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
        response = await cdp.call("Page.getFrameTree")
        return response.get("frameTree", {}).get("frame", {})
    except Exception as error:
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
        if (phase == "screenshot") == (observation_mode == "screenshot"):
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


async def _snapshot_action_refs(agent_browser: AgentBrowserClient, attempts: int) -> Any:
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return await agent_browser.snapshot()
        except Exception:
            if attempt >= max(1, attempts):
                raise
            await agent_browser.reconnect()
            await asyncio.sleep(0.75 * attempt)
    raise AssertionError("unreachable")


async def _finish_reference_capture(bundle: CaptureBundle, cdp: CDPClient,
    refs_started: float) -> None:
    try:
        frame = (await cdp.call("Page.getFrameTree")).get("frameTree", {}).get("frame", {})
    except Exception as error:
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
    action_observation = await _snapshot_action_refs(agent_browser, attempts)
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
    for attempt in range(1, max(1, attempts) + 1):
        try:
            active_page = await agent_browser.active_page()
            return await cdp.synchronize_target(active_page)
        except AgentBrowserBaseError as error:
            last_error = error
            if attempt < attempts:
                await agent_browser.reconnect()
                await asyncio.sleep(0.5 * attempt)
        except RunnerError as error:
            last_error = error
            transport_lost = is_cdp_transport_error(error)
            if transport_lost:
                try:
                    active_page = await agent_browser.active_page()
                    report = await cdp.reconnect_active_page(active_page)
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
        self.next_id = 0
        self.pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.session_id = ""
        self.navigation_events: list[dict[str, Any]] = []
        self.capture_setup_errors: list[dict[str, Any]] = []
        self.target: dict[str, Any] = {}
        self.connection_report: dict[str, Any] = {}
        self._failure_target_cleanup_attempted = False

    async def _enable_attached_target(self) -> dict[str, Any]:
        """Enable capture domains, the coordinate viewport and configured locales."""
        await self.call("Page.enable")
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
                await self.call(
                    "Target.detachFromTarget",
                    {"sessionId": self.session_id},
                    attached=False,
                )
                self.session_id = ""
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

    async def synchronize_target(self, active_page: AgentBrowserPage) -> dict[str, Any]:
        """Match the active task page and attach capture to its unique CDP target."""
        targets = (await self.call("Target.getTargets", attached=False)).get("targetInfos", [])
        selected = self._select_active_target(active_page, self._page_targets(targets))
        old_target_id = str(self.target.get("targetId", ""))
        new_target_id = str(selected.get("targetId", ""))
        report = self._target_switch_report(active_page, selected, old_target_id, new_target_id)
        if new_target_id == old_target_id:
            self.target = selected
            return report
        old_session_id = self.session_id
        if old_session_id:
            try:
                await self.call("Target.detachFromTarget", {"sessionId": old_session_id}, attached=False)
            except Exception as error:
                report["detach_error"] = f"{type(error).__name__}: {error}"
        attached = await self.call("Target.attachToTarget",
            {"targetId": new_target_id, "flatten": True}, attached=False)
        self.session_id = str(attached["sessionId"])
        self.target = selected
        report["locale_setup"] = await self._enable_attached_target()
        self.connection_report.setdefault("target_switches", []).append(report)
        return report

    def _select_active_target(self, active_page: AgentBrowserPage,
        pages: list[dict[str, Any]]) -> dict[str, Any]:
        active_key = comparable_page_url(active_page.url)
        candidates = [item for item in pages
            if comparable_page_url(str(item.get("url", ""))) == active_key]
        if self.observation_mode == "screenshot":
            candidates = [item for item in pages if item.get("targetId") == active_page.tab_id]
        if len(candidates) > 1 and active_page.title:
            title_matches = [item for item in candidates
                if str(item.get("title", "")).strip() == active_page.title.strip()]
            if title_matches:
                candidates = title_matches
        if not candidates and active_page.title:
            title_matches = [item for item in pages
                if str(item.get("title", "")).strip() == active_page.title.strip()]
            if len(title_matches) == 1:
                candidates = title_matches
        if not candidates:
            raise RunnerError("agent-browser active tab has no matching CDP page target: "
                f"tab={active_page.tab_id!r} url={active_page.url!r} title={active_page.title!r}")
        if len(candidates) != 1:
            raise RunnerError("agent-browser active tab matches multiple CDP page targets; "
                "refusing to capture an ambiguous page: "
                f"tab={active_page.tab_id!r} url={active_page.url!r} "
                f"title={active_page.title!r} matches={len(candidates)}")
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

    async def close(self) -> None:
        """Cancel the reader and close both CDP transport resources idempotently."""
        if self.reader is not None:
            self.reader.cancel()
            try:
                await self.reader
            except asyncio.CancelledError:
                pass
            self.reader = None
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
        if self.http is not None:
            await self.http.close()
            self.http = None

    async def _read_messages(self) -> None:
        """Route CDP responses to pending calls and fail them if transport closes."""
        assert self.ws is not None
        async for message in self.ws:
            if message.type != aiohttp.WSMsgType.TEXT:
                if message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                    break
                continue
            payload = json.loads(message.data)
            if payload.get("method") in {"Page.frameNavigated", "Page.navigatedWithinDocument"}:
                self.navigation_events.append({"method": payload["method"],
                    "params": payload.get("params", {}), "session_id": payload.get("sessionId"),
                    "recorded_at": utc_now()})
            message_id = payload.get("id")
            if isinstance(message_id, int) and message_id in self.pending:
                future = self.pending.pop(message_id)
                if not future.done():
                    future.set_result(payload)
                continue
        error = RunnerError("CDP websocket closed")
        for future in self.pending.values():
            if not future.done():
                future.set_exception(error)
        self.pending.clear()

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        attached: bool = True,
    ) -> dict[str, Any]:
        """Send one CDP command to the page session or browser connection."""
        if self.ws is None:
            raise RunnerError("CDP websocket is not connected")
        self.next_id += 1
        message_id = self.next_id
        request: dict[str, Any] = {"id": message_id, "method": method, "params": params or {}}
        if attached and self.session_id:
            request["sessionId"] = self.session_id
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pending[message_id] = future
        try:
            await self.ws.send_json(request)
        except (aiohttp.ClientError, ConnectionError, RuntimeError) as error:
            self.pending.pop(message_id, None)
            if is_cdp_transport_error(error):
                raise RunnerError(
                    f"CDP websocket closed while sending {method}: {error}"
                ) from error
            raise
        try:
            response = await asyncio.wait_for(future, timeout=self.timeout)
        except BaseException:
            self.pending.pop(message_id, None)
            raise
        if "error" in response:
            raise CDPError(method, response["error"])
        result = response.get("result", {})
        return result if isinstance(result, dict) else {}


def rewrite_ws_url(value: str, http_url: str) -> str:
    """Keep CDP's websocket path while replacing its externally unusable host."""
    source = urlsplit(value)
    target = urlsplit(http_url)
    scheme = "wss" if target.scheme == "https" else "ws"
    return urlunsplit((scheme, target.netloc, source.path, source.query, ""))


def comparable_page_url(value: str) -> str:
    """Normalize only URL spelling differences that cannot identify a tab."""
    text = value.strip()
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"}:
        return text
    path = parsed.path or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.query,
            parsed.fragment,
        )
    )
