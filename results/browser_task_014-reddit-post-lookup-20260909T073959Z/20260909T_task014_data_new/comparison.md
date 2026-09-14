# browser_task_014-reddit-post-lookup-20260909T073959Z verifier comparison

Frozen rubric SHA-256: `c8d413abd02711e0a624ff57822d29e0edd9802c5c75a62c9d86a86d76b9962a`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17/17 (1.000) | False | 10 | 10 | 0 | 56,646 | 6,067 | 62,713 |
| DOM-model | 17/17 (1.000) | False | 11 | 11 | 0 | 55,639 | 8,671 | 64,310 |

DOM-model minus screenshot tokens: **+1,597 (+2.55%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Apply required Reddit sorting and time filter (Top + past month) in r/MachineLearning | 4 | 4 | 4 | 4 | 4 |
| Open the highest-ranked post under the applied filters | 3 | 3 | 3 | 3 | 3 |
| Report exact post details: title, author, score, and comment count | 5 | 5 | 5 | 5 | 5 |
| Respect constraints: no sign-in and no interactions (vote/comment/save/create) | 3 | 3 | 3 | 3 | 3 |
| Stop at the specified stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
