# browser_task_090-si-defining-constant-table-20260909T091833Z verifier comparison

Frozen rubric SHA-256: `316185411a39bbb1b56e98d74c7dbc4d4714dc2022a91c98a872a1b80669e08f`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 9/16 (0.562) | False | 11 | 11 | 0 | 70,652 | 9,802 | 80,454 |
| DOM-model | 8/16 (0.500) | False | 16 | 16 | 0 | 94,832 | 16,532 | 111,364 |

DOM-model minus screenshot tokens: **+30,910 (+38.42%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Report defining constant #1 (as displayed in BIPM table) | 2 | 2 | 1 | 1 | 1 |
| Report defining constant #2 (as displayed in BIPM table) | 2 | 2 | 1 | 1 | 1 |
| Report defining constant #3 (as displayed in BIPM table) | 2 | 2 | 1 | 1 | 1 |
| Report defining constant #4 (as displayed in BIPM table) | 2 | 2 | 1 | 1 | 1 |
| Report defining constant #5 (as displayed in BIPM table) | 2 | 2 | 1 | 1 | 1 |
| Report defining constant #6 (as displayed in BIPM table) | 2 | 1 | 0 | 1 | 0 |
| Report defining constant #7 (as displayed in BIPM table) | 2 | 1 | 1 | 1 | 1 |
| Report BIPM uncertainty statement about the numerical values | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
