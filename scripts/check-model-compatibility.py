"""Check the configured model transports with seven paid logical requests."""

import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--execute", action="store_true", help="authorize paid diagnostic requests")
args = parser.parse_args()
if not args.execute:
    parser.error("paid checks require explicit approval and --execute")

# Diagnostic
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
    'gemini-3.5-flash-lite': [f'{mode}.{stage}' for mode in ('dom_model', 'screenshot_verifier')
        for stage in ('relevance', 'evidence_analysis', 'condition_disambiguation',
                      'reality_check', 'whole_rubric_rescore', 'per_criterion_rescore',
                      'side_effects', 'outcome', 'failure_analysis',
                      'action_only_scoring', 'task_validity', 'trajectory_validity')],
    'gemini-3.1-pro-preview': ['rubric_preparation.generation', 'rubric_preparation.dependency', 'native_pro.transport'],
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
    for model in ('gemini-3.5-flash-lite', 'gemini-3.1-pro-preview'):
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
    client = ModelClient(os.environ['GEMINI_API_KEY'], 'gemini-3.6-flash',
        os.environ.get('GEMINI_BASE_URL','https://generativelanguage.googleapis.com/v1beta'))
    receipt={'stage':'completion','configured_model':'gemini-3.6-flash'}
    receipts.append(receipt)
    response = None
    try:
        response=client._post({'model':'gemini-3.6-flash',
            'systemInstruction':{'parts':[{'text':'Return the supplied compatibility criterion as success, reason marker visible, states [1].'}]},
            'contents':[{'role':'user','parts':[{'text':'Criterion id: compatibility. State 1 contains COMPATIBILITY_OK.'},
                {'inlineData':{'mimeType':'image/png','data':url.split(',',1)[1]}}]}],
            'generationConfig':{'maxOutputTokens':10000,'thinkingConfig':{'thinkingLevel':'MEDIUM'},
                'mediaResolution':'MEDIA_RESOLUTION_HIGH','responseMimeType':'application/json','responseJsonSchema':GRADE_SCHEMA}})
        acceptance=response_acceptance('gemini-3.6-flash', response.get('model'), response, output_cap=10000)
        receipt['acceptance']=acceptance
        record_matches(receipt, 'gemini-3.6-flash', [response.get('model')], ['completion'])
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
        ('adjudication', 'gemini-4-argon', 'google', ADJUDICATION_SYSTEM_PROMPT),
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
