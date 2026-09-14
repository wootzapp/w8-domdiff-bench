# browser_task_033-software-package-metadata-20260909T080442Z verifier comparison

Frozen rubric SHA-256: `e987f50a1508388eff19029c26216ddd2da448997aefb8b1e786319631b301d5`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/20 (0.800) | False | 12 | 12 | 0 | 73,248 | 8,249 | 81,497 |
| DOM-model | 17.5/20 (0.875) | True | 18 | 18 | 0 | 87,176 | 15,750 | 102,926 |

DOM-model minus screenshot tokens: **+21,429 (+26.29%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the Requests project page on PyPI (no sign-in) | 2 | 2 | 2 | 2 | 2 |
| Identify the latest displayed Requests release on the PyPI project page | 2 | 0 | 0 | 2 | 2 |
| Report version and upload date for the latest displayed release | 4 | 0 | 0 | 4 | 3 |
| Report Requires Python value for the latest displayed release | 3 | 0 | 0 | 3 | 3 |
| Report license for the latest displayed release | 3 | 0 | 0 | 3 | 3 |
| Count number of Download files listed for the latest displayed release | 4 | 0 | 0 | 1 | 3 |
| Respect constraints: no sign-in, no downloading/installing, no inference for missing metadata | 2 | 2 | 2 | 1 | 1.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
