# browser_task_051-cultural-object-metadata-20260905T114131Z verifier comparison

Frozen rubric SHA-256: `91b7ec976b23af1ef9ce50b4a78f793427d7df837dbeb95f9f2f35634301ed4b`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/16 (0.625) | False | 16 | 16 | 0 | 97,257 | 11,417 | 108,674 |
| DOM-model | 12/16 (0.750) | False | 43 | 43 | 0 | 145,483 | 23,664 | 169,147 |

DOM-model minus screenshot tokens: **+60,473 (+55.65%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the exact Europeana record 90402/SK_A_2344 (The Milkmaid) | 3 | 3 | 3 | 3 | 3 |
| Report title exactly as displayed | 2 | 2 | 2 | 0 | 2 |
| Report creation date exactly as displayed | 2 | 0 | 0 | 2 | 2 |
| Report providing institution | 2 | 2 | 2 | 0 | 0 |
| Report type of item | 2 | 0 | 0 | 0 | 0 |
| Report displayed rights statement exactly | 3 | 0 | 0 | 3 | 3 |
| Report identifier exactly | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
