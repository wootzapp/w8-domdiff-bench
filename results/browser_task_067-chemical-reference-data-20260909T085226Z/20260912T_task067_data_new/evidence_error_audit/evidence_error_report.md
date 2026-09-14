# Evidence-Item Audit: browser_task_067-chemical-reference-data-20260909T085226Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access the specified NIST Chemistry WebBook record for water (ID=C7732185) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Access the specified NIST Chemistry WebBook record for water (ID=C7732185)); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report identity fields from the record: formula, molecular weight, IUPAC InChIKey, and CAS Registry Number | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report identity fields from the record: formula, molecular weight, IUPAC InChIKey, and CAS Registry Number); verifier caught | Present (dom_model0.txt m0:L20-L20); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Report CODATA experimental gas-phase standard enthalpy of formation (with unit and reference) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Report CODATA experimental gas-phase standard enthalpy of formation (with unit and reference)); verifier caught | Present (dom_model0.txt m0:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Preserve exact transcription as feasible and stop after required fields | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Preserve exact transcription as feasible and stop after required fields); verifier caught | Present (dom_model0.txt m0:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 4.
- Screenshot catch rate on common evidence: 4/4 (100.0%).
- DOM catch rate on common evidence: 4/4 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
