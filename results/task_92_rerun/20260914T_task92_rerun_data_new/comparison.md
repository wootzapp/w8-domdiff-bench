# browser_task_092-legislative-roll-call-inspection-20260914T092512Z verifier comparison

Frozen rubric SHA-256: `a890f41cead00360c390707224de60ae9e238a221b233e127832d42e133e7ac6`  
Denominator: `30`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3/30 (0.100) | False | 10 | 10 | 0 | 64,219 | 7,328 | 71,547 |
| DOM-model | 28/30 (0.933) | False | 30 | 30 | 0 | 127,460 | 16,621 | 144,081 |

DOM-model minus screenshot tokens: **+72,534 (+101.38%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the specified Office of the Clerk vote-details page for roll call 369 (2021) | 3 | 0 | 0 | 3 | 3 |
| Record roll-call number | 2 | 0 | 0 | 0 | 2 |
| Record bill number | 3 | 0 | 0 | 0 | 3 |
| Record displayed date and time (timestamp) | 3 | 0 | 0 | 0 | 3 |
| Record Congress and session shown for the historical vote | 4 | 0 | 0 | 0 | 4 |
| Record Vote Question | 3 | 0 | 0 | 0 | 3 |
| Record Vote Type | 2 | 0 | 0 | 0 | 2 |
| Record Status | 2 | 0 | 0 | 0 | 2 |
| Record aggregate VOTES totals (Yea, Nay, Present, Not Voting) | 6 | 0 | 0 | 0 | 6 |
| Stopping condition: stop after recording requested vote-header and aggregate-count fields | 2 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
