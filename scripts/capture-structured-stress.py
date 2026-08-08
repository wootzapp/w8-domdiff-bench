#!/usr/bin/env python3
'''Live capture harness for structured-snapshot stress tests only.'''
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recorder import CDPConnection, RecorderError, chromiumrl_call, enable_page_domains, reset_chromiumrl_tracing, wait_for_ready  # noqa: E402


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def data_url(html: str) -> str:
    return 'data:text/html;charset=utf-8,' + quote(html)


async def evaluate(cdp, expression, timeout=10.0):
    result = await cdp.send('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True}, use_session=True, timeout=timeout)
    return result.get('result', {}).get('value')


async def navigate(cdp, url, timeout=30.0):
    await cdp.send('Page.navigate', {'url': url}, use_session=True, timeout=timeout)
    await wait_for_ready(cdp, timeout=timeout)
    await asyncio.sleep(1)


async def wait_until(cdp, expression, timeout=20.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            if await evaluate(cdp, expression, 3):
                return True
        except Exception:
            pass
        await asyncio.sleep(.2)
    return False


async def fill(cdp, selector, text):
    position = await evaluate(cdp, f'''(() => {{
      const e=document.querySelector({json.dumps(selector)}); if(!e)return null;
      e.scrollIntoView({{block:'center'}}); e.focus(); const r=e.getBoundingClientRect();
      return {{x:r.left+r.width/2,y:r.top+r.height/2}};
    }})()''')
    if not isinstance(position, dict):
        raise RecorderError(f'missing selector {selector}')
    for event_type, extra in (('mousePressed', {'button':'left','buttons':1,'clickCount':1}), ('mouseReleased', {'button':'left','buttons':0,'clickCount':1})):
        await cdp.send('Input.dispatchMouseEvent', {'type':event_type, 'x':position['x'], 'y':position['y'], **extra}, use_session=True, timeout=5)
    events = [
      {'type':'keyDown','key':'Control','code':'ControlLeft','modifiers':2},
      {'type':'keyDown','key':'a','code':'KeyA','modifiers':2},
      {'type':'keyUp','key':'a','code':'KeyA','modifiers':2},
      {'type':'keyUp','key':'Control','code':'ControlLeft'},
    ]
    for event in events:
        await cdp.send('Input.dispatchKeyEvent', event, use_session=True, timeout=5)
    await cdp.send('Input.insertText', {'text':text}, use_session=True, timeout=5)


async def press_enter(cdp):
    base = {'key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'nativeVirtualKeyCode':13}
    await cdp.send('Input.dispatchKeyEvent', {'type':'rawKeyDown', **base}, use_session=True, timeout=5)
    await cdp.send('Input.dispatchKeyEvent', {'type':'keyUp', **base}, use_session=True, timeout=5)


async def snapshot(cdp, path):
    result = await chromiumrl_call(cdp, 'ChromiumRL.captureStructuredSnapshot', {}, timeout=40, label=path.parent.name)
    write_json(path, result)
    return result


PAGE_PROBE = r'''(() => {
 const w=document.createTreeWalker(document,NodeFilter.SHOW_TEXT); let tn=0,ne=0;
 while(w.nextNode()){tn++;if((w.currentNode.nodeValue||'').trim())ne++;}
 return {url:location.href,title:document.title,readyState:document.readyState,
 elementCount:document.querySelectorAll('*').length,textNodeCount:tn,nonemptyTextNodeCount:ne,
 bodyTextChars:(document.body?.innerText||'').length,
 headings:Array.from(document.querySelectorAll('h1,h2,h3')).map((e,i)=>({index:i,tag:e.tagName.toLowerCase(),text:(e.innerText||'').replace(/\s+/g,' ').trim()})).filter(x=>x.text)};
})()'''


async def probe(cdp, path, extra='null'):
    value = await evaluate(cdp, f'(() => {{const page={PAGE_PROBE};const extra=({extra});return {{...page,extra}};}})()', 15)
    write_json(path, value)
    return value


async def pair(cdp, directory, before_extra, action, after_extra):
    before_probe = await probe(cdp, directory/'runtime_before.json', before_extra)
    before = await snapshot(cdp, directory/'before.json')
    await action()
    after_probe = await probe(cdp, directory/'runtime_after.json', after_extra)
    after = await snapshot(cdp, directory/'after.json')
    return {'beforeProbe':before_probe,'afterProbe':after_probe,'beforeStats':before.get('snapshot',{}).get('stats',{}),'afterStats':after.get('snapshot',{}).get('stats',{})}


async def node_cap(cdp, root):
    directory=root/'node-cap'
    await navigate(cdp,'https://en.wikipedia.org/wiki/United_States',40)
    await wait_until(cdp,"document.querySelectorAll('h2').length>15",20)
    async def reload():
        await cdp.send('Page.reload',{},use_session=True,timeout=30)
        await wait_for_ready(cdp,timeout=40)
        await wait_until(cdp,"document.querySelectorAll('h2').length>15",20)
    return await pair(cdp,directory,'null',reload,'null')


async def todo(cdp, root):
    directory=root/'client-rerender'
    await navigate(cdp,'https://demo.playwright.dev/todomvc/#/',30)
    await evaluate(cdp,'localStorage.clear();location.reload();true')
    await wait_for_ready(cdp,timeout=20)
    await wait_until(cdp,"!!document.querySelector('.new-todo')",15)
    await fill(cdp,'.new-todo','buy milk'); await press_enter(cdp)
    if not await wait_until(cdp,"document.querySelectorAll('.todo-list li').length===1",10):
        raise RecorderError('first todo not added')
    async def add_second():
        await fill(cdp,'.new-todo','walk dog'); await press_enter(cdp)
        if not await wait_until(cdp,"document.querySelectorAll('.todo-list li').length===2",10):
            raise RecorderError('second todo not added')
    before_extra="({todos:document.querySelectorAll('.todo-list li').length,counter:document.querySelector('.todo-count')?.innerText||'',items:Array.from(document.querySelectorAll('.todo-list label')).map(x=>x.innerText)})"
    after_extra="({todos:document.querySelectorAll('.todo-list li').length,counter:document.querySelector('.todo-count')?.innerText||'',items:Array.from(document.querySelectorAll('.todo-list label')).map(x=>x.innerText)})"
    return await pair(cdp,directory,before_extra,add_second,after_extra)


async def form_values(cdp, root):
    directory=root/'form-values'
    await navigate(cdp,'https://quotes.toscrape.com/login',30)
    async def action():
        await fill(cdp,'#username','structured-user'); await fill(cdp,'#password','structured-pass')
    extra="({username:document.querySelector('#username')?.value,password:document.querySelector('#password')?.value})"
    return await pair(cdp,directory,extra,action,extra)


async def dynamic(cdp, root):
    directory=root/'dynamic-insertion'
    await navigate(cdp,'https://the-internet.herokuapp.com/dynamic_loading/2',30)
    async def action():
        await evaluate(cdp,"document.querySelector('#start button').click();true")
        ok=await wait_until(cdp,"document.querySelector('#finish')&&getComputedStyle(document.querySelector('#finish')).display!=='none'&&document.querySelector('#finish').innerText.includes('Hello World!')",20)
        if not ok: raise RecorderError('dynamic content did not appear')
    extra="({finishText:document.querySelector('#finish')?.innerText||'',finishDisplay:document.querySelector('#finish')?getComputedStyle(document.querySelector('#finish')).display:'missing'})"
    return await pair(cdp,directory,extra,action,extra)


async def repeated(cdp, root):
    directory=root/'repeated-groups'
    items=''.join(f'<li><span>Item {i:02d}</span><button>Remove {i:02d}</button></li>' for i in range(1,13))
    html=f'''<!doctype html><title>Repeated insertion</title><main><h1>Queue</h1><ul id="queue">{items}</ul></main>
<script>window.prependItem=()=>{{const e=document.createElement('li');e.innerHTML='<span>Inserted item</span><button>Remove inserted</button>';document.querySelector('#queue').prepend(e);}};</script>'''
    await navigate(cdp,data_url(html),20)
    async def action(): await evaluate(cdp,'window.prependItem();true')
    extra="({items:Array.from(document.querySelectorAll('#queue li')).map(x=>x.innerText.replace(/\\s+/g,' ').trim())})"
    return await pair(cdp,directory,extra,action,extra)


async def run(args):
    root=args.output_root.resolve(); root.mkdir(parents=True,exist_ok=True); results=[]
    async with CDPConnection(args.cdp_url,command_timeout=45) as cdp:
        cdp.log_path=root/'capture.log.jsonl'
        await enable_page_domains(cdp); await reset_chromiumrl_tracing(cdp)
        for name,function in (('node-cap',node_cap),('client-rerender',todo),('form-values',form_values),('dynamic-insertion',dynamic),('repeated-groups',repeated)):
            if args.scenario and name != args.scenario:
                continue
            print('CAPTURE',name,flush=True)
            try:
                value=await function(cdp,root); value.update({'scenario':name,'ok':True})
            except Exception as error:
                value={'scenario':name,'ok':False,'error':str(error)}; print('FAILED',name,error,flush=True)
            results.append(value); write_json(root/'capture_summary.json',results)


def parse_args():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cdp-url',default='http://127.0.0.1:49325')
    parser.add_argument('--output-root',type=Path,default=ROOT/'diagnostics/structured-diff-stress')
    parser.add_argument('--scenario',choices=('node-cap','client-rerender','form-values','dynamic-insertion','repeated-groups'))
    return parser.parse_args()


if __name__=='__main__': asyncio.run(run(parse_args()))
