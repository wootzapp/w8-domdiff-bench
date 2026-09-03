# viewport-modern-10-github-release-research-20260829T075327Z verifier comparison

Frozen rubric SHA-256: `94841ef8996547efe1534dcc890c5932b344e48b76633dc6a8fa3b45f49f52cd`  
Denominator: `14`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/14 (0.571) | False | 10 | 10 | 0 | 58,322 | 6,932 | 65,254 |
| DOM-model | 12/14 (0.857) | False | 16 | 16 | 0 | 77,152 | 10,792 | 87,944 |

DOM-model minus screenshot tokens: **+22,690 (+34.77%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access pytorch/pytorch release information source and determine the latest release | 3 | 0 | 3 | 3 | 3 |
| Report the release tag for the latest release | 2 | 2 | 2 | 2 | 2 |
| Report the release date for the latest release | 2 | 1 | 1 | 0 | 0 |
| Record the first three highlight bullets in displayed order | 4 | 4 | 4 | 0 | 4 |
| Respect constraints and stopping condition | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
