# browser_task_031-table-lookup-and-extraction-20260909T080306Z verifier comparison

Frozen rubric SHA-256: `1f258ed34b24d9908e533b69708ef9ff958f65a514ffc2a461789d2905a7a372`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3/15 (0.200) | False | 10 | 10 | 0 | 54,088 | 5,387 | 59,475 |
| DOM-model | 1/15 (0.067) | False | 10 | 10 | 0 | 53,497 | 5,227 | 58,724 |

DOM-model minus screenshot tokens: **-751 (-1.26%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Record complete 1921 Nobel Physics table entry | 4 | 0 | 0 | 0 | 0 |
| Record complete 1922 Nobel Physics table entry | 4 | 0 | 0 | 0 | 0 |
| Record complete 1923 Nobel Physics table entry | 4 | 0 | 0 | 0 | 0 |
| Adherence to explicit constraints and stopping condition | 3 | 3 | 3 | 3 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
