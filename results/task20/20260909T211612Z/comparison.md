# viewport-modern-20-coursera-beginner-course-comparison-20260829T083621Z verifier comparison

Frozen rubric SHA-256: `4ec0fbaa199566f7c2bee19ddff558ed44514b58833bd7e83a2aafca22fb1767`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/20 (0.400) | False | 107 | 107 | 0 | 560,313 | 25,766 | 586,079 |
| DOM-model | 6/20 (0.300) | False | 117 | 117 | 0 | 619,747 | 28,674 | 648,421 |

DOM-model minus screenshot tokens: **+62,342 (+10.64%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Start from Coursera homepage and perform search for beginner project-management courses | 3 | 3 | 3 | 3 | 3 |
| Open and identify first relevant beginner project-management course result | 2 | 2 | 2 | 2 | 2 |
| Open and identify second relevant beginner project-management course result | 2 | 0 | 0 | 0 | 0 |
| Extract required comparison attributes for both courses | 6 | 0 | 0 | 2 | 0 |
| Provide a clear side-by-side comparison | 3 | 0 | 0 | 0 | 0 |
| Recommend the shorter well-rated option (without enrolling) | 3 | 0 | 0 | 0 | 0 |
| Avoid enrolling or crossing critical commitment steps | 1 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
