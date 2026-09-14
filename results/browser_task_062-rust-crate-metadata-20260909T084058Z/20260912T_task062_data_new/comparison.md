# browser_task_062-rust-crate-metadata-20260909T084058Z verifier comparison

Frozen rubric SHA-256: `2139b52faa8bdae9dcac138b145be3103e9afb0237adea7d35a65b5878477ecd`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 22/22 (1.000) | True | 14 | 14 | 0 | 83,337 | 8,517 | 91,854 |
| DOM-model | 22/22 (1.000) | True | 28 | 28 | 0 | 129,025 | 18,418 | 147,443 |

DOM-model minus screenshot tokens: **+55,589 (+60.52%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Serde crate landing page on crates.io | 2 | 2 | 2 | 2 | 2 |
| Report displayed latest version | 2 | 1 | 1 | 2 | 2 |
| Report displayed release-date wording | 2 | 1 | 1 | 2 | 2 |
| Report minimum Rust version | 2 | 1 | 1 | 2 | 2 |
| Report license | 2 | 2 | 2 | 2 | 2 |
| Report package size with exact units | 2 | 2 | 1 | 2 | 2 |
| Report repository link/value | 2 | 1 | 1 | 2 | 2 |
| Report all-time download count (Downloads all time) | 3 | 1 | 1 | 3 | 3 |
| Report number of published versions | 2 | 1 | 1 | 2 | 2 |
| Respect constraints and stopping condition | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
