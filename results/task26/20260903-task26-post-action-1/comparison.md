# browser_task_030-course-detail-inspection-20260902T193220Z verifier comparison

Frozen rubric SHA-256: `f3c854c8733c3846664c89edb1f9c7c4522dfd2ebf0fd60de97567a062ae21e4`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 7.5/15 (0.500) | False | 10 | 10 | 0 | 62,417 | 7,955 | 70,372 |
| DOM-model | 7/15 (0.467) | False | 12 | 12 | 0 | 64,061 | 10,701 | 74,762 |

DOM-model minus screenshot tokens: **+4,390 (+6.24%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Attempt to access the specified Coursera course page without signing in | 3 | 3 | 3 | 3 | 3 |
| Record instructor name(s) | 2 | 2 | 2 | 0 | 0 |
| Record institution/partner offering the course | 2 | 2 | 2 | 0 | 1 |
| Record number of modules/weeks shown in the syllabus | 3 | 3 | 3 | 0 | 0 |
| Determine whether a free audit option is available | 3 | 3 | 3 | 2.5 | 2 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 1 |
| Handle unavailability appropriately (if applicable) | 3 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
