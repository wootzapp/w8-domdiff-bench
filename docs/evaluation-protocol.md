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
[category](EVIDENCE-CATEGORIES.md). A criterion can lose different items in
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

The saved audits require exact URL evidence within a representation where
the rubric makes website, page, record, or endpoint identity essential.
Visible branding and URLs in shared action history do not substitute under
that identity rule. A URL missing from a screenshot is not automatically a
loss for every criterion. The screenshot capture omits the browser’s
address bar, which makes this rule material to the aggregate comparison.

The primary URL-excluded analysis removes primary URL-category losses from
each representation’s numerator and keeps all audited criteria in the
cohort denominator. It preserves non-URL losses on the other side of the
same criterion. The report separately shows alternatives removing entire
criteria with URL findings; those have different denominators. These are
recalculations of saved findings, not new audits or experiments adding URLs
to screenshots.

### Published evaluation snapshot

The [technical report](technical-report.md) uses the latest selected saved
run per task: 100 completed audits covering 642 criteria. It includes 151
screenshot losses and 5 DOM losses, overlapping on two criteria. Findings
are saved automated audit/adjudication judgments, rather than independent
manual review of the original source states.

The saved runs used `gpt-5.2` for rubric generation and evidence judgments,
`o4-mini` for action/validity judgments, and `gpt-5.6-sol` for automated
audit/adjudication. See [model provenance](technical-report.md#models-and-evaluation-provenance).
These identities describe the saved runs; they do not freeze future CLI
defaults.

Exploratory 95% Wilson intervals assume independent criteria and do not
adjust for correlation among criteria within a task, repeated model runs,
or audit error. Website blockers, recorded execution failures, task scores,
and source-loss counts are separate measurements. Recording and evaluation
run versions can differ; check provenance before matching their artifacts.

## Commands

Download and validate one pair without paid calls or evaluation output:

```bash
./scripts/run-comparison --task task_01
```

Run the controlled comparison:

```bash
./scripts/run-comparison --task task_01 --execute
```

Run every paired task:

```bash
./scripts/run-comparison --all --execute
```

Generated runs are written under `evaluation/`, which is ignored by Git.

