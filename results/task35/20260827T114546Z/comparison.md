# viewport-requests-prs-viewport-requests-pull-request-inspection-20260826T185754Z verifier comparison

Frozen rubric SHA-256: `98803c496f9bd771276d057c008bdde589cda43010f2ce9b3c4c6b01eca48f79`  
Denominator: `26`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17/26 (0.654) | False | 42 | 42 | 0 | 304,703 | 25,651 | 330,354 |
| DOM-model | 15/26 (0.577) | False | 37 | 37 | 0 | 210,051 | 17,085 | 227,136 |

DOM-model minus screenshot tokens: **-103,218 (-31.24%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Apply GitHub PR filters (open, non-draft) and sort by most recently updated | 3 | 3 | 3 | 3 | 3 |
| Inspect the first three results after filtering/sorting | 3 | 3 | 3 | 1 | 1 |
| Report required fields for PR #1 | 4 | 4 | 3 | 3 | 2 |
| Report required fields for PR #2 | 4 | 4 | 1 | 1 | 1 |
| Report required fields for PR #3 | 4 | 4 | 1 | 1 | 1 |
| Verify presence of test files in 'Files changed' for each PR | 3 | 3 | 3 | 3 | 2 |
| Rank the three PRs by changed-file count | 2 | 2 | 2 | 2 | 2 |
| Respect constraints: no sign-in and no PR modifications | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
