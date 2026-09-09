# browser_task_037-package-platform-availability-20260905T112853Z verifier comparison

Frozen rubric SHA-256: `7fee6b108c0b7c8e1a22a4772573e3b6e4432db4d5f325a29999a4e798070274`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/20 (0.600) | False | 12 | 12 | 0 | 69,741 | 9,618 | 79,359 |
| DOM-model | 20/20 (1.000) | True | 18 | 18 | 0 | 76,776 | 11,002 | 87,778 |

DOM-model minus screenshot tokens: **+8,419 (+10.61%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Open the Homebrew Formulae page for ffmpeg | 2 | 2 | 2 | 2 | 2 |
| Record stable version | 2 | 0 | 0 | 2 | 2 |
| Record license | 2 | 0 | 0 | 2 | 2 |
| Record complete regular dependency list (Depends on) | 6 | 0 | 0 | 0 | 6 |
| Record bottle availability for macOS Apple Silicon and for Linux | 4 | 0 | 0 | 4 | 4 |
| Respect constraints and stopping condition | 4 | 4 | 4 | 2 | 4 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
