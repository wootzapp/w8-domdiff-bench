# Evidence-Item Audit: browser_task_020-github-code-search-20260909T074624Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Repository-scoped code-search attempt and resulting sign-in blocker | Repo-scoped class Depends search attempted; GitHub sign-in wall encountered | Present (screenshot6.png: Sign in to search code on GitHub); verifier caught | Present (dom_model6.txt m6:L22-L22; dom_model6.txt m6:L48-L49); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Whether the true Depends definition location was identified or blocked | Definition location not shown because code-search results were blocked | Present (screenshot6.png: Sign in to search code on GitHub); verifier caught | Present (dom_model6.txt m6:L48-L49); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Whether an exact definition file path and line number were available | No exact definition path or line number shown; sign-in blocker visible | Present (screenshot6.png: Sign in to search code on GitHub); verifier caught | Present (dom_model6.txt m6:L48-L49); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Whether declaration context for Depends was available | No declaration header or code context shown; sign-in blocker visible | Present (screenshot6.png: Sign in to search code on GitHub); verifier caught | Present (dom_model6.txt m6:L48-L49); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | No sign-in/edit/PR and appropriate response to the blocker | Agent remained signed out, made no edit/PR, and stopped after reporting the blocker | Present (screenshot6.png: Sign in; Sign up); verifier caught | Present (dom_model6.txt m6:L48-L49); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 5.
- Screenshot catch rate on common evidence: 5/5 (100.0%).
- DOM catch rate on common evidence: 5/5 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
