# browser_task_055-archive-item-metadata-20260909T082419Z verifier comparison

Frozen rubric SHA-256: `eef1854613f6306024c699a31af39fe9e4a073bd967c6ebb96affd9f8e80b25d`  
Denominator: `21`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 6.5/21 (0.310) | False | 12 | 12 | 0 | 81,282 | 10,492 | 91,774 |
| DOM-model | 14/21 (0.667) | False | 18 | 18 | 0 | 94,490 | 14,271 | 108,761 |

DOM-model minus screenshot tokens: **+16,987 (+18.51%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the specified Internet Archive item (prideprejudice00aust) | 3 | 3 | 3 | 3 | 3 |
| Report publication year | 2 | 2 | 2 | 2 | 2 |
| Report publisher | 2 | 2 | 2 | 0 | 2 |
| Report language | 2 | 2 | 2 | 0 | 2 |
| List all displayed Topics | 4 | 2 | 4 | 0 | 4 |
| Check Download Options for EPUB availability | 2 | 2 | 2 | 0 | 0 |
| Check Download Options for FULL TEXT availability | 2 | 2 | 2 | 0 | 0 |
| Check Download Options for B/W PDF availability | 2 | 2 | 2 | 0 | 0 |
| Respect constraints (no download, borrow, sign in, or add to collection) | 1 | 1 | 1 | 1 | 1 |
| Stop after recording requested information (stopping condition) | 1 | 1 | 1 | 0.5 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
