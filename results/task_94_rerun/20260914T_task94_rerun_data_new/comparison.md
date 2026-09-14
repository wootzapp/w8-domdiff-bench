# browser_task_094-eu-regulation-metadata-20260914T092727Z verifier comparison

Frozen rubric SHA-256: `dd3cc482d818e64a490ac97ab93402bf440a770eca29c4aca54cb37af6c25049`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 0.5/15 (0.033) | False | 12 | 12 | 0 | 69,169 | 7,166 | 76,335 |
| DOM-model | 1/15 (0.067) | False | 30 | 30 | 0 | 135,437 | 17,941 | 153,378 |

DOM-model minus screenshot tokens: **+77,043 (+100.93%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Record document number (CELEX) for EUR-Lex 32016R0679 | 2 | 2 | 0 | 0 | 0 |
| Record complete Official Journal citation shown under the title | 3 | 3 | 3 | 0 | 0 |
| Open and use EUR-Lex 'Document information' view and labeled 'Dates' metadata | 2 | 2 | 2 | 0.5 | 1 |
| Report Date of document (from Dates metadata) | 2 | 2 | 2 | 0 | 0 |
| Report entry-into-force Date of effect (from Dates metadata) and distinguish it from application date | 3 | 3 | 3 | 0 | 0 |
| Report application Date of effect (from Dates metadata) and distinguish it from entry-into-force date | 3 | 3 | 3 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
