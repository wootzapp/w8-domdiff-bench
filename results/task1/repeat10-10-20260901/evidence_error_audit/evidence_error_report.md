# Evidence-Item Audit: viewport-modern-1-cross-site-research-20260829T074513Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Best sellers section or equivalent best-selling list is shown | Best sellers section/list | Absent | Absent | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C1 | Xbox product page for EA SPORTS Madden NFL 27 is open | EA SPORTS™ Madden NFL 27 product page | Present (screenshot4.png: EA SPORTS™ Madden NFL 27); verifier caught | Present (dom_model4.txt m4:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Opened product is traceable to a Best sellers list | Madden NFL 27 selected from Best sellers | Absent | Absent | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Publisher shown on product page | Electronic Arts | Present (screenshot6.png: Published by Electronic Arts); verifier caught | Present (dom_model4.txt m4:L8-L10; dom_model5.txt m5:L9-L9); verifier missed | `DOM_MISSED_SCREENSHOT_CAUGHT` | SCREENSHOT |
| C2 | Developer shown on product page | Tiburon | Present (screenshot6.png: Developed by Tiburon); verifier caught | Present (dom_model5.txt m5:L10-L11); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Release date shown on product page | 8/13/2026 | Present (screenshot6.png: Release date 8/13/2026); verifier caught | Present (dom_model5.txt m5:L12-L13); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | No sign-in flow was initiated | No sign-in | Present (screenshot7.png: EA SPORTS™ Madden NFL 27); verifier caught | Present (dom_model7.txt m7:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | No purchase or download was initiated | No purchase/download | Present (screenshot7.png: BUY $69.99+); verifier caught | Present (dom_model4.txt m4:L14-L16); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 6.
- Screenshot catch rate on common evidence: 6/6 (100.0%).
- DOM catch rate on common evidence: 5/6 (83.33%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 1/1 (100.0%).
