# github-heavy-01-kubernetes-release-comparison-20260821T060103Z verifier comparison

Frozen rubric SHA-256: `8ebac35b484bcbea4038850615822b9baa14b46f37df879996bffce984618ea8`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/20 (0.300) | False | 29 | 29 | 0 | 168,863 | 16,019 | 184,882 |
| DOM-model | 6/20 (0.300) | False | 27 | 27 | 0 | 294,578 | 12,165 | 306,743 |

DOM-model minus screenshot tokens: **+121,861 (+65.91%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Identify the two newest stable Kubernetes releases (exclude alpha/beta/rc) | 4 | 4 | 4 | 4 | 4 |
| Report required fields for newest stable release | 5 | 0 | 0 | 0 | 0 |
| Report required fields for second-newest stable release | 5 | 0 | 0 | 0 | 0 |
| Calculate calendar-day difference between the two releases | 2 | 0 | 0 | 0 | 0 |
| Compliance with constraints and stopping condition (verification, no sign-in, no asset downloads, no repo modification, no invention) | 4 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
