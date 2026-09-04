# browser_task_049-economic-time-series-extraction-20260902T205455Z verifier comparison

Frozen rubric SHA-256: `de70c8663174c3bcec6737c1b7aeb1697301e430b254f08e61293b8d505e4e64`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/15 (1.000) | True | 14 | 14 | 0 | 72,724 | 5,806 | 78,530 |
| DOM-model | 14/15 (0.933) | False | 22 | 22 | 0 | 95,568 | 12,611 | 108,179 |

DOM-model minus screenshot tokens: **+29,649 (+37.75%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the correct FRED series page (UNRATE) and avoid sign-in/subscription actions | 3 | 3 | 3 | 3 | 3 |
| Record series metadata exactly as displayed | 4 | 4 | 4 | 4 | 3 |
| Record the three latest displayed observation months and values exactly as displayed | 6 | 0 | 0 | 6 | 6 |
| Stop after recording metadata and three latest observations | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
