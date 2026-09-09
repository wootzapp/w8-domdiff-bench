# browser_task_015-reddit-community-comparison-20260909T074040Z verifier comparison

Frozen rubric SHA-256: `002aa1d1eda9e7069a08c8bbb68a6d7c9e6e1ecf1dd4fd815d396f69641e6158`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/15 (1.000) | False | 10 | 10 | 0 | 56,220 | 6,521 | 62,741 |
| DOM-model | 15/15 (1.000) | False | 19 | 19 | 0 | 71,082 | 11,986 | 83,068 |

DOM-model minus screenshot tokens: **+20,327 (+32.40%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Record subscriber count for r/Python | 3 | 3 | 3 | 3 | 3 |
| Record subscriber count for r/learnpython | 3 | 3 | 3 | 3 | 3 |
| Record subscriber count for r/django | 3 | 3 | 3 | 3 | 3 |
| Rank the three communities from largest to smallest and present as a table | 4 | 4 | 4 | 4 | 4 |
| Comply with constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
