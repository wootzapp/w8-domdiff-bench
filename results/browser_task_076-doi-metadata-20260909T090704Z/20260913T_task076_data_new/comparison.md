# browser_task_076-doi-metadata-20260909T090704Z verifier comparison

Frozen rubric SHA-256: `256cf48db6dc6362d093dcf836d688dbfe7cc5f2c89f278d9c8a5c5b966e3a0b`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3/20 (0.150) | False | 20 | 20 | 0 | 116,821 | 11,325 | 128,146 |
| DOM-model | 9/20 (0.450) | False | 75 | 75 | 0 | 259,650 | 48,106 | 307,756 |

DOM-model minus screenshot tokens: **+179,610 (+140.16%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the supplied Crossref response (message object fields) | 3 | 3 | 3 | 3 | 3 |
| Report work title from message.title | 2 | 0 | 2 | 0 | 0 |
| Report publisher from message.publisher | 2 | 0 | 2 | 0 | 0 |
| Report published date from message.published.date-parts | 3 | 0 | 3 | 0 | 2 |
| Report work type from message.type | 2 | 0 | 2 | 0 | 1 |
| Report complete ordered author list from message.author | 6 | 0 | 6 | 0 | 2 |
| Stop after recording the requested fields (stopping condition) | 2 | 2 | 2 | 0 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
