# browser_task_075-collectible-card-rules-20260914T090059Z verifier comparison

Frozen rubric SHA-256: `6f14affeb38c269013e39e45b0490af6aae0f1273b38089a71952b4518441c09`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/17 (0.941) | True | 12 | 12 | 0 | 70,930 | 7,533 | 78,463 |
| DOM-model | 17/17 (1.000) | True | 23 | 23 | 0 | 117,599 | 11,931 | 129,530 |

DOM-model minus screenshot tokens: **+51,067 (+65.08%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the exact-card Scryfall API response at the provided URL | 3 | 3 | 3 | 2 | 3 |
| Record card identity fields: name, mana_cost, type_line | 3 | 3 | 3 | 3 | 3 |
| Record complete oracle_text | 3 | 3 | 1 | 3 | 3 |
| Record reserved flag | 2 | 2 | 2 | 2 | 2 |
| Record format legalities: Vintage, Legacy, Commander | 4 | 2 | 4 | 4 | 4 |
| Respect task constraints (no pricing/links; stop after requested fields) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
