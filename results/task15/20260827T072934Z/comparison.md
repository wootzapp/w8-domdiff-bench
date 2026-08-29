# github-heavy-03-cpython-workflow-inspection-20260821T060844Z verifier comparison

Frozen rubric SHA-256: `16d070221b4378ff6e347dfc9309b1d15a98e56d81ba0433ccd02a2079cda8bc`  
Denominator: `28`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/28 (0.536) | False | 12 | 12 | 0 | 85,234 | 10,215 | 95,449 |
| DOM-model | 14/28 (0.500) | False | 14 | 14 | 0 | 103,042 | 9,384 | 112,426 |

DOM-model minus screenshot tokens: **+16,977 (+17.79%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Inspect .github/workflows YAML files in python/cpython repository (public GitHub UI) | 3 | 3 | 3 | 2 | 3 |
| Identify the workflow responsible for running the main test suite on pull requests | 4 | 4 | 4 | 4 | 2 |
| Report trigger events for the main PR test workflow | 3 | 3 | 3 | 2 | 2 |
| Report declared permissions for the main PR test workflow (including absence vs empty) | 3 | 3 | 3 | 3 | 3 |
| Report OS matrix and Python-version matrix (if present) for the main PR test workflow | 4 | 4 | 4 | 1 | 0 |
| Report the exact test command used by the main PR test workflow | 4 | 4 | 4 | 0 | 0 |
| Identify the separate documentation workflow and report its file path and triggers | 4 | 4 | 4 | 1 | 2 |
| Adhere to constraints: public GitHub only, no sign-in, no editing/downloading, stop after verifying both workflows | 3 | 3 | 3 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
