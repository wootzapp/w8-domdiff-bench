# Evidence Error Audit: Task 96

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Search DailyMed for LIPITOR | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Select the Viatris non-repackaged label | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Label title and Packager | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Initial U.S. Approval year | No / N/A | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Dosage form and four strengths | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Route, active ingredient, and basis of strength | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Scope and stopping condition | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

The screenshot sequence shows the label header, section 3, and Ingredients and Appearance, but never displays `Initial U.S. Approval: 1996`. That text is explicit in `dom_model3.txt` and `dom_model4.txt`. This is genuine screenshot viewport loss, not a screenshot-verifier miss.
