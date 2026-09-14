# browser_task_050-international-data-comparison-20260909T082032Z verifier comparison

Frozen rubric SHA-256: `377507b06bf488f2fc4bdd475a2237f2433f27381fb1757339a5f7a3b9633638`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 3/16 (0.188) | False | 20 | 20 | 0 | 132,131 | 13,375 | 145,506 |
| DOM-model | 4/16 (0.250) | False | 48 | 48 | 0 | 203,829 | 35,755 | 239,584 |

DOM-model minus screenshot tokens: **+94,078 (+64.66%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the official World Bank API response at the supplied URL (or clearly report if inaccessible) | 3 | 3 | 3 | 3 | 3 |
| Identify the latest year (2020–2026) where all three countries have non-null population values (or conclude none exists) | 4 | 0 | 0 | 0 | 0 |
| Report exact Population, total value for India in the latest common non-null year (full integer, no rounding) | 2 | 0 | 0 | 0 | 0 |
| Report exact Population, total value for Brazil in the latest common non-null year (full integer, no rounding) | 2 | 0 | 0 | 0 | 0 |
| Report exact Population, total value for Nigeria in the latest common non-null year (full integer, no rounding) | 2 | 0 | 0 | 0 | 0 |
| Rank countries from highest to lowest population for that year (or state ranking cannot be produced) | 2 | 0 | 0 | 0 | 0 |
| Stopping condition respected (stop after required outputs, or after establishing unavailability) | 1 | 1 | 1 | 0 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
