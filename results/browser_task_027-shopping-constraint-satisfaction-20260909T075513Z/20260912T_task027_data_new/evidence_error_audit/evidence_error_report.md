# Evidence-Item Audit: browser_task_027-shopping-constraint-satisfaction-20260909T075513Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Browse eBay without restricted actions (no sign-in, no bid/cart/purchase) | Criterion-relevant browser state and final task claim | Present (screenshot8.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model12.txt m12:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Find a laptop listing in the $600–$900 range that appears to meet RAM/SSD thresholds | Criterion-relevant browser state and final task claim | Present (screenshot7.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model7.txt m7:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Open product detail page and verify RAM and SSD from the item specifics/detail table when available | Criterion-relevant browser state and final task claim | Present (screenshot12.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model12.txt m12:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Report model, price, RAM, and SSD capacity (with confirmation source) | Criterion-relevant browser state and final task claim | Present (screenshot8.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model9.txt m9:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Stop after one qualifying laptop is verified, and handle bot-check/CAPTCHA appropriately | Criterion-relevant browser state and final task claim | Present (screenshot0.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model9.txt m9:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 5.
- Screenshot catch rate on common evidence: 5/5 (100.0%).
- DOM catch rate on common evidence: 5/5 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
