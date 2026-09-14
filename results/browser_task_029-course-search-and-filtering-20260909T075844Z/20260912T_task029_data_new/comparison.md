# browser_task_029-course-search-and-filtering-20260909T075844Z verifier comparison

Frozen rubric SHA-256: `3daffb68fd3e0e8bf3aed4b5b7a36a638215f13377b5964ac7a3093aad4e3094`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17/18 (0.944) | False | 41 | 41 | 0 | 238,915 | 19,414 | 258,329 |
| DOM-model | 15/18 (0.833) | False | 46 | 46 | 0 | 319,661 | 24,988 | 344,649 |

DOM-model minus screenshot tokens: **+86,320 (+33.41%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Coursera Data Science browse/search results without signing in | 1 | 1 | 1 | 1 | 1 |
| Apply all requested Coursera filters (Data Science subject, Beginner level, English language, 1–3 months duration) or document unavoidable UI limitations | 4 | 4 | 4 | 4 | 4 |
| Identify the three highest-rated matching courses (or report fewer if not available) | 4 | 2 | 1 | 3 | 1 |
| Report required fields for Course #1 (title, rating, enrollment count if displayed) | 2 | 0 | 0 | 2 | 2 |
| Report required fields for Course #2 (title, rating, enrollment count if displayed) | 2 | 0 | 0 | 2 | 2 |
| Report required fields for Course #3 (title, rating, enrollment count if displayed) | 2 | 0 | 0 | 2 | 2 |
| Comply with constraints (no sign-in; no enroll/purchase/start trial; stop after verification) | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
