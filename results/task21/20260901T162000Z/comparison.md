# viewport-modern-21-google-finance-company-comparison-20260829T084259Z verifier comparison

Frozen rubric SHA-256: `cd38bcfece2d833a6ebeb27732f260083f2ca535f79f639d4626dc3d0913dc1a`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3.5/22 (0.159) | False | 14 | 14 | 0 | 84,885 | 9,747 | 94,632 |
| DOM-model | 5/22 (0.227) | False | 21 | 21 | 0 | 182,488 | 17,008 | 199,496 |

DOM-model minus screenshot tokens: **+104,864 (+110.81%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Google Finance and attempt to locate Apple (AAPL) page | 3 | 3 | 2 | 2.5 | 2 |
| Access Google Finance and attempt to locate Microsoft (MSFT) page | 3 | 3 | 0 | 0 | 0 |
| Report Apple metrics and latest visible news headline (or unavailability) | 6 | 6 | 6 | 1 | 2 |
| Report Microsoft metrics and latest visible news headline (or unavailability) | 6 | 6 | 6 | 0 | 0 |
| Provide a comparison and identify which company has larger market capitalization | 4 | 4 | 4 | 0 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
