#!/usr/bin/env python3
import asyncio, json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recorder import CDPConnection, RecorderError, target_id

CDP='http://127.0.0.1:49325'
HEAVY='https://www.amazon.com/s?k=wireless+mouse'

COMMANDS=[
  ('runtime_eval_no_enable','Runtime.evaluate',{'expression':'1+1','returnByValue':True},True,5.0),
  ('runtime_enable','Runtime.enable',{},True,5.0),
  ('dom_enable','DOM.enable',{},True,5.0),
  ('page_enable','Page.enable',{},True,5.0),
  ('chromiumrl_enable_heavy','ChromiumRL.enable',{'captureTouchTraces':True,'captureLayoutTimings':True,'captureCLSAttribution':True,'captureCompositorLayers':True},True,10.0),
  ('chromiumrl_enable_light','ChromiumRL.enable',{'captureTouchTraces':True,'captureLayoutTimings':False,'captureCLSAttribution':False,'captureCompositorLayers':False},True,10.0),
  ('chromiumrl_save_dom','ChromiumRL.saveDOMState',{},True,20.0),
  ('chromiumrl_observation','ChromiumRL.getAgentObservation',{},True,15.0),
]

async def browser_command(method, params=None, timeout=10.0):
    async with CDPConnection(CDP, command_timeout=10) as cdp:
        return await cdp.send(method, params or {}, timeout=timeout)

async def create_target(url):
    async with CDPConnection(CDP, command_timeout=10) as cdp:
        created=await cdp.send('Target.createTarget', {'url':url}, timeout=10)
        tid=str(created.get('targetId',''))
        await cdp.attach_to_target({'targetId': tid, 'id': tid, 'type': 'page', 'url': url})
        if url != 'about:blank':
            await asyncio.sleep(8)
        return tid

async def run_one(target_name, tid, command):
    label, method, params, use_session, timeout = command
    started=time.perf_counter()
    row={'target':target_name,'target_id':tid,'command':label,'method':method,'timeout_s':timeout}
    try:
        async with CDPConnection(CDP, command_timeout=10) as cdp:
            await cdp.attach_to_target({'targetId': tid, 'id': tid, 'type': 'page'})
            result=await cdp.send(method, params, use_session=use_session, timeout=timeout)
        row.update(ok=True, elapsed_ms=round((time.perf_counter()-started)*1000,3), result_keys=sorted(result.keys())[:20])
    except Exception as e:
        row.update(ok=False, elapsed_ms=round((time.perf_counter()-started)*1000,3), error=f'{type(e).__name__}: {e}')
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row

async def main():
    rows=[]
    async with CDPConnection(CDP, command_timeout=10) as cdp:
        about_tid=target_id(cdp.target)
    fresh_tid=await create_target('about:blank')
    heavy_tid=await create_target(HEAVY)
    targets=[('existing_about_or_selected',about_tid),('fresh_about_blank',fresh_tid),('heavy_real_page',heavy_tid)]
    for target_name, tid in targets:
        for cmd in COMMANDS:
            rows.append(await run_one(target_name, tid, cmd))
    Path('diagnostics/t2_probe_results.json').write_text(json.dumps({'cdp':CDP,'heavy_url':HEAVY,'rows':rows},indent=2), encoding='utf-8')

asyncio.run(main())
