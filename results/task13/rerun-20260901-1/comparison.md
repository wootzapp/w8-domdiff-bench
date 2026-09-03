# viewport-modern-13-slack-workspace-problem-search-20260829T075522Z verifier comparison

Frozen rubric SHA-256: `780bec69d1b93a66199c607a66f5d260df1a9098a7430da2bc4716a2bcee005c`  
Denominator: `40`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 18/40 (0.450) | False | 51 | 51 | 0 | 306,359 | 23,242 | 329,601 |
| DOM-model | 20/40 (0.500) | False | 59 | 59 | 0 | 425,741 | 27,867 | 453,608 |

DOM-model minus screenshot tokens: **+124,007 (+37.62%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Perform 4 separate global Slack searches (error, issue, failed, help) | 4 | 2 | 2 | 2 | 2 |
| Inspect up to 5 most recent substantive results per term (with deduplication basis) | 6 | 3 | 2 | 3 | 2 |
| Deduplicate messages appearing in multiple searches | 4 | 0 | 0 | 0 | 0 |
| Consult visible thread replies when relevant | 4 | 4 | 4 | 4 | 4 |
| Produce required output table with all specified columns | 10 | 0 | 0 | 0 | 0 |
| Resolution classification follows instruction (explicit only; no inference from silence) | 6 | 6 | 6 | 3 | 6 |
| Do not modify Slack content (no send/edit/delete/react) | 6 | 6 | 6 | 6 | 6 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
