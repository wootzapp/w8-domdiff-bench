# viewport-modern-22-cpython-workflow-inspection-20260829T084346Z verifier comparison

Frozen rubric SHA-256: `2158f2753928ee109cc23f6f910f89896b6bc0e507b54d2a1d5d7c813da2b40d`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/20 (0.500) | False | 14 | 14 | 0 | 77,640 | 7,864 | 85,504 |
| DOM-model | 7/20 (0.350) | False | 18 | 18 | 0 | 118,624 | 12,154 | 130,778 |

DOM-model minus screenshot tokens: **+45,274 (+52.95%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Locate and verify (from YAML) the PR main test-suite workflow under python/cpython/.github/workflows | 4 | 0 | 2 | 2 | 2 |
| Report required configuration fields for the main test-suite workflow (verified from YAML, or explicitly report inability to verify) | 8 | 0 | 0 | 2 | 0 |
| Identify the separate documentation workflow YAML and report its file path and triggers (verified from YAML, or explicitly report inability to verify) | 5 | 0 | 2 | 5 | 2 |
| Comply with browsing and stopping constraints | 3 | 1 | 3 | 1 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
