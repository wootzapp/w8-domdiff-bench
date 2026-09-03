# viewport-modern-16-amazon-carry-on-luggage-comparison-20260829T081858Z verifier comparison

Frozen rubric SHA-256: `2d015103c57f0826dbd4548812ce73317f2f4044c0d4d574ee0d456d68309c47`  
Denominator: `27`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 27/27 (1.000) | False | 36 | 36 | 0 | 172,340 | 11,417 | 183,757 |
| DOM-model | 27/27 (1.000) | False | 47 | 47 | 0 | 185,453 | 18,966 | 204,419 |

DOM-model minus screenshot tokens: **+20,662 (+11.24%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Search Amazon for hard-shell carry-on luggage | 3 | 3 | 3 | 3 | 3 |
| Apply visible filters: Prime-eligible, 4+ stars, and $60–$140 | 5 | 5 | 5 | 5 | 5 |
| Open three qualifying listings | 6 | 6 | 6 | 6 | 6 |
| Extract and compare required attributes across the three listings | 8 | 8 | 8 | 8 | 8 |
| Recommend the best option for international cabin travel (no purchase) | 5 | 5 | 5 | 5 | 5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
