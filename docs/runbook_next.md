# Collection and evaluation runbook

Run commands from the repository root using `.venv`. The catalog contains 25
public, read-only tasks. Each task has independent DOM and screenshot actors;
choose any positive trial count per arm. Actor requests use `gemini-3.1-pro-preview`, a
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
import json, os
from pathlib import Path
from w8bench.task_recorder.runner import load_env, MAX_TASK_MEMORY_CHARS
from w8bench.task_recorder.task_cli import parse_args, parse_task_catalog
from w8bench.verifier.common import validate_endpoint_configs
from w8bench.verifier.audit_requests import resolve_audit_config
from w8bench.verifier.package_manifests import require_local_packages
load_env(Path('.env'))
assert all(os.environ.get(k, '').strip() for k in ('OPENAI_API_KEY', 'GEMINI_API_KEY')), 'Missing credential'
assert os.environ.get('ACTOR_MODEL') == 'gemini-3.1-pro-preview', 'Unexpected actor model'
audit = resolve_audit_config()
assert audit['inventory'] == {'model': 'gemini-3.1-pro-preview', 'provider': 'google'}
assert audit['adjudication'] == {'model': 'gpt-6.1-sol', 'provider': 'openai'}
settings = parse_args(['--output-dir', 'recordings'])
assert settings.max_output_tokens == 10000 and settings.max_steps == 200
assert MAX_TASK_MEMORY_CHARS == 8000
catalog = Path('data/tasks.jsonl')
rows = parse_task_catalog(catalog.read_text(), source=str(catalog))
assert len(rows) == 25 and {r['task_id'] for r in rows} == {f'task_{n:02d}' for n in range(1, 26)}
assert Path('internal/task_validity.json').is_file(), 'Missing task-validity metadata'
validate_endpoint_configs('config')
require_local_packages()
print(json.dumps({'status': 'offline_preflight_passed', 'tasks': len(rows),
    'actor': os.environ['ACTOR_MODEL'], 'completion': 'gpt-6.1-sol',
    'rubric_model': 'gpt-5.2', 'verifier_models': ['gemini-3.1-pro-preview', 'gemini-3.8-flash'], 'audit': audit,
    'max_output_tokens': settings.max_output_tokens, 'max_turns': settings.max_steps,
    'memory_characters': MAX_TASK_MEMORY_CHARS}, indent=2))
PY
```

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
`recordings/collection/schedule_preview.jsonl`. Inspect all `50 × k` task/arm/trial
rows, alternating arm order, intended output paths and controls. It is not the
executable attempt ledger. Rubric-free planning cannot start an actor or judge.
Execution requires approved frozen rubrics and creates `ledger.jsonl` separately.
When all frozen rubrics exist, `--dry-run` creates or validates the ordinary
`ledger.jsonl`, and removing `--dry-run` resumes that same schedule.

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
but is not normally called by these two preparation stages. The native JSON output contract is `native-rubric-output-contract/v2`; output
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

**Gate:** all 25 valid drafts and a human review of every criterion. Generation
normally needs **50 logical calls**: two per task, before existing retries or
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

**Gate:** 25 frozen task rubrics, matching task definitions and approved review
hash. **Model calls: 0.**

## 4. Small model compatibility gate

This **paid** command dispatches eight nominal logical requests: two actor
requests, three native/rubric model transport probes, one completion request and
one request through each actual inventory/adjudication transport. It uses
`gpt-5.2`, `gemini-3.1-pro-preview`, `gemini-3.8-flash` and `gpt-6.1-sol`, with a
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
assert os.environ.get('ACTOR_MODEL') == 'gemini-3.1-pro-preview'
root = Path('internal/compatibility')
assert not root.exists(), 'Keep the prior receipt; choose a distinct check directory for a repeat'
root.mkdir(parents=True)
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
    'gemini-3.1-pro-preview': [f'{mode}.{stage}' for mode in ('dom_model', 'screenshot_verifier')
        for stage in ('relevance', 'evidence_analysis', 'condition_disambiguation',
                      'reality_check', 'whole_rubric_rescore', 'per_criterion_rescore',
                      'side_effects', 'outcome', 'failure_analysis')],
    'gemini-3.8-flash': [f'{mode}.{stage}' for mode in ('dom_model', 'screenshot_verifier')
        for stage in ('action_only_scoring', 'task_validity', 'trajectory_validity')],
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
                observation_mode=arm, viewport=(1365,768), model_turn=1, max_turns=200)
            assert decision['action']=='wait' and decision['seconds']==0
            assert 'COMPATIBILITY_OK' in decision['thought']
            record_matches(receipt, client.model, [response.get('model')], [f'actor.{arm}'])
            receipt['status'] = 'passed'
        finally:
            receipt.update(response=client.last_response, input_report=client.last_input_report)
    for model in ('gpt-5.2', 'gemini-3.1-pro-preview', 'gemini-3.8-flash'):
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
    write_json(root/'result.json', {'status':status,'nominal_logical_calls':8,'receipts':receipts})
    for client in clients:
        loop.run_until_complete(client.close())
    loop.close()
print('Compatibility gate:', status)
PY
```

**Gate:** all eight checks pass with permitted returned IDs, complete
responses, valid schema/JSON and readable image markers. Inspect
`internal/compatibility/result.json` and the actor requests/responses. Normally
**8 logical calls**; existing SDK/client retry policies can increase HTTP attempts.
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

## 5. Three-task pilot with full evaluation

The pilot uses `task_08`, `task_12`, `task_23`, both arms, one trial each. It is
separate from the full collection.

```sh
./scripts/run-task task_08 task_12 task_23 --trials 1 \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name pilot --dry-run

./scripts/run-task task_08 task_12 task_23 --trials 1 \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name pilot

./scripts/run-comparison --ledger recordings/pilot/ledger.jsonl \
  --output reports/pilot
```

Each actor attempt receives a fresh browser profile. Both arms finish before
their full evaluation starts: paired completion, screenshot verifier, DOM verifier
and a within-run audit with inventory/adjudication. These compare saved formats
from the same actor run; they do not pair the DOM actor's evidence with the
screenshot actor's evidence. Passive capture failure is recorded separately.

**Gate:** six scheduled attempts have recorded technical/evaluation outcomes;
inspect request isolation, capture hashes/timings, actor returned IDs, grading
coverage, frozen rubric identity, judge receipts and the report. Genuine task
failure is a result, not permission to rewrite a task. Resolve generic setup
faults before authorizing the full collection. The pilot permits at most
**1,200 actor calls** (six × 200). Judge calls depend on states, criteria,
selected evidence and existing retries; do not budget them as one per task.
Aggregation itself uses **0 model calls**.

## 6. Full collection, resume and evaluation

Supply any positive `BENCH_TRIALS`; omit positional selectors to use all 25 tasks:

```sh
: "${BENCH_TRIALS:?Set a positive integer trial count per arm}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name collection --dry-run

./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name collection
```

The executable ledger has `50 × k` attempts, retaining startup failures and
missing recordings. Task/arm/trial order alternates which arm runs first.
Repeat the exact execution command to resume; completed actor attempts are not
replaced, including failures. The command rejects changed catalog, rubric,
effective settings, browser source provenance or task/trial identities. Do not change the trial count
under an existing run name. Use a separate collection name for a different plan.

Both actors for a task/trial run before their judges. Existing error/retry
behavior is retained. API/recorder errors, turn limits, technical outcomes and
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

**Gate:** all `50 × k` ledger attempts are accounted for and evaluation coverage is
reported. The actor maximum is **10,000 × k calls** (25 tasks × two arms × k ×
200), often fewer. Full evaluation adds one primary completion request per
recorded attempt, variable original-verifier calls, and variable inventory/
adjudication requests; existing retries can add transport attempts. Rubrics stay
fixed and are not regenerated during evaluation. Exact totals come from receipts,
not from multiplying task counts by an assumed fixed judge-call count.

## 7. Aggregate and inspect the metrics

Use a new report directory; aggregation is local and makes no model calls:

```sh
./scripts/run-comparison --ledger recordings/collection/ledger.jsonl \
  --output reports/collection
```

By default the report calculates supported pass@k values from the actual trial
count. `--pass-k` can restrict the requested positive k values to those supported
for every retained task. All-trial success reliability is reported separately.

| Measurement or receipt | Location |
| --- | --- |
| Full denominator, ordering, technical/grade/evaluation outcomes, logs and recording paths | `recordings/collection/ledger.jsonl` |
| Actor model turns, rejections, termination calls, input/output usage, cached/reasoning subsets and output-limit flags | Recording `decisions.jsonl`, `turns/turn_*/request.json`, `response.json`, `result.json` |
| Current paired artifacts, capture ordering/timing, navigation flags, hashes and passive failures | Recording `manifest.json`, `steps/step_*/capture.json` and state files |
| Frozen task settings, actor returned model IDs, action counts and final technical status | Recording `task.json`, `manifest.json`, `final.json` |
| Independent paired completion and its judge usage | Recording `completion.json` and evaluation `paired_completion.json` |
| Screenshot/DOM auxiliary scores, model-call/usage receipts, logs and validity diagnostics | The `evaluation.json` path in the ledger and its stage subdirectories |
| Two within-run loss directions per actor run, four loss values across arms per task/trial, recovery and coverage | Evaluation `evidence_audit.json`, linked from `evaluation.json` |
| Rubric-generation costs including prior attempts | `internal/rubrics/drafts/task_XX.metrics.json`; workflow `generation.json` |
| Approval binding and immutable shared rubrics | `internal/rubrics/review.json`, `freeze.json`, `data/rubrics/task_XX.json` |
| Cross-arm task/trial pairs and per-task criteria/pass@k | `reports/collection/pairs.json`, `per_task.json` |
| Aggregate turns/tokens, token-per-turn distributions, completion, pass@k, auxiliary scores, audit directions, cost streams and coverage by arm/difficulty | `reports/collection/summary.json` and `report.md` |

The report retains every scheduled attempt, identifies unmatched arms and keeps
uncertain/ungraded outcomes distinct from definitive failures. Report all-attempt
and successful-pair costs together. Input/output token-per-turn metrics have
separate known-call denominators; unknown input/output usage makes exact totals
or means unavailable rather than zero. Cached input and reasoning tokens are
subsets, not extra tokens added to input plus output. Price-derived USD values
are estimates at the recorded price schedule, not provider invoices.

**Gate:** internally consistent identities/controls, complete denominator and
explicit cost/grade/audit coverage. **Model calls: 0.** Preserve the ledger,
recordings, evaluation receipts, frozen rubrics and private preparation receipts
needed to reproduce these counts.
