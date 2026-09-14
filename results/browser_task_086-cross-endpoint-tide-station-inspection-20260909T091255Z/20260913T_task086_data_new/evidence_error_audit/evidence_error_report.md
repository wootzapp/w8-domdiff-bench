# Evidence-Item Audit: browser_task_086-cross-endpoint-tide-station-inspection-20260909T091255Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use only NOAA station 9414290 and its details.self URL (or clearly report access failure) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: details.self URL for station 9414290); verifier caught | Present (dom_model0.txt m0:L1-L1; dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report base-station fields (ID, name, state, lat/long, timezone abbreviation & correction) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: state CA; timezone PST; timezonecorr -8; id 9414290; name San Francisco; lat 37.806305); verifier caught | Present (dom_model0.txt m0:L1-L1; dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Follow details.self and report required linked-details fields | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: id 9414290; established; removed; noaachart; timemeridian; timezone; origyear); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Respect task constraints on exactness and stopping condition | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Exact linked-details values and empty removed value); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 4.
- Screenshot catch rate on common evidence: 4/4 (100.0%).
- DOM catch rate on common evidence: 4/4 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
