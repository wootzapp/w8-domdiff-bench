"""Check screenshot text with one paid actor response."""

import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--execute", action="store_true", help="authorize paid diagnostic requests")
args = parser.parse_args()
if not args.execute:
    parser.error("paid checks require explicit approval and --execute")

# Diagnostic
import asyncio, json, os, subprocess
from pathlib import Path
from w8bench.task_recorder.capture import CDPClient, CaptureBundle, _capture_screenshot
from w8bench.task_recorder.runner import ModelClient, load_env
from w8bench.task_recorder.recorder_support import write_json
load_env(Path('.env'))
base = Path('internal/screenshot_text_calibration')
sequence = 1
root = base / f'check_{sequence:04d}'
while root.exists():
    sequence += 1
    root = base / f'check_{sequence:04d}'
root.mkdir(parents=True)
print('Text calibration receipts:', root)
container = os.environ['CONTAINER_NAME']
fixture_path = f'/tmp/w8-text-{root.name}.html'
fixture_html = Path('tests/fixtures/screenshot_text_calibration.html').read_text()
subprocess.run(['docker', 'exec', '-i', container, 'python3', '-c',
    'import sys; from pathlib import Path; '
    'Path(sys.argv[1]).open("x", encoding="utf-8").write(sys.stdin.read())', fixture_path],
    input=fixture_html, text=True, check=True)
url = 'file://' + fixture_path
expected = {'8':'J7M4Q2R9', '10':'V3K8T5N6', '12':'P9D2W7X4', '14':'F6C1Y8H3'}
loop = asyncio.new_event_loop()
cdp = CDPClient('http://127.0.0.1:' + os.environ['CDP_HOST_PORT'],
    observation_mode='screenshot', viewport=(1365,768))
client = ModelClient(os.environ['GEMINI_API_KEY'], os.environ['ACTOR_MODEL'],
    os.environ.get('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta'))
results = []
try:
    loop.run_until_complete(cdp.connect())
    loop.run_until_complete(cdp.call('Page.navigate', {'url':url}))
    loop.run_until_complete(asyncio.sleep(1))
    screenshot = root / 'screenshot.png'
    screenshot.write_bytes(loop.run_until_complete(_capture_screenshot(cdp)))
    directory = root / 'turn'
    directory.mkdir()
    bundle = CaptureBundle(observation_mode='screenshot', screenshot_path=screenshot,
        document_url=url)
    decision, response = loop.run_until_complete(client.decide(
        task='Read the exact string beside each 8 px, 10 px, 12 px and 14 px label. '
             'Return a wait action with seconds 0. Put a JSON object mapping '
             'the keys "8", "10", "12", "14" to the four strings in memory.',
        step=1, max_steps=200, bundle=bundle, task_memory='', recent_actions=[],
        turn_dir=directory, viewport=(1365,768), max_output_tokens=10000))
    assert decision['action'] == 'wait' and decision['seconds'] == 0
    sent = json.loads((directory/'request.json').read_text())
    part = sent['contents'][0]['parts'][1]
    assert set(part) == {'inlineData'}
    assert sent['generationConfig']['mediaResolution'] == 'MEDIA_RESOLUTION_HIGH'
    readings = json.loads(decision['memory'])
    assert set(readings) == set(expected) and all(isinstance(v,str) for v in readings.values())
    rows = []
    for size, value in expected.items():
        actual = readings[size]
        previous = list(range(len(actual)+1))
        for i, left in enumerate(value, 1):
            current = [i]
            for j, right in enumerate(actual, 1):
                current.append(min(current[-1]+1, previous[j]+1,
                    previous[j-1] + (left != right)))
            previous = current
        rows.append({'font_css_pixels':int(size), 'expected':value, 'actual':actual,
            'exact':actual == value, 'character_accuracy':max(0,1-previous[-1]/len(value))})
    results.append({'media_resolution':'HIGH', 'rows':rows,
        'exact_rows':sum(row['exact'] for row in rows),
        'mean_character_accuracy':sum(row['character_accuracy'] for row in rows)/len(rows),
        'returned_model':response.get('model'), 'usage':response.get('usage')})
    print(json.dumps(results[-1]))
finally:
    write_json(root/'result.json', {'nominal_actor_responses':1, 'results':results})
    loop.run_until_complete(cdp.close_owned_target_on_failure())
    loop.run_until_complete(cdp.close())
    loop.close()
    subprocess.run(['docker', 'exec', container, 'python3', '-c',
        'from pathlib import Path; import sys; Path(sys.argv[1]).unlink(missing_ok=True)',
        fixture_path], check=True)
assert len(results) == 1
