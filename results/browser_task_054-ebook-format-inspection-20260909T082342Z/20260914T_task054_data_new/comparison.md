# browser_task_054-ebook-format-inspection-20260909T082342Z verifier comparison

Frozen rubric SHA-256: `57a93ea7329943cb745b1d9a93d4314261802441f146263f525ee38ef06f7cf3`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/20 (0.500) | False | 12 | 12 | 0 | 81,712 | 10,408 | 92,120 |
| DOM-model | 14/20 (0.700) | False | 28 | 28 | 0 | 122,920 | 18,818 | 141,738 |

DOM-model minus screenshot tokens: **+49,618 (+53.86%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the correct Project Gutenberg eBook page (eBook #1342, Pride and Prejudice) | 2 | 2 | 2 | 2 | 2 |
| Report the Author | 2 | 0 | 0 | 2 | 2 |
| Report the Release Date (using the page label and exact displayed date) | 3 | 1 | 2 | 0 | 0 |
| Report the Last Update (using the page label and exact displayed date) | 3 | 0 | 0 | 0 | 0 |
| Report the Language | 2 | 2 | 2 | 2 | 2 |
| Check availability of format label: EPUB3 | 2 | 2 | 0 | 2 | 2 |
| Check availability of format label: Plain Text (accessible) | 2 | 2 | 0 | 0 | 2 |
| Check availability of format label: Download HTML (zip) | 2 | 2 | 0 | 0 | 2 |
| Respect task constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
