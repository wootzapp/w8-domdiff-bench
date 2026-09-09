# browser_task_002-cross-site-research-20260909T070119Z verifier comparison

Frozen rubric SHA-256: `2157f3abcd304f7618cb600205bd1f4ac17cb9bfeb93fd0b39f1da3c1e795d6a`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/15 (0.533) | False | 25 | 25 | 0 | 126,243 | 10,769 | 137,012 |
| DOM-model | 11/15 (0.733) | False | 32 | 32 | 0 | 133,979 | 12,991 | 146,970 |

DOM-model minus screenshot tokens: **+9,958 (+7.27%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate Xbox.com to the 'Best sellers' section and select a listed game | 4 | 4 | 4 | 2 | 2 |
| Open the selected game's product page | 3 | 3 | 3 | 3 | 3 |
| Report publisher, developer, and release date from the product page | 5 | 0 | 5 | 0 | 3 |
| Comply with constraints (no sign-in; no buying/downloading; stop after recording details) | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
