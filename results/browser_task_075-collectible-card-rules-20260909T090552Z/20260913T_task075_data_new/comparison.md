# browser_task_075-collectible-card-rules-20260909T090552Z verifier comparison

Frozen rubric SHA-256: `6f14affeb38c269013e39e45b0490af6aae0f1273b38089a71952b4518441c09`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/17 (0.824) | False | 21 | 21 | 0 | 117,521 | 10,122 | 127,643 |
| DOM-model | 5/17 (0.294) | False | 42 | 42 | 0 | 154,235 | 24,205 | 178,440 |

DOM-model minus screenshot tokens: **+50,797 (+39.80%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the exact-card Scryfall API response at the provided URL | 3 | 3 | 3 | 3 | 2 |
| Record card identity fields: name, mana_cost, type_line | 3 | 3 | 3 | 3 | 1 |
| Record complete oracle_text | 3 | 3 | 3 | 0 | 0 |
| Record reserved flag | 2 | 2 | 2 | 2 | 0 |
| Record format legalities: Vintage, Legacy, Commander | 4 | 4 | 4 | 4 | 0 |
| Respect task constraints (no pricing/links; stop after requested fields) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
