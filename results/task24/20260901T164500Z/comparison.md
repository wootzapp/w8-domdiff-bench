# viewport-modern-24-daytona-support-issue-triage-20260829T084532Z verifier comparison

Frozen rubric SHA-256: `313fe98f4bd8203bee317d7dc05112d5407b69dee9eff5ca208d203947e88f97`  
Denominator: `23`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 11.5/23 (0.500) | False | 14 | 14 | 0 | 100,227 | 12,620 | 112,847 |
| DOM-model | 20/23 (0.870) | False | 19 | 19 | 0 | 146,636 | 16,178 | 162,814 |

DOM-model minus screenshot tokens: **+49,967 (+44.28%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Inspect up to 8 most recent substantive requests in #daytona-support (including visible thread replies) | 4 | 4 | 1 | 2 | 1 |
| Per-request required fields: requester and timestamp | 3 | 3 | 3 | 1.5 | 3 |
| Per-request concise problem statement | 3 | 3 | 3 | 2 | 3 |
| Per-request latest response captured | 3 | 3 | 3 | 0 | 3 |
| Per-request status labeling with explicit evidence (resolved/unresolved/unclear) | 6 | 6 | 6 | 3 | 6 |
| Identify up to 3 requests needing follow-up | 2 | 2 | 2 | 1 | 2 |
| Non-modification of Slack content | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
