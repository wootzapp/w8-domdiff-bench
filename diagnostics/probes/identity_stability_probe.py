#!/usr/bin/env python3
import asyncio, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recorder import CDPConnection, enable_page_domains, reset_chromiumrl_tracing
CDP="http://127.0.0.1:49325"
URL="https://books.toscrape.com/"
CANDIDATES=["backendNodeId","nodeId","fingerprint","xpath","cssSelector","selector","idx"]
async def obs(cdp):
    r=await cdp.send("ChromiumRL.getAgentObservation", {}, use_session=True, timeout=10)
    res=r.get("result",r); return (res.get("observation",res) or {}).get("elements", [])
def table(a,b):
    n=max(len(a),1); out=[]
    for key in CANDIDATES:
        av=[e.get(key) for e in a if isinstance(e,dict) and e.get(key) is not None]
        bv=[e.get(key) for e in b if isinstance(e,dict) and e.get(key) is not None]
        aset=set(map(str,av)); bset=set(map(str,bv))
        out.append({"key":key,"presence_a":len(av),"presence_b":len(bv),"presence_rate":round(len(av)/n,3),"match_count":len(aset & bset),"match_rate":round(len(aset & bset)/max(len(aset),1),3)})
    return out
async def main():
    async with CDPConnection(CDP, command_timeout=10) as cdp:
        await enable_page_domains(cdp); await reset_chromiumrl_tracing(cdp)
        await cdp.send("Page.navigate", {"url":URL}, use_session=True, timeout=8)
        await asyncio.sleep(3)
        a=await obs(cdp); b=await obs(cdp)
        await cdp.send("Runtime.evaluate", {"expression":"window.scrollBy(0,600); true","returnByValue":True}, use_session=True, timeout=5)
        await asyncio.sleep(1)
        c=await obs(cdp)
        await cdp.send("Runtime.evaluate", {"expression":"document.body.setAttribute('data-probe','x'); true","returnByValue":True}, use_session=True, timeout=5)
        await asyncio.sleep(.5)
        d=await obs(cdp)
    result={"url":URL,"unchanged":table(a,b),"after_scroll":table(b,c),"after_dom_mutation":table(c,d),"counts":{"a":len(a),"b":len(b),"c":len(c),"d":len(d)}}
    Path("diagnostics/v3/identity_stability_probe_output.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
asyncio.run(main())
