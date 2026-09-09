# browser_task_004-museum-film-lookup-20260909T071414Z verifier comparison

Frozen rubric SHA-256: `81ae2fa388b310f12bcd2015339158be8169f748f3fd281893eb5bec3606ab77`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 4/15 (0.267) | False | 12 | 12 | 0 | 66,195 | 7,809 | 74,004 |
| DOM-model | 5/15 (0.333) | False | 12 | 12 | 0 | 65,451 | 8,675 | 74,126 |

DOM-model minus screenshot tokens: **+122 (+0.16%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate DMNS site to Sturm Infinity Theater 'currently playing' information | 3 | 1 | 1 | 1 | 2 |
| Identify one film currently playing (title) | 3 | 0 | 3 | 0 | 0 |
| Report what the film is about (description/summary) | 2 | 0 | 2 | 0 | 0 |
| Report scheduled showtimes for the selected film | 4 | 0 | 4 | 0 | 0 |
| Respect constraints (no sign-in, no purchase, no seat reservation) and stop after one film | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
