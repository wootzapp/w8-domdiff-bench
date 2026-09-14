# Evidence-Item Audit: browser_task_001-reddit-ranking-20260909T070105Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access to r/LocalLLaMA was prevented by an external blocker, which the agent reported without signing in | Reddit network security block page: 'You've been blocked by network security. To continue, log in to your Reddit account or use your developer token' | Present (screenshot0.png: You've been blocked by network security.); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | 'Top' sort and 'This Week' time filter could not be applied or verified because the feed never loaded | No feed/sort/time-filter UI rendered - only the security block page | Present (screenshot0.png: You've been blocked by network security.); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | The #1 post title and score were not observable because Reddit blocked the feed | No posts, titles, or scores rendered - only the security block page | Present (screenshot0.png: You've been blocked by network security.); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | The trajectory never signed in and performed no prohibited interactions (vote/comment/save/post) | Unauthenticated block page with the 'Log in' button never clicked | Present (screenshot0.png: Log in); verifier caught | Present (dom_model0.txt m0:L8-L8); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | The agent stopped after documenting the blocker instead of continuing to browse | Trajectory ends at the block page (0 actions beyond the initial state) | Present (screenshot0.png: You've been blocked by network security.); verifier caught | Present (dom_model0.txt m0:L7-L7); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 5.
- Screenshot catch rate on common evidence: 5/5 (100.0%).
- DOM catch rate on common evidence: 5/5 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
