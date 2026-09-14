# browser_task_041-standards-metadata-extraction-20260909T080918Z verifier comparison

Frozen rubric SHA-256: `390ac55adb7f6723236d47e498f5810fea3795edbb61e9dc073887d520bf5558`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 18.5/20 (0.925) | True | 12 | 12 | 0 | 77,486 | 7,249 | 84,735 |
| DOM-model | 16/20 (0.800) | True | 24 | 24 | 0 | 141,336 | 18,351 | 159,687 |

DOM-model minus screenshot tokens: **+74,952 (+88.45%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the RFC Editor record for RFC 9110 (info page) and base answers on it | 2 | 2 | 2 | 2 | 2 |
| Report RFC 9110 core metadata from the RFC Editor record | 6 | 6 | 6 | 4.5 | 6 |
| List every RFC obsoleted by RFC 9110 (as shown in the RFC Editor record) | 4 | 4 | 4 | 4 | 4 |
| Preserve full vs partial obsolescence for each obsoleted RFC (per RFC Editor record) | 6 | 6 | 6 | 6 | 3 |
| Stopping condition met (no extra actions beyond recording required info) | 2 | 2 | 1 | 2 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
