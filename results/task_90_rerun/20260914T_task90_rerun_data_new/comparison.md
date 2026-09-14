# browser_task_090-si-defining-constant-table-20260914T092152Z verifier comparison

Frozen rubric SHA-256: `316185411a39bbb1b56e98d74c7dbc4d4714dc2022a91c98a872a1b80669e08f`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/16 (0.875) | False | 11 | 11 | 0 | 71,884 | 8,895 | 80,779 |
| DOM-model | 15.5/16 (0.969) | False | 14 | 14 | 0 | 85,638 | 10,821 | 96,459 |

DOM-model minus screenshot tokens: **+15,680 (+19.41%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Report defining constant #1 (as displayed in BIPM table) | 2 | 1 | 0 | 2 | 2 |
| Report defining constant #2 (as displayed in BIPM table) | 2 | 2 | 0 | 2 | 2 |
| Report defining constant #3 (as displayed in BIPM table) | 2 | 2 | 0 | 2 | 2 |
| Report defining constant #4 (as displayed in BIPM table) | 2 | 2 | 0 | 2 | 2 |
| Report defining constant #5 (as displayed in BIPM table) | 2 | 2 | 0 | 2 | 2 |
| Report defining constant #6 (as displayed in BIPM table) | 2 | 0 | 0 | 0 | 1.5 |
| Report defining constant #7 (as displayed in BIPM table) | 2 | 1 | 0 | 2 | 2 |
| Report BIPM uncertainty statement about the numerical values | 2 | 2 | 0 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
