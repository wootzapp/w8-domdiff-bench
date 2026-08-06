#!/usr/bin/env python3
import asyncio, json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recorder import CDPConnection, enable_page_domains, reset_chromiumrl_tracing, target_id

CDP = "http://127.0.0.1:49325"
STABLE = "https://example.com/"
OTHER = "https://books.toscrape.com/"

def row(stage, method, ok, elapsed_ms, error="", keys=None):
    return {"stage": stage, "method": method, "ok": ok, "elapsed_ms": round(elapsed_ms, 3), "error": error, "keys": keys or []}

async def call(cdp, stage, method, params=None, timeout=8):
    st=time.perf_counter()
    try:
        r=await cdp.send(method, params or {}, use_session=True, timeout=timeout)
        return row(stage, method, True, (time.perf_counter()-st)*1000, keys=sorted(r.keys())[:20])
    except Exception as e:
        return row(stage, method, False, (time.perf_counter()-st)*1000, f"{type(e).__name__}: {e}")

async def calls(cdp, stage):
    return [
        await call(cdp, stage, "ChromiumRL.saveDOMState", {}, 8),
        await call(cdp, stage, "ChromiumRL.getAgentObservation", {}, 8),
        await call(cdp, stage, "Runtime.evaluate", {"expression":"1+1","returnByValue":True}, 8),
        await call(cdp, stage, "Page.getFrameTree", {}, 8),
    ]

async def rebind(cdp):
    tid = cdp.pinned_target_id or target_id(cdp.target)
    if cdp.session_id:
        try: await cdp.send("Target.detachFromTarget", {"sessionId": cdp.session_id}, timeout=5)
        except Exception: pass
    await cdp.attach_to_target({"targetId": tid, "id": tid, "type": "page"})
    cdp.pinned_target_id = tid
    await enable_page_domains(cdp)
    await reset_chromiumrl_tracing(cdp)

async def main():
    out=[]
    async with CDPConnection(CDP, command_timeout=10) as cdp:
        cdp.pinned_target_id = target_id(cdp.target)
        await enable_page_domains(cdp)
        await reset_chromiumrl_tracing(cdp)
        await cdp.send("Page.navigate", {"url": STABLE}, use_session=True, timeout=8)
        await asyncio.sleep(2)
        cdp.pinned_target_id = target_id(cdp.target)
        out += await calls(cdp, "stable_before")
        await cdp.send("Page.navigate", {"url": OTHER}, use_session=True, timeout=8)
        await asyncio.sleep(3)
        out += await calls(cdp, "after_cross_document_no_rebind")
        await rebind(cdp)
        out += await calls(cdp, "after_cross_document_rebind")
        await cdp.send("Runtime.evaluate", {"expression":"history.pushState({},'', '#same-doc'); true","returnByValue":True}, use_session=True, timeout=8)
        await asyncio.sleep(1)
        out += await calls(cdp, "after_same_document_no_rebind")
        await rebind(cdp)
        out += await calls(cdp, "after_same_document_rebind")
    Path("diagnostics/v3/nav_rebind_probe_output.json").write_text(json.dumps({"rows":out}, indent=2), encoding="utf-8")
    print(json.dumps({"rows":out}, indent=2))

asyncio.run(main())
