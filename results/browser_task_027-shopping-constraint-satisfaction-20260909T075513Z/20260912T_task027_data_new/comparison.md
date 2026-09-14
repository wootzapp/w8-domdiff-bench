# browser_task_027-shopping-constraint-satisfaction-20260909T075513Z verifier comparison

Frozen rubric SHA-256: `2212291f68520b789f988e7484e561cb893b90ec6481965020f5f65c8540c648`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8.5/18 (0.472) | False | 30 | 30 | 0 | 153,527 | 12,278 | 165,805 |
| DOM-model | 7/18 (0.389) | False | 36 | 36 | 0 | 284,622 | 19,654 | 304,276 |

DOM-model minus screenshot tokens: **+138,471 (+83.51%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Browse eBay without restricted actions (no sign-in, no bid/cart/purchase) | 2 | 2 | 2 | 2 | 2 |
| Find a laptop listing in the $600–$900 range that appears to meet RAM/SSD thresholds | 4 | 4 | 4 | 4 | 4 |
| Open product detail page and verify RAM and SSD from the item specifics/detail table when available | 6 | 6 | 0 | 1 | 0 |
| Report model, price, RAM, and SSD capacity (with confirmation source) | 3 | 3 | 0 | 1.5 | 0 |
| Stop after one qualifying laptop is verified, and handle bot-check/CAPTCHA appropriately | 3 | 3 | 3 | 0 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
