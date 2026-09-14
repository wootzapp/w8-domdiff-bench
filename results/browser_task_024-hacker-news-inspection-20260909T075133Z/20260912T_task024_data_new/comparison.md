# browser_task_024-hacker-news-inspection-20260909T075133Z verifier comparison

Frozen rubric SHA-256: `c3c7c4d619065b4c6191ec5934aa1368727ebecdba8fd35a44bb32f42ce4e196`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/15 (1.000) | True | 12 | 12 | 0 | 66,973 | 7,307 | 74,280 |
| DOM-model | 7/15 (0.467) | False | 16 | 16 | 0 | 109,962 | 9,239 | 119,201 |

DOM-model minus screenshot tokens: **+44,921 (+60.48%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Hacker News front page and view story list | 2 | 2 | 2 | 2 | 2 |
| Inspect exactly the first 30 front-page stories (or clearly report inability) | 4 | 1 | 1 | 4 | 1 |
| Identify GitHub-linked stories among the 30 (count + titles) | 7 | 0 | 1 | 7 | 2 |
| Respect constraints (no sign-in and no interactive actions) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
