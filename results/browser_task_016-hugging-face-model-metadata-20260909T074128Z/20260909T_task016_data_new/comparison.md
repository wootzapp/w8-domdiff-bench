# browser_task_016-hugging-face-model-metadata-20260909T074128Z verifier comparison

Frozen rubric SHA-256: `3ae38854ed411b9031803fe22503d5d4c10c2cf432936e9016379e99e0ae71fd`  
Denominator: `13`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/13 (1.000) | True | 12 | 12 | 0 | 64,902 | 5,972 | 70,874 |
| DOM-model | 13/13 (1.000) | True | 15 | 15 | 0 | 88,114 | 7,437 | 95,551 |

DOM-model minus screenshot tokens: **+24,677 (+34.82%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Open the correct Hugging Face repository page | 2 | 2 | 2 | 2 | 2 |
| Report license name from visible metadata | 3 | 0 | 0 | 3 | 3 |
| Report current likes count from visible metadata | 3 | 0 | 0 | 3 | 3 |
| Determine and report whether the repository is gated (from visible cues) | 3 | 0 | 0 | 3 | 3 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
