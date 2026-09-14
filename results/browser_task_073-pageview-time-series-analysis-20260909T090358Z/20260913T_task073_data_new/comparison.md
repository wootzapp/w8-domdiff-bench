# browser_task_073-pageview-time-series-analysis-20260909T090358Z verifier comparison

Frozen rubric SHA-256: `d4a151184f452268c309515f8df93743958ec6050655eb59d4badc4a9368eb4f`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 4/15 (0.267) | False | 18 | 18 | 0 | 124,998 | 11,569 | 136,567 |
| DOM-model | 5.5/15 (0.367) | False | 21 | 21 | 0 | 120,150 | 15,840 | 135,990 |

DOM-model minus screenshot tokens: **-577 (-0.42%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Report daily date–viewcount pairs from the supplied API response (or report missing/unavailable data) | 6 | 0 | 6 | 2 | 2.5 |
| Compute and show arithmetic for the total over the reported days | 3 | 3 | 3 | 1 | 1 |
| Identify highest-view date and show maximum-selection logic over the reported days | 3 | 3 | 3 | 1 | 1.5 |
| Adhere to task constraints (source fidelity, timestamp conversion, no re-aggregation) | 3 | 0 | 3 | 0 | 0.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
