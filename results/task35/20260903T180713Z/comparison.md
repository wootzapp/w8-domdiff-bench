# browser_task_040-map-entity-inspection-20260902T194254Z verifier comparison

Frozen rubric SHA-256: `e23f20ead698f7ee7ac1513ceb084162195c4a8bd1fc3f4aa8b9390196556ba2`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17/20 (0.850) | False | 12 | 12 | 0 | 70,619 | 7,069 | 77,688 |
| DOM-model | 15/20 (0.750) | False | 18 | 18 | 0 | 86,678 | 12,240 | 98,918 |

DOM-model minus screenshot tokens: **+21,230 (+27.33%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate to OpenStreetMap search results for 'British Museum, London' and open an object page | 3 | 3 | 3 | 3 | 3 |
| Select the correct British Museum object (Great Russell Street, London) | 4 | 4 | 4 | 4 | 4 |
| Report displayed OSM object type and ID | 3 | 3 | 3 | 3 | 3 |
| Report tag values: addr:street, addr:city, addr:postcode | 4 | 4 | 4 | 4 | 4 |
| Report tag values: tourism, museum, website | 4 | 4 | 4 | 1 | 0 |
| Respect constraints: no sign-in/editing; stop after recording requested identifiers and tags | 2 | 2 | 2 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
