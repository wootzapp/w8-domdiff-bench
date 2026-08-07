#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_browser.desktop_agent import DesktopWootzAgent, SYSTEM_PROMPT, is_actionable_for_blocking  # noqa: E402

from recorder import (  # noqa: E402
    CDPConnection,
    RecorderError,
    ScreenshotConfig,
    build_compact_dom_diff,
    render_dom_diff_text,
    capture_state_with_recovery,
    chromiumrl_call,
    enable_page_domains,
    reset_chromiumrl_tracing,
    utc_now,
    wait_for_ready,
    write_json,
    write_json_compact,
)


def data_url(html: str) -> str:
    return "data:text/html;charset=utf-8," + quote(html)


SCREENSHOT_CONFIG = ScreenshotConfig(source="cdp", container="", adb_serial="", timeout_seconds=10, format="jpeg", quality=70)


async def navigate(cdp: CDPConnection, url: str, *, timeout: float = 10.0) -> None:
    await cdp.send("Page.navigate", {"url": url}, use_session=True, timeout=timeout)
    await wait_for_ready(cdp, timeout=10.0)


async def eval_value(cdp: CDPConnection, expression: str, *, timeout: float = 5.0):
    res = await cdp.send("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": False}, use_session=True, timeout=timeout)
    return res.get("result", {}).get("value")


async def click_selector(cdp: CDPConnection, selector: str) -> None:
    expr = rf"""
    (() => {{
      const el = document.querySelector({json.dumps(selector)});
      if (!el) return {{error:'missing selector ' + {json.dumps(selector)}}};
      el.scrollIntoView({{block:'center', inline:'center'}});
      const r = el.getBoundingClientRect();
      return {{x:r.left+r.width/2, y:r.top+r.height/2}};
    }})()
    """
    val = await eval_value(cdp, expr)
    if not isinstance(val, dict) or val.get("error"):
        raise RecorderError(str(val))
    x, y = float(val["x"]), float(val["y"])
    for kind, extra in (("mouseMoved", {}), ("mousePressed", {"button":"left", "buttons":1, "clickCount":1}), ("mouseReleased", {"button":"left", "buttons":0, "clickCount":1})):
        await cdp.send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, **extra}, use_session=True, timeout=5.0)


async def fill_selector(cdp: CDPConnection, selector: str, text: str) -> None:
    await click_selector(cdp, selector)
    await cdp.send("Input.dispatchKeyEvent", {"type":"keyDown", "key":"Control", "code":"ControlLeft", "modifiers":2}, use_session=True, timeout=5.0)
    await cdp.send("Input.dispatchKeyEvent", {"type":"keyDown", "key":"a", "code":"KeyA", "modifiers":2}, use_session=True, timeout=5.0)
    await cdp.send("Input.dispatchKeyEvent", {"type":"keyUp", "key":"a", "code":"KeyA", "modifiers":2}, use_session=True, timeout=5.0)
    await cdp.send("Input.dispatchKeyEvent", {"type":"keyUp", "key":"Control", "code":"ControlLeft"}, use_session=True, timeout=5.0)
    await cdp.send("Input.insertText", {"text": text}, use_session=True, timeout=5.0)


async def select_value(cdp: CDPConnection, selector: str, value: str) -> None:
    expr = rf"""
    (() => {{
      const el = document.querySelector({json.dumps(selector)});
      if (!el) return {{error:'missing selector ' + {json.dumps(selector)}}};
      el.value = {json.dumps(value)};
      el.dispatchEvent(new Event('input', {{bubbles:true}}));
      el.dispatchEvent(new Event('change', {{bubbles:true}}));
      return {{value: el.value}};
    }})()
    """
    val = await eval_value(cdp, expr)
    if not isinstance(val, dict) or val.get("error"):
        raise RecorderError(str(val))


async def click_button_by_text(cdp: CDPConnection, needles: list[str], *, allow_unlabeled: bool = False) -> None:
    expr = rf"""
    (() => {{
      const needles = {json.dumps([n.lower() for n in needles])};
      const allowUnlabeled = {json.dumps(bool(allow_unlabeled))};
      const candidates = Array.from(document.querySelectorAll('button,a,[role=button],input[type=button],input[type=submit]'));
      const matchScore = (text) => {{
        const t = (text || '').replace(/\s+/g,' ').trim().toLowerCase();
        if (!t) return 0;
        for (const n of needles) {{
          if (t === n) return 100;
          const words = t.split(/[^a-z0-9£$€¥₹.]+/).filter(Boolean);
          if (words.includes(n)) return 80;
          if (t.includes(n)) return 20;
        }}
        return 0;
      }};
      let scored = candidates.map(e => [matchScore(e.innerText || e.value || e.getAttribute('aria-label') || ''), e]).filter(x => x[0] > 0);
      scored.sort((a,b) => b[0] - a[0]);
      let el = scored.length ? scored[0][1] : null;
      if (!el) {{
        const textCandidates = Array.from(document.querySelectorAll('body *')).map(e => {{
          const t = (e.innerText || e.textContent || '').replace(/\s+/g,' ').trim();
          const score = matchScore(t);
          if (!score || t.length > 80) return null;
          const r = e.getBoundingClientRect();
          const cs = getComputedStyle(e);
          if (!(r.width && r.height && r.bottom >= 0 && r.right >= 0 && r.top <= innerHeight && r.left <= innerWidth && cs.visibility !== 'hidden' && cs.display !== 'none')) return null;
          return {{score, el:e, childCount:e.children.length}};
        }}).filter(Boolean);
        textCandidates.sort((a,b) => (b.score - a.score) || (a.childCount - b.childCount));
        el = textCandidates[0]?.el || null;
      }}
      if (!el && allowUnlabeled) {{
        el = candidates.find(e => {{
          const r = e.getBoundingClientRect();
          return r.width && r.height && r.bottom >= 0 && r.right >= 0 && r.top <= innerHeight && r.left <= innerWidth;
        }});
      }}
      if (!el) return {{error:'no matching button', texts:candidates.slice(0,20).map(e => (e.innerText || e.value || e.getAttribute('aria-label') || '').trim())}};
      el.scrollIntoView({{block:'center', inline:'center'}});
      const r = el.getBoundingClientRect();
      return {{x:r.left+r.width/2, y:r.top+r.height/2, text:(el.innerText || el.value || '').trim()}};
    }})()
    """
    val = await eval_value(cdp, expr)
    if not isinstance(val, dict) or val.get("error"):
        raise RecorderError(str(val))
    x, y = float(val["x"]), float(val["y"])
    for kind, extra in (("mouseMoved", {}), ("mousePressed", {"button":"left", "buttons":1, "clickCount":1}), ("mouseReleased", {"button":"left", "buttons":0, "clickCount":1})):
        await cdp.send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, **extra}, use_session=True, timeout=5.0)


async def capture_pair(cdp: CDPConnection, task_dir: Path, step: int, action_name: str, action_coro, *, validate_diff: bool, collapse_text_chars: int = 500) -> dict:
    step_dir = task_dir / f"step_{step:03d}"
    before_dir = step_dir / ".before_tmp"
    after_dir = step_dir / ".after_tmp"
    step_dir.mkdir(parents=True, exist_ok=True)
    before = await capture_state_with_recovery(cdp, before_dir, "before", SCREENSHOT_CONFIG, write_dom=True, dom_capture="slim", observation_max_elements=250)
    if before.dom_captured and (before_dir / "chromiumrl_dom_slim.json.gz").exists():
        shutil.copyfile(before_dir / "chromiumrl_dom_slim.json.gz", step_dir / "dom_before.json.gz")
    await action_coro()
    await wait_for_ready(cdp, timeout=6.0)
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
    diff = build_compact_dom_diff(
        before.chromiumrl_dom,
        after.chromiumrl_dom,
        compare_result=compare_result,
        compare_timing=compare_timing,
        max_entries=200,
        before_index=before.index,
        after_index=after.index,
        action=action_name.split()[0],
        collapse_text_chars=collapse_text_chars,
        validate_diff=validate_diff,
        verbosity=getattr(cdp, "dom_diff_verbosity", "compact"),
    )
    write_json_compact(step_dir / "dom_diff.json", diff)
    (step_dir / "dom_diff.txt").write_text(render_dom_diff_text(diff), encoding="utf-8")
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


def added_text_lines(diff: dict) -> list[str]:
    delta = diff.get("text_delta") if isinstance(diff.get("text_delta"), dict) else {}
    return [str(x) for x in delta.get("added", []) if isinstance(x, str)]


def assert_added_text_contains(diff: dict, needles: list[str]) -> tuple[bool, str]:
    lines = added_text_lines(diff)
    missing = [needle for needle in needles if not any(needle.lower() in line.lower() for line in lines)]
    return (not missing, "missing from +TEXT " + ", ".join(missing) if missing else "ok")


def redacted_value_filled(diff: dict, *, length: int | None = None) -> bool:
    def walk(value):
        if isinstance(value, dict):
            if value.get("redacted") is True and value.get("filled") is True and (length is None or value.get("length") == int(length)):
                return True
            return any(walk(v) for v in value.values())
        if isinstance(value, list):
            return any(walk(v) for v in value)
        return False
    return walk(diff)


def compact_full_equivalent_core(full: dict, compact: dict, needles: list[str]) -> tuple[bool, str]:
    for key in ("cross_document",):
        if full.get(key) != compact.get(key):
            return False, f"{key} mismatch"
    for key in ("added_total", "removed_total", "changed_total", "flagged_total"):
        if (full.get("stats") or {}).get(key) != (compact.get("stats") or {}).get(key):
            return False, f"stats.{key} mismatch"
    compact_text = diff_text(compact)
    missing = [needle for needle in needles if needle.lower() not in compact_text]
    if missing:
        return False, "compact missing " + ", ".join(missing)
    return True, "ok"


def changed_with_kind(diff: dict, kind: str) -> list[dict]:
    return [e for e in diff.get("changed", []) if isinstance(e, dict) and kind in (e.get("kind") or [])]


async def run(args):
    out = Path(args.output_root)
    out.mkdir(parents=True, exist_ok=True)
    summary = []

    async def add_result(task: Path, task_id: str, ok: bool, reason: str, diff: dict | None = None, **extra):
        row = {"id": task_id, "ok": ok, "reason": reason, **extra}
        if diff is not None:
            row["bytes"] = (task / "step_001/dom_diff.json").stat().st_size if (task / "step_001/dom_diff.json").exists() else 0
            row["stats"] = diff.get("stats", {})
            row["cross_document"] = diff.get("cross_document")
            row["frames"] = diff.get("frames", {})
            if args.validate_diff:
                row["compare_validation"] = diff.get("compare_validation", {})
        summary.append(row)

    async with CDPConnection(args.cdp_url, command_timeout=30) as cdp:
        cdp.log_path = out / "log.jsonl"
        cdp.dom_diff_verbosity = getattr(args, "dom_diff_verbosity", "compact")
        await enable_page_domains(cdp)
        await reset_chromiumrl_tracing(cdp)
        agent = DesktopWootzAgent(cdp)

        # Regression: CDP key dispatch must include real virtual key codes.
        task = out / "regress-key-enter"
        write_json(task / "manifest.json", {"task_id":"regress-key-enter", "kind":"runner-regression"})
        await navigate(cdp, data_url("""<input id='x' autofocus><script>window.events=[]; const x=document.getElementById('x'); x.addEventListener('keydown', e=>events.push('down:'+e.key+':'+e.keyCode)); x.addEventListener('change', e=>events.push('change:'+x.value));</script>"""))
        await agent.fill(selector="#x", text="abc")
        await agent.press("Enter")
        key_state = await eval_value(cdp, "({value:x.value, events})")
        ok = isinstance(key_state, dict) and key_state.get("value") == "abc" and "down:Enter:13" in (key_state.get("events") or []) and "change:abc" in (key_state.get("events") or [])
        await add_result(task, "regress-key-enter", ok, "ok" if ok else json.dumps(key_state, ensure_ascii=False))

        # Regression: model observations must include unlabeled native form controls.
        task = out / "regress-form-observation"
        write_json(task / "manifest.json", {"task_id":"regress-form-observation", "kind":"runner-regression"})
        await navigate(cdp, data_url("""<form><input type='checkbox'> checkbox 1 <select id='s'><option>Please select</option><option value='2'>Option 2</option></select></form>"""))
        snap = await agent.snapshot(observation_source="auto", observation_max_elements=250)
        has_checkbox = any((e.get("tag") == "input" and "checkbox" in (e.get("accessibleName") or "").lower()) for e in snap.refs.values())
        option_ref = next((r for r,e in snap.refs.items() if e.get("tag") == "option" and "Option 2" in (e.get("accessibleName") or "")), None)
        selected = await agent.select_option(ref=option_ref, text="Option 2") if option_ref else {}
        selected_value = await eval_value(cdp, "document.querySelector('#s').value")
        ok = bool(has_checkbox and option_ref and selected_value == "2")
        await add_result(task, "regress-form-observation", ok, "ok" if ok else f"has_checkbox={has_checkbox} option_ref={option_ref} selected={selected} value={selected_value}")

        # Regression: plain anchors with false hit-test metadata must not create overlay warnings.
        task = out / "regress-overlay-classifier"
        write_json(task / "manifest.json", {"task_id":"regress-overlay-classifier", "kind":"runner-regression"})
        ok = (
            not is_actionable_for_blocking({"tag":"a", "href":"/product", "isHitTestable":False})
            and is_actionable_for_blocking({"tag":"button", "isHitTestable":False})
            and is_actionable_for_blocking({"role":"checkbox", "isHitTestable":False})
        )
        await add_result(task, "regress-overlay-classifier", ok, "ok" if ok else "anchor/button/checkbox blocking classification mismatch")

        # Regression: prompt keeps generic grounding rules for ordinal and load-more tasks.
        task = out / "regress-prompt-grounding"
        write_json(task / "manifest.json", {"task_id":"regress-prompt-grounding", "kind":"runner-regression"})
        ok = "ordinal/list tasks" in SYSTEM_PROMPT and "scroll/load until more content appears" in SYSTEM_PROMPT
        await add_result(task, "regress-prompt-grounding", ok, "ok" if ok else "missing ordinal/load-more grounding rule")

        # Regression: compact formatting must preserve core verifier facts from full formatting.
        task = out / "regress-compact-full-equivalence"
        write_json(task / "manifest.json", {"task_id":"regress-compact-full-equivalence", "kind":"runner-regression"})
        before_slim = {"method":"slim_dom_projection", "url":"https://example.test/list", "title":"List", "nodes":[
            {"k":"/html[1]", "tag":"html", "text":"", "attrs":{}, "vis":True, "vp":True},
            {"k":"/html[1]/body[1]/main[1]/p[1]", "parent":"/html[1]", "tag":"p", "text":"Old value", "attrs":{}, "vis":True, "vp":True},
        ]}
        after_slim = {"method":"slim_dom_projection", "url":"https://example.test/detail", "title":"Detail", "nodes":[
            {"k":"/html[1]", "tag":"html", "text":"", "attrs":{}, "vis":True, "vp":True},
            {"k":"/html[1]/body[1]/main[1]/h1[1]", "parent":"/html[1]", "tag":"h1", "text":"Exact Product", "attrs":{}, "vis":True, "vp":True},
            {"k":"/html[1]/body[1]/main[1]/p[1]", "parent":"/html[1]", "tag":"p", "text":"£19.63", "attrs":{}, "vis":True, "vp":True},
            {"k":"/html[1]/body[1]/main[1]/p[2]", "parent":"/html[1]", "tag":"p", "text":"In stock (18 available)", "attrs":{}, "vis":True, "vp":True},
        ]}
        full = build_compact_dom_diff(before_slim, after_slim, before_index={"page":{"url":"https://example.test/list"}}, after_index={"page":{"url":"https://example.test/detail"}}, verbosity="full")
        compact = build_compact_dom_diff(before_slim, after_slim, before_index={"page":{"url":"https://example.test/list"}}, after_index={"page":{"url":"https://example.test/detail"}}, verbosity="compact")
        ok, reason = compact_full_equivalent_core(full, compact, ["Exact Product", "£19.63", "In stock (18 available)"])
        await add_result(task, "regress-compact-full-equivalence", ok, reason)

        # Unit-level controlled checkbox.
        task = out / "diff-checkbox"
        write_json(task / "manifest.json", {"task_id":"diff-checkbox", "kind":"dom-diff-benchmark"})
        await navigate(cdp, data_url("<label><input id='agree' type='checkbox' onclick=\"this.toggleAttribute('checked', this.checked)\"> I agree</label>"))
        diff = await capture_pair(cdp, task, 1, "click checkbox", lambda: click_selector(cdp, "#agree"), validate_diff=args.validate_diff)
        ok, reason = assert_contains(diff, ["attr:checked"])
        await add_result(task, "diff-checkbox", ok, reason, diff)

        # Unit-level controlled modal collapse.
        task = out / "diff-modal"
        write_json(task / "manifest.json", {"task_id":"diff-modal", "kind":"dom-diff-benchmark"})
        await navigate(cdp, data_url("""
          <main><h1>Product page</h1></main>
          <div id='cookie' role='dialog'><p>We use cookies for analytics and ads.</p><button id='dismiss' onclick="document.getElementById('cookie').remove()">Accept cookies</button></div>
        """))
        diff = await capture_pair(cdp, task, 1, "click dismiss modal", lambda: click_selector(cdp, "#dismiss"), validate_diff=args.validate_diff)
        ok, reason = assert_contains(diff, ["we use cookies"])
        collapsed = bool(diff.get("removed") and diff["removed"][0].get("descendant_count", 0) >= 1)
        await add_result(task, "diff-modal", ok and collapsed, reason if ok else reason, diff, collapsed=collapsed)

        # Best-effort live consent/banner page. Run before other same-origin
        # Heroku tests to avoid session-state contamination hiding the modal.
        task = out / "diff-modal-real"
        write_json(task / "manifest.json", {"task_id":"diff-modal-real", "kind":"dom-diff-benchmark"})
        try:
            with contextlib.suppress(Exception):
                await cdp.send("Storage.clearDataForOrigin", {"origin": "https://the-internet.herokuapp.com", "storageTypes": "all"}, use_session=True, timeout=5.0)
            await navigate(cdp, args.real_modal_url, timeout=15.0)
            modal_visible = await eval_value(cdp, "(() => { const m=document.querySelector('#modal,.modal,[role=dialog]'); if(!m) return false; const r=m.getBoundingClientRect(); const cs=getComputedStyle(m); return !!(r.width && r.height && cs.display !== 'none' && cs.visibility !== 'hidden' && Number(cs.opacity || 1) !== 0); })()")
            if not modal_visible:
                raise RecorderError("real modal precondition failed: modal is not visible before capture")
            diff = await capture_pair(cdp, task, 1, "dismiss live consent", lambda: click_button_by_text(cdp, ["accept", "agree", "allow all", "reject", "decline", "continue", "close", "x", "×"], allow_unlabeled=False), validate_diff=args.validate_diff, collapse_text_chars=args.collapse_text_chars)
            ok = bool(diff.get("removed")) or any("visibility" in (e.get("kind") or []) for e in diff.get("changed", []))
            await add_result(task, "diff-modal-real", ok, "ok" if ok else "no removed subtree or visibility change", diff)
        except Exception as error:
            summary.append({"id":"diff-modal-real", "ok":False, "reason":str(error), "url":args.real_modal_url})

        # Cross-document same-site navigation.
        task = out / "diff-navigate-same-site"
        write_json(task / "manifest.json", {"task_id":"diff-navigate-same-site", "kind":"dom-diff-benchmark"})
        await navigate(cdp, "https://books.toscrape.com/")
        title = await eval_value(cdp, "document.querySelector('article.product_pod h3 a')?.getAttribute('title') || document.querySelector('article.product_pod h3 a')?.textContent.trim() || ''")
        price = await eval_value(cdp, "document.querySelector('article.product_pod .price_color')?.textContent.trim() || ''")
        diff = await capture_pair(cdp, task, 1, "click first book", lambda: click_selector(cdp, "article.product_pod h3 a"), validate_diff=args.validate_diff, collapse_text_chars=args.collapse_text_chars)
        added = added_text_lines(diff)
        availability = next((line for line in added if "in stock (" in line.lower()), "")
        ok_added, reason_added = assert_added_text_contains(diff, [str(title), str(price), availability or "In stock ("])
        ok = bool(diff.get("cross_document")) and not diff.get("changed") and ok_added
        await add_result(task, "diff-navigate-same-site", ok, "ok" if ok else f"cross_document={diff.get('cross_document')} title={title!r} price={price!r} availability={availability!r} changed={len(diff.get('changed', []))} {reason_added}", diff, expected_title=title, expected_price=price, expected_availability=availability)

        # Real text/page transition benchmark retained for size and price evidence.
        task = out / "diff-text"
        write_json(task / "manifest.json", {"task_id":"diff-text", "kind":"dom-diff-benchmark"})
        await navigate(cdp, "https://books.toscrape.com/")
        diff = await capture_pair(cdp, task, 1, "click first book", lambda: click_selector(cdp, "article.product_pod h3 a"), validate_diff=args.validate_diff, collapse_text_chars=args.collapse_text_chars)
        ok, reason = assert_contains(diff, ["£"])
        await add_result(task, "diff-text", ok, reason, diff)

        # Real form fill then submit.
        task = out / "diff-form"
        write_json(task / "manifest.json", {"task_id":"diff-form", "kind":"dom-diff-benchmark"})
        await navigate(cdp, "https://quotes.toscrape.com/login")
        diff1 = await capture_pair(cdp, task, 1, "fill username", lambda: fill_selector(cdp, "input[name='username']", "x"), validate_diff=args.validate_diff)
        ok1, reason1 = assert_contains(diff1, ["attr:value", "x"])
        diff2 = await capture_pair(cdp, task, 2, "fill password", lambda: fill_selector(cdp, "input[name='password']", "y"), validate_diff=args.validate_diff)
        ok2 = redacted_value_filled(diff2, length=1)
        reason2 = "ok" if ok2 else "password value not represented as redacted filled property"
        diff3 = await capture_pair(cdp, task, 3, "click login", lambda: click_selector(cdp, "input[type='submit']"), validate_diff=args.validate_diff)
        ok3, reason3 = assert_contains(diff3, ["logout"])
        summary.append({"id":"diff-form", "ok":ok1 and ok2 and ok3, "reason": f"username={reason1}; password={reason2}; submit={reason3}", "bytes":sum((task/f"step_{i:03d}/dom_diff.json").stat().st_size for i in (1,2,3)), "stats": diff3.get("stats", {}), "enrichment": {"step1": diff1.get("enrichment"), "step2": diff2.get("enrichment")}, "compare_validation": diff3.get("compare_validation", {}) if args.validate_diff else {}})

        # Real unmirrored checkbox and select on a public Selenium test page.
        selenium_form = "https://www.selenium.dev/selenium/web/web-form.html"
        task = out / "diff-checkbox-real"
        write_json(task / "manifest.json", {"task_id":"diff-checkbox-real", "kind":"dom-diff-benchmark"})
        await navigate(cdp, selenium_form)
        diff = await capture_pair(cdp, task, 1, "click checkbox", lambda: click_selector(cdp, "input[type='checkbox']"), validate_diff=args.validate_diff)
        checked_changes = changed_with_kind(diff, "attr:checked")
        await add_result(task, "diff-checkbox-real", bool(checked_changes), "ok" if checked_changes else "no attr:checked change", diff, checked_changes=len(checked_changes))

        task = out / "diff-select"
        write_json(task / "manifest.json", {"task_id":"diff-select", "kind":"dom-diff-benchmark"})
        await navigate(cdp, selenium_form)
        diff = await capture_pair(cdp, task, 1, "select option", lambda: select_value(cdp, "select", "2"), validate_diff=args.validate_diff)
        selected_changes = changed_with_kind(diff, "attr:selected")
        option_changes = [e for e in selected_changes if e.get("tag") == "option"]
        ok = bool(option_changes) and len(option_changes) <= 2
        await add_result(task, "diff-select", ok, "ok" if ok else f"selected option changes={len(option_changes)}", diff, selected_option_changes=len(option_changes))

        # Real dynamic same-document UI change on a public Selenium test page.
        task = out / "diff-dynamic"
        write_json(task / "manifest.json", {"task_id":"diff-dynamic", "kind":"dom-diff-benchmark"})
        await navigate(cdp, "https://the-internet.herokuapp.com/add_remove_elements/")
        diff = await capture_pair(cdp, task, 1, "click add element", lambda: click_button_by_text(cdp, ["add element"]), validate_diff=args.validate_diff)
        ok = not diff.get("cross_document") and diff.get("stats", {}).get("added_total", 0) > 0 and "delete" in diff_text(diff)
        await add_result(task, "diff-dynamic", ok, "ok" if ok else "no same-document Delete button insertion", diff)

        # Pure scroll noise floor. active/current changes are retained as flagged_changes, not unflagged semantic changes.
        task = out / "diff-scroll"
        write_json(task / "manifest.json", {"task_id":"diff-scroll", "kind":"dom-diff-benchmark"})
        await navigate(cdp, "https://en.wikipedia.org/wiki/Web_browser")
        try:
            diff = await capture_pair(cdp, task, 1, "scroll 1000px", lambda: cdp.send("Runtime.evaluate", {"expression":"window.scrollBy(0,1000); true", "returnByValue": True}, use_session=True, timeout=5.0), validate_diff=args.validate_diff)
            stats = diff.get("stats", {})
            ok = stats.get("added_total") == 0 and stats.get("changed_total") == 0
            await add_result(task, "diff-scroll", ok, "ok" if ok else "non-empty unflagged semantic diff", diff, flagged_total=stats.get("flagged_total", 0))
        except Exception as error:
            summary.append({"id":"diff-scroll", "ok":False, "reason":str(error)})




        with contextlib.suppress(Exception):
            await cdp.send("ChromiumRL.disable", {}, use_session=True, timeout=2.0)
    write_json(out / "diff_benchmark_summary.json", {"completed_at": utc_now(), "results": summary})
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-url", default="http://127.0.0.1:49325")
    parser.add_argument("--output-root", default="diagnostics/v6/diff_benchmarks")
    parser.add_argument("--validate-diff", action="store_true")
    parser.add_argument("--collapse-text-chars", type=int, default=500)
    parser.add_argument("--dom-diff-verbosity", choices=("compact", "full"), default="compact")
    parser.add_argument("--real-modal-url", default="https://the-internet.herokuapp.com/entry_ad")
    asyncio.run(run(parser.parse_args()))
