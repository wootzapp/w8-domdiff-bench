# Results

The matched comparison covers **97 tasks and 619 criteria per run**, identifying **61.00 screenshot losses (9.85%)** and **13.00 DOM losses (2.10%)** on average. Inventory uses `gpt-5.6-sol` and adjudication uses `gemini-3.1-pro-preview`. These measure evidence availability, not task success or answer correctness.

The matched comparison uses **97 tasks and 619 criteria per run**. Successful, failed and errored recordings with usable evidence are included. Recordings with no captured state remain unscored, not zero-loss audits.

| Run | Audited tasks | Criteria | Screenshot losses | DOM losses |
| --- | ---: | ---: | ---: | ---: |
| run_1 | 100 | 640 | 51 (7.97%) | 16 (2.50%) |
| run_2 | 99 | 633 | 62 (9.79%) | 15 (2.37%) |
| run_3 | 97 | 619 | 70 (11.31%) | 8 (1.29%) |

Selected results are in the [repository README](../README.md#evaluation-results).
The [technical report](../docs/technical-report.md) documents the repository's
browser capture pipeline, success rules, source-loss equations, models and
review roles, representation sizes, and the criterion-level
findings. [EVALUATIONS.md](EVALUATIONS.md) points to that report.

| Artifact | Contents | How to verify |
| --- | --- | --- |
| [summary.json](summary.json) | Coverage, paired outcomes, category counts, sensitivity analyses and file-size means. Rates and confidence limits are fractions in `[0, 1]`. | Compare with the report’s aggregate/category tables and the annotation TSV. |
| [Technical report](../docs/technical-report.md) | Repository methods and evaluation findings, including model roles, review boundaries, references, and representation sizes. | Follow criterion citations to audits, frozen rubrics, and run manifests; inspect the method and size sections for definitions and context. |
| [Evaluation figures](../docs/assets/evaluations/) | Published PNG images embedded in the report and SVG versions for export. | Compare their displayed counts and rates with the report tables and `summary.json`. |
| [Category annotations](evidence_categories.tsv) | One primary category and rationale for each confirmed representation/criterion loss. | Recompute its source-finding hash and compare the 222 rows with the category tables. |
| [Hosted evaluations](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/evaluations) | Per-task verifier results, audit/adjudication findings, and provenance supporting this benchmark. | Follow task references to the audits and final adjudications cited by the report. |

## Counting and sensitivity

The audits identify **219 affected run/criterion observations**, covering **118 distinct criterion positions across 49 tasks**. A criterion can lose different items in both representations. Each representation/criterion loss receives one primary category; averaged counts can be fractional. Rows are rounded independently; totals use unrounded counts. All 619 criteria remain in every matched run denominator. The exploratory subset uses 88 common tasks and 572 criteria per run.

The [protocol](../docs/evaluation-protocol.md) and [category guide](../docs/evidence-categories.md) define the rules. `confidence_intervals` contains task-then-run bootstrap bounds for rates, their difference and relative reduction. Bounds are fractions; multiply by 100 for percentages. Audit labels remain fixed.

## Mean recorded file sizes

| Representation | Artifact | Captured observations | Mean kB | Mean KiB |
| --- | --- | ---: | ---: | ---: |
| DOM-diff Optimized | `dom_model.txt` — compact model-facing text | 2,592 | 5.37 | **5.25** |
| Text-dense DOM | `dom_full.txt` — detailed readable text | 2,592 | 48.40 | **47.26** |
| Full DOM | `dom.json` — structured snapshot | 2,592 | 211.40 | **206.45** |

The same 2,592 captured states from all 300 retained recordings are used for all three means, including unsuccessful recordings. Files are weighted equally, not tasks. 1 kB = 1,000 bytes; 1 KiB = 1,024 bytes. Graphs use KiB.

Dataset repository:
[WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks).
