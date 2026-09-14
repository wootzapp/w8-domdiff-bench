# browser_task_085-asteroid-record-20260914T091428Z verifier comparison

Frozen rubric SHA-256: `30a92a02be1e3cbe99d28189166d1f6ad37b51219014af78d6ca5d00a9d40407`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 20/20 (1.000) | True | 12 | 12 | 0 | 73,546 | 7,501 | 81,047 |
| DOM-model | 20/20 (1.000) | True | 26 | 26 | 0 | 117,945 | 15,216 | 133,161 |

DOM-model minus screenshot tokens: **+52,114 (+64.30%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the supplied NASA/JPL SBDB response (99942 Apophis, phys-par=1) | 2 | 0 | 0 | 2 | 2 |
| Report object.fullname exactly | 2 | 0 | 0 | 2 | 2 |
| Report orbit class name and code from object.orbit_class | 3 | 0 | 0 | 3 | 3 |
| Report orbit.epoch exactly | 2 | 0 | 0 | 2 | 2 |
| Report absolute magnitude (H) value and uncertainty from phys_par | 3 | 0 | 0 | 3 | 3 |
| Report diameter value, uncertainty, and unit from phys_par | 4 | 0 | 0 | 4 | 4 |
| Report potentially hazardous asteroid flag from object.pha | 2 | 0 | 0 | 2 | 2 |
| Output scope: only requested fields; no extra SBDB fields | 2 | 2 | 1 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
