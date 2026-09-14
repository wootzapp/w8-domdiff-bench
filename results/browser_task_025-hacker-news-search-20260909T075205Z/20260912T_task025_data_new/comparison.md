# browser_task_025-hacker-news-search-20260909T075205Z verifier comparison

Frozen rubric SHA-256: `10d8137e689425c914ae0a893656b68a76d41e713d5413a3983bfa3b7d0fda40`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 19/20 (0.950) | True | 19 | 19 | 0 | 107,092 | 9,958 | 117,050 |
| DOM-model | 19/20 (0.950) | True | 28 | 28 | 0 | 161,210 | 20,284 | 181,494 |

DOM-model minus screenshot tokens: **+64,444 (+55.06%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Algolia Hacker News search for query 'LLM' | 3 | 3 | 3 | 3 | 3 |
| Apply required filters: Show HN posts and past-year time window | 4 | 4 | 4 | 4 | 4 |
| Sort results by points (descending) and verify sort order | 3 | 0 | 0 | 2 | 2 |
| Report top matching results with required fields | 6 | 3 | 0 | 6 | 6 |
| Respect constraints and stopping condition | 4 | 4 | 4 | 4 | 4 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
