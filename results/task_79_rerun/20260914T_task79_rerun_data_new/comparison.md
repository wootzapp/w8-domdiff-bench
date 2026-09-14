# browser_task_079-motor-race-result-analysis-20260914T090744Z verifier comparison

Frozen rubric SHA-256: `ebb9b172975df6aba5a6fdef96a7a5c172e30600f78d7899c84c675fda1f2ce7`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 20/20 (1.000) | True | 12 | 12 | 0 | 69,718 | 7,062 | 76,780 |
| DOM-model | 20/20 (1.000) | True | 36 | 36 | 0 | 116,043 | 18,918 | 134,961 |

DOM-model minus screenshot tokens: **+58,181 (+75.78%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the supplied Jolpica/Ergast JSON and correct array selection | 3 | 1 | 1 | 3 | 3 |
| Report race-level fields: raceName, date, circuitName | 3 | 3 | 2 | 3 | 3 |
| Report winner identity: driver and constructor | 3 | 3 | 2 | 3 | 3 |
| Report winner result summary: grid, laps, status | 3 | 3 | 2 | 3 | 3 |
| Report complete FastestLap object with required separation of subfields | 6 | 6 | 6 | 6 | 6 |
| Stopping condition met (no extra races/results beyond requested fields) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
