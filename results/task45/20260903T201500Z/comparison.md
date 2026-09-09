# browser_task_056-biomedical-literature-filtering-20260902T210331Z verifier comparison

Frozen rubric SHA-256: `fdd82154793c5083ef955b2a25e7c61b47feed2200fa7eb56834f783c96be4ab`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 18/18 (1.000) | False | 14 | 14 | 0 | 82,339 | 8,874 | 91,213 |
| DOM-model | 18/18 (1.000) | False | 21 | 21 | 0 | 92,244 | 16,598 | 108,842 |

DOM-model minus screenshot tokens: **+17,629 (+19.33%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Run PubMed Title-field search for the exact phrase | 3 | 3 | 3 | 3 | 3 |
| Apply required filters (Review; past five years) and sort (Most Recent) | 4 | 4 | 4 | 4 | 4 |
| Record result #1 (topmost after filters/sort) with all required fields | 3 | 3 | 3 | 3 | 3 |
| Record result #2 (second after filters/sort) with all required fields | 3 | 3 | 3 | 3 | 3 |
| Record result #3 (third after filters/sort) with all required fields | 3 | 3 | 3 | 3 | 3 |
| Respect stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
