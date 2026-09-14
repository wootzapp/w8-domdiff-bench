# Evidence-Item Audit: browser_task_026-shopping-constraint-satisfaction-20260909T075313Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Search Amazon for 'wireless mouse' | Criterion-relevant browser state and final task claim | Present (screenshot9.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model9.txt m9:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Apply required filters and sort order | Criterion-relevant browser state and final task claim | Present (screenshot8.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model6.txt m6:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Report top product (rank #1 after sort) | Criterion-relevant browser state and final task claim | Present (screenshot9.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model4.txt m4:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Report second product (rank #2 after sort) | Criterion-relevant browser state and final task claim | Present (screenshot4.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model8.txt m8:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report third product (rank #3 after sort) | Criterion-relevant browser state and final task claim | Present (screenshot9.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model8.txt m8:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Respect constraints and stopping condition | Criterion-relevant browser state and final task claim | Present (screenshot5.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model7.txt m7:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C6 | Handle bot check / access block appropriately | Criterion-relevant browser state and final task claim | Present (screenshot9.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model8.txt m8:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 7.
- Screenshot catch rate on common evidence: 7/7 (100.0%).
- DOM catch rate on common evidence: 7/7 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
