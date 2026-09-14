# browser_task_026-shopping-constraint-satisfaction-20260909T075313Z verifier comparison

Frozen rubric SHA-256: `b98cd8fd5da1831ceb7d0ff89fd58c491c1ee5ba1c2f9636ae58f15e809db13a`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/18 (0.333) | False | 25 | 25 | 0 | 157,549 | 16,609 | 174,158 |
| DOM-model | 6/18 (0.333) | False | 33 | 33 | 0 | 213,918 | 22,759 | 236,677 |

DOM-model minus screenshot tokens: **+62,519 (+35.90%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Search Amazon for 'wireless mouse' | 3 | 3 | 3 | 3 | 3 |
| Apply required filters and sort order | 4 | 1 | 1 | 1 | 1 |
| Report top product (rank #1 after sort) | 3 | 0 | 0 | 0 | 0 |
| Report second product (rank #2 after sort) | 3 | 0 | 0 | 0 | 0 |
| Report third product (rank #3 after sort) | 3 | 0 | 0 | 0 | 0 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |
| Handle bot check / access block appropriately | 2 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
