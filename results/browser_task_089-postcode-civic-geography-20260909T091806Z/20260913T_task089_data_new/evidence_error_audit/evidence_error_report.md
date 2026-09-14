# Evidence-Item Audit: browser_task_089-postcode-civic-geography-20260909T091806Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Report 11 specific fields from the result object for SW1A2AA | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: All eleven requested result fields, including admin_district, admin_ward, and codes.admin_district); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C1 | Use only result object fields (with sole exception of codes.admin_district) and keep fields distinct | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Direct result fields and nested result.codes.admin_district); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Preserve exact formatting/precision as returned | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: SW1A 2AA; St James's; 51.503541; -0.12767; E09000033); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Stopping condition: stop after recording all 11 requested fields | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Final answer contains only the eleven requested fields); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 1.
- Screenshot catch rate on common evidence: 1/1 (100.0%).
- DOM catch rate on common evidence: 1/1 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
