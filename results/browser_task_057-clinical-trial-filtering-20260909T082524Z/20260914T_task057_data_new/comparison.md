# browser_task_057-clinical-trial-filtering-20260909T082524Z verifier comparison

Frozen rubric SHA-256: `1ee0926b0edcdcc789f7b4f26568b5f9d84824be172b8387c267c7bef3072441`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 4/20 (0.200) | False | 79 | 79 | 0 | 412,186 | 23,493 | 435,679 |
| DOM-model | 6/20 (0.300) | False | 82 | 82 | 0 | 541,237 | 26,081 | 567,318 |

DOM-model minus screenshot tokens: **+131,639 (+30.21%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Apply specified search and filters on ClinicalTrials.gov | 4 | 4 | 4 | 2 | 2 |
| Sort results by Last Update Posted (newest first) | 3 | 3 | 3 | 0 | 2 |
| Report first displayed result (in displayed order) with required fields | 3 | 0 | 0 | 0 | 0 |
| Report second displayed result (in displayed order) with required fields | 3 | 0 | 0 | 0 | 0 |
| Report third displayed result (in displayed order) with required fields | 3 | 0 | 0 | 0 | 0 |
| Respect task constraints and stopping condition | 4 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
