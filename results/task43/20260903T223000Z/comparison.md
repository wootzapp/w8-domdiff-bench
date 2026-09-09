# browser_task_054-ebook-format-inspection-20260902T210225Z verifier comparison

Frozen rubric SHA-256: `2dc6ea5c8c32703420ff5fe1ffccd592adb9904baa38622c211b44d89722b928`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/20 (0.650) | False | 12 | 12 | 0 | 83,130 | 11,049 | 94,179 |
| DOM-model | 12/20 (0.600) | False | 28 | 28 | 0 | 117,373 | 20,123 | 137,496 |

DOM-model minus screenshot tokens: **+43,317 (+45.99%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Project Gutenberg eBook 1342 page (Pride and Prejudice) | 2 | 2 | 2 | 2 | 2 |
| Record author | 2 | 0 | 2 | 2 | 0 |
| Record Release Date (using Gutenberg label) | 3 | 0 | 1 | 0 | 3 |
| Record Last Update (using Gutenberg label) | 3 | 0 | 0 | 0 | 3 |
| Record language | 2 | 2 | 2 | 2 | 0 |
| Check availability of format: EPUB3 | 2 | 2 | 2 | 2 | 2 |
| Check availability of format: Plain Text (accessible) | 2 | 2 | 0 | 2 | 0 |
| Check availability of format: Download HTML (zip) | 2 | 0 | 0 | 2 | 0 |
| Respect stopping condition and constraints (no downloads; only named formats; stop after recording) | 2 | 2 | 2 | 1 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
