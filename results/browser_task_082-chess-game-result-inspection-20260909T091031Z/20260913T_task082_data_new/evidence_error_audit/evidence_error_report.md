# Evidence-Item Audit: browser_task_082-chess-game-result-inspection-20260909T091031Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access the specified public Lichess game page (Z01xx8LK) only | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Rapid Chess · Reini vs IloveAnya); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Record time control, rated/casual status, and speed category as displayed | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: 10+0 • Rated • Rapid); verifier caught | Present (dom_model1.txt m1:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Record both players' names, ratings, and rating changes (correct association) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Reini (1894) +8; IloveAnya (2010) −31); verifier caught | Present (dom_model1.txt m1:L14-L14; dom_model1.txt m1:L16-L16); verifier missed | `DOM_MISSED_SCREENSHOT_CAUGHT` | SCREENSHOT |
| C3 | Record termination/victory statement, winner, and number of moves | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Checkmate • White is victorious; Reini won by checkmate after 28 moves); verifier caught | Present (dom_model1.txt m1:L14-L14; dom_model1.txt m1:L16-L16); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Respect constraints and stopping condition | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: SIGN IN; REGISTER); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 5.
- Screenshot catch rate on common evidence: 5/5 (100.0%).
- DOM catch rate on common evidence: 4/5 (80.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 1/1 (100.0%).
