# browser_task_020-github-code-search-20260909T074624Z verifier comparison

Frozen rubric SHA-256: `5cc681d5bdaf6c0792b0062db6a687c29b6f9006c30dbbf35a077eac02df6060`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/12 (1.000) | False | 21 | 21 | 0 | 115,308 | 10,721 | 126,029 |
| DOM-model | 5/12 (0.417) | False | 37 | 37 | 0 | 220,862 | 20,364 | 241,226 |

DOM-model minus screenshot tokens: **+115,197 (+91.41%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Attempt repository-scoped code search (fastapi/fastapi) for the Depends definition | 2 | 2 | 2 | 2 | 2 |
| Correctly identify the true definition location (not just a usage/import) of Depends | 2 | 2 | 2 | 2 | 2 |
| Report exact file path and line number containing the Depends definition | 4 | 4 | 4 | 4 | 0 |
| Provide definition context (declaration header / surrounding symbol) as confirmation | 2 | 2 | 2 | 2 | 0 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
