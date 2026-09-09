# browser_task_030-course-detail-inspection-20260902T193220Z verifier comparison

Frozen rubric SHA-256: `f3c854c8733c3846664c89edb1f9c7c4522dfd2ebf0fd60de97567a062ae21e4`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/15 (0.533) | False | 10 | 10 | 0 | 62,994 | 7,679 | 70,673 |
| DOM-model | 14.5/15 (0.967) | False | 16 | 16 | 0 | 77,116 | 9,891 | 87,007 |

DOM-model minus screenshot tokens: **+16,334 (+23.11%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Attempt to access the specified Coursera course page without signing in | 3 | 3 | 3 | 3 | 3 |
| Record instructor name(s) | 2 | 2 | 2 | 0 | 2 |
| Record institution/partner offering the course | 2 | 2 | 2 | 0 | 2 |
| Record number of modules/weeks shown in the syllabus | 3 | 3 | 3 | 0 | 2.5 |
| Determine whether a free audit option is available | 3 | 3 | 3 | 3 | 3 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |
| Handle unavailability appropriately (if applicable) | 3 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
