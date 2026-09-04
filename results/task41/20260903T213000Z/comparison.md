# browser_task_051-cultural-object-metadata-20260902T205736Z verifier comparison

Frozen rubric SHA-256: `91b7ec976b23af1ef9ce50b4a78f793427d7df837dbeb95f9f2f35634301ed4b`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/16 (0.500) | False | 12 | 12 | 0 | 69,631 | 9,043 | 78,674 |
| DOM-model | 13/16 (0.812) | False | 22 | 22 | 0 | 84,624 | 13,503 | 98,127 |

DOM-model minus screenshot tokens: **+19,453 (+24.73%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the exact Europeana record 90402/SK_A_2344 (The Milkmaid) | 3 | 3 | 3 | 3 | 3 |
| Report title exactly as displayed | 2 | 2 | 2 | 2 | 2 |
| Report creation date exactly as displayed | 2 | 0 | 0 | 0 | 2 |
| Report providing institution | 2 | 0 | 2 | 2 | 2 |
| Report type of item | 2 | 0 | 0 | 1 | 0 |
| Report displayed rights statement exactly | 3 | 0 | 2 | 0 | 2 |
| Report identifier exactly | 2 | 0 | 2 | 0 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
