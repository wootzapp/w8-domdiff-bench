# viewport-python-write-text-viewport-python-path-write-text-20260826T184804Z verifier comparison

Frozen rubric SHA-256: `ddb7b0444a936baa648b7c10a857056bc632f41e050c5e86615c55e0ce5742c8`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 9/12 (0.750) | False | 24 | 24 | 0 | 106,233 | 8,941 | 115,174 |
| DOM-model | 7/12 (0.583) | False | 40 | 40 | 0 | 143,981 | 14,326 | 158,307 |

DOM-model minus screenshot tokens: **+43,133 (+37.45%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the Python docs site search for the specified query | 3 | 3 | 3 | 3 | 3 |
| Open a relevant pathlib search result | 2 | 2 | 2 | 2 | 2 |
| Navigate to the Path.write_text entry within the documentation page | 2 | 2 | 2 | 2 | 2 |
| Report what Path.write_text returns | 2 | 0 | 0 | 2 | 0 |
| Report the Python version in which the newline parameter was added | 3 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
