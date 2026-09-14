# Evidence-Item Audit: browser_task_075-collectible-card-rules-20260909T090552Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use only the exact-card Scryfall API response at the provided URL | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Use only the exact-card Scryfall API response at the provided URL); verifier caught | Present (dom_model5.txt m5:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Record card identity fields: name, mana_cost, type_line | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Record card identity fields: name, mana_cost, type_line); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Record complete oracle_text | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Record complete oracle_text); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Record reserved flag | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot5.png: Record reserved flag); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C4 | Record format legalities: Vintage, Legacy, Commander | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot5.png: Record format legalities: Vintage, Legacy, Commander); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C5 | Respect task constraints (no pricing/links; stop after requested fields) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot6.png: Respect task constraints (no pricing/links; stop after requested fields)); verifier caught | Present (dom_model2.txt m2:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 2.
- Screenshot catch rate on common evidence: 2/2 (100.0%).
- DOM catch rate on common evidence: 2/2 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
