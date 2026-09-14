# browser_task_092-legislative-roll-call-inspection-20260909T091934Z verifier comparison

Frozen rubric SHA-256: `a890f41cead00360c390707224de60ae9e238a221b233e127832d42e133e7ac6`  
Denominator: `30`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 0/30 (0.000) | False | 10 | 10 | 0 | 63,937 | 7,044 | 70,981 |
| DOM-model | 30/30 (1.000) | False | 30 | 30 | 0 | 126,692 | 16,274 | 142,966 |

DOM-model minus screenshot tokens: **+71,985 (+101.41%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the specified Office of the Clerk vote-details page for roll call 369 (2021) | 3 | 0 | 0 | 0 | 3 |
| Record roll-call number | 2 | 0 | 0 | 0 | 2 |
| Record bill number | 3 | 0 | 0 | 0 | 3 |
| Record displayed date and time (timestamp) | 3 | 0 | 0 | 0 | 3 |
| Record Congress and session shown for the historical vote | 4 | 0 | 0 | 0 | 4 |
| Record Vote Question | 3 | 0 | 0 | 0 | 3 |
| Record Vote Type | 2 | 0 | 0 | 0 | 2 |
| Record Status | 2 | 0 | 0 | 0 | 2 |
| Record aggregate VOTES totals (Yea, Nay, Present, Not Voting) | 6 | 0 | 0 | 0 | 6 |
| Stopping condition: stop after recording requested vote-header and aggregate-count fields | 2 | 0 | 0 | 0 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
