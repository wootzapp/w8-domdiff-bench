# browser_task_001-reddit-ranking-20260909T070105Z verifier comparison

Frozen rubric SHA-256: `08053dc4514113054566c6ea9f0a4a9e785428805d5e8f12c9f129ddcf7b8fbb`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17/17 (1.000) | False | 10 | 10 | 0 | 55,544 | 5,626 | 61,170 |
| DOM-model | 17/17 (1.000) | False | 11 | 11 | 0 | 54,643 | 6,267 | 60,910 |

DOM-model minus screenshot tokens: **-260 (-0.43%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access r/LocalLLaMA on Reddit without signing in | 3 | 3 | 3 | 3 | 3 |
| Verify and apply 'Top' sort and 'This Week' time filter | 4 | 4 | 4 | 4 | 4 |
| Identify the #1 post under Top/This Week and report title and score | 5 | 5 | 5 | 5 | 5 |
| Respect constraints (no sign-in and no interactions like vote/comment/save/post) | 3 | 3 | 3 | 3 | 3 |
| Stop after recording the #1 post title and score | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
