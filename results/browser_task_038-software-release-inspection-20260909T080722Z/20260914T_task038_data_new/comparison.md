# browser_task_038-software-release-inspection-20260909T080722Z verifier comparison

Frozen rubric SHA-256: `ba30b78805709c6d54a42713b2764923163d272ac3e0bdf2f524ce31b6d06a9f`  
Denominator: `14`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/14 (1.000) | False | 12 | 12 | 0 | 66,061 | 6,898 | 72,959 |
| DOM-model | 12/14 (0.857) | False | 12 | 12 | 0 | 68,583 | 7,207 | 75,790 |

DOM-model minus screenshot tokens: **+2,831 (+3.88%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access GitLab Runner releases list (no sign-in) | 2 | 2 | 2 | 2 | 2 |
| Select the first qualifying non-prerelease tag | 4 | 4 | 2 | 4 | 2 |
| Record the qualifying release tag and exact created date | 3 | 3 | 3 | 3 | 3 |
| Record first three 'Other' asset link names (exclude Source code archives, preserve order, no downloads) | 5 | 5 | 0 | 5 | 5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
