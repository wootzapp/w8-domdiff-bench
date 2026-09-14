# browser_task_012-arxiv-paper-metadata-20260909T073715Z verifier comparison

Frozen rubric SHA-256: `0ba8db17cb7a714de473b135020ece47b0a8098f986ce2fc4f86e50d3dde449f`  
Denominator: `13`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12.5/13 (0.962) | True | 12 | 12 | 0 | 71,458 | 7,760 | 79,218 |
| DOM-model | 12.5/13 (0.962) | True | 17 | 17 | 0 | 81,023 | 13,143 | 94,166 |

DOM-model minus screenshot tokens: **+14,948 (+18.87%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Attempt to access the correct arXiv entry (1706.03762) using arXiv pages | 2 | 2 | 2 | 2 | 2 |
| Comply with constraints (no sign-in; do not download or edit the paper) | 1 | 1 | 1 | 1 | 1 |
| Report total number of versions | 3 | 3 | 0 | 3 | 3 |
| Record the exact publication date string for version 1 | 3 | 3 | 1 | 3 | 3 |
| Record the exact publication date string for the latest version | 3 | 3 | 1 | 3 | 3 |
| Stopping condition satisfied (only version count + both dates, then stop) | 1 | 1 | 0 | 0.5 | 0.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
