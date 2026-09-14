# browser_task_058-food-product-nutrition-lookup-20260909T094500Z verifier comparison

Frozen rubric SHA-256: `ae2b0f4ffaaeffc8722627003c7d60317a3aa3d5479d92f2c544b84e631281ac`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 7/20 (0.350) | False | 12 | 12 | 0 | 81,479 | 9,983 | 91,462 |
| DOM-model | 14/20 (0.700) | False | 16 | 16 | 0 | 87,047 | 12,399 | 99,446 |

DOM-model minus screenshot tokens: **+7,984 (+8.73%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the exact Open Food Facts product record for barcode 3017620422003 | 3 | 3 | 3 | 3 | 3 |
| Report product name and barcode | 2 | 2 | 2 | 1 | 2 |
| Report displayed Nutri-Score | 2 | 2 | 2 | 2 | 2 |
| Report NOVA processing card classification and marker count (visible wording) | 3 | 3 | 3 | 1 | 3 |
| Report energy per 100 g (preserving displayed units) | 3 | 3 | 3 | 0 | 0 |
| Report sugars per 100 g (exact value) | 2 | 2 | 2 | 0 | 0 |
| Report complete displayed English ingredients text | 4 | 0 | 0 | 0 | 4 |
| Respect constraints and stopping condition | 1 | 1 | 1 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
