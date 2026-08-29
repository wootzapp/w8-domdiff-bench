# viewport-typescript-utilities-viewport-typescript-utility-types-20260826T184953Z verifier comparison

Frozen rubric SHA-256: `37a3d6b6f7c6005f50d068051f3295c4b775434f666b7a0e232039c88701c129`  
Denominator: `27`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/27 (0.481) | False | 19 | 19 | 0 | 149,823 | 14,302 | 164,125 |
| DOM-model | 27/27 (1.000) | True | 21 | 21 | 0 | 127,009 | 11,721 | 138,730 |

DOM-model minus screenshot tokens: **-25,395 (-15.47%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use TypeScript docs navigation/search to reach Utility Types reference | 3 | 3 | 3 | 3 | 3 |
| Report details for Pick utility type | 4 | 4 | 4 | 2 | 4 |
| Report details for Omit utility type | 4 | 4 | 4 | 2 | 4 |
| Report details for Exclude utility type | 4 | 4 | 4 | 1 | 4 |
| Report details for Extract utility type | 4 | 4 | 4 | 1 | 4 |
| Compare Pick, Omit, Exclude, and Extract based on docs | 3 | 3 | 3 | 2 | 3 |
| Navigate to keyof type operator page using TS docs UI and explain relationship to Pick/Omit per examples | 5 | 5 | 5 | 2 | 5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
