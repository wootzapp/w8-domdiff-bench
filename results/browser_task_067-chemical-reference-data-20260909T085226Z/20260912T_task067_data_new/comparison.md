# browser_task_067-chemical-reference-data-20260909T085226Z verifier comparison

Frozen rubric SHA-256: `1cf91356f00e3863c1d3520912f1db9c10bd6dbb0ff4e94e142d2f02e4d2392e`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 7/15 (0.467) | False | 12 | 12 | 0 | 67,102 | 7,736 | 74,838 |
| DOM-model | 8/15 (0.533) | False | 17 | 17 | 0 | 75,707 | 10,970 | 86,677 |

DOM-model minus screenshot tokens: **+11,839 (+15.82%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the specified NIST Chemistry WebBook record for water (ID=C7732185) | 3 | 2 | 3 | 3 | 3 |
| Report identity fields from the record: formula, molecular weight, IUPAC InChIKey, and CAS Registry Number | 4 | 3 | 3 | 4 | 3 |
| Report CODATA experimental gas-phase standard enthalpy of formation (with unit and reference) | 6 | 0 | 4 | 0 | 1 |
| Preserve exact transcription as feasible and stop after required fields | 2 | 0 | 1 | 0 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
