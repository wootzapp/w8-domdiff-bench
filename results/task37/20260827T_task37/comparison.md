# viewport-vscode-triage-viewport-vs-code-issue-triage-20260826T185614Z verifier comparison

Frozen rubric SHA-256: `f2367f0f19f251bcc6489f979e1d8f2361ef252920e4d494248079585e4c93fb`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/22 (0.682) | False | 19 | 19 | 0 | 131,679 | 13,429 | 145,108 |
| DOM-model | 17/22 (0.773) | False | 29 | 29 | 0 | 199,321 | 19,827 | 219,148 |

DOM-model minus screenshot tokens: **+74,040 (+51.02%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access microsoft/vscode GitHub issues list without signing in | 2 | 2 | 2 | 2 | 2 |
| Apply GitHub issue filters and sorting (bug + help wanted; oldest first) | 4 | 4 | 4 | 4 | 4 |
| Report the displayed matching count | 2 | 0 | 2 | 2 | 2 |
| Identify and report the three oldest matching issues with required fields | 6 | 0 | 3 | 2 | 2 |
| Open the oldest matching issue and report assignees and milestone (explicitly 'none' when none) | 4 | 0 | 4 | 1 | 4 |
| Respect constraints and stopping condition (no sign-in or issue interactions; stop after verification) | 4 | 4 | 4 | 4 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
