# Evidence-Item Audit: browser_task_072-regional-calendar-comparison-20260909T085558Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use only the official GOV.UK bank-holidays JSON response at the supplied URL (or clearly report access failure) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Use only the official GOV.UK bank-holidays JSON response at the supplied URL (or clearly report access failure)); verifier caught | Present (dom_model48.txt m48:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Scotland 2026 — report '2nd January' date and bunting | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot18.png: Scotland 2026 — report '2nd January' date and bunting); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Scotland 2026 — report 'Summer bank holiday' date and bunting | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot18.png: Scotland 2026 — report 'Summer bank holiday' date and bunting); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Scotland 2026 — report 'St Andrew’s Day' date and bunting | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot18.png: Scotland 2026 — report 'St Andrew’s Day' date and bunting); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C4 | England and Wales 2026 — report 'Summer bank holiday' date | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot8.png: England and Wales 2026 — report 'Summer bank holiday' date); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C5 | Stopping condition adhered to (only required events recorded) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot42.png: Stopping condition adhered to (only required events recorded)); verifier caught | Present (dom_model26.txt m26:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 2.
- Screenshot catch rate on common evidence: 2/2 (100.0%).
- DOM catch rate on common evidence: 2/2 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
