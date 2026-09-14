# browser_task_039-technical-parameter-extraction-20260909T080752Z verifier comparison

Frozen rubric SHA-256: `e09a0ab5237e118cd5f3c386ff2a529e59b9248793cb3808834b1af12137779e`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/12 (0.833) | False | 18 | 18 | 0 | 94,319 | 8,032 | 102,351 |
| DOM-model | 10/12 (0.833) | False | 21 | 21 | 0 | 110,976 | 10,236 | 121,212 |

DOM-model minus screenshot tokens: **+18,861 (+18.43%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Report meaning and default for .spec.strategy.rollingUpdate.maxUnavailable | 4 | 4 | 4 | 4 | 4 |
| Report meaning and default for .spec.strategy.rollingUpdate.maxSurge | 4 | 4 | 4 | 4 | 4 |
| Report meaning and default for .spec.progressDeadlineSeconds | 4 | 4 | 4 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
