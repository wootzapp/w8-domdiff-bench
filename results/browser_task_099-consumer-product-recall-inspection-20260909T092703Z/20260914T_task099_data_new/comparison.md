# browser_task_099-consumer-product-recall-inspection-20260909T092703Z verifier comparison

Frozen rubric SHA-256: `f525c5189c79ff820071b6074d55eef71ded39a4ffa09746ef1f5c23d9f8a218`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 7/20 (0.350) | False | 14 | 14 | 0 | 97,905 | 11,109 | 109,014 |
| DOM-model | 5/20 (0.250) | False | 21 | 21 | 0 | 107,846 | 21,912 | 129,758 |

DOM-model minus screenshot tokens: **+20,744 (+19.03%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Retrieve the recall object from the specified CPSC endpoint (RecallID=10000) | 2 | 2 | 2 | 2 | 2 |
| Report recall identifiers and core fields (RecallID, RecallNumber, RecallDate, Title) | 3 | 3 | 3 | 3 | 2 |
| Report all Products entries (Name and NumberOfUnits for each product) | 3 | 3 | 3 | 0 | 0 |
| Report all Injuries entries (Name for each) | 2 | 2 | 2 | 0 | 0 |
| Report all Retailers entries (Name for each) | 1 | 1 | 1 | 0 | 0 |
| Report all ManufacturerCountries entries (Country for each) | 2 | 2 | 2 | 2 | 0 |
| Report all Hazards, Remedies, and RemedyOptions entries (Name/Option for each) | 4 | 4 | 4 | 0 | 0 |
| Adhere to extraction constraints (no substitution; exact transcription; no fabrication) | 3 | 3 | 3 | 0 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
