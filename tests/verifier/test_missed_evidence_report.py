"""Statistical and saved-artifact checks for the missed-evidence report."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

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
            'explanation': 'Both verifiers missed the shared relationship.',
            'screenshot_evidence_loss': sl, 'dom_model_evidence_loss': dl,
            'adjudication': {key: {'confirmed': flag, 'citations': []} for key, flag in [
                ('screenshot_verifier_miss', sm), ('dom_model_verifier_miss', dm),
                ('screenshot_evidence_loss', sl), ('dom_model_evidence_loss', dl),
            ]},
        }
        for key, decisive in [('screenshot_evidence_loss', 'Screenshots omit a URL retained by DOM.'),
                               ('dom_model_evidence_loss', 'DOM omits a control state visible in screenshots.')]:
            criterion['adjudication'][key]['decisive_evidence'] = decisive if criterion[key] else ''
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


def category_annotations(root):
    """Explicit annotations for synthetic findings, including different paired types."""
    findings = {}
    for task in root.glob('task_*'):
        audit_file = sorted(task.iterdir())[-1] / 'evidence_audit.json'
        if not audit_file.exists():
            continue
        for criterion in json.loads(audit_file.read_text())['criteria']:
            for flag, category in [('screenshot_evidence_loss', 'URLs'),
                                    ('dom_model_evidence_loss', 'Control states')]:
                if criterion['adjudication'][flag]['confirmed']:
                    key = f'{task.name}/C{criterion["criterion_index"]}/{flag}'
                    findings[key] = {'category': category,
                                     'finding_sha256': report.finding_digest(criterion, flag)}
    path = root / 'categories.json'
    write_json(path, {'categories': list(report.CATEGORIES), 'findings': findings})
    return path


def generate_report(root, output):
    return report.generate_report(root, output, category_annotations(root))


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
    result = generate_report(tmp_path, output)
    text = output.read_text()
    assert result['counts']['audited_criteria'] == 4
    assert result['counts']['all_criteria'] == 8
    assert result['counts']['selected'] == 3
    assert result['counts']['both_evidence_loss'] == 1
    assert result['excluded_tasks'] == ['task_02']
    assert result['statistics']['evidence_loss']['common'] == 1
    assert '**2/4**; 95% CI **15.00–85.00%** (rate 50.00%)' in text
    assert '1/4 (25.00%)' in text
    assert text.index('Absolute rates') < text.index('Paired comparison') < text.index('Relative comparison')
    assert text.index('AI models used') < text.index('Files needed from the evaluation directory')
    assert 'configured-only-model' not in text
    assert 'screenshot-judge-v2' in text and 'dom-judge-v3' in text
    assert 'rubric-generator-v4' in text and 'audit-model-v5' in text
    assert 'correlation among criteria within a task' in text
    assert 'Planned ablation study' in text
    assert 'older runs' in text


def test_no_findings_still_report_intervals_and_undefined_relative_rate(tmp_path):
    saved_run(tmp_path, patterns=[(False, False, False, False)])
    result = generate_report(tmp_path, tmp_path / 'report.md')
    text = (tmp_path / 'report.md').read_text()
    assert '**0/1**; 95% CI **0.00–79.35%** (rate 0.00%)' in text
    assert 'relative reduction is undefined' in text
    assert result['statistics']['evidence_loss']['mcnemar_exact_p'] == 1


def test_report_lists_each_recorded_model_configuration(tmp_path):
    saved_run(tmp_path)
    other = saved_run(tmp_path, task='task_02')
    manifest_file = other / 'run_manifest.json'
    manifest = json.loads(manifest_file.read_text())
    manifest['commands']['dom_model'][2] = 'another-dom-judge'
    write_json(manifest_file, manifest)
    result = generate_report(tmp_path, tmp_path / 'report.md')
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


def test_categories_count_each_representation_and_exclude_rows_without_source_loss(tmp_path):
    saved_run(tmp_path, patterns=[(True, False, True, True), (True, True, False, False)])
    result = generate_report(tmp_path, tmp_path / 'docs' / 'report.md')
    text = (tmp_path / 'docs/report.md').read_text()
    assert result['category_counts']['URLs'] == {'screenshot': 1, 'dom': 0}
    assert result['category_counts']['Control states'] == {'screenshot': 0, 'dom': 1}
    assert list(result['category_counts']) == list(report.CATEGORIES)
    assert '| Category | Labels | Findings |' in text
    assert '| Screenshot: URLs<br>DOM: Control states | `BOTH_EVIDENCE_INCOMPLETE` |' in text
    assert '**C1**' not in text
    assert result['counts']['selected'] == 1
    assert result['counts']['no_source_loss'] == 1
    assert f'({report.DEFAULT_EVALUATION_URL}/task_01/20261022T090000Z/evidence_audit.json#L' in text
    assert '[category annotations](../categories.json)' in text
    assert str(tmp_path) not in text


def test_export_uses_only_source_loss_labels_details_and_statistics(tmp_path):
    run = saved_run(tmp_path, patterns=[(True, True, False, False),
                                       (True, False, True, False),
                                       (False, False, False, False)])
    audit_path = run / 'evidence_audit.json'
    audit = json.loads(audit_path.read_text())
    audit['criteria'][1]['classification'] = 'BOTH_MISSED'
    audit['criteria'][1]['adjudication']['screenshot_verifier_miss']['citations'] = [
        {'source': 'excluded-verifier-citation.png', 'location': 'unrelated location'}]
    write_json(audit_path, audit)
    result = generate_report(tmp_path, tmp_path / 'report.md')
    text = (tmp_path / 'report.md').read_text()
    assert result['counts']['audited_criteria'] == 3
    assert result['counts']['selected'] == 1
    assert result['counts']['no_source_loss'] == 2
    assert result['statistics'].keys() == {'evidence_loss'}
    assert result['statistics']['evidence_loss']['denominator'] == 3
    assert result['labels'] == {'SCREENSHOT_EVIDENCE_MISSING': 1}
    assert '**C1**' in text
    assert '**C0**' not in text and '**C2**' not in text
    assert 'Screenshots omit a URL retained by DOM.' in text
    for excluded in ('verifier miss', 'BOTH_MISSED', 'Both verifiers missed',
                     'excluded-verifier-citation.png', 'SAVED_LABEL', 'Screenshot output'):
        assert excluded not in text
    assert not any('miss' in key for key in result['counts'])


def test_source_loss_export_requires_decisive_evidence(tmp_path):
    run = saved_run(tmp_path, patterns=[(False, False, True, False)])
    path = run / 'evidence_audit.json'
    audit = json.loads(path.read_text())
    audit['criteria'][0]['adjudication']['screenshot_evidence_loss']['decisive_evidence'] = ''
    write_json(path, audit)
    with pytest.raises(ValueError, match='Missing decisive source evidence'):
        generate_report(tmp_path, tmp_path / 'report.md')


@pytest.mark.parametrize('change,error', [('missing', 'Missing evidence category'),
                                        ('stale', 'Stale evidence category'),
                                        ('unknown', 'Unknown evidence category')])
def test_report_rejects_missing_stale_or_unknown_category(tmp_path, change, error):
    saved_run(tmp_path)
    categories = category_annotations(tmp_path)
    annotations = json.loads(categories.read_text())
    key = next(iter(annotations['findings']))
    if change == 'missing':
        del annotations['findings'][key]
    elif change == 'stale':
        annotations['findings'][key]['finding_sha256'] = 'outdated'
    else:
        annotations['findings'][key]['category'] = 'Screenshot evidence loss'
    write_json(categories, annotations)
    with pytest.raises(ValueError, match=error):
        report.generate_report(tmp_path, tmp_path / 'report.md', categories)


def test_cli_defaults_to_docs_even_with_custom_evaluation_dir(tmp_path, monkeypatch):
    evaluation = tmp_path / 'saved-runs'
    saved_run(evaluation)
    monkeypatch.setattr(report, 'REPOSITORY', tmp_path)
    monkeypatch.setattr(report, 'DEFAULT_CATEGORIES', category_annotations(evaluation))
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--evaluation-dir', str(evaluation)])
    report.main()
    output = tmp_path / 'docs/missed_evidence_table.md'
    assert output.is_file()
    assert not (evaluation / 'missed_evidence_table.md').exists()
    summary = json.loads((tmp_path / 'docs/benchmark_statistics.json').read_text())
    assert summary['output'] == 'missed_evidence_table.md'
    assert summary['category_provenance'] == '../saved-runs/categories.json'
    assert f'({report.DEFAULT_EVALUATION_URL}/task_01/' in output.read_text()


def test_dataset_links_allow_revision_override_and_preserve_line_anchors(tmp_path, monkeypatch):
    evaluation = tmp_path / 'evaluation'
    saved_run(evaluation)
    categories = category_annotations(evaluation)
    output = tmp_path / 'docs/report.md'
    statistics = tmp_path / 'docs/statistics.json'
    base = 'https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/audit-revision/evaluation'
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--evaluation-dir', str(evaluation),
                                    '--categories', str(categories), '--output', str(output),
                                    '--summary-output', str(statistics), '--evaluation-url', base])
    report.main()
    text = output.read_text()
    assert f'({base}/task_01/20261022T090000Z/evidence_audit.json#L' in text
    assert f'({base}/task_01/20261022T090000Z/run_manifest.json)' in text
    assert '[category annotations](../evaluation/categories.json)' in text
    assert '../evaluation/task_01/' not in text
    assert report.DEFAULT_EVALUATION_URL not in text
    assert json.loads(statistics.read_text())['evaluation_url'] == base
