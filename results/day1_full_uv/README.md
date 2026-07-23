# Day 1 Full Universal Verifier Results

Day 1 ran Microsoft's released Universal Verifier over all 106 frozen
CUAVerifierBench Browserbase trajectories.

Important files:

| Path | Purpose |
|---|---|
| `summary/execution_summary.md` | Human-readable run summary |
| `reports/full_report.jsonl` | Combined official verifier report |
| `predictions/full_predictions.jsonl` | Consolidated task predictions |
| `predictions/process_outcome_results.jsonl` | Per-task process/outcome fields |
| `scores/raw_scores/<task_id>/mmrubric_0.8-5-3.json` | Raw per-task rubric score |
| `manifests/` | Corpus inventory, validation, and execution plan |
| `failures/` | Failure/retry manifests |
| `cache/cached_runs.jsonl` | Cache-check rows |
| `environment/` | Reproducibility snapshot |
| `logs/` | Execution logs |

Final coverage:

```text
Total trajectories: 106
Successfully scored: 106
Input failures: 0
Infrastructure failures: 0
Unresolved failures: 0
```

The original local materialized dataset remains under ignored `data/`.
