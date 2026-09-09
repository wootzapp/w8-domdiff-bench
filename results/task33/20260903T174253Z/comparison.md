# browser_task_037-package-platform-availability-20260902T193908Z verifier comparison

Frozen rubric SHA-256: `57da8821efb098c1edf6e2b1b22ccffe3d0ce7647f777532223aadc76424f28d`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 10/18 (0.556) | False | 18 | 18 | 0 | 101,486 | 11,161 | 112,647 |
| DOM-model | 10/18 (0.556) | False | 26 | 26 | 0 | 118,627 | 19,500 | 138,127 |

DOM-model minus screenshot tokens: **+25,480 (+22.62%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Homebrew Formulae ffmpeg page (specified source) without downloading/installing | 2 | 2 | 2 | 2 | 2 |
| Record stable version exactly as displayed | 2 | 2 | 0 | 0 | 0 |
| Record license exactly as displayed | 2 | 0 | 0 | 0 | 0 |
| List all regular 'Depends on' packages (excluding build-only and 'Uses from macOS') | 6 | 0 | 0 | 6 | 6 |
| Report bottle availability for macOS Apple Silicon exactly as displayed | 2 | 0 | 1 | 0 | 1 |
| Report bottle availability for Linux exactly as displayed | 2 | 0 | 1 | 0 | 0 |
| Stop at requested information only (respect stopping condition and scope constraints) | 2 | 2 | 2 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
