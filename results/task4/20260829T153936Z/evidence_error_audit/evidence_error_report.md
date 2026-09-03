# Evidence-Item Audit: viewport-modern-4-nasa-mission-lookup-20260829T074852Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | NASA-controlled pages are used without sign-in or registration | NASA.gov Artemis pages; unauthenticated browsing | Present (screenshot1.png: NASA; Artemis; Artemis I; Artemis II; Artemis III; Artemis IV); verifier caught | Present (dom_model2.txt m2:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Mission name shown on the mission page | Artemis II | Present (screenshot2.png: Artemis II); verifier missed | Present (dom_model2.txt m2:L27-L29); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C1 | Mission status needed to determine whether Artemis II is still upcoming | Occurred 5 months ago | Present (screenshot2.png: OCCURRED 5 MONTHS AGO); verifier missed | Present (dom_model2.txt m2:L27-L29); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C1 | NASA-stated Artemis II launch date/year | Launched April 1, 2026 | Present (screenshot2.png: LAUNCHED April 1, 2026); verifier missed | Present (dom_model2.txt m2:L34-L35); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C1 | Mission destination/type | Crewed Lunar Flyby | Present (screenshot2.png: MISSION TYPE Crewed Lunar Flyby); verifier missed | Present (dom_model2.txt m2:L30-L31); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C1 | NASA-stated primary mission objective | First crewed Artemis flight; step toward long-term Moon return and future Mars missions | Present (screenshot2.png: The first crewed Artemis flight marks a key step toward long-term return to the Moon and future missions to Mars.); verifier missed | Present (dom_model2.txt m2:L27-L29); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C2 | Trajectory stops after reaching the mission-detail page and answering | No browsing actions after the Artemis II final state | Present (screenshot2.png: Artemis II); verifier caught | Present (dom_model2.txt m2:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 7.
- Screenshot catch rate on common evidence: 2/7 (28.57%).
- DOM catch rate on common evidence: 7/7 (100.0%).
- DOM recovery of screenshot misses: 5/5 (100.0%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
