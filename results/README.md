# Results

The current saved paired evaluation covers **100 tasks and 642 audited
criteria**. Final automated adjudications identify **151 screenshot losses
(23.52%)** and **5 DOM losses (0.78%)**. These are evidence-availability
counts, rather than measurements of task success or answer correctness.

Selected results are in the [repository README](../README.md#evaluation-results).
The full source `EVALUATIONS.md` is preserved as the
[technical report](../docs/technical-report.md), including all tables,
sensitivities, blockers, execution failures, model provenance, and 154
criterion-level findings. [EVALUATIONS.md](EVALUATIONS.md) points to that
canonical report.

| Artifact | Contents | How to verify |
| --- | --- | --- |
| [summary.json](summary.json) | Full-dataset counts, paired outcomes, category counts, and sensitivity analyses. Rates and confidence limits are fractions in `[0, 1]`. | Compare with the report’s aggregate and category tables. |
| [Technical report](../docs/technical-report.md) | Entire evaluation write-up synchronized from the dataset’s `EVALUATIONS.md`. | Follow criterion citations to saved audits, frozen rubrics, and run manifests. |
| [Evaluation figures](../docs/assets/evaluations/) | PNG images embedded in the report and SVG versions for export. | Regenerate from the report’s tables with the figure script below. |
| [Hosted evaluations](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/evaluation) | Per-task verifier results, automated audits, and selected run provenance. | Check the latest selected run for each task and its final adjudications. |

## Counting and sensitivity

Two criteria have losses in both representations, affecting different
required items. The marginal counts therefore total 156 losses across 154
distinct affected criteria. All 642 audited criteria remain in the primary
rate denominator, including the 488 without a source gap.

The URL-excluded analysis removes 117 screenshot URL losses while retaining
all criteria: **34/642 (5.30%)** for screenshots and **5/642 (0.78%)** for
DOM. Excluding the 12 listed access-blocked task IDs leaves 88 tasks and
575 criteria. The report and JSON summary retain both versions of that
cohort, with and without URL losses, and the alternative analyses that
remove entire criteria with URL findings.

The judgments are existing automated audits, not a new manual review.
Criterion-level Wilson intervals do not adjust for correlation within tasks
or audit errors. See the [protocol](../docs/evaluation-protocol.md) and
[category guide](../docs/EVIDENCE-CATEGORIES.md) for definitions and caveats.

## Regenerate figures

The figure script requires Matplotlib, which is separate from the core
runtime dependencies. From the repository root, run:

```bash
python -m pip install matplotlib
python scripts/generate_evaluation_figures.py
```

The script reads `docs/technical-report.md`, checks rates, Wilson intervals,
and category totals, and writes PNG/SVG files to `docs/assets/evaluations/`.
It recalculates figures from saved findings and does not rerun models.

The source dataset’s `EVALUATIONS.md` SHA-256 is recorded in `summary.json`
to identify the documentation snapshot. The complete paired data is
available from
[WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks).
