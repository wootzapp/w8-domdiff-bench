# browser_task_055-archive-item-metadata-20260902T210259Z verifier comparison

Frozen rubric SHA-256: `6f91e5acc54931cf49fed11e9fa7d95d9d9ccea987ebcff0c96a051eaeafa5bd`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 20/20 (1.000) | True | 12 | 12 | 0 | 70,174 | 7,126 | 77,300 |
| DOM-model | 13/20 (0.650) | False | 15 | 15 | 0 | 78,018 | 10,303 | 88,321 |

DOM-model minus screenshot tokens: **+11,021 (+14.26%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the specified Internet Archive item (prideprejudice00aust) | 2 | 2 | 2 | 2 | 2 |
| Report publication year | 2 | 2 | 2 | 2 | 2 |
| Report publisher | 2 | 2 | 2 | 2 | 2 |
| Report language | 2 | 2 | 2 | 2 | 2 |
| List all displayed Topics | 4 | 2 | 2 | 4 | 4 |
| Check download availability: EPUB | 2 | 2 | 2 | 2 | 0 |
| Check download availability: FULL TEXT | 2 | 2 | 2 | 2 | 0 |
| Check download availability: B/W PDF | 2 | 2 | 2 | 2 | 0 |
| Respect interaction constraints (no download/borrow/sign-in/add to collection) and stop after recording requested info | 2 | 2 | 2 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
