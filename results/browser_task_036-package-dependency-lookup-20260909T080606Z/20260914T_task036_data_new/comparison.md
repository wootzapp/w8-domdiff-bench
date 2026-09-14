# browser_task_036-package-dependency-lookup-20260909T080606Z verifier comparison

Frozen rubric SHA-256: `21c4811a4e548e87e00a1e3531cb01097dc7c0680f13eb540ec9481d4dd05203`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/16 (1.000) | True | 12 | 12 | 0 | 68,627 | 7,473 | 76,100 |
| DOM-model | 16/16 (1.000) | True | 14 | 14 | 0 | 73,500 | 9,071 | 82,571 |

DOM-model minus screenshot tokens: **+6,471 (+8.50%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the Debian Bookworm curl package page (packages.debian.org/bookworm/curl) | 2 | 2 | 2 | 2 | 2 |
| Report the Bookworm curl package version | 3 | 3 | 3 | 3 | 3 |
| List every architecture in the 'Download curl' table | 3 | 2 | 3 | 3 | 3 |
| List all required dependencies under 'Depends' with displayed version constraints | 6 | 4 | 6 | 6 | 6 |
| Respect constraints (no download/install; remain on Bookworm package page; stop after recording required info) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
