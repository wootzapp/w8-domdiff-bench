# Evidence Error Audit: Task 99

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Retrieve RecallID 10000 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Core identifier fields and Title | Yes / Yes | Partial (Title cut off) / N/A | 3/3 / 2/3 | DOM_EVIDENCE_MISSING |
| Products | Yes / Yes | No / N/A | 0/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Injuries | Yes / Yes | No / N/A | 0/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Retailers | Yes / Yes | No / N/A | 0/1 / 0/1 | DOM_EVIDENCE_MISSING |
| ManufacturerCountries | Yes / Yes | No / N/A | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Hazards, Remedies, and RemedyOptions | Yes / Yes | No / N/A | 0/4 / 0/4 | DOM_EVIDENCE_MISSING |
| Exact extraction/no fabrication | Yes / Yes | Partial / N/A | 0/3 / 1/3 | DOM_EVIDENCE_MISSING |

The screenshots contain the complete recall object and expose the answer's incorrect product quantity, injuries, retailer, hazard, and remedy values. Every DOM state is a fixed prefix ending at or inside `Title`, before all requested arrays. The seven DOM gaps are genuine capture loss, not transfer loss or DOM-verifier misses.
