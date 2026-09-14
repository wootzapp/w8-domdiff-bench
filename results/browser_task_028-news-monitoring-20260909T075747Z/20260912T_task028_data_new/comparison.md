# browser_task_028-news-monitoring-20260909T075747Z verifier comparison

Frozen rubric SHA-256: `ecbe8f31750b2f052bb63998de33a2ea569f9d4c48902231f80cc943eac91636`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 4/18 (0.222) | False | 14 | 14 | 0 | 78,526 | 8,345 | 86,871 |
| DOM-model | 4/18 (0.222) | False | 31 | 31 | 0 | 117,611 | 20,861 | 138,472 |

DOM-model minus screenshot tokens: **+51,601 (+59.40%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access BBC Technology section (bbc.com/technology) without signing in | 3 | 3 | 3 | 3 | 3 |
| Record the five most recent BBC Technology headlines | 5 | 0 | 0 | 0 | 0 |
| Record publication timestamps exactly as displayed for each of the five headlines | 6 | 0 | 0 | 0 | 0 |
| Stop after recording five newest headlines and timestamps | 2 | 0 | 0 | 0 | 0 |
| Respect constraints: no sign-in and no ad interaction | 2 | 2 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
