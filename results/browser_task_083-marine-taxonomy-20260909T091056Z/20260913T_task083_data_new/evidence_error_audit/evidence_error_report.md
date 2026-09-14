# Evidence-Item Audit: browser_task_083-marine-taxonomy-20260909T091056Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access the specified WoRMS taxon record (AphiaID 137106) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Stenella clymene (Gray, 1850); AphiaID 137106); verifier caught | Present (dom_model0.txt m0:L1-L1; dom_model0.txt m0:L30-L30); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report identity fields: AphiaID and scientific name with authority (from the main record header) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: AphiaID 137106; Stenella clymene (Gray, 1850)); verifier caught | Present (dom_model0.txt m0:L30-L30; dom_model0.txt m0:L2-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Report taxonomic status from the record (without substituting synonyms) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Status accepted); verifier caught | Present (dom_model0.txt m0:L62-L62; dom_model0.txt m0:L63-L63); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Report genus and family from the Classification section | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Delphinidae (Family); Stenella (Genus)); verifier caught | Present (dom_model0.txt m0:L56-L56; dom_model0.txt m0:L58-L58); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report displayed environment states (affirmed vs struck-through) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Environment: marine; terrestrial shown struck through); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C5 | Stopping condition: stop after recording requested fields only | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: The final answer contains only the requested WoRMS fields); verifier caught | Present (dom_model0.txt m0:L2-L2); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 5.
- Screenshot catch rate on common evidence: 5/5 (100.0%).
- DOM catch rate on common evidence: 5/5 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
