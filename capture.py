"""Browser-facing ChromiumRL capture, target synchronization, and coordinates."""

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

from agent_browser import (
    AgentBrowserBaseError,
    AgentBrowserClient,
    AgentBrowserError,
    AgentBrowserObservation,
    AgentBrowserPage,
)
from recorder_support import RunnerError, normalized_http_url, write_json, write_text
from dom_diff import clean_dom_text, same_document_except_fragment


ROOT = Path(__file__).resolve().parent
FULL_RENDERER = ROOT / "scripts" / "render_chromiumrl_snapshot_full.py"
MODEL_RENDERER = ROOT / "scripts" / "render_chromiumrl_snapshot_model.py"

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

async def recorded_action_coordinate(
    cdp: CDPClient,
    bundle: CaptureBundle,
    target: dict[str, str] | None,
) -> dict[str, Any] | None:
    """Resolve action coordinates without changing DOM capture or diff inputs.

    getAgentObservation is used only for center coordinates. Existing structured
    snapshot bounds are a conservative fallback when that lookup is unavailable.
    """
    primary = await chromiumrl_action_coordinate(cdp, target)
    if isinstance(primary, dict):
        primary["coordinate_source"] = "get_agent_observation"
    if isinstance(primary, dict) and primary.get("status") == "resolved":
        return primary
    fallback = structured_snapshot_action_coordinate(bundle.snapshot, target)
    if isinstance(fallback, dict):
        fallback["coordinate_source"] = "structured_snapshot_bounds"
    if isinstance(fallback, dict) and fallback.get("status") == "resolved":
        fallback["get_agent_observation"] = primary
        return fallback
    if isinstance(primary, dict) and isinstance(fallback, dict):
        primary["structured_snapshot_fallback"] = fallback
    return primary or fallback


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
    line = agent_browser_ref_line(bundle.executable_agent_browser_text(), ref) if ref else ""
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


def verify_agent_browser_action(
    decision: dict[str, Any],
    before: CaptureBundle,
    after: CaptureBundle,
) -> dict[str, Any]:
    """Check writable-control results using the next official CLI observation."""
    action = clean_dom_text(decision.get("action")).lower()
    if action not in {"fill", "type", "select"}:
        return {"applicable": False, "status": "not_applicable"}
    requested = clean_dom_text(decision.get("text"))
    ref = AgentBrowserClient.action_ref(decision.get("id"))
    result: dict[str, Any] = {
        "applicable": True,
        "action": action,
        "ref": ref or None,
        "requested_text": requested,
    }
    if not ref:
        result.update(
            status="unavailable",
            reason="focused control has no attributable snapshot ref",
        )
        return result
    before_line = agent_browser_ref_line(before.executable_agent_browser_text(), ref)
    if not before_line:
        result.update(
            status="unavailable",
            reason="target ref is absent from the before-action observation",
        )
        return result
    signature = agent_browser_control_signature(before_line)
    same_ref_line = agent_browser_ref_line(after.executable_agent_browser_text(), ref)
    candidates = [
        line.strip()
        for line in after.executable_agent_browser_text().splitlines()
        if signature and agent_browser_control_signature(line) == signature
    ]
    if same_ref_line and agent_browser_control_signature(same_ref_line) == signature:
        line = same_ref_line
    else:
        matching_value = [
            line
            for line in candidates
            if requested
            and normalized_observation_text(requested) in normalized_observation_text(line)
        ]
        line = matching_value[0] if len(matching_value) == 1 else candidates[0] if len(candidates) == 1 else ""
    if not line:
        result.update(
            status="unavailable",
            reason="control identity is not unique in the after-action observation",
        )
        return result
    result["control_signature"] = signature
    result["observed_line"] = line[:500]
    if requested and normalized_observation_text(requested) in normalized_observation_text(line):
        result["status"] = "verified"
    else:
        result.update(
            status="mismatch",
            reason="requested value is not visible on the target control",
        )
    return result


def action_progress(
    before: CaptureBundle,
    after: CaptureBundle,
    diff_record: dict[str, Any],
) -> dict[str, bool]:
    """Conservative progress facts; any changed evidence prevents a false stall."""
    before_url = clean_dom_text(before.snapshot.get("url") or before.document_url)
    after_url = clean_dom_text(after.snapshot.get("url") or after.document_url)
    screenshot_changed = (
        before.screenshot_path.exists()
        and after.screenshot_path.exists()
        and before.screenshot_path.read_bytes() != after.screenshot_path.read_bytes()
    )
    observation_changed = bool(
        before.executable_agent_browser_text()
        and after.executable_agent_browser_text()
        and before.executable_agent_browser_text() != after.executable_agent_browser_text()
        and not after.executable_agent_browser_text().startswith(
            "[agent-browser snapshot unavailable:"
        )
    )
    result = {
        "url_changed": before_url != after_url,
        "semantic_dom_changed": int(
            diff_record.get("semantic_change_count", diff_record.get("change_count")) or 0
        )
        > 0,
        "viewport_content_changed": int(diff_record.get("viewport_change_count") or 0) > 0,
        "agent_browser_observation_changed": observation_changed,
        "screenshot_changed": screenshot_changed,
    }
    result["made_progress"] = any(result.values())
    return result


def copy_bundle(bundle: CaptureBundle, directory: Path) -> CaptureBundle:
    """Copy one immutable evidence bundle into an action's before directory."""
    directory.mkdir(parents=True, exist_ok=False)
    snapshot_path = directory / "dom.json"
    screenshot_path = directory / "screenshot.png"
    shutil.copy2(bundle.snapshot_path, snapshot_path)
    shutil.copy2(bundle.snapshot_path.with_name("dom_full.txt"), directory / "dom_full.txt")
    shutil.copy2(bundle.snapshot_path.with_name("dom_model.txt"), directory / "dom_model.txt")
    shutil.copy2(bundle.screenshot_path, screenshot_path)
    agent_browser_path: Path | None = None
    if bundle.agent_browser_path is not None:
        agent_browser_path = directory / "agent_browser.txt"
        shutil.copy2(bundle.agent_browser_path, agent_browser_path)
    agent_browser_action_path: Path | None = None
    if bundle.agent_browser_action_path is not None:
        agent_browser_action_path = directory / "agent_browser_actions.txt"
        shutil.copy2(bundle.agent_browser_action_path, agent_browser_action_path)
    return CaptureBundle(
        snapshot=bundle.snapshot,
        snapshot_path=snapshot_path,
        model_text=bundle.model_text,
        screenshot_path=screenshot_path,
        agent_browser_text=bundle.agent_browser_text,
        agent_browser_action_text=bundle.agent_browser_action_text,
        agent_browser_refs=bundle.agent_browser_refs,
        agent_browser_targets=bundle.agent_browser_targets,
        agent_browser_path=agent_browser_path,
        agent_browser_action_path=agent_browser_action_path,
        agent_browser_snapshot_command=bundle.agent_browser_snapshot_command,
        agent_browser_action_snapshot_command=(
            bundle.agent_browser_action_snapshot_command
        ),
        document_language=bundle.document_language,
        document_url=bundle.document_url,
        document_language_error=bundle.document_language_error,
    )



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
        line = agent_browser_ref_line(bundle.executable_agent_browser_text(), ref)
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


async def chromiumrl_action_coordinate(
    cdp: CDPClient,
    target: dict[str, str] | None,
) -> dict[str, Any] | None:
    """Resolve only a target coordinate through getAgentObservation.

    This supplementary call does not supply model evidence and is never written
    as a DOM capture. Diff and baseline options are explicitly disabled. The
    action ref and semantic identity continue to come from agent-browser; the
    ChromiumRL response is consumed only to obtain the matching element centre.
    """
    if not target:
        return None
    role = clean_dom_text(target.get("role")).casefold()
    name = clean_dom_text(target.get("name"))
    if not name:
        return None
    result = await capture_call(
        cdp,
        "ChromiumRL.getAgentObservation",
        {
            "inViewportOnly": False,
            "includeContent": False,
            "includeDiff": False,
            "updateBaseline": False,
            "maxElements": 10000,
            "maxInteractiveElements": 10000,
            "maxContentBlocks": 0,
            "maxDiffItems": 0,
        },
    )
    observation = result.get("observation")
    if not isinstance(observation, dict):
        raise RunnerError(
            f"unexpected ChromiumRL coordinate response: {result}"
        )
    elements = [
        item for item in observation.get("elements", []) if isinstance(item, dict)
    ]
    normalized_name = normalized_observation_text(name)
    name_matches = [
        item
        for item in elements
        if normalized_observation_text(item.get("accessibleName")) == normalized_name
    ]
    exact_matches = [
        item
        for item in name_matches
        if normalized_observation_text(item.get("role")) == role
    ]
    candidates = exact_matches or name_matches
    hit_testable = [
        item for item in candidates if item.get("isHitTestable") is True
    ]
    visible = [
        item
        for item in (hit_testable or candidates)
        if item.get("isVisible") is not False
    ]
    preferred = hit_testable if len(hit_testable) == 1 else visible
    if len(preferred) == 1:
        match = preferred[0]
        if exact_matches:
            match_method = "exact_role_name"
        else:
            match_method = "unique_accessible_name"
        if hit_testable:
            match_method += "_hit_testable"
    elif len(exact_matches) == 1:
        match = exact_matches[0]
        match_method = "exact_role_name"
    elif not exact_matches and len(name_matches) == 1:
        match = name_matches[0]
        match_method = "unique_accessible_name"
    else:
        return {
            "status": "ambiguous" if exact_matches or name_matches else "not_found",
            "source": "ChromiumRL.getAgentObservation",
            "match_method": None,
            "candidate_count": len(candidates),
        }
    center_x = match.get("centerX")
    center_y = match.get("centerY")
    if not isinstance(center_x, (int, float)) or not isinstance(center_y, (int, float)):
        bounds = match.get("bounds")
        if isinstance(bounds, dict):
            x = bounds.get("x")
            y = bounds.get("y")
            width = bounds.get("width")
            height = bounds.get("height")
            if all(isinstance(value, (int, float)) for value in (x, y, width, height)):
                center_x = float(x) + float(width) / 2
                center_y = float(y) + float(height) / 2
    if not isinstance(center_x, (int, float)) or not isinstance(center_y, (int, float)):
        return {
            "status": "missing_geometry",
            "source": "ChromiumRL.getAgentObservation",
            "match_method": match_method,
            "candidate_count": 1,
        }
    return {
        "status": "resolved",
        "source": "ChromiumRL.getAgentObservation",
        "match_method": match_method,
        "candidate_count": 1,
        "coordinate": [int(round(float(center_x))), int(round(float(center_y)))],
    }


def structured_snapshot_action_coordinate(
    snapshot: dict[str, Any],
    target: dict[str, str] | None,
) -> dict[str, Any] | None:
    """Use existing structured-snapshot geometry when an action is omitted.

    No additional snapshot is taken. This fallback is accepted only for one
    visible, hit-testable node with the same semantic name. Agent-browser's
    LabelText pseudo-role maps to an actual HTML label; all other role matches
    use exact browser roles, with a unique-name fallback for cross-AX naming.
    """
    if not target:
        return None
    target_name = normalized_observation_text(target.get("name"))
    target_role = normalized_observation_text(target.get("role"))
    if not target_name:
        return None
    nodes = [
        node for node in snapshot.get("nodes", []) if isinstance(node, dict)
    ]
    name_matches = [
        node
        for node in nodes
        if normalized_observation_text(node.get("accessibleName")) == target_name
        and node.get("visible") is not False
        and node.get("hitTestable") is True
    ]

    def role_matches(node: dict[str, Any]) -> bool:
        """Match exact roles, with agent-browser LabelText mapped to HTML label."""
        node_role = normalized_observation_text(node.get("role"))
        node_tag = normalized_observation_text(node.get("tag"))
        if target_role == "labeltext":
            return node_tag == "label"
        return bool(target_role and node_role == target_role)

    exact_matches = [node for node in name_matches if role_matches(node)]
    candidates = exact_matches or name_matches
    if len(candidates) != 1:
        return {
            "status": "ambiguous" if candidates else "not_found",
            "source": "ChromiumRL.captureStructuredSnapshot.bounds",
            "match_method": None,
            "candidate_count": len(candidates),
        }
    node = candidates[0]
    bounds = node.get("clippedBounds") or node.get("bounds")
    if not isinstance(bounds, dict):
        return {
            "status": "missing_geometry",
            "source": "ChromiumRL.captureStructuredSnapshot.bounds",
            "match_method": (
                "exact_role_name" if exact_matches else "unique_accessible_name"
            ),
            "candidate_count": 1,
        }
    values = [bounds.get(key) for key in ("x", "y", "width", "height")]
    if not all(isinstance(value, (int, float)) for value in values):
        return {
            "status": "missing_geometry",
            "source": "ChromiumRL.captureStructuredSnapshot.bounds",
            "match_method": (
                "exact_role_name" if exact_matches else "unique_accessible_name"
            ),
            "candidate_count": 1,
        }
    x, y, width, height = (float(value) for value in values)
    return {
        "status": "resolved",
        "source": "ChromiumRL.captureStructuredSnapshot.bounds",
        "match_method": (
            "exact_role_name" if exact_matches else "unique_accessible_name"
        ),
        "candidate_count": 1,
        "coordinate": [
            int(round(x + width / 2)),
            int(round(y + height / 2)),
        ],
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


def render_stored_snapshot(snapshot_path: Path) -> None:
    """Regenerate both text projections from one stored structured snapshot."""
    full_path = snapshot_path.with_name("dom_full.txt")
    model_path = snapshot_path.with_name("dom_model.txt")
    run_renderer(
        [
            str(FULL_RENDERER),
            str(snapshot_path),
            "--output",
            str(full_path),
            "--include-action-index",
            "--include-child-refs",
        ]
    )
    run_renderer(
        [
            str(MODEL_RENDERER),
            str(snapshot_path),
            "--output",
            str(model_path),
            "--include-offscreen-content",
            "--include-secondary",
            "--max-secondary-actions",
            "160",
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
        "model": file_version(MODEL_RENDERER),
    }


async def capture_call(
    cdp: CDPClient,
    method: str,
    params: dict[str, Any],
    *,
    attempts: int = 2,
) -> dict[str, Any]:
    """Retry a read-only capture command only when its response times out."""
    for attempt in range(1, attempts + 1):
        try:
            return await cdp.call(method, params)
        except TimeoutError as error:
            if attempt == attempts:
                raise RunnerError(f"{method} timed out after {attempts} attempts") from error
            await asyncio.sleep(0.5 * attempt)
    raise AssertionError("unreachable")


async def capture_structured_snapshot(
    cdp: CDPClient,
    *,
    max_nodes: int,
    max_text_chars: int,
) -> dict[str, Any]:
    """Capture an initial or before-action snapshot through ChromiumRL.

    Offscreen nodes are requested so recorded evidence does not depend only on
    the current viewport. After actions, captureSnapshotDiff owns both capture
    and comparison.
    """
    params: dict[str, Any] = {
        "inViewportOnly": False,
        "maxNodes": max_nodes,
        "maxTextChars": max_text_chars,
        "includeOffscreen": True,
    }
    result = await capture_call(
        cdp,
        "ChromiumRL.captureStructuredSnapshot",
        params,
    )
    snapshot = result.get("snapshot")
    if not isinstance(snapshot, dict):
        raise RunnerError(f"unexpected ChromiumRL snapshot response: {result}")
    return snapshot


async def capture_snapshot_diff(
    cdp: CDPClient,
    before_snapshot: dict[str, Any],
    *,
    action_type: str | None,
    max_nodes: int,
    max_text_chars: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture the after-state and compute its diff inside ChromiumRL."""
    params: dict[str, Any] = {
        "beforeSnapshot": before_snapshot,
        "inViewportOnly": False,
        "maxNodes": max_nodes,
        "maxTextChars": max_text_chars,
        "includeOffscreen": True,
    }
    if action_type:
        params["actionType"] = action_type
    result = await capture_call(
        cdp,
        "ChromiumRL.captureSnapshotDiff",
        params,
        attempts=1,
    )
    after_snapshot = result.get("afterSnapshot")
    diff = result.get("diff")
    if not isinstance(after_snapshot, dict) or not isinstance(diff, dict):
        raise RunnerError(
            f"unexpected ChromiumRL captureSnapshotDiff response: {result}"
        )
    return after_snapshot, diff


async def materialize_bundle(
    cdp: CDPClient,
    directory: Path,
    snapshot: dict[str, Any],
) -> CaptureBundle:
    """Atomically materialize one snapshot, screenshot, and two text views."""
    screenshot_result = await capture_call(
        cdp,
        "Page.captureScreenshot",
        {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
    )
    screenshot_data = screenshot_result.get("data")
    if not isinstance(screenshot_data, str):
        raise RunnerError("Page.captureScreenshot returned no image")
    language_state = await page_language_state(cdp)

    # Do not materialize a partial after/ directory if the CDP transport drops
    # between snapshot and screenshot capture; the caller can reconnect and retry.
    directory.mkdir(parents=True, exist_ok=False)
    snapshot_path = directory / "dom.json"
    write_json(snapshot_path, {"result": {"snapshot": snapshot}})
    screenshot_path = directory / "screenshot.png"
    screenshot_path.write_bytes(base64.b64decode(screenshot_data))
    render_stored_snapshot(snapshot_path)
    model_path = directory / "dom_model.txt"
    return CaptureBundle(
        snapshot=snapshot,
        snapshot_path=snapshot_path,
        model_text=model_path.read_text(encoding="utf-8"),
        screenshot_path=screenshot_path,
        document_language=language_state.language,
        document_url=language_state.url,
        document_language_error=language_state.error,
    )


async def capture_after_action_bundle(
    cdp: CDPClient,
    agent_browser: AgentBrowserClient,
    directory: Path,
    *,
    max_nodes: int,
    max_text_chars: int,
    attempts: int = 3,
) -> tuple[CaptureBundle, list[dict[str, Any]]]:
    """Capture after an action, reattaching only if the CDP transport was lost."""
    reconnects: list[dict[str, Any]] = []
    for attempt in range(1, max(1, attempts) + 1):
        try:
            snapshot = await capture_structured_snapshot(
                cdp,
                max_nodes=max_nodes,
                max_text_chars=max_text_chars,
            )
            bundle = await materialize_bundle(cdp, directory, snapshot)
            return bundle, reconnects
        except RunnerError as error:
            if not is_cdp_transport_error(error) or attempt >= max(1, attempts):
                raise
            reconnect = await synchronize_recorder_target(cdp, agent_browser)
            reconnect["capture_attempt"] = attempt
            reconnects.append(reconnect)
            await asyncio.sleep(0.75 * attempt)
    raise AssertionError("unreachable")


async def capture_after_action_diff_bundle(
    cdp: CDPClient,
    agent_browser: AgentBrowserClient,
    directory: Path,
    before_snapshot: dict[str, Any],
    *,
    action_type: str | None,
    max_nodes: int,
    max_text_chars: int,
    attempts: int = 3,
) -> tuple[CaptureBundle, dict[str, Any], list[dict[str, Any]]]:
    """Capture and diff after an action, reattaching on transport loss."""
    reconnects: list[dict[str, Any]] = []
    for attempt in range(1, max(1, attempts) + 1):
        try:
            snapshot, diff = await capture_snapshot_diff(
                cdp,
                before_snapshot,
                action_type=action_type,
                max_nodes=max_nodes,
                max_text_chars=max_text_chars,
            )
            bundle = await materialize_bundle(cdp, directory, snapshot)
            return bundle, diff, reconnects
        except RunnerError as error:
            if not is_cdp_transport_error(error) or attempt >= max(1, attempts):
                raise
            reconnect = await synchronize_recorder_target(cdp, agent_browser)
            reconnect["capture_attempt"] = attempt
            reconnects.append(reconnect)
            await asyncio.sleep(0.75 * attempt)
    raise AssertionError("unreachable")


async def capture_bundle(
    cdp: CDPClient,
    directory: Path,
    *,
    max_nodes: int,
    max_text_chars: int,
) -> CaptureBundle:
    """Capture and materialize an ordinary before/initial evidence bundle."""
    snapshot = await capture_structured_snapshot(
        cdp,
        max_nodes=max_nodes,
        max_text_chars=max_text_chars,
    )
    return await materialize_bundle(cdp, directory, snapshot)


async def attach_agent_browser_observation(
    bundle: CaptureBundle,
    agent_browser: AgentBrowserClient,
    *,
    attempts: int = 3,
) -> CaptureBundle:
    """Store the exact agent-browser ref snapshot supplied to the model."""
    for attempt in range(1, max(1, attempts) + 1):
        try:
            observation = await agent_browser.snapshot()
            action_observation = await agent_browser.snapshot(interactive=True)
            break
        except Exception:
            if attempt >= max(1, attempts):
                raise
            await agent_browser.reconnect()
            await asyncio.sleep(0.75 * attempt)
    else:
        raise AssertionError("unreachable")
    path = bundle.snapshot_path.with_name("agent_browser.txt")
    action_path = bundle.snapshot_path.with_name("agent_browser_actions.txt")
    write_text(path, observation.text)
    write_text(action_path, action_observation.text)
    return CaptureBundle(
        snapshot=bundle.snapshot,
        snapshot_path=bundle.snapshot_path,
        model_text=bundle.model_text,
        screenshot_path=bundle.screenshot_path,
        agent_browser_text=observation.text,
        agent_browser_action_text=action_observation.text,
        agent_browser_refs=action_observation.refs,
        agent_browser_targets=action_observation.targets,
        agent_browser_path=path,
        agent_browser_action_path=action_path,
        agent_browser_snapshot_command=observation.command,
        agent_browser_action_snapshot_command=action_observation.command,
        document_language=bundle.document_language,
        document_url=bundle.document_url,
        document_language_error=bundle.document_language_error,
    )


def attach_agent_browser_observation_error(
    bundle: CaptureBundle,
    error: BaseException,
) -> CaptureBundle:
    """Materialize a failed supplementary observation without losing the DOM diff."""
    path = bundle.snapshot_path.with_name("agent_browser.txt")
    action_path = bundle.snapshot_path.with_name("agent_browser_actions.txt")
    text = f"[agent-browser snapshot unavailable: {type(error).__name__}: {error}]\n"
    write_text(path, text)
    write_text(action_path, text)
    return CaptureBundle(
        snapshot=bundle.snapshot,
        snapshot_path=bundle.snapshot_path,
        model_text=bundle.model_text,
        screenshot_path=bundle.screenshot_path,
        agent_browser_text=text,
        agent_browser_action_text=text,
        agent_browser_refs=frozenset(),
        agent_browser_targets={},
        agent_browser_path=path,
        agent_browser_action_path=action_path,
        agent_browser_snapshot_command=(),
        agent_browser_action_snapshot_command=(),
        document_language=bundle.document_language,
        document_url=bundle.document_url,
        document_language_error=bundle.document_language_error,
    )



@dataclass(frozen=True)
class PageLanguageState:
    url: str = ""
    language: str = ""
    english_alternate_url: str = ""
    error: str = ""


def is_english_language(value: str) -> bool:
    """Accept plain English and any English BCP-47 regional variant."""
    language = value.strip().lower().replace("_", "-")
    return language == "en" or language.startswith("en-")


def english_locale_path_url(value: str) -> str:
    """Replace one BCP-47 locale path segment with en-US, generically."""
    parsed = urlsplit(value)
    parts = parsed.path.split("/")
    for index, part in enumerate(parts):
        if re.fullmatch(r"[A-Za-z]{2}-[A-Za-z]{2}", part) and not is_english_language(part):
            parts[index] = "en-US"
            return urlunsplit(
                (parsed.scheme, parsed.netloc, "/".join(parts), parsed.query, parsed.fragment)
            )
    return ""


async def page_language_state(cdp: CDPClient) -> PageLanguageState:
    """Read the live document locale without changing ChromiumRL capture output."""
    expression = """(() => {
      const alternates = [...document.querySelectorAll('link[rel="alternate"][hreflang]')]
        .map(node => ({
          language: node.hreflang || '',
          label: '',
          url: node.href || '',
          authoritative: true,
        }));
      const languageLinks = [...document.querySelectorAll('a[href]')]
        .map(node => ({
          language: node.hreflang || node.lang || '',
          label: (node.innerText || node.textContent || node.getAttribute('aria-label') || '').trim(),
          url: node.href || '',
          authoritative: false,
        }));
      return {
        url: location.href,
        language: document.documentElement.lang || '',
        alternates: [...alternates, ...languageLinks],
      };
    })()"""
    try:
        result = await cdp.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        value = (result.get("result") or {}).get("value")
        if not isinstance(value, dict):
            raise RunnerError("Runtime.evaluate returned no page-language object")
        candidates = [
            item
            for item in value.get("alternates", []) or []
            if isinstance(item, dict)
            and (
                is_english_language(str(item.get("language", "")))
                or bool(
                    re.fullmatch(
                        r"english(?:\s*\([^)]*\))?",
                        clean_dom_text(item.get("label")),
                        re.IGNORECASE,
                    )
                )
            )
            and str(item.get("url", "")).startswith(("http://", "https://"))
        ]
        candidates.sort(
            key=lambda item: (
                0 if item.get("authoritative") is True else 1,
                0 if str(item.get("language", "")).lower().replace("_", "-") == "en-us" else 1,
                0 if str(item.get("language", "")).lower() == "en" else 1,
                0 if clean_dom_text(item.get("label")).lower() == "english" else 1,
            )
        )
        return PageLanguageState(
            url=str(value.get("url", "")),
            language=str(value.get("language", "")).strip(),
            english_alternate_url=str(candidates[0]["url"]) if candidates else "",
        )
    except Exception as error:
        return PageLanguageState(error=f"{type(error).__name__}: {error}")


async def ensure_english_page(
    cdp: CDPClient,
    agent_browser: "AgentBrowserClient",
    *,
    settle_seconds: float,
    max_redirects: int = 2,
) -> tuple[PageLanguageState, list[dict[str, str]]]:
    """Follow authoritative English alternates before exposing a page to the model."""
    redirects: list[dict[str, str]] = []
    state = await page_language_state(cdp)
    for _ in range(max(0, max_redirects)):
        if not state.language or is_english_language(state.language):
            break
        candidate = state.english_alternate_url or english_locale_path_url(state.url)
        if not candidate or candidate == state.url:
            break
        redirects.append(
            {
                "from_url": state.url,
                "from_language": state.language,
                "to_url": candidate,
            }
        )
        await agent_browser.execute({"action": "navigate", "url": candidate})
        await asyncio.sleep(settle_seconds)
        state = await page_language_state(cdp)
    return state, redirects


async def synchronize_recorder_target(
    cdp: CDPClient,
    agent_browser: AgentBrowserClient,
    *,
    attempts: int = 3,
) -> dict[str, Any]:
    """Keep capture and action sessions on the same active page.

    A popup target can appear before Target.getTargets exposes its final URL.
    Retry the official active-tab lookup and target match briefly, but never
    fall back to capturing the previously attached page.
    """
    last_error: BaseException | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            active_page = await agent_browser.active_page()
            return await cdp.synchronize_target(active_page)
        except AgentBrowserBaseError as error:
            last_error = error
            if attempt < attempts:
                await agent_browser.reconnect()
                await asyncio.sleep(0.25 * attempt)
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
                await asyncio.sleep(0.25 * attempt)
    assert last_error is not None
    raise RunnerError(
        f"could not synchronize recorder to agent-browser active tab after "
        f"{max(1, attempts)} attempts: {last_error}"
    ) from last_error


@dataclass
class CaptureBundle:
    snapshot: dict[str, Any]
    snapshot_path: Path
    model_text: str
    screenshot_path: Path
    agent_browser_text: str = ""
    agent_browser_action_text: str = ""
    agent_browser_refs: frozenset[str] = field(default_factory=frozenset)
    agent_browser_targets: dict[str, dict[str, str]] = field(default_factory=dict)
    agent_browser_path: Path | None = None
    agent_browser_action_path: Path | None = None
    agent_browser_snapshot_command: tuple[str, ...] = field(default_factory=tuple)
    agent_browser_action_snapshot_command: tuple[str, ...] = field(default_factory=tuple)
    document_language: str = ""
    document_url: str = ""
    document_language_error: str = ""

    def executable_agent_browser_text(self) -> str:
        """Prefer the interactive-only ref snapshot used for executable actions."""
        return self.agent_browser_action_text or self.agent_browser_text



class CDPClient:
    def __init__(
        self,
        http_url: str,
        timeout: float = 30.0,
        *,
        keep_existing_tabs: bool = False,
        browser_language: str = "",
        browser_accept_language: str = "",
    ):
        """Configure one flattened CDP session and its tab/locale policy."""
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
        self.pending: dict[int, tuple[str, asyncio.Future[dict[str, Any]]]] = {}
        self.session_id = ""
        self.target: dict[str, Any] = {}
        self.connection_report: dict[str, Any] = {}

    async def _enable_attached_target(self) -> dict[str, Any]:
        """Enable required domains and best-effort English locale overrides."""
        for method in ("Page.enable", "DOM.enable", "Runtime.enable", "ChromiumRL.enable"):
            await self.call(method)
        locale_setup: dict[str, Any] = {}
        for label, method, params in (
            ("network_enable", "Network.enable", {}),
            (
                "accept_language_header",
                "Network.setExtraHTTPHeaders",
                {"headers": {"Accept-Language": self.browser_accept_language}},
            ),
            (
                "locale_override",
                "Emulation.setLocaleOverride",
                {"locale": self.browser_language},
            ),
        ):
            if label == "accept_language_header" and not self.browser_accept_language:
                locale_setup[label] = {"status": "skipped", "reason": "empty configuration"}
                continue
            if label == "locale_override" and not self.browser_language:
                locale_setup[label] = {"status": "skipped", "reason": "empty configuration"}
                continue
            try:
                await self.call(method, params)
                locale_setup[label] = {
                    "status": "ok",
                    "value": next(iter(params.values()), None),
                }
            except Exception as error:
                locale_setup[label] = {
                    "status": "error",
                    "error": f"{type(error).__name__}: {error}",
                }
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
        """Always release websocket and HTTP resources on context exit."""
        await self.close()

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
        """Create a clean task tab, close stale task tabs, and attach ChromiumRL."""
        await self._open_browser_transport()

        targets = (await self.call("Target.getTargets", attached=False)).get("targetInfos", [])
        pages = [
            item
            for item in targets
            if item.get("type") == "page"
            and not str(item.get("url", "")).startswith("devtools://")
        ]
        pages.sort(
            key=lambda item: (
                0
                if str(item.get("url", "")).startswith(("http://", "https://"))
                else 1
            )
        )
        cleanup: dict[str, Any] = {
            "page_targets_found": len(pages),
            "page_target_urls": [str(item.get("url", "")) for item in pages],
            "keep_existing_tabs": self.keep_existing_tabs,
            "fresh_target_created": False,
            "closed_count": 0,
            "closed_targets": [],
            "close_errors": [],
            "warnings": [],
        }
        if len(pages) > 10:
            cleanup["warnings"].append(
                f"found {len(pages)} live page targets; prior runs may have left browser state behind"
            )

        if self.keep_existing_tabs:
            if not pages:
                raise RunnerError("browser exposes no page target")
            self.target = pages[0]
        else:
            created = await self.call(
                "Target.createTarget",
                {"url": "about:blank"},
                attached=False,
            )
            fresh_target_id = str(created.get("targetId", ""))
            if not fresh_target_id:
                raise RunnerError("Target.createTarget returned no targetId")
            refreshed = (
                await self.call("Target.getTargets", attached=False)
            ).get("targetInfos", [])
            self.target = next(
                (
                    item
                    for item in refreshed
                    if str(item.get("targetId", "")) == fresh_target_id
                ),
                {
                    "targetId": fresh_target_id,
                    "type": "page",
                    "title": "",
                    "url": "about:blank",
                },
            )
            cleanup["fresh_target_created"] = True
            cleanup["fresh_target_id"] = fresh_target_id
            stale_pages = [
                item
                for item in refreshed
                if item.get("type") == "page"
                and str(item.get("targetId", "")) != fresh_target_id
                and not str(item.get("url", "")).startswith("devtools://")
            ]
            closed_target_ids: set[str] = set()
            cleanup_passes = 0
            cleanup_timeout_seconds = 5.0
            cleanup_deadline = time.monotonic() + cleanup_timeout_seconds
            while stale_pages and time.monotonic() < cleanup_deadline:
                cleanup_passes += 1
                for page in stale_pages:
                    target_id = str(page.get("targetId", ""))
                    url = str(page.get("url", ""))
                    try:
                        result = await self.call(
                            "Target.closeTarget",
                            {"targetId": target_id},
                            attached=False,
                        )
                        if result.get("success") is False:
                            raise RunnerError(
                                "Target.closeTarget returned success=false"
                            )
                        if target_id not in closed_target_ids:
                            cleanup["closed_targets"].append(
                                {"target_id": target_id, "url": url}
                            )
                            closed_target_ids.add(target_id)
                    except Exception as error:
                        cleanup["close_errors"].append(
                            {
                                "target_id": target_id,
                                "url": url,
                                "error": f"{type(error).__name__}: {error}",
                            }
                        )
                await asyncio.sleep(0.25)
                remaining_targets = (
                    await self.call("Target.getTargets", attached=False)
                ).get("targetInfos", [])
                stale_pages = [
                    item
                    for item in remaining_targets
                    if item.get("type") == "page"
                    and str(item.get("targetId", "")) != fresh_target_id
                    and not str(item.get("url", "")).startswith("devtools://")
                ]
            cleanup["cleanup_passes"] = cleanup_passes
            cleanup["cleanup_timeout_seconds"] = cleanup_timeout_seconds
            cleanup["closed_count"] = len(cleanup["closed_targets"])
            cleanup["remaining_page_targets"] = [
                {
                    "target_id": str(item.get("targetId", "")),
                    "url": str(item.get("url", "")),
                }
                for item in stale_pages
            ]
            if stale_pages:
                remaining = ", ".join(
                    str(item.get("targetId", "")) for item in stale_pages
                )
                raise RunnerError(
                    "could not close all previous task page targets: " + remaining
                )
            await self.call(
                "Target.activateTarget",
                {"targetId": fresh_target_id},
                attached=False,
            )

        cleanup["selected_target_id"] = self.target.get("targetId")
        cleanup["selected_target_url"] = str(self.target.get("url", ""))
        attached = await self.call(
            "Target.attachToTarget",
            {"targetId": self.target["targetId"], "flatten": True},
            attached=False,
        )
        self.session_id = str(attached["sessionId"])
        locale_setup = await self._enable_attached_target()
        self.connection_report = {
            "browser_version": self.browser_version,
            "tab_cleanup": cleanup,
            "locale_setup": locale_setup,
            "target_switches": [],
        }

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
        """Attach ChromiumRL capture to agent-browser's active page target.

        agent-browser follows a newly opened tab automatically, while a flattened
        CDP session remains attached to the page it originally selected. Match
        the official active-tab URL/title against live page targets and reattach
        before capturing. Ambiguous matches fail loudly instead of recording
        evidence from the wrong page.
        """
        targets = (await self.call("Target.getTargets", attached=False)).get(
            "targetInfos", []
        )
        pages = [
            item
            for item in targets
            if item.get("type") == "page"
            and not str(item.get("url", "")).startswith("devtools://")
        ]
        active_key = comparable_page_url(active_page.url)
        candidates = [
            item
            for item in pages
            if comparable_page_url(str(item.get("url", ""))) == active_key
        ]
        if len(candidates) > 1 and active_page.title:
            title_matches = [
                item
                for item in candidates
                if str(item.get("title", "")).strip() == active_page.title.strip()
            ]
            if title_matches:
                candidates = title_matches
        if not candidates:
            raise RunnerError(
                "agent-browser active tab has no matching CDP page target: "
                f"tab={active_page.tab_id!r} url={active_page.url!r} "
                f"title={active_page.title!r}"
            )
        if len(candidates) != 1:
            raise RunnerError(
                "agent-browser active tab matches multiple CDP page targets; "
                "refusing to capture an ambiguous page: "
                f"tab={active_page.tab_id!r} url={active_page.url!r} "
                f"title={active_page.title!r} matches={len(candidates)}"
            )

        selected = candidates[0]
        old_target_id = str(self.target.get("targetId", ""))
        new_target_id = str(selected.get("targetId", ""))
        report: dict[str, Any] = {
            "agent_browser_tab_id": active_page.tab_id,
            "agent_browser_url": active_page.url,
            "agent_browser_title": active_page.title,
            "previous_target_id": old_target_id,
            "previous_target_url": str(self.target.get("url", "")),
            "selected_target_id": new_target_id,
            "selected_target_url": str(selected.get("url", "")),
            "switched": new_target_id != old_target_id,
        }
        if new_target_id == old_target_id:
            self.target = selected
            return report

        old_session_id = self.session_id
        if old_session_id:
            try:
                await self.call(
                    "Target.detachFromTarget",
                    {"sessionId": old_session_id},
                    attached=False,
                )
            except Exception as error:
                report["detach_error"] = f"{type(error).__name__}: {error}"
        attached = await self.call(
            "Target.attachToTarget",
            {"targetId": new_target_id, "flatten": True},
            attached=False,
        )
        self.session_id = str(attached["sessionId"])
        self.target = selected
        report["locale_setup"] = await self._enable_attached_target()
        self.connection_report.setdefault("target_switches", []).append(report)
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
            message_id = payload.get("id")
            if isinstance(message_id, int) and message_id in self.pending:
                _method, future = self.pending.pop(message_id)
                if not future.done():
                    future.set_result(payload)
                continue
        error = RunnerError("CDP websocket closed")
        for _method, future in self.pending.values():
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
        self.pending[message_id] = (method, future)
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




def is_recoverable_action_error(error: BaseException) -> bool:
    """Return whether an action hit a transient browser-state failure.

    Dynamic pages can replace an element after a snapshot is captured but before
    the next action reaches CDP. The failed action remains recorded; the runner
    can then continue from the fresh after-action snapshot instead of treating a
    transient stale node or action timeout as a terminal task failure.
    """
    if isinstance(error, TimeoutError):
        return True
    if isinstance(error, AgentBrowserError):
        detail = error.error.lower()
        return any(
            marker in detail
            for marker in (
                "not found",
                "no element",
                "stale",
                "covered",
                "intercepts pointer events",
                "could not compute box model",
                "timeout",
                "timed out",
            )
        )
    return False


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
