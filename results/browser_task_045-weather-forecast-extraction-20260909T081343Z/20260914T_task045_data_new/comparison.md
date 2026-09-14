# browser_task_045-weather-forecast-extraction-20260909T081343Z verifier comparison

Frozen rubric SHA-256: `3ef97ba5958cfe041448d9d42a54ac4ad18b27d24a7a7bfbf0b4e4d15ec878ee`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 20/20 (1.000) | True | 19 | 19 | 0 | 103,685 | 9,178 | 112,863 |
| DOM-model | 20/20 (1.000) | True | 26 | 26 | 0 | 119,997 | 13,468 | 133,465 |

DOM-model minus screenshot tokens: **+20,602 (+18.25%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use National Weather Service forecast page for Downtown Seattle (or report access blocker) | 3 | 3 | 3 | 3 | 3 |
| Identify the first displayed daytime forecast period and the immediately following nighttime period (or report ambiguity) | 4 | 0 | 4 | 4 | 4 |
| Report required fields for the daytime period (with unavailable handling) | 5 | 5 | 5 | 5 | 5 |
| Report required fields for the nighttime period (with unavailable handling) | 5 | 5 | 5 | 5 | 5 |
| Respect constraints and stopping condition (no guessing; one pair only; no permissions) | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
