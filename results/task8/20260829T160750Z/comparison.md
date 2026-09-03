# viewport-modern-8-hugging-face-dataset-inspection-20260829T075200Z verifier comparison

Frozen rubric SHA-256: `b30cca4160f9316369cb69cff961d935739ef98c998bd703d33ac0e3683ad8d6`  
Denominator: `13`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/13 (0.923) | True | 14 | 14 | 0 | 75,713 | 7,515 | 83,228 |
| DOM-model | 9.5/13 (0.731) | False | 20 | 20 | 0 | 141,779 | 10,997 | 152,776 |

DOM-model minus screenshot tokens: **+69,548 (+83.56%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate to the Hugging Face SQuAD dataset page | 1 | 1 | 1 | 1 | 1 |
| Access and use the Dataset Viewer to view split information | 2 | 2 | 2 | 2 | 2 |
| Record train split name and row count exactly as shown | 4 | 4 | 4 | 3 | 4 |
| Record validation split name and row count exactly as shown | 4 | 4 | 4 | 4 | 1 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 1.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
