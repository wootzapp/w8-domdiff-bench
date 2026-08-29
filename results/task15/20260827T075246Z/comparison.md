# github-heavy-03-cpython-workflow-inspection-20260821T060844Z verifier comparison

Frozen rubric SHA-256: `16d070221b4378ff6e347dfc9309b1d15a98e56d81ba0433ccd02a2079cda8bc`  
Denominator: `28`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 11/28 (0.393) | False | 12 | 12 | 0 | 84,998 | 10,227 | 95,225 |
| DOM-model | 13.5/28 (0.482) | False | 14 | 14 | 0 | 102,601 | 10,623 | 113,224 |

DOM-model minus screenshot tokens: **+17,999 (+18.90%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Inspect .github/workflows YAML files in python/cpython repository (public GitHub UI) | 3 | 3 | 3 | 2 | 3 |
| Identify the workflow responsible for running the main test suite on pull requests | 4 | 4 | 4 | 2 | 2 |
| Report trigger events for the main PR test workflow | 3 | 3 | 3 | 2 | 2 |
| Report declared permissions for the main PR test workflow (including absence vs empty) | 3 | 3 | 1 | 3 | 2.5 |
| Report OS matrix and Python-version matrix (if present) for the main PR test workflow | 4 | 4 | 4 | 0 | 0.5 |
| Report the exact test command used by the main PR test workflow | 4 | 4 | 4 | 0 | 0 |
| Identify the separate documentation workflow and report its file path and triggers | 4 | 4 | 4 | 0 | 2.5 |
| Adhere to constraints: public GitHub only, no sign-in, no editing/downloading, stop after verifying both workflows | 3 | 3 | 3 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
