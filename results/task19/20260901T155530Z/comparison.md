# viewport-modern-19-apple-watch-model-comparison-20260829T083311Z verifier comparison

Frozen rubric SHA-256: `4a2249cfb89791ff5eb878da2f96cde2fd6f3f2bd1e63279dbbb79ce13ab3012`  
Denominator: `28`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/28 (0.500) | False | 63 | 63 | 0 | 421,482 | 26,102 | 447,584 |
| DOM-model | 21/28 (0.750) | False | 72 | 72 | 0 | 442,902 | 26,810 | 469,712 |

DOM-model minus screenshot tokens: **+22,128 (+4.94%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate from Apple homepage to Apple Watch and open the Apple Watch Series page | 3 | 3 | 3 | 3 | 3 |
| Open the Apple Watch SE page | 3 | 3 | 3 | 3 | 3 |
| Compare starting prices for Apple Watch Series vs Apple Watch SE | 4 | 0 | 4 | 2 | 3 |
| Compare available case sizes for Apple Watch Series vs Apple Watch SE | 4 | 0 | 4 | 2 | 2 |
| Compare stated battery life for Apple Watch Series vs Apple Watch SE | 3 | 0 | 3 | 0 | 1 |
| Identify two health or safety features for Apple Watch Series | 3 | 0 | 3 | 1 | 3 |
| Identify two health or safety features for Apple Watch SE | 3 | 0 | 3 | 0 | 3 |
| Make a recommendation for a first-time smartwatch buyer (no purchase) | 3 | 0 | 3 | 1 | 1 |
| Avoid purchasing or crossing transaction critical points | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
