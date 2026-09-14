# Evidence-Item Audit: browser_task_065-public-transport-interchange-inspection-20260909T084306Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Retrieve/use the official TfL StopPoint response for HUBKGX (or report inability to access it) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Retrieve/use the official TfL StopPoint response for HUBKGX (or report inability to access it)); verifier caught | Present (dom_model37.txt m37:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report StopPoint ID | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot35.png: Report StopPoint ID); verifier caught | Present (dom_model37.txt m37:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Report common name | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot35.png: Report common name); verifier caught | Present (dom_model2.txt m2:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Report latitude and longitude | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot37.png: Report latitude and longitude); verifier caught | Present (dom_model38.txt m38:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report every top-level transport mode | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report every top-level transport mode); verifier caught | Present (dom_model38.txt m38:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Report Zone value from additionalProperties (key = Zone) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot16.png: Report Zone value from additionalProperties (key = Zone)); verifier caught | Present (dom_model38.txt m38:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C6 | Report every Tube line identifier from lineModeGroups where modeName = tube | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot14.png: Report every Tube line identifier from lineModeGroups where modeName = tube); verifier caught | Present (dom_model38.txt m38:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C7 | Stopping condition satisfied (no extra fields beyond requested set) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot35.png: Stopping condition satisfied (no extra fields beyond requested set)); verifier caught | Present (dom_model37.txt m37:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 8.
- Screenshot catch rate on common evidence: 8/8 (100.0%).
- DOM catch rate on common evidence: 8/8 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
