# browser_task_065-public-transport-interchange-inspection-20260909T084306Z verifier comparison

Frozen rubric SHA-256: `543008185397c93552f530d9f11bfcefcbae78868854f88a68ac4f0697038ac0`  
Denominator: `23`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 4/23 (0.174) | False | 60 | 60 | 0 | 295,496 | 19,583 | 315,079 |
| DOM-model | 2/23 (0.087) | False | 84 | 84 | 0 | 342,232 | 32,375 | 374,607 |

DOM-model minus screenshot tokens: **+59,528 (+18.89%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Retrieve/use the official TfL StopPoint response for HUBKGX (or report inability to access it) | 2 | 2 | 2 | 2 | 2 |
| Report StopPoint ID | 2 | 2 | 2 | 0 | 0 |
| Report common name | 2 | 2 | 2 | 1 | 0 |
| Report latitude and longitude | 3 | 3 | 3 | 1 | 0 |
| Report every top-level transport mode | 4 | 4 | 4 | 0 | 0 |
| Report Zone value from additionalProperties (key = Zone) | 3 | 3 | 3 | 0 | 0 |
| Report every Tube line identifier from lineModeGroups where modeName = tube | 5 | 5 | 5 | 0 | 0 |
| Stopping condition satisfied (no extra fields beyond requested set) | 2 | 2 | 2 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
