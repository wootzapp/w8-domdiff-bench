# browser_task_067-chemical-reference-data-20260914T085132Z verifier comparison

Frozen rubric SHA-256: `1cf91356f00e3863c1d3520912f1db9c10bd6dbb0ff4e94e142d2f02e4d2392e`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/15 (0.533) | False | 12 | 12 | 0 | 68,702 | 8,535 | 77,237 |
| DOM-model | 7.5/15 (0.500) | False | 17 | 17 | 0 | 77,554 | 11,713 | 89,267 |

DOM-model minus screenshot tokens: **+12,030 (+15.58%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the specified NIST Chemistry WebBook record for water (ID=C7732185) | 3 | 0 | 0 | 3 | 3 |
| Report identity fields from the record: formula, molecular weight, IUPAC InChIKey, and CAS Registry Number | 4 | 2 | 4 | 4 | 3.5 |
| Report CODATA experimental gas-phase standard enthalpy of formation (with unit and reference) | 6 | 3 | 0 | 0 | 0 |
| Preserve exact transcription as feasible and stop after required fields | 2 | 1 | 0 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
