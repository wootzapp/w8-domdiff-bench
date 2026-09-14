# browser_task_069-ip-network-registration-20260914T085250Z verifier comparison

Frozen rubric SHA-256: `2e9f94d2e3c2b0d218506eacceb5a1cdbaf8c8feae59e06a46df40b539ee5e99`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 2/22 (0.091) | False | 12 | 12 | 0 | 77,965 | 9,173 | 87,138 |
| DOM-model | 2/22 (0.091) | False | 15 | 15 | 0 | 78,852 | 11,700 | 90,552 |

DOM-model minus screenshot tokens: **+3,414 (+3.92%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Extract top-level network handle | 2 | 0 | 0 | 0 | 0 |
| Extract top-level network name | 2 | 0 | 0 | 0 | 0 |
| Extract top-level startAddress | 2 | 0 | 0 | 0 | 0 |
| Extract top-level endAddress | 2 | 0 | 0 | 0 | 0 |
| Extract top-level network type | 2 | 0 | 0 | 0 | 0 |
| Extract every top-level network status value | 4 | 0 | 0 | 0 | 0 |
| Extract top-level parentHandle | 2 | 0 | 0 | 0 | 0 |
| Extract registrant entity fn from vCard | 4 | 0 | 0 | 0 | 0 |
| Use only supplied ARIN RDAP response and stop after recording requested fields | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
