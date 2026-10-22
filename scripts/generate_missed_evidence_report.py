#!/usr/bin/env python3
"""Generate the missed-evidence Markdown report from saved v3 audits.

Uses only the Python standard library and local files; makes no model/API calls.
Defaults to <repository>/evaluation when installed in <repository>/scripts.
Selects the latest timestamped run per task, exports confirmed final findings,
and verifies rubric identity, saved model outputs, and evidence-file pointers.
Leads with paired finding rates, 95% intervals, and saved AI-model provenance.
"""

import argparse
from collections import Counter
from pathlib import Path
import hashlib
import html
import json
import math
import re
from statistics import NormalDist


FLAGS = (
    ('dom_model_verifier_miss', 'DOM verifier miss'),
    ('screenshot_verifier_miss', 'Screenshot verifier miss'),
    ('dom_model_evidence_loss', 'DOM evidence loss'),
    ('screenshot_evidence_loss', 'Screenshot evidence loss'),
)


def wilson_interval(count, total):
    """Two-sided 95% Wilson score interval for a binomial proportion."""
    if total <= 0 or not 0 <= count <= total:
        raise ValueError('Expected 0 <= count <= total and total > 0')
    z = NormalDist().inv_cdf(0.975)
    rate = count / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    half_width = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return (0.0 if count == 0 else center - half_width,
            1.0 if count == total else center + half_width)


def exact_mcnemar(screenshot_only, dom_only):
    """Two-sided exact binomial McNemar p-value using discordant pairs."""
    if screenshot_only < 0 or dom_only < 0:
        raise ValueError('Discordant counts must be nonnegative')
    discordant = screenshot_only + dom_only
    tail = sum(math.comb(discordant, k) for k in range(min(screenshot_only, dom_only) + 1))
    return min(1.0, 2 * tail / (1 << discordant))


def paired_statistics(screenshot, dom, common, total):
    """Keep marginal rates, overlap, and the paired comparison on one denominator."""
    if total <= 0:
        raise ValueError('At least one audited criterion is required')
    screenshot_only, dom_only = screenshot - common, dom - common
    neither = total - screenshot - dom + common
    if min(common, screenshot_only, dom_only, neither) < 0:
        raise ValueError('Inconsistent paired counts')
    return {
        'denominator': total,
        'screenshot': {'count': screenshot, 'rate': screenshot / total,
                       'ci95': wilson_interval(screenshot, total)},
        'dom': {'count': dom, 'rate': dom / total, 'ci95': wilson_interval(dom, total)},
        'common': common,
        'screenshot_only': screenshot_only,
        'dom_only': dom_only,
        'neither': neither,
        'mcnemar_exact_p': exact_mcnemar(screenshot_only, dom_only),
        'dom_relative_reduction': (screenshot - dom) / screenshot if screenshot else None,
    }


def recorded_models(run, digest):
    """Read run provenance; count rubric models only when they made calls."""
    manifest_file = run / 'run_manifest.json'
    manifest = json.loads(manifest_file.read_text()) if manifest_file.is_file() else {}
    models = {}
    for folder, label in [('screenshot_verifier', 'Screenshot verification'), ('dom_model', 'DOM verification')]:
        metrics_file = run / folder / 'run_metrics.json'
        metrics = json.loads(metrics_file.read_text()) if metrics_file.is_file() else {}
        if metrics:
            assert metrics['frozen_rubric_sha256'] == digest
        command = manifest.get('commands', {}).get(folder, [])
        for flag, key, role in [('--judge-model', 'judge', 'evidence/rubric judge'),
                                ('--o4mini-model', 'action_and_validity_judge', 'action/validity judge')]:
            model = command[command.index(flag) + 1] if flag in command else (
                metrics.get('judge_models', {}).get(key, 'not recorded'))
            models[f'{label}: {role}'] = model
    generation_file = run / 'rubric_generation_metrics.json'
    generation = json.loads(generation_file.read_text()) if generation_file.is_file() else {}
    if generation:
        assert generation['frozen_rubric_sha256'] == digest
    active_models = sorted(model for model, calls in generation.get('call_metrics', {}).items()
                           if calls.get('logical_calls', 0) > 0)
    models['Rubric generation (Phase A)'] = ', '.join(active_models) or (
        'no generation calls recorded' if generation.get('rubric_generation_calls') == 0 else 'not recorded')
    return models


def rate_cell(stat, total):
    lower, upper = stat['ci95']
    return f'**{stat["count"]}/{total} ({100 * stat["rate"]:.2f}%)**; 95% CI {100 * lower:.2f}–{100 * upper:.2f}%'


def summary_lines(statistics, model_counts, sample_run, audited_tasks):
    lines = [
        '**Absolute rates and common findings**',
        '',
        f'The denominator is all **{statistics["verifier_miss"]["denominator"]} audited criteria across {audited_tasks} tasks**, including criteria with no finding. Only completed audits from each task’s latest selected run contribute; unaudited criteria are excluded. A verifier miss means the model overlooked or misused evidence or the rubric; source-evidence loss means required information was absent from a representation. The two measures are counted separately.',
        '',
        '| Finding | Screenshot: fraction, rate, 95% CI | DOM: fraction, rate, 95% CI | Common to both: fraction and rate |',
        '|---|---|---|---|',
    ]
    for key, label in [('verifier_miss', 'Verifier miss'), ('evidence_loss', 'Source-evidence loss')]:
        stat = statistics[key]
        total = stat['denominator']
        lines.append(f'| {label} | {rate_cell(stat["screenshot"], total)} | {rate_cell(stat["dom"], total)} | '
                     f'{stat["common"]}/{total} ({100 * stat["common"] / total:.2f}%) |')
    lines.extend([
        '',
        'Common findings concern the same task/criterion and are already included in both marginal counts; do not add them again.',
        '',
        '**Paired comparison**',
        '',
        '| Finding | Screenshot only | DOM only | Both | Neither | Exact McNemar p (two-sided) |',
        '|---|---|---|---|---|---|',
    ])
    for key, label in [('verifier_miss', 'Verifier miss'), ('evidence_loss', 'Source-evidence loss')]:
        stat = statistics[key]
        lines.append(f'| {label} | {stat["screenshot_only"]} | {stat["dom_only"]} | {stat["common"]} | '
                     f'{stat["neither"]} | {stat["mcnemar_exact_p"]:.4g} |')
    lines.extend([
        '',
        'Intervals use the [95% Wilson score method](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). '
        'The [two-sided exact McNemar test](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html) '
        'tests equal marginal rates using only discordant criterion pairs: '
        '`p = min(1, 2 × P[Binomial(screenshot_only + dom_only, 0.5) ≤ min(screenshot_only, dom_only)])`. '
        'These criterion-level intervals and tests assume independent criterion pairs; they do not adjust for correlation among criteria within a task, repeated model runs, or automated-audit error. Treat them as exploratory benchmark statistics.',
        '',
        '**Relative comparison (secondary point estimates)**',
        '',
    ])
    for key, label in [('verifier_miss', 'verifier misses'), ('evidence_loss', 'source-evidence losses')]:
        stat = statistics[key]
        relative = stat['dom_relative_reduction']
        if relative is None:
            text = 'relative reduction is undefined because the screenshot baseline is zero'
        else:
            direction = 'fewer' if relative >= 0 else 'more'
            text = f'DOM has {abs(relative) * 100:.1f}% {direction} than screenshots'
        lines.append(f'- {label.capitalize()}: {text} ({stat["screenshot"]["count"]} screenshot, {stat["dom"]["count"]} DOM).')
    lines.extend([
        '',
        'Relative percentages can change sharply when counts are small; read the absolute counts, rate intervals, and paired tests first.',
        '',
        '**AI models used — verification, rubric generation, and audit**',
        '',
        f'Model identities below come from saved provenance for the {audited_tasks} completed audits. Counts in parentheses are selected runs, not model calls.',
        '',
        '| Role | Recorded model(s) and run counts |',
        '|---|---|',
    ])
    for role, models in model_counts.items():
        identities = '; '.join(f'`{cell(model)}` ({count} runs)' for model, count in sorted(models.items()))
        lines.append(f'| {role} | {identities} |')
    lines.extend([
        '',
        'Both verifier results are checked against the same frozen rubric per task. Verification identities use saved command arguments, falling back to normalized run metrics; rubric-generation identities include only models with nonzero recorded generation calls. '
        'Models configured with zero generation calls are excluded from the rubric-generation row. Audit/adjudication judgments are automated.',
        '',
        'Example provenance: ' + link('run manifest', sample_run / 'run_manifest.json') + '. ' + ' '.join(
            link(label, sample_run / path) + '.' for label, path in [
                ('rubric-generation metrics', 'rubric_generation_metrics.json'),
                ('screenshot verification metrics', 'screenshot_verifier/run_metrics.json'),
                ('DOM verification metrics', 'dom_model/run_metrics.json'),
            ] if (sample_run / path).is_file()),
        '',
        '**Planned ablation study:** vary the verification and rubric-generation AI models and the DOM representations/models, keeping the task set, shared trajectories, frozen rubric within each paired comparison, and audit protocol controlled. '
        'This report describes the recorded configurations; cross-model and cross-DOM ablations have not been performed here. If multiple configurations appear above, their pooled counts do not constitute a controlled ablation.',
        '',
    ])
    return lines


def cell(value):
    return html.escape(' '.join(str(value).split()), quote=False).replace('|', '&#124;')


def link(label, path, line=None):
    if not path.is_file():
        raise ValueError(f'Link target does not exist: {path}')
    if line is not None and not 1 <= line <= len(path.read_text(encoding='utf-8').splitlines()):
        raise ValueError(f'Link line does not exist: {path}:{line}')
    target = str(path.resolve()) + (f':{line}' if line is not None else '')
    return f'[{label}]({target})'


def array_entries(text, key, indent):
    match = re.search(r'^' + ' ' * indent + re.escape(json.dumps(key)) + r': \[', text, re.M)
    assert match is not None, (key, indent)
    cursor = match.end()
    decoder = json.JSONDecoder()
    entries = []
    while True:
        while text[cursor].isspace() or text[cursor] == ',':
            cursor += 1
        if text[cursor] == ']':
            return entries
        value, end = decoder.raw_decode(text, cursor)
        entries.append((value, cursor, end, text.count('\n', 0, cursor) + 1))
        cursor = end


def source_locations(criterion, enabled):
    citations = {}
    for key, _ in enabled:
        for citation in criterion['adjudication'][key]['citations']:
            source = citation['source']
            locations = citations.setdefault(source, [])
            if citation['location'] not in locations:
                locations.append(citation['location'])
    return '; '.join(f'`{source}` ({cell("; ".join(locations))})' for source, locations in citations.items())


def generate_report(evaluation_dir: Path, output: Path) -> dict:
    """Validate saved artifacts and write summary statistics and detailed findings."""
    ROOT = evaluation_dir.resolve()
    OUTPUT = output.resolve()
    counts = Counter()
    labels = Counter()
    selected_tasks = set()
    miss_tasks = set()
    loss_only_tasks = set()
    rows = []
    excluded = []
    older_runs = []
    audits = []
    selected_runs = []
    audit_models = set()
    model_counts = {}
    verified_records = 0

    task_dirs = [p for p in ROOT.glob('task_*') if p.is_dir() and re.fullmatch(r'task_\d+', p.name)]
    if not task_dirs:
        raise ValueError(f'No task directories found in {ROOT}')
    for task in sorted(task_dirs, key=lambda p: int(p.name.split('_')[1])):
        runs = sorted(p for p in task.iterdir() if p.is_dir() and re.fullmatch(r'\d{8}T\d{6}Z', p.name))
        if not runs:
            raise ValueError(f'No timestamped run directories found in {task}')
        run = runs[-1]
        selected_runs.append(run)
        older_runs.extend(runs[:-1])
        counts['tasks'] += 1
        counts['runs'] += len(runs)
        rubric_file = run / 'frozen_rubric.json'
        rubric = json.loads(rubric_file.read_text())['precomputed_rubric']
        counts['all_criteria'] += len(rubric['items'])
        audit_file = run / 'evidence_audit.json'
        if not audit_file.exists():
            error_file = run / 'evidence_audit_error.json'
            manifest_file = run / 'run_manifest.json'
            manifest = json.loads(manifest_file.read_text())
            result_modes = [mode for mode, folder in [('DOM', 'dom_model'), ('Screenshot', 'screenshot_verifier')]
                            if (run / folder / 'result.json').is_file()]
            reason = json.loads(error_file.read_text())['message'] if error_file.exists() else (
                f'No completed evidence_audit.json exists; saved manifest status is {manifest.get("status", "unknown")}. '
                f'comparison.json is {"present" if (run / "comparison.json").is_file() else "absent"}. '
                f'Saved verifier results: {", ".join(result_modes) or "none"}.'
            )
            excluded.append((task.name, run.name, len(rubric['items']), reason, error_file if error_file.exists() else manifest_file))
            continue

        audit_text = audit_file.read_text()
        audit = json.loads(audit_text)
        audits.append(audit_file)
        audit_models.add(audit['audit_model'])
        assert audit['audit_method'] == 'automated_llm'
        assert audit['schema_version'] == 'automated-evidence-audit/v3'
        digest = hashlib.sha256(json.dumps(rubric, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        assert digest == audit['frozen_rubric_sha256']
        for role, model in recorded_models(run, digest).items():
            model_counts.setdefault(role, Counter())[model] += 1
        model_counts.setdefault('Automated evidence audit/adjudication', Counter())[audit['audit_model']] += 1
        criteria_entries = array_entries(audit_text, 'criteria', 2)
        assert len(criteria_entries) == len(audit['criteria']) == len(rubric['items'])
        comparison = json.loads((run / 'comparison.json').read_text())
        assert len(comparison['criteria']) == len(audit['criteria'])
        assert audit['task_alias'] == task.name
        counts['audited_tasks'] += 1
        counts['audited_criteria'] += len(criteria_entries)

        results = {}
        for mode, folder in [('dom_model', 'dom_model'), ('screenshot', 'screenshot_verifier')]:
            result_file = run / folder / 'result.json'
            result_text = result_file.read_text()
            result = json.loads(result_text)
            assert result['rubric_sha256'] == digest
            result_entries = array_entries(result_text, 'step6_rescoring_summary', 4)
            assert len(result_entries) == len(criteria_entries)
            results[mode] = (result_file, result, result_entries)

        for expected_index, (criterion, start, end, line) in enumerate(criteria_entries):
            index = criterion['criterion_index']
            assert index == expected_index
            assert criterion == audit['criteria'][index]
            assert criterion['criterion'] == rubric['items'][index]['criterion'] == comparison['criteria'][index]['criterion']
            for mode, (result_file, result, result_entries) in results.items():
                steps = result['intermediate_mm_rubric_steps']
                summary = result_entries[index][0]
                embedded = criterion[mode]['verifier_output']
                suffix = 'dom' if mode == 'dom_model' else 'image'
                assert summary['criterion'] == criterion['criterion']
                assert embedded['evidence_analysis'] == steps['step4_evidence_by_criterion'].get(str(index), [])
                assert embedded['action_only_points'] == summary['earned_points']
                assert embedded['final_points'] == summary[f'post_{suffix}_earned_points']
                assert embedded['final_justification'] == summary[f'post_{suffix}_justification']
                assert embedded['applicable_evidence'] == summary['applicable_evidence']
                assert criterion['adjudication'][mode + '_verifier_miss']['confirmed'] is not criterion[mode]['verifier_caught']
                verified_records += 1
            for key in ['dom_model_evidence_loss', 'screenshot_evidence_loss']:
                assert criterion[key] == criterion['adjudication'][key]['confirmed']

            enabled = [(key, name) for key, name in FLAGS if criterion['adjudication'][key]['confirmed']]
            if not enabled:
                counts['no_confirmed_finding'] += 1
                continue
            counts['selected'] += 1
            selected_tasks.add(task.name)
            labels[criterion['classification']] += 1
            for key, _ in enabled:
                counts[key] += 1
            dm = criterion['adjudication']['dom_model_verifier_miss']['confirmed']
            sm = criterion['adjudication']['screenshot_verifier_miss']['confirmed']
            loss = any(criterion['adjudication'][key]['confirmed'] for key in ['dom_model_evidence_loss', 'screenshot_evidence_loss'])
            if dm or sm:
                counts['miss'] += 1
                miss_tasks.add(task.name)
            else:
                counts['loss_only'] += 1
                loss_only_tasks.add(task.name)
            counts['both_missed'] += int(dm and sm)
            counts['both_evidence_loss'] += int(criterion['dom_model_evidence_loss'] and criterion['screenshot_evidence_loss'])
            counts['miss_and_loss'] += int((dm or sm) and loss)
            counts['loss'] += int(loss)

            adjudication_start = audit_text.index('"adjudication":', start, end)
            evidence_links = []
            for key, name in enabled:
                offset = audit_text.index(json.dumps(key) + ':', adjudication_start, end)
                flag_line = audit_text.count('\n', 0, offset) + 1
                evidence_links.append(link(name, audit_file, flag_line))
            for mode, missed, label in [('dom_model', dm, 'DOM output'), ('screenshot', sm, 'Screenshot output')]:
                if missed:
                    result_file, _, result_entries = results[mode]
                    evidence_links.append(link(label, result_file, result_entries[index][3]))
            detail = cell(criterion['explanation'])
            cited = source_locations(criterion, enabled)
            evidence_cell = '; '.join(evidence_links) + '<br>' + detail
            if cited:
                evidence_cell += '<br>Cited evidence: ' + cited + '.'
            rows.append('| ' + ' | '.join([
                task.name,
                f'**C{index}** — {cell(criterion["criterion"])}',
                f'`{criterion["classification"]}`',
                '<br>'.join(name for _, name in enabled),
                evidence_cell,
            ]) + ' |')

    assert counts['selected'] == len(rows)
    assert counts['audited_criteria'] == counts['selected'] + counts['no_confirmed_finding']
    assert counts['miss'] + counts['loss_only'] == counts['selected']
    assert counts['dom_model_verifier_miss'] + counts['screenshot_verifier_miss'] - counts['both_missed'] == counts['miss']

    if not audits:
        raise ValueError(f'No completed evidence audits found in {ROOT}')
    statistics = {
        'verifier_miss': paired_statistics(counts['screenshot_verifier_miss'], counts['dom_model_verifier_miss'],
                                           counts['both_missed'], counts['audited_criteria']),
        'evidence_loss': paired_statistics(counts['screenshot_evidence_loss'], counts['dom_model_evidence_loss'],
                                           counts['both_evidence_loss'], counts['audited_criteria']),
    }
    sample_run = audits[0].parent
    sample_task = sample_run.parent.name
    without_inputs = sum(not (p.parent / '_inputs').is_dir() for p in audits)
    date_values = sorted({f'{p.name[:4]}-{p.name[4:6]}-{p.name[6:8]}' for p in selected_runs})
    date_note = f'All selected runs are dated {date_values[0]}.' if len(date_values) == 1 else (
        f'Selected run dates span {date_values[0]} through {date_values[-1]}.'
    )
    old_tasks = ', '.join(sorted({p.parent.name for p in older_runs}, key=lambda name: int(name.split('_')[1])))
    older_note = (f'The {len(older_runs)} older runs for {old_tasks} are excluded to avoid counting a task twice.'
                  if older_runs else 'There are no older runs to exclude.')
    dominant_label = labels.most_common(1)[0][0] if labels else 'none'
    lines = [
        '**Missed evidence by task and criterion**',
        '',
        *summary_lines(statistics, model_counts, sample_run, counts['audited_tasks']),
        f'This table consolidates the saved evidence audits for the latest timestamped run of each task in this directory. It contains one row per task/criterion with an adjudicated DOM or screenshot verifier miss, evidence loss in either representation, or both. Criterion IDs (`C0`, `C1`, …) use the zero-based `criterion_index` from the audit.',
        '',
        f'There are {counts["tasks"]} tasks and {counts["runs"]} saved runs. The latest runs contain {counts["all_criteria"]} criteria; {counts["audited_tasks"]} tasks / {counts["audited_criteria"]} criteria have completed audits. The table contains **{counts["selected"]} criteria across {len(selected_tasks)} tasks**: **{counts["miss"]} with a verifier miss** and **{counts["loss_only"]} with evidence loss only**. Findings below are the existing automated audit/adjudication judgments ({", ".join(sorted(audit_models))}), rather than a new manual review of original screenshots or DOM states. {len(excluded)} tasks lack completed audits and are listed after the table.',
        '',
        '**Files needed from this directory**',
        '',
        '- `task_*/<latest-run>/evidence_audit.json` is the primary source: final `criteria[*]` contains the criterion, original classification, explanation, saved verifier analyses, and `adjudication` with confirmed findings, decisive evidence, and citations. Example: ' + link(f'{sample_task} audit', sample_run / 'evidence_audit.json') + '.',
        '- `task_*/<latest-run>/frozen_rubric.json` supplies the canonical criterion wording, order, and requirements. Example: ' + link(f'{sample_task} rubric', sample_run / 'frozen_rubric.json') + '.',
        '- `task_*/<latest-run>/dom_model/result.json` and `screenshot_verifier/result.json` supply each verifier’s actual evidence analysis, justification, and scores. Example: ' + link('DOM result', sample_run / 'dom_model/result.json') + ' and ' + link('screenshot result', sample_run / 'screenshot_verifier/result.json') + '.',
        '- `task_*/<latest-run>/run_manifest.json` establishes the saved run status and provenance. `comparison.json` cross-checks criterion order and scores; its aggregate scores alone do not establish a missed-evidence finding. Example: ' + link('manifest', sample_run / 'run_manifest.json') + ' and ' + link('comparison', sample_run / 'comparison.json') + '.',
        '- `task_*/<latest-run>/evidence_audit_error.json`, where present, explains why a task has no validated final audit. Failed attempt responses inside these files are excluded from the confirmed findings.',
        '',
        '**How to read the five columns**',
        '',
        '- **Task / criterion:** task alias and exact frozen-rubric criterion. The evidence path identifies the selected run.',
        '- **Label:** the audit’s original `classification`, copied unchanged. A representation-loss label can coexist with verifier misses; use Category for the complete finding.',
        '- **Category:** every final adjudication flag with `confirmed: true`. “DOM verifier miss” or “Screenshot verifier miss” means the verifier overlooked or materially misused available evidence, failed to acknowledge an evidence limitation, or misapplied the criterion. It can occur even when the final score is unchanged. “DOM evidence loss” or “Screenshot evidence loss” means decision-essential evidence was preserved by the other representation but lost in this one; it does not itself establish a verifier error.',
        '- **Pointer to evidence file:** links to the exact adjudication blocks in `evidence_audit.json` and, for confirmed verifier misses, the corresponding criterion in the model’s `result.json`. The explanation is copied from the final audit. “Cited evidence” identifies the original source file and its location; the linked audit retains the quotations.',
        '',
        f'To read only model mistakes, select rows with a **verifier miss** category: {counts["dom_model_verifier_miss"]} DOM misses and {counts["screenshot_verifier_miss"]} screenshot misses overlap on {counts["both_missed"]} criteria, giving {counts["miss"]} unique criteria across {len(miss_tasks)} tasks. Evidence loss affects {counts["loss"]} unique criteria; {counts["miss_and_loss"]} also have a verifier miss. These overlapping counts must not be added. The {counts["no_confirmed_finding"]} audited criteria with no confirmed flag are omitted.',
        '',
        f'**Evidence availability:** {without_inputs} of {len(audits)} completed latest-run audit folders lack `_inputs`. Cited `screenshotN.png` and `dom_modelN.txt` names identify sources recorded by the audits; they are not links to independently reviewed originals. The links below point to existing audit and result files that retain citations, quotations, and model reasoning.',
        '',
        '| Task | Criterion | Label | Category | Pointer to evidence file |',
        '|---|---|---|---|---|',
        *rows,
        '',
        '**Coverage gaps**',
        '',
        ('The following latest runs have no completed, validated audit. Their criteria are excluded from the table, and their absence is not evidence that either model caught everything.'
         if excluded else 'All latest runs have completed, validated audits.'),
        '',
    ]
    for task, timestamp, ncriteria, reason, evidence_file in excluded:
        lines.append(f'- **{task}** (`{timestamp}`, {ncriteria} criteria): {cell(reason)} ' + link('Status evidence', evidence_file) + '.')
    lines.extend([
        '',
        '**Verification and limits**',
        '',
        f'- Directly verified: selected the latest run for every task; matched criterion names/order to the frozen rubric and comparison; verified canonical rubric hashes against both results and the audit; checked {verified_records} saved model/criterion records for matching evidence analyses, points, and final justifications; checked every included finding against its final adjudication flag. Every linked file and target line exists.',
        '- Interpretation: the labels, explanations, and judgments are inherited from the automated audits. A verifier miss is not necessarily a failed browser task, a score disagreement, or a false negative; the linked justification specifies what was missed or overclaimed.',
        f'- Unverified boundary: independently confirming the automated findings requires the original screenshots/DOM states and shared trajectory. Resolving the {len(excluded)} coverage gaps requires a completed valid audit or a separate explicitly identified review.',
        f'- Run denominator: {older_note} {date_note} Exact timestamps are preserved in the linked paths.',
        '',
        f'The most frequent saved label is `{dominant_label}`; the table separately identifies the {counts["miss"]} criteria with a verifier-miss finding. There are {len(excluded)} unaudited tasks; original evidence was not independently reviewed.',
        '',
    ])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text('\n'.join(lines), encoding='utf-8')
    summary = {
        'output': str(OUTPUT),
        'bytes': OUTPUT.stat().st_size,
        'counts': dict(counts),
        'labels': dict(labels),
        'statistics': statistics,
        'models': {role: dict(models) for role, models in model_counts.items()},
        'affected_tasks': len(selected_tasks),
        'verified_model_criterion_records': verified_records,
        'excluded_tasks': [item[0] for item in excluded],
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--evaluation-dir', type=Path,
        default=Path(__file__).resolve().parent.parent / 'evaluation',
        help='Evaluation directory (default: ../evaluation relative to the script).',
    )
    parser.add_argument(
        '--output', type=Path,
        help='Output Markdown path (default: <evaluation-dir>/missed_evidence_table.md).',
    )
    args = parser.parse_args()
    if not args.evaluation_dir.is_dir():
        parser.error(f'Evaluation directory does not exist: {args.evaluation_dir}')
    output = args.output if args.output is not None else args.evaluation_dir / 'missed_evidence_table.md'
    if __debug__ is False:
        parser.error('Run without -O: integrity assertions must remain enabled.')
    summary = generate_report(args.evaluation_dir, output)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
