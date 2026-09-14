# browser_task_034-dependency-inspection-20260909T080508Z verifier comparison

Frozen rubric SHA-256: `bff329749131a4a0d59fe780a228d6d7277fea87b8202c6904f5168b64267bf6`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 19/20 (0.950) | False | 12 | 12 | 0 | 71,928 | 9,212 | 81,140 |
| DOM-model | 20/20 (1.000) | True | 22 | 22 | 0 | 97,095 | 13,428 | 110,523 |

DOM-model minus screenshot tokens: **+29,383 (+36.21%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access RubyGems rails gem page (without sign-in) | 2 | 2 | 2 | 2 | 2 |
| Respect constraints: no sign-in, no download/install | 1 | 1 | 1 | 1 | 1 |
| Identify the latest displayed Rails version | 3 | 3 | 3 | 3 | 3 |
| Record latest version metadata (version, release date, required Ruby, license) | 4 | 0 | 0 | 3 | 4 |
| Runtime dependency #1 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Runtime dependency #2 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Runtime dependency #3 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Runtime dependency #4 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Runtime dependency #5 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
