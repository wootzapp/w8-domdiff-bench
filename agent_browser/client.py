"""Thin adapter around the official agent-browser CLI.

This module owns only browser observation and action execution through the
official CLI. ChromiumRL capture, DOM diffing, screenshots, and run artifacts
remain the recorder's responsibility.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

# Shared recorder exception keeps adapter failures compatible with runner/CLI
# error handling without importing either higher-level module.
from recorder_errors import RunnerError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AgentBrowserError(RunnerError):
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


def normalized_http_url(value: str) -> str:
    """Normalize a valid CDP HTTP endpoint while rejecting other URL schemes."""
    parsed = urlsplit(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RunnerError(f"invalid CDP URL: {value!r}")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


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
            raise RunnerError("--agent-browser-command must not be empty")
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
        self.connection_result: dict[str, Any] = {}
        self.reconnect_count = 0

    def _invoke_sync(
        self,
        arguments: list[str],
        *,
        json_output: bool = True,
        use_session: bool = True,
    ) -> dict[str, Any] | str:
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
    ) -> dict[str, Any] | str:
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
        result = await self._invoke(["connect", self.cdp_target])
        assert isinstance(result, dict)
        self.connection_result = result
        self.connected = True

    async def reconnect(self) -> None:
        """Reattach the named CLI session without closing the browser target."""
        result = await self._invoke(["connect", self.cdp_target])
        assert isinstance(result, dict)
        self.connection_result = result
        self.connected = True
        self.reconnect_count += 1

    async def close(self) -> None:
        """Close only this CLI session; failures during cleanup are non-fatal."""
        if not self.connected:
            return
        try:
            await self._invoke(["close"], json_output=False)
        except BaseException:
            pass
        self.connected = False

    async def snapshot(self, *, interactive: bool = False) -> AgentBrowserObservation:
        """Capture compact evidence or the interactive ref namespace used to act."""
        # Keep the compact tree as the complete recorded accessibility evidence.
        # The separate interactive tree is the action namespace supplied to the
        # model and is captured last, so its refs are exactly the refs executed.
        arguments = ["snapshot", "-i"] if interactive else ["snapshot", "-c"]
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
        return AgentBrowserObservation(
            text=snapshot.rstrip() + "\n",
            refs=frozenset(self.action_ref(ref) for ref in refs),
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

    async def execute(self, decision: dict[str, Any]) -> dict[str, Any] | str:
        """Map one validated model action to exactly one official CLI operation."""
        action = str(decision["action"])
        ref = self.action_ref(decision.get("id"))
        selector = f"@{ref}" if ref else ""
        text = "" if decision.get("text") is None else str(decision.get("text"))

        if action == "navigate":
            url = "" if decision.get("url") is None else str(decision.get("url")).strip()
            if not url.startswith(("http://", "https://")):
                raise RunnerError("navigate requires an http(s) URL")
            return await self._invoke(["open", url])
        if action == "back":
            return await self._invoke(["back"])
        if action == "click":
            return await self._invoke(["click", selector])
        if action == "fill":
            return await self._invoke(["fill", selector, text])
        if action == "type":
            if selector:
                return await self._invoke(["type", selector, text])
            return await self._invoke(["keyboard", "type", text])
        if action == "select":
            return await self._invoke(["select", selector, text])
        if action == "press":
            key = "" if decision.get("key") is None else str(decision.get("key"))
            return await self._invoke(["press", key])
        if action == "scroll":
            raw_pixels = (
                800.0
                if decision.get("pixels") is None
                else float(decision.get("pixels"))
            )
            direction = "down" if raw_pixels >= 0 else "up"
            arguments = ["scroll", direction, str(max(1, round(abs(raw_pixels))))]
            if selector:
                # scroll --selector accepts CSS, whereas @eN is an agent-browser
                # snapshot ref. Hovering a ref places the pointer over that
                # element; the subsequent wheel command is then dispatched to
                # the element under the pointer, including nested scroll panes.
                await self._invoke(["hover", selector])
            return await self._invoke(arguments)
        if action == "wait":
            raw_seconds = (
                1.0
                if decision.get("seconds") is None
                else float(decision.get("seconds"))
            )
            milliseconds = round(1000 * min(10.0, max(0.0, raw_seconds)))
            return await self._invoke(["wait", str(milliseconds)])
        raise RunnerError(f"action {action!r} is not executable")
