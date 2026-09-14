# browser_task_070-unicode-ideograph-inspection-20260914T085343Z verifier comparison

Frozen rubric SHA-256: `d0ffe495ad2e47d67d52c42148e989a21aba2a4aa8fd88b63ab4a62c2b792f5e`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/20 (0.400) | False | 12 | 12 | 0 | 79,648 | 9,900 | 89,548 |
| DOM-model | 8/20 (0.400) | False | 17 | 17 | 0 | 99,151 | 16,126 | 115,277 |

DOM-model minus screenshot tokens: **+25,729 (+28.73%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access the Unicode Unihan record for U+4E00 (or clearly report access failure) | 2 | 2 | 2 | 2 | 2 |
| Respect task constraints (sole source, exact copying, no extra fields, stop at requested fields) | 2 | 2 | 2 | 1 | 0 |
| Record code-point identity and displayed glyph | 2 | 2 | 2 | 1 | 2 |
| Record numeric and encoding fields (decimal, UTF-8, UTF-16) | 3 | 3 | 3 | 3 | 3 |
| Record total stroke count | 1 | 1 | 1 | 1 | 1 |
| Record definition | 2 | 2 | 2 | 0 | 0 |
| Record Mandarin reading | 2 | 2 | 0 | 0 | 0 |
| Record Japanese On reading | 2 | 2 | 2 | 0 | 0 |
| Record Korean reading | 2 | 2 | 0 | 0 | 0 |
| Record Vietnamese reading | 2 | 2 | 2 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
