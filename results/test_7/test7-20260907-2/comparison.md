# browser_task_054-ebook-format-inspection-20260905T114228Z verifier comparison

Frozen rubric SHA-256: `2dc6ea5c8c32703420ff5fe1ffccd592adb9904baa38622c211b44d89722b928`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10.5/20 (0.525) | False | 12 | 12 | 0 | 80,064 | 10,518 | 90,582 |
| DOM-model | 14/20 (0.700) | False | 20 | 20 | 0 | 103,293 | 20,979 | 124,272 |

DOM-model minus screenshot tokens: **+33,690 (+37.19%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Project Gutenberg eBook 1342 page (Pride and Prejudice) | 2 | 2 | 2 | 2 | 2 |
| Record author | 2 | 1 | 1 | 2 | 2 |
| Record Release Date (using Gutenberg label) | 3 | 1 | 2 | 0.5 | 0 |
| Record Last Update (using Gutenberg label) | 3 | 0 | 0 | 0 | 0 |
| Record language | 2 | 2 | 2 | 2 | 2 |
| Check availability of format: EPUB3 | 2 | 2 | 2 | 2 | 2 |
| Check availability of format: Plain Text (accessible) | 2 | 2 | 2 | 0 | 2 |
| Check availability of format: Download HTML (zip) | 2 | 2 | 2 | 0 | 2 |
| Respect stopping condition and constraints (no downloads; only named formats; stop after recording) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
