# viewport-modern-2-job-listing-extraction-20260829T074612Z verifier comparison

Frozen rubric SHA-256: `a7e99908c99f87f84cb13fa8158e51519d08892dd942eae54246ec663b721b48`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/20 (0.500) | False | 29 | 29 | 0 | 170,609 | 16,157 | 186,766 |
| DOM-model | 12/20 (0.600) | False | 36 | 36 | 0 | 146,997 | 17,023 | 164,020 |

DOM-model minus screenshot tokens: **-22,746 (-12.18%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Microsoft Careers and attempt search for an Applied Scientist role in Redmond, WA | 3 | 3 | 3 | 3 | 3 |
| Open one relevant listing (Applied Scientist; Redmond, WA if available) and use it as the extraction source | 3 | 2 | 2 | 3 | 2 |
| Report the job number from the opened listing | 2 | 2 | 0 | 0 | 2 |
| Report the work-site arrangement from the opened listing | 2 | 2 | 0 | 0 | 2 |
| Extract two key responsibilities from the opened listing | 3 | 0 | 0 | 0 | 0 |
| Extract two preferred qualifications from the opened listing | 3 | 0 | 0 | 0 | 0 |
| Respect constraints and stopping condition (no sign-in, no applying, no form submission; stop after one listing) | 4 | 4 | 4 | 4 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
