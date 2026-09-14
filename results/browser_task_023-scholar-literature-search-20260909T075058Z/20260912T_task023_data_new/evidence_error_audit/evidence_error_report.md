# Evidence-Item Audit: browser_task_023-scholar-literature-search-20260909T075058Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Logged-out Google Scholar attempt ending at the access block | Access block explicitly present; unavailable requested evidence not fabricated | Present (screenshot0.png: SIGN IN; screenshot2.png: Our systems have detected unusual traffic from your computer network. Please try your request again later.); verifier caught | Present (dom_model0.txt m0:L13-L23; dom_model2.txt m2:L7-L8); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Original citation count unavailable because the block occurred before results | Access block explicitly present; unavailable requested evidence not fabricated | Present (screenshot2.png: Our systems have detected unusual traffic from your computer network. Please try your request again later.); verifier caught | Present (dom_model2.txt m2:L7-L8); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Cited-by results and 2024+ filter unavailable because of the block | Access block explicitly present; unavailable requested evidence not fabricated | Present (screenshot2.png: Our systems have detected unusual traffic from your computer network. Please try your request again later.); verifier caught | Present (dom_model2.txt m2:L7-L8); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | First citing-paper record unavailable because of the block | Access block explicitly present; unavailable requested evidence not fabricated | Present (screenshot2.png: Our systems have detected unusual traffic from your computer network. Please try your request again later.); verifier caught | Present (dom_model2.txt m2:L7-L8); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Second citing-paper record unavailable because of the block | Access block explicitly present; unavailable requested evidence not fabricated | Present (screenshot2.png: Our systems have detected unusual traffic from your computer network. Please try your request again later.); verifier caught | Present (dom_model2.txt m2:L7-L8); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Third citing-paper record unavailable because of the block | Access block explicitly present; unavailable requested evidence not fabricated | Present (screenshot2.png: Our systems have detected unusual traffic from your computer network. Please try your request again later.); verifier caught | Present (dom_model2.txt m2:L7-L8); verifier caught | `BOTH_CAUGHT` | TIE |
| C6 | Stopped at the block without fabricating or adding citing-paper records | Access block explicitly present; unavailable requested evidence not fabricated | Present (screenshot2.png: Our systems have detected unusual traffic from your computer network. Please try your request again later.); verifier caught | Present (dom_model2.txt m2:L7-L8); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 7.
- Screenshot catch rate on common evidence: 7/7 (100.0%).
- DOM catch rate on common evidence: 7/7 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
