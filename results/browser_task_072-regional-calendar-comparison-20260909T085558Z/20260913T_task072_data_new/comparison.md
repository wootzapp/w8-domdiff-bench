# browser_task_072-regional-calendar-comparison-20260909T085558Z verifier comparison

Frozen rubric SHA-256: `231a2296aa6a12b6ac225c3ca067a8b4ec03f032f694482c3b3796132483bfa7`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/12 (1.000) | True | 67 | 67 | 0 | 310,923 | 16,919 | 327,842 |
| DOM-model | 2.5/12 (0.208) | False | 79 | 79 | 0 | 302,482 | 22,354 | 324,836 |

DOM-model minus screenshot tokens: **-3,006 (-0.92%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the official GOV.UK bank-holidays JSON response at the supplied URL (or clearly report access failure) | 3 | 3 | 3 | 3 | 1.5 |
| Scotland 2026 — report '2nd January' date and bunting | 2 | 2 | 2 | 2 | 0 |
| Scotland 2026 — report 'Summer bank holiday' date and bunting | 2 | 2 | 2 | 2 | 0 |
| Scotland 2026 — report 'St Andrew’s Day' date and bunting | 2 | 2 | 2 | 2 | 0 |
| England and Wales 2026 — report 'Summer bank holiday' date | 2 | 2 | 2 | 2 | 0 |
| Stopping condition adhered to (only required events recorded) | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
