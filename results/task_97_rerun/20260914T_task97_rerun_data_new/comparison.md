# browser_task_097-dns-record-resolution-20260914T093312Z verifier comparison

Frozen rubric SHA-256: `654d46cb9a7cf409c8356499671fa0c4612b4a5d7216ce8501de2bd35f6df7fc`  
Denominator: `14`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/14 (0.929) | False | 38 | 38 | 0 | 191,753 | 18,193 | 209,946 |
| DOM-model | 10.5/14 (0.750) | False | 42 | 42 | 0 | 168,159 | 17,853 | 186,012 |

DOM-model minus screenshot tokens: **-23,934 (-11.40%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Google Public DNS web form and perform MX lookup for example.com | 3 | 3 | 3 | 3 | 2 |
| Report complete MX result-configuration heading | 2 | 0 | 2 | 0 | 0 |
| Report Status code (number and mnemonic) for MX result | 2 | 2 | 2 | 1 | 1 |
| Report required DNS flags (TC, RD, RA, AD, CD) for MX result | 3 | 3 | 3 | 3 | 3 |
| Report Question name and Question type (numeric and mnemonic) for MX result | 2 | 2 | 2 | 2 | 1 |
| Report every type-15 MX Answer record (name, type numeric/mnemonic, data) and exclude non-MX like RRSIG | 4 | 4 | 4 | 4 | 3.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
