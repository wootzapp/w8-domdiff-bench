# browser_task_072-regional-calendar-comparison-20260914T085604Z verifier comparison

Frozen rubric SHA-256: `231a2296aa6a12b6ac225c3ca067a8b4ec03f032f694482c3b3796132483bfa7`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/12 (1.000) | True | 12 | 12 | 0 | 74,654 | 7,635 | 82,289 |
| DOM-model | 12/12 (1.000) | True | 15 | 15 | 0 | 88,698 | 10,065 | 98,763 |

DOM-model minus screenshot tokens: **+16,474 (+20.02%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the official GOV.UK bank-holidays JSON response at the supplied URL (or clearly report access failure) | 3 | 3 | 3 | 3 | 3 |
| Scotland 2026 — report '2nd January' date and bunting | 2 | 2 | 2 | 2 | 2 |
| Scotland 2026 — report 'Summer bank holiday' date and bunting | 2 | 2 | 2 | 2 | 2 |
| Scotland 2026 — report 'St Andrew’s Day' date and bunting | 2 | 2 | 2 | 2 | 2 |
| England and Wales 2026 — report 'Summer bank holiday' date | 2 | 2 | 2 | 2 | 2 |
| Stopping condition adhered to (only required events recorded) | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
