# browser_task_010-official-documentation-lookup-20260909T073335Z verifier comparison

Frozen rubric SHA-256: `a8d84181ec0fe09d117995b4c001e182821ba5ac9631538a68d8a8bf32054f90`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6/18 (0.333) | False | 16 | 16 | 0 | 97,792 | 10,476 | 108,268 |
| DOM-model | 4.5/18 (0.250) | False | 35 | 35 | 0 | 160,833 | 27,256 | 188,089 |

DOM-model minus screenshot tokens: **+79,821 (+73.73%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Google Search to locate Gemini API documentation (attempt and navigation) | 3 | 3 | 3 | 3 | 2 |
| Documentation source is an official Google domain and no sign-in is performed | 3 | 3 | 3 | 1 | 1.5 |
| Record the documentation page title | 2 | 2 | 2 | 0 | 0 |
| Record the documentation domain | 2 | 2 | 2 | 0 | 0 |
| Identify the Python SDK shown in the documentation example | 3 | 3 | 3 | 0 | 0 |
| Identify the model used in the Python example | 3 | 3 | 3 | 0 | 0 |
| Stop after opening the official documentation and recording required fields | 2 | 2 | 2 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
