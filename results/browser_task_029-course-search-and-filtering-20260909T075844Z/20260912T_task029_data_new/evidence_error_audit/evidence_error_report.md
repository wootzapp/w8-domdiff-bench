# Evidence-Item Audit: browser_task_029-course-search-and-filtering-20260909T075844Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access Coursera Data Science browse/search results without signing in | Criterion-relevant browser state and final task claim | Present (screenshot12.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model18.txt m18:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Apply all requested Coursera filters (Data Science subject, Beginner level, English language, 1–3 months duration) or document unavoidable UI limitations | Criterion-relevant browser state and final task claim | Present (screenshot18.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model18.txt m18:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Identify the three highest-rated matching courses (or report fewer if not available) | Criterion-relevant browser state and final task claim | Present (screenshot15.png: Criterion-relevant visible browser state); verifier missed | Present (dom_model13.txt m13:L99-L101); verifier caught | `SCREENSHOT_MISSED_DOM_CAUGHT` | DOM |
| C3 | Report required fields for Course #1 (title, rating, enrollment count if displayed) | Criterion-relevant browser state and final task claim | Present (screenshot7.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model4.txt m4:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report required fields for Course #2 (title, rating, enrollment count if displayed) | Criterion-relevant browser state and final task claim | Present (screenshot7.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model4.txt m4:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Report required fields for Course #3 (title, rating, enrollment count if displayed) | Criterion-relevant browser state and final task claim | Present (screenshot7.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model4.txt m4:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C6 | Comply with constraints (no sign-in; no enroll/purchase/start trial; stop after verification) | Criterion-relevant browser state and final task claim | Present (screenshot12.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model7.txt m7:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 7.
- Screenshot catch rate on common evidence: 6/7 (85.71%).
- DOM catch rate on common evidence: 7/7 (100.0%).
- DOM recovery of screenshot misses: 1/1 (100.0%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
