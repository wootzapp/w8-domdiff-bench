#!/usr/bin/env python3
"""Desktop Wootz agent-browser runner.

DOM collection is not shortcut or synthetic. Every recorded step uses the
task-recorder's ChromiumRL saveDOMState/getAgentObservation/compareDOMState
flow and writes the standard verifier artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recorder import (  # noqa: E402
    CDPCommandError,
    CDPConnection,
    RecorderError,
    SCHEMA_VERSION,
    ScreenshotConfig,
    action_name,
    append_jsonl,
    artifact_record,
    build_dom_diff_summary,
    build_verifier_action,
    capture_state_with_recovery,
    collect_chromiumrl_signals,
    collect_interaction_capture,
    command_entry,
    enable_page_domains,
    initialize_task,
    is_session_not_found,
    reset_chromiumrl_tracing,
    target_id,
    step_numbers,
    timed_command,
    update_manifest,
    utc_now,
    write_json,
)


SYSTEM_PROMPT = """You are controlling a desktop Wootz browser through an agent-browser style SDK.

Return exactly one JSON object and no markdown.

Use the snapshot refs when possible. Coordinates are allowed only when no useful ref/selector exists.

Allowed actions:
- {"action":"open","url":"https://...","thoughts":"..."}
- {"action":"navigate","url":"https://...","thoughts":"..."}
- {"action":"click","ref":"e12","thoughts":"..."}
- {"action":"click","selector":"button[name='add']","thoughts":"..."}
- {"action":"left_click","coordinate":[x,y],"thoughts":"..."}
- {"action":"type","text":"search query","thoughts":"..."}
- {"action":"fill","ref":"e3","text":"input text","thoughts":"..."}
- {"action":"press","key":"Enter","thoughts":"..."}
- {"action":"scroll","pixels":700,"thoughts":"..."}  // positive = down, negative = up
- {"action":"wait","seconds":2,"thoughts":"..."}
- {"action":"terminate","status":"success|failure","final_answer":"...","thoughts":"..."}

Rules:
- Prefer click/fill by ref from the snapshot.
- If a modal, consent dialog, popup, interstitial, ad, login prompt, or overlay blocks the page, choose an action that dismisses or handles the blocker before continuing with the task.
- If recent action outcomes say there was no visible progress, do not repeat the same action on the same target. Change strategy: use search/navigation, choose a different visible control, scroll to new content, go back, or terminate if the task is impossible.
- Use open/navigate for the first URL if the browser is blank.
- Stop only after the task is visibly complete or impossible.
"""


KEY_CODES = {
    "Enter": "Enter",
    "Escape": "Escape",
    "Tab": "Tab",
    "Backspace": "Backspace",
    "Delete": "Delete",
    "Home": "Home",
    "End": "End",
    "ArrowDown": "ArrowDown",
    "ArrowUp": "ArrowUp",
    "ArrowLeft": "ArrowLeft",
    "ArrowRight": "ArrowRight",
}


@dataclass
class Snapshot:
    text: str
    payload: dict[str, Any]
    refs: dict[str, dict[str, Any]]


class ScrollFallbackUsed(RecorderError):
    """Raised after a scroll fallback succeeds so metadata can record it."""


def load_env_file(path: Path) -> None:
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


def truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...<truncated {len(value) - limit} chars>"


def require_number_pair(value: Any, field: str) -> tuple[float, float]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not isinstance(value[0], (int, float))
        or not isinstance(value[1], (int, float))
    ):
        raise RecorderError(f"{field} must be [x, y], got {value!r}")
    return float(value[0]), float(value[1])


def get_observation_dict(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result", {})
    observation = result.get("observation", result)
    if not isinstance(observation, dict):
        raise RecorderError(f"ChromiumRL.getAgentObservation returned unexpected payload: {payload}")
    return observation


def first_number(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, (int, float)):
            return float(value)
    return None


def element_center(element: dict[str, Any]) -> tuple[float, float] | None:
    x = first_number(element.get("centerX"), element.get("x"))
    y = first_number(element.get("centerY"), element.get("y"))
    if x is not None and y is not None:
        return x, y

    bounds = element.get("bounds") or element.get("boundingBox") or element.get("rect")
    if isinstance(bounds, dict):
        left = first_number(bounds.get("x"), bounds.get("left"))
        top = first_number(bounds.get("y"), bounds.get("top"))
        width = first_number(bounds.get("width"))
        height = first_number(bounds.get("height"))
        right = first_number(bounds.get("right"))
        bottom = first_number(bounds.get("bottom"))
        if left is not None and top is not None and width is not None and height is not None:
            return left + width / 2, top + height / 2
        if left is not None and top is not None and right is not None and bottom is not None:
            return (left + right) / 2, (top + bottom) / 2
    return None


def short(value: Any, limit: int = 80) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def element_label(element: dict[str, Any]) -> str:
    for key in ("accessibleName", "name", "text", "label", "placeholder", "value", "href"):
        value = short(element.get(key))
        if value:
            return value
    return ""


def normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise RecorderError(f"agent action must be a JSON object, got {action!r}")
    normalized = dict(action)
    name = action_name(normalized)
    aliases = {
        "visit_url": "navigate",
        "open_url": "navigate",
        "open": "navigate",
        "left_click": "click",
        "key": "press",
    }
    normalized["action"] = aliases.get(name, name)
    normalized.setdefault("thoughts", "Automated browser action")
    return normalized


def action_signature(action: dict[str, Any]) -> dict[str, Any]:
    """Small stable identity used only for generic loop detection."""

    name = action_name(action)
    signature: dict[str, Any] = {"action": name}
    for key in ("ref", "selector", "url", "key", "pixels", "text"):
        if key in action:
            value = action.get(key)
            if isinstance(value, str):
                value = value[:120]
            signature[key] = value
    if "coordinate" in action:
        coordinate = action.get("coordinate")
        if isinstance(coordinate, list) and len(coordinate) == 2:
            signature["coordinate"] = [round(float(coordinate[0])), round(float(coordinate[1]))]
    return signature


def page_scroll_y(page: dict[str, Any]) -> Any:
    viewport = page.get("viewport")
    return viewport.get("scrollY") if isinstance(viewport, dict) else None


def build_step_outcome(
    action: dict[str, Any],
    before_page: dict[str, Any],
    after_page: dict[str, Any],
    dom_diff_summary: dict[str, Any],
) -> dict[str, Any]:
    """Summarize whether a completed step changed observable page state.

    This is intentionally generic. It does not inspect website names, product
    names, cookie labels, or task-specific text.
    """

    stats = dom_diff_summary.get("stats", {}) if isinstance(dom_diff_summary.get("stats"), dict) else {}
    visible_text_added = dom_diff_summary.get("visible_text_added")
    visible_text_removed = dom_diff_summary.get("visible_text_removed")
    interactive_added = dom_diff_summary.get("interactive_added")
    interactive_removed = dom_diff_summary.get("interactive_removed")
    interactive_changed = dom_diff_summary.get("interactive_changed")
    url_changed = bool((dom_diff_summary.get("url") or {}).get("changed"))
    title_changed = bool((dom_diff_summary.get("title") or {}).get("changed"))
    scroll_changed = bool((dom_diff_summary.get("scroll") or {}).get("changed"))
    element_delta = sum(
        int(stats.get(key) or 0)
        for key in ("elements_added", "elements_removed", "elements_changed")
        if isinstance(stats.get(key), int)
    )
    visible_delta = (
        len(visible_text_added) if isinstance(visible_text_added, list) else 0
    ) + (
        len(visible_text_removed) if isinstance(visible_text_removed, list) else 0
    )
    interactive_delta = (
        len(interactive_added) if isinstance(interactive_added, list) else 0
    ) + (
        len(interactive_removed) if isinstance(interactive_removed, list) else 0
    ) + (
        len(interactive_changed) if isinstance(interactive_changed, list) else 0
    )
    made_progress = bool(url_changed or title_changed or scroll_changed or element_delta or visible_delta or interactive_delta)
    return {
        "action_signature": action_signature(action),
        "made_visible_progress": made_progress,
        "url_changed": url_changed,
        "title_changed": title_changed,
        "scroll_changed": scroll_changed,
        "element_delta_count": element_delta,
        "visible_text_delta_count": visible_delta,
        "interactive_delta_count": interactive_delta,
        "before": {
            "url": before_page.get("url"),
            "title": before_page.get("title"),
            "scrollY": page_scroll_y(before_page),
        },
        "after": {
            "url": after_page.get("url"),
            "title": after_page.get("title"),
            "scrollY": page_scroll_y(after_page),
        },
    }


def progress_warnings(history: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    completed = [
        item
        for item in history
        if item.get("approved") is True and isinstance(item.get("outcome"), dict)
    ]
    if not completed:
        return warnings

    last = completed[-1]["outcome"]
    if last.get("made_visible_progress") is False:
        signature = last.get("action_signature", {})
        warnings.append(
            "The previous approved action made no visible progress. Do not repeat "
            f"the same target/action: {json.dumps(signature, ensure_ascii=False)}"
        )

    recent = completed[-5:]
    signatures = [json.dumps((item.get("outcome") or {}).get("action_signature", {}), sort_keys=True) for item in recent]
    no_progress = [bool((item.get("outcome") or {}).get("made_visible_progress") is False) for item in recent]
    if len(recent) >= 3 and len(set(signatures[-3:])) == 1 and all(no_progress[-3:]):
        warnings.append(
            "The same action has failed to change the page for three consecutive approved steps. "
            "Choose a different strategy now instead of retrying it."
        )
    elif len(recent) >= 4 and sum(no_progress[-4:]) >= 3:
        warnings.append(
            "Most recent approved steps made no visible progress. Reassess the page and change strategy."
        )

    repeated: dict[str, dict[str, Any]] = {}
    for item in completed[-12:]:
        outcome = item.get("outcome") or {}
        signature = outcome.get("action_signature") if isinstance(outcome, dict) else {}
        if not isinstance(signature, dict):
            continue
        if signature.get("action") not in {"click", "left_click", "fill", "press"}:
            continue
        key = json.dumps(signature, sort_keys=True)
        record = repeated.setdefault(
            key,
            {
                "count": 0,
                "signature": signature,
                "url_or_title_changed": False,
                "scroll_changed": False,
            },
        )
        record["count"] += 1
        record["url_or_title_changed"] = bool(
            record["url_or_title_changed"] or outcome.get("url_changed") or outcome.get("title_changed")
        )
        record["scroll_changed"] = bool(record["scroll_changed"] or outcome.get("scroll_changed"))
    for record in repeated.values():
        if record["count"] >= 3 and not record["url_or_title_changed"] and not record["scroll_changed"]:
            warnings.append(
                "A recent click/fill/key target has been retried multiple times without URL, title, or scroll progress. "
                f"Do not retry it: {json.dumps(record['signature'], ensure_ascii=False)}"
            )
            break
    return warnings


def fallback_dom_diff_summary(before_page: dict[str, Any], after_page: dict[str, Any]) -> dict[str, Any]:
    before_viewport = before_page.get("viewport") if isinstance(before_page.get("viewport"), dict) else {}
    after_viewport = after_page.get("viewport") if isinstance(after_page.get("viewport"), dict) else {}
    return {
        "url": {"changed": before_page.get("url") != after_page.get("url")},
        "title": {"changed": before_page.get("title") != after_page.get("title")},
        "scroll": {"changed": before_viewport != after_viewport},
        "stats": {},
        "visible_text_added": [],
        "visible_text_removed": [],
        "interactive_added": [],
        "interactive_removed": [],
        "interactive_changed": [],
    }


def outcome_from_trajectory_item(task_dir: Path, item: dict[str, Any], action: dict[str, Any]) -> dict[str, Any] | None:
    existing = item.get("outcome")
    if isinstance(existing, dict):
        return existing

    before_page = item.get("before_page") if isinstance(item.get("before_page"), dict) else {}
    after_page = item.get("after_page") if isinstance(item.get("after_page"), dict) else {}
    if not before_page and not after_page:
        return None

    summary = fallback_dom_diff_summary(before_page, after_page)
    artifact_dir = item.get("artifacts_directory")
    if isinstance(artifact_dir, str) and artifact_dir:
        summary_path = task_dir / artifact_dir / "dom_diff_summary.json"
        if summary_path.exists():
            try:
                loaded = json.loads(summary_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    summary = loaded
            except json.JSONDecodeError:
                pass
    return build_step_outcome(action, before_page, after_page, summary)


async def apply_language_overrides(cdp: CDPConnection, *, locale: str, accept_language: str) -> dict[str, Any]:
    outcomes: dict[str, Any] = {}
    if accept_language:
        try:
            await cdp.send("Network.enable", {}, use_session=True, timeout=5.0)
            outcomes["Network.enable"] = {"ok": True}
        except Exception as error:
            outcomes["Network.enable"] = {"ok": False, "error": str(error)}
        try:
            await cdp.send(
                "Network.setExtraHTTPHeaders",
                {"headers": {"Accept-Language": accept_language}},
                use_session=True,
                timeout=5.0,
            )
            outcomes["Network.setExtraHTTPHeaders"] = {"ok": True, "accept_language": accept_language}
        except Exception as error:
            outcomes["Network.setExtraHTTPHeaders"] = {"ok": False, "error": str(error)}
    if locale:
        try:
            await cdp.send("Emulation.setLocaleOverride", {"locale": locale}, use_session=True, timeout=5.0)
            outcomes["Emulation.setLocaleOverride"] = {"ok": True, "locale": locale}
        except Exception as error:
            outcomes["Emulation.setLocaleOverride"] = {"ok": False, "error": str(error)}
    return outcomes


class DesktopWootzAgent:
    """Agent-browser style controller backed by desktop Wootz CDP."""

    def __init__(
        self,
        cdp: CDPConnection,
        input_timeout: float = 8.0,
        *,
        browser_locale: str = "en-US",
        accept_language: str = "en-US,en;q=0.9",
    ):
        self.cdp = cdp
        self.input_timeout = input_timeout
        self.browser_locale = browser_locale
        self.accept_language = accept_language
        self._last_snapshot: Snapshot | None = None

    async def apply_language_overrides(self) -> dict[str, Any]:
        return await apply_language_overrides(
            self.cdp,
            locale=self.browser_locale,
            accept_language=self.accept_language,
        )

    async def snapshot(self, max_elements: int = 120) -> Snapshot:
        value, timing = await timed_command(self.cdp, "ChromiumRL.getAgentObservation", required=True)
        payload = command_entry({}, timing, value)
        observation = get_observation_dict(payload)
        elements = observation.get("elements", [])
        visible_text_blocks = await self.visible_text_blocks(max_blocks=max_elements)
        refs: dict[str, dict[str, Any]] = {}
        lines = [
            f"url: {observation.get('url', '')}",
            f"title: {observation.get('title', '')}",
        ]
        scroll = observation.get("scroll")
        if scroll is not None:
            lines.append(f"scroll: {scroll}")
        lines.append("elements:")

        if isinstance(elements, list):
            ref_num = 1
            for element in elements:
                if not isinstance(element, dict):
                    continue
                if element.get("isVisible") is False or element.get("isInViewport") is False:
                    continue
                ref = f"e{ref_num}"
                ref_num += 1
                refs[ref] = element
                role = short(element.get("role") or element.get("tag") or element.get("nodeName") or "element", 32)
                label = element_label(element)
                center = element_center(element)
                center_text = f" center=[{round(center[0])},{round(center[1])}]" if center else ""
                href = short(element.get("href"), 90)
                href_text = f" href={json.dumps(href, ensure_ascii=False)}" if href else ""
                lines.append(f"  - [ref={ref}] {role} {json.dumps(label, ensure_ascii=False)}{center_text}{href_text}")
                if len(refs) >= max_elements:
                    break

        if visible_text_blocks:
            lines.append("visible_text:")
            for block in visible_text_blocks[:max_elements]:
                tag = short(block.get("tag", "text"), 24)
                text = short(block.get("text", ""), 220)
                center = block.get("center")
                center_text = ""
                if isinstance(center, list) and len(center) == 2:
                    center_text = f" center=[{round(center[0])},{round(center[1])}]"
                lines.append(f"  - {tag}{center_text}: {json.dumps(text, ensure_ascii=False)}")

        snapshot = Snapshot(
            text="\n".join(lines),
            payload={**payload, "visible_text_blocks": visible_text_blocks},
            refs=refs,
        )
        self._last_snapshot = snapshot
        return snapshot

    async def visible_text_blocks(self, max_blocks: int = 120) -> list[dict[str, Any]]:
        expression = """
        (() => {
          const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
          const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
          const candidates = Array.from(document.body ? document.body.querySelectorAll('*') : []);
          const blocks = [];
          const seen = new Set();
          for (const el of candidates) {
            const tag = (el.tagName || '').toLowerCase();
            if (['script', 'style', 'noscript', 'svg', 'path', 'img', 'video', 'canvas'].includes(tag)) continue;
            const rect = el.getBoundingClientRect();
            if (!rect || rect.width <= 0 || rect.height <= 0) continue;
            if (rect.bottom < 0 || rect.top > viewportHeight || rect.right < 0 || rect.left > viewportWidth) continue;
            const style = window.getComputedStyle(el);
            if (!style || style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) continue;
            let text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
            if (text.length < 2) continue;
            if (text.length > 260) text = text.slice(0, 260);
            const childTexts = Array.from(el.children || [])
              .map((child) => (child.innerText || child.textContent || '').replace(/\\s+/g, ' ').trim())
              .filter(Boolean);
            if (childTexts.some((childText) => childText === text)) continue;
            const key = tag + '|' + text;
            if (seen.has(key)) continue;
            seen.add(key);
            blocks.push({
              tag,
              role: el.getAttribute('role') || '',
              text,
              center: [rect.left + rect.width / 2, rect.top + rect.height / 2],
            });
            if (blocks.length >= %d) break;
          }
          return blocks;
        })()
        """ % max(1, int(max_blocks))
        try:
            response = await self.cdp.send(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
                use_session=True,
                timeout=min(self.input_timeout, 5.0),
            )
        except Exception:
            return []
        value = response.get("result", {}).get("result", {}).get("value", [])
        return value if isinstance(value, list) else []

    async def navigate(self, url: str) -> None:
        if not url:
            raise RecorderError("navigate/open action requires url")
        await self.cdp.send("Page.navigate", {"url": url}, use_session=True)

    async def click(self, *, ref: str | None = None, selector: str | None = None, coordinate: Any = None) -> tuple[float, float]:
        x, y = await self.resolve_point(ref=ref, selector=selector, coordinate=coordinate)
        await self.cdp.send(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": x, "y": y},
            use_session=True,
            timeout=self.input_timeout,
        )
        await self.cdp.send(
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
            use_session=True,
            timeout=self.input_timeout,
        )
        await self.cdp.send(
            "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1},
            use_session=True,
            timeout=self.input_timeout,
        )
        return x, y

    async def type_text(self, text: str) -> None:
        if text:
            await self.cdp.send("Input.insertText", {"text": text}, use_session=True, timeout=self.input_timeout)

    async def fill(self, *, text: str, ref: str | None = None, selector: str | None = None, coordinate: Any = None) -> None:
        await self.click(ref=ref, selector=selector, coordinate=coordinate)
        await self.press("Control+A")
        await self.press("Backspace")
        await self.type_text(text)

    async def press(self, key: str) -> None:
        if not key:
            raise RecorderError("press/key action requires key")
        if key in {"Control+A", "Ctrl+A", "Meta+A", "Command+A"}:
            await self.cdp.send(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "key": "Control", "code": "ControlLeft", "modifiers": 2},
                use_session=True,
                timeout=self.input_timeout,
            )
            await self.cdp.send(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "key": "a", "code": "KeyA", "modifiers": 2},
                use_session=True,
                timeout=self.input_timeout,
            )
            await self.cdp.send(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": "a", "code": "KeyA", "modifiers": 2},
                use_session=True,
                timeout=self.input_timeout,
            )
            await self.cdp.send(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": "Control", "code": "ControlLeft"},
                use_session=True,
                timeout=self.input_timeout,
            )
            return
        code = KEY_CODES.get(key, key)
        params = {"key": key, "code": code}
        await self.cdp.send(
            "Input.dispatchKeyEvent",
            {"type": "keyDown", **params},
            use_session=True,
            timeout=self.input_timeout,
        )
        await self.cdp.send(
            "Input.dispatchKeyEvent",
            {"type": "keyUp", **params},
            use_session=True,
            timeout=self.input_timeout,
        )

    async def scroll(self, pixels: float, coordinate: Any = None) -> None:
        if coordinate is not None:
            x, y = require_number_pair(coordinate, "coordinate")
        else:
            x, y = 600.0, 400.0
        try:
            await self.cdp.send(
                "Input.dispatchMouseEvent",
                {"type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": float(pixels)},
                use_session=True,
                timeout=self.input_timeout,
            )
        except RecorderError as error:
            if "Input.dispatchMouseEvent timed out" not in str(error):
                raise
            expected_target_id = target_id(self.cdp.target)
            await self.cdp.reconnect()
            await enable_page_domains(self.cdp)
            await reattach_to_target(self.cdp, expected_target_id)
            await self.cdp.send(
                "Runtime.evaluate",
                {
                    "expression": f"window.scrollBy(0, {json.dumps(float(pixels))}); true",
                    "returnByValue": True,
                    "awaitPromise": True,
                },
                use_session=True,
                timeout=self.input_timeout,
            )
            raise ScrollFallbackUsed(str(error))

    async def wait(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, min(float(seconds), 30.0)))

    async def resolve_point(self, *, ref: str | None = None, selector: str | None = None, coordinate: Any = None) -> tuple[float, float]:
        if coordinate is not None:
            return require_number_pair(coordinate, "coordinate")
        if ref:
            if self._last_snapshot is None or ref not in self._last_snapshot.refs:
                await self.snapshot()
            if self._last_snapshot and ref in self._last_snapshot.refs:
                center = element_center(self._last_snapshot.refs[ref])
                if center:
                    return center
            raise RecorderError(f"snapshot ref {ref!r} does not have usable coordinates")
        if selector:
            return await self.selector_center(selector)
        raise RecorderError("click/fill requires one of ref, selector, or coordinate")

    async def selector_center(self, selector: str) -> tuple[float, float]:
        expression = f"""
        (() => {{
          const selector = {json.dumps(selector)};
          const el = document.querySelector(selector);
          if (!el) return {{error: `selector not found: ${{selector}}`}};
          el.scrollIntoView({{block: 'center', inline: 'center'}});
          const r = el.getBoundingClientRect();
          return {{
            x: r.left + r.width / 2,
            y: r.top + r.height / 2,
            width: r.width,
            height: r.height,
          }};
        }})()
        """
        response = await self.cdp.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
            use_session=True,
        )
        value = response.get("result", {}).get("result", {}).get("value", {})
        if not isinstance(value, dict) or value.get("error"):
            raise RecorderError(str(value.get("error") if isinstance(value, dict) else value))
        x = value.get("x")
        y = value.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise RecorderError(f"selector {selector!r} did not resolve to coordinates: {value}")
        return float(x), float(y)

    async def perform(self, action: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_action(action)
        name = normalized["action"]

        if name == "navigate":
            await self.navigate(str(normalized.get("url", "")).strip())
            return normalized

        if name == "click":
            x, y = await self.click(
                ref=normalized.get("ref"),
                selector=normalized.get("selector"),
                coordinate=normalized.get("coordinate"),
            )
            normalized["coordinate"] = [round(x, 2), round(y, 2)]
            return normalized

        if name == "type":
            await self.type_text(str(normalized.get("text", "")))
            return normalized

        if name == "fill":
            text = str(normalized.get("text", ""))
            await self.fill(
                text=text,
                ref=normalized.get("ref"),
                selector=normalized.get("selector"),
                coordinate=normalized.get("coordinate"),
            )
            return normalized

        if name == "press":
            await self.press(str(normalized.get("key") or (normalized.get("keys") or [""])[0]).strip())
            return normalized

        if name == "scroll":
            pixels = normalized.get("pixels", normalized.get("deltaY", 0))
            if not isinstance(pixels, (int, float)):
                raise RecorderError(f"scroll action requires numeric pixels, got {pixels!r}")
            try:
                await self.scroll(float(pixels), coordinate=normalized.get("coordinate"))
                normalized["_execution_method"] = "cdp_mouse_wheel"
            except ScrollFallbackUsed as fallback:
                normalized["_execution_method"] = "runtime_scroll_fallback"
                normalized["_execution_fallback_reason"] = str(fallback)
            return normalized

        if name == "wait":
            seconds = normalized.get("seconds", 1)
            if not isinstance(seconds, (int, float)):
                seconds = 1
            await self.wait(float(seconds))
            return normalized

        if name == "terminate":
            return normalized

        raise RecorderError(f"unsupported automated action: {name}")


async def create_fresh_browser_context(cdp: CDPConnection) -> dict[str, Any]:
    """Create an isolated browser context if the CDP backend supports it."""

    try:
        created = await cdp.send("Target.createBrowserContext", {"disposeOnDetach": False}, timeout=10.0)
    except Exception as error:
        return {"ok": False, "error": str(error)}
    browser_context_id = str(created.get("browserContextId", ""))
    if not browser_context_id:
        return {"ok": False, "error": f"Target.createBrowserContext returned no browserContextId: {created}"}
    return {"ok": True, "browserContextId": browser_context_id}


async def open_fresh_tab(
    cdp: CDPConnection,
    url: str = "about:blank",
    *,
    browser_context_id: str = "",
) -> dict[str, Any]:
    """Create and attach to a new page target for a fresh non-resume task."""

    params = {"url": url}
    if browser_context_id:
        params["browserContextId"] = browser_context_id
    created = await cdp.send("Target.createTarget", params)
    target_id = str(created.get("targetId", ""))
    if not target_id:
        raise RecorderError(f"Target.createTarget returned no targetId: {created}")
    try:
        await cdp.send("Target.activateTarget", {"targetId": target_id})
    except CDPCommandError:
        # Some Chromium builds do not need or allow activation. Attaching is the
        # critical part for CDP/ChromiumRL commands.
        pass
    targets = await cdp.page_targets()
    target = next(
        (
            item
            for item in targets
            if str(item.get("targetId") or item.get("target_id") or item.get("id")) == target_id
        ),
        None,
    )
    if target is None:
        target = {"targetId": target_id, "type": "page", "url": url, "title": ""}
    await cdp.attach_to_target(target)
    await enable_page_domains(cdp)
    return cdp.target


async def reattach_to_target(cdp: CDPConnection, expected_target_id: str) -> None:
    if not expected_target_id:
        return
    targets = await cdp.page_targets()
    target = next((item for item in targets if target_id(item) == expected_target_id), None)
    if target is not None:
        await cdp.attach_to_target(target)
        await enable_page_domains(cdp)


async def clear_browser_data_for_fresh_task(cdp: CDPConnection) -> dict[str, Any]:
    """Clear browser profile state for a non-resume task.

    This is generic isolation, not task logic. Resume mode intentionally skips
    it so an in-progress task keeps its current logged-in/cookie/session state.
    """

    result: dict[str, Any] = {"started_at": utc_now(), "commands": []}

    async def run_command(method: str, params: dict[str, Any] | None = None, *, use_session: bool = False) -> None:
        entry: dict[str, Any] = {"method": method, "params": params or {}, "use_session": use_session}
        try:
            response = await cdp.send(method, params or {}, use_session=use_session, timeout=10.0)
            entry["ok"] = True
            entry["response"] = response
        except Exception as error:
            entry["ok"] = False
            entry["error"] = str(error)
        result["commands"].append(entry)

    await run_command("Network.enable", use_session=True)
    await run_command("Network.clearBrowserCookies")
    await run_command("Network.clearBrowserCache")
    await run_command(
        "Runtime.evaluate",
        {
            "expression": "location.origin",
            "returnByValue": True,
            "awaitPromise": True,
        },
        use_session=True,
    )
    origin_entries = result["commands"][-1].get("response", {})
    origin = ""
    if isinstance(origin_entries, dict):
        origin = str(origin_entries.get("result", {}).get("value", ""))
    if origin and origin not in {"null", "about://blank"}:
        await run_command("Storage.clearDataForOrigin", {"origin": origin, "storageTypes": "all"}, use_session=True)
    await run_command(
        "Runtime.evaluate",
        {
            "expression": """
            (() => {
              try { localStorage.clear(); } catch (error) {}
              try { sessionStorage.clear(); } catch (error) {}
              try {
                if ('caches' in window) {
                  caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key))));
                }
              } catch (error) {}
              return true;
            })()
            """,
            "returnByValue": True,
            "awaitPromise": True,
        },
        use_session=True,
    )
    result["completed_at"] = utc_now()
    return result


async def call_openai_json(
    *,
    api_key: str,
    model: str,
    task: str,
    history: list[dict[str, Any]],
    snapshot: Snapshot,
    timeout: float,
) -> dict[str, Any]:
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = base_url + "/chat/completions"
    user_payload = {
        "task": task,
        "recent_actions": history[-20:],
        "progress_warnings": progress_warnings(history),
        "snapshot": snapshot.text,
    }
    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": truncate_text(json.dumps(user_payload, ensure_ascii=False), 60000),
            },
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        async with session.post(url, headers=headers, json=body) as response:
            text = await response.text()
            if response.status >= 400:
                raise RecorderError(f"OpenAI request failed HTTP {response.status}: {text[:1000]}")
            data = json.loads(text)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise RecorderError(f"OpenAI response had no JSON content: {data}")
    try:
        action = json.loads(content)
    except json.JSONDecodeError as error:
        raise RecorderError(f"OpenAI did not return valid JSON: {content[:1000]}") from error
    return normalize_action(action)


def load_existing_history(task_dir: Path, limit: int = 40) -> list[dict[str, Any]]:
    trajectory = task_dir / "trajectory.jsonl"
    if not trajectory.exists():
        return []
    history: list[dict[str, Any]] = []
    for raw in trajectory.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        action = item.get("action")
        if not isinstance(action, dict):
            continue
        before_page = item.get("before_page") if isinstance(item.get("before_page"), dict) else {}
        after_page = item.get("after_page") if isinstance(item.get("after_page"), dict) else {}
        outcome = outcome_from_trajectory_item(task_dir, item, action)
        history.append(
            {
                "step": item.get("step"),
                "action": action,
                "approved": True,
                "outcome": outcome,
                "before": {
                    "url": before_page.get("url"),
                    "scrollY": (before_page.get("viewport") or {}).get("scrollY") if isinstance(before_page.get("viewport"), dict) else None,
                },
                "after": {
                    "url": after_page.get("url"),
                    "scrollY": (after_page.get("viewport") or {}).get("scrollY") if isinstance(after_page.get("viewport"), dict) else None,
                },
            }
        )
    return history[-limit:]


def saved_task_prompt(task_dir: Path) -> str:
    actions_path = task_dir / "actions.json"
    if not actions_path.exists():
        return ""
    try:
        data = json.loads(actions_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    return str(data.get("task", "")) if isinstance(data, dict) else ""


def validate_resume_prompt(task_dir: Path, task: str) -> None:
    saved = saved_task_prompt(task_dir)
    if saved and saved != task:
        raise RecorderError(
            "resume prompt does not match the saved task prompt. "
            f"Saved task: {saved!r}. New prompt: {task!r}. "
            "Use the exact same prompt with --resume, or start a new task id."
        )


async def record_automated_step(
    *,
    agent: DesktopWootzAgent,
    task_dir: Path,
    step_number: int,
    action: dict[str, Any],
    screenshot_config: ScreenshotConfig,
    settle_seconds: float,
    capture_all_targets: bool,
) -> dict[str, Any]:
    cdp = agent.cdp
    action = normalize_action(action)
    expected_target_id = target_id(cdp.target)
    step_dir = task_dir / f"step_{step_number:03d}"
    step_dir.mkdir(parents=False, exist_ok=False)
    write_json(step_dir / "action.json", action)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "step": step_number,
        "source_action_number": step_number,
        "status": "capturing_before",
        "started_at": utc_now(),
        "recording_mode": "agent_browser_desktop",
        "action": action,
    }
    write_json(step_dir / "step.json", metadata)

    tracing = await reset_chromiumrl_tracing(cdp)
    metadata["chromiumrl_trace_session_id"] = tracing.get("sessionId")
    before = await capture_state_with_recovery(
        cdp, step_dir / "before", "before", screenshot_config, capture_all_targets=capture_all_targets
    )
    metadata["status"] = "performing_action"
    metadata["before_captured_at"] = before.index["completed_at"]
    write_json(step_dir / "step.json", metadata)

    performed_action = await agent.perform(action)
    write_json(step_dir / "action.json", performed_action)

    if settle_seconds:
        await asyncio.sleep(settle_seconds)

    metadata["action"] = performed_action
    metadata["action_confirmed_at"] = utc_now()
    metadata["status"] = "capturing_after"
    write_json(step_dir / "step.json", metadata)

    await cdp.reconnect()
    await enable_page_domains(cdp)
    await reattach_to_target(cdp, expected_target_id)
    after = await capture_state_with_recovery(
        cdp, step_dir / "after", "after", screenshot_config, capture_all_targets=capture_all_targets
    )

    try:
        compare_response, compare_timing = await timed_command(
            cdp,
            "ChromiumRL.compareDOMState",
            {"referenceState": before.chromiumrl_dom},
            required=True,
        )
    except CDPCommandError as error:
        if not is_session_not_found(error):
            raise
        await cdp.refresh_page_session()
        await enable_page_domains(cdp)
        compare_response, compare_timing = await timed_command(
            cdp,
            "ChromiumRL.compareDOMState",
            {"referenceState": before.chromiumrl_dom},
            required=True,
        )

    dom_diff = {
        "schema_version": SCHEMA_VERSION,
        "method": "ChromiumRL.compareDOMState",
        "captured_at": utc_now(),
        "timing": compare_timing,
        "reference": "before/chromiumrl_dom.json",
        "current": "after/chromiumrl_dom.json",
        "chromiumrl_response": compare_response,
        "chromiumrl_result": compare_response.get("result", {}),
    }
    write_json(step_dir / "dom_diff.json", dom_diff)
    dom_diff_summary = build_dom_diff_summary(before, after)
    write_json(step_dir / "dom_diff_summary.json", dom_diff_summary)

    signals = await collect_chromiumrl_signals(cdp)
    write_json(step_dir / "chromiumrl_signals.json", signals)

    verifier_action = build_verifier_action(performed_action, before, after, signals)
    write_json(step_dir / "verifier_action.json", verifier_action)
    interaction_capture = await collect_interaction_capture(
        cdp,
        performed_action,
        verifier_action,
        before.chromiumrl_dom,
        after.chromiumrl_dom,
    )
    write_json(step_dir / "interaction_capture.json", interaction_capture)

    metadata.update(
        {
            "status": "complete",
            "completed_at": utc_now(),
            "after_captured_at": after.index["completed_at"],
            "before_page": before.page_state,
            "after_page": after.page_state,
            "outcome": build_step_outcome(performed_action, before.page_state, after.page_state, dom_diff_summary),
            "artifacts": artifact_record(step_dir, task_dir),
        }
    )
    write_json(step_dir / "step.json", metadata)

    append_jsonl(
        task_dir / "trajectory.jsonl",
        {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_dir.name,
            "step": step_number,
            "source_action_number": step_number,
            "action": performed_action,
            "started_at": metadata["started_at"],
            "completed_at": metadata["completed_at"],
            "before_page": before.page_state,
            "after_page": after.page_state,
            "outcome": metadata["outcome"],
            "artifacts_directory": step_dir.relative_to(task_dir).as_posix(),
            "dom_diff": "dom_diff.json",
            "dom_diff_summary": "dom_diff_summary.json",
            "verifier_action": "verifier_action.json",
            "chromiumrl_signals": "chromiumrl_signals.json",
            "interaction_capture": "interaction_capture.json",
        },
    )
    completed = sum(
        1
        for number in step_numbers(task_dir)
        if json.loads((task_dir / f"step_{number:03d}" / "step.json").read_text(encoding="utf-8")).get("status")
        == "complete"
    )
    update_manifest(task_dir, completed_steps=completed, status="recording")
    return {"action": performed_action, "outcome": metadata["outcome"]}


async def run(args: argparse.Namespace) -> None:
    load_env_file(ROOT / ".env")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("AGENT_BROWSER_MODEL", "").strip()
    if not api_key:
        raise RecorderError("OPENAI_API_KEY is missing. Add it to /data/aayush/task-recorder/.env")
    if not model:
        raise RecorderError("AGENT_BROWSER_MODEL is missing. Add it to /data/aayush/task-recorder/.env")

    task_dir = initialize_task(
        Path(args.output_root),
        args.task_id,
        {"mode": "agent_browser_desktop", "task": args.task},
        0,
        args.cdp_url,
        resume=args.resume,
    )
    if args.resume:
        validate_resume_prompt(task_dir, args.task)
    screenshot_config = ScreenshotConfig(
        source=args.screenshot_source,
        container=args.screenshot_container,
        adb_serial="",
        timeout_seconds=args.command_timeout,
    )
    history: list[dict[str, Any]] = load_existing_history(task_dir) if args.resume else []
    existing_steps = step_numbers(task_dir)
    next_step = (existing_steps[-1] + 1) if existing_steps else 1

    print(f"Connecting to desktop Wootz CDP at {args.cdp_url} ...")
    async with CDPConnection(
        args.cdp_url,
        command_timeout=args.command_timeout,
        target_url_contains=args.target_url_contains,
    ) as cdp:
        await enable_page_domains(cdp)
        startup_language_overrides = await apply_language_overrides(
            cdp,
            locale=args.browser_locale,
            accept_language=args.accept_language,
        )
        if not args.resume:
            fresh_context = {"ok": False, "reason": "disabled"}
            browser_context_id = ""
            if not args.keep_browser_data:
                fresh_context = await create_fresh_browser_context(cdp)
                if fresh_context.get("ok"):
                    browser_context_id = str(fresh_context.get("browserContextId", ""))
            fresh_target = await open_fresh_tab(cdp, args.fresh_tab_url, browser_context_id=browser_context_id)
            fresh_tab_language_overrides = await apply_language_overrides(
                cdp,
                locale=args.browser_locale,
                accept_language=args.accept_language,
            )
            cleanup_result: dict[str, Any] | None = None
            if not args.keep_browser_data and not browser_context_id:
                cleanup_result = await clear_browser_data_for_fresh_task(cdp)
            append_jsonl(
                task_dir / "agent_browser_decisions.jsonl",
                {
                    "timestamp": utc_now(),
                    "source": "runner",
                    "event": "fresh_tab_created",
                    "fresh_browser_context": fresh_context,
                    "target": fresh_target,
                    "url": args.fresh_tab_url,
                    "startup_language_overrides": startup_language_overrides,
                    "fresh_tab_language_overrides": fresh_tab_language_overrides,
                    "browser_data_cleared": not args.keep_browser_data,
                    "browser_data_cleanup": cleanup_result,
                },
            )
            print(f"Started non-resume task in a fresh tab: {args.fresh_tab_url}")
            if browser_context_id:
                print("Started non-resume task in an isolated browser context.")
            elif not args.keep_browser_data:
                print("Cleared browser cookies/cache/storage for fresh non-resume task.")
        else:
            resume_language_overrides = await apply_language_overrides(
                cdp,
                locale=args.browser_locale,
                accept_language=args.accept_language,
            )
            append_jsonl(
                task_dir / "agent_browser_decisions.jsonl",
                {
                    "timestamp": utc_now(),
                    "source": "runner",
                    "event": "resume_language_overrides",
                    "language_overrides": resume_language_overrides,
                },
            )
            print("Resume mode: keeping the current browser tab/session.")
        agent = DesktopWootzAgent(
            cdp,
            input_timeout=args.input_timeout,
            browser_locale=args.browser_locale,
            accept_language=args.accept_language,
        )

        step = next_step
        recorded_this_run = 0
        while recorded_this_run < args.max_steps:
            await agent.apply_language_overrides()
            snapshot = await agent.snapshot(max_elements=args.max_elements)
            action = await call_openai_json(
                api_key=api_key,
                model=model,
                task=args.task,
                history=history,
                snapshot=snapshot,
                timeout=args.model_timeout,
            )
            decision = {
                "timestamp": utc_now(),
                "step": step,
                "task": args.task,
                "source": "model",
                "snapshot": snapshot.text,
                "action": action,
            }
            append_jsonl(task_dir / "agent_browser_decisions.jsonl", decision)

            print("\n" + "=" * 78)
            print(f"PROPOSED STEP {step:03d} (model)")
            print(json.dumps(action, indent=2, ensure_ascii=False))
            print("=" * 78)

            if action_name(action) == "terminate":
                final = {
                    "completed_at": utc_now(),
                    "status": action.get("status", "success"),
                    "final_answer": action.get("final_answer", ""),
                    "action": action,
                }
                write_json(task_dir / "agent_browser_final.json", final)
                update_manifest(task_dir, status="complete", finished_at=utc_now())
                print(f"Agent terminated: {json.dumps(final, ensure_ascii=False)}")
                return

            if not args.yes:
                reply = input("Approve this action? [y/N/q]: ").strip().lower()
                if reply in {"q", "quit", "stop"}:
                    update_manifest(task_dir, status="stopped", stopped_at=utc_now())
                    print(f"Stopped before step {step:03d}")
                    return
                if reply not in {"y", "yes"}:
                    history.append({"step": step, "action": action, "approved": False})
                    continue

            result = await record_automated_step(
                agent=agent,
                task_dir=task_dir,
                step_number=step,
                action=action,
                screenshot_config=screenshot_config,
                settle_seconds=args.settle_seconds,
                capture_all_targets=not args.no_capture_all_targets,
            )
            history.append(
                {
                    "step": step,
                    "action": result["action"],
                    "approved": True,
                    "outcome": result["outcome"],
                }
            )
            print(f"Recorded automated step {step:03d} in {task_dir / f'step_{step:03d}'}")
            step += 1
            recorded_this_run += 1

    update_manifest(task_dir, status="max_steps_reached", stopped_at=utc_now())
    print(f"Stopped after max steps: {args.max_steps}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automated desktop agent-browser runner for task-recorder")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--cdp-url", default="http://127.0.0.1:49325")
    parser.add_argument("--target-url-contains", default="")
    parser.add_argument("--output-root", default="tasks")
    parser.add_argument("--command-timeout", type=float, default=90.0)
    parser.add_argument("--input-timeout", type=float, default=8.0)
    parser.add_argument("--model-timeout", type=float, default=120.0)
    parser.add_argument("--settle-seconds", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--max-elements", type=int, default=120)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fresh-tab-url", default="about:blank")
    parser.add_argument("--keep-browser-data", action="store_true")
    parser.add_argument("--browser-locale", default=os.environ.get("BROWSER_LANG", "en-US"))
    parser.add_argument("--accept-language", default=os.environ.get("BROWSER_ACCEPT_LANGUAGE", "en-US,en;q=0.9"))
    parser.add_argument("--yes", action="store_true", help="perform model actions without approval prompts")
    parser.add_argument("--no-capture-all-targets", action="store_true", default=True)
    parser.add_argument("--capture-all-targets", dest="no_capture_all_targets", action="store_false")
    parser.add_argument("--screenshot-source", choices=("cdp", "none"), default="cdp")
    parser.add_argument("--screenshot-container", default="wootz-desktop-browser-replay-001")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.max_steps <= 0:
        raise SystemExit("--max-steps must be positive")
    try:
        asyncio.run(run(args))
    except (RecorderError, aiohttp.ClientError, asyncio.TimeoutError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
