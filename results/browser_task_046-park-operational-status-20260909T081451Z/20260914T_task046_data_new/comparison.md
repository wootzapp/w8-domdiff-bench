# browser_task_046-park-operational-status-20260909T081451Z verifier comparison

Frozen rubric SHA-256: `e24fd31de542dbb9ecf85ffa9e52387f76f4eba36181c54daaeb2de5917686b9`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 2/20 (0.100) | False | 14 | 14 | 0 | 88,083 | 10,829 | 98,912 |
| DOM-model | 4/20 (0.200) | False | 20 | 20 | 0 | 92,311 | 16,515 | 108,826 |

DOM-model minus screenshot tokens: **+9,914 (+10.02%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Yosemite Current Conditions page (NPS) and locate the Active Alerts module | 2 | 0 | 2 | 1 | 2 |
| Active park-alert count on Yosemite Current Conditions page | 3 | 0 | 3 | 0 | 0 |
| Report the first two active park-alert titles (or all if fewer than two) | 3 | 0 | 3 | 0 | 0 |
| Report displayed Tioga Road status | 2 | 0 | 2 | 0 | 0 |
| Access Yosemite Entrance Reservations page (NPS) | 1 | 0 | 1 | 0 | 0 |
| Determine 2026 entrance timed-reservation requirement from Entrance Reservations page | 5 | 0 | 5 | 0 | 0 |
| Follow constraints and stopping condition | 4 | 0 | 4 | 1 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
