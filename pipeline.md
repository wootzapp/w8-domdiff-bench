# Universal Verifier Execution Pipeline

This repository contains two completed execution stages:

```text
Day 0: one-trajectory smoke test
Day 1: full 106-trajectory Universal Verifier run
```

The heavy dataset folders are kept locally under `data/` and are ignored for
GitHub. The curated result artifacts are under `results/`.

## Day 0 - Smoke Test

Day 0 proved that Microsoft's released Universal Verifier can score one frozen
CUAVerifierBench trajectory end to end.

```text
Frozen CUAVerifierBench trajectory
        ↓
Label-safe materialization
        ↓
Input and screenshot validation
        ↓
OpenAI judge preflight
        ↓
Official verify_trajectories.py
        ↓
One mmrubric score JSON
```

Key result files:

| File | Purpose |
|---|---|
| `results/day0_smoke_test/summary/execution_summary.md` | Human-readable smoke-test summary |
| `results/day0_smoke_test/reports/openai_verification_result.json` | Compact verifier result |
| `results/day0_smoke_test/reports/verify_report_openai.jsonl` | Official verifier report row |
| `results/day0_smoke_test/scores/mmrubric_0.8-5-3.json` | Raw rubric score JSON |
| `results/day0_smoke_test/manifests/trajectory_validation.json` | Input validation result |

The retained trajectory was `Adidas--11857213`.

## Day 1 - Full Universal Verifier Run

Day 1 ran Microsoft's released Universal Verifier over the complete frozen
CUAVerifierBench Browserbase split.

```text
microsoft/CUAVerifierBench
configuration: trajectories
split: fara7b_om2w_browserbase
rows: 106
        ↓
Label-safe materialization
        ↓
Full input validation
        ↓
3-task preflight
        ↓
Cache/resume check
        ↓
Fresh 10-task batch
        ↓
Fresh 93-task remainder
        ↓
106 final score artifacts
```

Key fixed settings:

| Setting | Value |
|---|---|
| Fara commit | `9f14b6e34094fe469a54a821e81e013a0739520d` |
| Main multimodal judge | `gpt-5.2` |
| Action/rubric judge | `o4-mini` |
| Rubric threshold | `0.8` |
| Max images per criterion | `5` |
| Worker processes | `1` |
| Top-level success | `outcome` |

Key result files:

| File | Purpose |
|---|---|
| `results/day1_full_uv/summary/execution_summary.md` | Human-readable run summary |
| `results/day1_full_uv/reports/full_report.jsonl` | Combined official verifier report for 106 tasks |
| `results/day1_full_uv/predictions/full_predictions.jsonl` | Consolidated prediction rows |
| `results/day1_full_uv/predictions/process_outcome_results.jsonl` | Process and outcome fields for every task |
| `results/day1_full_uv/scores/raw_scores/` | 106 per-task `mmrubric_0.8-5-3.json` files |
| `results/day1_full_uv/manifests/` | Dataset inventory, validation, and execution plan |
| `results/day1_full_uv/failures/` | Empty failure manifests showing no unresolved/input/infra failures |

Final coverage:

```text
Total dataset rows: 106
Valid inputs: 106
Successfully scored: 106
Input failures: 0
Infrastructure failures: 0
Unresolved failures: 0
```

## Local-Only Data

The local dataset and generated verifier workspace remain available on this
machine but are intentionally not prepared for GitHub:

```text
data/       # downloaded and materialized dataset, screenshots, action logs
outputs/    # original local run workspace
repo/       # upstream Microsoft Fara checkout
.venv/      # local Python environment
.env        # local OpenAI key
```

Those paths are ignored in `.gitignore`. The pushed repository should use
`results/` as the public artifact surface.
