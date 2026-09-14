# Evidence-Item Audit: browser_task_087-river-monitoring-20260909T091320Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use the correct USGS monitoring location (USGS-01646500) and Continuous Data section | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Potomac River Near Wash, DC Little Falls Pump Sta - USGS-01646500); verifier caught | Present (dom_model2.txt m2:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report station name | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Potomac River Near Wash, DC Little Falls Pump Sta - USGS-01646500); verifier caught | Present (dom_model2.txt m2:L24-L24); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Latest Continuous Data observation: Discharge (cubic feet per second) | Criterion-relevant evidence sufficient to evaluate the agent response | Absent | Present (dom_model2.txt m2:L24-L24); verifier caught | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Latest Continuous Data observation: Gage height (feet) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot4.png: Gage height, feet: 2.82 ft - Sep 09, 2026 04:50:00 AM EDT); verifier caught | Present (dom_model3.txt m3:L25-L25); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Display both series if not initially shown; preserve provisional labels and stop after required reporting | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot2.png: Graph controls for Gage height and Discharge); verifier caught | Present (dom_model2.txt m2:L9-L9; dom_model2.txt m2:L10-L10); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 4.
- Screenshot catch rate on common evidence: 4/4 (100.0%).
- DOM catch rate on common evidence: 4/4 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
