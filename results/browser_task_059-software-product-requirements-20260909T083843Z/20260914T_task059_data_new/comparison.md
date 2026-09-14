# browser_task_059-software-product-requirements-20260909T083843Z verifier comparison

Frozen rubric SHA-256: `7435c18812ab17285e1090f30e18253e9571625c88d16876d37126706fdf9d97`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/17 (0.765) | False | 22 | 22 | 0 | 122,303 | 12,167 | 134,470 |
| DOM-model | 12/17 (0.706) | False | 33 | 33 | 0 | 184,298 | 18,755 | 203,053 |

DOM-model minus screenshot tokens: **+68,583 (+51.00%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the correct Steam store page for Portal 2 | 2 | 2 | 2 | 2 | 2 |
| Report Release Date, Developer, and Publisher | 3 | 3 | 3 | 3 | 3 |
| Report complete displayed 'All Reviews' summary (not Recent Reviews) | 3 | 2 | 1 | 1 | 1 |
| Record System Requirements OS headings shown and each heading’s minimum Storage requirement | 7 | 5 | 7 | 5 | 4 |
| Respect constraints: no sign-in and no purchase-related actions | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
