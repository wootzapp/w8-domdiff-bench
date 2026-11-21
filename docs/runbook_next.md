# Collection and evaluation runbook

Run commands from the repository root using `.venv`. The catalog contains 40
public, read-only tasks. Each task has independent DOM and screenshot actors;
choose any positive trial count per arm. Actor requests use `gemini-3.8-flash`, a
10,000-token output limit, medium reasoning, 8,000 memory characters and at most
200 model turns. Read the [datacard](datacard.md) for the permitted arm differences
and the [evaluation protocol](evaluation-protocol.md) for metrics and denominators.

The commands below are separated by gates. Stop at a failed gate, inspect its
receipts and resolve it before continuing. A dry command makes no model calls.
Commands marked **paid** make requests only when deliberately executed. This
runbook does not authorize running them automatically.

## 1. Offline preflight

Configure `.env` using `.env.example` and install the project dependencies. Keep
credentials out of terminal output and version control. Environment values take
precedence over `.env`.

```sh
.venv/bin/python - <<'PY'
import hashlib, json, os
from collections import Counter
from pathlib import Path
from w8bench.task_recorder.runner import load_env, MAX_TASK_MEMORY_CHARS
from w8bench.task_recorder.task_cli import parse_args, parse_task_catalog
from w8bench.verifier.common import validate_endpoint_configs, native_judge_model
from w8bench.verifier.batch import judge_transport
from w8bench.settings import actor_settings
from w8bench.verifier.audit_requests import resolve_audit_config
from w8bench.verifier.package_manifests import require_local_packages
load_env(Path('.env'))
assert all(os.environ.get(k, '').strip() for k in ('OPENAI_API_KEY', 'GEMINI_API_KEY')), 'Missing credential'
assert os.environ.get('ACTOR_MODEL') == 'gemini-3.8-flash', 'Unexpected actor model'
assert judge_transport() == 'batch', 'Unexpected judge transport'
assert os.environ.get('NATIVE_JUDGE_PROFILE', 'primary') == 'primary', 'Unexpected native profile'
assert native_judge_model() == 'gemini-3.5-flash-lite', 'Unexpected native model'
media = actor_settings({})['media_resolution']
assert media == 'HIGH', 'Unexpected actor media resolution'
audit = resolve_audit_config()
assert audit['inventory'] == {'model': 'gemini-3.1-pro-preview', 'provider': 'google'}
assert audit['adjudication'] == {'model': 'gpt-6.1-sol', 'provider': 'openai'}
settings = parse_args(['--output-dir', 'recordings'])
assert settings.max_output_tokens == 10000 and settings.max_steps == 200
assert MAX_TASK_MEMORY_CHARS == 8000
catalog = Path('data/tasks.jsonl')
rows = parse_task_catalog(catalog.read_text(), source=str(catalog))
assert len(rows) == 40 and {r['task_id'] for r in rows} == {f'task_{n:02d}' for n in range(1, 41)}
assert Counter(r['difficulty'] for r in rows) == dict.fromkeys(('easy', 'medium', 'hard', 'complex'), 10)
assert Path('internal/task_validity.json').is_file(), 'Missing task-validity metadata'
validate_endpoint_configs('config')
require_local_packages()
print(json.dumps({'status': 'offline_preflight_passed', 'tasks': len(rows),
    'catalog_sha256': hashlib.sha256(catalog.read_bytes()).hexdigest(),
    'actor': os.environ['ACTOR_MODEL'], 'completion': 'gpt-6.1-sol',
    'rubric_model': 'gpt-5.2', 'verifier_models': ['gemini-3.5-flash-lite'], 'audit': audit,
    'judge_transport': judge_transport(), 'native_profile': 'primary',
    'max_output_tokens': settings.max_output_tokens, 'max_turns': settings.max_steps,
    'media_resolution': media,
    'memory_characters': MAX_TASK_MEMORY_CHARS}, indent=2))
PY
```

A requested output name already on disk selects the next available numeric
suffix. Read the printed schedule path and use its actual run name for later
commands.

This checks configured identities and credential presence, not provider access,
credit balance or model compatibility. It does not print keys or contact a provider.
Check browser ownership and reachability without running an actor:

```sh
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
```

Choose `BENCH_TRIALS` explicitly in your shell, then require it before planning:

```sh
: "${BENCH_TRIALS:?Set a positive integer trial count per arm}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name collection \
  --judge-model gpt-6.1-sol --dry-run
```

When any required frozen rubric is missing, this writes only
`recordings/collection/catalog.jsonl` and
`recordings/collection/schedule_preview.jsonl`. Inspect all `80 × k` task/arm/trial
rows, alternating arm order, intended output paths and controls. It is not the
executable attempt ledger. Rubric-free planning cannot start an actor or judge.
Execution requires approved frozen rubrics and creates `ledger.jsonl` separately.
When all frozen rubrics exist, `--dry-run` creates or validates the ordinary
`ledger.jsonl`. To execute that schedule, remove `--dry-run` and add `--resume`,
using the run name printed by the planning command. A planning-only preview
cannot be resumed as execution; use a new run after rubric approval.

Task validity is checked against `internal/task_validity.json` using the UTC date.
Expired tasks stop planning/execution unless the operator explicitly supplies
`--allow-expired`. That override is recorded; it is not a claim of renewed
readiness. Keep the same override on a resumed command. A broken task is replaced
only under the documented readiness rules, with a reason and receipt, never
because its actor score is poor.

**Gate:** expected catalog task IDs and count, credentials present, pinned settings, browser
status and correct schedule preview. **Model calls: 0.**

## 2. Generate all rubric drafts and prepare review

Draft generation uses the existing screenshot verifier's rubric-generation and
dependency-check prompts, with `gpt-5.2`. It receives the expanded catalog task and
start URL, not an actor trajectory or result. The action-judge client is configured
but is not normally called by these two preparation stages. The native JSON output contract is `native-rubric-output-contract/v3`; output
settings and response-repair budgets follow the verifier.

First run the read-only preflight:

```sh
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage draft --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics
```

Then, after authorizing the paid preparation requests:

```sh
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage draft --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Run one rubric preparation command at a time. The same command resumes preparation: completed drafts are reused, and failed or
interrupted draft attempts retain their call/usage receipts before another
attempt is made. A changed catalog/task binding is rejected. Do not use a new
directory to conceal earlier costs. Frozen rubrics prevent drafting into the same
version; choose a distinct version for a deliberate task/rubric revision.
Authentication exhaustion marks that task ungraded and continues other tasks.
The workflow reports `partial` and exits nonzero until every task has a completed
draft. Resume preserves the failed attempt's calls and usage. Effective request
settings must match on resume; credentials and configuration file locations do
not define that behavioral contract.

Prepare the offline review document:

```sh
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage review --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Review `internal/rubrics/review.md`, each draft and its expanded instruction.
The review also includes dependency-check responses, per-model generation usage,
receipt paths and an explicitly unknown USD cost until a trusted price
configuration is supplied. Check coverage, stopping conditions, forbidden actions, observability in either
arm, criterion overlap and weights. Mutable values must be judged using the
values observed during the run and an observation date, rather than a frozen
answer. Correct criteria in `internal/rubrics/drafts/task_*.json` if necessary,
then regenerate the review document. Keep task identity, expanded instruction and
start URL unchanged. A changed draft resets its approval; unchanged approvals
are retained and prior review versions are archived.

**Gate:** all 40 valid drafts and a human review of every criterion. Generation
normally needs **80 logical calls**: two per task, before existing retries or
repair iterations. Review needs **0**. Actual calls, transport attempts and token
usage are in each `task_XX.metrics.json`, including prior attempts; unknown usage
is not a measured zero.

## 3. Approve and freeze

Approval is an explicit review action. In `internal/rubrics/review.json`, fill
`approved_by` and `approval_date` (`YYYY-MM-DD`), and set every task's `approved`
to `true` with nonempty `review_notes` after checking its listed requirements.
Do not alter binding hashes or substitute criteria in the approval file.

Validate approval without writing, then freeze offline:

```sh
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage freeze --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics

.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage freeze --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Freeze checks catalog/task/draft hashes, approval and unscored positive criterion
weights. It writes one `data/rubrics/task_XX.json` per task, bound to the approval
file hash, and `internal/rubrics/freeze.json`. An identical repeat is harmless;
a changed existing frozen rubric is refused. Reuse the same frozen criteria and
weights across both arms, all trials and every grading stage.

**Gate:** 40 frozen task rubrics, matching task definitions and approved review
hash. **Model calls: 0.**

## 4. Small model compatibility gate

This **paid** command dispatches eight nominal logical requests: two actor
requests, three native/rubric model transport probes, one completion request and
one request through each actual inventory/adjudication transport. It uses
`gpt-5.2`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`, `gemini-3.8-flash` and `gpt-6.1-sol`, with a
PNG, strict actor/completion schemas and configured Gemini settings. The two
audit probes use their actual system prompts with a synthetic marker response.
These are transport compatibility diagnostics; the pilot exercises full native
stage and audit payloads. No browser or action is launched.

```sh
.venv/bin/python - <<'PY'
import asyncio, base64, json, logging, os
from pathlib import Path
from PIL import Image, ImageDraw
from w8bench.task_recorder.capture import CaptureBundle
from w8bench.task_recorder.runner import ModelClient, load_env, response_text, action_rejection_reason
from w8bench.task_recorder.recorder_support import write_json
from w8bench.verifier.instrumentation import instrument_client_calls, usage_dict
from w8bench.verifier.completion import GRADE_SCHEMA
from w8bench.verifier.clients.retry import GracefulRetryClient
from w8bench.model_identity import match_model_id, response_acceptance
from w8bench.verifier.audit_requests import _completion, SYSTEM_PROMPT, ADJUDICATION_SYSTEM_PROMPT
load_env(Path('.env'))
os.environ['JUDGE_TRANSPORT'] = 'normal'
assert os.environ.get('ACTOR_MODEL') == 'gemini-3.8-flash'
base = Path('internal/compatibility')
sequence = 1
root = base / f'check_{sequence:04d}'
while root.exists():
    sequence += 1
    root = base / f'check_{sequence:04d}'
root.mkdir(parents=True)
print('Compatibility receipts:', root)
image = Image.new('RGB', (1365, 768), 'white')
ImageDraw.Draw(image).text((40, 40), 'COMPATIBILITY_OK', fill='black')
image.save(root / 'screenshot.png')
(root / 'dom.json').write_text('{}')
(root / 'dom_model.txt').write_text('URL: https://example.test/\nVisible text: COMPATIBILITY_OK\n')
url = 'data:image/png;base64,' + base64.b64encode((root / 'screenshot.png').read_bytes()).decode()
loop = asyncio.new_event_loop()
receipts, clients = [], []
status = 'failed'
native_roles = {
    'gpt-5.2': ['rubric_preparation.generation', 'rubric_preparation.dependency'],
    'gemini-3.5-flash-lite': [f'{mode}.{stage}' for mode in ('dom_model', 'screenshot_verifier')
        for stage in ('relevance', 'evidence_analysis', 'condition_disambiguation',
                      'reality_check', 'whole_rubric_rescore', 'per_criterion_rescore',
                      'side_effects', 'outcome', 'failure_analysis',
                      'action_only_scoring', 'task_validity', 'trajectory_validity')],
    'gemini-3.1-pro-preview': ['native_pro.transport'],
}
def record_matches(receipt, model, returned, roles):
    ids = list(returned) or [None]
    receipt['model_checks'] = [dict(stage_role=role, **match_model_id(model, identity))
        for role in roles for identity in ids]
    for check in receipt['model_checks']:
        print(json.dumps(check))
    assert all(check['matched'] for check in receipt['model_checks']), 'Missing or refused returned model ID'
try:
    for arm in ('dom', 'screenshot'):
        client = ModelClient(os.environ['GEMINI_API_KEY'], os.environ['ACTOR_MODEL'],
            os.environ.get('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta'))
        bundle = CaptureBundle(snapshot_path=root/'dom.json', screenshot_path=root/'screenshot.png',
            model_text=(root/'dom_model.txt').read_text(), observation_mode=arm,
            document_url='https://example.test/', document_language='en',
            agent_browser_action_text='- button "COMPATIBILITY_OK" [ref=e1]',
            agent_browser_refs=frozenset({'e1'}))
        turn = root / arm
        turn.mkdir()
        receipt = {'stage': 'actor', 'arm': arm, 'configured_model': client.model}
        receipts.append(receipt)
        try:
            decision, response = loop.run_until_complete(client.decide(
                task='Synthetic compatibility check only. Read the visible marker and return a wait '
                     'proposal with seconds 0 and thought COMPATIBILITY_OK. Set unused fields '
                     'to null. The proposal will not be executed.',
                step=1, max_steps=200, bundle=bundle, task_memory='', recent_actions=[],
                turn_dir=turn, viewport=(1365,768), max_output_tokens=10000))
            assert not action_rejection_reason(decision, bundle.agent_browser_refs, [],
                observation_mode=arm, model_turn=1, max_turns=200)
            assert decision['action']=='wait' and decision['seconds']==0
            assert 'COMPATIBILITY_OK' in decision['thought']
            record_matches(receipt, client.model, [response.get('model')], [f'actor.{arm}'])
            receipt['status'] = 'passed'
        finally:
            receipt.update(response=client.last_response, input_report=client.last_input_report)
    for model in ('gpt-5.2', 'gemini-3.5-flash-lite', 'gemini-3.1-pro-preview'):
        client = GracefulRetryClient.from_path('config', logger=logging.getLogger('compatibility'), eval_model=model, evidence_mode='screenshot_verifier')
        clients.append(client)
        calls = instrument_client_calls(client, receipt=True)
        receipt = {'stage':'native_transport', 'configured_model':model, 'stage_roles':native_roles[model], 'call_metrics':calls}
        receipts.append(receipt)
        try:
            result = loop.run_until_complete(client.create(messages=[{'role':'user','content':[
                {'type':'text','text':'Read the visible marker. Return JSON {"marker":"COMPATIBILITY_OK"}.'},
                {'type':'image_url','image_url':{'url':url,'detail':'high'}}]}], json_output=True))
            assert result.finish_reason=='stop' and json.loads(result.content)=={'marker':'COMPATIBILITY_OK'}
            record_matches(receipt, model, calls['returned_models'], native_roles[model])
            receipt['status']='passed'
        finally:
            receipt['usage']=usage_dict(client)
    client = ModelClient(os.environ['OPENAI_API_KEY'], 'gpt-6.1-sol',
        os.environ.get('OPENAI_BASE_URL','https://api.openai.com/v1'))
    receipt={'stage':'completion','configured_model':'gpt-6.1-sol'}
    receipts.append(receipt)
    response = None
    try:
        response=client._post({'model':'gpt-6.1-sol','instructions':'Return the supplied compatibility criterion as success, reason marker visible, states [1].',
            'input':[{'role':'user','content':[{'type':'input_text','text':'Criterion id: compatibility. State 1 contains COMPATIBILITY_OK.'},
                {'type':'input_image','image_url':url,'detail':'high'}]}], 'max_output_tokens':10000,
            'reasoning':{'effort':'medium'},'text':{'format':{'type':'json_schema','name':'completion_grade','strict':True,'schema':GRADE_SCHEMA}}})
        acceptance=response_acceptance('gpt-6.1-sol', response.get('model'), response, output_cap=10000)
        receipt['acceptance']=acceptance
        record_matches(receipt, 'gpt-6.1-sol', [response.get('model')], ['completion'])
        assert response.get('status')=='completed'
        assert acceptance['accepted'], acceptance['refusal_reason']
        value=json.loads(response_text(response))
        assert set(value)==set(GRADE_SCHEMA['required']) and isinstance(value['criteria'],list) and len(value['criteria'])==1
        criterion=value['criteria'][0]
        assert set(criterion)==set(GRADE_SCHEMA['properties']['criteria']['items']['required'])
        assert criterion['id']=='compatibility' and criterion['verdict']=='success'
        assert isinstance(criterion['reason'],str) and criterion['reason']
        assert isinstance(criterion['states'],list) and all(type(index) is int for index in criterion['states'])
        assert criterion['states']==[1]
        receipt['status']='passed'
    finally:
        receipt.update(response=response, usage=response.get('usage') if response else None)
    for stage, model, provider, system in (
        ('inventory', 'gemini-3.1-pro-preview', 'google', SYSTEM_PROMPT),
        ('adjudication', 'gpt-6.1-sol', 'openai', ADJUDICATION_SYSTEM_PROMPT),
    ):
        records=[]
        receipt={'stage':stage, 'configured_model':model, 'provider':provider, 'call_records':records}
        receipts.append(receipt)
        try:
            value=_completion(model, [{'role':'system','content':system},
                {'role':'user','content':[{'type':'text','text':'Synthetic transport compatibility only. The supplied state contains COMPATIBILITY_OK. Return only JSON {"marker":"COMPATIBILITY_OK"}; no criterion audit is requested.'},
                    {'type':'image_url','image_url':{'url':url,'detail':'high'}}]}], records=records, provider=provider)
            record_matches(receipt, model, [record.get('response_model') for record in records], [stage])
            assert value=={'marker':'COMPATIBILITY_OK'}
            receipt.update(status='passed', response=value)
        finally:
            receipt['usage']=[record.get('usage') for record in records]
    status='passed'
except BaseException as error:
    if receipts and receipts[-1].get('status') != 'passed':
        receipts[-1].update(status='failed', error_type=type(error).__name__, error=str(error))
    raise
finally:
    write_json(root/'result.json', {'status':status,'nominal_logical_calls':7,'receipts':receipts})
    for client in clients:
        loop.run_until_complete(client.close())
    loop.close()
print('Compatibility gate:', status)
PY
```

**Gate:** all seven checks pass with permitted returned IDs, complete
responses, valid schema/JSON and readable image markers. Inspect
`internal/compatibility/check_NNNN/result.json` and the actor requests/responses. Normally
**7 logical calls**; existing SDK/client retry policies can increase HTTP attempts.
Each native transport probe lists all default native stage roles for its model,
including both rubric preparation roles. Every role records and prints its
configured ID, returned ID and the shared matcher's `exact`, `suffix` or `refused`
form. Completion, inventory and adjudication have separate role receipts. Missing
or refused IDs block real runs. This gate deliberately requires a matching native
transport ID; production native mismatches remain diagnostic.
This checks small request compatibility, not long-context limits, real browser
control or the complete audit protocol. The pilot checks those integration paths.
Stop on a model mismatch, unsupported parameter, incomplete response or malformed
output and resolve the configuration rather than changing the benchmark silently.

### Browser coordinate calibration

With the browser running and no task active, run the local fixture check. It uses
synthetic coordinates and makes **0 model calls**:

```sh
W8_CALIBRATION_CDP_URL="$(.venv/bin/python - <<'PY'
import os
from pathlib import Path
from w8bench.task_recorder.runner import load_env
load_env(Path('.env'))
print('http://127.0.0.1:' + os.environ['CDP_HOST_PORT'])
PY
)" .venv/bin/python -m pytest -q -s tests/capture/test_evidence.py \
  -k normalized_coordinate_calibration_in_w8
```

The fixture checks four corners, a small button and scrolled content through the
real executor, plus image dimensions and device pixel ratio 1. Inspect
`reports/browser_calibration/run_N/calibration.json`; all six targets must be hit.
The check opens a fresh page and closes prior task pages.

After approval for paid compatibility checks, use the same fixture for **6
screenshot-actor responses**. The fixture is served only on the local Docker
bridge. It supplies no DOM or target boxes to the actor; target detection is used
only to score the click afterwards. Run this before the pilot, with no task active:

```sh
.venv/bin/python - <<'PY'
import asyncio, functools, http.server, json, os, subprocess, threading, time
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
networks = json.loads(subprocess.check_output(['docker', 'inspect', '--format',
    '{{json .NetworkSettings.Networks}}', container], text=True))
gateway = next(iter(networks.values()))['Gateway']
server = http.server.ThreadingHTTPServer((gateway, 0), functools.partial(
    http.server.SimpleHTTPRequestHandler, directory=str(Path('tests/fixtures').resolve())))
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f'http://{gateway}:{server.server_port}/coordinate_calibration.html'
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
    server.shutdown()
    server.server_close()
assert len(results) == len(targets) and all(item['hit'] for item in results)
PY
```

**Gate:** six correct hits, normalized integer coordinates, permitted returned
model ID and complete responses. Review `internal/coordinate_calibration/check_NNNN/result.json`
and saved requests, responses and transport receipts. The transport gate plus
coordinate calibration makes **13 nominal model checks**; transient failures
can add transport attempts. Complete the text calibration below before the pilot.

### Screenshot text calibration

With no task active, the following **paid** diagnostic reads four high-contrast
strings at 8, 10, 12 and 14 CSS pixels. The screenshot actor uses HIGH and sends
one saved PNG for **1 nominal actor response**. The model
receives only the image and the reading instruction; expected strings are used
only to score its response. No returned browser action is executed.

```sh
.venv/bin/python - <<'PY'
import asyncio, functools, http.server, json, os, subprocess, threading
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
networks = json.loads(subprocess.check_output(['docker', 'inspect', '--format',
    '{{json .NetworkSettings.Networks}}', os.environ['CONTAINER_NAME']], text=True))
gateway = next(iter(networks.values()))['Gateway']
server = http.server.ThreadingHTTPServer((gateway, 0), functools.partial(
    http.server.SimpleHTTPRequestHandler, directory=str(Path('tests/fixtures').resolve())))
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f'http://{gateway}:{server.server_port}/screenshot_text_calibration.html'
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
    server.shutdown()
    server.server_close()
assert len(results) == 1
PY
```

**Gate:** complete responses, the configured returned model, correct resolution
in each saved request, and reviewed per-size exact-match and character accuracy.
Inspect `internal/screenshot_text_calibration/check_NNNN/result.json` and the
request/response. This measures fixture OCR, not general page legibility. The
screenshot actor uses HIGH. The seven transport checks, six coordinate checks
and one text check make **14 nominal model checks**, plus any transport retries.
Actor generation uses local input estimation. Cached model metadata sets the
limit; estimates above 50% trigger free `countTokens` requests with transport
retries and a recorded local-estimate fallback. Preflight requests do not consume
actor model turns.

## 5. Four-task pilot with full evaluation

The pilot uses `task_26` (easy), `task_02` (medium), `task_19` (hard) and
`task_25` (complex),
both arms, one trial each. It is separate from the full collection.

```sh
./scripts/run-task task_26 task_02 task_19 task_25 --trials 1 \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name pilot --dry-run
```

Set `BENCH_PILOT_RUN` to the run name printed above, such as `pilot` or
`pilot_2`, before executing its ledger:

```sh
: "${BENCH_PILOT_RUN:?Set the printed pilot run name}"
./scripts/run-task task_26 task_02 task_19 task_25 --trials 1 \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name "$BENCH_PILOT_RUN" --resume

./scripts/run-comparison --ledger "recordings/$BENCH_PILOT_RUN/ledger.jsonl" \
  --output "reports/$BENCH_PILOT_RUN"
```

Each actor attempt receives a fresh browser profile. Both arms finish before
their full evaluation starts: paired completion, screenshot verifier, DOM verifier
and a within-run audit with inventory/adjudication. These compare saved formats
from the same actor run; they do not pair the DOM actor's evidence with the
screenshot actor's evidence. Passive capture failure is recorded separately.

**Gate:** eight scheduled rows have recorded final technical/evaluation outcomes;
inspect request isolation, capture hashes/timings, actor returned IDs, grading
coverage, frozen rubric identity, judge receipts and the report. Genuine task
failure is a result, not permission to rewrite a task. Resolve generic setup
faults before authorizing the full collection. The pilot permits at most
**1,600 final-attempt actor responses** (eight × 200), plus up to 1,600 responses
from prior technical attempts. Up to three transport attempts per response gives
a 9,600-attempt upper bound. Judge calls depend on states, criteria, selected
evidence and existing retries; do not budget them as one per task.
Aggregation itself uses **0 model calls**.

## 6. Full collection, resume and evaluation

Supply any positive `BENCH_TRIALS`; omit positional selectors to use all 40 tasks:

```sh
: "${BENCH_TRIALS:?Set a positive integer trial count per arm}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name collection --dry-run
```

Set `BENCH_COLLECTION_RUN` to the printed run name, then execute that ledger:

```sh
: "${BENCH_COLLECTION_RUN:?Set the printed collection run name}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name "$BENCH_COLLECTION_RUN" --resume
```

The executable ledger has `80 × k` task/arm/trial rows, retaining startup
failures and missing recordings. A row can have two actor attempts when its first
attempt is technical. Task/arm/trial order alternates which arm runs first.
Execution uses `--resume` and the existing ledger's printed run name; completed final attempts are
retained and pending technical reruns continue from their recorded attempt. The command rejects changed catalog, rubric,
effective settings, browser source provenance or task/trial identities. Do not change the trial count
under an existing run name. Use a separate collection name for a different plan.

Without `--resume`, a command creates a new run; `--resume` requires an existing
execution-capable ledger.

Both actors for a task/trial finish their final attempts before their judges.
A technical failure permits one fresh attempt; success, turns and tokens use the
final attempt. Prior technical-attempt costs remain separate. Transient actor
requests allow two further transport attempts, which do not consume model turns
until a response arrives. Website blocks, actor failures, turn caps and provider
auth/quota/billing errors do not trigger a technical rerun. Technical outcomes and
completion grades remain separate. Inspect ledger and logs before repeating any
command; do not treat missing usage as free work or erase failed-attempt receipts.

To retry an incomplete evaluation without repeating a finished actor, use the
recording path stored in its ledger row:

```sh
: "${BENCH_RECORDING:?Set one completed recording path from ledger.jsonl}"
: "${BENCH_TASK_ID:?Set its task_XX catalog identity}"
.venv/bin/python -m w8bench.verifier.run_comparison \
  --run "$BENCH_RECORDING" --rubric "data/rubrics/$BENCH_TASK_ID.json" \
  --judge-model gpt-6.1-sol

.venv/bin/python -m w8bench.verifier.run_comparison \
  --run "$BENCH_RECORDING" --rubric "data/rubrics/$BENCH_TASK_ID.json" \
  --judge-model gpt-6.1-sol --execute
```

The first command is a read-only evaluation preflight. The second reuses completed
bound stages and preserves prior failed/interrupted attempt receipts. Resume the
batch command afterward to reconcile its ledger evaluation status. Do not modify
saved evidence, requests, hashes or completion files to force a cache hit.
The [effective settings contract](evaluation-protocol.md#effective-settings-contract)
includes model/provider/routes/base URLs, reasoning and output/turn/memory caps,
prompt/schema hashes and versions, task-specific rubric hashes, normalized
configuration content hashes, browser pins and available actual source provenance.
Credentials, ports, container/Compose names, image names/tags and file locations
are excluded. Differences in effective settings refuse cached reuse and resume.
Native scoring exhaustion retains usage with null scores and a `judge_fallback`
reason; ungraded audits have no pooled loss rate. Completion has one request per
grading attempt; inventory and adjudication each allow three validation attempts.

**Gate:** all `80 × k` ledger rows and their attempt histories are accounted for,
with evaluation coverage reported. Final attempts permit at most **16,000 × k
actor responses** (40 tasks × two arms × k × 200). Prior technical attempts can
add the same number; the transport-attempt upper bound is **96,000 × k**. Full
evaluation adds one primary completion request per final recording, variable
original-verifier calls, and variable inventory/
adjudication requests; existing retries can add transport attempts. Rubrics stay
fixed and are not regenerated during evaluation. Exact totals come from receipts,
not from multiplying task counts by an assumed fixed judge-call count.

## 7. Aggregate and inspect the metrics

Aggregation is local and makes no model calls. Use the selected collection name:

```sh
: "${BENCH_COLLECTION_RUN:?Set the printed collection run name}"
./scripts/run-comparison --ledger "recordings/$BENCH_COLLECTION_RUN/ledger.jsonl" \
  --output "reports/$BENCH_COLLECTION_RUN"
```

By default the report calculates supported pass@k values from the actual trial
count. `--pass-k` can restrict the requested positive k values to those supported
for every retained task. All-trial success reliability is reported separately.

| Measurement or receipt | Location |
| --- | --- |
| Full denominator, ordering, technical/grade/evaluation outcomes, logs and recording paths | `recordings/<collection-run>/ledger.jsonl` |
| Actor response turns, rejected proposals, termination responses, input/output usage, cached/reasoning subsets and output-limit flags | Recording `decisions.jsonl`, `turns/turn_*/request.json`, `response.json`, `result.json` |
| Actor transport attempts, durations, statuses, parser stage and usage coverage | Per-turn transport receipts and raw failed responses |
| Earlier technical-attempt costs | `cost_streams["technical_attempts:actor"]` and retained ledger `attempts` |
| Current paired artifacts, capture ordering/timing, navigation flags, hashes and passive failures | Recording `manifest.json`, `steps/step_*/capture.json` and state files |
| Frozen task settings, actor returned model IDs, action counts and final technical status | Recording `task.json`, `manifest.json`, `final.json` |
| Independent paired completion and its judge usage | Shared `evaluations/common/.../completion.json` and profile `paired_completion.json` |
| Screenshot/DOM auxiliary scores, model-call/usage receipts, logs and validity diagnostics | The `evaluation.json` path in the ledger and its stage subdirectories |
| Two within-run loss directions per actor run, four loss values across arms per task/trial, recovery and coverage | Evaluation `evidence_audit.json`, linked from `evaluation.json` |
| Rubric-generation costs including prior attempts | `internal/rubrics/drafts/task_XX.metrics.json`; workflow `generation.json` |
| Approval binding and immutable shared rubrics | `internal/rubrics/review.json`, `freeze.json`, `data/rubrics/task_XX.json` |
| Cross-arm task/trial pairs and per-task criteria/pass@k | `reports/<collection-run>/pairs.json`, `per_task.json` |
| Aggregate turns/tokens, token-per-turn distributions, completion, pass@k, auxiliary scores, audit directions, cost streams and coverage by arm/difficulty | `reports/<collection-run>/summary.json` and `report.md` |

The report retains every scheduled attempt, identifies unmatched arms and keeps
uncertain/ungraded outcomes distinct from definitive failures. Comparison and
aggregation require fresh launcher provenance. Use `--allow-nonfresh` only for
an explicit comparison of raw/reused sessions; the report records the override
without changing their provenance. Report all-attempt
and successful-pair costs together. Input/output token-per-turn metrics have
separate known-call denominators; unknown input/output usage makes exact totals
or means unavailable rather than zero. Cached input and reasoning tokens are
subsets, not extra tokens added to input plus output. Price-derived USD values
are estimates at the recorded price schedule, not provider invoices.

**Gate:** internally consistent identities/controls, complete denominator and
explicit cost/grade/audit coverage. **Model calls: 0.** Preserve the ledger,
recordings, evaluation receipts, frozen rubrics and private preparation receipts
needed to reproduce these counts.

## Batch judging

Set `JUDGE_TRANSPORT=batch` and `NATIVE_JUDGE_PROFILE=primary` before scheduling.
The ledger binds these settings. Native judging uses `gemini-3.5-flash-lite`;
`pro` selects `gemini-3.1-pro-preview` with separate result folders. Actor
requests, their input preflight and rubric generation use normal transport.
Judging can take hours to days across dependent rounds. Exit code 75 means a
batch is pending. Repeating the same command polls existing jobs and never
resubmits an answered or still-submitted item.

Inspect the synthetic batch smoke plan offline:

```sh
.venv/bin/python -m w8bench.verifier.batch smoke \
  --output-dir .runtime/judge_batch_smoke
```

**Gate:** explicit approval to submit the smoke batches. **Model calls: 0 for
preflight; after approval, five tiny generation requests: three Google, two
OpenAI.** These cover Flash-Lite and Pro OpenAI-compatible native requests,
Google GenerateContent inventory, OpenAI Responses completion and Chat
adjudication, including images, JSON output and the actual reasoning settings.
After approval, submit and repeat later to poll:

```sh
.venv/bin/python -m w8bench.verifier.batch smoke \
  --output-dir .runtime/judge_batch_smoke --execute || [ "$?" -eq 75 ]
```

Inspect `.runtime/judge_batch_smoke/smoke.json`, provider job IDs, returned model
IDs and usage before approving pilot judging. Cancellation is explicit:

```sh
.venv/bin/python -m w8bench.verifier.batch smoke \
  --output-dir .runtime/judge_batch_smoke --cancel --execute
```

For full evaluation or resume, select all finalized recordings from the saved
ledger. This performs no actor work. Set `BENCH_EVALUATION_RUN` to the actual
pilot or collection run name:

```sh
: "${BENCH_EVALUATION_RUN:?Set the saved pilot or collection run name}"
.venv/bin/python - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
ledger = Path('recordings') / os.environ['BENCH_EVALUATION_RUN'] / 'ledger.jsonl'
rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
runs = [row['recording'] for row in rows if (Path(row['recording']) / 'final.json').is_file()]
assert runs, 'No finalized recordings available for judging'
command = [sys.executable, '-m', 'w8bench.verifier.run_comparison', '--run', *runs,
    '--rubric', 'data/rubrics', '--judge-model', 'gpt-6.1-sol', '--judge-transport', 'batch', '--execute']
result = subprocess.run(command, check=False)
assert result.returncode in (0, 75), f'Evaluation needs attention: exit {result.returncode}'
PY
```

**Gate:** approved rubrics and recorded pilot/collection. **Model calls:** every
ready request from the existing full pipelines; polling/replay adds no generation
calls. Invalid answers and failed/expired items retain the existing retry budgets.
Repeat until completed, then resume the batch command to reconcile ledger status
and aggregate. Use `--judge-transport normal` only for a separate evaluation with
matching effective settings; it cannot silently resume Batch results.

For the pilot judge comparison, use the same command with `--compare-profiles`:

```sh
.venv/bin/python - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
ledger = Path('recordings') / os.environ['BENCH_PILOT_RUN'] / 'ledger.jsonl'
runs = [row['recording'] for row in map(json.loads, ledger.read_text().splitlines())
        if (Path(row['recording']) / 'final.json').is_file()]
assert runs, 'No finalized pilot recordings'
result = subprocess.run([sys.executable, '-m', 'w8bench.verifier.run_comparison', '--run', *runs,
    '--rubric', 'data/rubrics', '--judge-model', 'gpt-6.1-sol', '--judge-transport', 'batch',
    '--compare-profiles', '--execute'], check=False)
assert result.returncode in (0, 75), f'Judge comparison needs attention: exit {result.returncode}'
PY
```

**Gate:** explicit approval for both judge profiles. **Model calls:** the primary
full evaluation plus the Pro native pipelines and their own inventory/adjudication
for every selected recording. Common completion is shared; no actor or rubric is
rerun. The printed `profile_comparison.json` path contains per-arm/per-format
criterion agreement, disagreements, agreement on each audit's screenshot-only
subset and their union/intersection, each arm's two directional losses and coverage,
and profile-specific usage/cost streams. Quality counts include ungraded native
results, observed repair events, explicit refusals, audits blocked by an unavailable
native verifier and runs without loss values.
Primary and Pro outputs are never mixed in the primary aggregate.

To cancel outstanding judging, use the selected recording paths and rubric with
`--cancel --execute`. The controller records cancellation before requesting it
from each provider and refuses late results. If submission acknowledgement was
lost, do not recreate the job: reconcile its actual provider job ID in the saved
`submission_uncertain` receipt first. Never delete that receipt to force a retry.
