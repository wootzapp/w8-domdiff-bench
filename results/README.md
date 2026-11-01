# Results

The benchmark’s paired evaluation and validated audits cover **100 tasks and 640 criteria**. Inventory uses `gpt-5.6-sol` and final adjudication uses `gpt-5.6-terra`. The audits identify **50 screenshot losses (7.81%)** and **14 DOM losses (2.19%)**. These measure evidence availability, not task success or answer correctness.

All 100 recorded tasks have usable, aligned evidence and validated audits covering 640 criteria. Successful, failed and errored recordings with usable evidence are included; no tasks are excluded.

| Analysis | Tasks | Audited criteria | Screenshot losses | DOM losses |
| --- | ---: | ---: | ---: | ---: |
| All source-evidence loss categories | 100 | 640 | **50 (7.81%)** | **14 (2.19%)** |
| Listed access-blocked task IDs excluded | 91 | 593 | **50 (8.43%)** | **12 (2.02%)** |

Selected results are in the [repository README](../README.md#evaluation-results).
The [technical report](../docs/technical-report.md) documents the repository's
browser capture pipeline, success rules, source-loss equations, models and
review roles, representation sizes, and all 63 criterion-level
findings. [EVALUATIONS.md](EVALUATIONS.md) points to that report.

| Artifact | Contents | How to verify |
| --- | --- | --- |
| [summary.json](summary.json) | Coverage, paired outcomes, category counts, sensitivity analyses and file-size means. Rates and confidence limits are fractions in `[0, 1]`. | Compare with the report’s aggregate/category tables and the annotation TSV. |
| [Technical report](../docs/technical-report.md) | Repository methods and evaluation findings, including model roles, review boundaries, references, and representation sizes. | Follow criterion citations to audits, frozen rubrics, and run manifests; inspect the method and size sections for definitions and context. |
| [Evaluation figures](../docs/assets/evaluations/) | Published PNG images embedded in the report and SVG versions for export. | Compare their displayed counts and rates with the report tables and `summary.json`. |
| [Category annotations](evidence_categories.tsv) | One primary category and rationale for each confirmed representation/criterion loss. | Recompute its source-finding hash and compare the 64 rows with the category tables. |
| [Hosted evaluations](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/evaluation) | Per-task verifier results, audit/adjudication findings, and provenance supporting this benchmark. | Follow task references to the audits and final adjudications cited by the report. |

## Counting and sensitivity

One criterion has losses in both representations, affecting different required items. The marginal counts total 64 representation/criterion losses across 63 distinct affected criteria. All 640 audited criteria stay in the primary denominator, including 577 without a confirmed paired gap.

Excluding the nine cited blocker-task IDs leaves **91 tasks and 593 criteria**. The blocker subset is exploratory, not pre-specified. Category labels are report annotations of saved findings.

The [protocol](../docs/evaluation-protocol.md) and [category guide](../docs/evidence-categories.md) define the rules. Intervals resample whole tasks and hold automated labels fixed; independent human review has not been established.

`task_cluster_ci95` stores the 95% bounds for each reported loss rate. All
rates and interval bounds are fractions; multiply by 100 for percentages.

## Mean recorded file sizes

| Representation | Artifact | Captured observations | Mean kB | Mean KiB |
| --- | --- | ---: | ---: | ---: |
| DOM-diff Optimized | `dom_model.txt` — compact model-facing text | 883 | 5.23 | **5.11** |
| Text-dense DOM | `dom_full.txt` — detailed readable text | 883 | 48.51 | **47.38** |
| Full DOM | `dom.json` — structured snapshot | 883 | 213.15 | **208.15** |

The same 883 captured states from all 100 selected recordings are used for all three means, including unsuccessful recordings. Files are weighted equally, not tasks. 1 kB = 1,000 bytes; 1 KiB = 1,024 bytes. Graphs use KiB.

The complete paired trajectories and evaluation artifacts used by this
repository are available from
[WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks).
