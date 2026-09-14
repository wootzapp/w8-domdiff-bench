# browser_task_048-corporate-filing-filtering-20260909T081902Z verifier comparison

Frozen rubric SHA-256: `c8197d17535a38a70b94467043e3b15de71f9f6afc6ce6cacf16ebc253dfbecb`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 5/20 (0.250) | False | 12 | 12 | 0 | 73,341 | 8,610 | 81,951 |
| DOM-model | 6/20 (0.300) | False | 14 | 14 | 0 | 74,426 | 10,958 | 85,384 |

DOM-model minus screenshot tokens: **+3,433 (+4.19%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate to Tesco PLC Companies House filing history (correct company/page) | 3 | 3 | 3 | 3 | 3 |
| Apply the 'Accounts' category filter via the page interface | 4 | 4 | 4 | 0 | 1 |
| Record newest (most recent) account filing #1 details | 3 | 0 | 3 | 0 | 0 |
| Record newest account filing #2 details | 3 | 0 | 3 | 0 | 0 |
| Record newest account filing #3 details | 3 | 0 | 3 | 0 | 0 |
| Respect constraints and stopping condition | 4 | 4 | 4 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
