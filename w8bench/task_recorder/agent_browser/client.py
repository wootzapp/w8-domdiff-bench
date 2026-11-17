"""Browser observations and actions through agent-browser commands and CDP."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class AgentBrowserBaseError(Exception):
    """Base error raised by the agent-browser adapter."""


def normalized_http_url(value: str) -> str:
    """Validate a CDP HTTP endpoint and discard any accidental path/query."""
    parsed = urlsplit(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AgentBrowserBaseError(f"invalid CDP URL: {value!r}")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


class AgentBrowserError(AgentBrowserBaseError):
    """An official agent-browser command failed."""

    def __init__(self, command: list[str], error: str):
        """Preserve the failed CLI arguments and its human-readable error."""
        super().__init__(f"agent-browser {' '.join(command)!r} failed: {error}")
        self.command = command
        self.error = error


@dataclass(frozen=True)
class AgentBrowserPage:
    tab_id: str
    url: str
    title: str


@dataclass(frozen=True)
class AgentBrowserObservation:
    text: str
    refs: frozenset[str]
    origin: str
    command: tuple[str, ...]
    targets: dict[str, dict[str, str]] = field(default_factory=dict)


def agent_browser_session_name(task_id: str, process_id: int) -> str:
    """Build a short unique name that stays below Unix socket path limits."""
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:16]
    return f"rec-{digest}-{process_id}"


def container_agent_browser_command(container_name: str) -> str:
    """Build the command that invokes w8-core's bundled agent-browser."""
    name = container_name.strip()
    if not name:
        raise AgentBrowserBaseError("w8-core container name must not be empty")
    return shlex.join(["docker", "exec", name, "agent-browser"])


class AgentBrowserClient:
    """Official agent-browser CLI attached to the recorder's existing Chromium."""

    def __init__(
        self,
        command: str,
        *,
        session: str,
        cdp_url: str,
        timeout: float,
    ):
        """Configure one named official-CLI session attached to an existing CDP."""
        self.command = shlex.split(command)
        if not self.command:
            raise AgentBrowserBaseError("--agent-browser-command must not be empty")
        self.session = session
        self.timeout = timeout
        parsed = urlsplit(normalized_http_url(cdp_url))
        self.cdp_target = (
            str(parsed.port)
            if parsed.hostname in {"127.0.0.1", "localhost", "::1"} and parsed.port
            else cdp_url
        )
        self.connected = False
        self.version = ""

    def _invoke_sync(
        self,
        arguments: list[str],
        *,
        json_output: bool = True,
        use_session: bool = True,
    ) -> dict[str, Any] | list[dict[str, Any]] | str:
        """Run one CLI command, enforcing timeout, exit status, and JSON shape."""
        command = [*self.command]
        if use_session:
            command.extend(["--session", self.session])
        command.extend(arguments)
        if json_output:
            command.append("--json")
        environment = dict(os.environ)
        environment["NO_COLOR"] = "1"
        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise AgentBrowserError(
                arguments,
                f"timed out after {self.timeout:g} seconds",
            ) from error
        return self._command_output(arguments, completed, json_output)

    @staticmethod
    def _command_output(arguments: list[str], completed: Any, json_output: bool) -> dict[str, Any] | list[dict[str, Any]] | str:
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if completed.returncode != 0:
            raise AgentBrowserError(
                arguments,
                stderr or stdout or f"exit code {completed.returncode}",
            )
        if not json_output:
            return stdout
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise AgentBrowserError(
                arguments,
                f"invalid JSON output: {stdout[:2000]}",
            ) from error
        if arguments[0] == "batch" and isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            raise AgentBrowserError(arguments, "JSON output was not an object")
        if payload.get("success") is False:
            detail = payload.get("error")
            if not isinstance(detail, str):
                detail = json.dumps(detail, ensure_ascii=False)
            raise AgentBrowserError(arguments, detail or "command reported success=false")
        return payload

    async def _invoke(
        self,
        arguments: list[str],
        *,
        json_output: bool = True,
        use_session: bool = True,
    ) -> dict[str, Any] | list[dict[str, Any]] | str:
        """Run the blocking CLI subprocess on a worker thread."""
        return await asyncio.to_thread(
            self._invoke_sync,
            arguments,
            json_output=json_output,
            use_session=use_session,
        )

    async def connect(self) -> None:
        """Check the official CLI version and attach the named session to CDP."""
        version = await self._invoke(
            ["--version"],
            json_output=False,
            use_session=False,
        )
        self.version = str(version).strip()
        await self.reconnect()

    async def reconnect(self) -> None:
        """Reattach the named CLI session without closing the browser target."""
        result = await self._invoke(["connect", self.cdp_target])
        assert isinstance(result, dict)
        self.connected = True

    async def close(self) -> None:
        """Close only this CLI session; failures during cleanup are non-fatal."""
        if not self.connected:
            return
        try:
            await self._invoke(["close"], json_output=False)
        except BaseException:
            pass
        self.connected = False

    async def _viewport_geometry(self, targets: dict) -> tuple[dict, dict | None]:
        viewport = None
        # Batch read-only checks: no extra snapshots (which would replace
        # the ref map), no per-ref subprocesses, and no scroll-into-view.
        boxes: dict[str, dict[str, float]] = {}
        ordered_refs = list(targets)
        for start in range(0, len(ordered_refs), 128):
            chunk = ordered_refs[start:start + 128]
            checks = ["batch", shlex.join(["eval",
                "({width:innerWidth,height:innerHeight})"]),
                *(shlex.join(["get", "box", f"@{ref}"]) for ref in chunk)]
            results = await self._invoke(checks)
            if not isinstance(results, list) or len(results) != len(chunk) + 1:
                raise AgentBrowserError(checks, "invalid viewport geometry batch")
            viewport_row = results[0]
            viewport_result = viewport_row.get("result") if isinstance(viewport_row, dict) else None
            viewport = viewport_result.get("result") if isinstance(viewport_result, dict) else None
            if (not isinstance(viewport_row, dict) or viewport_row.get("success") is not True
                    or not isinstance(viewport, dict)
                    or any(not isinstance(viewport.get(key), (int, float))
                        or not math.isfinite(viewport[key]) or viewport[key] <= 0
                        for key in ("width", "height"))):
                raise AgentBrowserError(checks, "viewport dimensions unavailable")
            for ref, row in zip(chunk, results[1:]):
                box = row.get("result") if isinstance(row, dict) else None
                if not isinstance(row, dict) or row.get("success") is not True or not isinstance(box, dict):
                    raise AgentBrowserError(checks, f"viewport geometry unavailable for @{ref}")
                if any(not isinstance(box.get(key), (int, float)) or not math.isfinite(box[key])
                       for key in ("x", "y", "width", "height")):
                    raise AgentBrowserError(checks, f"invalid viewport geometry for @{ref}")
                boxes[ref] = box
        return boxes, viewport

    def _visible_snapshot(self, snapshot: str, targets: dict, boxes: dict, viewport: dict | None) -> tuple[str, dict]:
        # Keep only ref-bearing lines. Non-ref structural/context lines can
        # contain full-page text even after offscreen target refs are gone.
        lines = []
        # Child-frame boxes are frame-local, not top-level viewport
        # coordinates. Snapshot indentation identifies their frame owner.
        frames: list[tuple[int, float, float, tuple[float, float, float, float]]] = []
        for line in snapshot.splitlines():
            indent = len(line) - len(line.lstrip())
            while frames and frames[-1][0] >= indent:
                frames.pop()
            line_refs = re.findall(r"\[ref=(@?e\d+)\]", line)
            if len(line_refs) != 1:
                continue
            ref = self.action_ref(line_refs[0])
            box = boxes.get(ref)
            if box is None:
                continue
            offset_x, offset_y = (frames[-1][1], frames[-1][2]) if frames else (0, 0)
            clip = frames[-1][3] if frames else (0, 0, viewport["width"], viewport["height"])
            x, y = box["x"] + offset_x, box["y"] + offset_y
            intersection = (max(x, clip[0]), max(y, clip[1]),
                min(x + box["width"], clip[2]), min(y + box["height"], clip[3]))
            if targets[ref]["role"].lower() == "iframe":
                frames.append((indent, x, y, intersection))
            if intersection[2] > intersection[0] and intersection[3] > intersection[1]:
                lines.append(line)
        snapshot = "\n".join(lines) or "[No executable targets overlap the viewport.]"
        emitted_refs = {self.action_ref(ref) for ref in re.findall(r"\[ref=(@?e\d+)\]", snapshot)}
        targets = {ref: target for ref, target in targets.items() if ref in emitted_refs}
        return snapshot, targets

    async def snapshot(self) -> AgentBrowserObservation:
        """Capture viewport-overlapping executable refs without scrolling."""
        arguments = ["snapshot", "-i"]
        payload = await self._invoke(arguments)
        assert isinstance(payload, dict)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise AgentBrowserError(arguments, "response contains no data object")
        snapshot = data.get("snapshot")
        refs = data.get("refs")
        if not isinstance(snapshot, str) or not isinstance(refs, dict):
            raise AgentBrowserError(
                arguments,
                "response does not contain snapshot text and refs",
            )
        targets: dict[str, dict[str, str]] = {}
        for raw_ref, raw_target in refs.items():
            ref = self.action_ref(raw_ref)
            if not ref or not isinstance(raw_target, dict):
                continue
            targets[ref] = {
                "role": str(raw_target.get("role", "")),
                "name": str(raw_target.get("name", "")),
            }
        boxes, viewport = await self._viewport_geometry(targets)
        snapshot, targets = self._visible_snapshot(snapshot, targets, boxes, viewport)
        return AgentBrowserObservation(
            text=snapshot.rstrip() + "\n",
            refs=frozenset(targets),
            targets=targets,
            origin=str(data.get("origin", "")),
            command=tuple(arguments),
        )


    async def active_page(self) -> AgentBrowserPage:
        """Return the official agent-browser session's one active tab."""
        arguments = ["tab", "list"]
        payload = await self._invoke(arguments)
        assert isinstance(payload, dict)
        data = payload.get("data")
        tabs = data.get("tabs") if isinstance(data, dict) else None
        if not isinstance(tabs, list):
            raise AgentBrowserError(arguments, "response contains no tabs list")
        active_tabs = [
            item
            for item in tabs
            if isinstance(item, dict)
            and item.get("active") is True
            and item.get("type", "page") == "page"
        ]
        if len(active_tabs) != 1:
            raise AgentBrowserError(
                arguments,
                f"expected exactly one active page tab, found {len(active_tabs)}",
            )
        active = active_tabs[0]
        tab_id = str(active.get("tabId", "")).strip()
        url = str(active.get("url", "")).strip()
        if not tab_id or not url:
            raise AgentBrowserError(
                arguments,
                "active tab is missing tabId or url",
            )
        return AgentBrowserPage(
            tab_id=tab_id,
            url=url,
            title=str(active.get("title", "")).strip(),
        )

    @staticmethod
    def action_ref(value: Any) -> str:
        """Normalize either eN or @eN into the ref form stored in artifacts."""
        ref = "" if value is None else str(value).strip()
        return ref[1:] if ref.startswith("@") else ref

    @staticmethod
    async def _dispatch_pointer(decision: dict, cdp: Any, viewport: tuple[int, int]) -> None:
        action = decision["action"]
        x = decision.get("x")
        y = decision.get("y")
        if x is None: x = viewport[0] / 2
        if y is None: y = viewport[1] / 2
        await cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        if action == "click":
            await cdp.call("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
            await cdp.call("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
        else:
            await cdp.call("Input.dispatchMouseEvent", {
                "type": "mouseWheel", "x": x, "y": y,
                "deltaX": 0, "deltaY": decision["pixels"]})

    @staticmethod
    async def _dispatch_key(decision: dict, cdp: Any) -> None:
        parts = str(decision["key"]).split("+")
        aliases = {"CTRL": "Control", "CONTROL": "Control", "ALT": "Alt",
            "SHIFT": "Shift", "META": "Meta", "CMD": "Meta", "COMMAND": "Meta"}
        modifiers = 0
        for part in parts[:-1]:
            name = aliases.get(part.upper())
            if name is None:
                raise AgentBrowserBaseError(f"unsupported key modifier: {part}")
            modifiers |= {"Alt": 1, "Control": 2, "Meta": 4, "Shift": 8}[name]
        key = parts[-1]
        key = {"ESC": "Escape", "SPACE": " ", "ARROWUP": "ArrowUp",
            "ARROWDOWN": "ArrowDown", "ARROWLEFT": "ArrowLeft",
            "ARROWRIGHT": "ArrowRight", "ENTER": "Enter", "TAB": "Tab",
            "BACKSPACE": "Backspace", "DELETE": "Delete", "HOME": "Home",
            "END": "End", "PAGEUP": "PageUp", "PAGEDOWN": "PageDown"}.get(key.upper(), key)
        code = {"Enter": 13, "Tab": 9, "Backspace": 8, "Delete": 46,
            "Escape": 27, " ": 32, "ArrowLeft": 37, "ArrowUp": 38,
            "ArrowRight": 39, "ArrowDown": 40, "Home": 36, "End": 35,
            "PageUp": 33, "PageDown": 34}.get(key)
        if code is None and len(key) == 1 and key.isascii() and key.isalnum():
            code = ord(key.upper())
        if code is None:
            raise AgentBrowserBaseError(f"unsupported key: {key}")
        params = {"key": key, "windowsVirtualKeyCode": code, "modifiers": modifiers}
        if not modifiers and (len(key) == 1 or key == "Enter"):
            params["text"] = "\r" if key == "Enter" else key
        await cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **params})
        await cdp.call("Input.dispatchKeyEvent", {
            "type": "keyUp", **{k: v for k, v in params.items() if k != "text"}})

    async def _execute_input(self, decision: dict, cdp: Any, viewport: tuple[int, int]) -> dict:
        # Coordinate and focused-keyboard actions use browser input events only: no locators,
        # accessibility tree, Runtime.evaluate, or DOM-based hit testing.
        # Both modes share these primitives; only DOM refs use the CLI.
        action = decision["action"]
        if action == "navigate":
            result = await cdp.call("Page.navigate", {"url": decision["url"]})
            if result.get("errorText"):
                raise AgentBrowserBaseError(result["errorText"])
        elif action == "back":
            history = await cdp.call("Page.getNavigationHistory")
            index = int(history["currentIndex"]) - 1
            if index < 0:
                raise AgentBrowserBaseError("no previous navigation entry")
            await cdp.call("Page.navigateToHistoryEntry", {"entryId": history["entries"][index]["id"]})
        elif action in {"click", "scroll"}:
            await self._dispatch_pointer(decision, cdp, viewport)
        elif action == "type":
            await cdp.call("Input.insertText", {"text": decision["text"]})
        elif action == "press":
            await self._dispatch_key(decision, cdp)
        elif action == "wait":
            await asyncio.sleep(decision["seconds"])
        else:
            raise AgentBrowserBaseError(f"action {action!r} is not executable")
        # Event delivery is not confirmation of a page-level outcome.
        return {"success": True, "status": "input_dispatched"}

    async def execute(self, decision: dict[str, Any], *, cdp: Any,
                      viewport: tuple[int, int] = (1365, 768)) -> dict[str, Any] | str:
        """Map one action to browser input and report delivery.

        Reference clicks use the CLI. A reference-targeted scroll first hovers
        the ref and then scrolls so nested panes can receive input. Actions
        without a reference use CDP input or a local wait.
        """
        if decision.get("id") is None:
            return await self._execute_input(decision, cdp, viewport)
        action = str(decision["action"])
        ref = self.action_ref(decision.get("id"))
        selector = f"@{ref}" if ref else ""
        if action == "click":
            return await self._invoke(["click", selector])
        if action == "scroll":
            raw_pixels = (
                800.0
                if decision.get("pixels") is None
                else float(decision.get("pixels"))
            )
            direction = "down" if raw_pixels >= 0 else "up"
            magnitude = max(1, round(abs(raw_pixels)))
            arguments = ["scroll", direction, str(magnitude)]
            hover_issued = bool(selector)
            if selector:
                # scroll --selector accepts CSS, whereas @eN is an agent-browser
                # snapshot ref. Hovering a ref places the pointer over that
                # element; the subsequent wheel command is then dispatched to
                # the element under the pointer, including nested scroll panes.
                await self._invoke(["hover", selector])
            result = await self._invoke(arguments)
            assert isinstance(result, dict)
            return {
                **result,
                "normalized_parameters": {
                    "pixels": magnitude if direction == "down" else -magnitude,
                },
                "hover_issued": hover_issued,
            }
        raise AgentBrowserBaseError(f"action {action!r} is not executable")
