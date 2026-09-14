# browser_task_085-asteroid-record-20260909T091202Z verifier comparison

Frozen rubric SHA-256: `30a92a02be1e3cbe99d28189166d1f6ad37b51219014af78d6ca5d00a9d40407`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 4/20 (0.200) | False | 19 | 19 | 0 | 109,574 | 11,765 | 121,339 |
| DOM-model | 2/20 (0.100) | False | 47 | 47 | 0 | 175,444 | 34,149 | 209,593 |

DOM-model minus screenshot tokens: **+88,254 (+72.73%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the supplied NASA/JPL SBDB response (99942 Apophis, phys-par=1) | 2 | 2 | 2 | 2 | 2 |
| Report object.fullname exactly | 2 | 2 | 2 | 0 | 0 |
| Report orbit class name and code from object.orbit_class | 3 | 3 | 3 | 0 | 0 |
| Report orbit.epoch exactly | 2 | 2 | 2 | 0 | 0 |
| Report absolute magnitude (H) value and uncertainty from phys_par | 3 | 3 | 3 | 0 | 0 |
| Report diameter value, uncertainty, and unit from phys_par | 4 | 4 | 4 | 0 | 0 |
| Report potentially hazardous asteroid flag from object.pha | 2 | 2 | 2 | 0 | 0 |
| Output scope: only requested fields; no extra SBDB fields | 2 | 2 | 2 | 2 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
