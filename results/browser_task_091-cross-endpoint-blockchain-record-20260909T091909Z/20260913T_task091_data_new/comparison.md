# browser_task_091-cross-endpoint-blockchain-record-20260909T091909Z verifier comparison

Frozen rubric SHA-256: `c594cfe6a041f7fc5690e1f8f8f8fc13f658d4743fcc53b14c72a5bb8e16ba8f`  
Denominator: `21`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 21/21 (1.000) | True | 12 | 12 | 0 | 73,520 | 7,356 | 80,876 |
| DOM-model | 21/21 (1.000) | True | 16 | 16 | 0 | 69,798 | 9,725 | 79,523 |

DOM-model minus screenshot tokens: **-1,353 (-1.67%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Resolve block hash using Blockstream block-height endpoint | 3 | 3 | 3 | 3 | 3 |
| Construct only the documented /api/block/{hash} follow-up URL from the resolved hash | 2 | 2 | 2 | 2 | 2 |
| Retrieve the exact block record via /api/block/{hash} (external dependency-aware) | 2 | 2 | 2 | 2 | 2 |
| Report required fields from the exact block response | 8 | 8 | 8 | 8 | 8 |
| Preserve exact returned values and distinctions (hashes, timestamp, size vs weight) | 3 | 3 | 3 | 3 | 3 |
| Stop after reporting the resolved hash and the requested block fields | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
