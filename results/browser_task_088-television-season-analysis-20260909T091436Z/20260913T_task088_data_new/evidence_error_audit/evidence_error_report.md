# Evidence-Item Audit: browser_task_088-television-season-analysis-20260909T091436Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Restrict analysis to TVMaze episode list for show 82 and season = 1 only | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot6.png: Season 1 episode 10 followed by Season 2 episode 1); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C1 | Report correct season-1 episode count | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot6.png: Season 1 episode number 10 before Season 2 begins); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Report boundary episodes (first and final) for season 1 with required fields | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot6.png: Fire and Blood; season 1; number 10; airdate 2011-06-19); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Identify maximum non-null rating.average among season-1 episodes using rating.average for ranking | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot5.png: Season 1 rating.average values including 8.9); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C4 | Report all season-1 episodes tied for highest rating with required fields (no arbitrary tie-breaking) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot6.png: Fire and Blood rating.average 8.9); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C5 | Stopping condition adherence (report only requested outputs) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Episode response contains summaries that the final answer does not reproduce); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 1.
- Screenshot catch rate on common evidence: 1/1 (100.0%).
- DOM catch rate on common evidence: 1/1 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
