# viewport-modern-9-github-issue-search-20260829T075254Z verifier comparison

Frozen rubric SHA-256: `5bf60a7a9d78ee3c7683bff9207e0e075ed78cc479341647685794795b8587e5`  
Denominator: `10`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3/10 (0.300) | False | 12 | 12 | 0 | 71,871 | 8,610 | 80,481 |
| DOM-model | 9/10 (0.900) | True | 16 | 16 | 0 | 95,316 | 9,459 | 104,775 |

DOM-model minus screenshot tokens: **+24,294 (+30.19%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Apply exact GitHub issue search filters (repo, open, label:bug, created last 30 days) | 4 | 2 | 4 | 2 | 3 |
| Report total matching issue count | 2 | 1 | 0 | 0 | 2 |
| Provide the three newest matching issues (title + issue number) | 3 | 0 | 0 | 0 | 3 |
| Respect constraints and stopping condition | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
