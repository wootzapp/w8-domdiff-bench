# browser_task_051-cultural-object-metadata-20260909T082146Z verifier comparison

Frozen rubric SHA-256: `5a2c65783a6ed51812d8b45896ecebb899378a1aeb5f24f624b632a401658fbd`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/18 (0.667) | False | 12 | 12 | 0 | 75,588 | 8,935 | 84,523 |
| DOM-model | 16/18 (0.889) | False | 32 | 32 | 0 | 110,865 | 18,327 | 129,192 |

DOM-model minus screenshot tokens: **+44,669 (+52.85%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use the exact Europeana record 90402/SK_A_2344 (The Milkmaid) or report access failure | 3 | 3 | 3 | 3 | 3 |
| Record the Title exactly as displayed (or state not displayed/unavailable) | 2 | 0 | 2 | 2 | 2 |
| Record the Creation date exactly as displayed (or state not displayed/unavailable) | 2 | 0 | 0 | 0 | 2 |
| Record the Providing institution as shown on the record (without following external link), or state not displayed/unavailable | 2 | 0 | 0 | 2 | 2 |
| Record the Type of item exactly as displayed (or state not displayed/unavailable) | 2 | 0 | 0 | 0 | 2 |
| Record the displayed Rights statement exactly (or state not displayed/unavailable) | 2 | 0 | 0 | 2 | 2 |
| Record the Identifier exactly as displayed (or state not displayed/unavailable) | 2 | 0 | 0 | 0 | 0 |
| Respect task constraints (no external link navigation, no creator inference, no substitution, stop after six fields) and handle missing/blocked data appropriately | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
