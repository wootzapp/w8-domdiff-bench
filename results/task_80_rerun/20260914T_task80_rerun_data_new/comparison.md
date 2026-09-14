# browser_task_080-protein-record-inspection-20260914T090913Z verifier comparison

Frozen rubric SHA-256: `da6c0c2e585c969c9e8a4722f03ca6e9a3c22ecc5bd5ce27271a367fa424c122`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3/17 (0.176) | False | 10 | 10 | 0 | 58,367 | 6,251 | 64,618 |
| DOM-model | 15/17 (0.882) | False | 11 | 11 | 0 | 61,253 | 7,646 | 68,899 |

DOM-model minus screenshot tokens: **+4,281 (+6.63%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the UniProtKB entry page for accession P04637 (or determine it is inaccessible) | 3 | 0 | 0 | 3 | 3 |
| Record entry name | 2 | 0 | 0 | 0 | 2 |
| Record recommended protein name | 2 | 0 | 0 | 0 | 2 |
| Record primary gene name | 2 | 0 | 0 | 0 | 2 |
| Record organism | 2 | 0 | 0 | 0 | 2 |
| Record canonical sequence length | 2 | 0 | 0 | 0 | 2 |
| Record reviewed status (as displayed) | 2 | 0 | 0 | 0 | 2 |
| Stopping condition met (all six fields reported, then stop) | 2 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
