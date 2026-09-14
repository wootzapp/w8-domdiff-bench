# browser_task_044-earthquake-filtering-and-ranking-20260909T081131Z verifier comparison

Frozen rubric SHA-256: `91a73e9ce7cbb9cfa0fb89a1c190e63915795fb801c4c3a183f71d4b2fc9165d`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 7/16 (0.438) | False | 29 | 29 | 0 | 162,360 | 14,629 | 176,989 |
| DOM-model | 11/16 (0.688) | False | 37 | 37 | 0 | 182,877 | 20,311 | 203,188 |

DOM-model minus screenshot tokens: **+26,199 (+14.80%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Apply correct USGS query filters (UTC range, worldwide, magnitude threshold) | 5 | 5 | 5 | 3 | 4 |
| Order results by magnitude (largest to smallest) | 2 | 2 | 2 | 0 | 0 |
| Report top three results with required fields (preserve USGS order for ties, UTC times) | 5 | 5 | 5 | 0 | 3 |
| Handle fewer-than-three results correctly | 2 | 2 | 2 | 2 | 2 |
| Respect constraints: no alerts/notifications and proper UTC handling disclosure | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
