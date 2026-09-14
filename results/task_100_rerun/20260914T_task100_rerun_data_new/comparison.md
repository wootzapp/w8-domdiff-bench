# browser_task_100-earthquake-impact-record-inspection-20260914T093938Z verifier comparison

Frozen rubric SHA-256: `09b96da6445a00cd31d5960838b5e2b955b3c8f8c71da1313c4436b2bfb6d3d3`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/18 (0.833) | False | 12 | 12 | 0 | 68,660 | 6,879 | 75,539 |
| DOM-model | 17.5/18 (0.972) | True | 16 | 16 | 0 | 82,585 | 11,002 | 93,587 |

DOM-model minus screenshot tokens: **+18,048 (+23.89%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Event identity (title and displayed coordinates) | 3 | 0 | 0 | 3 | 3 |
| Intensity: Did You Feel It? (community MMI) | 2 | 0 | 0 | 0 | 2 |
| Intensity: ShakeMap (estimated MMI) | 2 | 0 | 0 | 2 | 2 |
| Ground Failure: Landslide Estimate (area and population exposure wording) | 3 | 0 | 0 | 3 | 3 |
| Ground Failure: Liquefaction Estimate (area and population exposure wording) | 3 | 0 | 0 | 3 | 3 |
| Origin card fields (review status, magnitude/type, depth, time, contributor) | 5 | 0 | 0 | 4 | 4.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
