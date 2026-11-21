"""Paired recorder capture with isolated actor observations and target synchronization."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import secrets
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
CAPTURE_POLICY_VERSION = "paired-capture/v2"
EMPTY_DOM_MARKER = "[No exportable DOM content]"

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


def action_progress(before: CaptureBundle, after: CaptureBundle) -> dict[str, Any]:
    """Report observation changes without inferring task completion or progress."""
    if before.observation_mode != after.observation_mode:
        raise RunnerError("cannot compare progress across observation modes")
    result = {"url_changed": before.document_url != after.document_url}
    if before.observation_mode == "screenshot":
        from PIL import Image
        with Image.open(before.screenshot_path) as left, Image.open(after.screenshot_path) as right:
            result["screenshot_changed"] = (left.size != right.size
                or left.convert("RGBA").tobytes() != right.convert("RGBA").tobytes())
    else:
        from .runner import chromiumrl_evidence_for_model
        result.update(dom_changed=chromiumrl_evidence_for_model(before.model_text) != chromiumrl_evidence_for_model(after.model_text),
            agent_browser_observation_changed=(
                re.sub(r"\bref=@?e\d+(?=[,\]\s]|$)", "ref=<element>", before.agent_browser_action_text)
                != re.sub(r"\bref=@?e\d+(?=[,\]\s]|$)", "ref=<element>", after.agent_browser_action_text)))
    return {**result, "observation_changed": any(result.values()), "task_progress": None}


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
    """Capture viewport DOM, including valid exports with no selected nodes."""
    params: dict[str, Any] = {
        "inViewportOnly": True,
        "maxNodes": max_nodes,
        "maxTextChars": max_text_chars,
        "includeOffscreen": False,
    }
    result = await capture_call(cdp, "ChromiumRL.captureStructuredSnapshot", params)
    snapshot = result.get("snapshot")
    if not isinstance(snapshot, dict):
        raise RunnerError(f"unexpected ChromiumRL snapshot response: {result}")
    return snapshot


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
    if snapshot.get("nodes") == []:
        content = next((section for section in sections if section.get("name") == "content"), None)
        if content is not None:
            content["lines"].append(EMPTY_DOM_MARKER)
        else:
            index = next((index for index, section in enumerate(sections)
                if section.get("name") in {"media", "actions", "scroll_regions"}), len(sections))
            sections.insert(index, {"name": "content", "lines": [EMPTY_DOM_MARKER]})
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
                max_text_chars=max_text_chars, observation_mode=observation_mode,
                agent_browser=agent_browser)
            return bundle, reconnects
        except RunnerError as error:
            if not is_cdp_transport_error(error) or attempt >= attempts:
                raise
            failed_metadata = directory / "capture.json"
            failed_capture = json.loads(failed_metadata.read_text()) if failed_metadata.is_file() else None
            number = 1
            preserved = directory.with_name(f"{directory.name}_capture_attempt_{number:02d}")
            while preserved.exists() or preserved.is_symlink():
                number += 1
                preserved = directory.with_name(f"{directory.name}_capture_attempt_{number:02d}")
            if directory.exists():
                directory.rename(preserved)
            append_json_line(directory.parent.parent / "capture_failures.jsonl", {
                "directory": str(directory.relative_to(directory.parent.parent)), "attempt": attempt,
                "preserved_capture": str(preserved.relative_to(directory.parent.parent)),
                "recorded_at": utc_now(), "error": f"{type(error).__name__}: {error}",
                "capture": failed_capture})
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
    screenshot_bytes: bytes | None = None
    action_observation: Any = None


async def _capture_frame(cdp: CDPClient, metadata: dict[str, Any], kind: str) -> dict[str, Any]:
    try:
        response = await capture_call(cdp, "Page.getFrameTree", {})
        frame = response.get("frameTree", {}).get("frame", {})
    except Exception as error:
        if getattr(error, "technical_failure_class", None):
            raise
        metadata["metadata_errors"].append({"kind": kind, "error": f"{type(error).__name__}: {error}"})
        return {}
    if kind == "url_before":
        started = time.monotonic()
        deadline = started + cdp.timeout
        readiness = {"policy_version": "document-readiness/v1", "timeout_seconds": cdp.timeout,
            "status": "unavailable", "navigation_changes": [], "animation_frames": None}
        metadata["readiness"] = readiness
        try:
            while frame.get("id"):
                key = (str(cdp.target.get("targetId", "")), frame["id"], frame.get("loaderId"))
                readiness.update(target_id=key[0], frame_id=key[1], loader_id=key[2])
                same_document = key == getattr(cdp, "_last_capture_document", None)
                world = await capture_call(cdp, "Page.createIsolatedWorld", {"frameId": frame["id"],
                    "worldName": TARGET_IDENTITY_WORLD, "grantUniveralAccess": False})
                context = world["executionContextId"]
                read_state = "({ready_state:document.readyState,mime_type:document.contentType})"
                expression = ("(async()=>{if(document.readyState==='loading')await new Promise(resolve=>"
                    "document.addEventListener('DOMContentLoaded',resolve,{once:true}));"
                    "await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));"
                    "return " + read_state + ";})()")
                try:
                    if same_document or time.monotonic() >= deadline:
                        state = await capture_call(cdp, "Runtime.evaluate", {"contextId": context,
                            "expression": read_state, "returnByValue": True})
                        status = "same_document" if same_document else "timeout"
                    else:
                        try:
                            state = await asyncio.wait_for(cdp.call("Runtime.evaluate", {
                                "contextId": context, "expression": expression,
                                "awaitPromise": True, "returnByValue": True}),
                                timeout=max(0.0, deadline-time.monotonic()))
                            status = "ready"
                        except asyncio.TimeoutError:
                            # Expiry of the readiness promise is not a failed CDP
                            # observation. A fresh synchronous read still follows
                            # the ordinary recovery/error policy.
                            state = await capture_call(cdp, "Runtime.evaluate", {"contextId": context,
                                "expression": read_state, "returnByValue": True})
                            status = "timeout"
                except CDPError as error:
                    if not any(text in str(error) for text in (
                            "Execution context was destroyed", "Cannot find context with specified id")):
                        raise
                    refreshed = await capture_call(cdp, "Page.getFrameTree", {})
                    changed = refreshed.get("frameTree", {}).get("frame", {})
                    if (key[0], changed.get("id"), changed.get("loaderId")) == key:
                        raise
                    readiness["navigation_changes"].append(list(key))
                    response, frame = refreshed, changed
                    if time.monotonic() >= deadline:
                        readiness.update(status="timeout", frame_id=frame.get("id"),
                            loader_id=frame.get("loaderId"), mime_type=frame.get("mimeType"), ready_state=None)
                        metadata.update(document_mime_type=frame.get("mimeType"), document_ready_state=None)
                        cdp._last_capture_document = (key[0], frame.get("id"), frame.get("loaderId"))
                        break
                    continue
                value = state.get("result", {}).get("value")
                if state.get("exceptionDetails") or not isinstance(value, dict):
                    raise RunnerError("document readiness metadata unavailable")
                refreshed = await capture_call(cdp, "Page.getFrameTree", {})
                changed = refreshed.get("frameTree", {}).get("frame", {})
                if (key[0], changed.get("id"), changed.get("loaderId")) != key:
                    readiness["navigation_changes"].append(list(key))
                    response, frame = refreshed, changed
                    if time.monotonic() >= deadline:
                        readiness.update(status="timeout", frame_id=frame.get("id"),
                            loader_id=frame.get("loaderId"), mime_type=frame.get("mimeType"), ready_state=None)
                        metadata.update(document_mime_type=frame.get("mimeType"), document_ready_state=None)
                        cdp._last_capture_document = (key[0], frame.get("id"), frame.get("loaderId"))
                        break
                    continue
                response, frame = refreshed, changed
                readiness.update(status=status, ready_state=value.get("ready_state"),
                    mime_type=value.get("mime_type"), animation_frames=2 if status == "ready" else None)
                metadata.update(document_mime_type=value.get("mime_type"),
                    document_ready_state=value.get("ready_state"))
                cdp._last_capture_document = key
                break
        finally:
            readiness["wait_seconds"] = time.monotonic()-started
    frames = []
    pending = [response.get("frameTree", {})]
    while pending:
        tree = pending.pop()
        if tree.get("frame", {}).get("id"):
            frames.append(tree["frame"])
        pending.extend(tree.get("childFrames", []))
    # Only counters leave the isolated world. Open shadow roots receive their
    # own observers; closed roots and unreported remote frames remain unknown.
    expression = ("(()=>{const key='__w8CaptureChanges';let state=globalThis[key];const initial=!state;"
        "if(initial){state={count:0,roots:new WeakSet(),observers:[],openShadowRoots:0};"
        "Object.defineProperty(globalThis,key,{value:state});}"
        "const pending=[document];while(pending.length){const root=pending.pop();"
        "if(!state.roots.has(root)){state.roots.add(root);"
        "if(root!==document){state.openShadowRoots++;if(!initial)state.count++;}"
        "const observer=new MutationObserver(records=>{state.count+=records.length});"
        "observer.observe(root,{subtree:true,childList:true,characterData:true,attributes:true});"
        "state.observers.push(observer);}"
        "for(const element of root.querySelectorAll('*')){if(element.shadowRoot)pending.push(element.shadowRoot);}}"
        "for(const observer of state.observers)state.count+=observer.takeRecords().length;"
        "return{count:state.count,openShadowRoots:state.openShadowRoots};})()")
    if kind == "url_before":
        metadata["paint_event_start"] = len(getattr(cdp, "paint_events", []))
        monitor = {"scope": "known_frames_and_open_shadow_roots", "frames": [],
            "subframes_observed": False, "closed_shadow_roots_observed": False,
            "coverage_complete": False, "status": "unavailable",
            "unobserved_reasons": ["closed_shadow_roots_not_observed", "unreported_remote_frames_not_observed"]}
        metadata["content_change_monitor"] = monitor
        try:
            await capture_call(cdp, "LayerTree.enable", {})
            metadata["paint_monitor_available"] = True
            metadata["paint_change_monitor"] = {"source": "LayerTree.layerPainted",
                "coverage": "reported_events_only", "coverage_complete": False, "status": "observing"}
        except Exception as error:
            if getattr(error, "technical_failure_class", None):
                raise
            metadata["paint_monitor_available"] = False
            metadata["paint_change_monitor"] = {"source": "LayerTree.layerPainted",
                "coverage": "reported_events_only", "coverage_complete": False, "status": "unavailable"}
            metadata.setdefault("monitor_errors", []).append({"kind": "paint", "error_type": type(error).__name__})
        for entry in frames:
            receipt = {"frame_id": entry["id"], "status": "unavailable", "loader_id_before": entry.get("loaderId")}
            monitor["frames"].append(receipt)
            try:
                world = await capture_call(cdp, "Page.createIsolatedWorld", {"frameId": entry["id"],
                    "worldName": TARGET_IDENTITY_WORLD, "grantUniveralAccess": False})
                context_id = world["executionContextId"]
                counter = await capture_call(cdp, "Runtime.evaluate", {"contextId": context_id,
                    "returnByValue": True, "expression": expression})
                value = counter.get("result", {}).get("value")
                if not isinstance(value, dict) or type(value.get("count")) is not int or type(value.get("openShadowRoots")) is not int:
                    raise RunnerError("capture mutation counter unavailable")
                receipt.update(status="observing", execution_context_id=context_id,
                    mutations_before=value["count"], open_shadow_roots_before=value["openShadowRoots"])
            except Exception as error:
                if getattr(error, "technical_failure_class", None):
                    raise
                receipt["error_type"] = type(error).__name__
        if any(receipt["status"] == "observing" for receipt in monitor["frames"]):
            monitor["status"] = "observing"
    elif kind == "url_after":
        monitor = metadata.get("content_change_monitor", {})
        for receipt in monitor.get("frames", []):
            if receipt.get("status") != "observing":
                continue
            try:
                counter = await capture_call(cdp, "Runtime.evaluate", {"contextId": receipt["execution_context_id"],
                    "returnByValue": True, "expression": expression})
                value = counter.get("result", {}).get("value")
                if (not isinstance(value, dict) or type(value.get("count")) is not int
                        or type(value.get("openShadowRoots")) is not int or value["count"] < receipt["mutations_before"]):
                    raise RunnerError("capture mutation counter unavailable or reset")
                receipt.update(status="observed", mutations_after=value["count"],
                    mutations_during_capture=value["count"]-receipt["mutations_before"],
                    open_shadow_roots_after=value["openShadowRoots"])
            except Exception as error:
                if getattr(error, "technical_failure_class", None):
                    raise
                receipt.update(status="unavailable", error_type=type(error).__name__)
        before_ids = {receipt["frame_id"] for receipt in monitor.get("frames", [])}
        after_by_id = {entry["id"]: entry for entry in frames}
        monitor["frames_added_during_capture"] = sorted(set(after_by_id)-before_ids)
        monitor["frames_removed_during_capture"] = sorted(before_ids-set(after_by_id))
        monitor["frame_navigations_during_capture"] = [receipt["frame_id"] for receipt in monitor.get("frames", [])
            if receipt["frame_id"] in after_by_id and receipt.get("loader_id_before") != after_by_id[receipt["frame_id"]].get("loaderId")]
        observed = [receipt for receipt in monitor.get("frames", []) if receipt.get("status") == "observed"]
        monitor["status"] = "observed" if len(observed) == len(before_ids) and before_ids else "partial" if observed else "unavailable"
        monitor["observed_frame_count"] = len(observed)
        monitor["mutations_during_capture"] = sum(receipt["mutations_during_capture"] for receipt in observed)
        monitor["subframes_observed"] = bool(observed) and all(receipt.get("status") == "observed"
            for receipt in monitor.get("frames", []) if receipt["frame_id"] != frame.get("id")) and len(before_ids)>1
        observed_change = bool(monitor["mutations_during_capture"] or monitor["frames_added_during_capture"]
            or monitor["frames_removed_during_capture"] or monitor["frame_navigations_during_capture"]
            or any(receipt["open_shadow_roots_after"] != receipt["open_shadow_roots_before"] for receipt in observed))
        monitor["observed_content_changed"] = observed_change if observed or before_ids else None
        # A quiet observed subset does not establish that unobserved content
        # stayed unchanged. Keep overall absence of change unknown.
        metadata["content_changed_during_capture"] = True if observed_change else None
        events = [event for event in getattr(cdp, "paint_events", [])[metadata.get("paint_event_start", 0):]
            if event.get("target_id") == metadata["target_id"]]
        metadata["paint_events_during_capture"] = events
        metadata["paint_changed_during_capture"] = True if events else None
        metadata.setdefault("paint_change_monitor", {"source": "LayerTree.layerPainted",
            "coverage": "reported_events_only", "coverage_complete": False, "status": "unavailable"})["reported_paint_changed"] = (bool(events)
            if metadata.get("paint_monitor_available") else None)
    return frame


async def _capture_screenshot(cdp: CDPClient) -> bytes:
    result = await capture_call(cdp, "Page.captureScreenshot", {
        "format": "png", "fromSurface": True, "captureBeyondViewport": False})
    data = base64.b64decode(result["data"], validate=True)
    import io
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        if cdp.viewport is not None and image.size != cdp.viewport:
            raise RunnerError("screenshot dimensions differ from the coordinate viewport")
        image.verify()
    return data


async def _capture_phase(cdp: CDPClient, directory: Path, phase: str, state: _CaptureState,
    max_nodes: int, max_text_chars: int, agent_browser: AgentBrowserClient | None = None) -> None:
    if phase == "structured_dom":
        state.snapshot = await capture_structured_snapshot(cdp, max_nodes=max_nodes,
            max_text_chars=max_text_chars)
    elif phase == "screenshot":
        state.screenshot_bytes = await _capture_screenshot(cdp)
    elif phase == "executable_refs":
        state.action_observation = await _snapshot_action_refs(agent_browser, 3, cdp)
    elif phase == "dom_model_artifacts":
        if state.dom_error is not None:
            raise RunnerError("structured DOM capture unavailable")
        state.snapshot_path = directory / "dom.json"
        write_json(state.snapshot_path, {"result": {"snapshot": state.snapshot}})
        render_full_stored_snapshot(state.snapshot_path)
        model_dom = await model_dom_from_snapshot(cdp, state.snapshot)
        model_path = directory / "dom_model.json"
        write_json(model_path, {"result": {"modelDOM": model_dom}})
        render_model_dom_stored_projection(model_path)
        state.model_text = model_path.with_suffix(".txt").read_text(encoding="utf-8")


def _invalidate_capture(directory: Path, phase: str, state: _CaptureState,
    record: dict[str, Any], error: Exception) -> None:
    names = {"structured_dom": ("dom.json", "dom_full.txt"),
        "dom_model_artifacts": ("dom_model.json", "dom_model.txt"),
        "screenshot": ("screenshot.png",), "executable_refs": ("agent_browser_actions.txt",)}[phase]
    for name in names:
        for path in (directory / name, directory / f".{name}.tmp"):
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                record.setdefault("cleanup_errors", []).append(str(cleanup_error))
    if phase in {"structured_dom", "dom_model_artifacts"}:
        state.snapshot_path = None
        state.model_text = ""
        for name in ("dom.json", "dom_full.txt", "dom_model.json", "dom_model.txt"):
            (directory / name).unlink(missing_ok=True)
            (directory / ("."+name+".tmp")).unlink(missing_ok=True)
    elif phase == "screenshot":
        state.screenshot_path = None
        state.screenshot_bytes = None
    else:
        state.action_observation = None
    if phase in {"structured_dom", "dom_model_artifacts"}:
        state.dom_error = error


async def _record_capture_phase(cdp: CDPClient, directory: Path, phase: str,
    state: _CaptureState, metadata: dict[str, Any], interval_started: float,
    observation_mode: str, max_nodes: int, max_text_chars: int,
    agent_browser: AgentBrowserClient | None = None) -> None:
    record = {"kind": phase, "started_at": utc_now()}
    started = time.monotonic()
    try:
        await _capture_phase(cdp, directory, phase, state, max_nodes, max_text_chars, agent_browser)
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


async def _finish_capture(cdp: CDPClient, directory: Path, state: _CaptureState,
    metadata: dict[str, Any], interval_started: float, navigation_start: int,
    observation_mode: str, max_nodes: int, max_text_chars: int) -> CaptureBundle:
    frame = await _capture_frame(cdp, metadata, "url_after")
    metadata["url_after"] = str(frame.get("url", metadata["url_before"]))
    metadata["loader_id_after"] = frame.get("loaderId", "")
    metadata["navigation_during_capture"] = (metadata["url_before"] != metadata["url_after"]
        or metadata["loader_id_before"] != metadata["loader_id_after"]
        or len(cdp.navigation_events) != navigation_start)
    metadata["navigation_events"] = cdp.navigation_events[navigation_start:]
    metadata.update(raw_capture_ended_at=utc_now(), raw_capture_duration_seconds=time.monotonic()-interval_started)
    if state.dom_error is None:
        empty = state.snapshot.get("nodes") == []
        metadata["dom_export"] = {"status": "empty" if empty else "content",
            "marker": EMPTY_DOM_MARKER if empty else None, "stats": state.snapshot.get("stats")}
    if state.screenshot_bytes is not None:
        state.screenshot_path = directory / "screenshot.png"
    action_path = None
    if state.action_observation is not None:
        action_path = directory / "agent_browser_actions.txt"
    metadata["capture_order"].append("dom_model_artifacts")
    await _record_capture_phase(cdp, directory, "dom_model_artifacts", state, metadata,
        interval_started, observation_mode, max_nodes, max_text_chars)
    metadata.update(ended_at=utc_now(), duration_seconds=time.monotonic() - interval_started,
        url_metadata_complete=not metadata["metadata_errors"],
        document_language=str(state.snapshot.get("documentLanguage") or state.snapshot.get("language") or "")
            if observation_mode == "dom" else None)
    observation = state.action_observation
    return CaptureBundle(snapshot=state.snapshot, snapshot_path=state.snapshot_path, model_text=state.model_text,
        screenshot_path=state.screenshot_path, observation_mode=observation_mode,
        document_url=metadata["url_after"], capture_metadata=metadata,
        document_language=str(state.snapshot.get("documentLanguage") or state.snapshot.get("language") or ""),
        agent_browser_action_text=observation.text if observation is not None else "",
        agent_browser_refs=observation.refs if observation is not None else frozenset(),
        agent_browser_targets=observation.targets if observation is not None else {},
        agent_browser_action_path=action_path)


async def capture_bundle(cdp: CDPClient, directory: Path, *, max_nodes: int,
    max_text_chars: int, observation_mode: str = "dom",
    agent_browser: AgentBrowserClient | None = None) -> CaptureBundle:
    """Acquire paired raw observations before projecting or writing artifacts."""
    if observation_mode not in {"dom", "screenshot"}:
        raise RunnerError("unknown observation mode")
    if observation_mode == "screenshot" and agent_browser is not None:
        raise RunnerError("accessibility observations are forbidden in screenshot mode")
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {"policy_version": CAPTURE_POLICY_VERSION,
        "started_at": utc_now(), "target_id": str(cdp.target.get("targetId", "")),
        "session_id": getattr(cdp, "session_id", ""), "captures": [],
        "capture_order": ["structured_dom", "screenshot"] + (["executable_refs"] if agent_browser is not None else []),
        "paired_complete": True, "navigation_during_capture": False,
        "content_changed_during_capture": None, "paint_changed_during_capture": None,
        "setup_errors": list(getattr(cdp, "capture_setup_errors", [])), "metadata_errors": []}
    interval_started = time.monotonic()
    state = _CaptureState()
    try:
        frame = await _capture_frame(cdp, metadata, "url_before")
        navigation_start = len(cdp.navigation_events)
        metadata["url_before"] = str(frame.get("url", cdp.target.get("url", "")))
        metadata["loader_id_before"] = frame.get("loaderId", "")
        for phase in metadata["capture_order"]:
            await _record_capture_phase(cdp, directory, phase, state, metadata,
                interval_started, observation_mode, max_nodes, max_text_chars, agent_browser)
        return await _finish_capture(cdp, directory, state, metadata, interval_started,
            navigation_start, observation_mode, max_nodes, max_text_chars)
    finally:
        # Persist any acquired raw evidence even when a later raw observation
        # fails. Do not issue projection or browser calls after that failure.
        if state.screenshot_bytes is not None:
            (directory / "screenshot.png").write_bytes(state.screenshot_bytes)
        if state.action_observation is not None:
            write_text(directory / "agent_browser_actions.txt", state.action_observation.text)
        if state.snapshot and state.dom_error is None and not (directory / "dom.json").exists():
            write_json(directory / "dom.json", {"result": {"snapshot": state.snapshot}})
        if "raw_capture_ended_at" not in metadata:
            metadata.update(raw_capture_ended_at=utc_now(), raw_capture_duration_seconds=time.monotonic()-interval_started)
            metadata["preserved_raw_artifacts"] = {name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
                for name in ("dom.json", "screenshot.png", "agent_browser_actions.txt") if (directory/name).is_file()}
        metadata.update(ended_at=utc_now(), duration_seconds=time.monotonic()-interval_started)
        write_json(directory / "capture.json", metadata)


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


async def _synchronize_capture_tab(cdp: CDPClient) -> dict[str, Any]:
    # Target metadata identifies tabs without reading page content.
    try:
        targets = (await cdp.call("Target.getTargets", attached=False)).get("targetInfos", [])
    except RunnerError as error:
        if not is_cdp_transport_error(error):
            raise
        target = cdp.target
        return await cdp.reconnect_active_page(AgentBrowserPage(
            "", "", "", target_id=str(target.get("targetId", ""))))
    children = [item for item in targets if item.get("type") == "page"
        and item.get("openerId") == cdp.target.get("targetId")]
    if len(children) > 1:
        raise RunnerError("multiple popup tabs opened; target is ambiguous")
    selected = children[0] if children else next((item for item in targets
        if item.get("targetId") == cdp.target.get("targetId")), None)
    if selected is None:
        raise RunnerError("the task tab closed without a unique popup")
    return await cdp.synchronize_target(AgentBrowserPage(
        "", "", "", target_id=str(selected["targetId"])))


async def synchronize_recorder_target(
    cdp: CDPClient,
    agent_browser: AgentBrowserClient | None,
    *,
    attempts: int = 6,
) -> dict[str, Any]:
    """Apply one exact-target popup policy, then align the reference CLI if used."""
    last_error: BaseException | None = None
    observation_recovered = False
    for attempt in range(1, max(1, attempts) + 1):
        try:
            report = await _synchronize_capture_tab(cdp)
            if agent_browser is not None:
                await cdp.synchronize_target()
                active_page = await agent_browser.active_page(cdp, target_id=str(cdp.target["targetId"]))
                selected = cdp._select_active_target(active_page, [{"targetId": cdp.target["targetId"]}])
                cdp.target_registry[selected["targetId"]]["tab_id"] = active_page.tab_id
                cdp.connection_report["target_registry"] = list(cdp.target_registry.values())
                if cdp.recording_dir is not None:
                    write_json(cdp.recording_dir / "target_registry.json", {"recorded_at": utc_now(),
                        "targets": cdp.connection_report["target_registry"]})
                report["agent_browser_tab_id"] = active_page.tab_id
            return report
        except (AgentBrowserBaseError, RunnerError) as error:
            last_error = error
            if cdp._page_failure is not None:
                raise cdp._page_failure
            if "ambiguous" in str(error) or "without a unique popup" in str(error):
                raise
            if getattr(error, "technical_failure_class", None) == "browser_crash":
                raise
            if getattr(error, "technical_failure_class", None) == "cdp_stall":
                if observation_recovered:
                    raise
                await cdp.recover_observation()
                observation_recovered = True
            if attempt < attempts:
                if agent_browser is not None and isinstance(error, AgentBrowserBaseError):
                    await agent_browser.reconnect()
                await asyncio.sleep(0.5 * attempt)
    assert last_error is not None
    raise RunnerError(f"could not synchronize exact task target after {max(1, attempts)} attempts: {last_error}") from last_error


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
        self._last_capture_document: tuple[str, str, str | None] | None = None
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
        self.paint_events: list[dict[str, Any]] = []

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
                                timeout=LIVENESS_PROBE_SECONDS)
                except Exception as error:
                    entry["identity_error"] = type(error).__name__
                    if self._page_failure is not None:
                        raise self._page_failure
                    if self._transport_error is not None:
                        raise self._transport_error
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
        target_id = active_page.target_id
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
                if method == "LayerTree.layerPainted":
                    self.paint_events.append({"method": method, "recorded_at": utc_now(),
                        "target_id": self.session_targets.get(str(event_session), str(self.target.get("targetId", "")))})
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
