# browser_task_064-legislation-structure-inspection-20260909T084207Z verifier comparison

Frozen rubric SHA-256: `29761b5dc27ac06d69d581fbc838bb739d73b4f0da27ce219174f8ebc715e525`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/20 (0.700) | False | 16 | 16 | 0 | 93,681 | 11,086 | 104,767 |
| DOM-model | 13/20 (0.650) | False | 21 | 21 | 0 | 115,937 | 16,534 | 132,471 |

DOM-model minus screenshot tokens: **+27,704 (+26.44%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access legislation.gov.uk and reach Data Protection Act 2018 in Original (As enacted) Introductory Text (or clearly report blocker) | 3 | 3 | 3 | 3 | 3 |
| Record chapter number exactly as displayed (as enacted) | 3 | 3 | 3 | 3 | 3 |
| Record complete long title exactly as displayed (as enacted) | 3 | 3 | 3 | 3 | 3 |
| Record Royal Assent date exactly as displayed (as enacted) | 3 | 2 | 3 | 3 | 3 |
| Count top-level Parts in as-enacted table of contents (Parts only, exclude nested Parts in Schedules) | 4 | 4 | 4 | 2 | 1 |
| Count top-level Schedules in as-enacted table of contents (each counted once) | 4 | 0 | 1 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
