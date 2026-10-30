# Results

The paired evaluation contains **92 tasks**. Completed automated evidence
audits cover **91 tasks and 582 criteria**, with **118 screenshot losses
(20.27%)** and **7 DOM losses (1.20%)**.

Of 100 recorded tasks, 92 had usable, aligned evidence for evaluation; 8 were excluded because captures were missing/incomplete or failed URL alignment. Evidence-loss results cover 91 tasks because task 76’s audit failed validation.

| Coverage | Count |
| --- | ---: |
| Recorded tasks | 100 |
| Evaluated tasks | 92 |
| Completed evidence audits | 91 |
| Criteria scored by both verifiers | 589 |
| Criteria included in evidence-loss rates | 582 |

| Measure | Screenshot | DOM-diff Optimized |
| --- | ---: | ---: |
| Evidence losses | **118/582 (20.27%)** | **7/582 (1.20%)** |
| Verifier interpretation misses | 84/582 (14.43%) | 76/582 (13.06%) |

These are evidence-availability and interpretation measurements, not task-success
rates. Recording outcomes are **81 successes, 7 agent failures and 12 execution
errors**. Evaluation includes 80 successes, 7 agent failures and 5 execution
errors: outcomes alone do not decide whether evidence is usable.

## Counting and coverage

The 118 screenshot and 7 DOM losses overlap on 4 criteria, giving
**121 affected criteria across 74 tasks**. All 582 audited
criteria remain in the denominator, including 461 without a source gap.
Task 76's verifier scores are retained; its 7 criteria are not
included in evidence-loss rates because its audit is incomplete.

Excluded task IDs are **5, 18, 20, 46, 49, 59, 77 and 94**. Task 5 fails initial
URL alignment; the other seven lack a complete captured state sequence.
The preparation report preserves the exact validation errors.

| Screenshot loss only | DOM loss only | Loss in both | Neither |
| ---: | ---: | ---: | ---: |
| 114 | 3 | 4 | 461 |

## Artifacts

- [Summary](summary.json): counts, cohort exclusions, confidence intervals,
  model roles, sizes and selected evaluation paths.
- [Source audits on Hugging Face](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/a10226a46d3a9c3ee5f0f40b244163d2a6b50e75/evaluation): full criterion-level
  adjudications, citations and frozen-rubric checksums.
- [Technical report](../docs/technical-report.md): methods, interpretation,
  coverage and criterion-level findings.
- [Figures](../docs/assets/evaluations/): evidence-loss rates and task coverage.

Saved inputs and evaluations use `trajectories/` and `evaluation/`. The
[dataset repository](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks)
provides task data; match the selected task IDs and source checksums before
comparing downloaded artifacts with this summary.

## Limits

The findings come from `gpt-5.6-sol` audit/adjudication. Human verification is
not established by these saved artifacts. Wilson intervals do not adjust for
correlation within a task or audit error. The saved audits have no primary
category annotations, so URL-only and access-blocker sensitivity totals are
not asserted. See the [protocol](../docs/evaluation-protocol.md).
