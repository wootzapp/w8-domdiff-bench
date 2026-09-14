# browser_task_078-cross-endpoint-game-data-20260909T094544Z verifier comparison

Frozen rubric SHA-256: `fc0553ae76f7d38f74791ed0b8d2518a353fa3a7bbc068449bdc7ffe0bd460e1`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/20 (0.700) | False | 90 | 90 | 0 | 404,496 | 19,763 | 424,259 |
| DOM-model | 5/20 (0.250) | False | 113 | 113 | 0 | 452,081 | 25,803 | 477,884 |

DOM-model minus screenshot tokens: **+53,625 (+12.64%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the supplied Pikachu Pokémon response and its returned species.url | 3 | 0 | 0 | 1 | 0 |
| Report required Pokémon fields (id, raw height, raw weight, base_experience) | 4 | 0 | 4 | 4 | 4 |
| Report all types in slot order using exact API strings | 3 | 0 | 3 | 3 | 0 |
| Compute and report the highest base stat (include ties) from complete stats array | 4 | 0 | 4 | 4 | 0 |
| Open species.url and report species fields (color.name, habitat.name, capture_rate, generation.name) | 4 | 0 | 0 | 0 | 0 |
| Stop after recording all requested fields (no extra/unrequested outputs) | 2 | 2 | 2 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
