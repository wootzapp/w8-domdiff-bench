# viewport-modern-24-daytona-support-issue-triage-20260829T084532Z verifier comparison

Frozen rubric SHA-256: `313fe98f4bd8203bee317d7dc05112d5407b69dee9eff5ca208d203947e88f97`  
Denominator: `23`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 18.5/23 (0.804) | False | 16 | 16 | 0 | 111,314 | 12,528 | 123,842 |
| DOM-model | 21/23 (0.913) | False | 18 | 18 | 0 | 141,144 | 16,384 | 157,528 |

DOM-model minus screenshot tokens: **+33,686 (+27.20%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Inspect up to 8 most recent substantive requests in #daytona-support (including visible thread replies) | 4 | 1 | 4 | 1 | 2 |
| Per-request required fields: requester and timestamp | 3 | 3 | 3 | 2 | 3 |
| Per-request concise problem statement | 3 | 3 | 3 | 2.5 | 3 |
| Per-request latest response captured | 3 | 3 | 3 | 3 | 3 |
| Per-request status labeling with explicit evidence (resolved/unresolved/unclear) | 6 | 6 | 6 | 6 | 6 |
| Identify up to 3 requests needing follow-up | 2 | 2 | 2 | 2 | 2 |
| Non-modification of Slack content | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
