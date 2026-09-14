# browser_task_095-electricity-generation-mix-20260914T093058Z verifier comparison

Frozen rubric SHA-256: `7d5a5a273e604a77efabed606d75705b44c94f7111244a300e7c2a6f2108eb8c`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/12 (1.000) | True | 12 | 12 | 0 | 70,345 | 7,231 | 77,576 |
| DOM-model | 12/12 (1.000) | True | 17 | 17 | 0 | 76,672 | 11,852 | 88,524 |

DOM-model minus screenshot tokens: **+10,948 (+14.11%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Select the exact requested data record (from 2025-01-01T12:00Z to 2025-01-01T12:30Z) | 4 | 4 | 4 | 4 | 4 |
| Report every generationmix fuel-perc pair in returned order with exact precision | 4 | 4 | 4 | 4 | 4 |
| Identify all fuels with perc equal to zero (explicit zeros only) | 2 | 2 | 2 | 2 | 2 |
| Calculate the sum of all returned perc values for the selected record | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
