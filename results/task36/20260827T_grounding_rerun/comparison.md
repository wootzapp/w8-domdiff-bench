# viewport-typescript-utilities-viewport-typescript-utility-types-20260826T184953Z verifier comparison

Frozen rubric SHA-256: `37a3d6b6f7c6005f50d068051f3295c4b775434f666b7a0e232039c88701c129`  
Denominator: `27`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/27 (0.593) | False | 20 | 20 | 0 | 157,557 | 14,963 | 172,520 |
| DOM-model | 11/27 (0.407) | False | 28 | 28 | 0 | 166,540 | 13,857 | 180,397 |

DOM-model minus screenshot tokens: **+7,877 (+4.57%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use TypeScript docs navigation/search to reach Utility Types reference | 3 | 3 | 3 | 3 | 3 |
| Report details for Pick utility type | 4 | 4 | 4 | 3 | 1 |
| Report details for Omit utility type | 4 | 4 | 4 | 3 | 1 |
| Report details for Exclude utility type | 4 | 4 | 4 | 1 | 1 |
| Report details for Extract utility type | 4 | 4 | 4 | 1 | 1 |
| Compare Pick, Omit, Exclude, and Extract based on docs | 3 | 3 | 3 | 2 | 1 |
| Navigate to keyof type operator page using TS docs UI and explain relationship to Pick/Omit per examples | 5 | 5 | 5 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
