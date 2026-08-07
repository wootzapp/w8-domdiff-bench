#!/usr/bin/env python3
"""Shared desktop Wootz ChromiumRL/CDP capture utilities."""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import hashlib
import json
import gzip
import os
import re
import sys
import time
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp


SCHEMA_VERSION = "1.0"
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
COORDINATE_ACTIONS = {"click", "left_click", "scroll", "mouse_move", "fill"}

TIMEOUT_DOM_CAPTURE = 20.0
TIMEOUT_OBSERVATION = 10.0
TIMEOUT_SCREENSHOT = 10.0
TIMEOUT_EVALUATE = 5.0
TIMEOUT_INPUT = 8.0
TIMEOUT_SIGNAL = 2.0

class RecorderError(RuntimeError):
    pass


class ChromiumRLUnavailable(RecorderError):
    pass


class CDPCommandError(RecorderError):
    def __init__(self, method: str, error: Any):
        super().__init__(f"CDP command {method} failed: {error}")
        self.method = method
        self.error = error


def is_session_not_found(error: BaseException) -> bool:
    if not isinstance(error, CDPCommandError):
        return False
    if isinstance(error.error, dict):
        message = str(error.error.get("message", ""))
    else:
        message = str(error.error)
    return "Session with given id not found" in message


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def first_number(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, (int, float)):
            return float(value)
    return None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_json_compact(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_json_gz(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(",", ":"))
    temporary.replace(path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def log_event(cdp: Any, event: str, **fields: Any) -> None:
    record = {"ts": utc_now(), "event": event, **fields}
    try:
        if getattr(cdp, "log_path", None) is not None:
            append_jsonl(cdp.log_path, record)
        elif hasattr(cdp, "event_log"):
            cdp.event_log.append(record)
    except Exception:
        pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_task_id(task_id: str) -> str:
    if not TASK_ID_RE.fullmatch(task_id):
        raise RecorderError(
            "task id must start with a letter or digit and contain only letters, digits, '.', '_' or '-'"
        )
    return task_id


def normalized_http_base(value: str) -> str:
    raw = value.strip().rstrip("/")
    if raw.startswith("ws://"):
        raw = "http://" + raw[5:]
    elif raw.startswith("wss://"):
        raw = "https://" + raw[6:]
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RecorderError(f"invalid CDP URL: {value!r}")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def rewrite_websocket_url(websocket_url: str, http_base: str) -> str:
    source = urlsplit(websocket_url)
    target = urlsplit(http_base)
    scheme = "wss" if target.scheme == "https" else "ws"
    return urlunsplit((scheme, target.netloc, source.path, source.query, ""))


def target_id(target: dict[str, Any]) -> str:
    return str(target.get("targetId") or target.get("id") or "")


def normalize_target_info(target: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(target)
    identifier = target_id(normalized)
    if identifier and "targetId" not in normalized:
        normalized["targetId"] = identifier
    if identifier and "id" not in normalized:
        normalized["id"] = identifier
    return normalized


def target_priority(target: dict[str, Any]) -> tuple[int, int, int, int]:
    url = str(target.get("url", ""))
    title = str(target.get("title", ""))
    is_web_url = url.startswith(("http://", "https://"))
    is_blank = url in {"", "about:blank"} or url.startswith(("chrome-native://", "chrome://"))
    has_real_title = bool(title.strip()) and title.strip().lower() not in {"about:blank", "new tab"}
    is_attached = bool(target.get("attached"))
    return (
        0 if is_web_url else 1,
        0 if not is_blank else 1,
        0 if has_real_title else 1,
        0 if is_attached else 1,
    )


def select_page_target(targets: list[dict[str, Any]], target_url_contains: str = "") -> dict[str, Any]:
    candidates = [normalize_target_info(item) for item in targets if item.get("type") == "page"]
    candidates = [item for item in candidates if not str(item.get("url", "")).startswith("devtools://")]
    if target_url_contains:
        candidates = [item for item in candidates if target_url_contains in str(item.get("url", ""))]
    if not candidates:
        qualifier = f" containing {target_url_contains!r}" if target_url_contains else ""
        raise RecorderError(f"no page target{qualifier} is exposed by WootzApp")
    best_priority = min(target_priority(item) for item in candidates)
    for item in candidates:
        if target_priority(item) == best_priority:
            return item
    return candidates[0]


def safe_target_dir_name(index: int, target: dict[str, Any]) -> str:
    identifier = target_id(target) or f"target-{index:02d}"
    url = str(target.get("url", ""))
    title = str(target.get("title", ""))
    source = urlsplit(url).netloc or title or identifier
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", source).strip("._-")[:48] or "page"
    return f"{index:02d}_{identifier}_{slug}"


class CDPConnection:
    def __init__(
        self,
        http_base: str,
        command_timeout: float = 30.0,
        target_url_contains: str = "",
    ) -> None:
        self.http_base = normalized_http_base(http_base)
        self.command_timeout = command_timeout
        self.target_url_contains = target_url_contains
        self.http: aiohttp.ClientSession | None = None
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self.message_id = 0
        self.session_id = ""
        self.target: dict[str, Any] = {}
        self.version: dict[str, Any] = {}
        self.pinned_target_id = ""
        self.pending: dict[int, tuple[str, asyncio.Future[dict[str, Any]]]] = {}
        self.reader_task: asyncio.Task[None] | None = None
        self.event_log: list[dict[str, Any]] = []
        self.renderer_crashed: dict[str, Any] | None = None
        self.enable_runtime_domain = False
        self.main_frame_navigated = False
        self.renderer_wedged = False
        self.log_path: Path | None = None

    async def __aenter__(self) -> "CDPConnection":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.close()

    async def get_json(self, path: str) -> Any:
        if self.http is None:
            raise RecorderError("CDP HTTP session is not initialized")
        url = self.http_base + path
        try:
            async with self.http.get(
                url,
                headers={"Host": "localhost"},
                timeout=aiohttp.ClientTimeout(total=self.command_timeout),
            ) as response:
                body = await response.text()
                if response.status != 200:
                    raise RecorderError(f"GET {url} returned HTTP {response.status}: {body[:500]}")
                return json.loads(body)
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as error:
            raise RecorderError(f"cannot read CDP endpoint {url}: {error}") from error

    async def connect(self) -> None:
        self.http = aiohttp.ClientSession()
        try:
            self.version = await self.get_json("/json/version")
            browser_ws = self.version.get("webSocketDebuggerUrl")
            if not browser_ws:
                raise RecorderError("/json/version has no webSocketDebuggerUrl")
            rewritten = rewrite_websocket_url(str(browser_ws), self.http_base)
            self.ws = await self.http.ws_connect(
                rewritten,
                headers={"Host": "localhost"},
                timeout=aiohttp.ClientWSTimeout(
                    ws_receive=self.command_timeout,
                    ws_close=10.0,
                ),
                heartbeat=20,
                max_msg_size=256 * 1024 * 1024,
            )
            self.reader_task = asyncio.create_task(self._reader_loop())

            await self.refresh_page_session()
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            await self.close()
            raise RecorderError(f"cannot connect to browser WebSocket {self.http_base}: {error}") from error
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        if self.ws is not None and not self.ws.closed and self.session_id:
            with contextlib.suppress(Exception):
                await self.send("ChromiumRL.disable", {}, use_session=True, timeout=2.0)
        if self.reader_task is not None:
            self.reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError, TimeoutError):
                await self.reader_task
            self.reader_task = None
        if self.ws is not None and not self.ws.closed:
            await self.ws.close()
        if self.http is not None and not self.http.closed:
            await self.http.close()
        self.ws = None
        self.http = None
        self.session_id = ""
        self.pending.clear()

    async def reconnect(self) -> None:
        await self.close()
        await self.connect()

    async def refresh_page_session(self) -> None:
        targets = await self.page_targets()
        pinned = next((item for item in targets if self.pinned_target_id and target_id(item) == self.pinned_target_id), None)
        if pinned is not None:
            self.target = pinned
        else:
            previous = self.pinned_target_id or target_id(self.target)
            self.target = select_page_target(targets, self.target_url_contains)
            selected = target_id(self.target)
            self.event_log.append(
                {
                    "timestamp": utc_now(),
                    "event": "initial_target_selected" if not previous else "target_switched",
                    "previous_target_id": previous,
                    "selected_target_id": selected,
                    "selected_target": self.target,
                }
            )
            if self.pinned_target_id and selected != self.pinned_target_id:
                self.pinned_target_id = selected
        await self.attach_to_target(self.target)

    async def rebind_session(self) -> None:
        identifier = self.pinned_target_id or target_id(self.target)
        if not identifier:
            await self.refresh_page_session()
            identifier = target_id(self.target)
        old_session = self.session_id
        if old_session:
            try:
                await self.send("Target.detachFromTarget", {"sessionId": old_session}, timeout=5.0)
            except RecorderError:
                pass
        await self.attach_to_target({"targetId": identifier, "id": identifier, "type": "page"})
        self.pinned_target_id = identifier
        self.main_frame_navigated = False
        await enable_page_domains(self)
        await reset_chromiumrl_tracing(self)
        if self.log_path is not None:
            append_jsonl(self.log_path, {"ts": utc_now(), "event": "session_rebound", "target_id": identifier})

    async def page_targets(self) -> list[dict[str, Any]]:
        """Return page targets, preferring /json/list order.

        Chrome/Android tab order from /json/list tends to track the browser UI
        better than Target.getTargets. Falling back keeps doctor/recording usable
        if the HTTP target list is unavailable.
        """
        result = await self.send("Target.getTargets")
        target_infos = [
            normalize_target_info(item)
            for item in result.get("targetInfos", [])
            if isinstance(item, dict)
            and item.get("type") == "page"
            and target_id(item)
            and not str(item.get("url", "")).startswith("devtools://")
        ]
        try:
            listed = await self.get_json("/json/list")
            if isinstance(listed, list) and target_infos:
                ordered: list[dict[str, Any]] = []
                remaining = list(target_infos)
                for listed_item in listed:
                    if not isinstance(listed_item, dict) or listed_item.get("type") != "page":
                        continue
                    listed_url = str(listed_item.get("url", ""))
                    listed_title = str(listed_item.get("title", ""))
                    match_index = next(
                        (
                            index
                            for index, candidate in enumerate(remaining)
                            if str(candidate.get("url", "")) == listed_url
                            and str(candidate.get("title", "")) == listed_title
                        ),
                        None,
                    )
                    if match_index is None:
                        match_index = next(
                            (
                                index
                                for index, candidate in enumerate(remaining)
                                if str(candidate.get("url", "")) == listed_url
                            ),
                            None,
                        )
                    if match_index is not None:
                        ordered.append(remaining.pop(match_index))
                ordered.extend(remaining)
                if ordered:
                    return ordered
        except RecorderError:
            pass
        return target_infos

    async def attach_to_target(self, target: dict[str, Any]) -> None:
        normalized = normalize_target_info(target)
        identifier = target_id(normalized)
        if not identifier:
            raise RecorderError(f"target has no id: {target}")
        attached = await self.send(
            "Target.attachToTarget",
            {"targetId": identifier, "flatten": True},
        )
        self.session_id = str(attached.get("sessionId", ""))
        if not self.session_id:
            raise RecorderError("Target.attachToTarget returned no sessionId")
        self.target = normalized

    async def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        use_session: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        if self.ws is None or self.ws.closed:
            raise RecorderError("CDP WebSocket is not connected")
        if self.renderer_crashed is not None and method != "Target.getTargets":
            raise RecorderError(f"renderer target crashed: {self.renderer_crashed}")
        self.message_id += 1
        request_id = self.message_id
        payload: dict[str, Any] = {"id": request_id, "method": method, "params": params or {}}
        if use_session:
            if not self.session_id:
                raise RecorderError(f"{method} requires an attached page session")
            payload["sessionId"] = self.session_id

        deadline = timeout if timeout is not None else self.command_timeout
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self.pending[request_id] = (method, future)
        await self.ws.send_json(payload)
        try:
            return await asyncio.wait_for(future, timeout=deadline)
        except asyncio.TimeoutError as error:
            self.pending.pop(request_id, None)
            raise RecorderError(f"CDP command {method} timed out after {deadline:.1f}s") from error

    async def _reader_loop(self) -> None:
        if self.ws is None:
            return
        while True:
            message = await self.ws.receive()
            if message.type == aiohttp.WSMsgType.TEXT:
                response = json.loads(message.data)
                request_id = response.get("id")
                if isinstance(request_id, int):
                    item = self.pending.pop(request_id, None)
                    if item is None:
                        continue
                    method, future = item
                    if future.done():
                        continue
                    if "error" in response:
                        future.set_exception(CDPCommandError(method, response["error"]))
                    else:
                        result = response.get("result", {})
                        future.set_result(result if isinstance(result, dict) else {"value": result})
                    continue
                await self._handle_event(response)
                continue
            if message.type in {
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            }:
                error = RecorderError("CDP WebSocket closed")
                for _, future in list(self.pending.values()):
                    if not future.done():
                        future.set_exception(error)
                self.pending.clear()
                return

    async def _handle_event(self, message: dict[str, Any]) -> None:
        method = str(message.get("method", ""))
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if method in {
            "Page.javascriptDialogOpening",
            "Page.frameNavigated",
            "Target.targetCreated",
            "Target.targetDestroyed",
            "Inspector.targetCrashed",
        }:
            event = {"timestamp": utc_now(), "event": method, "params": params}
            self.event_log.append(event)
            if self.log_path is not None:
                append_jsonl(self.log_path, {"ts": event["timestamp"], "event": method, "params": params})
        if method == "Page.frameNavigated":
            frame = params.get("frame") if isinstance(params, dict) else {}
            if isinstance(frame, dict) and frame.get("parentId") is None:
                self.main_frame_navigated = True
                if self.log_path is not None:
                    append_jsonl(self.log_path, {"ts": utc_now(), "event": "main_frame_navigated", "url": frame.get("url")})
        if method == "Page.javascriptDialogOpening":
            asyncio.create_task(self._dismiss_javascript_dialog())
        elif method == "Inspector.targetCrashed":
            self.renderer_crashed = {"timestamp": utc_now(), "params": params}
            error = RecorderError(f"renderer target crashed: {params}")
            for _, future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(error)
            self.pending.clear()

    async def _dismiss_javascript_dialog(self) -> None:
        try:
            await self.send("Page.handleJavaScriptDialog", {"accept": True}, use_session=True, timeout=2.0)
            event = {"timestamp": utc_now(), "event": "javascript_dialog_dismissed"}
            self.event_log.append(event)
            if self.log_path is not None:
                append_jsonl(self.log_path, {"ts": event["timestamp"], "event": "javascript_dialog_dismissed"})
        except Exception as error:
            self.event_log.append(
                {"timestamp": utc_now(), "event": "javascript_dialog_dismiss_failed", "error": str(error)}
            )


async def timed_command(
    cdp: CDPConnection,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    required: bool,
    label: str | None = None,
    timeout: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prefix = f"{label}: " if label else ""
    started = time.perf_counter()
    print(f"{prefix}{method} ...", flush=True)
    try:
        if method.startswith("ChromiumRL.") and method not in {"ChromiumRL.enable", "ChromiumRL.disable"}:
            result = await chromiumrl_call(cdp, method, params or {}, timeout=timeout or cdp.command_timeout, label=label or "")
        else:
            result = await cdp.send(method, params, use_session=True, timeout=timeout)
        timing = {"ok": True, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
        print(f"{prefix}{method} ok in {timing['elapsed_ms']:.1f}ms", flush=True)
        return result, timing
    except Exception as error:
        timing = {
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": str(error),
        }
        print(f"{prefix}{method} failed after {timing['elapsed_ms']:.1f}ms: {error}", flush=True)
        if required:
            raise
        return {}, timing


def command_entry(params: dict[str, Any], timing: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "timing": timing, "result": result}


@dataclass
class CapturedState:
    directory: Path
    chromiumrl_dom: dict[str, Any]
    page_state: dict[str, Any]
    index: dict[str, Any]
    agent_observation: dict[str, Any]
    degraded: bool = False
    capture_notes: list[str] | None = None
    observation_source: str = "chromiumrl"
    dom_captured: bool = False
    frame_tree: dict[str, Any] | None = None
    form_enrichment: dict[str, Any] | None = None


@dataclass(frozen=True)
class ScreenshotConfig:
    source: str
    container: str
    adb_serial: str
    timeout_seconds: float
    format: str = "jpeg"
    quality: int = 70


async def activate_current_target(cdp: CDPConnection, *, label: str = "") -> dict[str, Any]:
    identifier = cdp.pinned_target_id or target_id(cdp.target)
    result = {"ok": True, "target_id": identifier, "errors": []}
    if not identifier:
        result["ok"] = False
        result["errors"].append("no target id")
        log_event(cdp, "activate_failed", label=label, result=result)
        return result
    try:
        await cdp.send("Target.activateTarget", {"targetId": identifier}, timeout=TIMEOUT_SIGNAL)
    except Exception as error:
        result["ok"] = False
        result["errors"].append(f"Target.activateTarget: {error}")
    try:
        await cdp.send("Page.bringToFront", {}, use_session=True, timeout=TIMEOUT_SIGNAL)
    except Exception as error:
        result["ok"] = False
        result["errors"].append(f"Page.bringToFront: {error}")
    if not result["ok"]:
        log_event(cdp, "activate_failed", label=label, result=result)
    return result


async def enable_page_domains(cdp: CDPConnection) -> dict[str, Any]:
    results: dict[str, Any] = {}
    if getattr(cdp, "enable_runtime_domain", False):
        try:
            await cdp.send("Runtime.enable", {}, use_session=True, timeout=5.0)
            results["Runtime.enable"] = {"ok": True}
        except Exception as error:
            results["Runtime.enable"] = {"ok": False, "error": str(error)}
            log_event(cdp, "warning", warning="Runtime.enable failed", error=str(error))
    else:
        results["Runtime.enable"] = {"ok": True, "skipped": True, "reason": "default disabled; Runtime.evaluate works without Runtime.enable"}
    try:
        await cdp.send("Page.enable", {}, use_session=True, timeout=5.0)
        results["Page.enable"] = {"ok": True}
    except Exception as error:
        results["Page.enable"] = {"ok": False, "error": str(error)}
        log_event(cdp, "warning", warning="Page.enable failed", error=str(error))
    return results


PAGE_STATE_EXPRESSION = r"""
(() => {
  const de = document.documentElement || {};
  const body = document.body || {};
  const viewportHeight = window.innerHeight || de.clientHeight || 0;
  const viewportWidth = window.innerWidth || de.clientWidth || 0;
  const scrollHeight = Math.max(de.scrollHeight || 0, body.scrollHeight || 0, de.clientHeight || 0);
  const scrollWidth = Math.max(de.scrollWidth || 0, body.scrollWidth || 0, de.clientWidth || 0);
  return {
    url: location.href,
    title: document.title,
    readyState: document.readyState,
    viewport: {
      innerWidth: viewportWidth, innerHeight: viewportHeight,
      scrollX: window.scrollX || 0, scrollY: window.scrollY || 0,
      scrollWidth, scrollHeight,
      canScrollDown: (window.scrollY || 0) + viewportHeight < scrollHeight - 1,
      canScrollUp: (window.scrollY || 0) > 0
    },
    nodeCount: document.querySelectorAll('*').length
  };
})()
"""


async def probe_renderer_responsive(cdp: CDPConnection, *, timeout: float = 3.0) -> bool:
    try:
        await cdp.send(
            "Runtime.evaluate",
            {"expression": "1", "returnByValue": True, "awaitPromise": False},
            use_session=True,
            timeout=timeout,
        )
        return True
    except Exception as error:
        cdp.renderer_wedged = True
        log_event(cdp, "renderer_wedged", error=str(error), probe="Runtime.evaluate:1", timeout=timeout)
        return False


async def chromiumrl_call(
    cdp: CDPConnection,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float,
    label: str = "",
) -> dict[str, Any]:
    for attempt in (1, 2):
        try:
            return await cdp.send(method, params or {}, use_session=True, timeout=timeout)
        except RecorderError as error:
            log_event(cdp, "chromiumrl_timeout", method=method, attempt=attempt, label=label, error=str(error))
            if not await probe_renderer_responsive(cdp, timeout=3.0):
                log_event(cdp, "chromiumrl_unavailable", method=method, label=label, error=str(error), renderer_wedged=True)
                raise ChromiumRLUnavailable(f"renderer_unresponsive during {method}: {error}") from error
            if attempt == 1:
                try:
                    await cdp.rebind_session()
                    continue
                except RecorderError as rebind_error:
                    log_event(cdp, "chromiumrl_rebind_failed", method=method, error=str(rebind_error))
            log_event(cdp, "chromiumrl_unavailable", method=method, label=label, error=str(error), renderer_wedged=False)
            raise ChromiumRLUnavailable(f"{method} unavailable after rebind: {error}") from error
    raise ChromiumRLUnavailable(f"{method} unavailable")


async def reset_chromiumrl_tracing(cdp: CDPConnection, *, full_tracing: bool = False) -> dict[str, Any]:
    try:
        await cdp.send("ChromiumRL.disable", {}, use_session=True, timeout=5.0)
    except RecorderError:
        pass
    params = {
        "captureTouchTraces": True,
        "captureLayoutTimings": bool(full_tracing),
        "captureCLSAttribution": bool(full_tracing),
        "captureCompositorLayers": bool(full_tracing),
    }
    result = await cdp.send("ChromiumRL.enable", params, use_session=True, timeout=5.0)
    trace_session_id = str(result.get("sessionId", "")).strip()
    if not trace_session_id:
        raise RecorderError(f"ChromiumRL.enable returned no sessionId: {result}")
    return result


JS_OBSERVATION_EXPRESSION = r"""
(() => {
  const t0 = performance.now();
  const SEL = 'a[href],button,input,select,textarea,option,summary,[role=button],[role=link],' +
              '[role=checkbox],[role=radio],[role=tab],[role=menuitem],[role=combobox],' +
              '[role=searchbox],[role=textbox],[onclick],[tabindex]:not([tabindex="-1"]),' +
              '[contenteditable=""],[contenteditable=true]';
  const vw = innerWidth, vh = innerHeight;
  const xpath = (el) => {
    const parts = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling)
        if (s.tagName === n.tagName) i++;
      parts.unshift(n.tagName.toLowerCase() + '[' + i + ']');
    }
    return '/' + parts.join('/');
  };
  const collect = (root, ox = 0, oy = 0) => {
    const out = [];
    for (const el of root.querySelectorAll(SEL)) {
      if (performance.now() - t0 > 1200) return {out, truncated: true};
      const tag = el.tagName.toLowerCase();
      const anchor = tag === 'option' && el.parentElement ? el.parentElement : el;
      const r = anchor.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const cs = getComputedStyle(anchor);
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
      if (el.disabled || el.getAttribute('aria-hidden') === 'true') continue;
      const labelText = (() => {
        if (el.labels && el.labels.length) return Array.from(el.labels).map(l => l.innerText || '').join(' ');
        const closest = el.closest && el.closest('label');
        if (closest) return closest.innerText || '';
        if ((el.type === 'checkbox' || el.type === 'radio') && el.nextSibling) return el.nextSibling.textContent || '';
        return '';
      })();
      const name = (el.getAttribute('aria-label') || labelText || el.innerText ||
                    (tag === 'option' ? el.textContent : '') || el.placeholder || el.title || el.alt ||
                    (tag !== 'input' || !['checkbox','radio'].includes(String(el.type || '').toLowerCase()) ? el.value : '') || '').replace(/\s+/g,' ').trim();
      const cx = ox + r.left + r.width / 2, cy = oy + r.top + r.height / 2;
      const item = {
        tag, role: el.getAttribute('role') || '',
        accessibleName: name.slice(0, 120), href: el.getAttribute('href') || '',
        value: (el.value || '').toString().slice(0, 80), xpath: xpath(el),
        bounds: { x: ox + r.left, y: oy + r.top, width: r.width, height: r.height },
        centerX: cx, centerY: cy,
        isInViewport: cy >= 0 && cy <= vh && cx >= 0 && cx <= vw,
        isVisible: true, isHitTestable: tag !== 'option'
      };
      if ('checked' in el) item.checked = !!el.checked;
      if ('selected' in el) item.selected = !!el.selected;
      out.push(item);
      if (out.length >= 300) return {out, truncated: true};
    }
    return {out, truncated: false};
  };
  let result = collect(document);
  const out = result.out;
  let truncated = result.truncated;
  for (const iframe of document.querySelectorAll('iframe')) {
    if (performance.now() - t0 > 1200 || out.length >= 300) { truncated = true; break; }
    try {
      if (!iframe.contentDocument) continue;
      const r = iframe.getBoundingClientRect();
      const child = collect(iframe.contentDocument, r.left, r.top);
      out.push(...child.out.slice(0, 300 - out.length));
      truncated = truncated || child.truncated;
    } catch (error) {}
  }
  return { url: location.href, title: document.title,
           scroll: { x: scrollX, y: scrollY, scrollTop: scrollY,
                     maxY: Math.max(0, document.documentElement.scrollHeight - vh),
                     pageHeight: document.documentElement.scrollHeight,
                     viewportWidth: vw, viewportHeight: vh,
                     canScrollDown: scrollY + vh < document.documentElement.scrollHeight - 1,
                     canScrollUp: scrollY > 0 },
           viewport: { width: vw, height: vh }, elements: out, truncated, source: 'js_fallback' };
})()
"""


async def collect_js_observation(cdp: CDPConnection, label: str = "") -> dict[str, Any]:
    runtime, timing = await timed_command(
        cdp,
        "Runtime.evaluate",
        {"expression": JS_OBSERVATION_EXPRESSION, "returnByValue": True, "awaitPromise": False},
        required=False,
        label=label,
        timeout=TIMEOUT_EVALUATE,
    )
    observation = runtime.get("result", {}).get("value", {}) if isinstance(runtime, dict) else {}
    if not isinstance(observation, dict):
        observation = {"url": "", "title": "", "elements": [], "source": "js_fallback", "error": "invalid Runtime.evaluate result"}
    return command_entry({}, timing, {"observation": observation})


async def collect_agent_observation(
    cdp: CDPConnection,
    directory: Path,
    *,
    source: str = "auto",
    label: str = "",
    page_state: dict[str, Any] | None = None,
    observation_max_elements: int | None = None,
) -> dict[str, Any]:
    page_state = page_state or {}
    chromiumrl_params: dict[str, Any] = {}
    if observation_max_elements and observation_max_elements > 0:
        chromiumrl_params = {
            "maxElements": int(observation_max_elements),
            "maxInteractiveElements": int(observation_max_elements),
        }
    if source == "js":
        payload = await collect_js_observation(cdp, label=label or directory.name)
        payload["source"] = "js_fallback"
        trim_observation_context(payload)
        write_json_compact(directory / "chromiumrl_agent_observation.json", payload)
        return payload

    def obs_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return observation_payload(payload)

    async def js_payload(reason: str) -> dict[str, Any]:
        log_event(cdp, "observation_fallback", reason=reason, fallback="js")
        payload = await collect_js_observation(cdp, label=label or directory.name)
        payload["source"] = "js_fallback"
        return payload

    if source == "cross_check":
        chromiumrl_payload: dict[str, Any] | None = None
        chromiumrl_error = ""
        try:
            value = await chromiumrl_call(cdp, "ChromiumRL.getAgentObservation", chromiumrl_params, timeout=TIMEOUT_OBSERVATION, label=label or directory.name)
            chromiumrl_payload = command_entry(chromiumrl_params, {"ok": True, "elapsed_ms": 0}, value)
            chromiumrl_payload["source"] = "chromiumrl"
        except Exception as error:
            chromiumrl_error = str(error)
        js = await collect_js_observation(cdp, label=label or directory.name)
        js["source"] = "js_fallback"
        cr_obs = obs_from_payload(chromiumrl_payload or {})
        js_obs = obs_from_payload(js)
        log_event(
            cdp,
            "observation_cross_check",
            label=label,
            url=(page_state.get("url") or cr_obs.get("url") or js_obs.get("url")),
            chromiumrl_count=len(cr_obs.get("elements", []) or []),
            chromiumrl_labelled=labelled_element_count(cr_obs),
            js_count=len(js_obs.get("elements", []) or []),
            js_labelled=labelled_element_count(js_obs),
            chromiumrl_error=chromiumrl_error,
        )
        payload = chromiumrl_payload or js
        trim_observation_context(payload)
        write_json_compact(directory / "chromiumrl_agent_observation.json", payload)
        return payload

    try:
        value = await chromiumrl_call(cdp, "ChromiumRL.getAgentObservation", chromiumrl_params, timeout=TIMEOUT_OBSERVATION, label=label or directory.name)
        payload = command_entry(chromiumrl_params, {"ok": True, "elapsed_ms": 0}, value)
        payload["source"] = "chromiumrl"
        obs = obs_from_payload(payload)
        reason = observation_is_implausible(obs, page_state)
        if reason and source == "auto":
            js = await js_payload(reason)
            js_obs = obs_from_payload(js)
            cr_labelled = labelled_element_count(obs)
            js_labelled = labelled_element_count(js_obs)
            winner = "js_fallback" if js_labelled > cr_labelled else "chromiumrl"
            log_event(
                cdp,
                "observation_implausible",
                reason=reason,
                label=label,
                chromiumrl_count=len(obs.get("elements", []) or []),
                chromiumrl_labelled=cr_labelled,
                js_count=len(js_obs.get("elements", []) or []),
                js_labelled=js_labelled,
                winner=winner,
            )
            payload = js if winner == "js_fallback" else payload
        elif reason:
            log_event(cdp, "observation_implausible", reason=reason, label=label, source=source, fallback="not_allowed")
        trim_observation_context(payload)
        write_json_compact(directory / "chromiumrl_agent_observation.json", payload)
        return payload
    except ChromiumRLUnavailable as error:
        if source == "chromiumrl":
            raise
        payload = await js_payload(str(error))
        trim_observation_context(payload)
        write_json_compact(directory / "chromiumrl_agent_observation.json", payload)
        return payload


FORM_CONTROL_STATE_EXPRESSION = r"""
(() => {
  const xpath = (el) => {
    const parts = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling)
        if (s.tagName === n.tagName) i++;
      parts.unshift(n.tagName.toLowerCase() + '[' + i + ']');
    }
    return '/' + parts.join('/');
  };
  const out = [];
  for (const el of document.querySelectorAll('input,textarea,select,option')) {
    const item = {tag: el.tagName.toLowerCase(), selector: '', xpath: xpath(el)};
    try { item.selector = el.id ? '#' + CSS.escape(el.id) : ''; } catch (e) {}
    if ('value' in el) item.value = String(el.value || '');
    if ('checked' in el) item.checked = !!el.checked;
    if ('selected' in el) item.selected = !!el.selected;
    out.push(item);
  }
  return out;
})()
"""


async def collect_form_control_state(cdp: CDPConnection, *, label: str = "") -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    runtime, timing = await timed_command(
        cdp,
        "Runtime.evaluate",
        {"expression": FORM_CONTROL_STATE_EXPRESSION, "returnByValue": True, "awaitPromise": False},
        required=False,
        label=label,
        timeout=TIMEOUT_EVALUATE,
    )
    value = runtime.get("result", {}).get("value", []) if isinstance(runtime, dict) else []
    by_key: dict[str, dict[str, Any]] = {}
    meta: dict[str, Any] = {
        "attempted": True,
        "ok": bool(timing.get("ok")),
        "error": timing.get("error", ""),
        "controls_seen": 0,
        "controls_enriched": 0,
    }
    if isinstance(value, list):
        meta["controls_seen"] = len(value)
        for item in value:
            if not isinstance(item, dict):
                continue
            for key_name in ("selector", "xpath"):
                key = item.get(key_name)
                if isinstance(key, str) and key.strip():
                    by_key[f"{key_name}:{key.strip()}"] = item
    elif meta["ok"]:
        meta["ok"] = False
        meta["error"] = "Runtime.evaluate returned a non-list form state"
    return by_key, meta


def _prop_value(value: Any, *, redacted: bool = False) -> dict[str, Any]:
    if redacted:
        text = str(value or "")
        return {"v": "<REDACTED>", "src": "prop", "redacted": True, "filled": bool(text), "length": len(text)}
    return {"v": str(value).lower() if isinstance(value, bool) else str(value), "src": "prop"}


def enrich_dom_with_form_state(dom_state: dict[str, Any], form_state: dict[str, dict[str, Any]]) -> int:
    enriched = 0
    for node in dom_state.get("nodes", []) if isinstance(dom_state.get("nodes"), list) else []:
        if not isinstance(node, dict):
            continue
        candidates = []
        if isinstance(node.get("cssSelector"), str) and node.get("cssSelector").strip():
            candidates.append("selector:" + node.get("cssSelector").strip())
        if isinstance(node.get("xpath"), str) and node.get("xpath").strip():
            candidates.append("xpath:" + node.get("xpath").strip())
        match = next((form_state[k] for k in candidates if k in form_state), None)
        if not match:
            continue
        attrs = node.get("_semantic_attrs_override") if isinstance(node.get("_semantic_attrs_override"), dict) else semantic_attrs(node.get("attributes"))
        touched = False
        sensitive_control = any(SENSITIVE_FIELD_RE.search(str(attrs.get(k, ""))) for k in ("name", "id", "type", "autocomplete"))
        for key in ("value", "checked", "selected"):
            if key in match:
                attrs[key] = _prop_value(match[key], redacted=(key == "value" and sensitive_control))
                touched = True
        if touched:
            node["_semantic_attrs_override"] = attrs
            enriched += 1
    return enriched



def _frame_tree_root(frame_tree_result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(frame_tree_result, dict):
        return {}
    root = frame_tree_result.get("frameTree")
    if isinstance(root, dict):
        return root
    result = frame_tree_result.get("result")
    if isinstance(result, dict) and isinstance(result.get("frameTree"), dict):
        return result["frameTree"]
    return {}


def walk_frame_tree(frame_tree_result: dict[str, Any]) -> list[dict[str, Any]]:
    root = _frame_tree_root(frame_tree_result)
    frames: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], depth: int) -> None:
        frame = node.get("frame") if isinstance(node.get("frame"), dict) else {}
        if frame:
            item = dict(frame)
            item["depth"] = depth
            frames.append(item)
        for child in node.get("childFrames") or []:
            if isinstance(child, dict):
                visit(child, depth + 1)

    if root:
        visit(root, 0)
    return frames


def main_frame_info(frame_tree_result: dict[str, Any]) -> dict[str, Any]:
    for frame in walk_frame_tree(frame_tree_result):
        if frame.get("depth") == 0:
            return frame
    return {}


def frame_coverage_from_tree(frame_tree_result: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any]:
    frames = walk_frame_tree(frame_tree_result)
    child_frames = [f for f in frames if f.get("depth", 0) > 0]
    js_iframe_frames = set()
    if isinstance(projection, dict):
        for node in projection.get("nodes", []) or []:
            if isinstance(node, dict) and node.get("source") == "js_iframe" and node.get("frame"):
                js_iframe_frames.add(str(node.get("frame")))
    traversed = 1 + len(js_iframe_frames) if frames else len(js_iframe_frames)
    coverage = "main_frame_plus_same_origin_iframes" if js_iframe_frames else "main_frame_only"
    return {
        "count": len(frames),
        "child_frames": len(child_frames),
        "traversed": traversed,
        "coverage": coverage,
        "child_frame_urls": [str(f.get("url") or "") for f in child_frames if f.get("url")],
        "same_origin_iframe_sources": sorted(js_iframe_frames),
        "shadow_dom": "none",
    }


JS_IFRAME_DOM_PROJECTION_EXPRESSION = r"""
(() => {
  const t0 = performance.now();
  const SEM = new Set(['id','href','src','value','checked','selected','disabled','readonly','required','type','name','placeholder','title','alt','role','data-testid']);
  const STATE = /(?:^|[-_])(active|current|selected|checked|open|expanded|collapsed|disabled|error|invalid|success|hidden|show|star|rating)(?:$|[-_])/i;
  const styleKeys = ['display','visibility','opacity','color','backgroundColor','textDecoration'];
  const xpath = (el) => {
    const parts = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling)
        if (s.tagName === n.tagName) i++;
      parts.unshift(n.tagName.toLowerCase() + '[' + i + ']');
    }
    return '/' + parts.join('/');
  };
  const attrsFor = (el) => {
    const attrs = {};
    for (const attr of Array.from(el.attributes || [])) {
      const name = attr.name.toLowerCase();
      if (SEM.has(name) || name.startsWith('aria-')) attrs[name] = attr.value;
      else if (name === 'class') {
        const kept = attr.value.split(/\s+/).filter(t => STATE.test(t));
        if (kept.length) attrs.class = Array.from(new Set(kept)).join(' ');
      }
    }
    if ('value' in el && el.value !== '') attrs.value = {v:String(el.value), src:'prop'};
    if ('checked' in el) attrs.checked = {v:String(!!el.checked), src:'prop'};
    if ('selected' in el) attrs.selected = {v:String(!!el.selected), src:'prop'};
    return attrs;
  };
  const out = [];
  let truncated = false;
  let frameIndex = 0;
  for (const iframe of document.querySelectorAll('iframe')) {
    frameIndex += 1;
    if (performance.now() - t0 > 1200 || out.length >= 500) { truncated = true; break; }
    let doc;
    try { doc = iframe.contentDocument; } catch (e) { continue; }
    if (!doc || !doc.documentElement) continue;
    const frameRect = iframe.getBoundingClientRect();
    const frameKey = iframe.getAttribute('src') || (doc.location && doc.location.href) || ('iframe[' + frameIndex + ']');
    const frameId = frameKey;
    const nodes = Array.from(doc.querySelectorAll('*'));
    const keyOf = (el) => 'frame:' + frameId + ':' + xpath(el);
    for (const el of nodes) {
      if (performance.now() - t0 > 1200 || out.length >= 500) { truncated = true; break; }
      const tag = el.tagName.toLowerCase();
      if (['script','style','noscript','template'].includes(tag)) continue;
      const text = (el.textContent || '').replace(/\s+/g,' ').trim().slice(0,200);
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      const parent = el.parentElement ? keyOf(el.parentElement) : '';
      const style = {};
      for (const k of styleKeys) if (cs[k]) style[k] = cs[k];
      out.push({
        k: keyOf(el), parent, tag, text, attrs: attrsFor(el),
        vis: !!(r.width && r.height && cs.display !== 'none' && cs.visibility !== 'hidden' && +cs.opacity !== 0),
        vp: frameRect.bottom + r.bottom > 0 && frameRect.top + r.top < innerHeight,
        style, frame: frameId, source: 'js_iframe'
      });
    }
  }
  return {nodes: out, truncated};
})()
"""


async def collect_js_iframe_projection(cdp: CDPConnection, *, label: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    runtime, timing = await timed_command(
        cdp,
        "Runtime.evaluate",
        {"expression": JS_IFRAME_DOM_PROJECTION_EXPRESSION, "returnByValue": True, "awaitPromise": False},
        required=False,
        label=label,
        timeout=TIMEOUT_EVALUATE,
    )
    value = runtime.get("result", {}).get("value", {}) if isinstance(runtime, dict) else {}
    nodes = value.get("nodes", []) if isinstance(value, dict) else []
    if not isinstance(nodes, list):
        nodes = []
    meta = {"attempted": True, "ok": bool(timing.get("ok")), "error": timing.get("error", ""), "nodes": len(nodes), "truncated": bool(value.get("truncated")) if isinstance(value, dict) else False}
    return [n for n in nodes if isinstance(n, dict)], meta


async def capture_screenshot_best_effort(cdp: CDPConnection, directory: Path, config: ScreenshotConfig) -> dict[str, Any]:
    if config.source == "none":
        write_json(directory / "screenshot_skipped.json", {"ok": True, "source": "none"})
        return {"ok": True, "source": "none", "artifact": "screenshot_skipped.json"}
    fmt = getattr(config, "format", "jpeg") or "jpeg"
    if fmt == "jpg":
        fmt = "jpeg"
    extension = "jpg" if fmt == "jpeg" else fmt
    params: dict[str, Any] = {"format": fmt, "fromSurface": True, "captureBeyondViewport": False}
    if fmt in {"jpeg", "webp"}:
        quality = int(getattr(config, "quality", 70) or 70)
        params["quality"] = max(1, min(100, quality))
    attempts: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        screenshot = await cdp.send("Page.captureScreenshot", params, use_session=True, timeout=TIMEOUT_SCREENSHOT)
        encoded = screenshot.get("data")
        if isinstance(encoded, str) and encoded:
            data = base64.b64decode(encoded, validate=True)
            artifact = f"screenshot.{extension}"
            (directory / artifact).write_bytes(data)
            return {"source": "cdp", "ok": True, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "artifact": artifact, "bytes": len(data), "params": params}
        attempts.append({"source": "cdp", "ok": False, "params": params, "error": "no screenshot data"})
    except Exception as error:
        attempts.append({"source": "cdp", "ok": False, "params": params, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "error": str(error)})
    write_json(directory / "screenshot_error.json", {"ok": False, "attempts": attempts})
    return {"ok": False, "attempts": attempts, "artifact": "screenshot_error.json"}


async def capture_state(
    cdp: CDPConnection,
    directory: Path,
    label: str,
    screenshot_config: ScreenshotConfig,
    *,
    capture_all_targets: bool = False,
    observation_source: str = "auto",
    write_dom: bool = False,
    dom_capture: str = "slim",
    observation_max_elements: int | None = None,
) -> CapturedState:
    directory.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    commands: dict[str, Any] = {}
    notes: list[str] = []
    degraded = False
    page_state: dict[str, Any] = {}
    chromiumrl_dom: dict[str, Any] = {}
    dom_captured = False
    frame_tree: dict[str, Any] = {}
    form_enrichment: dict[str, Any] = {"attempted": False, "ok": False, "error": "not_attempted", "controls_enriched": 0}

    commands["activate"] = await activate_current_target(cdp, label=label)

    runtime, commands["Runtime.evaluate"] = await timed_command(
        cdp,
        "Runtime.evaluate",
        {"expression": PAGE_STATE_EXPRESSION, "returnByValue": True, "awaitPromise": False},
        required=False,
        label=label,
        timeout=TIMEOUT_EVALUATE,
    )
    value = runtime.get("result", {}).get("value", {}) if isinstance(runtime, dict) else {}
    if isinstance(value, dict):
        page_state = value
    else:
        degraded = True
        notes.append("page_state_failed")
    write_json_compact(directory / "page_state.json", page_state)

    frame_tree, commands["Page.getFrameTree"] = await timed_command(cdp, "Page.getFrameTree", required=False, label=label, timeout=TIMEOUT_EVALUATE)
    if not isinstance(frame_tree, dict):
        frame_tree = {}

    commands["screenshot"] = await capture_screenshot_best_effort(cdp, directory, screenshot_config)
    if not commands["screenshot"].get("ok"):
        degraded = True
        notes.append("screenshot_failed")

    try:
        agent_observation = await collect_agent_observation(cdp, directory, source=observation_source, label=label, page_state=page_state, observation_max_elements=observation_max_elements)
    except Exception as error:
        degraded = True
        notes.append(f"observation_failed:{error}")
        agent_observation = {"source": "none", "result": {"observation": {"url": page_state.get("url", ""), "title": page_state.get("title", ""), "elements": []}}}
        write_json_compact(directory / "chromiumrl_agent_observation.json", agent_observation)
    commands["observation"] = {"ok": True, "source": agent_observation.get("source", "chromiumrl")}

    if write_dom and dom_capture != "none":
        try:
            save_dom = await chromiumrl_call(cdp, "ChromiumRL.saveDOMState", {}, timeout=TIMEOUT_DOM_CAPTURE, label=label)
            chromiumrl_dom = save_dom.get("state", {}) if isinstance(save_dom, dict) else {}
            if not isinstance(chromiumrl_dom, dict):
                chromiumrl_dom = {}
            try:
                form_state, form_enrichment = await collect_form_control_state(cdp, label=f"{label}:form_state")
                form_enrichment["controls_enriched"] = enrich_dom_with_form_state(chromiumrl_dom, form_state)
                commands["form_control_state"] = form_enrichment
            except Exception as form_error:
                form_enrichment = {"attempted": True, "ok": False, "error": str(form_error), "controls_enriched": 0}
                commands["form_control_state"] = form_enrichment
            try:
                iframe_nodes, iframe_meta = await collect_js_iframe_projection(cdp, label=f"{label}:iframe_dom")
                if iframe_nodes:
                    chromiumrl_dom["_extra_projected_nodes"] = iframe_nodes
                commands["js_iframe_dom"] = iframe_meta
            except Exception as iframe_error:
                commands["js_iframe_dom"] = {"attempted": True, "ok": False, "error": str(iframe_error), "nodes": 0}
            slim_dom = project_dom_state(chromiumrl_dom)
            write_json_gz(directory / "chromiumrl_dom_slim.json.gz", slim_dom)
            if dom_capture == "full":
                write_json_gz(directory / "chromiumrl_dom_raw.json.gz", chromiumrl_dom)
            dom_captured = True
            commands["ChromiumRL.saveDOMState"] = {"ok": True, "raw_nodes": len(chromiumrl_dom.get("nodes", []) or []), "slim_nodes": len(slim_dom.get("nodes", []) or []), "dom_capture": dom_capture}
        except Exception as error:
            degraded = True
            notes.append(f"dom_failed:{error}")
            commands["ChromiumRL.saveDOMState"] = {"ok": False, "error": str(error), "dom_capture": dom_capture}
            log_event(cdp, "capture_degraded", label=label, reason=str(error))

    index = {
        "schema_version": SCHEMA_VERSION,
        "label": label,
        "captured_at": started_at,
        "completed_at": utc_now(),
        "target": cdp.target,
        "page": page_state,
        "commands": commands,
        "degraded": degraded,
        "capture_notes": notes,
        "observation_source": agent_observation.get("source", "chromiumrl"),
        "dom_captured": dom_captured,
        "frame_tree": frame_tree,
        "frames": frame_coverage_from_tree(frame_tree, project_dom_state(chromiumrl_dom) if chromiumrl_dom else None),
        "form_enrichment": form_enrichment,
    }
    return CapturedState(directory, chromiumrl_dom, page_state, index, agent_observation, degraded, notes, agent_observation.get("source", "chromiumrl"), dom_captured, frame_tree, form_enrichment)


async def capture_state_with_recovery(
    cdp: CDPConnection,
    directory: Path,
    label: str,
    screenshot_config: ScreenshotConfig,
    *,
    capture_all_targets: bool = False,
    chromiumrl_full_tracing: bool = False,
    observation_source: str = "auto",
    write_dom: bool = False,
    dom_capture: str = "slim",
    observation_max_elements: int | None = None,
) -> CapturedState:
    if cdp.main_frame_navigated:
        try:
            await cdp.rebind_session()
        except RecorderError as error:
            log_event(cdp, "warning", message="session rebind failed before capture", error=str(error))
    return await capture_state(
        cdp,
        directory,
        label,
        screenshot_config,
        capture_all_targets=capture_all_targets,
        observation_source=observation_source,
        write_dom=write_dom,
        dom_capture=dom_capture,
        observation_max_elements=observation_max_elements,
    )


def action_name(action: Any) -> str:
    if not isinstance(action, dict):
        return ""
    name = action.get("action", action.get("action_type", ""))
    return str(name)


def action_thoughts(action: Any) -> str:
    if isinstance(action, dict):
        return str(action.get("thoughts") or action.get("thought") or "")
    return ""


def action_coordinate(action: Any) -> list[int] | None:
    if not isinstance(action, dict):
        return None
    raw = action.get("coordinate")
    if raw is None and "x" in action and "y" in action:
        raw = [action["x"], action["y"]]
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            return [int(round(float(raw[0]))), int(round(float(raw[1])))]
        except (TypeError, ValueError):
            return None
    return None


def viewport_center(page_state: dict[str, Any]) -> list[int] | None:
    viewport = page_state.get("viewport", {})
    if not isinstance(viewport, dict):
        return None
    width = viewport.get("innerWidth")
    height = viewport.get("innerHeight")
    try:
        return [int(round(float(width) / 2)), int(round(float(height) / 2))]
    except (TypeError, ValueError):
        return None


def node_at_coordinate(dom_state: dict[str, Any], coordinate: list[int] | None) -> dict[str, Any] | None:
    if not coordinate:
        return None
    x, y = coordinate
    best: dict[str, Any] | None = None
    best_area: float | None = None
    for node in dom_state.get("nodes", []):
        if not isinstance(node, dict) or not node.get("isVisible", True):
            continue
        bounds = node.get("bounds")
        if not isinstance(bounds, dict):
            continue
        try:
            left = float(bounds.get("x", 0))
            top = float(bounds.get("y", 0))
            width = float(bounds.get("width", 0))
            height = float(bounds.get("height", 0))
        except (TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue
        if left <= x <= left + width and top <= y <= top + height:
            area = width * height
            if best_area is None or area < best_area:
                best = node
                best_area = area
    return best


def first_visible_node(dom_state: dict[str, Any]) -> dict[str, Any] | None:
    for node in dom_state.get("nodes", []):
        if isinstance(node, dict) and node.get("isVisible", False) and isinstance(node.get("nodeId"), int):
            return node
    return None


def find_xy(value: Any) -> list[int] | None:
    if isinstance(value, dict):
        for key in ("coordinate", "point", "position"):
            candidate = value.get(key)
            if isinstance(candidate, (list, tuple)) and len(candidate) >= 2:
                try:
                    return [int(round(float(candidate[0]))), int(round(float(candidate[1])))]
                except (TypeError, ValueError):
                    pass
        for x_key, y_key in (
            ("x", "y"),
            ("clientX", "clientY"),
            ("pageX", "pageY"),
            ("screenX", "screenY"),
            ("viewportX", "viewportY"),
        ):
            if x_key in value and y_key in value:
                try:
                    return [int(round(float(value[x_key]))), int(round(float(value[y_key])))]
                except (TypeError, ValueError):
                    pass
        for nested in value.values():
            coordinate = find_xy(nested)
            if coordinate:
                return coordinate
    elif isinstance(value, list):
        for item in value:
            coordinate = find_xy(item)
            if coordinate:
                return coordinate
    return None


def latest_touch_coordinate(signals: dict[str, Any]) -> list[int] | None:
    command = signals.get("commands", {}).get("ChromiumRL.getTouchTraces", {})
    traces = command.get("result", {}).get("traces", [])
    if isinstance(traces, list):
        for trace in reversed(traces):
            coordinate = find_xy(trace)
            if coordinate:
                return coordinate
    return None


def observation_payload(state_or_payload: Any) -> dict[str, Any]:
    payload = getattr(state_or_payload, "agent_observation", state_or_payload)
    if not isinstance(payload, dict):
        return {}
    result = payload.get("result", {})
    if not isinstance(result, dict):
        return {}
    observation = result.get("observation", {})
    return observation if isinstance(observation, dict) else {}


def observation_elements(state_or_payload: Any) -> list[dict[str, Any]]:
    observation = observation_payload(state_or_payload)
    elements = observation.get("elements", [])
    return [item for item in elements if isinstance(item, dict)]


def element_label_text(element: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("text", "accessibleName", "name", "label", "placeholder", "value", "href"):
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(" ".join(value.split()))
    return " ".join(parts).strip()


def labelled_element_count(observation: dict[str, Any]) -> int:
    elements = observation.get("elements", []) if isinstance(observation, dict) else []
    if not isinstance(elements, list):
        return 0
    return sum(1 for element in elements if isinstance(element, dict) and element_label_text(element))


def trim_observation_context(payload: dict[str, Any], *, limit: int = 80) -> dict[str, Any]:
    observation = observation_payload(payload)
    elements = observation.get("elements", []) if isinstance(observation, dict) else []
    if not isinstance(elements, list):
        return payload
    for element in elements:
        if not isinstance(element, dict):
            continue
        context = element.get("context")
        if not isinstance(context, str) or not context.strip():
            continue
        label = element_label_text(element)
        norm_context = " ".join(context.split())
        norm_label = " ".join(label.split())
        if norm_label and norm_label.lower() in norm_context.lower() and len(norm_context) > len(norm_label):
            element.pop("context", None)
        elif len(norm_context) > limit:
            element["context"] = norm_context[:limit - 1] + "…"
        else:
            element["context"] = norm_context
    return payload


def observation_is_implausible(obs: dict[str, Any], page_state: dict[str, Any]) -> str | None:
    elements = obs.get("elements") or []
    url = (page_state.get("url") or obs.get("url") or "").strip()
    if url in ("", "about:blank") or url.startswith(("chrome://", "chrome-native://")):
        return None
    if not elements:
        return "zero_elements"
    viewport = page_state.get("viewport") if isinstance(page_state.get("viewport"), dict) else {}
    scroll_height = first_number(viewport.get("scrollHeight"), viewport.get("pageHeight"), viewport.get("height"), 0) or 0
    if len(elements) < 3 and scroll_height > 2000:
        return "too_few_elements_for_page_height"
    if all(not element_label_text(e) for e in elements if isinstance(e, dict)):
        return "no_labelled_elements"
    return None


def element_identity(element: dict[str, Any]) -> str:
    # diagnostics/v3/identity_stability_probe_output.json showed selector is
    # present and stable, while fingerprint collides (e.g. repeated Home links).
    # Prefer selector, use nodeId as tiebreaker/auditable fallback, and never
    # use fingerprint before structural identifiers.
    for key in ("selector", "nodeId", "backendNodeId", "xpath", "cssSelector", "href", "text", "accessibleName", "idx", "fingerprint"):
        value = element.get(key)
        if value not in (None, "", [], {}):
            return f"{key}:{str(value).strip()}"
    return "unknown:" + hashlib.sha1(json.dumps(element, sort_keys=True, default=str).encode()).hexdigest()[:12]


def compact_element(element: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("idx", "nodeId", "backendNodeId", "xpath", "cssSelector", "selector", "tag", "role", "accessibleName", "text", "context", "href", "value", "placeholder"):
        value = element.get(key)
        if value not in (None, "", [], {}):
            result[key] = value
    for key in ("centerX", "centerY"):
        if key in element:
            result[key] = element[key]
    bounds = element.get("bounds")
    if isinstance(bounds, dict):
        result["bounds"] = bounds
    return result


def text_set_from_elements(elements: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for element in elements:
        for key in ("text", "accessibleName", "context"):
            value = element.get(key)
            if isinstance(value, str):
                text = " ".join(value.split())
                if text:
                    values.add(text)
    return values


def element_at_coordinate_from_observation(state_or_payload: Any, coordinate: list[int] | None) -> dict[str, Any] | None:
    if not coordinate:
        return None
    x, y = coordinate
    best: dict[str, Any] | None = None
    best_area: float | None = None
    for element in observation_elements(state_or_payload):
        bounds = element.get("bounds")
        if not isinstance(bounds, dict):
            continue
        try:
            left = float(bounds.get("x", 0))
            top = float(bounds.get("y", 0))
            width = float(bounds.get("width", 0))
            height = float(bounds.get("height", 0))
        except (TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue
        if left <= x <= left + width and top <= y <= top + height:
            area = width * height
            if best_area is None or area < best_area:
                best = element
                best_area = area
    return best



SEMANTIC_ATTRS = {
    "id", "href", "src", "value", "checked", "selected", "disabled", "readonly", "required",
    "type", "name", "placeholder", "title", "alt", "role", "data-testid",
}
STATE_CLASS_RE = re.compile(r"(?:^|[-_])(active|current|selected|checked|open|expanded|collapsed|disabled|error|invalid|success|hidden|show|star|rating)(?:$|[-_])", re.I)
SENSITIVE_FIELD_RE = re.compile(r"csrf|token|secret|session|auth|password", re.I)
DIFF_STYLE_KEYS = ("display", "visibility", "opacity", "color", "backgroundColor", "textDecoration")
SKIP_DOM_TAGS = {"#comment", "script", "style", "noscript", "template"}
INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea", "summary", "option"}
INTERACTIVE_ROLES = {"button", "link", "checkbox", "radio", "tab", "menuitem", "combobox", "searchbox", "textbox", "option"}


def _attr_items(attributes: Any) -> list[tuple[str, str]]:
    if isinstance(attributes, dict):
        return [(str(k), str(v)) for k, v in attributes.items()]
    result: list[tuple[str, str]] = []
    if isinstance(attributes, list):
        for item in attributes:
            if isinstance(item, dict):
                name = item.get("name")
                value = item.get("value", "")
                if name not in (None, ""):
                    result.append((str(name), str(value)))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                result.append((str(item[0]), str(item[1])))
    return result


def semantic_attrs(attributes: Any) -> dict[str, Any]:
    kept: dict[str, Any] = {}
    class_tokens: list[str] = []
    for name, value in _attr_items(attributes):
        lname = name.lower()
        if lname in SEMANTIC_ATTRS or lname.startswith("aria-"):
            kept[lname] = value
        elif lname == "class":
            for token in str(value).split():
                if STATE_CLASS_RE.search(token):
                    class_tokens.append(token)
    if "value" in kept and any(SENSITIVE_FIELD_RE.search(str(kept.get(k, ""))) for k in ("name", "id", "type", "autocomplete")):
        kept["value"] = "<REDACTED>"
    if class_tokens:
        kept["class"] = " ".join(dict.fromkeys(class_tokens))
    return kept


def normalize_dom_text(value: Any, limit: int = 200) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def node_tag(node: dict[str, Any]) -> str:
    return str(node.get("tagName") or node.get("nodeName") or "").lower()


def _node_raw_key(node: dict[str, Any]) -> str:
    for key in ("stablePath", "cssSelector", "xpath"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def build_structural_paths(nodes: list[dict[str, Any]]) -> dict[Any, str]:
    by_id = {node.get("nodeId"): node for node in nodes if isinstance(node, dict) and node.get("nodeId") is not None}
    cache: dict[Any, str] = {}

    def segment(node: dict[str, Any]) -> str:
        tag = node_tag(node) or "node"
        sibling = node.get("siblingIndex")
        try:
            return f"{tag}[{int(sibling)}]"
        except Exception:
            return f"{tag}[]"

    def path_for(node: dict[str, Any]) -> str:
        node_id = node.get("nodeId")
        if node_id in cache:
            return cache[node_id]
        parent = by_id.get(node.get("parentId"))
        if parent is not None and parent is not node:
            value = path_for(parent).rstrip("/") + "/" + segment(node)
        else:
            value = "/" + segment(node)
        if node_id is not None:
            cache[node_id] = value
        return value

    return {node.get("nodeId"): path_for(node) for node in nodes if isinstance(node, dict)}


def dom_key_population(dom_state: dict[str, Any]) -> dict[str, Any]:
    nodes = [n for n in dom_state.get("nodes", []) if isinstance(n, dict)]
    total = len(nodes)
    fields = {}
    for key in ("stablePath", "cssSelector", "xpath"):
        count = sum(1 for n in nodes if isinstance(n.get(key), str) and n.get(key).strip())
        fields[key] = {"count": count, "rate": round(count / total, 4) if total else 0.0}
    return {"total_nodes": total, "fields": fields}


def project_dom_state(dom_state: dict[str, Any]) -> dict[str, Any]:
    if dom_state.get("method") == "slim_dom_projection":
        return dom_state
    raw_nodes = [n for n in dom_state.get("nodes", []) if isinstance(n, dict)]
    structural_paths = build_structural_paths(raw_nodes)
    projected: list[dict[str, Any]] = []
    key_counts: dict[str, int] = {}
    for node in raw_nodes:
        tag = node_tag(node)
        text = normalize_dom_text(node.get("textContent"))
        if tag in SKIP_DOM_TAGS:
            continue
        if tag == "#text" and not text:
            continue
        raw_key = _node_raw_key(node) or structural_paths.get(node.get("nodeId"), "")
        if not raw_key:
            raw_key = f"/{tag}[{node.get('parentId','')}/{node.get('siblingIndex','')}/{node.get('nodeId','')}]"
        count = key_counts.get(raw_key, 0)
        key_counts[raw_key] = count + 1
        key = raw_key if count == 0 else f"{raw_key}#{count+1}"
        attrs = node.get("_semantic_attrs_override") if isinstance(node.get("_semantic_attrs_override"), dict) else semantic_attrs(node.get("attributes"))
        style_src = node.get("keyStyles") if isinstance(node.get("keyStyles"), dict) else {}
        style = {k: style_src.get(k) for k in DIFF_STYLE_KEYS if style_src.get(k) not in (None, "")}
        parent_id = node.get("parentId")
        parent_raw = ""
        if parent_id is not None:
            parent_node = next((n for n in raw_nodes if n.get("nodeId") == parent_id), None)
            if parent_node is not None:
                parent_raw = _node_raw_key(parent_node) or structural_paths.get(parent_id, "")
                parent_count = key_counts.get(parent_raw, 0)
                # Parent is usually already seen in document order. If duplicate suffix was needed,
                # subtree collapse still works for normal unique structural paths.
        projected.append({
            "k": key,
            "parent": parent_raw,
            "tag": tag,
            "text": text,
            "attrs": attrs,
            "vis": bool(node.get("isVisible")),
            "vp": bool(node.get("isInViewport")),
            "style": style,
            "nodeId": node.get("nodeId"),
            "parentId": parent_id,
            "siblingIndex": node.get("siblingIndex"),
        })
    for extra in dom_state.get("_extra_projected_nodes", []) if isinstance(dom_state.get("_extra_projected_nodes"), list) else []:
        if isinstance(extra, dict) and extra.get("k"):
            projected.append(dict(extra))
    return {
        "schema_version": SCHEMA_VERSION,
        "method": "slim_dom_projection",
        "url": dom_state.get("url", ""),
        "title": dom_state.get("title", ""),
        "viewport": dom_state.get("viewport", {}),
        "key_population": dom_key_population(dom_state),
        "nodes": projected,
    }


def _is_interactive_projected(node: dict[str, Any]) -> bool:
    tag = str(node.get("tag") or "").lower()
    attrs = node.get("attrs") if isinstance(node.get("attrs"), dict) else {}
    role = str(attrs.get("role") or "").lower()
    return tag in INTERACTIVE_TAGS or role in INTERACTIVE_ROLES or any(k in attrs for k in ("checked", "selected", "disabled", "value"))


def _children_by_parent(nodes_by_key: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    children: dict[str, list[dict[str, Any]]] = {}
    for node in nodes_by_key.values():
        parent = str(node.get("parent") or "")
        if parent:
            children.setdefault(parent, []).append(node)
    return children


def _subtree_nodes(root: dict[str, Any], children: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    stack = list(children.get(str(root.get("k")), []))
    while stack:
        node = stack.pop(0)
        out.append(node)
        stack[0:0] = children.get(str(node.get("k")), [])
    return out


def collapse_subtree_entry(root: dict[str, Any], nodes_by_key: dict[str, dict[str, Any]], *, text_chars: int = 500) -> dict[str, Any]:
    children = _children_by_parent(nodes_by_key)
    descendants = _subtree_nodes(root, children)
    texts: list[str] = []
    interactive: list[dict[str, Any]] = []
    for node in [root, *descendants]:
        if node.get("vis") and node.get("text"):
            texts.append(str(node.get("text")))
        if _is_interactive_projected(node) and len(interactive) < 20:
            interactive.append({k: node.get(k) for k in ("k", "tag", "text", "attrs", "vis", "vp") if node.get(k) not in (None, "", {}, [])})
    attrs = root.get("attrs") if isinstance(root.get("attrs"), dict) else {}
    entry = {k: root.get(k) for k in ("k", "tag", "text", "attrs", "vis", "vp") if root.get(k) not in (None, "", {}, [])}
    if attrs.get("role"):
        entry["role"] = attrs.get("role")
    entry["descendant_count"] = len(descendants)
    visible_text = " ".join(" ".join(texts).split())[:max(0, int(text_chars))]
    if visible_text:
        entry["visible_text"] = visible_text
    if interactive:
        entry["interactive_descendants"] = interactive
    return entry


def _attr_plain(value: Any) -> str:
    if isinstance(value, dict) and "v" in value:
        return str(value.get("v", ""))
    return str(value or "")


def _class_tokens(value: Any) -> set[str]:
    return {token for token in _attr_plain(value).split() if token}


def classify_projected_change(before: dict[str, Any], after: dict[str, Any], *, action: str = "") -> tuple[list[str], dict[str, Any], int, bool]:
    kinds: list[str] = []
    changes: dict[str, Any] = {}
    weight = 0
    if before.get("text") != after.get("text"):
        kinds.append("text")
        changes["text"] = {"before": before.get("text", ""), "after": after.get("text", "")}
        weight = max(weight, 30)
    b_attrs = before.get("attrs") if isinstance(before.get("attrs"), dict) else {}
    a_attrs = after.get("attrs") if isinstance(after.get("attrs"), dict) else {}
    attr_changed_names: list[str] = []
    for name in sorted(set(b_attrs) | set(a_attrs)):
        if b_attrs.get(name) != a_attrs.get(name):
            attr_changed_names.append(name)
            kinds.append(f"attr:{name}")
            changes.setdefault("attrs", {})[name] = {"before": b_attrs.get(name), "after": a_attrs.get(name)}
            if name in {"value", "checked", "selected", "disabled"} or name.startswith("aria-"):
                weight = max(weight, 80)
            else:
                weight = max(weight, 25)
    likely_scroll_artifact = False
    if action == "scroll" and set(attr_changed_names) == {"class"} and len(kinds) == 1:
        before_tokens = _class_tokens(b_attrs.get("class"))
        after_tokens = _class_tokens(a_attrs.get("class"))
        delta = before_tokens ^ after_tokens
        if delta and all(token.lower() in {"active", "current"} or "active" in token.lower() or "current" in token.lower() for token in delta):
            likely_scroll_artifact = True
            weight = 1
    semantic_before_visibility = bool(kinds) and not likely_scroll_artifact
    if before.get("vis") != after.get("vis"):
        # Visibility itself is semantic for clicks/forms/navigation: modal/banner
        # show-hide, validation messages, and drawers often change only display.
        # During a pure scroll, ChromiumRL can flip visibility for nodes entering
        # or leaving the viewport; with no text/attr change that is scroll noise.
        if action == "scroll" and not semantic_before_visibility:
            kinds.append("visibility")
            changes["visibility"] = {"before": before.get("vis"), "after": after.get("vis")}
            likely_scroll_artifact = True
            weight = 1
        else:
            kinds.append("visibility")
            changes["visibility"] = {"before": before.get("vis"), "after": after.get("vis")}
            weight = max(weight, 100)
            semantic_before_visibility = True
    b_style = before.get("style") if isinstance(before.get("style"), dict) else {}
    a_style = after.get("style") if isinstance(after.get("style"), dict) else {}
    if semantic_before_visibility:
        for prop in sorted(set(b_style) | set(a_style)):
            if b_style.get(prop) != a_style.get(prop):
                kinds.append(f"style:{prop}")
                changes.setdefault("style", {})[prop] = {"before": b_style.get(prop), "after": a_style.get(prop)}
                weight = max(weight, 10)
    return kinds, changes, weight, likely_scroll_artifact


def rank_diff_entry(entry: dict[str, Any]) -> tuple[int, str]:
    return (-int(entry.get("semantic_weight", 0)), str(entry.get("k", "")))


def _url_document_key(url: str) -> tuple[str, str, str]:
    try:
        parts = urlsplit(url or "")
        return (parts.scheme, parts.netloc, parts.path)
    except Exception:
        return ("", "", str(url or ""))


def _is_blankish_url(url: str) -> bool:
    return not url or url == "about:blank" or url.startswith(("chrome://", "chrome-native://"))


def detect_cross_document(before_dom: dict[str, Any], after_dom: dict[str, Any], before_index: dict[str, Any] | None, after_index: dict[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    before_index = before_index or {}
    after_index = after_index or {}
    before_frame = main_frame_info(before_index.get("frame_tree", {}))
    after_frame = main_frame_info(after_index.get("frame_tree", {}))
    before_loader = str(before_frame.get("loaderId") or "")
    after_loader = str(after_frame.get("loaderId") or "")
    before_url = str((before_index.get("page") or {}).get("url") or before_dom.get("url") or before_frame.get("url") or "")
    after_url = str((after_index.get("page") or {}).get("url") or after_dom.get("url") or after_frame.get("url") or "")
    loader_changed = bool(before_loader and after_loader and before_loader != after_loader)
    path_changed = not _is_blankish_url(before_url) and not _is_blankish_url(after_url) and _url_document_key(before_url) != _url_document_key(after_url)
    cross = bool(loader_changed or path_changed)
    return cross, {"from_url": before_url, "to_url": after_url, "from_loader": before_loader, "to_loader": after_loader, "loader_changed": loader_changed, "path_or_origin_changed": path_changed}


def _visible_text_set(projection: dict[str, Any]) -> set[str]:
    values = set()
    for node in projection.get("nodes", []) or []:
        if isinstance(node, dict) and node.get("vis") and node.get("text"):
            text = " ".join(str(node.get("text") or "").split())
            if text:
                values.add(text)
    return values

STATE_TEXT_RE = re.compile(r"\b(?:stock|available|availability|unavailable|sold|price|tax|total|subtotal|error|required|invalid|success|selected|checked|disabled|enabled|basket|cart|checkout|shipping|delivery|pickup|rating|review|reviews|option)\b", re.I)
NUMERIC_TEXT_RE = re.compile(r"(?:\d|[£$€¥₹]|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten)\b)", re.I)


def _text_has_numeric_or_state(text: str) -> bool:
    return bool(NUMERIC_TEXT_RE.search(text or "") or STATE_TEXT_RE.search(text or ""))


def _short_common_chrome_text(text: str) -> bool:
    normalized = " ".join(str(text or "").split())
    return bool(normalized and len(normalized) < 40 and not _text_has_numeric_or_state(normalized))


def _semantic_context_for_text_node(node: dict[str, Any]) -> str:
    path = str(node.get("k") or node.get("parent") or "").lower()
    tag = str(node.get("tag") or "").lower()
    attrs = node.get("attrs") if isinstance(node.get("attrs"), dict) else {}
    classes = str(attrs.get("class") or "").lower()
    role = str(attrs.get("role") or "").lower()
    parts: list[str] = []
    for needle, label in (
        ("product_page", "product"),
        ("product_pod", "listing_item"),
        ("price_color", "price"),
        ("instock", "availability"),
        ("table", "table"),
        ("breadcrumb", "breadcrumb"),
        ("side_categories", "sidebar"),
        ("sidebar", "sidebar"),
        ("header", "header"),
        ("footer", "footer"),
        ("nav", "nav"),
        ("content_inner", "main"),
        ("main", "main"),
        ("article", "article"),
        ("section", "section"),
    ):
        if needle in path or needle in classes or needle == role:
            parts.append(label)
    if tag:
        parts.append(tag)
    # Preserve enough ancestry shape to distinguish listing-row price from
    # product-page price, but strip positional details that vary across pages.
    tail = re.sub(r"(?::nth-of-type\(\d+\)|\[\d+\]|#\d+)", "", path)
    tail = ">".join(part.strip() for part in tail.split(">")[-4:])
    if tail:
        parts.append(tail[-180:])
    return "|".join(dict.fromkeys(p for p in parts if p))


def _visible_text_records(projection: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for node in projection.get("nodes", []) or []:
        if not isinstance(node, dict) or not node.get("vis") or not node.get("text"):
            continue
        text = " ".join(str(node.get("text") or "").split())
        if not text:
            continue
        context = _semantic_context_for_text_node(node)
        identity = (text, context)
        if identity in seen:
            continue
        seen.add(identity)
        records.append({"text": text, "context": context, "k": node.get("k", ""), "tag": node.get("tag", ""), "weight": _text_record_weight(text, context)})
    return records


def _text_record_weight(text: str, context: str) -> tuple[int, int, str]:
    weight = 0
    lower_context = (context or "").lower()
    if _text_has_numeric_or_state(text):
        weight += 1000
    if any(x in lower_context for x in ("product", "price", "availability", "table", "article", "main")):
        weight += 500
    if any(x in lower_context for x in ("sidebar", "breadcrumb", "header", "footer", "nav")):
        weight -= 300
    return (-weight, -len(text), text)


def _cross_document_text_delta(before_projection: dict[str, Any], after_projection: dict[str, Any], *, limit: int = 200) -> dict[str, Any]:
    before_records = _visible_text_records(before_projection)
    after_records = _visible_text_records(after_projection)
    before_pairs = {(r["text"], r["context"]) for r in before_records}
    after_pairs = {(r["text"], r["context"]) for r in after_records}
    before_texts = {r["text"] for r in before_records}
    after_texts = {r["text"] for r in after_records}
    common_texts = before_texts & after_texts

    suppressed_common_chrome = 0

    def emit_records(records: list[dict[str, Any]], other_pairs: set[tuple[str, str]], *, suppress_common: bool) -> tuple[list[str], int]:
        nonlocal suppressed_common_chrome
        candidates: list[dict[str, Any]] = []
        for record in records:
            text = record["text"]
            # Persistent chrome such as category/sidebar/nav labels often survives a
            # navigation with slightly different structural paths. Suppress only
            # short, identical, non-numeric/non-state strings; prices, counts,
            # availability, errors, totals, etc. are never suppressed here.
            if suppress_common and text in common_texts and _short_common_chrome_text(text):
                suppressed_common_chrome += 1
                continue
            pair = (text, record["context"])
            if pair in other_pairs:
                continue
            # Do not suppress numeric/state values even if the same raw string appears elsewhere.
            # If context changed, the text moved semantically and is verifier-relevant.
            candidates.append(record)
        candidates.sort(key=lambda r: r.get("weight", (0, 0, "")))
        out: list[str] = []
        seen_text: set[str] = set()
        for record in candidates:
            text = record["text"]
            if text in seen_text:
                continue
            seen_text.add(text)
            out.append(text)
            if len(out) >= limit:
                break
        return out, len(candidates)

    added, added_total = emit_records(after_records, before_pairs, suppress_common=True)
    removed, removed_total = emit_records(before_records, after_pairs, suppress_common=True)
    return {
        "added": added,
        "removed": removed,
        "added_total": added_total,
        "removed_total": removed_total,
        "suppressed_common_chrome": suppressed_common_chrome,
        "common_text_total": len(common_texts),
    }


def _action_label(node: dict[str, Any]) -> str:
    attrs = node.get("attrs") if isinstance(node.get("attrs"), dict) else {}
    for value in (node.get("text"), attrs.get("aria-label"), attrs.get("title"), attrs.get("alt"), attrs.get("value"), attrs.get("placeholder")):
        label = " ".join(str(value or "").split())
        if label:
            return label
    return ""


def _action_region_score(node: dict[str, Any]) -> int:
    path = str(node.get("k") or "").lower()
    score = 0
    if node.get("vp"):
        score += 300
    if node.get("vis"):
        score += 200
    if any(x in path for x in ("content_inner", "product_page", "article", "main", "section")):
        score += 250
    if any(x in path for x in ("header", "breadcrumb", "side_categories", "sidebar", "footer", "nav")):
        score -= 250
    tag = str(node.get("tag") or "").lower()
    attrs = node.get("attrs") if isinstance(node.get("attrs"), dict) else {}
    role = str(attrs.get("role") or "").lower()
    if tag in {"button", "input", "select", "textarea"} or role in {"button", "checkbox", "radio", "combobox", "textbox"}:
        score += 350
    elif tag == "a" or role == "link":
        score += 50
    label = _action_label(node).lower()
    if any(word in label for word in ("add", "basket", "cart", "buy", "submit", "continue", "checkout", "select", "option")):
        score += 300
    return score


def _projected_action_entry(node: dict[str, Any]) -> dict[str, Any] | None:
    if not _is_interactive_projected(node):
        return None
    label = _action_label(node)
    if not label:
        return None
    entry = {k: node.get(k) for k in ("k", "tag", "attrs", "vis", "vp", "frame", "source") if node.get(k) not in (None, "", {}, [])}
    entry["text"] = label
    entry["action_score"] = _action_region_score(node)
    return entry


def _action_context(node: dict[str, Any], nodes_by_key: dict[str, dict[str, Any]]) -> str:
    label = _action_label(node)
    parent = str(node.get("parent") or "")
    seen = set()
    while parent and parent not in seen:
        seen.add(parent)
        candidate = nodes_by_key.get(parent)
        if not candidate:
            break
        text = " ".join(str(candidate.get("text") or "").split())
        if text and text != label:
            return text[:180]
        parent = str(candidate.get("parent") or "")
    return ""


def _action_signature_for_dedupe(entry: dict[str, Any]) -> tuple[str, str, str]:
    path = str(entry.get("k") or "")
    label = str(entry.get("text") or "")
    tag = str(entry.get("tag") or "")
    leaf = re.sub(r":nth-of-type\(\d+\)|\[\d+\]|#\d+$", "", path.rsplit(">", 1)[-1])
    return tag, label, leaf


def _dedupe_ranked_actions(entries: list[dict[str, Any]], *, limit: int = 40) -> list[dict[str, Any]]:
    label_counts: dict[str, int] = {}
    for entry in entries:
        label = str(entry.get("text") or "")
        label_counts[label] = label_counts.get(label, 0) + 1
    for entry in entries:
        if label_counts.get(str(entry.get("text") or ""), 0) > 1 and entry.get("context"):
            entry["action_score"] = int(entry.get("action_score", 0) or 0) - 75
    entries.sort(key=lambda e: (-int(e.get("action_score", 0) or 0), str(e.get("text") or ""), str(e.get("context") or ""), str(e.get("k") or "")))
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        sig = _action_signature_for_dedupe(entry)
        # Keep distinct labelled links/buttons, but avoid filling top_actions with
        # many identical controls from a repeated carousel/list. Context remains
        # on the retained item so the action is still interpretable.
        if sig in seen:
            continue
        seen.add(sig)
        cleaned = dict(entry)
        cleaned.pop("action_score", None)
        out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _document_entry(projection: dict[str, Any], *, text_chars: int) -> dict[str, Any]:
    nodes = [n for n in projection.get("nodes", []) or [] if isinstance(n, dict)]
    nodes_by_key = {str(n.get("k")): n for n in nodes if n.get("k")}
    root = next((n for n in nodes if n.get("tag") == "html"), nodes[0] if nodes else {})
    texts = [str(n.get("text")) for n in nodes if n.get("vis") and n.get("text")]
    interactive = []
    for node in nodes:
        entry = _projected_action_entry(node)
        if entry is not None:
            context = _action_context(node, nodes_by_key)
            if context:
                entry["context"] = context
            interactive.append(entry)
    interactive = _dedupe_ranked_actions(interactive, limit=40)
    return {
        "root": root.get("k", ""),
        "title": projection.get("title", ""),
        "descendant_count": max(0, len(nodes) - 1),
        "visible_text": " ".join(" ".join(texts).split())[:max(0, int(text_chars))],
        "interactive_descendants": interactive,
    }


def _entry_text(entry: dict[str, Any]) -> str:
    parts = []
    for key in ("text", "visible_text"):
        value = entry.get(key)
        if value:
            parts.append(str(value))
    for child in entry.get("interactive_descendants", []) if isinstance(entry.get("interactive_descendants"), list) else []:
        if isinstance(child, dict):
            for key in ("text", "visible_text"):
                value = child.get(key)
                if value:
                    parts.append(str(value))
    return " ".join(" ".join(parts).split())


def _group_signature(entry: dict[str, Any]) -> str:
    path = str(entry.get("k") or "")
    parent = path.rsplit("/", 1)[0] if "/" in path else ""
    tag = str(entry.get("tag") or "node")
    attrs = entry.get("attrs") if isinstance(entry.get("attrs"), dict) else {}
    cls = attrs.get("class", "")
    role = attrs.get("role", "") or entry.get("role", "")
    # Strip positional details from the leaf only; parent remains to avoid merging
    # unrelated repeated structures in different page regions.
    leaf = path.rsplit("/", 1)[-1]
    leaf = re.sub(r":nth-of-type\(\d+\)|\[\d+\]|#\d+$", "", leaf)
    return "|".join(str(x) for x in (parent, tag, role, cls, leaf))


def collapse_repeated_diff_groups(entries: list[dict[str, Any]], *, text_chars: int = 300) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for entry in entries:
        sig = _group_signature(entry)
        if sig not in groups:
            order.append(sig)
        groups.setdefault(sig, []).append(entry)
    out: list[dict[str, Any]] = []
    group_index = 1
    for sig in order:
        members = groups[sig]
        if len(members) < 3:
            out.extend(members)
            continue
        member_texts = []
        for member in members:
            text = _entry_text(member)
            if text:
                member_texts.append(text[:220])
        combined_text = " ".join(member_texts)
        combined_text = " ".join(combined_text.split())[:max(0, int(text_chars))]
        sample = []
        for member in members[:2]:
            sample.append({k: member.get(k) for k in ("k", "tag", "text", "attrs", "visible_text", "descendant_count") if member.get(k) not in (None, "", {}, [])})
        out.append({
            "kind": "group",
            "group_id": f"g{group_index}",
            "signature": sig,
            "count": len(members),
            "sample": sample,
            "text": combined_text,
            "member_text": member_texts[:40],
            "semantic_weight": max(int(member.get("semantic_weight", 0) or 0) for member in members),
        })
        group_index += 1
    return out


def _collect_paths(value: Any, paths: dict[str, str]) -> None:
    if isinstance(value, dict):
        k = value.get("k")
        if isinstance(k, str) and k:
            paths.setdefault(k, "")
        for child in value.values():
            _collect_paths(child, paths)
    elif isinstance(value, list):
        for child in value:
            _collect_paths(child, paths)


def _replace_paths_with_ids(value: Any, id_by_path: dict[str, str]) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "k" and isinstance(item, str) and item in id_by_path:
                out["id"] = id_by_path[item]
            elif key in {"parent", "root"} and isinstance(item, str) and item in id_by_path:
                out[key] = id_by_path[item]
            elif key == "signature" and isinstance(item, str):
                # Group signatures can include long parent paths; keep a short readable leaf.
                out[key] = item.rsplit("|", 1)[-1] or item[-80:]
            else:
                out[key] = _replace_paths_with_ids(item, id_by_path)
        return out
    if isinstance(value, list):
        return [_replace_paths_with_ids(item, id_by_path) for item in value]
    return value


def compact_dom_diff_payload(diff: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(diff, ensure_ascii=False))
    payload["format"] = "compact"

    # Changed entries carry all verifier evidence in `changes`; remove redundant
    # before/after full node projections that repeated unchanged attrs/styles.
    for section in ("changed", "flagged_changes"):
        for entry in payload.get(section, []) if isinstance(payload.get(section), list) else []:
            if not isinstance(entry, dict):
                continue
            entry.pop("before", None)
            entry.pop("after", None)
            entry.pop("style", None)

    # Cross-document compact representation: counts + text delta + top actions.
    if payload.get("cross_document"):
        doc_added = payload.pop("document_added", {}) if isinstance(payload.get("document_added"), dict) else {}
        doc_removed = payload.pop("document_removed", {}) if isinstance(payload.get("document_removed"), dict) else {}
        if doc_added or doc_removed:
            payload["document"] = {
                "removed_nodes": doc_removed.get("descendant_count", 0),
                "added_nodes": doc_added.get("descendant_count", 0),
            }
        top_actions = payload.pop("interactive_added", [])
        payload["top_actions"] = top_actions[:10] if isinstance(top_actions, list) else []

    paths_seen: dict[str, str] = {}
    for key in ("added", "removed", "changed", "flagged_changes", "top_actions"):
        _collect_paths(payload.get(key), paths_seen)
    sorted_paths = sorted(paths_seen)
    id_by_path = {path: f"n{i+1}" for i, path in enumerate(sorted_paths)}
    payload = _replace_paths_with_ids(payload, id_by_path)
    if id_by_path:
        payload["paths"] = {short_id: path for path, short_id in id_by_path.items()}
    return payload


def _quote_short(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + "…"
    return json.dumps(text, ensure_ascii=False)


def render_dom_diff_text(diff: dict[str, Any]) -> str:
    lines: list[str] = []
    nav = diff.get("navigation") if isinstance(diff.get("navigation"), dict) else {}
    source = diff.get("source") if isinstance(diff.get("source"), dict) else {}
    after = source.get("after") if isinstance(source.get("after"), dict) else {}
    title = after.get("title") or ""
    url = after.get("url") or nav.get("to_url") or ""
    lines.append(f"PAGE title={_quote_short(title, 160)} url={_quote_short(url, 240)}")
    if diff.get("cross_document"):
        document = diff.get("document") if isinstance(diff.get("document"), dict) else {}
        lines.append(
            f"NAV from={_quote_short(nav.get('from_url'), 180)} to={_quote_short(nav.get('to_url'), 180)} "
            f"removed_nodes={document.get('removed_nodes', 0)} added_nodes={document.get('added_nodes', 0)}"
        )
    text_delta = diff.get("text_delta") if isinstance(diff.get("text_delta"), dict) else {}
    for text in text_delta.get("added", [])[:80] if isinstance(text_delta.get("added"), list) else []:
        lines.append(f"+TEXT {_quote_short(text, 220)}")
    for text in text_delta.get("removed", [])[:80] if isinstance(text_delta.get("removed"), list) else []:
        lines.append(f"-TEXT {_quote_short(text, 220)}")
    for entry in diff.get("added", []) if isinstance(diff.get("added"), list) else []:
        if entry.get("kind") == "group":
            lines.append(f"+GROUP {entry.get('group_id','')} {entry.get('signature','')} x{entry.get('count',0)} {_quote_short(entry.get('text'), 240)}")
            for member_text in entry.get("member_text", [])[:20] if isinstance(entry.get("member_text"), list) else []:
                lines.append(f"  +ITEM {_quote_short(member_text, 180)}")
        else:
            lines.append(f"+[{entry.get('id', entry.get('k', ''))}] {entry.get('tag','node')} {_quote_short(entry.get('text') or entry.get('visible_text'), 220)}")
    for entry in diff.get("removed", []) if isinstance(diff.get("removed"), list) else []:
        if entry.get("kind") == "group":
            lines.append(f"-GROUP {entry.get('group_id','')} {entry.get('signature','')} x{entry.get('count',0)} {_quote_short(entry.get('text'), 240)}")
            for member_text in entry.get("member_text", [])[:20] if isinstance(entry.get("member_text"), list) else []:
                lines.append(f"  -ITEM {_quote_short(member_text, 180)}")
        else:
            lines.append(f"-[{entry.get('id', entry.get('k', ''))}] {entry.get('tag','node')} {_quote_short(entry.get('text') or entry.get('visible_text'), 220)}")
    for entry in diff.get("changed", []) if isinstance(diff.get("changed"), list) else []:
        changes = entry.get("changes") if isinstance(entry.get("changes"), dict) else {}
        facts = []
        if "text" in changes:
            t = changes["text"]
            facts.append(f"text:{_quote_short(t.get('before'), 80)}->{_quote_short(t.get('after'), 80)}")
        for name, change in (changes.get("attrs") or {}).items() if isinstance(changes.get("attrs"), dict) else []:
            facts.append(f"{name}:{_quote_short(change.get('before'), 60)}->{_quote_short(change.get('after'), 60)}")
        if "visibility" in changes:
            v = changes["visibility"]
            facts.append(f"visible:{v.get('before')}->{v.get('after')}")
        lines.append(f"~[{entry.get('id', entry.get('k', ''))}] {entry.get('tag','node')} {'; '.join(facts)}")
    for entry in diff.get("flagged_changes", []) if isinstance(diff.get("flagged_changes"), list) else []:
        lines.append(f"![{entry.get('id', entry.get('k', ''))}] flagged={entry.get('likely_scroll_artifact', False)} kind={','.join(entry.get('kind', []))}")
    for entry in diff.get("top_actions", []) if isinstance(diff.get("top_actions"), list) else []:
        lines.append(f"ACTION [{entry.get('id', entry.get('k', ''))}] {entry.get('tag','node')} {_quote_short(entry.get('text'), 160)}" + (f" context={_quote_short(entry.get('context'), 180)}" if entry.get('context') else ""))
    stats = diff.get("stats") if isinstance(diff.get("stats"), dict) else {}
    frames = diff.get("frames") if isinstance(diff.get("frames"), dict) else {}
    lines.append(
        f"STATS +{stats.get('added_total',0)}/-{stats.get('removed_total',0)} ~{stats.get('changed_total',0)} "
        f"flagged={stats.get('flagged_total',0)} truncated={bool(stats.get('truncated'))} "
        f"frames={frames.get('traversed',0)}/{frames.get('count',0)} shadow={frames.get('shadow_dom','unknown')}"
    )
    return "\n".join(lines).rstrip() + "\n"


def compare_operation_counts(compare_result: dict[str, Any] | None) -> dict[str, int]:
    payload = ((compare_result or {}).get("result") or compare_result or {}) if isinstance(compare_result, dict) else {}
    counts: dict[str, int] = {}
    for key in ("insertions", "deletions", "moves", "attributeChanges", "textChanges", "layoutChanges", "styleChanges", "typeChanges"):
        value = payload.get(key) if isinstance(payload, dict) else None
        counts[key] = len(value) if isinstance(value, list) else 0
    return counts


def validate_local_diff_against_compare(local: dict[str, Any], compare_result: dict[str, Any] | None) -> dict[str, Any]:
    compare_counts = compare_operation_counts(compare_result)
    changed = local.get("changed", []) if isinstance(local.get("changed"), list) else []
    local_counts = {
        "insertions": int((local.get("stats") or {}).get("added_total", 0)),
        "deletions": int((local.get("stats") or {}).get("removed_total", 0)),
        "attributeChanges": sum(1 for e in changed if any(str(k).startswith("attr:") for k in e.get("kind", []))),
        "textChanges": sum(1 for e in changed if "text" in e.get("kind", [])),
        "styleChanges": sum(1 for e in changed if any(str(k).startswith("style:") for k in e.get("kind", []))),
    }
    categories = sorted(set(compare_counts) | set(local_counts))
    return {
        "enabled": True,
        "counts": {key: {"local": local_counts.get(key, 0), "compareDOMState": compare_counts.get(key, 0), "delta": local_counts.get(key, 0) - compare_counts.get(key, 0)} for key in categories},
    }


def build_compact_dom_diff(
    before_dom: dict[str, Any],
    after_dom: dict[str, Any],
    *,
    compare_result: dict[str, Any] | None = None,
    compare_timing: dict[str, Any] | None = None,
    max_entries: int = 200,
    before_index: dict[str, Any] | None = None,
    after_index: dict[str, Any] | None = None,
    action: str = "",
    collapse_text_chars: int = 500,
    validate_diff: bool = False,
    verbosity: str = "compact",
) -> dict[str, Any]:
    before_projection = project_dom_state(before_dom) if before_dom else {"nodes": [], "key_population": {}, "url": "", "title": ""}
    after_projection = project_dom_state(after_dom) if after_dom else {"nodes": [], "key_population": {}, "url": "", "title": ""}
    cross_document, navigation = detect_cross_document(before_dom, after_dom, before_index, after_index)
    frames = frame_coverage_from_tree((after_index or {}).get("frame_tree", {}) or (before_index or {}).get("frame_tree", {}), after_projection)
    source = {
        "before": {"url": before_dom.get("url", ""), "title": before_dom.get("title", ""), "nodes": len(before_dom.get("nodes", []) or [])},
        "after": {"url": after_dom.get("url", ""), "title": after_dom.get("title", ""), "nodes": len(after_dom.get("nodes", []) or [])},
        "compareDOMState": {"timing": compare_timing or {}, "summary": ((compare_result or {}).get("result") or compare_result or {}).get("summary", {}) if isinstance(compare_result, dict) else {}},
    }
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "method": "local_slim_dom_semantic_diff",
        "captured_at": utc_now(),
        "cross_document": cross_document,
        "navigation": navigation,
        "source": source,
        "frames": frames,
        "enrichment": {"before": (before_index or {}).get("form_enrichment", {}), "after": (after_index or {}).get("form_enrichment", {})},
        "key_population": {"before": before_projection.get("key_population", {}), "after": after_projection.get("key_population", {})},
    }
    if cross_document:
        text_delta = _cross_document_text_delta(before_projection, after_projection, limit=200)
        added_text = text_delta.get("added", [])
        removed_text = text_delta.get("removed", [])
        stats = {
            "added_total": len(after_projection.get("nodes", []) or []),
            "added_roots_total": 1 if after_projection.get("nodes") else 0,
            "added_emitted": 1 if after_projection.get("nodes") else 0,
            "removed_total": len(before_projection.get("nodes", []) or []),
            "removed_roots_total": 1 if before_projection.get("nodes") else 0,
            "removed_emitted": 1 if before_projection.get("nodes") else 0,
            "changed_total": 0,
            "changed_emitted": 0,
            "flagged_total": 0,
            "flagged_emitted": 0,
            "truncated": int(text_delta.get("added_total", 0) or 0) > len(added_text) or int(text_delta.get("removed_total", 0) or 0) > len(removed_text),
            "suppressed_common_chrome": int(text_delta.get("suppressed_common_chrome", 0) or 0),
        }
        before_doc = _document_entry(before_projection, text_chars=collapse_text_chars)
        after_doc = _document_entry(after_projection, text_chars=collapse_text_chars)
        base.update({
            "stats": stats,
            "document_removed": before_doc,
            "document_added": after_doc,
            "text_delta": text_delta,
            "interactive_added": after_doc.get("interactive_descendants", [])[:40],
            "added": [],
            "removed": [],
            "changed": [],
            "flagged_changes": [],
        })
        if validate_diff:
            base["compare_validation"] = validate_local_diff_against_compare(base, compare_result)
        return base if verbosity == "full" else compact_dom_diff_payload(base)

    before_nodes = {str(n.get("k")): n for n in before_projection.get("nodes", []) if isinstance(n, dict) and n.get("k")}
    after_nodes = {str(n.get("k")): n for n in after_projection.get("nodes", []) if isinstance(n, dict) and n.get("k")}
    before_keys = set(before_nodes)
    after_keys = set(after_nodes)
    added_keys = after_keys - before_keys
    removed_keys = before_keys - after_keys
    common_keys = before_keys & after_keys

    added_roots = [k for k in added_keys if str(after_nodes[k].get("parent") or "") not in added_keys]
    removed_roots = [k for k in removed_keys if str(before_nodes[k].get("parent") or "") not in removed_keys]
    added_entries = [collapse_subtree_entry(after_nodes[k], after_nodes, text_chars=collapse_text_chars) for k in added_roots]
    removed_entries = [collapse_subtree_entry(before_nodes[k], before_nodes, text_chars=collapse_text_chars) for k in removed_roots]

    changed_entries: list[dict[str, Any]] = []
    flagged_entries: list[dict[str, Any]] = []
    for key in common_keys:
        kinds, changes, weight, likely_scroll_artifact = classify_projected_change(before_nodes[key], after_nodes[key], action=action)
        if not kinds:
            continue
        entry = {
            "k": key,
            "tag": after_nodes[key].get("tag"),
            "kind": kinds,
            "semantic_weight": weight,
            "before": {k: before_nodes[key].get(k) for k in ("text", "attrs", "vis", "vp", "style", "frame", "source") if before_nodes[key].get(k) not in (None, "", {}, [])},
            "after": {k: after_nodes[key].get(k) for k in ("text", "attrs", "vis", "vp", "style", "frame", "source") if after_nodes[key].get(k) not in (None, "", {}, [])},
            "changes": changes,
        }
        if likely_scroll_artifact:
            entry["likely_scroll_artifact"] = True
            flagged_entries.append(entry)
        else:
            changed_entries.append(entry)

    added_entries = collapse_repeated_diff_groups(added_entries, text_chars=300)
    removed_entries = collapse_repeated_diff_groups(removed_entries, text_chars=300)

    def truncate(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        entries = sorted(entries, key=rank_diff_entry)
        return entries[:max(0, int(max_entries))]

    added_emit = truncate(added_entries)
    removed_emit = truncate(removed_entries)
    changed_emit = truncate(changed_entries)
    flagged_emit = truncate(flagged_entries)
    suspicious = bool(before_nodes and (len(added_keys) + len(removed_keys)) > 0.60 * len(before_nodes))
    stats = {
        "added_total": len(added_keys),
        "added_roots_total": len(added_entries),
        "added_emitted": len(added_emit),
        "removed_total": len(removed_keys),
        "removed_roots_total": len(removed_entries),
        "removed_emitted": len(removed_emit),
        "changed_total": len(changed_entries),
        "changed_emitted": len(changed_emit),
        "flagged_total": len(flagged_entries),
        "flagged_emitted": len(flagged_emit),
        "truncated": len(added_entries) > len(added_emit) or len(removed_entries) > len(removed_emit) or len(changed_entries) > len(changed_emit) or len(flagged_entries) > len(flagged_emit),
        "suspicious_diff_scale": suspicious,
    }
    base.update({"stats": stats, "added": added_emit, "removed": removed_emit, "changed": changed_emit, "flagged_changes": flagged_emit})
    if validate_diff:
        base["compare_validation"] = validate_local_diff_against_compare(base, compare_result)
    return base if verbosity == "full" else compact_dom_diff_payload(base)


def build_dom_diff_summary(before: CapturedState, after: CapturedState) -> dict[str, Any]:
    before_obs = observation_payload(before)
    after_obs = observation_payload(after)
    before_elements = observation_elements(before)
    after_elements = observation_elements(after)
    before_by_id = {element_identity(element): element for element in before_elements}
    after_by_id = {element_identity(element): element for element in after_elements}
    before_ids = set(before_by_id)
    after_ids = set(after_by_id)

    before_scroll = before.page_state.get("viewport", {}) if isinstance(before.page_state.get("viewport"), dict) else {}
    after_scroll = after.page_state.get("viewport", {}) if isinstance(after.page_state.get("viewport"), dict) else {}
    before_text = text_set_from_elements(before_elements)
    after_text = text_set_from_elements(after_elements)

    added_ids = sorted(after_ids - before_ids)
    removed_ids = sorted(before_ids - after_ids)
    common_ids = sorted(before_ids & after_ids)
    changed: list[dict[str, Any]] = []
    for identity in common_ids:
        before_element = before_by_id[identity]
        after_element = after_by_id[identity]
        changes: dict[str, Any] = {}
        for key in ("text", "accessibleName", "href", "value", "selected", "expanded"):
            if key in before_element and key in after_element and before_element.get(key) != after_element.get(key):
                changes[key] = {"before": before_element.get(key), "after": after_element.get(key)}
        before_center = (first_number(before_element.get("centerX")), first_number(before_element.get("centerY")))
        after_center = (first_number(after_element.get("centerX")), first_number(after_element.get("centerY")))
        try:
            dx = (after_center[0] or 0) - (before_center[0] or 0)
            dy = (after_center[1] or 0) - (before_center[1] or 0)
            scroll_dx = float(after_scroll.get("scrollX", 0) or 0) - float(before_scroll.get("scrollX", 0) or 0)
            scroll_dy = float(after_scroll.get("scrollY", 0) or 0) - float(before_scroll.get("scrollY", 0) or 0)
            moved = abs(dx + scroll_dx) > 8 or abs(dy + scroll_dy) > 8
        except Exception:
            moved = False
        if changes:
            if moved:
                changes["moved"] = True
            changed.append({"id": identity, "element": compact_element(after_element), "changes": changes})

    return {
        "schema_version": SCHEMA_VERSION,
        "method": "local_agent_observation_summary",
        "captured_at": utc_now(),
        "url": {
            "before": before.page_state.get("url") or before_obs.get("url"),
            "after": after.page_state.get("url") or after_obs.get("url"),
            "changed": (before.page_state.get("url") or before_obs.get("url"))
            != (after.page_state.get("url") or after_obs.get("url")),
        },
        "title": {
            "before": before.page_state.get("title") or before_obs.get("title"),
            "after": after.page_state.get("title") or after_obs.get("title"),
            "changed": (before.page_state.get("title") or before_obs.get("title"))
            != (after.page_state.get("title") or after_obs.get("title")),
        },
        "scroll": {
            "before": before_scroll,
            "after": after_scroll,
            "changed": (before_scroll.get("scrollX"), before_scroll.get("scrollY")) != (after_scroll.get("scrollX"), after_scroll.get("scrollY")),
        },
        "stats": {
            "before": before_obs.get("stats", {}),
            "after": after_obs.get("stats", {}),
            "elements_before": len(before_elements),
            "elements_after": len(after_elements),
            "elements_added": len(added_ids),
            "elements_removed": len(removed_ids),
            "elements_changed": len(changed),
        },
        "visible_text_added": sorted(after_text - before_text)[:100],
        "visible_text_removed": sorted(before_text - after_text)[:100],
        "interactive_added": [compact_element(after_by_id[identity]) for identity in added_ids[:100]],
        "interactive_removed": [compact_element(before_by_id[identity]) for identity in removed_ids[:100]],
        "interactive_changed": changed[:100],
    }


def build_verifier_action(
    action: Any,
    before: CapturedState,
    after: CapturedState,
    signals: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(action, dict):
        return {
            "action": "unknown",
            "thoughts": str(action),
            "_recorder_warnings": ["source action was not a JSON object"],
        }

    name = action_name(action)
    result: dict[str, Any] = {"action": name, "thoughts": action_thoughts(action)}
    warnings: list[str] = []

    reference_coordinate = action_coordinate(action)
    coordinate = latest_touch_coordinate(signals) if name in COORDINATE_ACTIONS else None
    inferred_from = "ChromiumRL.getTouchTraces"
    if coordinate is None:
        coordinate = reference_coordinate
        inferred_from = "reference_action"
    if coordinate is None and name == "scroll":
        coordinate = viewport_center(before.page_state) or viewport_center(after.page_state)
        inferred_from = "viewport_center_fallback"
    if coordinate is not None:
        result["coordinate"] = coordinate
        result["_coordinate_source"] = inferred_from
        if reference_coordinate is not None:
            result["_reference_coordinate"] = reference_coordinate
    elif name in COORDINATE_ACTIONS:
        warnings.append("coordinate was required but could not be inferred")

    if name == "scroll":
        if "pixels" in action:
            result["pixels"] = action["pixels"]
        else:
            warnings.append("pixels is required for scroll but was missing")
    elif name == "type":
        if "text" in action:
            result["text"] = action["text"]
        else:
            warnings.append("text is required for type but was missing")
    elif name in {"web_search", "search"}:
        if "query" in action:
            result["query"] = action["query"]
        else:
            warnings.append("query is required for search but was missing")
    elif name in {"navigate", "visit_url", "open"}:
        if "url" in action:
            result["url"] = action["url"]
        else:
            warnings.append("url is required for navigate but was missing")
    elif name in {"press", "key"}:
        if "key" in action:
            result["key"] = action["key"]
        elif isinstance(action.get("keys"), list) and action["keys"]:
            result["key"] = action["keys"][0]
            result["_key_source"] = "keys[0]"
        else:
            warnings.append("key is required for press but was missing")
    elif name == "terminate":
        result["status"] = action.get("status", "success")

    element = element_at_coordinate_from_observation(before, coordinate) or element_at_coordinate_from_observation(
        after, coordinate
    )
    if element is not None:
        result["_target_element"] = compact_element(element)
    if warnings:
        result["_recorder_warnings"] = warnings
    return result


async def collect_chromiumrl_signals(cdp: CDPConnection) -> dict[str, Any]:
    frame_tree, frame_tree_timing = await timed_command(cdp, "Page.getFrameTree", required=False, timeout=5.0)
    ids = frame_ids(frame_tree)
    main_frame_id = ids[0] if ids else ""
    requests: list[tuple[str, dict[str, Any]]] = [
        ("ChromiumRL.getTouchTraces", {}),
        ("ChromiumRL.getCLSAttribution", {}),
        ("ChromiumRL.getCompositorLayers", {"includePaintInfo": True, "includeTransforms": False}),
        ("ChromiumRL.getVisualHash", {}),
    ]
    if main_frame_id:
        requests.insert(
            1,
            ("ChromiumRL.getLayoutTimings", {"frameId": main_frame_id, "includeZeroTime": False}),
        )
    result: dict[str, Any] = {
        "captured_at": utc_now(),
        "main_frame_id": main_frame_id,
        "commands": {
            "Page.getFrameTree": command_entry({}, frame_tree_timing, frame_tree),
        },
    }
    for method, params in requests:
        value, timing = await timed_command(cdp, method, params, required=False, label="signals", timeout=5.0)
        result["commands"][method] = command_entry(params, timing, value)
    return result


async def collect_touch_trace_signals(cdp: CDPConnection) -> dict[str, Any]:
    value, timing = await timed_command(cdp, "ChromiumRL.getTouchTraces", required=False, label="signals", timeout=5.0)
    return {
        "captured_at": utc_now(),
        "commands": {
            "ChromiumRL.getTouchTraces": command_entry({}, timing, value),
        },
    }



async def collect_interaction_capture(
    cdp: CDPConnection,
    action: Any,
    verifier_action: dict[str, Any],
    before_dom: dict[str, Any],
    after_dom: dict[str, Any],
) -> dict[str, Any]:
    coordinate = verifier_action.get("coordinate")
    node = node_at_coordinate(before_dom, coordinate) or node_at_coordinate(after_dom, coordinate)
    if node is None:
        node = first_visible_node(after_dom) or first_visible_node(before_dom)
    node_id = node.get("nodeId") if isinstance(node, dict) else None
    if not isinstance(node_id, int):
        return {
            "captured_at": utc_now(),
            "target": None,
            "commands": {},
            "skipped": "no DOM nodeId was available for ChromiumRL.captureInteraction",
        }
    name = action_name(action) or verifier_action.get("action") or "unknown"
    params = {
        "interactionType": str(name),
        "targetNodeId": node_id,
        "captureDurationMs": 1,
    }
    target = {
        "nodeId": node_id,
        "coordinate": coordinate,
        "cssSelector": node.get("cssSelector"),
        "xpath": node.get("xpath"),
        "bounds": node.get("bounds"),
    }
    result: dict[str, Any] = {
        "captured_at": utc_now(),
        "target": target,
        "selected_method": None,
        "commands": {},
    }
    # Some ChromiumRL builds expose the singular method name, while older notes
    # may refer to the plural alias. Use the real method first and probe the
    # plural alias only as a fallback to avoid noisy verifier artifacts.
    # Interaction capture is optional evidence. Some Wootz builds expose the
    # method but never answer it, so bound each probe and never stall a run.
    for method in ("ChromiumRL.captureInteraction", "ChromiumRL.captureInteractions"):
        value, timing = await timed_command(cdp, method, params, required=False, timeout=2.0)
        result["commands"][method] = command_entry(params, timing, value)
        if timing.get("ok"):
            result["selected_method"] = method
            break
    return result


def artifact_record(step_dir: Path, task_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(step_dir.rglob("*")):
        if path.is_file() and path != step_dir / "step.json":
            relative = path.relative_to(task_dir).as_posix()
            result[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return result


def step_numbers(task_dir: Path) -> list[int]:
    numbers: list[int] = []
    for path in task_dir.glob("step_*"):
        match = re.fullmatch(r"step_(\d{3,})", path.name)
        if match and path.is_dir():
            numbers.append(int(match.group(1)))
    return sorted(numbers)


def write_verifier_readme(task_dir: Path) -> None:
    text = """# Verifier artifact guide

Required files:

- `manifest.json` — run metadata and task id.
- `log.jsonl` — complete event stream and model/action trace.
- `agent_browser_final.json` — final claim/status to verify.
- `step_NNN/action.json` — normalized action and verifier action fields.
- `step_NNN/page_state.json` — after-step URL/title/viewport state.
- `step_NNN/dom_diff.json` — primary verifier evidence.
- `step_NNN/dom_diff.txt` — human-readable rendering of the same diff.

Default step files:

- `after.jpg` — after-step screenshot.
- `before.jpg` — present only with `--screenshot-mode both`.
- `dom_before.json.gz` and `dom_after.json.gz` — slim DOM projections used to produce the diff.

Optional agent-debug files, present only with `--keep-observations`:

- `observation_before.json.gz`
- `observation_after.json.gz`
- `observation_diff.json`

Final state:

- `final_state/dom_full.json.gz` — raw final ChromiumRL DOM snapshot when enabled.
- `final_state/dom_state.json.gz` — slim final DOM projection.
- `final_state/page_state.json` — final URL/title/viewport state.
- `final_state/observation.json` — final capped interactive observation; this is not a DOM snapshot.

Use the last step's `dom_diff.json` for the final transition. There is intentionally no `final_state/dom_diff.json`.
"""
    (task_dir / "VERIFIER.md").write_text(text, encoding="utf-8")


def update_manifest(task_dir: Path, **updates: Any) -> dict[str, Any]:
    path = task_dir / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(updates)
    manifest["updated_at"] = utc_now()
    write_json(path, manifest)
    return manifest


def initialize_task(
    output_root: Path,
    task_id: str,
    source_actions: Any,
    action_count: int,
    cdp_url: str,
    *,
    resume: bool,
) -> Path:
    validate_task_id(task_id)
    task_dir = output_root.resolve() / task_id
    if task_dir.exists():
        if not resume:
            raise RecorderError(f"task directory already exists: {task_dir}; use --resume to append")
        if not (task_dir / "manifest.json").is_file():
            raise RecorderError(f"cannot resume {task_dir}: manifest.json is missing")
        return task_dir
    task_dir.mkdir(parents=True)
    append_jsonl(task_dir / "log.jsonl", {"ts": utc_now(), "event": "run_started", "task_id": task_id, "source_actions": source_actions})
    write_json(
        task_dir / "manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "status": "recording",
            "started_at": utc_now(),
            "updated_at": utc_now(),
            "cdp_url": cdp_url,
            "source_actions": source_actions,
            "source_action_count": action_count,
            "completed_steps": 0,
        },
    )
    write_verifier_readme(task_dir)
    return task_dir


async def wait_for_ready(cdp: CDPConnection, *, timeout: float = 12.0, quiet_ms: int = 500) -> dict[str, Any]:
    started = time.perf_counter()
    last_count: int | None = None
    stable_since: float | None = None
    last_state = ""
    while (time.perf_counter() - started) < timeout:
        try:
            runtime = await cdp.send(
                "Runtime.evaluate",
                {"expression": "({readyState: document.readyState, count: document.querySelectorAll('*').length})", "returnByValue": True},
                use_session=True,
                timeout=min(TIMEOUT_EVALUATE, max(0.5, timeout - (time.perf_counter() - started))),
            )
            value = runtime.get("result", {}).get("value") or runtime.get("result", {}).get("result", {}).get("value", {})
            if isinstance(value, dict):
                last_state = str(value.get("readyState", ""))
                count = int(value.get("count", 0) or 0)
                now = time.perf_counter()
                if count == last_count:
                    if stable_since is None:
                        stable_since = now
                else:
                    last_count = count
                    stable_since = now
                if last_state in {"interactive", "complete"} and stable_since is not None and (now - stable_since) * 1000 >= quiet_ms:
                    return {"ok": True, "elapsed_ms": round((now - started) * 1000, 3), "readyState": last_state, "node_count": count}
        except Exception as error:
            return {"ok": False, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "reason": "evaluate_failed", "error": str(error)}
        await asyncio.sleep(0.25)
    return {"ok": False, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "reason": "load_wait_timeout", "readyState": last_state, "node_count": last_count}


async def run_doctor(args: argparse.Namespace) -> None:
    async with CDPConnection(
        args.cdp_url,
        command_timeout=args.command_timeout,
        target_url_contains=args.target_url_contains,
    ) as cdp:
        cdp.enable_runtime_domain = bool(getattr(args, "enable_runtime_domain", False))
        domains = await enable_page_domains(cdp)
        chromiumrl = await reset_chromiumrl_tracing(cdp, full_tracing=args.chromiumrl_full_tracing)
        state, state_timing = await timed_command(cdp, "ChromiumRL.saveDOMState", required=True, timeout=TIMEOUT_DOM_CAPTURE)
        dom_state = state.get("state", {})
        optional_methods: dict[str, Any] = {}
        for method, params, budget in (
            ("ChromiumRL.getAgentObservation", {}, TIMEOUT_OBSERVATION),
            ("ChromiumRL.getTouchTraces", {}, TIMEOUT_SIGNAL),
        ):
            value, timing = await timed_command(cdp, method, params, required=False, timeout=budget)
            optional_methods[method] = command_entry(params, timing, value)

        await cdp.send("ChromiumRL.disable", {}, use_session=True, timeout=TIMEOUT_SIGNAL)
        report = {
            "ok": True,
            "cdp_url": cdp.http_base,
            "browser": cdp.version,
            "target": cdp.target,
            "cdp_session_id": cdp.session_id,
            "domains": domains,
            "chromiumrl_enable": chromiumrl,
            "chromiumrl_save_dom_state": {
                "timing": state_timing,
                "node_count": len(state.get("state", {}).get("nodes", [])),
            },
            "chromiumrl_optional_methods": optional_methods,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))


def add_connection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cdp-url", default="http://127.0.0.1:49325")
    parser.add_argument("--command-timeout", type=float, default=30.0)
    parser.add_argument(
        "--target-url-contains",
        default="",
        help="select the first page target whose URL contains this text",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Shared desktop Wootz ChromiumRL/CDP utility commands."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="verify CDP and the ChromiumRL custom domain")
    add_connection_arguments(doctor)
    doctor.add_argument("--chromiumrl-full-tracing", action="store_true", help="enable legacy heavy ChromiumRL tracing probes")
    doctor.add_argument("--enable-runtime-domain", action="store_true", help="call Runtime.enable for debugging")
    return parser


async def async_main(args: argparse.Namespace) -> None:
    if args.command == "doctor":
        await run_doctor(args)
        return
    raise RecorderError(f"unsupported command: {args.command}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(async_main(args))
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted; already-written capture files were preserved.", file=sys.stderr)
        return 130
    except (RecorderError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
