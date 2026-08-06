import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recorder import CDPConnection, enable_page_domains, reset_chromiumrl_tracing

CDP = "http://127.0.0.1:49325"
URL = "https://en.wikipedia.org/wiki/Web_browser"

def ident(e):
    return e.get("xpath") or e.get("cssSelector") or e.get("fingerprint") or e.get("href") or e.get("text")

async def obs(cdp):
    r = await cdp.send("ChromiumRL.getAgentObservation", {}, use_session=True, timeout=30)
    res = r.get("result", r)
    return (res.get("observation", res) or {}).get("elements", [])

async def main():
    async with CDPConnection(CDP, command_timeout=30) as cdp:
        await enable_page_domains(cdp); await reset_chromiumrl_tracing(cdp)
        await cdp.send("Page.navigate", {"url": URL}, use_session=True)
        await asyncio.sleep(5)
        before = await obs(cdp)
        await cdp.send("Runtime.evaluate", {"expression": "window.scrollTo(0,1000); true",
                                            "returnByValue": True}, use_session=True)
        await asyncio.sleep(1.5)
        after = await obs(cdp)
        bmap = {ident(e): e for e in before if ident(e)}
        amap = {ident(e): e for e in after if ident(e)}
        rows = []
        for k in list(bmap)[:400]:
            if k in amap:
                b, a = bmap[k], amap[k]
                by = (b.get("bounds") or {}).get("y", b.get("centerY"))
                ay = (a.get("bounds") or {}).get("y", a.get("centerY"))
                if isinstance(by, (int, float)) and isinstance(ay, (int, float)):
                    rows.append({"id": str(k)[:60], "y_before": by, "y_after": ay, "delta": ay - by})
            if len(rows) >= 15: break
        print(json.dumps({"scrolled_by": 1000, "samples": rows}, indent=2))

asyncio.run(main())
