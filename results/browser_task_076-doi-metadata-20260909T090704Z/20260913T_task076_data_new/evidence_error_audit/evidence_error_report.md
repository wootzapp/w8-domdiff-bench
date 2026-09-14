# Evidence-Item Audit: browser_task_076-doi-metadata-20260909T090704Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use only the supplied Crossref response (message object fields) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Use only the supplied Crossref response (message object fields)); verifier caught | Present (dom_model4.txt m4:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report work title from message.title | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot2.png: Report work title from message.title); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Report publisher from message.publisher | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report publisher from message.publisher); verifier caught | Present (dom_model4.txt m4:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Report published date from message.published.date-parts | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot2.png: Report published date from message.published.date-parts); verifier caught | Present (dom_model6.txt m6:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report work type from message.type | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot2.png: Report work type from message.type); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C5 | Report complete ordered author list from message.author | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot2.png: Report complete ordered author list from message.author); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C6 | Stop after recording the requested fields (stopping condition) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Stop after recording the requested fields (stopping condition)); verifier caught | Present (dom_model6.txt m6:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 4.
- Screenshot catch rate on common evidence: 4/4 (100.0%).
- DOM catch rate on common evidence: 4/4 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
