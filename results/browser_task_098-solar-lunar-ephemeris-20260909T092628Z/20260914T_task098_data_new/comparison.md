# browser_task_098-solar-lunar-ephemeris-20260909T092628Z verifier comparison

Frozen rubric SHA-256: `5ce36d2eff177b2341d7b5591e6c6cffe5385ac37029b1673c22a7e23f7d5b0e`  
Denominator: `23`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/23 (0.696) | False | 14 | 14 | 0 | 88,578 | 9,976 | 98,554 |
| DOM-model | 21/23 (0.913) | False | 20 | 20 | 0 | 98,799 | 17,728 | 116,527 |

DOM-model minus screenshot tokens: **+17,973 (+18.24%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Report geometry.coordinates (preserve order) | 2 | 2 | 1 | 2 | 2 |
| Report date fields: day, month, year, day_of_week | 3 | 3 | 3 | 3 | 3 |
| Report timezone fields: tz and isdst | 2 | 1 | 1 | 1 | 1 |
| Report lunar phase summary: curphase and fracillum | 2 | 2 | 2 | 2 | 2 |
| Report every field in closestphase | 3 | 3 | 3 | 3 | 3 |
| Report all Moon events (moondata) as phen/time pairs in returned order | 4 | 2 | 4 | 4 | 4 |
| Report all Sun events (sundata) as phen/time pairs in returned order | 4 | 0 | 0 | 0 | 4 |
| Adhere to task constraints and stopping condition | 3 | 1 | 1 | 1 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
