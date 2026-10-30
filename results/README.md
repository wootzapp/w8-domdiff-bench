# Results

The benchmark’s paired evaluation covers **92 tasks and 589 scored criteria**. Completed `gpt-5.6-sol` audits cover **91 tasks and 582 criteria**, identifying **118 screenshot losses (20.27%)** and **7 DOM losses (1.20%)**. These measure evidence availability, not task success or answer correctness.

Of 100 recorded tasks, 92 had usable, aligned evidence for evaluation; 8 were excluded because captures were missing/incomplete or failed URL alignment. Evidence-loss results cover 91 tasks because task 76’s audit failed validation.

| Analysis | Tasks | Audited criteria | Screenshot losses | DOM losses |
| --- | ---: | ---: | ---: | ---: |
| All source-evidence loss categories | 91 | 582 | **118 (20.27%)** | **7 (1.20%)** |
| URL loss category excluded | 91 | 582 | **33 (5.67%)** | **7 (1.20%)** |
| Listed access-blocked task IDs excluded | 82 | 529 | **107 (20.23%)** | **7 (1.32%)** |
| Listed access-blocked task IDs and URL loss category excluded | 82 | 529 | **32 (6.05%)** | **7 (1.32%)** |

Selected results are in the [repository README](../README.md#evaluation-results).
The [technical report](../docs/technical-report.md) documents the repository's
browser capture pipeline, success rules, source-loss equations, models and
review roles, representation sizes, and all 121 criterion-level
findings. [EVALUATIONS.md](EVALUATIONS.md) points to that report.

| Artifact | Contents | How to verify |
| --- | --- | --- |
| [summary.json](summary.json) | Coverage, paired outcomes, category counts, sensitivity analyses and file-size means. Rates and confidence limits are fractions in `[0, 1]`. | Compare with the report’s aggregate/category tables and the annotation TSV. |
| [Technical report](../docs/technical-report.md) | Repository methods and evaluation findings, including model roles, review boundaries, references, and representation sizes. | Follow criterion citations to audits, frozen rubrics, and run manifests; inspect the method and size sections for definitions and context. |
| [Evaluation figures](../docs/assets/evaluations/) | Published PNG images embedded in the report and SVG versions for export. | Compare their displayed counts and rates with the report tables and `summary.json`. |
| [Category annotations](evidence_categories.tsv) | One primary category and rationale for each confirmed representation/criterion loss. | Recompute its source-finding hash and compare the 125 rows with the category tables. |
| [Hosted evaluations](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/8f9301ddad1c18b675c5b2df1c364bbbeff8f0a6/evaluation) | Per-task verifier results, audit/adjudication findings, and provenance supporting this benchmark. | Follow task references to the audits and final adjudications cited by the report. |

## Counting and sensitivity

Four criteria have losses in both representations, affecting different required items. The marginal counts total 125 representation/criterion losses across 121 distinct affected criteria. All 582 audited criteria stay in the primary denominator, including 461 without a confirmed paired gap.

Excluding 85 primary screenshot URL losses leaves **33/582 (5.67%)** screenshot losses and **7/582 (1.20%)** DOM losses. Excluding the nine cited blocker-task IDs leaves **82 tasks and 529 criteria**. The report and summary retain both subset views and alternatives removing entire criteria with primary URL findings. Category labels are report annotations of unchanged audit findings, with rationales in the TSV.

The [protocol](../docs/evaluation-protocol.md) and [category guide](../docs/evidence-categories.md) define the rules. Wilson intervals do not adjust for within-task correlation or annotation error; internal human review remains a separate step.

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
