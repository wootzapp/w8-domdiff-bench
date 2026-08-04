#!/usr/bin/env python3
"""Shared desktop Wootz ChromiumRL/CDP capture utilities."""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp


SCHEMA_VERSION = "1.0"
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
COORDINATE_ACTIONS = {"left_click", "scroll", "mouse_move"}
class RecorderError(RuntimeError):
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
                max_msg_size=0,
            )

            await self.refresh_page_session()
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            await self.close()
            raise RecorderError(f"cannot connect to browser WebSocket {self.http_base}: {error}") from error
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        if self.ws is not None and not self.ws.closed:
            await self.ws.close()
        if self.http is not None and not self.http.closed:
            await self.http.close()
        self.ws = None
        self.http = None
        self.session_id = ""

    async def reconnect(self) -> None:
        await self.close()
        await self.connect()

    async def refresh_page_session(self) -> None:
        targets = await self.page_targets()
        self.target = select_page_target(targets, self.target_url_contains)
        await self.attach_to_target(self.target)

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
        self.message_id += 1
        request_id = self.message_id
        payload: dict[str, Any] = {"id": request_id, "method": method, "params": params or {}}
        if use_session:
            if not self.session_id:
                raise RecorderError(f"{method} requires an attached page session")
            payload["sessionId"] = self.session_id
        await self.ws.send_json(payload)

        deadline = timeout if timeout is not None else self.command_timeout

        async def wait_for_response() -> dict[str, Any]:
            while True:
                message = await self.ws.receive()
                if message.type == aiohttp.WSMsgType.TEXT:
                    response = json.loads(message.data)
                    if response.get("id") != request_id:
                        continue
                    if "error" in response:
                        raise CDPCommandError(method, response["error"])
                    result = response.get("result", {})
                    return result if isinstance(result, dict) else {"value": result}
                if message.type in {
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                }:
                    raise RecorderError(f"CDP WebSocket closed while waiting for {method}")

        try:
            return await asyncio.wait_for(wait_for_response(), timeout=deadline)
        except asyncio.TimeoutError as error:
            raise RecorderError(f"CDP command {method} timed out after {deadline:.1f}s") from error


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


async def capture_screenshot_best_effort(
    cdp: CDPConnection, directory: Path, screenshot_config: ScreenshotConfig
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    if screenshot_config.source == "none":
        result = {"ok": True, "skipped": True, "source": "none"}
        write_json(directory / "screenshot_skipped.json", result)
        return result

    if screenshot_config.source in {"auto", "adb"}:
        adb_attempt = await capture_adb_screenshot(screenshot_config, directory)
        attempts.append(adb_attempt)
        if adb_attempt.get("ok"):
            return {"ok": True, "source": "adb", "attempts": attempts}
        if screenshot_config.source == "adb":
            write_json(directory / "screenshot_error.json", {"ok": False, "attempts": attempts})
            return {"ok": False, "attempts": attempts, "artifact": "screenshot_error.json"}

    for params in (
        {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
        {"format": "png", "fromSurface": False, "captureBeyondViewport": False},
    ):
        started = time.perf_counter()
        try:
            screenshot = await cdp.send("Page.captureScreenshot", params, use_session=True)
            timing = {"ok": True, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
            encoded = screenshot.get("data")
            if not isinstance(encoded, str) or not encoded:
                attempts.append(
                    {
                        "source": "cdp",
                        "params": params,
                        "timing": timing,
                        "ok": False,
                        "error": "Page.captureScreenshot returned no image data",
                    }
                )
                continue
            try:
                (directory / "screenshot.png").write_bytes(base64.b64decode(encoded, validate=True))
            except (ValueError, binascii.Error) as error:
                attempts.append(
                    {
                        "source": "cdp",
                        "params": params,
                        "timing": timing,
                        "ok": False,
                        "error": f"Page.captureScreenshot returned invalid base64: {error}",
                    }
                )
                continue
            attempts.append(
                {"source": "cdp", "params": params, "timing": timing, "ok": True, "artifact": "screenshot.png"}
            )
            return {"ok": True, "source": "cdp", "attempts": attempts}
        except Exception as error:
            attempts.append(
                {
                    "source": "cdp",
                    "params": params,
                    "timing": {
                        "ok": False,
                        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                        "error": str(error),
                    },
                    "ok": False,
                    "error": str(error),
                }
            )
    write_json(directory / "screenshot_error.json", {"ok": False, "attempts": attempts})
    return {"ok": False, "attempts": attempts, "artifact": "screenshot_error.json"}


PAGE_STATE_EXPRESSION = """(() => ({
  url: location.href,
  title: document.title,
  readyState: document.readyState,
  viewport: {
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    scrollX: window.scrollX,
    scrollY: window.scrollY,
    scrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
    scrollHeight: document.documentElement ? document.documentElement.scrollHeight : 0
  }
}))()"""


async def capture_target_snapshot(
    cdp: CDPConnection,
    target: dict[str, Any],
    directory: Path,
    label: str,
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    commands: dict[str, Any] = {}
    page_state: dict[str, Any] = {}
    node_count = 0
    try:
        await cdp.attach_to_target(target)
        commands["domains"] = await enable_page_domains(cdp)
        commands["ChromiumRL.enable"] = await reset_chromiumrl_tracing(cdp)

        save_dom, commands["ChromiumRL.saveDOMState"] = await timed_command(
            cdp, "ChromiumRL.saveDOMState", required=True, label=label
        )
        chromiumrl_dom = save_dom.get("state", {})
        if not isinstance(chromiumrl_dom, dict) or not isinstance(chromiumrl_dom.get("nodes"), list):
            raise RecorderError(f"ChromiumRL.saveDOMState returned an invalid state: {save_dom}")
        node_count = len(chromiumrl_dom.get("nodes", []))
        write_json(directory / "chromiumrl_dom.json", chromiumrl_dom)

        runtime, commands["Runtime.evaluate"] = await timed_command(
            cdp,
            "Runtime.evaluate",
            {"expression": PAGE_STATE_EXPRESSION, "returnByValue": True, "awaitPromise": False},
            required=True,
            label=label,
        )
        if runtime.get("exceptionDetails"):
            raise RecorderError(f"Runtime.evaluate failed: {runtime['exceptionDetails']}")
        value = runtime.get("result", {}).get("value", {})
        if isinstance(value, dict):
            page_state = value
        write_json(directory / "page_state.json", page_state)

        agent_observation = await collect_agent_observation(cdp, directory)
        commands["ChromiumRL.getAgentObservation"] = agent_observation["timing"]

        result = {
            "ok": True,
            "target": normalize_target_info(target),
            "page": page_state,
            "node_count": node_count,
            "started_at": started_at,
            "completed_at": utc_now(),
            "commands": commands,
        }
        write_json(directory / "state_index.json", result)
        return result
    except Exception as error:
        result = {
            "ok": False,
            "target": normalize_target_info(target),
            "page": page_state,
            "node_count": node_count,
            "started_at": started_at,
            "completed_at": utc_now(),
            "commands": commands,
            "error": str(error),
        }
        write_json(directory / "capture_error.json", result)
        return result


async def capture_all_page_targets(
    cdp: CDPConnection,
    directory: Path,
    label: str,
    restore_target: dict[str, Any],
) -> dict[str, Any]:
    started_at = utc_now()
    targets = await cdp.page_targets()
    summaries: list[dict[str, Any]] = []
    for index, target in enumerate(targets, start=1):
        target_dir = directory / safe_target_dir_name(index, target)
        summaries.append(await capture_target_snapshot(cdp, target, target_dir, f"{label}/target_{index:02d}"))
    try:
        await cdp.attach_to_target(restore_target)
        await enable_page_domains(cdp)
        await reset_chromiumrl_tracing(cdp)
    except Exception as error:
        summaries.append(
            {
                "ok": False,
                "target": normalize_target_info(restore_target),
                "error": f"failed to restore main target after all-target capture: {error}",
            }
        )
    result = {
        "ok": all(item.get("ok") for item in summaries),
        "started_at": started_at,
        "completed_at": utc_now(),
        "target_count": len(targets),
        "targets": summaries,
    }
    write_json(directory / "all_targets_index.json", result)
    return result


async def enable_page_domains(cdp: CDPConnection) -> dict[str, Any]:
    outcomes: dict[str, Any] = {}
    for method, required in (
        ("Runtime.enable", True),
        ("DOM.enable", True),
    ):
        _, outcomes[method] = await timed_command(cdp, method, required=required)
    return outcomes


async def reset_chromiumrl_tracing(cdp: CDPConnection) -> dict[str, Any]:
    try:
        await cdp.send("ChromiumRL.disable", {}, use_session=True)
    except CDPCommandError:
        pass
    params = {
        "captureTouchTraces": True,
        "captureLayoutTimings": True,
        "captureCLSAttribution": True,
        "captureCompositorLayers": True,
    }
    result = await cdp.send("ChromiumRL.enable", params, use_session=True)
    trace_session_id = str(result.get("sessionId", "")).strip()
    if not trace_session_id:
        raise RecorderError(f"ChromiumRL.enable returned no sessionId: {result}")
    return result


def frame_ids(frame_tree: dict[str, Any]) -> list[str]:
    result: list[str] = []

    def visit(item: dict[str, Any]) -> None:
        frame_id = item.get("frame", {}).get("id")
        if frame_id:
            result.append(str(frame_id))
        for child in item.get("childFrames", []) or []:
            visit(child)

    root = frame_tree.get("frameTree")
    if isinstance(root, dict):
        visit(root)
    return result


@dataclass
class CapturedState:
    directory: Path
    chromiumrl_dom: dict[str, Any]
    page_state: dict[str, Any]
    index: dict[str, Any]
    agent_observation: dict[str, Any]


@dataclass(frozen=True)
class ScreenshotConfig:
    source: str
    container: str
    adb_serial: str
    timeout_seconds: float


async def capture_adb_screenshot(config: ScreenshotConfig, directory: Path) -> dict[str, Any]:
    started = time.perf_counter()
    command = [
        "docker",
        "exec",
        config.container,
        "adb",
        "-s",
        config.adb_serial,
        "exec-out",
        "screencap",
        "-p",
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=config.timeout_seconds)
    except FileNotFoundError as error:
        return {
            "source": "adb",
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"docker executable not found: {error}",
        }
    except asyncio.TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        return {
            "source": "adb",
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"adb screencap timed out after {config.timeout_seconds:.1f}s",
        }

    elapsed = round((time.perf_counter() - started) * 1000, 3)
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        return {
            "source": "adb",
            "ok": False,
            "elapsed_ms": elapsed,
            "returncode": process.returncode,
            "stderr": stderr_text,
        }
    if not stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        return {
            "source": "adb",
            "ok": False,
            "elapsed_ms": elapsed,
            "bytes": len(stdout),
            "stderr": stderr_text,
            "error": "adb screencap did not return PNG data",
        }
    (directory / "screenshot.png").write_bytes(stdout)
    return {
        "source": "adb",
        "ok": True,
        "elapsed_ms": elapsed,
        "artifact": "screenshot.png",
        "bytes": len(stdout),
        "container": config.container,
        "adb_serial": config.adb_serial,
    }


async def capture_state(
    cdp: CDPConnection,
    directory: Path,
    label: str,
    screenshot_config: ScreenshotConfig,
    *,
    capture_all_targets: bool,
) -> CapturedState:
    directory.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    commands: dict[str, Any] = {}

    save_dom, commands["ChromiumRL.saveDOMState"] = await timed_command(
        cdp, "ChromiumRL.saveDOMState", required=True, label=label
    )
    chromiumrl_dom = save_dom.get("state", {})
    if not isinstance(chromiumrl_dom, dict) or not isinstance(chromiumrl_dom.get("nodes"), list):
        raise RecorderError(f"ChromiumRL.saveDOMState returned an invalid state: {save_dom}")
    write_json(directory / "chromiumrl_dom.json", chromiumrl_dom)

    visual_hash, commands["ChromiumRL.getVisualHash"] = await timed_command(
        cdp, "ChromiumRL.getVisualHash", required=False, label=label
    )
    write_json(directory / "chromiumrl_visual_hash.json", visual_hash)

    agent_observation = await collect_agent_observation(cdp, directory)
    commands["ChromiumRL.getAgentObservation"] = agent_observation["timing"]

    runtime, commands["Runtime.evaluate"] = await timed_command(
        cdp,
        "Runtime.evaluate",
        {"expression": PAGE_STATE_EXPRESSION, "returnByValue": True, "awaitPromise": False},
        required=True,
        label=label,
    )
    if runtime.get("exceptionDetails"):
        raise RecorderError(f"Runtime.evaluate failed: {runtime['exceptionDetails']}")
    page_state = runtime.get("result", {}).get("value", {})
    if not isinstance(page_state, dict):
        raise RecorderError(f"Runtime.evaluate returned no page state: {runtime}")
    write_json(directory / "page_state.json", page_state)

    commands["screenshot"] = await capture_screenshot_best_effort(cdp, directory, screenshot_config)
    if capture_all_targets:
        commands["all_targets"] = await capture_all_page_targets(cdp, directory / "all_targets", label, cdp.target)

    artifacts: dict[str, Any] = {}
    for path in sorted(directory.iterdir()):
        if path.is_file():
            artifacts[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    index = {
        "schema_version": SCHEMA_VERSION,
        "label": label,
        "captured_at": started_at,
        "completed_at": utc_now(),
        "target": cdp.target,
        "page": page_state,
        "commands": commands,
        "artifacts": artifacts,
    }
    write_json(directory / "state_index.json", index)
    return CapturedState(directory, chromiumrl_dom, page_state, index, agent_observation)


async def capture_state_with_recovery(
    cdp: CDPConnection,
    directory: Path,
    label: str,
    screenshot_config: ScreenshotConfig,
    *,
    capture_all_targets: bool,
) -> CapturedState:
    try:
        await cdp.refresh_page_session()
        await enable_page_domains(cdp)
        await reset_chromiumrl_tracing(cdp)
        return await capture_state(
            cdp, directory, label, screenshot_config, capture_all_targets=capture_all_targets
        )
    except CDPCommandError as error:
        if not is_session_not_found(error):
            raise
        print("CDP page session was invalidated; reattaching and retrying capture once...")
        await cdp.refresh_page_session()
        await enable_page_domains(cdp)
        await reset_chromiumrl_tracing(cdp)
        return await capture_state(
            cdp, directory, label, screenshot_config, capture_all_targets=capture_all_targets
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


def element_identity(element: dict[str, Any]) -> str:
    for key in ("fingerprint", "selector", "href", "text", "accessibleName"):
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"
    node_id = element.get("nodeId")
    return f"nodeId:{node_id}"


def compact_element(element: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("idx", "nodeId", "tag", "role", "accessibleName", "text", "context", "href"):
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
        for key in ("text", "accessibleName", "href", "bounds", "centerX", "centerY"):
            if before_element.get(key) != after_element.get(key):
                changes[key] = {"before": before_element.get(key), "after": after_element.get(key)}
        if changes:
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
            "changed": before_scroll != after_scroll,
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
    elif name == "web_search":
        if "query" in action:
            result["query"] = action["query"]
        else:
            warnings.append("query is required for web_search but was missing")
    elif name == "visit_url":
        if "url" in action:
            result["url"] = action["url"]
        else:
            warnings.append("url is required for visit_url but was missing")
    elif name == "key":
        if "key" in action:
            result["key"] = action["key"]
        elif isinstance(action.get("keys"), list) and action["keys"]:
            result["key"] = action["keys"][0]
            result["_key_source"] = "keys[0]"
        else:
            warnings.append("key is required for key but was missing")
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


async def collect_agent_observation(cdp: CDPConnection, directory: Path) -> dict[str, Any]:
    value, timing = await timed_command(cdp, "ChromiumRL.getAgentObservation", required=False, label=directory.name)
    payload = command_entry({}, timing, value)
    write_json(directory / "chromiumrl_agent_observation.json", payload)
    return payload


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
    write_json(task_dir / "actions.json", source_actions)
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


async def run_doctor(args: argparse.Namespace) -> None:
    async with CDPConnection(
        args.cdp_url,
        command_timeout=args.command_timeout,
        target_url_contains=args.target_url_contains,
    ) as cdp:
        domains = await enable_page_domains(cdp)
        chromiumrl = await reset_chromiumrl_tracing(cdp)
        state, state_timing = await timed_command(cdp, "ChromiumRL.saveDOMState", required=True)
        compare_response, compare_timing = await timed_command(
            cdp,
            "ChromiumRL.compareDOMState",
            {"referenceState": state.get("state", {})},
            required=False,
            timeout=min(30.0, max(1.0, cdp.command_timeout)),
        )
        dom_state = state.get("state", {})
        node = first_visible_node(dom_state) if isinstance(dom_state, dict) else None
        node_id = node.get("nodeId") if isinstance(node, dict) else None
        optional_methods: dict[str, Any] = {}
        for method, params in (
            ("ChromiumRL.getAgentObservation", {}),
            ("ChromiumRL.getTouchTraces", {}),
        ):
            value, timing = await timed_command(cdp, method, params, required=False)
            optional_methods[method] = command_entry(params, timing, value)

        capture_params = (
            {
                "interactionType": "wait",
                "targetNodeId": node_id,
                "captureDurationMs": 1,
            }
            if isinstance(node_id, int)
            else {}
        )
        if not isinstance(node_id, int):
            optional_methods["ChromiumRL.captureInteraction"] = {"skipped": "no DOM nodeId available"}
        else:
            for method in ("ChromiumRL.captureInteraction", "ChromiumRL.captureInteractions"):
                value, timing = await timed_command(cdp, method, capture_params, required=False, timeout=2.0)
                optional_methods[method] = command_entry(capture_params, timing, value)
                if timing.get("ok"):
                    optional_methods["ChromiumRL.captureInteraction.selected"] = method
                    break
        await cdp.send("ChromiumRL.disable", {}, use_session=True)
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
            "chromiumrl_compare_dom_state": {
                "timing": compare_timing,
                "result_keys": sorted(compare_response.keys()),
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
