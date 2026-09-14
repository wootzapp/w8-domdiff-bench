# browser_task_047-regulatory-api-search-20260909T100115Z verifier comparison

Frozen rubric SHA-256: `77f681aa2e64f1e70e5391e7218bc122c01fbe9a0f59bdf56758b7fd900be0af`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 4/20 (0.200) | False | 18 | 18 | 0 | 126,030 | 14,954 | 140,984 |
| DOM-model | 4/20 (0.200) | False | 29 | 29 | 0 | 137,151 | 25,821 | 162,972 |

DOM-model minus screenshot tokens: **+21,988 (+15.60%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the specified official Federal Register API endpoint with the exact query (or clearly report access failure) | 2 | 0 | 1 | 2 | 2 |
| Rely only on the response top-level "results" array (no link-following or extra sources) | 2 | 2 | 2 | 2 | 2 |
| Report the first up to three API results in returned order (newest first) and stop | 4 | 4 | 4 | 0 | 0 |
| Result 1: Provide title, every listed agency, document type, and publication date (as present in API payload) | 4 | 4 | 4 | 0 | 0 |
| Result 2: Provide title, every listed agency, document type, and publication date (as present in API payload) | 4 | 4 | 4 | 0 | 0 |
| Result 3: Provide title, every listed agency, document type, and publication date (as present in API payload) | 4 | 4 | 4 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
