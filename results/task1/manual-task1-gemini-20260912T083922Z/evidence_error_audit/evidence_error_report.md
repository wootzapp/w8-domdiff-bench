# Evidence-Item Audit: viewport-modern-1-cross-site-research-20260829T074513Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Agent used Xbox.com and navigated to the Xbox games section while attempting to locate the 'Best sellers' list | xbox.com home page followed by the 'XBOX games' page (https://www.xbox.com/en-US/games) | Present (screenshot3.png: XBOX games); verifier caught | Present (dom_model3.txt m3:L9-L9); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Product page for the game selected from the list opened on Xbox.com | EA SPORTS™ Madden NFL 27 store product page (URL .../games/store/ea-sports-madden-nfl-27/9nj6f163vf8c) | Present (screenshot4.png: EA SPORTS™ Madden NFL 27); verifier caught | Present (dom_model4.txt m4:L2-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Publisher value shown on the product page | Electronic Arts | Present (screenshot6.png: Published by - Electronic Arts); verifier caught | Present (dom_model4.txt m4:L10-L10); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Developer value shown on the product page | Tiburon | Present (screenshot6.png: Developed by - Tiburon); verifier caught | Present (dom_model5.txt m5:L10-L11); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Release date value shown on the product page | 8/13/2026 | Present (screenshot6.png: Release date - 8/13/2026); verifier caught | Present (dom_model5.txt m5:L12-L13); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Trajectory stayed logged out and never initiated sign-in, purchase, or download | Unauthenticated store page with purchase CTAs ('GET EA PLAY', 'BUY $69.99+') unclicked and no sign-in/checkout/download flow | Present (screenshot5.png: GET EA PLAY  - OR -  BUY $69.99+); verifier caught | Present (dom_model4.txt m4:L34-L34); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 6.
- Screenshot catch rate on common evidence: 6/6 (100.0%).
- DOM catch rate on common evidence: 6/6 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
