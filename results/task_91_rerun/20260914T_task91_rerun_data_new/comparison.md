# browser_task_091-cross-endpoint-blockchain-record-20260914T092331Z verifier comparison

Frozen rubric SHA-256: `c594cfe6a041f7fc5690e1f8f8f8fc13f658d4743fcc53b14c72a5bb8e16ba8f`  
Denominator: `21`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 21/21 (1.000) | True | 12 | 12 | 0 | 75,206 | 9,077 | 84,283 |
| DOM-model | 21/21 (1.000) | True | 18 | 18 | 0 | 74,786 | 12,292 | 87,078 |

DOM-model minus screenshot tokens: **+2,795 (+3.32%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Resolve block hash using Blockstream block-height endpoint | 3 | 0 | 0 | 3 | 3 |
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
