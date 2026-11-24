"""Check local configuration and catalog controls without provider calls."""

import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.parse_args()

# Diagnostic
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
