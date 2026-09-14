# browser_task_005-event-lookup-20260909T094331Z verifier comparison

Frozen rubric SHA-256: `1d9fb62eb123094877e0d4f2d9defa7dfd985148ce7c88e3efa589b359e1671c`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/15 (0.800) | False | 14 | 14 | 0 | 73,136 | 7,084 | 80,220 |
| DOM-model | 12/15 (0.800) | False | 17 | 17 | 0 | 74,310 | 9,769 | 84,079 |

DOM-model minus screenshot tokens: **+3,859 (+4.81%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the George H. W. Bush Presidential Library website (bush41.org) and navigate to events listings | 3 | 3 | 3 | 3 | 3 |
| Determine the next upcoming event (chronologically soonest future event) from available official listings | 4 | 2 | 4 | 2 | 3 |
| Report required event details: title, date, time, and location | 5 | 5 | 5 | 4 | 3 |
| Respect constraints (no sign-in, no registration, no ticket purchase) | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
