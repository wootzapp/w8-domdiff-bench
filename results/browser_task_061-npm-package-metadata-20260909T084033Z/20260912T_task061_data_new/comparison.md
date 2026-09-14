# browser_task_061-npm-package-metadata-20260909T084033Z verifier comparison

Frozen rubric SHA-256: `51d85ccf1ea752a69f80236d568acd7c68dbea30f14b67afb334ca03e1873afe`  
Denominator: `14`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/14 (1.000) | True | 12 | 12 | 0 | 71,446 | 7,959 | 79,405 |
| DOM-model | 9/14 (0.643) | False | 27 | 27 | 0 | 98,633 | 18,848 | 117,481 |

DOM-model minus screenshot tokens: **+38,076 (+47.95%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use official npm Registry response at specified URL | 2 | 2 | 2 | 2 | 2 |
| Record package name | 1 | 1 | 1 | 1 | 1 |
| Record latest version | 2 | 0 | 0 | 2 | 2 |
| Record license | 1 | 1 | 1 | 1 | 1 |
| Record Node.js engine requirement from engines.node | 2 | 0 | 0 | 2 | 0 |
| Record unpacked size in bytes from dist.unpackedSize | 2 | 0 | 0 | 2 | 0 |
| Record file count from dist.fileCount | 2 | 0 | 0 | 2 | 2 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
