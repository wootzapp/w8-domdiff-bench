# browser_task_060-discography-chronology-20260902T210922Z verifier comparison

Frozen rubric SHA-256: `f66485781e243e66cb233cd21d8dd438730604f80c8696c3be7e64478c864267`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3/12 (0.250) | False | 16 | 16 | 0 | 89,513 | 9,713 | 99,226 |
| DOM-model | 3/12 (0.250) | False | 16 | 16 | 0 | 101,988 | 9,939 | 111,927 |

DOM-model minus screenshot tokens: **+12,701 (+12.80%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the official Daft Punk MusicBrainz artist record and correct section scope (including all constraints) | 3 | 3 | 3 | 2 | 2 |
| Album entry #1: first dated entry in displayed chronological order | 3 | 3 | 1 | 1 | 1 |
| Album entry #2: second dated entry in displayed chronological order | 3 | 3 | 0 | 0 | 0 |
| Album entry #3: third dated entry in displayed chronological order (and stop after three) | 3 | 3 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
