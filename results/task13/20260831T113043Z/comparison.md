# viewport-modern-13-slack-workspace-problem-search-20260829T075522Z verifier comparison

Frozen rubric SHA-256: `780bec69d1b93a66199c607a66f5d260df1a9098a7430da2bc4716a2bcee005c`  
Denominator: `40`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/40 (0.400) | False | 51 | 51 | 0 | 307,383 | 23,857 | 331,240 |
| DOM-model | 15/40 (0.375) | False | 57 | 57 | 0 | 408,954 | 25,880 | 434,834 |

DOM-model minus screenshot tokens: **+103,594 (+31.27%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Perform 4 separate global Slack searches (error, issue, failed, help) | 4 | 2 | 2 | 2 | 1 |
| Inspect up to 5 most recent substantive results per term (with deduplication basis) | 6 | 3 | 2 | 3 | 2 |
| Deduplicate messages appearing in multiple searches | 4 | 0 | 0 | 0 | 0 |
| Consult visible thread replies when relevant | 4 | 4 | 2 | 3 | 3 |
| Produce required output table with all specified columns | 10 | 0 | 0 | 0 | 0 |
| Resolution classification follows instruction (explicit only; no inference from silence) | 6 | 3 | 3 | 2 | 3 |
| Do not modify Slack content (no send/edit/delete/react) | 6 | 6 | 6 | 6 | 6 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
