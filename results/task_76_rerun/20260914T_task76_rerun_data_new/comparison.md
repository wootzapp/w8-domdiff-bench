# browser_task_076-doi-metadata-20260914T090131Z verifier comparison

Frozen rubric SHA-256: `256cf48db6dc6362d093dcf836d688dbfe7cc5f2c89f278d9c8a5c5b966e3a0b`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 19/20 (0.950) | False | 12 | 12 | 0 | 69,268 | 6,589 | 75,857 |
| DOM-model | 16/20 (0.800) | False | 26 | 26 | 0 | 137,785 | 16,578 | 154,363 |

DOM-model minus screenshot tokens: **+78,506 (+103.49%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the supplied Crossref response (message object fields) | 3 | 3 | 3 | 3 | 2 |
| Report work title from message.title | 2 | 2 | 2 | 2 | 2 |
| Report publisher from message.publisher | 2 | 2 | 2 | 2 | 2 |
| Report published date from message.published.date-parts | 3 | 3 | 3 | 3 | 0 |
| Report work type from message.type | 2 | 2 | 2 | 2 | 2 |
| Report complete ordered author list from message.author | 6 | 6 | 6 | 5 | 6 |
| Stop after recording the requested fields (stopping condition) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
