# browser_task_068-vehicle-vin-decoding-20260914T085208Z verifier comparison

Frozen rubric SHA-256: `0b31852b1b0027ad6fd0446aa26d8eab82e58cefa4dc503e87d599200e64de25`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/16 (1.000) | True | 12 | 12 | 0 | 81,512 | 9,917 | 91,429 |
| DOM-model | 16/16 (1.000) | True | 20 | 20 | 0 | 106,176 | 18,134 | 124,310 |

DOM-model minus screenshot tokens: **+32,881 (+35.96%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the official NHTSA vPIC DecodeVinValues response for the specified VIN | 3 | 3 | 3 | 3 | 3 |
| Record Make from Results object | 1 | 1 | 1 | 1 | 1 |
| Record Model from Results object | 1 | 1 | 1 | 1 | 1 |
| Record ModelYear from Results object | 1 | 1 | 1 | 1 | 1 |
| Record BodyClass from Results object | 1 | 1 | 1 | 1 | 1 |
| Record EngineCylinders from Results object | 1 | 1 | 1 | 1 | 1 |
| Record EngineHP from Results object | 1 | 1 | 1 | 1 | 1 |
| Record PlantCity from Results object | 1 | 1 | 1 | 1 | 1 |
| Record PlantState from Results object | 1 | 1 | 1 | 1 | 1 |
| Record PlantCountry from Results object | 1 | 1 | 1 | 1 | 1 |
| Record ErrorText exactly as returned | 2 | 2 | 2 | 2 | 2 |
| Stopping condition compliance (stop after recording all requested fields) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
