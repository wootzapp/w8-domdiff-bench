# browser_task_037-package-platform-availability-20260909T080647Z verifier comparison

Frozen rubric SHA-256: `9d32a5e889be0c21958c7736140181e10f8caa992f0f6d4a53f28324d0e74646`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 22/22 (1.000) | True | 15 | 15 | 0 | 81,249 | 8,933 | 90,182 |
| DOM-model | 22/22 (1.000) | True | 21 | 21 | 0 | 91,763 | 13,415 | 105,178 |

DOM-model minus screenshot tokens: **+14,996 (+16.63%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Homebrew Formulae page for ffmpeg | 2 | 2 | 2 | 2 | 2 |
| Record stable version exactly as displayed | 2 | 0 | 0 | 2 | 2 |
| Record license exactly as displayed | 2 | 0 | 0 | 2 | 2 |
| List all regular dependencies under 'Depends on' (excluding build-only and 'Uses from macOS') | 8 | 0 | 0 | 8 | 8 |
| Report bottle availability for macOS on Apple Silicon exactly as displayed | 3 | 0 | 0 | 3 | 3 |
| Report bottle availability for Linux exactly as displayed | 3 | 0 | 0 | 3 | 3 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
