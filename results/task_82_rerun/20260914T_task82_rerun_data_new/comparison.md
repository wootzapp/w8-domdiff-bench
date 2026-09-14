# browser_task_082-chess-game-result-inspection-20260914T091145Z verifier comparison

Frozen rubric SHA-256: `2080808bbccbe3444a4d2234275a959221a249014904721553df11db85c833d6`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 18/20 (0.900) | False | 12 | 12 | 0 | 69,953 | 7,286 | 77,239 |
| DOM-model | 17/20 (0.850) | False | 17 | 17 | 0 | 96,580 | 11,783 | 108,363 |

DOM-model minus screenshot tokens: **+31,124 (+40.30%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the specified public Lichess game page (Z01xx8LK) only | 3 | 3 | 3 | 3 | 3 |
| Record time control, rated/casual status, and speed category as displayed | 3 | 3 | 3 | 3 | 3 |
| Record both players' names, ratings, and rating changes (correct association) | 5 | 5 | 5 | 5 | 4 |
| Record termination/victory statement, winner, and number of moves | 4 | 4 | 4 | 3 | 3 |
| Respect constraints and stopping condition | 5 | 5 | 5 | 4 | 4 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
