# browser_task_084-exoplanet-discovery-record-20260914T091337Z verifier comparison

Frozen rubric SHA-256: `86405cadd21cd92c4b3494960aa9c7d29a6466ae18e9c2484e3a5850e1ba7be8`  
Denominator: `14`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/14 (0.929) | True | 12 | 12 | 0 | 75,684 | 7,942 | 83,626 |
| DOM-model | 14/14 (1.000) | True | 29 | 29 | 0 | 129,447 | 21,091 | 150,538 |

DOM-model minus screenshot tokens: **+66,912 (+80.01%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the NASA Exoplanet Archive overview page and locate the 'Architecture & Discovery Information' block | 1 | 1 | 1 | 1 | 1 |
| Use only the Architecture & Discovery Information block (single row) and stop after reporting the eight requested fields | 2 | 2 | 2 | 2 | 2 |
| Report stellar-host name | 1 | 1 | 1 | 1 | 1 |
| Report planet name | 1 | 1 | 1 | 1 | 1 |
| Report value under Orbital Separation | 2 | 0 | 0 | 2 | 2 |
| Report value under Planet Size | 2 | 2 | 0 | 1 | 2 |
| Report discovery method | 1 | 1 | 0 | 1 | 1 |
| Report discovery year | 1 | 1 | 1 | 1 | 1 |
| Report reference | 2 | 2 | 0 | 2 | 2 |
| Report disposition | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
