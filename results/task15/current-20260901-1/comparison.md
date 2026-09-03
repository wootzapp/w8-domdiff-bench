# viewport-modern-15-slack-workspace-expertise-directory-20260829T075920Z verifier comparison

Frozen rubric SHA-256: `960a001a9ca0fee90c99bc2cdd7acb575dd997af36c7ea310c30ccf8d38abced`  
Denominator: `26`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 9/26 (0.346) | False | 51 | 51 | 0 | 283,769 | 21,611 | 305,380 |
| DOM-model | 12/26 (0.462) | False | 63 | 63 | 0 | 418,053 | 27,865 | 445,918 |

DOM-model minus screenshot tokens: **+140,538 (+46.02%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Slack People/member directory interface (or report access blockers) without DMs/edits | 2 | 2 | 2 | 2 | 2 |
| Use Slack workspace search (or report access blockers) without DMs/edits | 2 | 0 | 0 | 2 | 2 |
| Identify up to 12 accessible relevant members (or explain limitation) | 6 | 3 | 0 | 1 | 1 |
| Report only Slack-visible fields per person (and mark missing fields as not present) | 7 | 5 | 7 | 3 | 6 |
| Provide one supporting public message reference when available (or explicitly note none accessible) | 5 | 5 | 5 | 1 | 1 |
| Group members by likely area of expertise and mark unclear classifications | 4 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
