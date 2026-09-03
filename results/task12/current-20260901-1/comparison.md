# viewport-modern-12-github-repository-comparison-20260829T075442Z verifier comparison

Frozen rubric SHA-256: `441f732aa19ee4c31967d923133ee134ce0beaf908d9f141773e1e8adaf07d78`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/20 (0.750) | False | 12 | 12 | 0 | 74,587 | 7,792 | 82,379 |
| DOM-model | 20/20 (1.000) | True | 15 | 15 | 0 | 96,790 | 7,862 | 104,652 |

DOM-model minus screenshot tokens: **+22,273 (+27.04%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Record stars/forks/open issues for vllm-project/vllm | 4 | 4 | 4 | 4 | 4 |
| Record stars/forks/open issues for ggml-org/llama.cpp | 4 | 4 | 4 | 4 | 4 |
| Record stars/forks/open issues for sgl-project/sglang | 4 | 4 | 4 | 1 | 4 |
| Present results in a table with repository names and all nine metrics | 3 | 3 | 3 | 2 | 3 |
| Rank repositories by stars | 2 | 2 | 2 | 1 | 2 |
| Comply with constraints: no sign-in and no repository modifications | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
