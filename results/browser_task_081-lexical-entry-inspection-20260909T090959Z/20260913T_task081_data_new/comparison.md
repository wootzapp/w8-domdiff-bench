# browser_task_081-lexical-entry-inspection-20260909T090959Z verifier comparison

Frozen rubric SHA-256: `3e3d33a6f5ea8e4d4e131ac6c0c0240e9d1ffcfcdb84761486dde623915d2793`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 18/18 (1.000) | True | 12 | 12 | 0 | 70,924 | 9,143 | 80,067 |
| DOM-model | 13/18 (0.722) | False | 24 | 24 | 0 | 131,247 | 19,441 | 150,688 |

DOM-model minus screenshot tokens: **+70,621 (+88.20%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only the English section of the Wiktionary entry | 3 | 3 | 3 | 3 | 3 |
| Report the four prose-etymology source-language stages (Middle English back to Arabic) | 4 | 4 | 4 | 4 | 1 |
| Provide the first IPA transcription and the Standard Southern British IPA transcription (distinct) | 4 | 4 | 2 | 4 | 2 |
| Report UK and US hyphenation | 2 | 2 | 0 | 2 | 2 |
| Report noun countability label(s) and plural form | 3 | 3 | 3 | 3 | 3 |
| Stopping condition respected (no extra, unrequested content) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
