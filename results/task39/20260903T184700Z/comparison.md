# browser_task_045-weather-forecast-extraction-20260902T204853Z verifier comparison

Frozen rubric SHA-256: `d094ae4e3765549cd9674953a8eb4f773258027e3a385b7a11f7073c64a3f849`  
Denominator: `14`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/14 (1.000) | True | 19 | 19 | 0 | 101,021 | 8,593 | 109,614 |
| DOM-model | 14/14 (1.000) | True | 36 | 36 | 0 | 151,940 | 19,581 | 171,521 |

DOM-model minus screenshot tokens: **+61,907 (+56.48%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the National Weather Service forecast page for Downtown Seattle and reach the forecast period list | 2 | 2 | 2 | 2 | 2 |
| Identify the first displayed daytime forecast period (as shown) | 2 | 2 | 2 | 2 | 2 |
| Identify the immediately following nighttime period | 2 | 2 | 2 | 2 | 2 |
| Report required fields for the daytime period | 3 | 3 | 3 | 3 | 3 |
| Report required fields for the nighttime period | 3 | 3 | 3 | 3 | 3 |
| Stopping condition and constraint compliance | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
