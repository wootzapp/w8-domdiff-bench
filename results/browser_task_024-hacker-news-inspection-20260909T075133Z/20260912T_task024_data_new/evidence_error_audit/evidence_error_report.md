# Evidence-Item Audit: browser_task_024-hacker-news-inspection-20260909T075133Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Hacker News front page and ranked story list | news.ycombinator.com front page with numbered stories | Present (screenshot0.png: Hacker News; numbered story list); verifier caught | Present (dom_model0.txt m0:L8-L10); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Complete coverage of stories 1 through 30 across ordered states | Every rank from 1 through 30 is present across the evidence sequence | Present (screenshot0.png: Stories 1–23; screenshot1.png: Stories 11–30); verifier caught | Present (dom_model0.txt m0:L15-L24; dom_model1.txt m1:L48-L55); verifier missed | `DOM_MISSED_SCREENSHOT_CAUGHT` | SCREENSHOT |
| C2 | Exactly one github.com-linked story among ranks 1–30, with its title | 1 — I-have-ADHD: A skill to stop coding agents from burying the answer | Present (screenshot0.png: 20. I-have-ADHD: A skill to stop coding agents from burying the answer (github.com/ayghri); screenshot1.png: Rows 11–30 with no second github.com domain); verifier caught | Present (dom_model0.txt m0:L15-L24; dom_model0.txt m0:L49-L50; dom_model1.txt m1:L44-L55); verifier missed | `DOM_MISSED_SCREENSHOT_CAUGHT` | SCREENSHOT |
| C3 | Only passive inspection and scrolling; no prohibited interaction | Logged out with only one scroll action | Present (screenshot0.png: login); verifier caught | Present (dom_model0.txt m0:L8-L9); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 4.
- Screenshot catch rate on common evidence: 4/4 (100.0%).
- DOM catch rate on common evidence: 2/4 (50.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 2/2 (100.0%).
