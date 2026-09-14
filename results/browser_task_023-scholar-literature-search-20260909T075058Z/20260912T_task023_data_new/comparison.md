# browser_task_023-scholar-literature-search-20260909T075058Z verifier comparison

Frozen rubric SHA-256: `be2cf947b51ee43a5254de444eeb65eb7d175fbcc7ea08f53ad322637e49fc4b`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17/17 (1.000) | False | 14 | 14 | 0 | 77,630 | 7,407 | 85,037 |
| DOM-model | 17/17 (1.000) | False | 15 | 15 | 0 | 73,728 | 8,164 | 81,892 |

DOM-model minus screenshot tokens: **-3,145 (-3.70%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Google Scholar without signing in and handle access blocks appropriately | 3 | 3 | 3 | 3 | 3 |
| Record the original Google Scholar citation count for 'Attention Is All You Need' | 3 | 3 | 3 | 3 | 3 |
| Open 'Cited by' results and apply date filter to 2024 onward | 3 | 3 | 3 | 3 | 3 |
| Most-cited citing paper (2024+): title, authors, citation count | 3 | 3 | 3 | 3 | 3 |
| Second most-cited citing paper (2024+): title, authors, citation count | 2 | 2 | 2 | 2 | 2 |
| Third most-cited citing paper (2024+): title, authors, citation count | 2 | 2 | 2 | 2 | 2 |
| Respect stopping condition (no extra records beyond what is requested) | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
