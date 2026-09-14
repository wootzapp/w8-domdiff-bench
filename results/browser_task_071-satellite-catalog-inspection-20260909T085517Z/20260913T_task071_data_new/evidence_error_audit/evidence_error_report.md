# Evidence-Item Audit: browser_task_071-satellite-catalog-inspection-20260909T085517Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access the CelesTrak SATCAT record for CATNR=25544 (or clearly report access failure) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Access the CelesTrak SATCAT record for CATNR=25544 (or clearly report access failure)); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Use the CelesTrak SATCAT record only (no switching objects/sources; no expanding codes) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Use the CelesTrak SATCAT record only (no switching objects/sources; no expanding codes)); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Report identity fields (name, international designator, NORAD catalog number, object type) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Report identity fields (name, international designator, NORAD catalog number, object type)); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Report status/ownership fields using raw codes (operational status code, owner code) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Report status/ownership fields using raw codes (operational status code, owner code)); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report launch fields (launch date and launch-site code) using raw code | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Report launch fields (launch date and launch-site code) using raw code); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Report orbital parameters (period, inclination, apogee, perigee) with exact numbers/units | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Report orbital parameters (period, inclination, apogee, perigee) with exact numbers/units); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C6 | Honor stopping condition (stop after recording all requested fields from the displayed record) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Honor stopping condition (stop after recording all requested fields from the displayed record)); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 7.
- Screenshot catch rate on common evidence: 7/7 (100.0%).
- DOM catch rate on common evidence: 7/7 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
