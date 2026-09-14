# browser_task_032-technical-documentation-inspection-20260909T080346Z verifier comparison

Frozen rubric SHA-256: `694dab3808aea3a9751b6e53ef19bee73f42a8c06b3be48a3b1c415cd8170d46`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/20 (0.300) | False | 12 | 12 | 0 | 77,232 | 9,421 | 86,653 |
| DOM-model | 4/20 (0.200) | False | 23 | 23 | 0 | 128,765 | 18,149 | 146,914 |

DOM-model minus screenshot tokens: **+60,261 (+69.54%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Record formal definition: initial value | 3 | 0 | 0 | 0 | 1 |
| Record formal definition: applies to | 3 | 3 | 3 | 0 | 0 |
| List all keyword values shown in the current formal syntax | 4 | 0 | 0 | 4 | 2 |
| Report earliest supported desktop Chrome version for base property | 2 | 2 | 0 | 0 | 0 |
| Report earliest supported desktop Firefox version for base property | 2 | 2 | 0 | 0 | 0 |
| Report earliest supported desktop Safari version for base property | 2 | 1 | 0 | 0 | 0 |
| Respect task constraints and stopping condition | 4 | 4 | 4 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
