# browser_task_054-ebook-format-inspection-20260905T114228Z verifier comparison

Frozen rubric SHA-256: `2dc6ea5c8c32703420ff5fe1ffccd592adb9904baa38622c211b44d89722b928`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 9/20 (0.450) | False | 12 | 12 | 0 | 79,209 | 10,646 | 89,855 |
| DOM-model | 14/20 (0.700) | False | 28 | 28 | 0 | 123,013 | 18,573 | 141,586 |

DOM-model minus screenshot tokens: **+51,731 (+57.57%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Project Gutenberg eBook 1342 page (Pride and Prejudice) | 2 | 2 | 2 | 2 | 2 |
| Record author | 2 | 1 | 2 | 2 | 2 |
| Record Release Date (using Gutenberg label) | 3 | 2 | 1 | 0 | 0 |
| Record Last Update (using Gutenberg label) | 3 | 0 | 0 | 0 | 0 |
| Record language | 2 | 2 | 2 | 2 | 2 |
| Check availability of format: EPUB3 | 2 | 2 | 2 | 2 | 2 |
| Check availability of format: Plain Text (accessible) | 2 | 2 | 2 | 0 | 2 |
| Check availability of format: Download HTML (zip) | 2 | 2 | 2 | 0 | 2 |
| Respect stopping condition and constraints (no downloads; only named formats; stop after recording) | 2 | 2 | 2 | 1 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
