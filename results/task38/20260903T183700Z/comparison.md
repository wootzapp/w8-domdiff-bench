# browser_task_043-vulnerability-record-inspection-20260902T204516Z verifier comparison

Frozen rubric SHA-256: `023a491c76d640061e4a584219b3f5365355dbca7e98fbe664cb3610550a8ff6`  
Denominator: `25`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 22.5/25 (0.900) | False | 21 | 21 | 0 | 128,235 | 13,595 | 141,830 |
| DOM-model | 23/25 (0.920) | True | 43 | 43 | 0 | 213,281 | 30,769 | 244,050 |

DOM-model minus screenshot tokens: **+102,220 (+72.07%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use CVE.org CNA record (CVE-2021-44228) as the source | 3 | 3 | 3 | 3 | 3 |
| Report CVE status | 2 | 2 | 2 | 2 | 2 |
| Report publication date | 2 | 2 | 2 | 2 | 2 |
| Report CNA name | 2 | 2 | 2 | 2 | 2 |
| Report vendor | 2 | 2 | 2 | 0 | 0.5 |
| Report product | 2 | 2 | 2 | 1.5 | 1.5 |
| Quote the affected-version statement exactly as written in the Description | 5 | 5 | 5 | 5 | 5 |
| Provide the first reference URL displayed in the CNA record | 3 | 3 | 3 | 3 | 3 |
| Respect constraints and stopping condition | 4 | 4 | 4 | 4 | 4 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
