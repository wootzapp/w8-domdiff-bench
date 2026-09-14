# browser_task_088-television-season-analysis-20260914T091851Z verifier comparison

Frozen rubric SHA-256: `d2fdb96b6054746d69994126190fbfb081d8e7b2a8f1e5d5a29a41f39492c3a2`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 22/22 (1.000) | True | 12 | 12 | 0 | 76,679 | 7,797 | 84,476 |
| DOM-model | 22/22 (1.000) | True | 32 | 32 | 0 | 172,566 | 20,739 | 193,305 |

DOM-model minus screenshot tokens: **+108,829 (+128.83%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Restrict analysis to TVMaze episode list for show 82 and season = 1 only | 4 | 4 | 4 | 4 | 4 |
| Report correct season-1 episode count | 3 | 3 | 3 | 3 | 3 |
| Report boundary episodes (first and final) for season 1 with required fields | 4 | 4 | 4 | 4 | 4 |
| Identify maximum non-null rating.average among season-1 episodes using rating.average for ranking | 4 | 4 | 4 | 4 | 4 |
| Report all season-1 episodes tied for highest rating with required fields (no arbitrary tie-breaking) | 5 | 5 | 3 | 5 | 5 |
| Stopping condition adherence (report only requested outputs) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
