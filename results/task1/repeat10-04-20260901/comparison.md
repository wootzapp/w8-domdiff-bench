# viewport-modern-1-cross-site-research-20260829T074513Z verifier comparison

Frozen rubric SHA-256: `fac623938e43e710f25c70350a0989e6d1ce38338113f171c5de38c6529c6a15`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/15 (0.667) | False | 22 | 22 | 0 | 112,576 | 10,387 | 122,963 |
| DOM-model | 8/15 (0.533) | False | 20 | 20 | 0 | 93,205 | 8,741 | 101,946 |

DOM-model minus screenshot tokens: **-21,017 (-17.09%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate Xbox.com to the 'Best sellers' section | 3 | 1 | 0 | 1 | 0 |
| Open a product page for a game from 'Best sellers' | 3 | 3 | 1 | 2 | 1 |
| Report publisher, developer, and release date from the product page | 6 | 6 | 6 | 4 | 4 |
| Respect constraints (no sign-in; no purchase or download; stop after recording details) | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
