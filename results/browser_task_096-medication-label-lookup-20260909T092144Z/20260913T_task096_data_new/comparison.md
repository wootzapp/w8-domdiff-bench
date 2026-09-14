# browser_task_096-medication-label-lookup-20260909T092144Z verifier comparison

Frozen rubric SHA-256: `f654e9ea48250723c3b05e69989ab730a13e96913fc51272cf10af7248e24db5`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 17/20 (0.850) | False | 20 | 20 | 0 | 125,722 | 12,398 | 138,120 |
| DOM-model | 19/20 (0.950) | True | 31 | 31 | 0 | 171,914 | 18,470 | 190,384 |

DOM-model minus screenshot tokens: **+52,264 (+37.84%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access DailyMed and attempt search for LIPITOR | 2 | 2 | 2 | 2 | 2 |
| Use DailyMed and select the correct non-repackaged LIPITOR label (Viatris Specialty LLC) | 4 | 4 | 4 | 4 | 4 |
| Report page label title and Packager from the selected label | 2 | 2 | 2 | 2 | 2 |
| Report Initial U.S. Approval year from the label | 2 | 0 | 2 | 0 | 2 |
| Report dosage form and all strengths from Section 3 (four strengths) | 4 | 4 | 4 | 4 | 4 |
| Report Route of Administration, active Ingredient Name, and Basis of Strength from Ingredients and Appearance | 4 | 4 | 4 | 4 | 4 |
| Respect constraints and stopping condition (scope control) | 2 | 2 | 2 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
