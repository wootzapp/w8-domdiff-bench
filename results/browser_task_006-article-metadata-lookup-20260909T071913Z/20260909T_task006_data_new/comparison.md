# browser_task_006-article-metadata-lookup-20260909T071913Z verifier comparison

Frozen rubric SHA-256: `fd4b6e5db6e3942d425c795d4667da54104038119a8cacb7e2817b6505e2c2a1`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/12 (0.500) | False | 25 | 25 | 0 | 129,931 | 11,227 | 141,158 |
| DOM-model | 6/12 (0.500) | False | 35 | 35 | 0 | 174,515 | 18,782 | 193,297 |

DOM-model minus screenshot tokens: **+52,139 (+36.94%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Search Engine Land and attempt to locate the earliest available article using on-site methods | 4 | 4 | 4 | 4 | 4 |
| Identify the earliest available article and capture required metadata (or report inability to confirm) | 5 | 5 | 0 | 0 | 0 |
| Stop after finding the earliest available article (or after reaching a clear external blocker) | 1 | 1 | 1 | 0 | 0 |
| Respect constraints (no sign-in, no publishing/editing/commenting) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
