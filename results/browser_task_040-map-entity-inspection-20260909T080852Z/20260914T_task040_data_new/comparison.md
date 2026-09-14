# browser_task_040-map-entity-inspection-20260909T080852Z verifier comparison

Frozen rubric SHA-256: `2f5a5cab05458d03a0e495ac223e152659863ab23a1d08ce8b9ad6bfd8dcac8e`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12.5/16 (0.781) | False | 13 | 13 | 0 | 77,842 | 9,659 | 87,501 |
| DOM-model | 13/16 (0.812) | False | 15 | 15 | 0 | 82,213 | 11,956 | 94,169 |

DOM-model minus screenshot tokens: **+6,668 (+7.62%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access OpenStreetMap search for 'British Museum, London' | 2 | 2 | 2 | 2 | 2 |
| Navigate to the exact British Museum OSM object page | 4 | 4 | 4 | 4 | 4 |
| Record displayed OSM object type and ID | 2 | 2 | 2 | 2 | 2 |
| Report addr:street tag value | 1 | 1 | 1 | 1 | 1 |
| Report addr:city tag value | 1 | 1 | 1 | 1 | 1 |
| Report addr:postcode tag value | 1 | 1 | 1 | 1 | 1 |
| Report tourism tag value | 1 | 1 | 1 | 0 | 0 |
| Report museum tag value | 1 | 1 | 1 | 0 | 0 |
| Report website tag value | 1 | 1 | 1 | 0 | 0 |
| Respect constraints (no sign-in/edit; stop after recording requested info) | 2 | 2 | 2 | 1.5 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
