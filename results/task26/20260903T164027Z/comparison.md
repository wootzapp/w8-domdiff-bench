# browser_task_030-course-detail-inspection-20260902T193220Z verifier comparison

Frozen rubric SHA-256: `f3c854c8733c3846664c89edb1f9c7c4522dfd2ebf0fd60de97567a062ae21e4`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/15 (1.000) | True | 12 | 12 | 0 | 72,097 | 9,115 | 81,212 |
| DOM-model | 14/15 (0.933) | False | 19 | 19 | 0 | 87,475 | 13,133 | 100,608 |

DOM-model minus screenshot tokens: **+19,396 (+23.88%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Attempt to access the specified Coursera course page without signing in | 3 | 3 | 3 | 3 | 3 |
| Record instructor name(s) | 2 | 2 | 2 | 2 | 2 |
| Record institution/partner offering the course | 2 | 2 | 2 | 2 | 2 |
| Record number of modules/weeks shown in the syllabus | 3 | 3 | 3 | 3 | 2 |
| Determine whether a free audit option is available | 3 | 3 | 3 | 3 | 3 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |
| Handle unavailability appropriately (if applicable) | 3 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
