# browser_task_093-supreme-court-case-analysis-20260909T092007Z verifier comparison

Frozen rubric SHA-256: `c49eaa21d4a9edd5fde2cc07d823703bf25320782831a5f91ca52c9c0b249dbb`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/16 (1.000) | True | 14 | 14 | 0 | 81,499 | 8,183 | 89,682 |
| DOM-model | 16/16 (1.000) | True | 26 | 26 | 0 | 106,653 | 13,252 | 119,905 |

DOM-model minus screenshot tokens: **+30,223 (+33.70%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the correct Oyez case page (Brown v. Board of Education of Topeka (1), not Brown II) | 3 | 3 | 3 | 3 | 3 |
| Report identity & docket metadata (docket number and deciding Court) | 2 | 2 | 1 | 2 | 2 |
| Report all required dates with argued vs. reargued ranges kept distinct | 3 | 3 | 3 | 3 | 3 |
| Report the displayed Question from the Oyez page | 2 | 1 | 2 | 2 | 2 |
| Conclusion card decision details (split and prevailing side) | 2 | 2 | 1 | 2 | 2 |
| Conclusion card majority-opinion author | 1 | 1 | 1 | 1 | 1 |
| Conclusion card one-line holding immediately below the majority-opinion label | 3 | 0 | 2 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
