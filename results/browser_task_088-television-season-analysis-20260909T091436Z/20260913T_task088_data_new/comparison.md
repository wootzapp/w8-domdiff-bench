# browser_task_088-television-season-analysis-20260909T091436Z verifier comparison

Frozen rubric SHA-256: `d2fdb96b6054746d69994126190fbfb081d8e7b2a8f1e5d5a29a41f39492c3a2`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/22 (0.591) | False | 42 | 42 | 0 | 216,169 | 16,295 | 232,464 |
| DOM-model | 9/22 (0.409) | False | 61 | 61 | 0 | 237,152 | 28,488 | 265,640 |

DOM-model minus screenshot tokens: **+33,176 (+14.27%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Restrict analysis to TVMaze episode list for show 82 and season = 1 only | 4 | 4 | 4 | 4 | 2 |
| Report correct season-1 episode count | 3 | 3 | 3 | 3 | 1 |
| Report boundary episodes (first and final) for season 1 with required fields | 4 | 4 | 4 | 4 | 2 |
| Identify maximum non-null rating.average among season-1 episodes using rating.average for ranking | 4 | 4 | 2 | 0 | 1 |
| Report all season-1 episodes tied for highest rating with required fields (no arbitrary tie-breaking) | 5 | 5 | 2 | 0 | 1 |
| Stopping condition adherence (report only requested outputs) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
