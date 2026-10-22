"""Statistical and saved-artifact checks for the missed-evidence report."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'generate_missed_evidence_report.py'
SPEC = importlib.util.spec_from_file_location('generate_missed_evidence_report', SCRIPT)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def saved_run(root, task='task_01', timestamp='20261022T090000Z', *, patterns=None, audited=True):
    """Each pattern is (screenshot miss, DOM miss, screenshot loss, DOM loss)."""
    if patterns is None:
        patterns = [(True, False, True, False), (False, True, False, True),
                    (True, True, True, True), (False, False, False, False)]
    run = root / task / timestamp
    items = [{'criterion': f'Criterion {i}'} for i in range(len(patterns))]
    rubric = {'items': items}
    digest = hashlib.sha256(json.dumps(rubric, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    write_json(run / 'frozen_rubric.json', {'precomputed_rubric': rubric})
    write_json(run / 'run_manifest.json', {'status': 'complete', 'commands': {
        'screenshot_verifier': ['python', '--judge-model', 'screenshot-judge-v2', '--o4mini-model', 'action-judge-v2'],
        'dom_model': ['python', '--judge-model', 'dom-judge-v3', '--o4mini-model', 'action-judge-v2'],
    }})
    if not audited:
        return run
    write_json(run / 'rubric_generation_metrics.json', {
        'frozen_rubric_sha256': digest,
        'rubric_generation_calls': 2,
        'call_metrics': {'rubric-generator-v4': {'logical_calls': 2},
                         'configured-only-model': {'logical_calls': 0}},
    })
    criteria = []
    summaries = {'dom_model': [], 'screenshot': []}
    for i, (sm, dm, sl, dl) in enumerate(patterns):
        criterion = {
            'criterion_index': i, 'criterion': items[i]['criterion'], 'classification': 'SAVED_LABEL',
            'explanation': 'Saved adjudication.', 'screenshot_evidence_loss': sl, 'dom_model_evidence_loss': dl,
            'adjudication': {key: {'confirmed': flag, 'citations': []} for key, flag in [
                ('screenshot_verifier_miss', sm), ('dom_model_verifier_miss', dm),
                ('screenshot_evidence_loss', sl), ('dom_model_evidence_loss', dl),
            ]},
        }
        for mode, missed in [('dom_model', dm), ('screenshot', sm)]:
            suffix = 'dom' if mode == 'dom_model' else 'image'
            criterion[mode] = {'verifier_caught': not missed, 'verifier_output': {
                'evidence_analysis': [], 'action_only_points': 0, 'final_points': 1,
                'final_justification': 'Saved justification.', 'applicable_evidence': [],
            }}
            summaries[mode].append({
                'criterion': items[i]['criterion'], 'earned_points': 0, f'post_{suffix}_earned_points': 1,
                f'post_{suffix}_justification': 'Saved justification.', 'applicable_evidence': [],
            })
        criteria.append(criterion)
    write_json(run / 'evidence_audit.json', {
        'schema_version': 'automated-evidence-audit/v3', 'audit_method': 'automated_llm',
        'audit_model': 'audit-model-v5', 'frozen_rubric_sha256': digest, 'task_alias': task,
        'criteria': criteria,
    })
    write_json(run / 'comparison.json', {'criteria': items})
    for mode, folder in [('dom_model', 'dom_model'), ('screenshot', 'screenshot_verifier')]:
        write_json(run / folder / 'result.json', {
            'rubric_sha256': digest, 'intermediate_mm_rubric_steps': {
                'step4_evidence_by_criterion': {}, 'step6_rescoring_summary': summaries[mode],
            },
        })
        write_json(run / folder / 'run_metrics.json', {
            'frozen_rubric_sha256': digest,
            'judge_models': {'judge': 'normalized-judge', 'action_and_validity_judge': 'normalized-action'},
        })
    return run


def test_wilson_interval_including_boundary_counts():
    assert report.wilson_interval(5, 100) == pytest.approx((0.021543679154367966, 0.11175046923191914))
    assert report.wilson_interval(0, 10) == pytest.approx((0, 0.2775327998628892))
    assert report.wilson_interval(10, 10) == pytest.approx((0.7224672001371107, 1))


@pytest.mark.parametrize('count,total', [(0, 0), (-1, 10), (11, 10)])
def test_wilson_rejects_invalid_denominators_and_counts(count, total):
    with pytest.raises(ValueError):
        report.wilson_interval(count, total)


@pytest.mark.parametrize('screen,dom,expected', [(0, 0, 1), (3, 3, 1), (3, 1, 0.625), (10, 0, 0.001953125)])
def test_exact_paired_test(screen, dom, expected):
    assert report.exact_mcnemar(screen, dom) == pytest.approx(expected)
    assert report.exact_mcnemar(dom, screen) == pytest.approx(expected)


def test_paired_statistics_preserve_overlap_and_zero_baseline():
    stat = report.paired_statistics(3, 2, 1, 10)
    assert (stat['screenshot_only'], stat['dom_only'], stat['common'], stat['neither']) == (2, 1, 1, 6)
    assert stat['mcnemar_exact_p'] == 1
    assert report.paired_statistics(0, 2, 0, 10)['dom_relative_reduction'] is None
    with pytest.raises(ValueError):
        report.paired_statistics(2, 2, 3, 10)
    with pytest.raises(ValueError):
        report.paired_statistics(0, 0, 0, 0)


def test_report_uses_all_audited_criteria_and_only_latest_runs(tmp_path):
    saved_run(tmp_path)
    saved_run(tmp_path, timestamp='20261021T090000Z', patterns=[(True, True, True, True)])
    saved_run(tmp_path, task='task_02', audited=False)
    output = tmp_path / 'report.md'
    result = report.generate_report(tmp_path, output)
    text = output.read_text()
    assert result['counts']['audited_criteria'] == 4
    assert result['counts']['all_criteria'] == 8
    assert result['counts']['selected'] == 3
    assert result['counts']['both_evidence_loss'] == 1
    assert result['excluded_tasks'] == ['task_02']
    assert result['statistics']['verifier_miss']['common'] == 1
    assert '**2/4 (50.00%)**; 95% CI 15.00–85.00%' in text
    assert '1/4 (25.00%)' in text
    assert text.index('Absolute rates') < text.index('Paired comparison') < text.index('Relative comparison')
    assert text.index('AI models used') < text.index('Files needed from this directory')
    assert 'configured-only-model' not in text
    assert 'screenshot-judge-v2' in text and 'dom-judge-v3' in text
    assert 'rubric-generator-v4' in text and 'audit-model-v5' in text
    assert 'correlation among criteria within a task' in text
    assert 'Planned ablation study' in text
    assert 'older runs' in text


def test_no_findings_still_report_intervals_and_undefined_relative_rate(tmp_path):
    saved_run(tmp_path, patterns=[(False, False, False, False)])
    result = report.generate_report(tmp_path, tmp_path / 'report.md')
    text = (tmp_path / 'report.md').read_text()
    assert '**0/1 (0.00%)**; 95% CI 0.00–79.35%' in text
    assert 'relative reduction is undefined' in text
    assert result['statistics']['verifier_miss']['mcnemar_exact_p'] == 1


def test_report_lists_each_recorded_model_configuration(tmp_path):
    saved_run(tmp_path)
    other = saved_run(tmp_path, task='task_02')
    manifest_file = other / 'run_manifest.json'
    manifest = json.loads(manifest_file.read_text())
    manifest['commands']['dom_model'][2] = 'another-dom-judge'
    write_json(manifest_file, manifest)
    result = report.generate_report(tmp_path, tmp_path / 'report.md')
    assert result['models']['DOM verification: evidence/rubric judge'] == {
        'dom-judge-v3': 1, 'another-dom-judge': 1,
    }
    assert result['models']['Rubric generation (Phase A)'] == {'rubric-generator-v4': 2}
    assert 'pooled counts do not constitute a controlled ablation' in (tmp_path / 'report.md').read_text()


def test_metadata_fallback_missing_provenance_and_zero_generation_calls(tmp_path):
    run = saved_run(tmp_path)
    manifest = run / 'run_manifest.json'
    manifest.unlink()
    digest = json.loads((run / 'evidence_audit.json').read_text())['frozen_rubric_sha256']
    models = report.recorded_models(run, digest)
    assert models['DOM verification: evidence/rubric judge'] == 'normalized-judge'
    (run / 'dom_model/run_metrics.json').unlink()
    models = report.recorded_models(run, digest)
    assert models['DOM verification: evidence/rubric judge'] == 'not recorded'
    write_json(run / 'rubric_generation_metrics.json', {
        'frozen_rubric_sha256': digest, 'rubric_generation_calls': 0, 'call_metrics': {},
    })
    assert report.recorded_models(run, digest)['Rubric generation (Phase A)'] == 'no generation calls recorded'
    (run / 'rubric_generation_metrics.json').unlink()
    assert report.recorded_models(run, digest)['Rubric generation (Phase A)'] == 'not recorded'


def test_metadata_rejects_metrics_for_another_rubric(tmp_path):
    run = saved_run(tmp_path)
    with pytest.raises(AssertionError):
        report.recorded_models(run, 'wrong-rubric-hash')
