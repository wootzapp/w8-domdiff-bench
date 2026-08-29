# github-heavy-02-vs-code-issue-triage-20260821T060622Z verifier comparison

Frozen rubric SHA-256: `8f154a60fff3ce21367074a1b5a18975050b39d79414252f25a9cdf984c30743`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 21/22 (0.955) | False | 21 | 21 | 0 | 134,038 | 13,027 | 147,065 |
| DOM-model | 19/22 (0.864) | False | 22 | 22 | 0 | 218,939 | 12,316 | 231,255 |

DOM-model minus screenshot tokens: **+84,190 (+57.25%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Apply GitHub issue filters (bug + help wanted) in microsoft/vscode | 4 | 4 | 4 | 4 | 4 |
| Sort filtered issues from oldest to newest | 3 | 3 | 3 | 3 | 3 |
| Report the displayed matching count | 2 | 1 | 2 | 2 | 2 |
| Report details for the three oldest matching issues (list view) | 6 | 0 | 6 | 5 | 3 |
| Open the oldest matching issue and report assignees and milestone | 4 | 0 | 4 | 4 | 4 |
| Respect constraints and stopping condition | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
