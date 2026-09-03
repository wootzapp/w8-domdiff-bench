# viewport-modern-25-feedback-and-ideas-engagement-report-20260829T084700Z verifier comparison

Frozen rubric SHA-256: `7547715cc8f3225196dd1bc0b041ef3e891a20417b2bb2a20668e656156ddba5`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6.5/20 (0.325) | False | 44 | 44 | 0 | 295,308 | 20,112 | 315,420 |
| DOM-model | 6/20 (0.300) | False | 51 | 51 | 0 | 542,841 | 29,744 | 572,585 |

DOM-model minus screenshot tokens: **+257,165 (+81.53%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Inspect up to 10 most recent substantive proposals in #feedback-and-ideas | 3 | 0 | 1 | 1 | 1 |
| Per-proposal required fields reported | 5 | 0 | 1 | 2 | 2 |
| Accuracy limited to visible Slack evidence (no hallucinations) | 4 | 0 | 0 | 0.5 | 0 |
| Rank top 3 proposals by combined visible reactions + replies (with tie-breaking) | 5 | 0 | 0 | 0 | 0 |
| Non-modification constraint respected | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
