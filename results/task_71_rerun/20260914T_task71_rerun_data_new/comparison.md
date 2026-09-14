# browser_task_071-satellite-catalog-inspection-20260914T085508Z verifier comparison

Frozen rubric SHA-256: `549ae13c1406f1148bdbc102555365301e39694363e504bdd26ea03262b5520b`  
Denominator: `23`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 23/23 (1.000) | True | 12 | 12 | 0 | 71,639 | 7,151 | 78,790 |
| DOM-model | 23/23 (1.000) | True | 17 | 17 | 0 | 73,857 | 11,872 | 85,729 |

DOM-model minus screenshot tokens: **+6,939 (+8.81%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the CelesTrak SATCAT record for CATNR=25544 (or clearly report access failure) | 3 | 0 | 0 | 3 | 3 |
| Use the CelesTrak SATCAT record only (no switching objects/sources; no expanding codes) | 3 | 0 | 0 | 3 | 3 |
| Report identity fields (name, international designator, NORAD catalog number, object type) | 4 | 0 | 0 | 4 | 4 |
| Report status/ownership fields using raw codes (operational status code, owner code) | 3 | 0 | 0 | 3 | 3 |
| Report launch fields (launch date and launch-site code) using raw code | 3 | 0 | 0 | 3 | 3 |
| Report orbital parameters (period, inclination, apogee, perigee) with exact numbers/units | 4 | 0 | 0 | 4 | 4 |
| Honor stopping condition (stop after recording all requested fields from the displayed record) | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
