# viewport-modern-11-github-code-search-20260829T075405Z verifier comparison

Frozen rubric SHA-256: `bef270a2e06cda808d197e687ef621e0ea814ec5a4e48b637b68ddcc649a0b46`  
Denominator: `19`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/19 (0.316) | False | 14 | 14 | 0 | 82,387 | 10,501 | 92,888 |
| DOM-model | 19/19 (1.000) | False | 18 | 18 | 0 | 120,728 | 9,323 | 130,051 |

DOM-model minus screenshot tokens: **+37,163 (+40.01%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Attempt in-repository code search for the Depends definition in fastapi/fastapi | 4 | 4 | 4 | 4 | 4 |
| Identify the true definition location vs. a re-export/import (as supported by in-repo evidence) | 4 | 4 | 4 | 0 | 4 |
| Report file path and line number for the defining declaration when available | 4 | 4 | 4 | 0 | 4 |
| Provide definition context (declaration header / surrounding symbol) as confirmation | 3 | 3 | 3 | 0 | 3 |
| Stop after recording the requested search result details | 2 | 2 | 2 | 0 | 2 |
| Respect constraints (no sign-in, no file edits, no pull request) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
