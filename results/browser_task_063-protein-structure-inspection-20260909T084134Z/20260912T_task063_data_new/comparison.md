# browser_task_063-protein-structure-inspection-20260909T084134Z verifier comparison

Frozen rubric SHA-256: `2b6d742bc4854ebed327a519c46a92c0e11d5a011131e16c97c5839cabd5f8ab`  
Denominator: `23`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/23 (0.652) | False | 12 | 12 | 0 | 76,024 | 10,322 | 86,346 |
| DOM-model | 23/23 (1.000) | True | 29 | 29 | 0 | 139,322 | 17,215 | 156,537 |

DOM-model minus screenshot tokens: **+70,191 (+81.29%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the RCSB PDB 1TUP Structure Summary page as the source (or report access failure) | 2 | 2 | 2 | 2 | 2 |
| Report complete structure title | 2 | 2 | 1 | 2 | 2 |
| Report released date exactly as displayed | 2 | 0 | 1 | 2 | 2 |
| Report experimental method | 2 | 2 | 1 | 2 | 2 |
| Report resolution with units exactly (if displayed) | 3 | 3 | 3 | 3 | 3 |
| Report protein molecule name | 3 | 3 | 3 | 0 | 3 |
| Report protein source organism (exclude DNA rows with N/A) | 3 | 3 | 3 | 3 | 3 |
| List every unique ligand ID displayed (deduplicated) | 5 | 5 | 2 | 0 | 5 |
| Stop after recording all requested fields | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
