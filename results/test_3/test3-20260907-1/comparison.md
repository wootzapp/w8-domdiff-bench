# browser_task_043-vulnerability-record-inspection-20260905T114043Z verifier comparison

Frozen rubric SHA-256: `023a491c76d640061e4a584219b3f5365355dbca7e98fbe664cb3610550a8ff6`  
Denominator: `25`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17.5/25 (0.700) | False | 12 | 12 | 0 | 80,155 | 10,672 | 90,827 |
| DOM-model | 17/25 (0.680) | False | 27 | 27 | 0 | 140,539 | 22,006 | 162,545 |

DOM-model minus screenshot tokens: **+71,718 (+78.96%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use CVE.org CNA record (CVE-2021-44228) as the source | 3 | 3 | 3 | 3 | 3 |
| Report CVE status | 2 | 2 | 1 | 2 | 2 |
| Report publication date | 2 | 2 | 2 | 2 | 2 |
| Report CNA name | 2 | 2 | 2 | 2 | 2 |
| Report vendor | 2 | 2 | 2 | 0 | 0 |
| Report product | 2 | 2 | 2 | 1.5 | 1 |
| Quote the affected-version statement exactly as written in the Description | 5 | 5 | 0 | 5 | 5 |
| Provide the first reference URL displayed in the CNA record | 3 | 3 | 3 | 0 | 0 |
| Respect constraints and stopping condition | 4 | 4 | 4 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
