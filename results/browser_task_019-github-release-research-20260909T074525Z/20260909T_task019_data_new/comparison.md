# browser_task_019-github-release-research-20260909T074525Z verifier comparison

Frozen rubric SHA-256: `b6de0067c9d19eb4956371b6c427ccb33bacfad0dbf9df5d089946db8cfcac71`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/16 (0.875) | False | 12 | 12 | 0 | 68,481 | 7,646 | 76,127 |
| DOM-model | 16/16 (1.000) | True | 23 | 23 | 0 | 103,171 | 12,413 | 115,584 |

DOM-model minus screenshot tokens: **+39,457 (+51.83%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the pytorch/pytorch releases listing (or report access blocker) | 2 | 2 | 2 | 2 | 2 |
| Identify the latest pytorch/pytorch release | 3 | 1 | 3 | 3 | 3 |
| Report release tag for the latest release | 2 | 0 | 2 | 2 | 2 |
| Report release date for the latest release | 2 | 0 | 2 | 0 | 2 |
| Extract the first three highlight bullets in displayed order | 5 | 0 | 5 | 5 | 5 |
| Stop after required metadata and first three highlights (or after reporting an unavoidable blocker) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
