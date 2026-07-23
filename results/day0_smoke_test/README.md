# Day 0 Smoke Test Results

Day 0 ran Microsoft's released Universal Verifier on exactly one frozen
CUAVerifierBench trajectory: `Adidas--11857213`.

Important files:

| Path | Purpose |
|---|---|
| `summary/execution_summary.md` | Human-readable summary |
| `reports/openai_verification_result.json` | Compact result |
| `reports/verify_report_openai.jsonl` | Official verifier report row |
| `scores/mmrubric_0.8-5-3.json` | Raw Universal Verifier score |
| `manifests/trajectory_validation.json` | Input validation |
| `logs/` | Execution logs |

The materialized trajectory, screenshots, and local dataset remain under
ignored `data/` and `outputs/` paths.
