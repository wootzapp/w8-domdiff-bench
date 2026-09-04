# browser_task_035-container-image-tag-comparison-20260902T193751Z verifier comparison

Frozen rubric SHA-256: `cb2de57303a92b029886abe9967220c909add7f383169cd0ff1f8d4beedaafe0`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 11/18 (0.611) | False | 13 | 13 | 0 | 79,600 | 9,262 | 88,862 |
| DOM-model | 8.5/18 (0.472) | False | 18 | 18 | 0 | 101,827 | 14,637 | 116,464 |

DOM-model minus screenshot tokens: **+27,602 (+31.06%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the official Python image Docker Hub Tags page and search for 3.12-slim | 3 | 3 | 3 | 3 | 3 |
| Identify up to three most recently updated tags whose names begin exactly with 3.12-slim | 5 | 3 | 5 | 2 | 1 |
| Report displayed update date/time for each selected tag (or state unavailable) | 3 | 3 | 3 | 0.5 | 1.5 |
| Report displayed Linux/amd64 image size for each selected tag (or 'unavailable') | 4 | 4 | 4 | 2.5 | 1.5 |
| Respect stated constraints (no sign-in; no pull/run; exclude non-prefix matches; stop after three) | 3 | 3 | 3 | 3 | 1.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
