# browser_task_053-book-edition-resolution-20260905T114200Z verifier comparison

Frozen rubric SHA-256: `df2cd914f5daf2c129e0016af85936e64a8eb2834b1efb4856281c21f710a629`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/15 (0.800) | False | 12 | 12 | 0 | 72,083 | 8,362 | 80,445 |
| DOM-model | 15/15 (1.000) | False | 13 | 13 | 0 | 78,212 | 9,632 | 87,844 |

DOM-model minus screenshot tokens: **+7,399 (+9.20%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Open Library edition via ISBN-13 (9780141439518) | 3 | 2 | 3 | 2 | 3 |
| Record resolved edition title | 1 | 1 | 1 | 1 | 1 |
| Record displayed author | 1 | 1 | 1 | 1 | 1 |
| Record displayed Publish Date | 2 | 2 | 2 | 2 | 2 |
| Record publisher | 1 | 1 | 1 | 1 | 1 |
| Record language | 1 | 1 | 1 | 1 | 1 |
| Record page count exactly as displayed | 2 | 2 | 2 | 2 | 2 |
| Record ISBN-13 exactly as displayed | 2 | 2 | 2 | 0 | 2 |
| Follow constraints (no sign-in/borrow/waitlist; stop after fields captured) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
