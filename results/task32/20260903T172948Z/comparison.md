# browser_task_036-package-dependency-lookup-20260902T193835Z verifier comparison

Frozen rubric SHA-256: `5c74985a56146dcfa8c60664d6dcd3009430051000f0132eddfa086cc0129b7d`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/18 (0.889) | False | 12 | 12 | 0 | 66,066 | 8,145 | 74,211 |
| DOM-model | 16/18 (0.889) | False | 26 | 26 | 0 | 105,102 | 15,990 | 121,092 |

DOM-model minus screenshot tokens: **+46,881 (+63.17%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the Debian Bookworm curl package page (packages.debian.org/bookworm/curl) | 2 | 2 | 2 | 2 | 2 |
| Record the Bookworm curl package version | 3 | 3 | 3 | 3 | 3 |
| Record all architectures in the 'Download curl' table | 3 | 2 | 3 | 1 | 1 |
| Record all required dependencies under Depends (with version constraints) | 7 | 7 | 7 | 7 | 7 |
| Respect constraints: no download/install; stop after recording requested items | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
