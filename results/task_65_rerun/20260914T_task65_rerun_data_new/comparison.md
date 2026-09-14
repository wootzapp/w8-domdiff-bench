# browser_task_065-public-transport-interchange-inspection-20260914T084230Z verifier comparison

Frozen rubric SHA-256: `543008185397c93552f530d9f11bfcefcbae78868854f88a68ac4f0697038ac0`  
Denominator: `23`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/23 (0.652) | False | 68 | 68 | 0 | 328,063 | 20,209 | 348,272 |
| DOM-model | 16/23 (0.696) | False | 87 | 87 | 0 | 367,605 | 29,906 | 397,511 |

DOM-model minus screenshot tokens: **+49,239 (+14.14%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Retrieve/use the official TfL StopPoint response for HUBKGX (or report inability to access it) | 2 | 2 | 2 | 2 | 2 |
| Report StopPoint ID | 2 | 2 | 2 | 2 | 2 |
| Report common name | 2 | 1 | 2 | 2 | 2 |
| Report latitude and longitude | 3 | 3 | 3 | 0 | 0 |
| Report every top-level transport mode | 4 | 4 | 4 | 2 | 3 |
| Report Zone value from additionalProperties (key = Zone) | 3 | 3 | 3 | 0 | 0 |
| Report every Tube line identifier from lineModeGroups where modeName = tube | 5 | 5 | 5 | 5 | 5 |
| Stopping condition satisfied (no extra fields beyond requested set) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
