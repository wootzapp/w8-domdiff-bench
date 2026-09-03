# viewport-modern-2-job-listing-extraction-20260829T074612Z verifier comparison

Frozen rubric SHA-256: `a7e99908c99f87f84cb13fa8158e51519d08892dd942eae54246ec663b721b48`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/20 (0.500) | False | 30 | 30 | 0 | 173,576 | 15,883 | 189,459 |
| DOM-model | 14/20 (0.700) | False | 32 | 32 | 0 | 134,584 | 13,886 | 148,470 |

DOM-model minus screenshot tokens: **-40,989 (-21.63%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Microsoft Careers and attempt search for an Applied Scientist role in Redmond, WA | 3 | 3 | 3 | 3 | 3 |
| Open one relevant listing (Applied Scientist; Redmond, WA if available) and use it as the extraction source | 3 | 1 | 2 | 3 | 3 |
| Report the job number from the opened listing | 2 | 0 | 0 | 0 | 2 |
| Report the work-site arrangement from the opened listing | 2 | 0 | 0 | 0 | 2 |
| Extract two key responsibilities from the opened listing | 3 | 0 | 0 | 0 | 0 |
| Extract two preferred qualifications from the opened listing | 3 | 0 | 0 | 0 | 0 |
| Respect constraints and stopping condition (no sign-in, no applying, no form submission; stop after one listing) | 4 | 4 | 4 | 4 | 4 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
