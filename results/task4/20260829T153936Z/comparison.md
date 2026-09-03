# viewport-modern-4-nasa-mission-lookup-20260829T074852Z verifier comparison

Frozen rubric SHA-256: `0f9dc5356a1403cc2467a32f218430edb430748c64ba1e9f1948b7a8ea05a6a8`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/18 (0.556) | False | 12 | 12 | 0 | 63,158 | 6,182 | 69,340 |
| DOM-model | 13/18 (0.722) | False | 17 | 17 | 0 | 68,184 | 8,525 | 76,709 |

DOM-model minus screenshot tokens: **+7,369 (+10.63%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use NASA’s website as the source of truth (no sign-in/registration) | 3 | 3 | 3 | 3 | 3 |
| Identify the next planned Artemis mission and report required mission details | 13 | 9 | 10 | 5 | 8 |
| Stop after recording the required mission details | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
