# viewport-modern-7-hugging-face-model-metadata-20260829T075129Z verifier comparison

Frozen rubric SHA-256: `9987bb9c357f375553c846717d9773950b4d02729bd79c7fa2effa5f2a614def`  
Denominator: `13`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/13 (1.000) | True | 10 | 10 | 0 | 54,789 | 5,282 | 60,071 |
| DOM-model | 13/13 (1.000) | True | 37 | 37 | 0 | 199,389 | 16,558 | 215,947 |

DOM-model minus screenshot tokens: **+155,876 (+259.49%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the correct Hugging Face repository page (meta-llama/Llama-3.1-8B-Instruct) and rely on visible metadata | 2 | 2 | 2 | 2 | 2 |
| Report the license name from repository metadata | 3 | 3 | 3 | 3 | 3 |
| Report the current likes count from repository metadata | 3 | 3 | 3 | 3 | 3 |
| Determine whether the repository is gated (from visible UI evidence) | 3 | 3 | 3 | 3 | 3 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
