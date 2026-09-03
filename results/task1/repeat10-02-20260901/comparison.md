# viewport-modern-1-cross-site-research-20260829T074513Z verifier comparison

Frozen rubric SHA-256: `fac623938e43e710f25c70350a0989e6d1ce38338113f171c5de38c6529c6a15`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10.5/15 (0.700) | False | 21 | 21 | 0 | 108,827 | 8,951 | 117,778 |
| DOM-model | 10/15 (0.667) | False | 21 | 21 | 0 | 97,514 | 8,427 | 105,941 |

DOM-model minus screenshot tokens: **-11,837 (-10.05%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate Xbox.com to the 'Best sellers' section | 3 | 3 | 1 | 1.5 | 1 |
| Open a product page for a game from 'Best sellers' | 3 | 3 | 2 | 2 | 2 |
| Report publisher, developer, and release date from the product page | 6 | 6 | 4 | 4 | 4 |
| Respect constraints (no sign-in; no purchase or download; stop after recording details) | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
