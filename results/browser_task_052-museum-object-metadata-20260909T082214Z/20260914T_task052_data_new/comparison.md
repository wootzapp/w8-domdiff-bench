# browser_task_052-museum-object-metadata-20260909T082214Z verifier comparison

Frozen rubric SHA-256: `c02904ee56b52f562119b176de2bac1fc28485b26acb5f9b7abc0bc96bd4a09e`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 22/22 (1.000) | True | 16 | 16 | 0 | 95,407 | 9,201 | 104,608 |
| DOM-model | 21/22 (0.955) | True | 35 | 35 | 0 | 153,275 | 19,527 | 172,802 |

DOM-model minus screenshot tokens: **+68,194 (+65.19%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the specified Smithsonian/NASM object record (Apollo 11 Command Module Columbia) | 3 | 3 | 3 | 3 | 3 |
| Record the object name | 2 | 2 | 1 | 2 | 2 |
| Record the museum | 2 | 1 | 2 | 2 | 1 |
| Extract mission month and year from Brief Description | 3 | 3 | 3 | 3 | 3 |
| Record complete Primary Materials field (verbatim) | 4 | 2 | 2 | 4 | 4 |
| Record complete Overall Dimensions field (verbatim, exact measurements) | 4 | 2 | 2 | 4 | 4 |
| Record Inventory Number | 2 | 2 | 2 | 2 | 2 |
| Respect stopping condition and scope constraints (single-record only; no extras) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
