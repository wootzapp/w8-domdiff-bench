#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recorder import (  # noqa: E402
    CDPConnection,
    RecorderError,
    ScreenshotConfig,
    append_jsonl,
    build_compact_dom_diff,
    capture_state_with_recovery,
    chromiumrl_call,
    enable_page_domains,
    reset_chromiumrl_tracing,
    utc_now,
    wait_for_ready,
    write_json,
    write_json_compact,
    write_json_gz,
)


def data_url(html: str) -> str:
    return "data:text/html;charset=utf-8," + quote(html)


SCREENSHOT_CONFIG = ScreenshotConfig(source="cdp", container="", adb_serial="", timeout_seconds=10, format="jpeg", quality=70)


async def navigate(cdp: CDPConnection, url: str) -> None:
    await cdp.send("Page.navigate", {"url": url}, use_session=True, timeout=8.0)
    await wait_for_ready(cdp, timeout=8.0)


async def click_selector(cdp: CDPConnection, selector: str) -> None:
    expr = f"""
    (() => {{
      const el = document.querySelector({json.dumps(selector)});
      if (!el) return {{error:'missing selector'}};
      el.scrollIntoView({{block:'center', inline:'center'}});
      const r = el.getBoundingClientRect();
      return {{x:r.left+r.width/2, y:r.top+r.height/2}};
    }})()
    """
    res = await cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True}, use_session=True, timeout=5.0)
    val = res.get("result", {}).get("value", {})
    if not isinstance(val, dict) or val.get("error"):
        raise RecorderError(str(val))
    x, y = float(val["x"]), float(val["y"])
    for kind, extra in (("mouseMoved", {}), ("mousePressed", {"button":"left", "clickCount":1}), ("mouseReleased", {"button":"left", "clickCount":1})):
        await cdp.send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, **extra}, use_session=True, timeout=5.0)


async def fill_selector(cdp: CDPConnection, selector: str, text: str) -> None:
    await click_selector(cdp, selector)
    await cdp.send("Input.dispatchKeyEvent", {"type":"keyDown", "key":"Control", "code":"ControlLeft", "modifiers":2}, use_session=True, timeout=5.0)
    await cdp.send("Input.dispatchKeyEvent", {"type":"keyDown", "key":"a", "code":"KeyA", "modifiers":2}, use_session=True, timeout=5.0)
    await cdp.send("Input.dispatchKeyEvent", {"type":"keyUp", "key":"a", "code":"KeyA", "modifiers":2}, use_session=True, timeout=5.0)
    await cdp.send("Input.dispatchKeyEvent", {"type":"keyUp", "key":"Control", "code":"ControlLeft"}, use_session=True, timeout=5.0)
    await cdp.send("Input.insertText", {"text": text}, use_session=True, timeout=5.0)


async def capture_pair(cdp: CDPConnection, task_dir: Path, step: int, action_name: str, action_coro) -> dict:
    step_dir = task_dir / f"step_{step:03d}"
    before_dir = step_dir / ".before_tmp"
    after_dir = step_dir / ".after_tmp"
    step_dir.mkdir(parents=True, exist_ok=True)
    before = await capture_state_with_recovery(cdp, before_dir, "before", SCREENSHOT_CONFIG, write_dom=True, dom_capture="slim", observation_max_elements=250)
    if before.dom_captured and (before_dir / "chromiumrl_dom_slim.json.gz").exists():
        shutil.copyfile(before_dir / "chromiumrl_dom_slim.json.gz", step_dir / "dom_before.json.gz")
    await action_coro()
    await wait_for_ready(cdp, timeout=5.0)
    after = await capture_state_with_recovery(cdp, after_dir, "after", SCREENSHOT_CONFIG, write_dom=True, dom_capture="slim", observation_max_elements=250)
    if after.dom_captured and (after_dir / "chromiumrl_dom_slim.json.gz").exists():
        shutil.copyfile(after_dir / "chromiumrl_dom_slim.json.gz", step_dir / "dom_after.json.gz")
    compare_result = {}
    compare_timing = {"ok": False, "skipped": True}
    if before.chromiumrl_dom:
        t0 = time.perf_counter()
        try:
            compare_result = await chromiumrl_call(cdp, "ChromiumRL.compareDOMState", {"referenceState": before.chromiumrl_dom}, timeout=20.0, label=f"{action_name}_compare")
            compare_timing = {"ok": True, "elapsed_ms": round((time.perf_counter()-t0)*1000, 3)}
        except Exception as error:
            compare_timing = {"ok": False, "elapsed_ms": round((time.perf_counter()-t0)*1000, 3), "error": str(error)}
    diff = build_compact_dom_diff(before.chromiumrl_dom, after.chromiumrl_dom, compare_result=compare_result, compare_timing=compare_timing, max_entries=200)
    write_json_compact(step_dir / "dom_diff.json", diff)
    write_json(step_dir / "action.json", {"action": action_name, "completed_at": utc_now(), "before_page": before.page_state, "after_page": after.page_state})
    for tmp in (before_dir, after_dir):
        if tmp.exists():
            shutil.rmtree(tmp)
    return diff


def diff_text(diff: dict) -> str:
    return json.dumps(diff, ensure_ascii=False).lower()


def assert_contains(diff: dict, needles: list[str]) -> tuple[bool, str]:
    text = diff_text(diff)
    missing = [n for n in needles if n.lower() not in text]
    return (not missing, "missing " + ", ".join(missing) if missing else "ok")


async def run(args):
    out = Path(args.output_root)
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    async with CDPConnection(args.cdp_url, command_timeout=30) as cdp:
        cdp.log_path = out / "log.jsonl"
        await enable_page_domains(cdp)
        await reset_chromiumrl_tracing(cdp)

        # diff-checkbox: controlled DOM state change on a checkbox.
        task = out / "diff-checkbox"
        write_json(task / "manifest.json", {"task_id":"diff-checkbox", "kind":"dom-diff-benchmark"})
        await navigate(cdp, data_url("<label><input id='agree' type='checkbox' onclick=\"this.toggleAttribute('checked', this.checked)\"> I agree</label>"))
        diff = await capture_pair(cdp, task, 1, "click checkbox", lambda: click_selector(cdp, "#agree"))
        ok, reason = assert_contains(diff, ["attr:checked"])
        summary.append({"id":"diff-checkbox", "ok":ok, "reason":reason, "bytes":(task/"step_001/dom_diff.json").stat().st_size, "stats": diff.get("stats", {})})

        # diff-modal: controlled removed subtree; public cookie banners are not stable by region.
        task = out / "diff-modal"
        write_json(task / "manifest.json", {"task_id":"diff-modal", "kind":"dom-diff-benchmark"})
        await navigate(cdp, data_url("""
          <main><h1>Product page</h1></main>
          <div id='cookie' role='dialog'><p>We use cookies for analytics and ads.</p><button id='dismiss' onclick="document.getElementById('cookie').remove()">Accept cookies</button></div>
        """))
        diff = await capture_pair(cdp, task, 1, "dismiss modal", lambda: click_selector(cdp, "#dismiss"))
        ok, reason = assert_contains(diff, ["we use cookies"])
        collapsed = bool(diff.get("removed") and diff["removed"][0].get("descendant_count", 0) >= 1)
        summary.append({"id":"diff-modal", "ok":ok and collapsed, "reason":reason if ok else reason, "collapsed":collapsed, "bytes":(task/"step_001/dom_diff.json").stat().st_size, "stats": diff.get("stats", {})})

        # diff-text: real site navigation should add/replace content containing a price.
        task = out / "diff-text"
        write_json(task / "manifest.json", {"task_id":"diff-text", "kind":"dom-diff-benchmark"})
        await navigate(cdp, "https://books.toscrape.com/")
        diff = await capture_pair(cdp, task, 1, "open first book", lambda: click_selector(cdp, "article.product_pod h3 a"))
        ok, reason = assert_contains(diff, ["£"])
        summary.append({"id":"diff-text", "ok":ok, "reason":reason, "bytes":(task/"step_001/dom_diff.json").stat().st_size, "stats": diff.get("stats", {})})

        # diff-form: real form fill then submit; validates value change and post-submit state.
        task = out / "diff-form"
        write_json(task / "manifest.json", {"task_id":"diff-form", "kind":"dom-diff-benchmark"})
        await navigate(cdp, "https://quotes.toscrape.com/login")
        diff1 = await capture_pair(cdp, task, 1, "fill username", lambda: fill_selector(cdp, "input[name='username']", "x"))
        ok1, reason1 = assert_contains(diff1, ["attr:value", "x"])
        diff2 = await capture_pair(cdp, task, 2, "submit form", lambda: (fill_selector(cdp, "input[name='password']", "y")))
        # Submit after password fill in a third same task step to keep diffs atomic.
        diff3 = await capture_pair(cdp, task, 3, "click login", lambda: click_selector(cdp, "input[type='submit']"))
        ok3, reason3 = assert_contains(diff3, ["logout"])
        summary.append({"id":"diff-form", "ok":ok1 and ok3, "reason": f"fill={reason1}; submit={reason3}", "bytes":sum((task/f"step_{i:03d}/dom_diff.json").stat().st_size for i in (1,2,3)), "stats": diff3.get("stats", {})})

        # diff-scroll: pure scroll should not report semantic DOM changes.
        task = out / "diff-scroll"
        write_json(task / "manifest.json", {"task_id":"diff-scroll", "kind":"dom-diff-benchmark"})
        await navigate(cdp, "https://en.wikipedia.org/wiki/Web_browser")
        diff = await capture_pair(cdp, task, 1, "scroll 1000px", lambda: cdp.send("Runtime.evaluate", {"expression":"window.scrollBy(0,1000); true", "returnByValue": True}, use_session=True, timeout=5.0))
        stats = diff.get("stats", {})
        ok = stats.get("added_total") == 0 and stats.get("changed_total") == 0
        summary.append({"id":"diff-scroll", "ok":ok, "reason":"ok" if ok else "non-empty semantic diff", "bytes":(task/"step_001/dom_diff.json").stat().st_size, "stats": stats})

        with contextlib.suppress(Exception):
            await cdp.send("ChromiumRL.disable", {}, use_session=True, timeout=2.0)
    write_json(out / "diff_benchmark_summary.json", {"completed_at": utc_now(), "results": summary})
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import contextlib
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-url", default="http://127.0.0.1:49325")
    parser.add_argument("--output-root", default="diagnostics/v5/diff_benchmarks")
    asyncio.run(run(parser.parse_args()))
