# browser_task_011-arxiv-literature-search-20260909T073439Z verifier comparison

Frozen rubric SHA-256: `8154a1385faa60d8797d38cd3790be785d2a99dc77c1de0f22ef29f1e639920b`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 5/20 (0.250) | False | 24 | 24 | 0 | 162,507 | 16,522 | 179,029 |
| DOM-model | 6/20 (0.300) | False | 29 | 29 | 0 | 208,544 | 21,137 | 229,681 |

DOM-model minus screenshot tokens: **+50,652 (+28.29%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use arXiv Advanced Search with required filters (cs.LG, last 30 days, exact-title phrase, newest first) | 4 | 2 | 2 | 3 | 3 |
| Report the most recent matching paper (Paper #1) with required metadata | 3 | 0 | 0 | 0 | 0.5 |
| Report the 2nd most recent matching paper (Paper #2) with required metadata | 3 | 0 | 0 | 0 | 0 |
| Report the 3rd most recent matching paper (Paper #3) with required metadata | 3 | 0 | 0 | 0 | 0 |
| Verification checks recorded for each reported paper (category, date window, exact title phrase) | 5 | 0 | 5 | 0 | 1.5 |
| Stopping condition and constraints compliance (stop after 3; no login; no submissions/modifications) | 2 | 2 | 2 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
