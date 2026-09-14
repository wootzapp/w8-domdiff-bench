# Evidence-Item Audit: browser_task_028-news-monitoring-20260909T075747Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access BBC Technology section (bbc.com/technology) without signing in | Criterion-relevant browser state and final task claim | Present (screenshot1.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model1.txt m1:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Record the five most recent BBC Technology headlines | Criterion-relevant browser state and final task claim | Present (screenshot1.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model1.txt m1:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Record publication timestamps exactly as displayed for each of the five headlines | Criterion-relevant browser state and final task claim | Present (screenshot1.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model2.txt m2:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Stop after recording five newest headlines and timestamps | Criterion-relevant browser state and final task claim | Present (screenshot1.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model0.txt m0:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Respect constraints: no sign-in and no ad interaction | Criterion-relevant browser state and final task claim | Present (screenshot1.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model0.txt m0:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 5.
- Screenshot catch rate on common evidence: 5/5 (100.0%).
- DOM catch rate on common evidence: 5/5 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
