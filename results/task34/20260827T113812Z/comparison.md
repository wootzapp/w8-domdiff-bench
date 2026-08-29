# viewport-python-write-text-viewport-python-path-write-text-20260826T184804Z verifier comparison

Frozen rubric SHA-256: `ddb7b0444a936baa648b7c10a857056bc632f41e050c5e86615c55e0ce5742c8`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/12 (0.667) | False | 25 | 25 | 0 | 112,683 | 8,421 | 121,104 |
| DOM-model | 6/12 (0.500) | False | 29 | 29 | 0 | 108,208 | 10,109 | 118,317 |

DOM-model minus screenshot tokens: **-2,787 (-2.30%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the Python docs site search for the specified query | 3 | 3 | 3 | 3 | 3 |
| Open a relevant pathlib search result | 2 | 2 | 2 | 2 | 2 |
| Navigate to the Path.write_text entry within the documentation page | 2 | 2 | 1 | 2 | 1 |
| Report what Path.write_text returns | 2 | 0 | 0 | 1 | 0 |
| Report the Python version in which the newline parameter was added | 3 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
