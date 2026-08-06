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


@dataclass(frozen=True)
class ScreenshotConfig:
    source: str
    container: str
    adb_serial: str
    timeout_seconds: float
    format: str = "jpeg"
    quality: int = 80


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
  const SEL = 'a[href],button,input,select,textarea,summary,[role=button],[role=link],' +
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
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
      if (el.disabled || el.getAttribute('aria-hidden') === 'true') continue;
      const name = (el.getAttribute('aria-label') || el.innerText || el.value ||
                    el.placeholder || el.title || el.alt || '').replace(/\s+/g,' ').trim();
      const cx = ox + r.left + r.width / 2, cy = oy + r.top + r.height / 2;
      out.push({
        tag: el.tagName.toLowerCase(), role: el.getAttribute('role') || '',
        accessibleName: name.slice(0, 120), href: el.getAttribute('href') || '',
        value: (el.value || '').toString().slice(0, 80), xpath: xpath(el),
        bounds: { x: ox + r.left, y: oy + r.top, width: r.width, height: r.height },
        centerX: cx, centerY: cy,
        isInViewport: cy >= 0 && cy <= vh && cx >= 0 && cx <= vw,
        isVisible: true, isHitTestable: true
      });
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
) -> dict[str, Any]:
    page_state = page_state or {}
    if source == "js":
        payload = await collect_js_observation(cdp, label=label or directory.name)
        payload["source"] = "js_fallback"
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
            value = await chromiumrl_call(cdp, "ChromiumRL.getAgentObservation", {}, timeout=TIMEOUT_OBSERVATION, label=label or directory.name)
            chromiumrl_payload = command_entry({}, {"ok": True, "elapsed_ms": 0}, value)
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
        write_json_compact(directory / "chromiumrl_agent_observation.json", payload)
        return payload

    try:
        value = await chromiumrl_call(cdp, "ChromiumRL.getAgentObservation", {}, timeout=TIMEOUT_OBSERVATION, label=label or directory.name)
        payload = command_entry({}, {"ok": True, "elapsed_ms": 0}, value)
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
        write_json_compact(directory / "chromiumrl_agent_observation.json", payload)
        return payload
    except ChromiumRLUnavailable as error:
        if source == "chromiumrl":
            raise
        payload = await js_payload(str(error))
        write_json_compact(directory / "chromiumrl_agent_observation.json", payload)
        return payload


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
        quality = int(getattr(config, "quality", 80) or 80)
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
) -> CapturedState:
    directory.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    commands: dict[str, Any] = {}
    notes: list[str] = []
    degraded = False
    page_state: dict[str, Any] = {}
    chromiumrl_dom: dict[str, Any] = {}
    dom_captured = False

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

    commands["screenshot"] = await capture_screenshot_best_effort(cdp, directory, screenshot_config)
    if not commands["screenshot"].get("ok"):
        degraded = True
        notes.append("screenshot_failed")

    try:
        agent_observation = await collect_agent_observation(cdp, directory, source=observation_source, label=label, page_state=page_state)
    except Exception as error:
        degraded = True
        notes.append(f"observation_failed:{error}")
        agent_observation = {"source": "none", "result": {"observation": {"url": page_state.get("url", ""), "title": page_state.get("title", ""), "elements": []}}}
        write_json_compact(directory / "chromiumrl_agent_observation.json", agent_observation)
    commands["observation"] = {"ok": True, "source": agent_observation.get("source", "chromiumrl")}

    if write_dom:
        try:
            save_dom = await chromiumrl_call(cdp, "ChromiumRL.saveDOMState", {}, timeout=TIMEOUT_DOM_CAPTURE, label=label)
            chromiumrl_dom = save_dom.get("state", {}) if isinstance(save_dom, dict) else {}
            if not isinstance(chromiumrl_dom, dict):
                chromiumrl_dom = {}
            write_json_gz(directory / "chromiumrl_dom.json.gz", chromiumrl_dom)
            dom_captured = True
        except Exception as error:
            degraded = True
            notes.append(f"dom_failed:{error}")
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
    }
    return CapturedState(directory, chromiumrl_dom, page_state, index, agent_observation, degraded, notes, agent_observation.get("source", "chromiumrl"), dom_captured)


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
            "source_action_count": action_count,
            "completed_steps": 0,
        },
    )
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
