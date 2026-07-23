# Microsoft Universal Verifier Execution

This repository contains a cleaned, GitHub-ready record of two completed
Universal Verifier executions.

| Stage | Purpose | Status | Output root |
|---|---|---|---|
| Day 0 | One-trajectory official-pipeline smoke test | Complete | `results/day0_smoke_test/` |
| Day 1 | Full 106-trajectory Universal Verifier execution | Complete | `results/day1_full_uv/` |

The full execution pipeline is documented in `pipeline.md`. The detailed
full-trajectory run notes are in `pipeline_day1_full_uv.md`.

## What Is Tracked

- experiment scripts and commands;
- OpenAI endpoint config templates without secrets;
- result summaries, reports, predictions, manifests, logs, and score JSONs;
- learning logs and pipeline documentation.

## What Stays Local Only

The dataset and heavy generated workspace remain on this machine for reference
but are ignored for GitHub:

```text
data/       # downloaded/materialized dataset, screenshots, action logs
outputs/    # original local execution workspace
repo/       # upstream Microsoft Fara checkout
.venv/      # local Python environment
.env        # local API key
```

Use `.env.example` as the template if you need to rerun locally. Do not commit
the real `.env` file.

## Layout

```text
results/day0_smoke_test/     # curated one-trajectory smoke-test results
results/day1_full_uv/        # curated 106-trajectory full-run results
scripts/                     # materialization, validation, run, and finalize helpers
commands/                    # recorded command history
config/                      # experiment registry and fixed run config
endpoint_configs/openai/     # secret-free OpenAI endpoint configs
```

## Result Entry Points

- `results/day0_smoke_test/summary/execution_summary.md`
- `results/day1_full_uv/summary/execution_summary.md`
- `results/day1_full_uv/predictions/process_outcome_results.jsonl`
- `results/day1_full_uv/reports/full_report.jsonl`
