# Evidence-Item Audit: browser_task_022-stackoverflow-search-20260909T074929Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Correct python+pandas tagged listing in a logged-out session | Both tags visible; no sign-in | Present (screenshot6.png: Tagged with python pandas; Log in; Sign up); verifier caught | Present (dom_model6.txt m6:L1-L2; dom_model6.txt m6:L17-L18; dom_model6.txt m6:L46-L47); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Applied last-365-days filter and highest-score sort, with score>=50 and accepted-only constraints still absent | 365-day window and Highest score applied; two required constraints not applied | Present (screenshot6.png: 295 questions from the last 365 days; Days old 365; Highest score selected); verifier caught | Present (dom_model6.txt m6:L1-L2; dom_model6.txt m6:L38-L40; dom_model6.txt m6:L101-L108); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Evidence for three qualifying question records or a justified zero-result conclusion | No verified top-three qualifying records and no proof that zero qualifying questions exist | Present (screenshot6.png: 8 votes, 347 views; 6 votes, 224 views; screenshot7.png: Multiple 5-vote question rows); verifier caught | Present (dom_model6.txt m6:L39-L74; dom_model7.txt m7:L38-L66); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | No prohibited interaction and stopping-state evidence | Logged out with only filter, cookie, typing, apply, and scroll actions; task stopped prematurely | Present (screenshot6.png: Log in; Sign up; screenshot7.png: Question-list browsing only); verifier caught | Present (dom_model6.txt m6:L17-L18; dom_model7.txt m7:L17-L18); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 4.
- Screenshot catch rate on common evidence: 4/4 (100.0%).
- DOM catch rate on common evidence: 4/4 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
