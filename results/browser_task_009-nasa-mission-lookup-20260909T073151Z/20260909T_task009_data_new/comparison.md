# browser_task_009-nasa-mission-lookup-20260909T073151Z verifier comparison

Frozen rubric SHA-256: `d8501aa855b5b07aec67fd374fcfe17455c57c18ab59a631d96ed88fe1d6fe4d`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/20 (0.800) | False | 20 | 20 | 0 | 121,878 | 13,041 | 134,919 |
| DOM-model | 19/20 (0.950) | True | 33 | 33 | 0 | 144,408 | 19,182 | 163,590 |

DOM-model minus screenshot tokens: **+28,671 (+21.25%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use NASA’s website as the source of truth | 3 | 3 | 3 | 3 | 3 |
| Identify the next planned Artemis mission | 4 | 4 | 4 | 0 | 3 |
| Report mission name | 2 | 2 | 2 | 2 | 2 |
| Report planned launch year | 3 | 0 | 0 | 3 | 3 |
| Report destination | 2 | 2 | 2 | 2 | 2 |
| Report primary objective | 3 | 3 | 3 | 3 | 3 |
| Respect constraints (no sign-in, no registration) and stopping condition | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
