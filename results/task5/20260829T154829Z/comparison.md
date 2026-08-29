# viewport-modern-5-official-documentation-lookup-20260829T074921Z verifier comparison

Frozen rubric SHA-256: `a94c72e687adb2f66a294d2b151bb27fc53f4888441e2875e0e17bf645bd20b1`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 2/17 (0.118) | False | 12 | 12 | 0 | 69,706 | 7,300 | 77,006 |
| DOM-model | 12/17 (0.706) | False | 15 | 15 | 0 | 70,655 | 8,684 | 79,339 |

DOM-model minus screenshot tokens: **+2,333 (+3.03%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Find and open Google's official Gemini API documentation page (official Google domain) | 4 | 4 | 2 | 0 | 3 |
| Report the page title of the official Gemini API documentation page | 2 | 2 | 0 | 0 | 0 |
| Report the domain of the documentation source | 2 | 2 | 0 | 0 | 0 |
| Identify the Python SDK shown in the documentation's Python example | 3 | 3 | 1 | 0 | 3 |
| Identify the model used in the Python example on that documentation page | 3 | 3 | 1 | 0 | 3 |
| Respect constraints and stopping condition (no sign-in, no API key creation, no code execution; stop after recording required fields) | 3 | 3 | 3 | 2 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
