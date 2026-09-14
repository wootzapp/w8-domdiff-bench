# browser_task_035-container-image-tag-comparison-20260909T080532Z verifier comparison

Frozen rubric SHA-256: `003b90014d5fed37a6292b1c5ce248284dabbaa1bc85dec01fd756fba5b5bc02`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/20 (0.500) | False | 12 | 12 | 0 | 71,064 | 8,404 | 79,468 |
| DOM-model | 11/20 (0.550) | False | 18 | 18 | 0 | 92,346 | 15,943 | 108,289 |

DOM-model minus screenshot tokens: **+28,821 (+36.27%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the official Python image Tags page on Docker Hub and search for '3.12-slim' | 3 | 3 | 3 | 3 | 3 |
| Filter to only tag names that begin exactly with '3.12-slim' (exact-prefix match) | 3 | 3 | 3 | 2 | 2 |
| Identify the three most recently updated tags among the exact-prefix matches (or report limitations) | 8 | 4 | 8 | 2 | 3 |
| Report required displayed fields for each of the (up to) three selected tags (no guessing) | 4 | 2 | 2 | 1 | 1 |
| Respect task constraints (no sign-in; no pulling/running images) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
