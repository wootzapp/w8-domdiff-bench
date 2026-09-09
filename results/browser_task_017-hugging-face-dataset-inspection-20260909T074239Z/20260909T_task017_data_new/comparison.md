# browser_task_017-hugging-face-dataset-inspection-20260909T074239Z verifier comparison

Frozen rubric SHA-256: `432739090bfbc188d44079a449ae58637894eaf19a08f1d997ece6a4385e886c`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3/12 (0.250) | False | 10 | 10 | 0 | 52,499 | 6,249 | 58,748 |
| DOM-model | 7/12 (0.583) | False | 13 | 13 | 0 | 78,381 | 7,940 | 86,321 |

DOM-model minus screenshot tokens: **+27,573 (+46.93%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the Hugging Face SQuAD dataset page and Dataset Viewer | 2 | 0 | 0 | 2 | 2 |
| Record Dataset Viewer row count for the train split (exact split name and rows) | 4 | 0 | 0 | 0 | 4 |
| Record Dataset Viewer row count for the validation split (exact split name and rows) | 4 | 0 | 0 | 0 | 0 |
| Follow constraints and stopping condition | 2 | 1 | 1 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
