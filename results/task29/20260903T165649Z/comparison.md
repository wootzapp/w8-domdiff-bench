# browser_task_033-software-package-metadata-20260902T193608Z verifier comparison

Frozen rubric SHA-256: `46ee2364509495df70963bcb909cda3a115c3c27bcf2257464b9c0f3ebf129b9`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/20 (0.800) | False | 16 | 16 | 0 | 102,935 | 12,151 | 115,086 |
| DOM-model | 20/20 (1.000) | True | 25 | 25 | 0 | 128,239 | 20,655 | 148,894 |

DOM-model minus screenshot tokens: **+33,808 (+29.38%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the correct PyPI project page for Requests and identify the latest displayed release | 4 | 4 | 4 | 4 | 4 |
| Report latest release version | 2 | 2 | 2 | 2 | 2 |
| Report latest release upload date | 2 | 2 | 2 | 2 | 2 |
| Report 'Requires Python' value | 2 | 2 | 0 | 2 | 2 |
| Report license | 2 | 2 | 0 | 2 | 2 |
| Count and report the number of 'Download files' listed for the latest release | 3 | 3 | 3 | 1 | 3 |
| Respect constraints and stopping condition | 5 | 5 | 5 | 3 | 5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
