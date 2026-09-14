# browser_task_095-electricity-generation-mix-20260909T092120Z verifier comparison

Frozen rubric SHA-256: `7d5a5a273e604a77efabed606d75705b44c94f7111244a300e7c2a6f2108eb8c`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/12 (0.500) | False | 12 | 12 | 0 | 73,668 | 8,706 | 82,374 |
| DOM-model | 6.5/12 (0.542) | False | 22 | 22 | 0 | 91,358 | 15,349 | 106,707 |

DOM-model minus screenshot tokens: **+24,333 (+29.54%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Select the exact requested data record (from 2025-01-01T12:00Z to 2025-01-01T12:30Z) | 4 | 4 | 4 | 4 | 4 |
| Report every generationmix fuel-perc pair in returned order with exact precision | 4 | 2 | 4 | 1 | 1 |
| Identify all fuels with perc equal to zero (explicit zeros only) | 2 | 1 | 2 | 1 | 1 |
| Calculate the sum of all returned perc values for the selected record | 2 | 2 | 2 | 0 | 0.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
