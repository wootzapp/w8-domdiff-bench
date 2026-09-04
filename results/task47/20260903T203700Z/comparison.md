# browser_task_058-food-product-nutrition-lookup-20260902T210656Z verifier comparison

Frozen rubric SHA-256: `a9be21fbee7bbd2dedcc5211f2687044f63f04852414e09586ecefb36303a3cd`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/20 (0.750) | False | 12 | 12 | 0 | 78,239 | 8,650 | 86,889 |
| DOM-model | 15.5/20 (0.775) | False | 17 | 17 | 0 | 84,300 | 11,666 | 95,966 |

DOM-model minus screenshot tokens: **+9,077 (+10.45%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Open the exact Open Food Facts product record for barcode 3017620422003 | 3 | 3 | 3 | 3 | 3 |
| Report product name and barcode | 2 | 2 | 2 | 2 | 2 |
| Report displayed Nutri-Score | 2 | 2 | 2 | 2 | 2 |
| Report NOVA card processing classification and marker count (visible wording) | 3 | 3 | 3 | 3 | 3 |
| Report energy per 100 g with displayed units | 3 | 3 | 3 | 0 | 3 |
| Report sugars per 100 g exactly | 2 | 2 | 2 | 0 | 2 |
| Report complete displayed English ingredients text | 4 | 0 | 0 | 4 | 0 |
| Respect constraints and stopping condition | 1 | 1 | 1 | 1 | 0.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
