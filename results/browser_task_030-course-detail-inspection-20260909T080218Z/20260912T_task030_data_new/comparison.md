# browser_task_030-course-detail-inspection-20260909T080218Z verifier comparison

Frozen rubric SHA-256: `d72d9b5be1488b333321130e761a98f676847890a290a6b5fe324b932028a2e6`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15.5/16 (0.969) | False | 12 | 12 | 0 | 72,207 | 8,102 | 80,309 |
| DOM-model | 15/16 (0.938) | False | 16 | 16 | 0 | 85,692 | 11,927 | 97,619 |

DOM-model minus screenshot tokens: **+17,310 (+21.55%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the specified Coursera course page without signing in/enrolling (or record unavailability state) | 4 | 4 | 3 | 4 | 3 |
| Record instructor name(s) | 2 | 2 | 2 | 2 | 2 |
| Record institution/partner | 2 | 2 | 2 | 2 | 2 |
| Record number of modules/weeks shown in the syllabus | 3 | 3 | 3 | 2.5 | 3 |
| Determine whether a free audit option is available | 3 | 3 | 3 | 3 | 3 |
| Stop after recording overview and syllabus details (respect stopping condition and constraints) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
