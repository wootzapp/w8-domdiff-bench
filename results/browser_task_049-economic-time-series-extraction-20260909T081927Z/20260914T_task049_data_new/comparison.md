# browser_task_049-economic-time-series-extraction-20260909T081927Z verifier comparison

Frozen rubric SHA-256: `e7d920165717bb854ffc6669291fce77cdb6a22a09c2c21c07c0bf59a111708c`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/15 (0.667) | False | 16 | 16 | 0 | 93,347 | 9,662 | 103,009 |
| DOM-model | 11/15 (0.733) | False | 33 | 33 | 0 | 160,734 | 20,940 | 181,674 |

DOM-model minus screenshot tokens: **+78,665 (+76.37%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the FRED UNRATE series page (or clearly report access blocking) | 2 | 2 | 2 | 2 | 2 |
| Use the correct series content (UNRATE) rather than a different unemployment series | 2 | 2 | 2 | 2 | 2 |
| Record series metadata exactly as displayed (units, frequency, seasonal adjustment) | 4 | 2 | 2 | 3 | 4 |
| Record the three latest displayed observation months and values exactly | 5 | 0 | 1 | 2 | 2 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
