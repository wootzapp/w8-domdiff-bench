# Evaluation Protocol

The comparison uses one recorded task, one final answer, one action history,
and one frozen rubric for both evidence modes.

## Inputs

Each paired task contains:

- ordered screenshots for the screenshot verifier;
- ordered `dom_modelN.txt` states for the DOM-model verifier;
- the same `web_surfer.log` action history;
- the same final answer;
- the same task definition and frozen rubric.

The preflight checks task identity, action alignment, state ordering, rubric
shape, and required files before model clients are created.

## Controlled scoring

Both sides use the same judge model, action model, rubric threshold, evidence
count, majority-vote count, and success rule. Only the evidence loader differs.
The comparison command fails if those controls drift.

One rubric is generated or imported first. Its canonical SHA-256 and point
denominator are recorded, then the unchanged object is passed to both sides.

Both modes receive the recorded refs, targets, and available coordinates.
Coordinates are derived element centres, not exact click-event traces;
provenance stays outside judge inputs. Some published pairs projected these
fields separately, so comparisons across collections must account for that
input difference.

Tool-failure diagnostics distinguish command parameters from `thoughts` and
`target` annotations. They run after scoring and outcome verification, without
changing points, penalties, thresholds, or the recorded action history.

### Success rules

The normalized rubric score is the earned point total divided by the maximum
available points. `rubric_is_success` records whether that ratio meets the
rubric threshold, currently **0.8** in the paired comparison. A strict
full-score success means earning every available point (`x/x`).

The standalone verifier runners select their binary `score` with `--success`:

| Rule | Binary success condition |
| --- | --- |
| `outcome` | The outcome judge returns `output_success=true`. |
| `process` | The normalized rubric score meets the rubric threshold. |
| `both` | Both the outcome and process conditions hold. |

The paired comparison currently fixes **`--success outcome`**. It separately
retains rubric points, the normalized score, and `rubric_is_success`, so its
binary result can differ from a strict full-score summary. The shared
controls also fix five evidence items per criterion, a screenshot keypoint
threshold of 3, a minimum relevance threshold of 0, and one voting instance.
See the [implementation](../w8bench/verifier/common.py) and the
[formal definitions](technical-report.md#rubric-scores-and-task-success-rules).
Saved run manifests establish the settings used for a particular run.

## Evidence-loss audit

The audit asks whether a rubric fact is present in each ordered evidence
source. It keeps missing source evidence separate from judge disagreement.
The headline counts are therefore evidence-availability measurements, not a
general claim that one verifier always scores tasks better.

### Source-loss counting

A representation loses evidence for a criterion when at least one required
item is absent from that representation and present in the other, across
the eligible ordered source states. A criterion contributes at most one
loss per representation even when several required items are missing.
Items absent from both representations, or present in both, do not trigger
paired source loss. Evidence that a verifier overlooks or misinterprets is
a separate interpretation error.

Each representation/criterion loss receives one primary
[category](evidence-categories.md). A criterion can lose different items in
both representations and have a different category on each side. Such a
criterion contributes once to each marginal count; the counts overlap.
Multiple criteria can also depend on the same capture omission.

Rates divide confirmed criterion-level losses by all audited criteria in
the selected cohort, including criteria with no loss. This measures paired
availability differences rather than absolute information loss against the
live webpage, since gaps shared by both representations remain undetected.
The report gives the [availability indicators and rate equations](technical-report.md#paired-source-evidence-loss)
and their [current numerical values](technical-report.md#current-counts-and-relative-reduction).

### URL identity and sensitivity

Observed URLs in the formatted action history count as evidence for each
verifier receiving them. A URL absent from screenshot pixels alone is not a
loss when that shared context establishes the required identity. Navigation
arguments and a supplied start URL express intent, not an observed page.
Query strings, fragments and text removed by the history formatter cannot be
restored by inference. Citations distinguish shared history from page content.

The primary URL-excluded analysis removes primary URL-category losses from
each representation’s numerator and keeps all audited criteria in the
cohort denominator. It preserves non-URL losses on the other side of the
same criterion. The report separately shows alternatives removing entire
criteria with URL findings; those have different denominators. These are
recalculations of saved findings, not new audits or experiments adding URLs
to screenshots.

### Benchmark evaluation

The [technical report](technical-report.md) contains the published counts and
the [category annotations](../results/evidence_categories.tsv). Inventory uses
`gpt-5.6-sol` and adjudication uses `gpt-5.6-terra`.

Evaluation requires usable, aligned captures. Audit failures remain listed
separately and do not count as either confirmed loss or confirmed absence of
loss. Verifier scores remain available when an audit fails validation.

The acting agent uses `gpt-5.6` for browser-action generation. The verifiers
use `gpt-5.2` for rubric generation and evidence judgments and `gpt-5.6-terra`
for action/validity judgments. See
[models and review roles](technical-report.md#models-and-evaluation-provenance).

Standalone verifier commands select this model with `--action-model`.
The paired comparison supplies the same model to both verifiers.

`EVIDENCE_ADJUDICATOR_MODEL` selects the audit adjudicator; its default is
`gpt-5.6-terra`. It does not change the recording or verifier models.

Aggregate intervals resample whole tasks, keeping their criteria and both
modalities together. The reported rate remains total losses divided by total
criteria, not the average of task rates. The paired difference uses the same
task draws. The percentile bootstrap uses 20,000 draws and records its seed.
It assumes independent tasks and does not measure annotation error. A single
task has no estimable interval; constant samples are marked as degenerate.
Website blockers, recorded execution failures, task scores, and source-loss
counts are separate measurements.

### Human review

Optional human review can use 150 audited criteria selected uniformly without
replacement. Two reviewers independently use the frozen rubric, ordered
sources and the formatted history received by each verifier. Final answers
remain claims, not proof of page content. Reviewers must not consult model
findings or each other's labels before submitting.

Inter-reviewer agreement and agreement with the locked audit labels remain
unreported until both human sheets are completed. Distinct model variants do
not establish independent human verification.

## Operation

See the [runbook](runbook.md#score-a-prepared-task) for preparation, validation,
and comparison commands. Saved rubrics, scores, audits, and provenance are
written under `evaluation/`.
