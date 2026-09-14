# browser_task_087-river-monitoring-20260914T091633Z verifier comparison

Frozen rubric SHA-256: `d6936e2ce99610f826aa5b76541407e58617a7aeee59041b81839605a3a8d94d`  
Denominator: `13`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/13 (0.462) | False | 22 | 22 | 0 | 135,018 | 13,785 | 148,803 |
| DOM-model | 8.5/13 (0.654) | False | 28 | 28 | 0 | 147,986 | 18,247 | 166,233 |

DOM-model minus screenshot tokens: **+17,430 (+11.71%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the correct USGS monitoring location (USGS-01646500) and Continuous Data section | 3 | 3 | 3 | 3 | 3 |
| Report station name | 2 | 1 | 1 | 2 | 2 |
| Latest Continuous Data observation: Discharge (cubic feet per second) | 3 | 0 | 0 | 0 | 2.5 |
| Latest Continuous Data observation: Gage height (feet) | 3 | 0 | 0 | 0 | 0 |
| Display both series if not initially shown; preserve provisional labels and stop after required reporting | 2 | 2 | 2 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
