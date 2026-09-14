# browser_task_077-patent-record-inspection-20260914T090247Z verifier comparison

Frozen rubric SHA-256: `b074ef487637c1bc30d9d5aa9f3006c69baaff8696ed2f1abd51f4d6f943ecc6`  
Denominator: `30`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 26/30 (0.867) | False | 54 | 54 | 0 | 318,474 | 24,267 | 342,741 |
| DOM-model | 24/30 (0.800) | False | 57 | 57 | 0 | 354,508 | 28,722 | 383,230 |

DOM-model minus screenshot tokens: **+40,489 (+11.81%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the specified Google Patents record (US6285999B1) and its Info section only | 3 | 3 | 0 | 3 | 2 |
| Report Title exactly as displayed | 2 | 2 | 2 | 2 | 2 |
| Report Publication number exactly as displayed | 2 | 2 | 0 | 2 | 2 |
| Report Application number exactly as displayed | 2 | 2 | 0 | 2 | 2 |
| Report Inventor exactly as displayed | 3 | 3 | 3 | 3 | 3 |
| Report every Current Assignee exactly as displayed (kept separate from Original Assignee) | 4 | 1 | 0 | 3 | 4 |
| Report Original Assignee exactly as displayed (kept separate from Current Assignee) | 3 | 3 | 3 | 0 | 0 |
| Report Priority date exactly as displayed | 2 | 2 | 0 | 2 | 1 |
| Report Filing date exactly as displayed | 2 | 2 | 0 | 2 | 2 |
| Report Publication date exactly as displayed | 2 | 2 | 0 | 2 | 1 |
| Report displayed Legal status exactly as displayed | 3 | 3 | 0 | 3 | 3 |
| Stop after recording all requested fields from the Info section | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
