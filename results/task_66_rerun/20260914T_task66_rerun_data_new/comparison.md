# browser_task_066-mathematical-sequence-reference-20260914T084957Z verifier comparison

Frozen rubric SHA-256: `968c547760de5254b62f0c731bf1ac922008b64893841d0bd4bc9c4da5c8b24c`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/16 (1.000) | True | 12 | 12 | 0 | 69,467 | 6,843 | 76,310 |
| DOM-model | 15.5/16 (0.969) | True | 12 | 12 | 0 | 63,535 | 7,797 | 71,332 |

DOM-model minus screenshot tokens: **-4,978 (-6.52%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use MathWorld Fibonacci Number page as source | 2 | 2 | 2 | 2 | 2 |
| Record displayed Fibonacci recurrence (exact notation) | 3 | 2 | 3 | 3 | 2.5 |
| Record initial conditions (exact notation) | 3 | 0 | 1 | 3 | 3 |
| Report first eight positive-index Fibonacci numbers (F1–F8 only) | 4 | 4 | 4 | 4 | 4 |
| Report linked OEIS identifier (exact as displayed) | 2 | 2 | 2 | 2 | 2 |
| Respect stopping condition and scope constraints | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
