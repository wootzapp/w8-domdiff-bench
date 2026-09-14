# browser_task_083-marine-taxonomy-20260914T091225Z verifier comparison

Frozen rubric SHA-256: `220c4bbaf2708ab9dd1684f51db25d10dabb735d5bfbac6a340dd33641cd8d8e`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/16 (1.000) | True | 12 | 12 | 0 | 66,500 | 6,261 | 72,761 |
| DOM-model | 15/16 (0.938) | True | 16 | 16 | 0 | 77,077 | 8,252 | 85,329 |

DOM-model minus screenshot tokens: **+12,568 (+17.27%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the specified WoRMS taxon record (AphiaID 137106) | 3 | 0 | 0 | 3 | 3 |
| Report identity fields: AphiaID and scientific name with authority (from the main record header) | 3 | 0 | 0 | 3 | 3 |
| Report taxonomic status from the record (without substituting synonyms) | 2 | 0 | 0 | 2 | 2 |
| Report genus and family from the Classification section | 3 | 0 | 0 | 3 | 3 |
| Report displayed environment states (affirmed vs struck-through) | 3 | 0 | 0 | 3 | 2 |
| Stopping condition: stop after recording requested fields only | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
