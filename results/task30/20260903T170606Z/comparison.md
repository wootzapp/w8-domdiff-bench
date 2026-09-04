# browser_task_034-dependency-inspection-20260902T193655Z verifier comparison

Frozen rubric SHA-256: `295ffe6649d7b6bfbcba3f0b1a4768f274bf8bfc6959a7f790557aeba6a6a1d3`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 18/20 (0.900) | False | 12 | 12 | 0 | 72,629 | 8,895 | 81,524 |
| DOM-model | 19/20 (0.950) | False | 25 | 25 | 0 | 123,087 | 15,680 | 138,767 |

DOM-model minus screenshot tokens: **+57,243 (+70.22%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access RubyGems Rails gem page without signing in/downloading | 3 | 3 | 3 | 3 | 3 |
| Record latest displayed Rails version metadata | 5 | 0 | 0 | 3 | 4 |
| Record runtime dependency #1 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Record runtime dependency #2 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Record runtime dependency #3 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Record runtime dependency #4 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Record runtime dependency #5 in displayed order (name + requirement) | 2 | 2 | 2 | 2 | 2 |
| Stop after recording requested metadata and first five runtime dependencies | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
