# viewport-modern-14-slack-workspace-resources-discovery-20260829T075758Z verifier comparison

Frozen rubric SHA-256: `71fa238fdab90d92345221eb435470252f3b8815380a3a61631d9d5507d41e42`  
Denominator: `27`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/27 (0.296) | False | 28 | 28 | 0 | 173,338 | 16,663 | 190,001 |
| DOM-model | 8/27 (0.296) | False | 38 | 38 | 0 | 241,269 | 21,403 | 262,672 |

DOM-model minus screenshot tokens: **+72,671 (+38.25%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Slack global search with link/file-focused filtering across the workspace | 4 | 4 | 4 | 4 | 4 |
| Collect up to 20 most recent accessible messages containing shared links or files | 4 | 1 | 1 | 1 | 1 |
| Deduplicate identical resources | 3 | 0 | 0 | 0 | 0 |
| Report required fields for each resource | 7 | 0 | 0 | 0 | 0 |
| Group resources into the specified categories | 2 | 0 | 0 | 0 | 0 |
| Do not open external links or download files | 4 | 0 | 0 | 0 | 0 |
| Do not modify Slack content | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
