# browser_task_013-chess-profile-lookup-20260909T073812Z verifier comparison

Frozen rubric SHA-256: `1db9087c848d5ad336f7c063babff47c82c0d673cec6184a853a62ab5e162c17`  
Denominator: `13`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 11/13 (0.846) | True | 15 | 15 | 0 | 76,260 | 8,575 | 84,835 |
| DOM-model | 13/13 (1.000) | True | 32 | 32 | 0 | 134,935 | 13,952 | 148,887 |

DOM-model minus screenshot tokens: **+64,052 (+75.50%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Magnus Carlsen’s Chess.com profile page (without signing in) | 3 | 3 | 3 | 3 | 3 |
| Record Blitz rating exactly as displayed | 4 | 0 | 4 | 3 | 4 |
| Record Bullet rating exactly as displayed | 4 | 0 | 4 | 3 | 4 |
| Respect constraints: no sign-in and no interaction with another player; stop after recording ratings | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
