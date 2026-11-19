"""Actor transport retry and response accounting."""
import json
import urllib.error
from io import BytesIO

import pytest

from tests.conftest import actor_preflight_response
from w8bench.task_recorder import runner
from w8bench.task_recorder.recorder_support import RunnerError, write_json, append_json_line, write_json_lines


@pytest.mark.parametrize('code', [429, 500, 502, 503, 504])
def test_actor_retries_transient_http_only(monkeypatch, tmp_path, code):
    client = runner.ModelClient('credential-for-redaction', 'gemini-3.8-flash', 'https://offline.test')
    client.last_input_report = {'api_call_started': True}
    client.turn_dir = tmp_path
    calls = []
    sleeps = []
    monkeypatch.setattr(runner.time, 'sleep', sleeps.append)
    def request(*args, **kwargs):
        preflight = actor_preflight_response(args[0])
        if preflight is not None: return preflight
        calls.append(kwargs['timeout'])
        if len(calls) < 3:
            raise urllib.error.HTTPError('https://offline.test', code, 'temporary', {}, BytesIO(b'{"error":{"message":"temporary rate limit"}}'))
        return BytesIO(b'{"modelVersion":"gemini-3.8-flash","candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"{}"}]}}]}')
    monkeypatch.setattr(runner.urllib.request, 'urlopen', request)
    assert client._post({'contents': []})['model'] == 'gemini-3.8-flash'
    assert calls == [180, 180, 180]
    rows = [json.loads(x) for x in (tmp_path / 'transport_attempts.jsonl').read_text().splitlines()]
    assert len(rows) == 3 and rows[0]['usage'] is None
    assert rows[0]['status_code'] == code and rows[-1]['status'] == 'response_received'
    assert len(sleeps) == 2 and 2 <= sleeps[0] <= 2.5 and 8 <= sleeps[1] <= 8.5


@pytest.mark.parametrize('code,body', [(401,'auth'), (403,'forbidden'), (400,'bad request'), (429,'insufficient_quota'), (429,'credit_balance_exhausted'), (503,'billing disabled')])
def test_actor_does_not_retry_permanent_provider_errors(monkeypatch, tmp_path, code, body):
    client = runner.ModelClient('credential-for-redaction', 'gemini-3.8-flash', 'https://offline.test')
    client.last_input_report = {'api_call_started': True}
    client.turn_dir = tmp_path
    calls = []
    def request(*args, **kwargs):
        preflight = actor_preflight_response(args[0])
        if preflight is not None: return preflight
        calls.append(1)
        raise urllib.error.HTTPError('https://offline.test',code,'failed',{},BytesIO(json.dumps({'error':{'message':body+' credential-for-redaction'}}).encode()))
    monkeypatch.setattr(runner.urllib.request, 'urlopen', request)
    with pytest.raises(RunnerError):client._post({'contents': []})
    assert len(calls) == 1
    assert 'credential-for-redaction' not in (tmp_path / 'transport_attempts.jsonl').read_text()


def test_actor_exhausted_transport_has_unknown_usage(monkeypatch, tmp_path):
    client = runner.ModelClient('offline', 'gemini-3.8-flash', 'https://offline.test')
    client.last_input_report = {'api_call_started': True}
    client.turn_dir = tmp_path
    monkeypatch.setattr(runner.time,'sleep',lambda _:None)
    def request(*args, **kwargs):
        preflight = actor_preflight_response(args[0])
        if preflight is not None: return preflight
        raise TimeoutError('timed out')
    monkeypatch.setattr(runner.urllib.request,'urlopen',request)
    with pytest.raises(RunnerError) as error:client._post({'contents':[]})
    assert error.value.technical_failure_class == 'actor_transport_exhausted'
    rows=[json.loads(x) for x in (tmp_path/'transport_attempts.jsonl').read_text().splitlines()]
    assert len(rows)==3 and all(x['usage'] is None for x in rows)
    assert not client.last_input_report.get('model_response_received')


@pytest.mark.parametrize('writer', ['json','jsonl','jsonlines'])
def test_unicode_writers_escape_lone_surrogates_and_keep_valid_unicode(tmp_path, writer):
    path=tmp_path/'receipt.json'
    value={'text':'café 😀 '+chr(0xD83D)}
    if writer=='json':write_json(path,value)
    elif writer=='jsonl':append_json_line(path,value)
    else:write_json_lines(path,[value])
    raw=path.read_text()
    assert 'café 😀' in raw and '\\ud83d' in raw
    assert json.loads(raw)==value


def test_failure_health_and_interruption_receipts_are_redacted(monkeypatch, tmp_path):
    from types import SimpleNamespace
    monkeypatch.setenv('OPENAI_API_KEY','secret-health-marker')
    monkeypatch.setattr(runner,'subprocess',SimpleNamespace(run=lambda *a, **k:SimpleNamespace(returncode=0,stdout='secret-health-marker',stderr='')),raising=False)
    monkeypatch.setattr(runner,'generate_trajectory_artifacts',lambda _: {'status':'complete'})
    manifest={'steps':[],'states':[],'model_turns':0,'browser_profile_provenance':{'container_id':'a'*64}}
    runner.finalize_recording_artifacts(tmp_path,manifest,{'status':'failure','run_status':'interrupted'})
    assert 'secret-health-marker' not in (tmp_path/'failure_health.json').read_text()
    assert '[redacted]' in (tmp_path/'failure_health.json').read_text()
    assert json.loads((tmp_path/'interruption.json').read_text())['model_turns']==0


@pytest.mark.asyncio
async def test_no_response_is_not_a_model_turn(actor_request_args, monkeypatch):
    from types import SimpleNamespace
    client=runner.ModelClient('offline','gemini-3.8-flash','https://offline.test')
    monkeypatch.setattr(runner.time,'sleep',lambda _:None)
    def request(*a,**k):
        preflight = actor_preflight_response(a[0])
        if preflight is not None: return preflight
        raise TimeoutError('offline')
    monkeypatch.setattr(runner.urllib.request,'urlopen',request)
    async def inline(function,*args,**kwargs):return function(*args,**kwargs)
    monkeypatch.setattr(runner.asyncio,'to_thread',inline)
    args=SimpleNamespace(max_output_tokens=10000,max_steps=200)
    directory=actor_request_args['turn_dir']; directory.mkdir(parents=True)
    root=directory.parents[1]
    manifest={'model_turns':1,'states':[{}],'returned_actor_models':[]}
    with pytest.raises(RunnerError):
        await runner._model_turn(args,{'instruction':'inspect'},client,actor_request_args['bundle'],runner.ActorState(),manifest,root,directory,1,'dom',(1365,768))
    assert manifest['model_turns']==0 and manifest['actor_transport_attempts']==3
    assert not (root/'decisions.jsonl').exists()


def test_each_modality_schema_is_validated_and_comparable(run_pair):
    from w8bench.task_recorder.prepare_verifier_data import inspect_recording
    from w8bench.verifier.compare_results import compare
    paths,*_=run_pair
    dom,ss=[inspect_recording(paths[mode]) for mode in ['dom','screenshot']]
    assert dom['manifest']['controls']['action_schema_sha256'] != ss['manifest']['controls']['action_schema_sha256']
    assert compare(dom,ss)[0]['both_successful'] is False
    ss['manifest']['controls']['action_schema_sha256']='invalid'
    with pytest.raises(ValueError,match='schema'):compare(dom,ss)


@pytest.mark.asyncio
async def test_uncertain_input_is_not_replayed_and_keeps_both_coordinates(actor_observation, tmp_path):
    from types import SimpleNamespace
    from w8bench.task_recorder.agent_browser import AgentBrowserClient
    from w8bench.task_recorder.capture import CDPError
    calls=[]
    async def call(method,params):
        calls.append((method,params))
        raise CDPError(method,{'code':-32603,'message':'Internal error'})
    cdp=SimpleNamespace(call=call,observation_mode='screenshot')
    driver=AgentBrowserClient('unused',session='offline',cdp_url='http://offline.test',timeout=90)
    manifest={'states':[{}],'steps':[]}
    with pytest.raises(CDPError):
        await runner._deliver_action({'action':'click','x':1000,'y':1000,'thought':'Click the corner'},actor_observation,
            driver,cdp,(1365,768),manifest,tmp_path,1,'screenshot')
    action=json.loads((actor_observation.directory/'action.json').read_text())
    assert action['model_coordinates']['x']==1000
    assert action['executed_coordinates']=={'x':1364,'y':767,'units':'css_pixels'}
    assert action['action_succeeded'] is False and len(calls)==1


@pytest.mark.parametrize('kind',['common','native_answer'])
def test_verifier_json_writers_preserve_unicode(tmp_path,kind):
    from types import SimpleNamespace
    from w8bench.verifier.common import write_json as common_write
    from w8bench.verifier.trajectory import FinalAnswer
    value={'text':'café 😀 '+chr(0xD83D)}
    path=tmp_path/'answer.json'
    if kind=='common':common_write(path,value)
    else:FinalAnswer.save(SimpleNamespace(to_dict=lambda:value),path)
    assert json.loads(path.read_text())==value and 'café 😀' in path.read_text()


def test_failure_health_is_recorded_before_browser_cleanup(run_pair, tmp_path, monkeypatch):
    from types import SimpleNamespace
    import asyncio
    seen=[]
    output=tmp_path/'timing'
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):seen.append((output/'fixture'/'failure_health.json').exists())
    monkeypatch.setattr(runner,'CDPClient',lambda *a,**k:Client())
    async def failed(*args):raise RunnerError('fixture capture failure')
    monkeypatch.setattr(runner,'_initial_capture',failed)
    args=runner.parse_args(['--observation-mode','screenshot','--capture-only','--task-id','fixture',
        '--output-dir',str(output),'--env-file',str(tmp_path/'missing.env')])
    assert asyncio.run(runner.run(args))==2
    assert seen==[True]


@pytest.mark.asyncio
async def test_cancelled_transport_retains_pending_attempt_without_retry(actor_request_args, monkeypatch):
    client=runner.ModelClient('offline','gemini-3.8-flash','https://offline.test')
    calls=[]
    def request(*a,**k):
        preflight = actor_preflight_response(a[0])
        if preflight is not None: return preflight
        calls.append(1)
        raise runner.asyncio.CancelledError()
    async def inline(function,*a,**k):return function(*a,**k)
    monkeypatch.setattr(runner.urllib.request,'urlopen',request)
    monkeypatch.setattr(runner.asyncio,'to_thread',inline)
    with pytest.raises(runner.asyncio.CancelledError):await client.decide(**actor_request_args)
    pending=json.loads((actor_request_args['turn_dir']/'transport_pending.json').read_text())
    assert pending['attempt']==1 and pending['status']=='started' and pending['usage'] is None
    assert calls==[1] and client.transport_cancelled and client.last_response is None
