# browser_task_061-npm-package-metadata-20260914T083717Z verifier comparison

Frozen rubric SHA-256: `51d85ccf1ea752a69f80236d568acd7c68dbea30f14b67afb334ca03e1873afe`  
Denominator: `14`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/14 (1.000) | True | 12 | 12 | 0 | 70,711 | 6,690 | 77,401 |
| DOM-model | 14/14 (1.000) | True | 20 | 20 | 0 | 97,974 | 12,939 | 110,913 |

DOM-model minus screenshot tokens: **+33,512 (+43.30%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use official npm Registry response at specified URL | 2 | 0 | 0 | 2 | 2 |
| Record package name | 1 | 0 | 0 | 1 | 1 |
| Record latest version | 2 | 0 | 0 | 2 | 2 |
| Record license | 1 | 0 | 0 | 1 | 1 |
| Record Node.js engine requirement from engines.node | 2 | 0 | 0 | 2 | 2 |
| Record unpacked size in bytes from dist.unpackedSize | 2 | 0 | 0 | 2 | 2 |
| Record file count from dist.fileCount | 2 | 0 | 0 | 2 | 2 |
| Respect constraints and stopping condition | 2 | 2 | 0 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
