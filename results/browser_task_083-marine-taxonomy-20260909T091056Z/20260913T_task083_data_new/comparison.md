# browser_task_083-marine-taxonomy-20260909T091056Z verifier comparison

Frozen rubric SHA-256: `220c4bbaf2708ab9dd1684f51db25d10dabb735d5bfbac6a340dd33641cd8d8e`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/16 (1.000) | True | 12 | 12 | 0 | 67,178 | 6,549 | 73,727 |
| DOM-model | 14/16 (0.875) | False | 16 | 16 | 0 | 77,213 | 9,710 | 86,923 |

DOM-model minus screenshot tokens: **+13,196 (+17.90%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the specified WoRMS taxon record (AphiaID 137106) | 3 | 1 | 3 | 3 | 3 |
| Report identity fields: AphiaID and scientific name with authority (from the main record header) | 3 | 0 | 3 | 3 | 3 |
| Report taxonomic status from the record (without substituting synonyms) | 2 | 0 | 2 | 2 | 2 |
| Report genus and family from the Classification section | 3 | 0 | 3 | 3 | 3 |
| Report displayed environment states (affirmed vs struck-through) | 3 | 0 | 1 | 3 | 1 |
| Stopping condition: stop after recording requested fields only | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
