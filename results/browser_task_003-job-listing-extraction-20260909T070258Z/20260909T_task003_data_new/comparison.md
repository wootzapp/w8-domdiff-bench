# browser_task_003-job-listing-extraction-20260909T070258Z verifier comparison

Frozen rubric SHA-256: `6cb1ce774b4da7e22243c6a0ae5ffb597dc341935f8a53dfbce2c309d01e3fb2`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17/20 (0.850) | False | 58 | 58 | 0 | 278,622 | 17,104 | 295,726 |
| DOM-model | 17/20 (0.850) | False | 70 | 70 | 0 | 383,016 | 22,506 | 405,522 |

DOM-model minus screenshot tokens: **+109,796 (+37.13%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Microsoft Careers to search for an Applied Scientist role in/associated with Redmond, WA (or clearly report access blockers) | 3 | 3 | 3 | 3 | 3 |
| Open one relevant listing and stop after opening one (or report that no exact match exists) | 3 | 3 | 3 | 3 | 3 |
| Report the job number from the listing (or state it is not shown) | 2 | 0 | 0 | 2 | 2 |
| Report the work-site arrangement from the listing (or state it is not shown) | 2 | 0 | 0 | 2 | 2 |
| Report two key responsibilities from the listing | 3 | 0 | 0 | 0 | 0 |
| Report two preferred qualifications from the listing (or clearly state preferred qualifications are not listed) | 3 | 0 | 0 | 3 | 3 |
| Respect constraints (no sign-in, no application, no form submission) | 4 | 4 | 4 | 4 | 4 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
