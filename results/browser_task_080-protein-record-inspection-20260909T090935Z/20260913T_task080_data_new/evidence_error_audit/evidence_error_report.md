# Evidence-Item Audit: browser_task_080-protein-record-inspection-20260909T090935Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access the UniProtKB entry page for accession P04637 (or determine it is inaccessible) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Access the UniProtKB entry page for accession P04637 (or determine it is inaccessible)); verifier caught | Present (dom_model0.txt m0:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Record entry name | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: P04637 · P53_HUMAN); verifier missed | Present (dom_model0.txt m0:L26-L26); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C2 | Record recommended protein name | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Protein Cellular tumor antigen p53); verifier missed | Present (dom_model0.txt m0:L2-L2); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C3 | Record primary gene name | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Gene TP53); verifier missed | Present (dom_model0.txt m0:L30-L30); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C4 | Record organism | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Organism Homo sapiens (Human)); verifier missed | Present (dom_model0.txt m0:L2-L2); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C5 | Record canonical sequence length | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Amino acids 393 (go to sequence)); verifier missed | Present (dom_model0.txt m0:L40-L40); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C6 | Record reviewed status (as displayed) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Status UniProtKB reviewed (Swiss-Prot)); verifier missed | Present (dom_model0.txt m0:L27-L27); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C7 | Stopping condition met (all six fields reported, then stop) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Stopping condition met (all six fields reported, then stop)); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 8.
- Screenshot catch rate on common evidence: 2/8 (25.0%).
- DOM catch rate on common evidence: 8/8 (100.0%).
- DOM recovery of screenshot misses: 6/6 (100.0%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
