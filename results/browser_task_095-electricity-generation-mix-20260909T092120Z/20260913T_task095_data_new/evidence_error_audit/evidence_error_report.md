# Evidence Error Audit: Task 95

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Select the exact 12:00–12:30 record | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Report every fuel/percentage pair | Yes / Yes | No / N/A | 1/4 / 1/4 | DOM_EVIDENCE_MISSING |
| Identify every explicitly zero fuel | Yes / Yes | No / N/A | 1/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Sum all returned percentages | Yes / Yes | No / N/A | 0/2 / 0.5/2 | DOM_EVIDENCE_MISSING |

The screenshots show all nine values for the requested record, including both zero-valued fuels and a total of 100.0. Every DOM state ends mid-record after the first few pairs, so the missing suffix is genuine source capture loss. Neither verifier overlooked evidence that existed in its own input.
