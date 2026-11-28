"""Check screenshot targeting with six paid actor responses."""

import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--execute", action="store_true", help="authorize paid diagnostic requests")
args = parser.parse_args()
if not args.execute:
    parser.error("paid checks require explicit approval and --execute")

# Diagnostic
import asyncio, json, os, subprocess, time
from pathlib import Path
from w8bench.task_recorder.capture import CDPClient, CaptureBundle, _capture_screenshot
from w8bench.task_recorder.agent_browser import AgentBrowserClient
from w8bench.task_recorder.runner import ModelClient, load_env, action_rejection_reason
from w8bench.task_recorder.recorder_support import write_json
load_env(Path('.env'))
base = Path('internal/coordinate_calibration')
sequence = 1
root = base / f'check_{sequence:04d}'
while root.exists():
    sequence += 1
    root = base / f'check_{sequence:04d}'
root.mkdir(parents=True)
print('Coordinate receipts:', root)
container = os.environ['CONTAINER_NAME']
fixture_path = f'/tmp/w8-coordinate-{root.name}.html'
fixture_html = Path('tests/fixtures/coordinate_calibration.html').read_text()
subprocess.run(['docker', 'exec', '-i', container, 'python3', '-c',
    'import sys; from pathlib import Path; '
    'Path(sys.argv[1]).open("x", encoding="utf-8").write(sys.stdin.read())', fixture_path],
    input=fixture_html, text=True, check=True)
url = 'file://' + fixture_path
loop = asyncio.new_event_loop()
cdp = CDPClient('http://127.0.0.1:' + os.environ['CDP_HOST_PORT'],
    observation_mode='screenshot', viewport=(1365, 768))
driver = AgentBrowserClient('unused', session='coordinate-calibration',
    cdp_url=cdp.http_url, timeout=90)
client = ModelClient(os.environ['GEMINI_API_KEY'], os.environ['ACTOR_MODEL'],
    os.environ.get('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta'))
results = []
targets = [('North west (NW)', 'north-west'), ('North east (NE)', 'north-east'),
    ('South west (SW)', 'south-west'), ('South east (SE)', 'south-east'),
    ('Small (+)', 'small'), ('Scrolled (S)', 'scrolled')]
try:
    loop.run_until_complete(cdp.connect())
    loop.run_until_complete(cdp.call('Page.navigate', {'url': url}))
    for index, (label, target) in enumerate(targets, 1):
        if target == 'scrolled':
            loop.run_until_complete(driver.execute({'action':'scroll', 'x':500,
                'y':500, 'pixels':1000}, cdp=cdp, viewport=(1365,768)))
        time.sleep(1)
        directory = root / f'turn_{index:06d}'
        directory.mkdir()
        screenshot = directory / 'screenshot.png'
        screenshot.write_bytes(loop.run_until_complete(_capture_screenshot(cdp)))
        loop.run_until_complete(cdp.call('Runtime.evaluate', {'expression':'hitTargets = []'}))
        bundle = CaptureBundle(observation_mode='screenshot', screenshot_path=screenshot,
            document_url=url)
        decision, response = loop.run_until_complete(client.decide(
            task=f'Click the visible button labelled {label}. Return one click action.',
            step=index, max_steps=200, bundle=bundle, task_memory='', recent_actions=[],
            turn_dir=directory, viewport=(1365,768), max_output_tokens=10000))
        rejection = action_rejection_reason(decision, frozenset(), [],
            observation_mode='screenshot', model_turn=index, max_turns=200)
        execution = None
        if not rejection and decision['action'] == 'click':
            execution = loop.run_until_complete(driver.execute(decision, cdp=cdp, viewport=(1365,768)))
        actual = loop.run_until_complete(cdp.call('Runtime.evaluate',
            {'expression':'hitTargets.at(-1) || null', 'returnByValue':True}))['result'].get('value')
        results.append({'target':target, 'actual':actual, 'hit':actual == target,
            'rejection':rejection, 'decision':decision, 'execution':execution,
            'returned_model':response.get('model'), 'usage':response.get('usage')})
        print(json.dumps(results[-1]))
finally:
    write_json(root / 'result.json', {'hits':sum(item['hit'] for item in results),
        'targets':len(targets), 'results':results})
    loop.run_until_complete(cdp.close_owned_target_on_failure())
    loop.run_until_complete(cdp.close())
    loop.close()
    subprocess.run(['docker', 'exec', container, 'python3', '-c',
        'from pathlib import Path; import sys; Path(sys.argv[1]).unlink(missing_ok=True)',
        fixture_path], check=True)
assert len(results) == len(targets) and all(item['hit'] for item in results)
