# viewport-modern-6-chess-profile-lookup-20260829T074948Z verifier comparison

Frozen rubric SHA-256: `efecc4b2d2ac529ca72d2d1520667713c8836927304f465bdb0733988e59dadb`  
Denominator: `14`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/14 (0.429) | False | 35 | 35 | 0 | 162,360 | 11,848 | 174,208 |
| DOM-model | 6/14 (0.429) | False | 38 | 38 | 0 | 151,247 | 10,864 | 162,111 |

DOM-model minus screenshot tokens: **-12,097 (-6.94%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Open Magnus Carlsen’s Chess.com profile | 3 | 3 | 3 | 3 | 3 |
| Record Blitz rating exactly as displayed | 4 | 0 | 0 | 0 | 1 |
| Record Bullet rating exactly as displayed | 4 | 0 | 0 | 0 | 0 |
| Respect constraints and stopping condition | 3 | 3 | 3 | 3 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
