# browser_task_056-biomedical-literature-filtering-20260909T082457Z verifier comparison

Frozen rubric SHA-256: `83c4e2c84cb3b2f4835b4a922e0786ea608b99630dde345ce70b66463ede74ef`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 20/20 (1.000) | False | 12 | 12 | 0 | 75,006 | 7,513 | 82,519 |
| DOM-model | 14/20 (0.700) | False | 16 | 16 | 0 | 77,321 | 11,682 | 89,003 |

DOM-model minus screenshot tokens: **+6,484 (+7.86%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Run PubMed Title-field search for the exact phrase | 3 | 3 | 3 | 3 | 3 |
| Apply required PubMed filters | 4 | 4 | 4 | 4 | 0 |
| Sort results by Most Recent | 2 | 2 | 2 | 2 | 0 |
| Record first result with all required fields | 3 | 3 | 3 | 3 | 3 |
| Record second result with all required fields | 3 | 3 | 3 | 3 | 3 |
| Record third result with all required fields | 3 | 3 | 3 | 3 | 3 |
| Stop after capturing the first three results (stopping condition) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
