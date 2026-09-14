# browser_task_074-occupational-profile-analysis-20260909T090500Z verifier comparison

Frozen rubric SHA-256: `dd3422752f1fa816da9a0f682de0c82e2ba8cdb298e19108b5d9486950da0350`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/22 (0.455) | False | 14 | 14 | 0 | 90,408 | 9,591 | 99,999 |
| DOM-model | 11/22 (0.500) | False | 21 | 21 | 0 | 113,883 | 16,916 | 130,799 |

DOM-model minus screenshot tokens: **+30,800 (+30.80%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use correct O*NET Summary Report profile (15-1252.00 only) | 3 | 3 | 3 | 3 | 3 |
| Record occupation title and code | 2 | 2 | 2 | 2 | 2 |
| Record Bright Outlook status | 2 | 2 | 2 | 2 | 2 |
| Record Job Zone title | 2 | 2 | 2 | 2 | 2 |
| Record annual median wage (national Wages & Employment Trends value) | 3 | 0 | 0 | 0 | 0 |
| Record current employment (national Wages & Employment Trends value) | 3 | 0 | 0 | 0 | 0 |
| Record projected-growth wording and rate | 3 | 0 | 0 | 0 | 0 |
| Record projected job openings | 2 | 0 | 0 | 0 | 0 |
| Respect task constraints and stopping condition | 2 | 1 | 2 | 1 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
