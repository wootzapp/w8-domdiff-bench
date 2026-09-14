# Evidence-Item Audit: browser_task_078-cross-endpoint-game-data-20260909T094544Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use only the supplied Pikachu Pokémon response and its returned species.url | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot37.png: Use only the supplied Pikachu Pokémon response and its returned species.url); verifier caught | Present (dom_model8.txt m8:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report required Pokémon fields (id, raw height, raw weight, base_experience) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Report required Pokémon fields (id, raw height, raw weight, base_experience)); verifier caught | Present (dom_model70.txt m70:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Report all types in slot order using exact API strings | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot40.png: Report all types in slot order using exact API strings); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Compute and report the highest base stat (include ties) from complete stats array | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot40.png: Compute and report the highest base stat (include ties) from complete stats array); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C4 | Open species.url and report species fields (color.name, habitat.name, capture_rate, generation.name) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot37.png: Open species.url and report species fields (color.name, habitat.name, capture_rate, generation.name)); verifier caught | Present (dom_model11.txt m11:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Stop after recording all requested fields (no extra/unrequested outputs) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot36.png: Stop after recording all requested fields (no extra/unrequested outputs)); verifier caught | Present (dom_model25.txt m25:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 4.
- Screenshot catch rate on common evidence: 4/4 (100.0%).
- DOM catch rate on common evidence: 4/4 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
