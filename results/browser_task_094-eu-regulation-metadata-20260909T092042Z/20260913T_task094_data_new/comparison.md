# browser_task_094-eu-regulation-metadata-20260909T092042Z verifier comparison

Frozen rubric SHA-256: `dd3cc482d818e64a490ac97ab93402bf440a770eca29c4aca54cb37af6c25049`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/15 (1.000) | True | 12 | 12 | 0 | 71,503 | 6,282 | 77,785 |
| DOM-model | 15/15 (1.000) | True | 23 | 23 | 0 | 117,070 | 11,988 | 129,058 |

DOM-model minus screenshot tokens: **+51,273 (+65.92%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Record document number (CELEX) for EUR-Lex 32016R0679 | 2 | 2 | 2 | 2 | 2 |
| Record complete Official Journal citation shown under the title | 3 | 3 | 3 | 3 | 3 |
| Open and use EUR-Lex 'Document information' view and labeled 'Dates' metadata | 2 | 2 | 2 | 2 | 2 |
| Report Date of document (from Dates metadata) | 2 | 2 | 2 | 2 | 2 |
| Report entry-into-force Date of effect (from Dates metadata) and distinguish it from application date | 3 | 3 | 3 | 3 | 3 |
| Report application Date of effect (from Dates metadata) and distinguish it from entry-into-force date | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
