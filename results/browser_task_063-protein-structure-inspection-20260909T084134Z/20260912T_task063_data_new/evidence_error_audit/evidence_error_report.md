# Evidence-Item Audit: browser_task_063-protein-structure-inspection-20260909T084134Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use the RCSB PDB 1TUP Structure Summary page as the source (or report access failure) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Use the RCSB PDB 1TUP Structure Summary page as the source (or report access failure)); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report complete structure title | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report complete structure title); verifier caught | Present (dom_model0.txt m0:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Report released date exactly as displayed | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report released date exactly as displayed); verifier caught | Present (dom_model0.txt m0:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Report experimental method | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report experimental method); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report resolution with units exactly (if displayed) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report resolution with units exactly (if displayed)); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Report protein molecule name | Criterion-relevant evidence sufficient to evaluate the agent response | Absent | Present (dom_model1.txt m1:L74-L74); verifier caught | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C6 | Report protein source organism (exclude DNA rows with N/A) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report protein source organism (exclude DNA rows with N/A)); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C7 | List every unique ligand ID displayed (deduplicated) | Criterion-relevant evidence sufficient to evaluate the agent response | Absent | Present (dom_model1.txt m1:L57-L57); verifier caught | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C8 | Stop after recording all requested fields | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Stop after recording all requested fields); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 7.
- Screenshot catch rate on common evidence: 7/7 (100.0%).
- DOM catch rate on common evidence: 7/7 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
