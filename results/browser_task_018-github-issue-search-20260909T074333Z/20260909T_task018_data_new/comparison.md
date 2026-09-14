# browser_task_018-github-issue-search-20260909T074333Z verifier comparison

Frozen rubric SHA-256: `1070898bbbc7964a59520ec21c339408ad17d6faca93bcb2306f1ef43249e9a0`  
Denominator: `11`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10.5/11 (0.955) | True | 16 | 16 | 0 | 96,379 | 9,434 | 105,813 |
| DOM-model | 11/11 (1.000) | True | 18 | 18 | 0 | 109,237 | 10,460 | 119,697 |

DOM-model minus screenshot tokens: **+13,884 (+13.12%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access GitHub issues for huggingface/transformers and verify the date basis for the 30-day window | 1 | 1 | 1 | 1 | 1 |
| Apply exact GitHub issue search filters (open + label: bug + created in last 30 days) for huggingface/transformers | 4 | 4 | 4 | 4 | 4 |
| Report total count of matching issues | 2 | 2 | 0 | 2 | 2 |
| Provide the three newest matching issue records (issue number + title) | 3 | 3 | 0 | 2.5 | 3 |
| Comply with constraints (no sign-in; no issue interactions; stop after verification) | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
