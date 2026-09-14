# browser_task_089-postcode-civic-geography-20260914T092026Z verifier comparison

Frozen rubric SHA-256: `31a747cbdae946437d32ce2f8ae2ec81d89d1c630bd4ee658425f925b6985095`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/12 (1.000) | True | 12 | 12 | 0 | 65,494 | 5,741 | 71,235 |
| DOM-model | 12/12 (1.000) | True | 24 | 24 | 0 | 87,227 | 12,984 | 100,211 |

DOM-model minus screenshot tokens: **+28,976 (+40.68%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Report 11 specific fields from the result object for SW1A2AA | 6 | 6 | 6 | 6 | 6 |
| Use only result object fields (with sole exception of codes.admin_district) and keep fields distinct | 3 | 3 | 3 | 3 | 3 |
| Preserve exact formatting/precision as returned | 2 | 2 | 2 | 2 | 2 |
| Stopping condition: stop after recording all 11 requested fields | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
