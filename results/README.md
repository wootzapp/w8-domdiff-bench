# Results

The benchmark’s paired evaluation and validated audits cover **92 tasks and 589 criteria**. Inventory uses `gpt-5.6-sol` and final adjudication uses `gpt-5.6-terra`. The audits identify **41 screenshot losses (6.96%)** and **10 DOM losses (1.70%)**. These measure evidence availability, not task success or answer correctness.

Of 100 recorded tasks, 92 had usable, aligned evidence for evaluation; 8 were excluded because captures were missing/incomplete or failed URL alignment. All 92 evaluated tasks have validated evidence audits covering 589 criteria.

| Analysis | Tasks | Audited criteria | Screenshot losses | DOM losses |
| --- | ---: | ---: | ---: | ---: |
| All source-evidence loss categories | 92 | 589 | **41 (6.96%)** | **10 (1.70%)** |
| URL loss category excluded | 92 | 589 | **34 (5.77%)** | **10 (1.70%)** |
| Listed access-blocked task IDs excluded | 83 | 536 | **41 (7.65%)** | **9 (1.68%)** |
| Listed access-blocked task IDs and URL loss category excluded | 83 | 536 | **34 (6.34%)** | **9 (1.68%)** |

Selected results are in the [repository README](../README.md#evaluation-results).
The [technical report](../docs/technical-report.md) documents the repository's
browser capture pipeline, success rules, source-loss equations, models and
review roles, representation sizes, and all 50 criterion-level
findings. [EVALUATIONS.md](EVALUATIONS.md) points to that report.

| Artifact | Contents | How to verify |
| --- | --- | --- |
| [summary.json](summary.json) | Coverage, paired outcomes, category counts, sensitivity analyses and file-size means. Rates and confidence limits are fractions in `[0, 1]`. | Compare with the report’s aggregate/category tables and the annotation TSV. |
| [Technical report](../docs/technical-report.md) | Repository methods and evaluation findings, including model roles, review boundaries, references, and representation sizes. | Follow criterion citations to audits, frozen rubrics, and run manifests; inspect the method and size sections for definitions and context. |
| [Evaluation figures](../docs/assets/evaluations/) | Published PNG images embedded in the report and SVG versions for export. | Compare their displayed counts and rates with the report tables and `summary.json`. |
| [Category annotations](evidence_categories.tsv) | One primary category and rationale for each confirmed representation/criterion loss. | Recompute its source-finding hash and compare the 51 rows with the category tables. |
| [Hosted evaluations](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/evaluation) | Per-task verifier results, audit/adjudication findings, and provenance supporting this benchmark. | Follow task references to the audits and final adjudications cited by the report. |

## Counting and sensitivity

One criterion has losses in both representations, affecting different required items. The marginal counts total 51 representation/criterion losses across 50 distinct affected criteria. All 589 audited criteria stay in the primary denominator, including 539 without a confirmed paired gap.

Excluding seven primary screenshot URL losses leaves **34/589 (5.77%)** screenshot losses and **10/589 (1.70%)** DOM losses. Excluding the nine cited blocker-task IDs leaves **83 tasks and 536 criteria**. The report retains both views and alternatives removing entire URL criteria. Category labels are report annotations of saved findings.

The [protocol](../docs/evaluation-protocol.md) and [category guide](../docs/evidence-categories.md) define the rules. Intervals resample whole tasks and hold automated labels fixed; independent human review has not been established.

`task_cluster_ci95` stores the 95% bounds for each reported loss rate. All
rates and interval bounds are fractions; multiply by 100 for percentages.

## Mean recorded file sizes

| Representation | Artifact | Captured observations | Mean kB | Mean KiB |
| --- | --- | ---: | ---: | ---: |
| DOM-diff Optimized | `dom_model.txt` — compact model-facing text | 853 | 5.28 | **5.16** |
| Text-dense DOM | `dom_full.txt` — detailed readable text | 853 | 48.70 | **47.56** |
| Full DOM | `dom.json` — structured snapshot | 853 | 212.96 | **207.97** |

The same 853 recorded states are used for all three means. 1 kB = 1,000 bytes; 1 KiB = 1,024 bytes. Graphs use KiB.

The complete paired trajectories and evaluation artifacts used by this
repository are available from
[WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks).
