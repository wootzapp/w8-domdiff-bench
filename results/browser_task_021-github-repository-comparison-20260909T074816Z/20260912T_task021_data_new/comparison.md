# browser_task_021-github-repository-comparison-20260909T074816Z verifier comparison

Frozen rubric SHA-256: `debcba8462f7fdd11da93321b7a54b61c17e70bd24a971559faa0669d7264395`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 20/20 (1.000) | True | 14 | 14 | 0 | 84,272 | 8,111 | 92,383 |
| DOM-model | 20/20 (1.000) | True | 16 | 16 | 0 | 109,552 | 10,084 | 119,636 |

DOM-model minus screenshot tokens: **+27,253 (+29.50%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Record GitHub metrics for vllm-project/vllm | 4 | 4 | 0 | 4 | 4 |
| Record GitHub metrics for ggml-org/llama.cpp | 4 | 4 | 0 | 4 | 4 |
| Record GitHub metrics for sgl-project/sglang | 4 | 4 | 0 | 4 | 4 |
| Present results in a table | 3 | 3 | 3 | 3 | 3 |
| Rank repositories by stars | 3 | 3 | 3 | 3 | 3 |
| Respect constraints (no sign-in and no repository interactions) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
