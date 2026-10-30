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

A criterion can lose different items in both representations and contributes
once to each marginal count; the counts overlap. Primary
[category](evidence-categories.md) labels require separate annotations; they
are not assigned by the stored audit classification.
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

URL-excluded calculations require explicit per-representation category
annotations. They are not reported for this cohort because those annotations
are not stored. A subset calculation must disclose whether it removes losses
from the numerator or whole criteria from the denominator.

### Benchmark evaluation

The [technical report](technical-report.md) covers 92 evaluated tasks and
91 completed evidence audits, with 582 audited criteria, 118 screenshot losses
and 7 DOM losses. Of 100 recorded tasks, 92 had usable, aligned evidence for evaluation; 8 were excluded because captures were missing/incomplete or failed URL alignment. Evidence-loss results cover 91 tasks because task 76’s audit failed validation.

The findings are automated audit/adjudication judgments. Human verification
is not established by these saved artifacts.

The acting agent uses `gpt-5.6` for browser-action generation. The verifiers
use `gpt-5.2` for rubric generation and evidence judgments and `gpt-5.6-terra`
for action/validity judgments. See
[model provenance](technical-report.md#models-and-evaluation-provenance).

Standalone verifier commands select this model with `--action-model`.
The paired comparison supplies the same model to both verifiers.

Exploratory 95% Wilson intervals assume independent criteria and do not
adjust for correlation among criteria within a task or annotation error.
Website blockers, recorded execution failures, task scores, and source-loss
counts are separate measurements.

## Operation

See the [runbook](runbook.md#score-a-prepared-task) for preparation, validation,
and comparison commands. Saved rubrics, scores, audits, and provenance are
written under `evaluation/`.
