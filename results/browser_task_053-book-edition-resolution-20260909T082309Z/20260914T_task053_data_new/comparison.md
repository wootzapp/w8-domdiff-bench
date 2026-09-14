# browser_task_053-book-edition-resolution-20260909T082309Z verifier comparison

Frozen rubric SHA-256: `e15710db7702bbbb56d6f2791c1fbc501b338de2f93ebe1f777dd4dc0b9e8735`  
Denominator: `13`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 9/13 (0.692) | False | 12 | 12 | 0 | 69,454 | 7,915 | 77,369 |
| DOM-model | 13/13 (1.000) | True | 27 | 27 | 0 | 115,127 | 14,610 | 129,737 |

DOM-model minus screenshot tokens: **+52,368 (+67.69%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Resolve the supplied ISBN-13 on Open Library to the correct edition | 3 | 3 | 3 | 1 | 3 |
| Record the resolved edition's title | 1 | 1 | 1 | 1 | 1 |
| Record the resolved edition's displayed author | 1 | 1 | 1 | 1 | 1 |
| Record the resolved edition's Publish Date (displayed) | 2 | 2 | 2 | 2 | 2 |
| Record the resolved edition's publisher | 1 | 1 | 1 | 1 | 1 |
| Record the resolved edition's language | 1 | 1 | 1 | 1 | 1 |
| Record the resolved edition's page count (exactly as displayed) | 2 | 2 | 0 | 2 | 2 |
| Record the resolved edition's ISBN-13 (exactly as displayed) | 2 | 2 | 2 | 0 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
