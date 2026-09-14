# browser_task_022-stackoverflow-search-20260909T074929Z verifier comparison

Frozen rubric SHA-256: `686ac06cb94ab6ea86b0b6d34f7a460778f78a64d2bf8d39a666c8ee5bc3ceee`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 7/16 (0.438) | False | 23 | 23 | 0 | 137,261 | 13,754 | 151,015 |
| DOM-model | 8/16 (0.500) | False | 33 | 33 | 0 | 197,142 | 21,832 | 218,974 |

DOM-model minus screenshot tokens: **+67,959 (+45.00%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Stack Overflow tagged search for python+pandas (no sign-in) | 3 | 3 | 3 | 3 | 3 |
| Apply required filters and sort order | 5 | 2 | 3 | 2 | 3 |
| Report top 3 matching questions (title, score, view count) | 6 | 0 | 0 | 0 | 0 |
| Respect interaction constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
