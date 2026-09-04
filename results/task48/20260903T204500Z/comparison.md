# browser_task_059-software-product-requirements-20260902T210739Z verifier comparison

Frozen rubric SHA-256: `a00b1267410f44c5bf9f867727d36a692a39a8988496e933bf742c4d813ea795`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/22 (0.591) | False | 24 | 24 | 0 | 144,592 | 13,028 | 157,620 |
| DOM-model | 16/22 (0.727) | False | 37 | 37 | 0 | 222,113 | 21,561 | 243,674 |

DOM-model minus screenshot tokens: **+86,054 (+54.60%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Portal 2 store page on Steam (app/620) | 3 | 3 | 3 | 3 | 3 |
| Record Release Date, Developer, and Publisher (as displayed on Steam) | 4 | 4 | 4 | 4 | 4 |
| Record complete displayed 'All Reviews' summary (not Recent Reviews) | 4 | 0 | 0 | 0 | 4 |
| Record operating-system headings shown under System Requirements | 3 | 2 | 2 | 3 | 1 |
| Record minimum Storage requirement for each OS heading (Minimum, per heading) | 5 | 0 | 0 | 1 | 1 |
| Comply with constraints and stopping condition (no sign-in/purchase actions; stop after recording requested info) | 3 | 3 | 3 | 2 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
