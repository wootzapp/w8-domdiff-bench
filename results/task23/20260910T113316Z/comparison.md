# viewport-modern-23-requests-pull-request-inspection-20260829T084451Z verifier comparison

Frozen rubric SHA-256: `dd52e47e7db0b8a9ebe57ae41a2401c6c5ac3dec04f4f30d048b826660a2d735`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 4/20 (0.200) | False | 18 | 18 | 0 | 116,116 | 13,577 | 129,693 |
| DOM-model | 5/20 (0.250) | False | 22 | 22 | 0 | 140,158 | 18,676 | 158,834 |

DOM-model minus screenshot tokens: **+29,141 (+22.47%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Filter and sort pull request list correctly (open, non-draft, most recently updated) | 3 | 2 | 2 | 2 | 2.5 |
| Inspect and report PR #1 details and file-change summary (as displayed by GitHub) | 4 | 0 | 1 | 0 | 1.5 |
| Inspect and report PR #2 details and file-change summary (as displayed by GitHub) | 4 | 0 | 0 | 0 | 0 |
| Inspect and report PR #3 details and file-change summary (as displayed by GitHub) | 4 | 0 | 0 | 0 | 0 |
| Rank the three PRs by changed-file count | 2 | 0 | 0 | 0 | 0 |
| Respect constraints and stopping condition (no sign-in, no PR actions; stop after verifying three summaries) | 3 | 2 | 1 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
