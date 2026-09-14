# Data-New Tasks 1–100: Screenshot vs DOM-Model Results

This standalone report covers the 98 completed and audited tasks from `data-new/`. It excludes all runs from the older `data/` dataset and excludes the later noncanonical rerun of Task 1. Tasks 77 and 97 are not included in the aggregates because Task 77 has no matching screenshot/DOM pair and Task 97 has no completed verifier run. Each task used one frozen rubric for both verifier modes and includes the saved score, token usage, criterion-level evidence audit, manual source findings, and artifact links.

The numerical fields below were cross-checked against the canonical `20260909T_task001_data_new` through `20260909T_task019_data_new` comparison JSON files; the `20260912T_task020_data_new` through `20260912T_task030_data_new` and `20260912T_task061_data_new` through `20260912T_task070_data_new` runs; the `20260913T_task071_data_new` through `20260913T_task090_data_new` runs, excluding unavailable Task 77; the `20260914T_task031_data_new` through `20260914T_task060_data_new` runs (Task 47 uses the completed `_retry` run after an interrupted empty partial run); and the completed `20260913T_task091_data_new` through `20260914T_task100_data_new` runs, excluding unrun Task 97. Evidence-loss classifications come from the completed screenshot/DOM source audit recorded for each task.

## Overall result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Tasks audited | 98 | 98 |
| Rubric criteria audited | 621 | 621 |
| Aggregate process points | 1157/1723 | 1146/1723 |
| Scoring tokens | 11,215,516 | 15,083,036 |
| Asymmetric source-evidence loss | 28/621 (4.5%) | 79/621 (12.7%) |

Across 621 criteria, the cumulative asymmetric source gaps are twenty-eight screenshot losses and seventy-nine DOM losses. The cumulative confirmed verifier misses are eight screenshot misses and eight DOM misses. Tasks 51–60 add thirteen screenshot source gaps, no DOM source gaps, one screenshot-verifier miss, and three DOM-verifier interpretation misses. Tasks 41–50 add three screenshot source gaps, six DOM source gaps, and one DOM-verifier interpretation miss. Tasks 31–40 add two screenshot source gaps and no DOM source gaps; Tasks 91–96 and 98–100 add two screenshot source gaps and thirteen DOM source gaps. For Tasks 81–90 specifically, the second audit confirmed one screenshot source gap, twenty-one DOM source gaps, and two DOM-verifier grounding misses. DOM gaps include omitted linked text, lost formatting/typography, and fixed-prefix truncation of long JSON responses; they are not inferred merely from lower scores.

## Task 1 — Reddit ranking

Task ID: `browser_task_001-reddit-ranking-20260909T070105Z`

Run: `20260909T_task001_data_new`

Frozen rubric: 5 criteria, 17 maximum points

Rubric SHA-256: `08053dc4514113054566c6ea9f0a4a9e785428805d5e8f12c9f129ddcf7b8fbb`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/17 (100%) | 17/17 (100%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Failure | Environment blocker | Environment blocker |
| Actions / states | 0 / 1 screenshot | 0 / 1 DOM state |
| Scoring LLM calls | 10 | 11 |
| API attempts / retries | 10 / 0 | 11 / 0 |
| Duration | 74.605 s | 86.565 s |

Both verifiers gave full process credit because the rubric permits full credit when an external blocker is clearly reported. Both outcome checks still failed because the requested #1 post title and score were not delivered.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 55,544 | 5,626 | 1,600 | 61,170 |
| DOM model | 54,643 | 6,267 | 1,280 | 60,910 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 260 fewer scoring tokens, a 0.4% reduction. Rubric generation was separate: 12,591 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access r/LocalLLaMA without signing in | Blocker visible / Yes | Blocker explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Apply Top + This Week | Blocker proves controls unavailable / Yes | Blocker proves controls unavailable / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Report #1 post title and score | Blocker proves feed unavailable / Yes | Blocker proves feed unavailable / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Respect no-login/no-interaction constraints | Empty action history and blocked state / Yes | Empty action history and blocked state / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop at the appropriate point | Zero actions and blocker reported / Yes | Zero actions and blocker reported / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual source check confirmed that `screenshot0.png` visibly says “You've been blocked by network security,” and `dom_model0.txt` contains the same message, login/developer-token requirement, and absence of subreddit content. The blank DOM title warning did not remove relevant evidence, and the DOM source was not truncated.

### Evidence-error result

- Screenshot evidence misses: **0/5**
- DOM-model evidence misses: **0/5**
- Asymmetric evidence loss: **0/5**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both modalities and both verifiers behaved consistently. The task failed because of a genuine website access blocker, not because either evidence representation or verifier missed available information.

### Artifacts

- [Frozen rubric](rubrics/browser_task_001-reddit-ranking-20260909T070105Z.json)
- [Comparison report](results/browser_task_001-reddit-ranking-20260909T070105Z/20260909T_task001_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_001-reddit-ranking-20260909T070105Z/20260909T_task001_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_001-reddit-ranking-20260909T070105Z/20260909T_task001_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_001-reddit-ranking-20260909T070105Z/20260909T_task001_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 2 — Xbox cross-site research

Task ID: `browser_task_002-cross-site-research-20260909T070119Z`

Run: `20260909T_task002_data_new`

Frozen rubric: 4 criteria, 15 maximum points

Rubric SHA-256: `2157f3abcd304f7618cb600205bd1f4ac17cb9bfeb93fd0b39f1da3c1e795d6a`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 8/15 (53.3%) | 11/15 (73.3%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 10 / 11 screenshots | 10 / 11 DOM states |
| Scoring LLM calls | 25 | 32 |
| API attempts / retries | 25 / 0 | 32 / 0 |
| Duration | 101.142 s | 116.420 s |

DOM scored three points higher because its final state explicitly preserved the developer and release date. Both modes failed the outcome because “Best sellers” provenance and the publisher field were not proven.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 126,243 | 10,769 | 1,792 | 137,012 |
| DOM model | 133,979 | 12,991 | 1,792 | 146,970 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 9,958 more scoring tokens, a 7.3% increase. Rubric generation was separate: 12,591 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Select a game from Best sellers | Positive provenance absent / correctly rejected | Positive provenance absent / correctly rejected | 2/4 / 2/4 | BOTH_CAUGHT |
| Open selected product page | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Publisher, developer, release date | Developer/date absent; publisher ambiguous / correctly limited | Developer/date explicit; publisher relation missing / correctly limited | 0/5 / 3/5 | SCREENSHOT_EVIDENCE_MISSING |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that no screenshot displays a “Best sellers” section. The product page is clearly visible in `screenshot9.png`, but `screenshot10.png` stops in the Gallery/Description area before the developer and release-date fields. In `dom_model10.txt`, the exact values `Developed by → Tiburon` and `Release date → 8/13/2026` are present. The DOM shows a `Published by` label without its associated value; `Electronic Arts` appears separately near the title, so neither verifier treated that as conclusive publisher evidence.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **1/4 criteria**
- DOM-side asymmetric evidence loss: **0/4 criteria**
- Confirmed verifier perception misses: **0/4 criteria**
- DOM recovery of screenshot source gaps: **1/1 eligible criterion**
- Verifier-miss recovery rate: **N/A (neither verifier overlooked available evidence)**

**Summary:** DOM recovered developer and release-date evidence that the screenshot sequence did not capture, producing the higher process score. This was screenshot capture loss, not a screenshot-verifier reading error. DOM used more tokens and still lacked a reliable publisher label–value relationship.

### Artifacts

- [Frozen rubric](rubrics/browser_task_002-cross-site-research-20260909T070119Z.json)
- [Comparison report](results/browser_task_002-cross-site-research-20260909T070119Z/20260909T_task002_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_002-cross-site-research-20260909T070119Z/20260909T_task002_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_002-cross-site-research-20260909T070119Z/20260909T_task002_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_002-cross-site-research-20260909T070119Z/20260909T_task002_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 3 — Microsoft Careers job extraction

Task ID: `browser_task_003-job-listing-extraction-20260909T070258Z`

Run: `20260909T_task003_data_new`

Frozen rubric: 7 criteria, 20 maximum points

Rubric SHA-256: `6cb1ce774b4da7e22243c6a0ae5ffb597dc341935f8a53dfbce2c309d01e3fb2`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/20 (85.0%) | 17/20 (85.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 36 / 37 screenshots | 36 / 37 DOM states |
| Scoring LLM calls | 58 | 70 |
| API attempts / retries | 58 / 0 | 70 / 0 |
| Duration | 101.738 s | 122.890 s |

Both verifiers produced the same criterion scores. The process rubric passed, but both outcome checks failed because the agent's two reported responsibilities did not match the listing's actual responsibility bullets.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 278,622 | 17,104 | 1,792 | 295,726 |
| DOM model | 383,016 | 22,506 | 1,536 | 405,522 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 109,796 more scoring tokens, a 37.1% increase. Rubric generation was separate: 13,370 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Search Applied Scientist in Redmond | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Open one relevant listing | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report job number | Yes: `200017828` / Yes | Yes: `200017828` / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report work-site arrangement | Yes: `3 days / week in-office` / Yes | Yes: `3 days / week in-office` / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report two responsibilities | Yes / Yes, but answer contradicted source | Yes / Yes, but answer contradicted source | 0/3 / 0/3 | BOTH_CAUGHT |
| Report two preferred qualifications | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Respect no-sign-in/no-application constraints | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |

Manual inspection confirmed the job metadata in `screenshot4.png` and `dom_model4.txt`, the actual responsibility bullets in `screenshot5.png` and `dom_model5.txt`, and preferred qualifications in `screenshot6.png` and `dom_model6.txt`. The final answer replaced the listing's explicit responsibilities—LLM fine-tuning with RLHF, agent adversarial evaluations/safety mitigations, and delivering mitigations with the Responsible AI engineering team—with unsupported generalized duties. Both verifiers detected that mismatch correctly. The automated audit's two wording-based disagreement flags did not correspond to score, evidence-presence, or verifier-catch disagreements.

### Evidence-error result

- Screenshot evidence misses: **0/7 criteria**
- DOM-model evidence misses: **0/7 criteria**
- Asymmetric evidence loss: **0/7 criteria**
- Confirmed verifier perception misses: **0/7 criteria**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both representations contained the required evidence and both verifiers interpreted it consistently. The task failed because the agent reported incorrect responsibilities, not because screenshot or DOM evidence was missing or overlooked. DOM used 37.1% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_003-job-listing-extraction-20260909T070258Z.json)
- [Comparison report](results/browser_task_003-job-listing-extraction-20260909T070258Z/20260909T_task003_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_003-job-listing-extraction-20260909T070258Z/20260909T_task003_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_003-job-listing-extraction-20260909T070258Z/20260909T_task003_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_003-job-listing-extraction-20260909T070258Z/20260909T_task003_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 4 — DMNS museum film lookup

Task ID: `browser_task_004-museum-film-lookup-20260909T071414Z`

Run: `20260909T_task004_data_new`

Frozen rubric: 5 criteria, 15 maximum points

Rubric SHA-256: `81ae2fa388b310f12bcd2015339158be8169f748f3fd281893eb5bec3606ab77`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 4/15 (26.7%) | 5/15 (33.3%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 12 |
| API attempts / retries | 12 / 0 | 12 / 0 |
| Duration | 98.152 s | 109.860 s |

Both modes failed because the agent returned only a structured-snapshot timeout and did not report a film title, synopsis, or showtimes. DOM received one additional navigation point even though both modalities captured the same relevant page state.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 66,195 | 7,809 | 2,304 | 74,004 |
| DOM model | 65,451 | 8,675 | 2,944 | 74,126 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 122 more scoring tokens, a 0.2% increase. Rubric generation was separate: 12,890 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Reach currently-playing information | “Now Showing” + “Sturm Theater” visible / Yes | Same page text explicit / Yes | 1/3 / 2/3 | BOTH_CAUGHT |
| Identify one current film title | Absent / correctly rejected | Absent / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Report film synopsis | Absent / correctly rejected | Absent / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Report showtimes | Absent / correctly rejected | Absent / correctly rejected | 0/4 / 0/4 | BOTH_CAUGHT |
| Respect constraints | Present / Yes | Present / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot1.png` visibly shows the DMNS “Films & Shows” page, a “Now Showing” heading, and a “Sturm Theater” section. `dom_model1.txt` preserves the same URL and text. Neither source contains a visible film title, film-specific synopsis, or showtime schedule. Both verifiers correctly identified those absences. Because the navigation evidence was materially the same, the screenshot 1/3 versus DOM 2/3 allocation is judge/scoring variance rather than DOM recovering evidence missed by the screenshot verifier.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **0/5 criteria**
- DOM-side asymmetric evidence loss: **0/5 criteria**
- Confirmed verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both modalities captured the same incomplete state and both verifiers correctly recognized what was and was not available. The one-point DOM advantage reflects scoring variance, not extra DOM evidence. Token usage was effectively equal, with DOM using 0.2% more.

### Artifacts

- [Frozen rubric](rubrics/browser_task_004-museum-film-lookup-20260909T071414Z.json)
- [Comparison report](results/browser_task_004-museum-film-lookup-20260909T071414Z/20260909T_task004_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_004-museum-film-lookup-20260909T071414Z/20260909T_task004_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_004-museum-film-lookup-20260909T071414Z/20260909T_task004_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_004-museum-film-lookup-20260909T071414Z/20260909T_task004_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 5 — George H. W. Bush Foundation event lookup

Task ID: `browser_task_005-event-lookup-20260909T094331Z`

Run: `20260909T_task005_data_new`

Frozen rubric: 4 criteria, 15 maximum points

Rubric SHA-256: `1d9fb62eb123094877e0d4f2d9defa7dfd985148ce7c88e3efa589b359e1671c`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/15 (80.0%) | 12/15 (80.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 2 / 3 screenshots | 2 / 3 DOM states |
| Scoring LLM calls | 14 | 17 |
| API attempts / retries | 14 / 0 | 17 / 0 |
| Duration | 80.029 s | 119.447 s |

The totals match, but the criterion allocation differs. DOM received one more point for establishing the earliest visible event, while screenshot received one more point for the incomplete event-details answer. Both outcome checks failed because the trajectory did not prove the event was the overall next event and inferred a location that the page did not label.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 73,136 | 7,084 | 1,664 | 80,220 |
| DOM model | 74,310 | 9,769 | 1,664 | 84,079 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 3,859 more scoring tokens, a 4.8% increase. Rubric generation was separate: 12,608 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Reach official events listing | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Determine the next upcoming event | Only 9:00 AM event visible / correctly limited | 9:00 AM and 11:00 AM events explicit / Yes | 2/4 / 3/4 | SCREENSHOT_EVIDENCE_MISSING |
| Report title, date, time, and location | Title/date/time present; location absent / Yes | Same fields present; location absent / Yes | 4/5 / 3/5 | BOTH_CAUGHT |
| Respect constraints | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot2.png` shows the September 11, 2026 event at 9:00 AM–11:00 AM but no second event in the viewport. `dom_model2.txt` contains that event plus another event on the same date at 11:00 AM–4:00 PM, providing evidence that 9:00 AM is earliest among the captured listings. Neither modality proves that the captured list is globally complete, so DOM still received only partial credit. Both sources contain the same title/date/time and omit a separately labeled location; the screenshot 4/5 versus DOM 3/5 difference on event details is judge/scoring variance, not evidence availability or a verifier miss.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **1/4 criteria**
- DOM-side asymmetric evidence loss: **0/4 criteria**
- Confirmed verifier perception misses: **0/4 criteria**
- DOM recovery of screenshot source gaps: **1/1 eligible criterion**
- Verifier-miss recovery rate: **N/A (neither verifier overlooked available evidence)**

**Summary:** DOM preserved a second event outside the screenshot viewport and therefore supported a stronger chronological comparison. Both verifiers correctly handled the evidence available to them; the equal 12/15 totals hide one genuine screenshot source gap and one offsetting point of scoring variance. DOM used 4.8% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_005-event-lookup-20260909T094331Z.json)
- [Comparison report](results/browser_task_005-event-lookup-20260909T094331Z/20260909T_task005_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_005-event-lookup-20260909T094331Z/20260909T_task005_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_005-event-lookup-20260909T094331Z/20260909T_task005_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_005-event-lookup-20260909T094331Z/20260909T_task005_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 6 — Search Engine Land earliest-article lookup

Task ID: `browser_task_006-article-metadata-lookup-20260909T071913Z`

Run: `20260909T_task006_data_new`

Frozen rubric: 4 criteria, 12 maximum points

Rubric SHA-256: `fd4b6e5db6e3942d425c795d4667da54104038119a8cacb7e2817b6505e2c2a1`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6/12 (50.0%) | 6/12 (50.0%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 8 / 9 screenshots | 8 / 9 DOM states |
| Scoring LLM calls | 25 | 35 |
| API attempts / retries | 25 / 0 | 35 / 0 |
| Duration | 85.939 s | 125.444 s |

Both verifiers produced identical criterion scores. The agent paginated from the latest-posts archive through page 8, then returned only an agent-browser timeout without identifying an earliest article or reporting its title, date, and author.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 129,931 | 11,227 | 1,536 | 141,158 |
| DOM model | 174,515 | 18,782 | 2,304 | 193,297 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 52,139 more scoring tokens, a 36.9% increase. Rubric generation was separate: 12,133 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Attempt on-site earliest-article search | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Identify earliest article and metadata | Required result absent / correctly rejected | Required result absent / correctly rejected | 0/5 / 0/5 | BOTH_CAUGHT |
| Stop after result or clear blocker | Condition unmet / correctly rejected | Condition unmet / correctly rejected | 0/1 / 0/1 | BOTH_CAUGHT |
| Respect constraints | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot8.png` shows a normally loaded Search Engine Land archive page titled “More from Search Engine Land: Page 8,” with articles dated July 24, 2026. `dom_model8.txt` preserves the same page and additionally identifies it as “Page 8 of 721.” Neither source shows the archive endpoint or the earliest article, and the final answer contains only a browser-timeout message with no article metadata. Both verifiers correctly determined that the task was incomplete. The DOM-only total-page count reinforces that page 8 is far from the archive end but does not supply the missing requested article, so it is not counted as asymmetric loss of required evidence.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **0/4 criteria**
- DOM-side asymmetric evidence loss: **0/4 criteria**
- Confirmed verifier perception misses: **0/4 criteria**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both modalities and verifiers reached the same conclusion: the agent made a valid on-site attempt but never found or reported the earliest article. There was no verifier perception miss or asymmetric loss of the required evidence. DOM used 36.9% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_006-article-metadata-lookup-20260909T071913Z.json)
- [Comparison report](results/browser_task_006-article-metadata-lookup-20260909T071913Z/20260909T_task006_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_006-article-metadata-lookup-20260909T071913Z/20260909T_task006_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_006-article-metadata-lookup-20260909T071913Z/20260909T_task006_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_006-article-metadata-lookup-20260909T071913Z/20260909T_task006_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 7 — Amazon-to-AllRecipes recipe lookup

Task ID: browser_task_007-cross-site-recipe-lookup-20260909T072810Z

Run: 20260909T_task007_data_new

Frozen rubric: 6 criteria, 12 maximum points

Rubric SHA-256: 92aa9a35c900cfea9df77683c49e2d406af0a68c5cafd9169458a5c81323c15b

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/12 (100%) | 12/12 (100%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 25 |
| API attempts / retries | 12 / 0 | 25 / 0 |
| Duration | 99.680 s | 148.904 s |

Both verifiers gave full credit. Amazon evidence confirms Tata Salt as the #2 Grocery & Gourmet Foods bestseller, and the AllRecipes request reaches a genuine Cloudflare verification interstitial. The task explicitly requires stopping and reporting such a bot check rather than bypassing it.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 71,091 | 7,567 | 1,984 | 78,658 |
| DOM model | 106,954 | 15,287 | 2,496 | 122,241 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 43,583 more scoring tokens, a 55.4% increase. Rubric generation was separate: 12,645 tokens across 2 calls; scoring reported rubric_generation_calls: 0 for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access Amazon India bestsellers | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Verify product ranked #2 | Tata Salt explicit / Yes | #2 Tata Salt explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Attempt AllRecipes recipe search | Cloudflare block visible / Yes | Interstitial explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report recipe title or valid blocker | Block correctly reported / Yes | Block correctly reported / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Report ingredients or valid blocker | Block correctly reported / Yes | Block correctly reported / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that screenshot0.png visibly shows the Amazon India Grocery & Gourmet Foods bestseller grid with “#2” above Tata Salt, while dom_model0.txt explicitly records the same rank and product. screenshot1.png shows Cloudflare “Verifyingâ¦”, and dom_model1.txt contains the corresponding verification/interstitial text with no recipe content. The final answer's claim that a specific “Verify you are human” checkbox appeared is not shown in either captured source, but both verifiers correctly treated this as a minor description mismatch rather than evidence against the genuine blocker.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **0/6 criteria**
- DOM-side asymmetric evidence loss: **0/6 criteria**
- Confirmed verifier perception misses: **0/6 criteria**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both evidence representations contained and recovered the same decisive facts: Tata Salt was ranked #2 and AllRecipes was blocked by a verification interstitial. Both verifiers scored the constrained task as successfully completed. DOM used 55.4% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_007-cross-site-recipe-lookup-20260909T072810Z.json)
- [Comparison report](results/browser_task_007-cross-site-recipe-lookup-20260909T072810Z/20260909T_task007_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_007-cross-site-recipe-lookup-20260909T072810Z/20260909T_task007_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_007-cross-site-recipe-lookup-20260909T072810Z/20260909T_task007_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_007-cross-site-recipe-lookup-20260909T072810Z/20260909T_task007_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 8 — Playwright software-release research

Task ID: `browser_task_008-software-release-research-20260909T072902Z`

Run: `20260909T_task008_data_new`

Frozen rubric: 6 criteria, 17 maximum points

Rubric SHA-256: `dbd97e8cc89d447ae6e4e451a73e26b3eacff43e05f39ea4d84a8ce8e496ffa0`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/17 (76.5%) | 14.5/17 (85.3%) |
| Rubric threshold | Fail | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 9 / 10 screenshots | 9 / 10 DOM states |
| Scoring LLM calls | 23 | 36 |
| API attempts / retries | 23 / 0 | 36 / 0 |
| Duration | 103.844 s | 145.545 s |

Both outcome checks failed because the agent reported an incorrect publication date. DOM scored 1.5 points higher: screenshot scoring was 0.5 points higher for stable-release identification, while DOM was 2 points higher for the three release-note changes.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 122,055 | 11,193 | 1,664 | 133,248 |
| DOM model | 183,566 | 18,865 | 2,304 | 202,431 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 69,183 more scoring tokens, a 51.9% increase. Rubric generation was separate: 12,743 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access official Releases page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Identify newest stable release | `v1.63.0` + `Latest` visible / Yes | `v1.63.0` + `Latest` explicit / Yes | 2/2 / 1.5/2 | BOTH_CAUGHT |
| Report tag and publication date | Tag + relative age only / correctly rejected wrong date | Tag + Sep. 4, 2026 explicit / correctly contradicted wrong date | 1/3 / 1/3 | SCREENSHOT_EVIDENCE_MISSING |
| Extract three release-note changes | All three visible / No, third change overlooked | All three explicit / Yes | 2/4 / 4/4 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Verify one change in official docs | Test-lock docs visible / Yes | Test-lock docs explicit / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed two distinct effects. First, the screenshots show only GitHub's relative “released this 4 days ago” text; the exact September 4, 2026 date is outside the captured viewport, while `dom_model0.txt` and `dom_model6.txt` preserve it. Both verifiers still correctly rejected the agent's incorrect 2025-01-07 date. Second, `screenshot3.png` visibly contains “Visible-only locators,” but the screenshot verifier said only two GitHub release-note changes were supported—even though that frame was selected. `dom_model3.txt` explicitly contains the same third change, and the DOM verifier recovered all three. The 2/2 versus 1.5/2 stable-release difference is scoring strictness/LLM variance: both verifiers found `v1.63.0` and its `Latest` marker.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **1/6 criteria**
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed verifier perception misses: **Screenshot 1/6; DOM 0/6**
- DOM recovery of screenshot verifier misses: **1/1 eligible criterion (100%)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** DOM recovered one third release-note change that was visibly present but overlooked by the screenshot verifier, and it preserved an exact date that was outside the screenshot viewport. The agent's date was nevertheless wrong, so both final outcomes failed. DOM used 51.9% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_008-software-release-research-20260909T072902Z.json)
- [Comparison report](results/browser_task_008-software-release-research-20260909T072902Z/20260909T_task008_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_008-software-release-research-20260909T072902Z/20260909T_task008_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_008-software-release-research-20260909T072902Z/20260909T_task008_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_008-software-release-research-20260909T072902Z/20260909T_task008_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 9 — NASA Artemis mission lookup

Task ID: `browser_task_009-nasa-mission-lookup-20260909T073151Z`

Run: `20260909T_task009_data_new`

Frozen rubric: 7 criteria, 20 maximum points

Rubric SHA-256: `d8501aa855b5b07aec67fd374fcfe17455c57c18ab59a631d96ed88fe1d6fe4d`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/20 (80.0%) | 19/20 (95.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Pass |
| Overall verifier score | 0 | 1 |
| Actions / states | 5 / 6 screenshots | 5 / 6 DOM states |
| Scoring LLM calls | 20 | 33 |
| API attempts / retries | 20 / 0 | 33 / 0 |
| Duration | 95.384 s | 139.027 s |

Both modalities contained the same decisive mission-status evidence. The screenshot verifier correctly treated Artemis II's completed status as a core failure; the DOM verifier acknowledged that status but still awarded 3/4 and passed the outcome.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 121,878 | 13,041 | 2,688 | 134,919 |
| DOM model | 144,408 | 19,182 | 1,664 | 163,590 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 28,671 more scoring tokens, a 21.3% increase. Rubric generation was separate: 13,423 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use NASA as source | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Identify next planned mission | “Occurred 5 months ago” visible / correctly used | Same status explicit / found but used incorrectly | 0/4 / 3/4 | BOTH_CAUGHT |
| Report mission name | Artemis II visible / Yes | Artemis II explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report launch year | April 1, 2026 visible / Yes | April 1, 2026 explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report destination | Crewed Lunar Flyby visible / Yes | Crewed Lunar Flyby explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report primary objective | Objective text visible / Yes | Objective text explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot5.png` and `dom_model5.txt` both state that Artemis II “occurred 5 months ago” and launched April 1, 2026. Therefore, Artemis II cannot satisfy the task's “next planned” requirement. The DOM verifier did not miss this evidence: its own analysis cited both “Occurred 5 months ago” and past-tense “LaunchED,” but it treated the completed mission as a defensible next mission and passed the outcome. This is a DOM verifier reasoning/scoring error, not DOM evidence loss. The screenshot verifier correctly applied the same evidence and failed the outcome.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/7 criteria**
- DOM-side asymmetric source-evidence loss: **0/7 criteria**
- Confirmed verifier perception misses: **0/7 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**
- Confirmed evidence-use/scoring errors: **DOM 1/7; Screenshot 0/7**

**Summary:** Both modalities preserved and both verifiers found the decisive evidence that Artemis II had already occurred. The 3-point and outcome disagreement came from DOM-side overcrediting after the evidence was found, not from a difference in evidence availability. DOM used 21.3% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_009-nasa-mission-lookup-20260909T073151Z.json)
- [Comparison report](results/browser_task_009-nasa-mission-lookup-20260909T073151Z/20260909T_task009_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_009-nasa-mission-lookup-20260909T073151Z/20260909T_task009_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_009-nasa-mission-lookup-20260909T073151Z/20260909T_task009_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_009-nasa-mission-lookup-20260909T073151Z/20260909T_task009_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 10 — Gemini official-documentation lookup

Task ID: `browser_task_010-official-documentation-lookup-20260909T073335Z`

Run: `20260909T_task010_data_new`

Frozen rubric: 7 criteria, 18 maximum points

Rubric SHA-256: `a8d84181ec0fe09d117995b4c001e182821ba5ac9631538a68d8a8bf32054f90`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6/18 (33.3%) | 4.5/18 (25.0%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 3 / 4 screenshots | 3 / 4 DOM states |
| Scoring LLM calls | 16 | 35 |
| API attempts / retries | 16 / 0 | 35 / 0 |
| Duration | 90.867 s | 161.148 s |

Both verifiers correctly concluded that the agent was blocked by Google's unusual-traffic CAPTCHA before reaching Gemini documentation. The 1.5-point difference came from how generously the judges credited the search attempt, partial constraint compliance, and stopping behavior.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 97,792 | 10,476 | 1,728 | 108,268 |
| DOM model | 160,833 | 27,256 | 2,432 | 188,089 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 79,821 more scoring tokens, a 73.7% increase. Rubric generation was separate: 13,255 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Attempt Google Search | Query + CAPTCHA present / Yes | Query + CAPTCHA explicit / Yes | 3/3 / 2/3 | BOTH_CAUGHT |
| Official domain and no sign-in | No docs; no sign-in / Yes | No docs; no sign-in / Yes | 1/3 / 1.5/3 | BOTH_CAUGHT |
| Documentation title | Absent / correctly rejected | Absent / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Documentation domain | Absent / correctly rejected | Absent / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Python SDK | Absent / correctly rejected | Absent / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Example model | Absent / correctly rejected | Absent / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Stop at blocker | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot3.png` visibly shows the reCAPTCHA checkbox and “Our systems have detected unusual traffic,” while `dom_model3.txt` explicitly preserves the same blocker text and the intended search URL. No screenshot or DOM state contains an opened Gemini API documentation page, page title, documentation domain, Python SDK, or model identifier. Both verifiers correctly identified those facts as absent. The score differences on the search-attempt, official-domain, and stopping criteria are judge/scoring variance over the same evidence, not evidence loss or verifier perception failure.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/7 criteria**
- DOM-side asymmetric source-evidence loss: **0/7 criteria**
- Confirmed verifier perception misses: **0/7 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both representations captured the same Google CAPTCHA blocker and omitted the same unavailable documentation details. Both verifiers reached the correct failed outcome; the 1.5-point process-score difference reflects scoring variance only. DOM used 73.7% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_010-official-documentation-lookup-20260909T073335Z.json)
- [Comparison report](results/browser_task_010-official-documentation-lookup-20260909T073335Z/20260909T_task010_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_010-official-documentation-lookup-20260909T073335Z/20260909T_task010_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_010-official-documentation-lookup-20260909T073335Z/20260909T_task010_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_010-official-documentation-lookup-20260909T073335Z/20260909T_task010_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 11 — arXiv literature search

Task ID: `browser_task_011-arxiv-literature-search-20260909T073439Z`

Run: `20260909T_task011_data_new`

Frozen rubric: 6 criteria, 20 maximum points

Rubric SHA-256: `8154a1385faa60d8797d38cd3790be785d2a99dc77c1de0f22ef29f1e639920b`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 5/20 (25.0%) | 6/20 (30.0%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 9 / 10 screenshots | 9 / 10 DOM states |
| Scoring LLM calls | 24 | 29 |
| API attempts / retries | 24 / 0 | 29 / 0 |
| Duration | 128.630 s | 169.511 s |

Both verifiers found that the search used the title phrase, date range, and newest-first ordering but applied broad Computer Science filtering rather than `cs.LG` only. They also found that the agent reported the visible second result as Paper #1 and supplied unsupported Papers #2 and #3. Both therefore failed the task.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 162,507 | 16,522 | 1,856 | 179,029 |
| DOM model | 208,544 | 21,137 | 2,176 | 229,681 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 50,652 more scoring tokens, a 28.3% increase. Rubric generation was separate: 13,538 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Required search filters | Query summary visible / Yes | Query summary explicit / Yes | 3/4 / 3/4 | BOTH_CAUGHT |
| Most recent paper | Top result `2609.08682`; agent used #2 / Yes | Same ordering explicit / Yes | 0/3 / 0.5/3 | BOTH_CAUGHT |
| Second paper | Actual #2 visible; claimed paper absent / Yes | Same; claimed paper absent / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Third paper | Claimed paper absent / Yes | Claimed paper absent / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Per-paper verification | One reported paper partly verifiable / Yes | Same facts explicit / Yes | 0/5 / 1.5/5 | BOTH_CAUGHT |
| Stop and constraints | No prohibited action; three items reported / Yes | Same action history / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot9.png` and `dom_model9.txt` both expose the decisive result ordering: `2609.08682` (`cs.AR`) is first and `2609.08663` (`cs.LG`, `cs.AI`) is second. Both also expose the broad Computer Science query, exact title term, date range, and newest-first sorting. Neither representation supports the agent's claimed Papers #2 and #3. The screenshot verifier explicitly recovered the same result IDs, titles, authors, categories, and ordering as the DOM verifier.

The 1-point process-score difference is not an evidence miss. The DOM judge awarded minimal metadata credit to the real but incorrectly ordered `2609.08663`, plus partial verification credit, while the screenshot judge treated those criterion failures more strictly. The stop/constraints criterion also differed by one point because the screenshot judge credited stopping after three items in form, while the DOM judge penalized stopping without three substantiated matches.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/6 criteria**
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed verifier perception misses: **0/6 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both modalities contained and both verifiers recovered the same decisive search and result evidence. The DOM verifier scored 1 point higher through more generous partial-credit judgments, not because it recovered evidence missed by the screenshot verifier. DOM used 28.3% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_011-arxiv-literature-search-20260909T073439Z.json)
- [Comparison report](results/browser_task_011-arxiv-literature-search-20260909T073439Z/20260909T_task011_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_011-arxiv-literature-search-20260909T073439Z/20260909T_task011_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_011-arxiv-literature-search-20260909T073439Z/20260909T_task011_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_011-arxiv-literature-search-20260909T073439Z/20260909T_task011_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 12 — arXiv paper metadata

Task ID: `browser_task_012-arxiv-paper-metadata-20260909T073715Z`

Run: `20260909T_task012_data_new`

Frozen rubric: 6 criteria, 13 maximum points

Rubric SHA-256: `0ba8db17cb7a714de473b135020ece47b0a8098f986ce2fc4f86e50d3dde449f`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12.5/13 (96.2%) | 12.5/13 (96.2%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 17 |
| API attempts / retries | 12 / 0 | 17 / 0 |
| Duration | 81.525 s | 116.384 s |

Both verifiers confirmed that the agent reached arXiv entry `1706.03762`, complied with the constraints, correctly reported seven versions, and reproduced the exact v1 and v7 submission-history strings. Both deducted 0.5 point because the final answer included redundant header-summary dates beyond the three requested items.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 71,458 | 7,760 | 1,664 | 79,218 |
| DOM model | 81,023 | 13,143 | 2,880 | 94,166 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 14,948 more scoring tokens, an 18.9% increase. Rubric generation was separate: 13,030 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct arXiv entry | ID and history visible / Yes | ID and history explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| No sign-in/download/edit | Actions show scroll only / Yes | Actions show scroll only / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Total versions | `v1`–`v7` visible / Yes | `v1`–`v7` explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Exact v1 date | Visible / Yes | Explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Exact latest date | `v7` visible / Yes | `v7` explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop after requested items | Extra text in answer / Yes | Extra text in answer / Yes | 0.5/1 / 0.5/1 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot1.png` visibly shows the complete submission history from `v1` through `v7`, including `Mon, 12 Jun 2017 17:57:34 UTC (1,102 KB)` and `Wed, 2 Aug 2023 00:41:18 UTC (1,124 KB)`. `dom_model1.txt` preserves the same version sequence and exact strings. Both verifier analyses cited these values correctly.

The audit script flagged minor wording differences about constraint evidence, but manual review found no substantive disagreement: both relied on the one scroll action and correctly found no sign-in, PDF opening/download, or edit action.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/6 criteria**
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed verifier perception misses: **0/6 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Screenshot and DOM contained the same required metadata, both verifiers recovered it correctly, and both produced the identical passing score. There was no evidence loss or verifier perception miss. DOM used 18.9% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_012-arxiv-paper-metadata-20260909T073715Z.json)
- [Comparison report](results/browser_task_012-arxiv-paper-metadata-20260909T073715Z/20260909T_task012_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_012-arxiv-paper-metadata-20260909T073715Z/20260909T_task012_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_012-arxiv-paper-metadata-20260909T073715Z/20260909T_task012_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_012-arxiv-paper-metadata-20260909T073715Z/20260909T_task012_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 13 — Chess.com profile lookup

Task ID: `browser_task_013-chess-profile-lookup-20260909T073812Z`

Run: `20260909T_task013_data_new`

Frozen rubric: 4 criteria, 13 maximum points

Rubric SHA-256: `1db9087c848d5ad336f7c063babff47c82c0d673cec6184a853a62ab5e162c17`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 11/13 (84.6%) | 13/13 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 2 / 3 screenshots | 2 / 3 DOM states |
| Scoring LLM calls | 15 | 32 |
| API attempts / retries | 15 / 0 | 32 / 0 |
| Duration | 93.296 s | 120.403 s |

Both verifiers confirmed that the agent reached Magnus Carlsen’s logged-out Chess.com profile, reported Blitz `3316` and Bullet `3184`, avoided prohibited interactions, and stopped. The score difference concerns whether the adjacent rating-change indicators were part of “exactly as displayed.”

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 76,260 | 8,575 | 2,880 | 84,835 |
| DOM model | 134,935 | 13,952 | 1,216 | 148,887 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 64,052 more scoring tokens, a 75.5% increase. Rubric generation was separate: 12,691 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. The DOM pipeline recorded 2 fallback invocations but no API retries.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct logged-out profile | Present / Yes | Present / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Blitz exactly displayed | `3316 ↓63` / Yes | `3316 63`; arrow semantics absent / Partial | 3/4 / 4/4 | DOM_EVIDENCE_MISSING |
| Bullet exactly displayed | `3184 ↓73` / Yes | `3184 73`; arrow semantics absent / Partial | 3/4 / 4/4 | DOM_EVIDENCE_MISSING |
| Constraints and stopping | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot2.png` visibly displays Blitz `3316` with a red `↓ 63` indicator and Bullet `3184` with a red `↓ 73` indicator. The screenshot verifier recovered these symbols and deducted one point from each exact-display criterion because the agent reported only the rating numbers.

`dom_model2.txt` preserves the core ratings and adjacent magnitudes as flattened text—`Blitz 3316 63` and `Bullet 3184 73`—but does not preserve the downward arrows, color, or the semantic relationship identifying those numbers as rating decreases. The DOM verifier therefore treated `3316` and `3184` as exact rating values and awarded full credit. This is partial DOM representation loss for the exact-formatting evidence, not a failure to recover the core rating values.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/4 criteria**
- DOM-side asymmetric source-evidence loss: **2/4 criteria**, limited to rating-change symbol semantics
- Confirmed screenshot-verifier perception misses: **0/4 criteria**
- Confirmed DOM-verifier perception misses: **0/4 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both modalities and verifiers recovered the correct Blitz and Bullet rating numbers. Screenshot evidence additionally preserved the downward-change indicators, while DOM flattened away their arrow semantics; this produced two extra DOM points under the rubric’s exact-display requirement. DOM used 75.5% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_013-chess-profile-lookup-20260909T073812Z.json)
- [Comparison report](results/browser_task_013-chess-profile-lookup-20260909T073812Z/20260909T_task013_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_013-chess-profile-lookup-20260909T073812Z/20260909T_task013_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_013-chess-profile-lookup-20260909T073812Z/20260909T_task013_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_013-chess-profile-lookup-20260909T073812Z/20260909T_task013_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 14 — Reddit post lookup

Task ID: `browser_task_014-reddit-post-lookup-20260909T073959Z`

Run: `20260909T_task014_data_new`

Frozen rubric: 5 criteria, 17 maximum points

Rubric SHA-256: `c8d413abd02711e0a624ff57822d29e0edd9802c5c75a62c9d86a86d76b9962a`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/17 (100.0%) | 17/17 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 0 / 1 screenshot | 0 / 1 DOM state |
| Scoring LLM calls | 10 | 11 |
| API attempts / retries | 10 / 0 | 11 / 0 |
| Duration | 81.392 s | 98.477 s |

Both verifiers confirmed that Reddit blocked the environment before the agent could access r/MachineLearning, apply the requested filters, open a post, or recover its metadata. The rubric awarded full process credit under its uncontrollable-blocker rules, while the outcome check correctly remained failed because the requested post details were not obtained.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 56,646 | 6,067 | 1,536 | 62,713 |
| DOM model | 55,639 | 8,671 | 3,264 | 64,310 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 1,597 more scoring tokens, a 2.5% increase. Rubric generation was separate: 12,783 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Apply Top + past month | Blocker present / Yes | Blocker explicit / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Open highest-ranked post | No listing due to blocker / Yes | No listing due to blocker / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report post metadata | Metadata absent due to blocker / Yes | Metadata absent due to blocker / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| No sign-in/interactions | Logged-out blocker; no actions / Yes | Same / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop at blocker | Stopped with explanation / Yes | Same / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` clearly displays “You've been blocked by network security,” with only “Log in” and “File a ticket” options. `dom_model0.txt` preserves the same blocker message, Reddit URL, and options. Neither representation contains a subreddit post list, filtering controls, or post title/author/score/comment data.

The DOM file’s missing page-title warning did not remove any criterion-relevant evidence: the URL and complete blocker text were retained, and the DOM verifier cited them correctly.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/5 criteria**
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Screenshot and DOM captured the same Reddit network-security blocker, and both verifiers interpreted it consistently. Process scores were perfect under blocker-aware rubric rules, but both outcome checks failed because the requested post metadata was unavailable. There was no evidence loss or perception miss; DOM used 2.5% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_014-reddit-post-lookup-20260909T073959Z.json)
- [Comparison report](results/browser_task_014-reddit-post-lookup-20260909T073959Z/20260909T_task014_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_014-reddit-post-lookup-20260909T073959Z/20260909T_task014_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_014-reddit-post-lookup-20260909T073959Z/20260909T_task014_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_014-reddit-post-lookup-20260909T073959Z/20260909T_task014_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 15 — Reddit community comparison

Task ID: `browser_task_015-reddit-community-comparison-20260909T074040Z`

Run: `20260909T_task015_data_new`

Frozen rubric: 5 criteria, 15 maximum points

Rubric SHA-256: `002aa1d1eda9e7069a08c8bbb68a6d7c9e6e1ecf1dd4fd815d396f69641e6158`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/15 (100.0%) | 15/15 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 0 / 1 screenshot | 0 / 1 DOM state |
| Scoring LLM calls | 10 | 19 |
| API attempts / retries | 10 / 0 | 19 / 0 |
| Duration | 75.883 s | 132.279 s |

Both verifiers confirmed that Reddit’s network-security block prevented the agent from accessing r/Python, r/learnpython, and r/django, obtaining subscriber counts, or producing the requested ranking table. Blocker-aware rubric rules awarded full process credit, while both outcome checks failed because the requested comparison was not completed.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 56,220 | 6,521 | 2,240 | 62,741 |
| DOM model | 71,082 | 11,986 | 2,304 | 83,068 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 20,327 more scoring tokens, a 32.4% increase. Rubric generation was separate: 12,794 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. The DOM pipeline recorded 1 fallback invocation but no API retry.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| r/Python subscriber count | Blocker; count absent / Yes | Blocker; count absent / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| r/learnpython subscriber count | Shared blocker; count absent / Yes | Shared blocker; count absent / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| r/django subscriber count | Shared blocker; count absent / Yes | Shared blocker; count absent / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Ranking table | Inputs unavailable / Yes | Inputs unavailable / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Constraints and stop | No prohibited action; stopped / Yes | Same / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` clearly shows Reddit’s “You've been blocked by network security” page and only the “Log in” and “File a ticket” options. `dom_model0.txt` preserves the same blocker text and the r/Python URL. Neither source contains subscriber counts for any of the three communities or a ranking table.

The DOM file’s missing page-title warning does not affect criterion evidence because the platform URL and blocker text remain explicit. The audit script’s minor wording flags do not reflect a substantive disagreement; both verifiers reached the same evidence conclusions.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/5 criteria**
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both modalities captured and both verifiers recognized the same Reddit-wide access blocker. There was no evidence loss or perception miss. Both received full blocker-aware process credit but failed the outcome because no subscriber counts or ranking were obtained. DOM used 32.4% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_015-reddit-community-comparison-20260909T074040Z.json)
- [Comparison report](results/browser_task_015-reddit-community-comparison-20260909T074040Z/20260909T_task015_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_015-reddit-community-comparison-20260909T074040Z/20260909T_task015_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_015-reddit-community-comparison-20260909T074040Z/20260909T_task015_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_015-reddit-community-comparison-20260909T074040Z/20260909T_task015_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 16 — Hugging Face model metadata

Task ID: `browser_task_016-hugging-face-model-metadata-20260909T074128Z`

Run: `20260909T_task016_data_new`

Frozen rubric: 5 criteria, 13 maximum points

Rubric SHA-256: `3ae38854ed411b9031803fe22503d5d4c10c2cf432936e9016379e99e0ae71fd`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/13 (100.0%) | 13/13 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 15 |
| API attempts / retries | 12 / 0 | 15 / 0 |
| Duration | 61.647 s | 75.660 s |

Both verifiers confirmed that the agent was on the requested Hugging Face repository and correctly reported its visible license (`llama3.1`), likes count (`6.85k`), and gated status while remaining logged out and stopping without requesting access or downloading files.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 64,902 | 5,972 | 1,600 | 70,874 |
| DOM model | 88,114 | 7,437 | 1,472 | 95,551 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 24,677 more scoring tokens, a 34.8% increase. Rubric generation was separate: 12,599 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither scoring pipeline recorded an API retry or fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Hugging Face repository | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| License name | `License: llama3.1` / Yes | `License: llama3.1` / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Current likes count | `6.85k` / Yes | `like 6.85k` / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Repository gated status | Access-agreement banner / Yes | Same banner text / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Constraints and stopping | Logged out; no prohibited action / Yes | Same plus wait-only history / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` and `screenshot1.png` visibly contain the exact repository slug, license badge, `6.85k` like count, and the banner stating that contact-information sharing must be agreed to before accessing the model. The logged-out controls are visible, and there is no indication of an access request or download.

`dom_model0.txt` and `dom_model1.txt` preserve the same evidence explicitly, including the URL/title, `License: llama3.1`, `like 6.85k`, the gating notice, and `Log In` / `Sign Up`. Neither DOM state was truncated and the run recorded no context omissions or evidence warnings.

The offline audit flagged two intermediate `environment_issues_confirmed` wording mismatches. These are not substantive evidence disagreements: both verifiers cited the same facts, awarded identical points, and reached the same final outcome.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/5 criteria**
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed screenshot-verifier perception misses: **0/5 criteria**
- Confirmed DOM-verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Screenshot and DOM contained the same required Hugging Face metadata, both verifiers recovered it correctly, and both produced the identical passing score. There was no evidence loss or verifier perception miss. DOM used 34.8% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_016-hugging-face-model-metadata-20260909T074128Z.json)
- [Comparison report](results/browser_task_016-hugging-face-model-metadata-20260909T074128Z/20260909T_task016_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_016-hugging-face-model-metadata-20260909T074128Z/20260909T_task016_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_016-hugging-face-model-metadata-20260909T074128Z/20260909T_task016_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_016-hugging-face-model-metadata-20260909T074128Z/20260909T_task016_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 17 — Hugging Face dataset inspection

Task ID: `browser_task_017-hugging-face-dataset-inspection-20260909T074239Z`

Run: `20260909T_task017_data_new`

Frozen rubric: 4 criteria, 12 maximum points

Rubric SHA-256: `432739090bfbc188d44079a449ae58637894eaf19a08f1d997ece6a4385e886c`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 3/12 (25.0%) | 7/12 (58.3%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 0 / 1 screenshot | 0 / 1 DOM state |
| Scoring LLM calls | 10 | 13 |
| API attempts / retries | 10 / 0 | 13 / 0 |
| Duration | 73.538 s | 94.652 s |

Both verifiers found the correct `rajpurkar/squad` page, the rendered Dataset Viewer, and the visible train split count. The agent’s final answer reported only a generic action-generation failure and did not provide either requested split count, so both outcome checks failed. The DOM process score is higher because it incorrectly awarded the train-count criterion based on evidence availability alone.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 52,499 | 6,249 | 2,176 | 58,748 |
| DOM model | 78,381 | 7,940 | 2,368 | 86,321 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 27,573 more scoring tokens, a 46.9% increase. Rubric generation was separate: 12,522 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry, and the DOM pipeline recorded no fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct SQuAD page and viewer | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Train split count | `train Â· 87.6k rows` / Yes | `train`, `87.6k rows` / Yes | 0/4 / 4/4 | BOTH_CAUGHT |
| Validation split count | Absent / correctly identified | Absent / correctly identified | 0/4 / 0/4 | BOTH_CAUGHT |
| Constraints and stopping | Logged out; task incomplete / Yes | Same / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` visibly shows the correct dataset page, a rendered Dataset Viewer, and the selected split as `train Â· 87.6k rows`. The validation split count is not visible because the split selector is not expanded. `dom_model0.txt` preserves the same page identity and train count on lines 74–76, but it likewise contains no validation split value.

Both verifiers correctly extracted the train evidence. The screenshot scorer then correctly gave 0/4 because the rubric requires the agent to record/report the value, and the final answer did not do so. The DOM scorer instead gave 4/4 merely because the value was present in the DOM, explicitly acknowledging that the agent did not report it. This is an overcrediting judgment by the DOM verifier, not a difference in evidence capture or recovery.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/4 criteria**
- DOM-side asymmetric source-evidence loss: **0/4 criteria**
- Confirmed screenshot-verifier perception misses: **0/4 criteria**
- Confirmed DOM-verifier perception misses: **0/4 criteria**
- DOM scoring/judgment errors: **1/4 criteria** (train count overcredited)
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both representations exposed the same relevant evidence and both verifiers recovered it. The 4-point score gap is not evidence loss: the DOM scorer overcredited a train count that the agent never reported. Both final outcomes correctly failed, and DOM used 46.9% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z.json)
- [Comparison report](results/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z/20260909T_task017_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z/20260909T_task017_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z/20260909T_task017_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z/20260909T_task017_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 18 — GitHub issue search

Task ID: `browser_task_018-github-issue-search-20260909T074333Z`

Run: `20260909T_task018_data_new`

Frozen rubric: 5 criteria, 11 maximum points

Rubric SHA-256: `1070898bbbc7964a59520ec21c339408ad17d6faca93bcb2306f1ef43249e9a0`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 10.5/11 (95.5%) | 11/11 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 3 / 4 screenshots | 3 / 4 DOM states |
| Scoring LLM calls | 16 | 18 |
| API attempts / retries | 16 / 0 | 18 / 0 |
| Duration | 96.514 s | 94.019 s |

Both verifiers confirmed the correct repository issue search, exact filter query, count of 17 matching open issues, three newest issue numbers and titles, and compliance with the no-sign-in/no-interaction constraints. The screenshot verifier deducted 0.5 points because the agent additionally reported absolute opened dates that were not visible in the pixels; the DOM contained those exact dates.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 96,379 | 9,434 | 1,536 | 105,813 |
| DOM model | 109,237 | 10,460 | 1,472 | 119,697 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 13,884 more scoring tokens, a 13.1% increase. Rubric generation was separate: 12,679 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry, and the DOM pipeline recorded no fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct repo and date basis | Present / Yes | Present / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Exact issue filters | Present / Yes | Present / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Matching issue count | `Open 17` / Yes | `Open 17` / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Three newest issue records | Numbers/titles caught; exact dates absent | Numbers/titles and exact dates / Yes | 2.5/3 / 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints and stopping | Present / Yes | Present / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot3.png` shows the final filtered list ordered by Newest, `Open 17`, and the first three matching issues as #48633, #48630, and #48626 with the titles reported by the agent. It displays only relative timestamps: `opened 2h ago`, `opened 8h ago`, and `opened 12h ago`.

`dom_model3.txt` preserves the same filter, count, issue ordering, numbers, and titles, but also exposes the corresponding absolute dates: #48633 opened Sep 9, 2026; #48630 and #48626 opened Sep 8, 2026. Thus, the screenshot verifier did not overlook visible text; the pixel representation lacked the exact dates that were available in DOM evidence.

The differing action-only points for the count and newest-issues criteria are independent judge variance. Both evidence stages recovered the required count and issue records. The remaining final 0.5-point difference is attributable to the screenshot-only absence of absolute date metadata.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **1/5 criteria** (absolute opened dates)
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed screenshot-verifier perception misses: **0/5 criteria**
- Confirmed DOM-verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible perception misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible perception misses)**

**Summary:** Both verifiers recovered all rubric-required issue-search evidence and passed the task. DOM additionally preserved exact opened dates that the screenshot represented only as relative times, avoiding a 0.5-point screenshot deduction. This is screenshot representation loss, not a screenshot-verifier perception miss. DOM used 13.1% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_018-github-issue-search-20260909T074333Z.json)
- [Comparison report](results/browser_task_018-github-issue-search-20260909T074333Z/20260909T_task018_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_018-github-issue-search-20260909T074333Z/20260909T_task018_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_018-github-issue-search-20260909T074333Z/20260909T_task018_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_018-github-issue-search-20260909T074333Z/20260909T_task018_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 19 — GitHub release research

Task ID: `browser_task_019-github-release-research-20260909T074525Z`

Run: `20260909T_task019_data_new`

Frozen rubric: 6 criteria, 16 maximum points

Rubric SHA-256: `b6de0067c9d19eb4956371b6c427ccb33bacfad0dbf9df5d089946db8cfcac71`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/16 (87.5%) | 16/16 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Pass |
| Overall verifier score | 0 | 1 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 23 |
| API attempts / retries | 12 / 0 | 23 / 0 |
| Duration | 80.199 s | 117.278 s |

Both verifiers confirmed the latest PyTorch release, tag, first three highlight bullets, and stopping behavior. The screenshot verifier could not validate the agent’s exact release date because the pixel evidence displayed only a relative time. The DOM preserved the exact timestamp and therefore passed the outcome.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 68,481 | 7,646 | 1,920 | 76,127 |
| DOM model | 103,171 | 12,413 | 1,152 | 115,584 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 39,457 more scoring tokens, a 51.8% increase. Rubric generation was separate: 12,644 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry. The DOM pipeline recorded one fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access releases listing | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Latest release | `PyTorch 2.14.0`, Latest / Yes | Same / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Release tag | `v2.14.0` / Yes | `v2.14.0` / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Exact release date | Only `last week`; exact date absent | `02 Sep 17:40` / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| First three highlights | Present / Yes | Present / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Stopping condition | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` displays the release as `PyTorch 2.14.0 Release`, marks it `Latest`, shows tag `v2.14.0`, but gives only the relative timestamp `ethche released this last week`. `screenshot1.png` clearly shows the first three Highlights in the same order reported by the agent.

`dom_model0.txt` preserves the same release metadata and additionally exposes `ethche released this 02 Sep 17:40` and `02 Sep 17:40`, exactly matching the agent’s final answer. Both DOM states preserve the highlight text. The exact date was therefore available only in the DOM representation.

The action-only point differences are independent judge variance and were resolved by evidence for every criterion except the release date. The final 2-point and outcome difference is attributable to the exact timestamp being absent from the screenshot pixels but present in DOM evidence.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **1/6 criteria** (exact release timestamp)
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed screenshot-verifier perception misses: **0/6 criteria**
- Confirmed DOM-verifier perception misses: **0/6 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible perception misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible perception misses)**

**Summary:** Both verifiers recovered all shared release evidence correctly. DOM additionally preserved the exact absolute release timestamp, while the screenshot showed only “last week”; this caused the screenshot’s 2-point deduction and failed outcome. It is screenshot representation loss, not verifier perception failure. DOM used 51.8% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_019-github-release-research-20260909T074525Z.json)
- [Comparison report](results/browser_task_019-github-release-research-20260909T074525Z/20260909T_task019_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_019-github-release-research-20260909T074525Z/20260909T_task019_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_019-github-release-research-20260909T074525Z/20260909T_task019_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_019-github-release-research-20260909T074525Z/20260909T_task019_data_new/evidence_error_audit/evidence_error_report.md)


---


---

## Task 20 — GitHub code search

Task ID: `browser_task_020-github-code-search-20260909T074624Z`

Run: `20260912T_task020_data_new`

Frozen rubric: 5 criteria, 12 maximum points

Rubric SHA-256: `5cc681d5bdaf6c0792b0062db6a687c29b6f9006c30dbbf35a077eac02df6060`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/12 (100.0%) | 5/12 (41.7%) |
| Rubric threshold | Pass | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 6 / 7 screenshots | 6 / 7 DOM states |
| Scoring LLM calls | 21 | 37 |
| API attempts / retries | 21 / 0 | 37 / 0 |
| Duration | 75.484 s | 105.917 s |

Both verifiers recognized the repository-scoped search attempt, GitHub sign-in blocker, and missing requested answer. The process-score difference came from how the blocker exception was applied: the screenshot run granted full blocker credit, while the DOM run judged that direct repository-file navigation remained possible.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 115,308 | 10,721 | 1,472 | 126,029 |
| DOM model | 220,862 | 20,364 | 2,368 | 241,226 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 115,197 more scoring tokens, a 91.4% increase. Rubric generation was separate: 12,394 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Attempt repository-scoped code search | Search attempt and sign-in blocker visible / Yes | Repo-qualified query and blocker explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Identify the true definition location | Definition absent and blocker visible / Yes | Definition absent and blocker explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report exact file path and line number | Path/line absent and blocker visible / Yes | Path/line absent and blocker explicit / Yes | 4/4 / 0/4 | BOTH_CAUGHT |
| Provide definition context | Declaration context absent / Yes | Declaration context absent / Yes | 2/2 / 0/2 | BOTH_CAUGHT |
| Respect constraints and stopping condition | Signed-out state and blocker visible / Yes | Signed-out state and blocker explicit / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

Manual inspection of `screenshot0.png` through `screenshot6.png` confirmed that the agent opened the FastAPI repository, attempted GitHub search, and reached the final “Sign in to search code on GitHub” page. No screenshot contains an opened `Depends` definition, exact file path and line number, or declaration context.

`dom_model6.txt` explicitly preserves `repo:fastapi/fastapi class Depends` at line 22 and the sign-in requirement at lines 48–49. No DOM state contains an opened definition, exact line, or declaration context. The representations therefore contain the same criterion-relevant evidence; the score difference is a blocker-policy judgment difference rather than asymmetric evidence loss.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/5 criteria**
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed screenshot-verifier perception misses: **0/5 criteria**
- Confirmed DOM-verifier perception misses: **0/5 criteria**
- Screenshot catch rate on common evidence: **5/5 (100%)**
- DOM catch rate on common evidence: **5/5 (100%)**

**Summary:** Both modalities preserved and both verifiers recovered the same task-relevant evidence. The screenshot verifier scored 12/12 and the DOM verifier scored 5/12 because they applied the frozen rubric's blocker allowance differently, not because either modality lost evidence. DOM used 91.4% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_020-github-code-search-20260909T074624Z.json)
- [Comparison report](results/browser_task_020-github-code-search-20260909T074624Z/20260912T_task020_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_020-github-code-search-20260909T074624Z/20260912T_task020_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_020-github-code-search-20260909T074624Z/20260912T_task020_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_020-github-code-search-20260909T074624Z/20260912T_task020_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 21 — GitHub repository comparison

Task ID: `browser_task_021-github-repository-comparison-20260909T074816Z`

Run: `20260912T_task021_data_new`

Frozen rubric: 6 criteria, 20 maximum points

Rubric SHA-256: `debcba8462f7fdd11da93321b7a54b61c17e70bd24a971559faa0669d7264395`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 20/20 (100.0%) | 20/20 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 2 / 3 screenshots | 2 / 3 DOM states |
| Scoring LLM calls | 14 | 16 |
| API attempts / retries | 14 / 0 | 16 / 0 |
| Duration | 64.892 s | 76.389 s |

Both verifiers confirmed all three repositories, all nine requested GitHub metrics, the correctly formatted comparison table, the descending star ranking, and compliance with the no-sign-in/no-interaction constraints. Both modes earned full process credit and passed the final outcome.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 84,272 | 8,111 | 1,344 | 92,383 |
| DOM model | 109,552 | 10,084 | 2,112 | 119,636 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 27,253 more scoring tokens, a 29.5% increase. Rubric generation was separate: 13,185 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry, and the DOM pipeline recorded no fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| vllm-project/vllm metrics | Present / Yes | Present / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| ggml-org/llama.cpp metrics | Present / Yes | Present / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| sgl-project/sglang metrics | Present / Yes | Present / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Present results in a table | All nine underlying values present / Yes | All nine underlying values present / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Rank repositories by stars | Three star counts present / Yes | Three star counts present / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Respect no-sign-in/no-interaction constraints | Logged-out, read-only states / Yes | Logged-out, read-only states / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png`, `screenshot1.png`, and `screenshot2.png` visibly contain the requested metrics for vllm, llama.cpp, and sglang respectively. The corresponding `dom_model0.txt` through `dom_model2.txt` files explicitly preserve the same repository identities and values. Both verifiers combined the per-repository values correctly to validate the final table and ranking.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/6 criteria**
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed screenshot-verifier perception misses: **0/6 criteria**
- Confirmed DOM-verifier perception misses: **0/6 criteria**
- Screenshot catch rate on common evidence: **6/6 (100%)**
- DOM catch rate on common evidence: **6/6 (100%)**

**Summary:** Both representations contained the complete criterion-relevant evidence, and both verifiers recovered and scored it consistently. There was no source-evidence loss or confirmed verifier miss in either modality. DOM used 29.5% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_021-github-repository-comparison-20260909T074816Z.json)
- [Comparison report](results/browser_task_021-github-repository-comparison-20260909T074816Z/20260912T_task021_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_021-github-repository-comparison-20260909T074816Z/20260912T_task021_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_021-github-repository-comparison-20260909T074816Z/20260912T_task021_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_021-github-repository-comparison-20260909T074816Z/20260912T_task021_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 22 — Stack Overflow search

Task ID: `browser_task_022-stackoverflow-search-20260909T074929Z`

Run: `20260912T_task022_data_new`

Frozen rubric: 4 criteria, 16 maximum points

Rubric SHA-256: `686ac06cb94ab6ea86b0b6d34f7a460778f78a64d2bf8d39a666c8ee5bc3ceee`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 7/16 (43.8%) | 8/16 (50.0%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 7 / 8 screenshots | 7 / 8 DOM states |
| Scoring LLM calls | 23 | 33 |
| API attempts / retries | 23 / 0 | 33 / 0 |
| Duration | 90.613 s | 126.648 s |

Both verifiers confirmed the correct python+pandas listing and recognized that the 365-day filter and highest-score sorting were applied. Neither representation proved that the score-at-least-50 or accepted-answer constraints were enforced, and the agent did not provide three qualifying records or rigorously establish that none existed.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 137,261 | 13,754 | 1,728 | 151,015 |
| DOM model | 197,142 | 21,832 | 2,176 | 218,974 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 67,959 more scoring tokens, a 45.0% increase. Rubric generation was separate: 12,522 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry, and the DOM pipeline recorded no fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct python+pandas tagged listing | Present / Yes | Present / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Apply required filters and sort order | Partial settings present / Yes | Same partial settings present / Yes | 2/5 / 3/5 | BOTH_CAUGHT |
| Report top three matching questions | Qualifying set not proven / Yes | Qualifying set not proven / Yes | 0/6 / 0/6 | BOTH_CAUGHT |
| Respect constraints and stopping condition | Logged out; no prohibited interaction / Yes | Same / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot6.png` and `dom_model6.txt` both show the last-365-days result set and Highest score/MostVotes sorting. They also show no positive score-at-least-50 or accepted-answer-only constraint. `screenshot6.png`, `screenshot7.png`, `dom_model6.txt`, and `dom_model7.txt` expose only low-score rows from the filtered result subset and do not prove that no qualifying records exist across the complete result set.

The one-point process-score difference is not evidence loss. Both verifiers recovered the same partial filter state; the screenshot scorer awarded 2/5 while the DOM scorer awarded 3/5 for that same incomplete criterion.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/4 criteria**
- DOM-side asymmetric source-evidence loss: **0/4 criteria**
- Confirmed screenshot-verifier perception misses: **0/4 criteria**
- Confirmed DOM-verifier perception misses: **0/4 criteria**
- Screenshot catch rate on common evidence: **4/4 (100%)**
- DOM catch rate on common evidence: **4/4 (100%)**

**Summary:** Both modalities contained and both verifiers recovered the same criterion-relevant evidence. The task failed because the agent did not enforce all required constraints or provide the requested records. The one-point difference is scoring variance, and DOM used 45.0% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_022-stackoverflow-search-20260909T074929Z.json)
- [Comparison report](results/browser_task_022-stackoverflow-search-20260909T074929Z/20260912T_task022_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_022-stackoverflow-search-20260909T074929Z/20260912T_task022_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_022-stackoverflow-search-20260909T074929Z/20260912T_task022_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_022-stackoverflow-search-20260909T074929Z/20260912T_task022_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 23 — Google Scholar literature search

Task ID: `browser_task_023-scholar-literature-search-20260909T075058Z`

Run: `20260912T_task023_data_new`

Frozen rubric: 7 criteria, 17 maximum points

Rubric SHA-256: `be2cf947b51ee43a5254de444eeb65eb7d175fbcc7ea08f53ad322637e49fc4b`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/17 (100.0%) | 17/17 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 2 / 3 screenshots | 2 / 3 DOM states |
| Scoring LLM calls | 14 | 15 |
| API attempts / retries | 14 / 0 | 15 / 0 |
| Duration | 70.472 s | 78.469 s |

Both verifiers confirmed that the agent attempted the correct Google Scholar search while logged out, encountered a genuine unusual-traffic block, stopped without bypassing it, and did not fabricate the unavailable citation details. The blocker allowances in the frozen rubric produced full process credit, while both outcome checks failed because the requested citation results were not delivered.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 77,630 | 7,407 | 1,408 | 85,037 |
| DOM model | 73,728 | 8,164 | 1,088 | 81,892 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 3,145 fewer scoring tokens, a 3.7% reduction. Rubric generation was separate: 13,801 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry, and the DOM pipeline recorded no fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use Scholar logged out and handle block | Block visible / Yes | Block explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Original citation count | Unavailable due to block / Yes | Unavailable due to block / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Cited-by results and 2024+ filter | Unavailable due to block / Yes | Unavailable due to block / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| First citing-paper record | Unavailable due to block / Yes | Unavailable due to block / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Second citing-paper record | Unavailable due to block / Yes | Unavailable due to block / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Third citing-paper record | Unavailable due to block / Yes | Unavailable due to block / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Respect stopping condition | Blocked stop, no fabricated records / Yes | Same / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` and `screenshot1.png` show Google Scholar in a logged-out state, while `screenshot2.png` visibly reports unusual traffic and asks the user to try again later. `dom_model2.txt` preserves the same block message at lines 7–8 and contains no search results, citation count, Cited-by page, date filter, or citing-paper records.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/7 criteria**
- DOM-side asymmetric source-evidence loss: **0/7 criteria**
- Confirmed screenshot-verifier perception misses: **0/7 criteria**
- Confirmed DOM-verifier perception misses: **0/7 criteria**
- Screenshot catch rate on common evidence: **7/7 (100%)**
- DOM catch rate on common evidence: **7/7 (100%)**

**Summary:** Both representations captured the same genuine Google Scholar access block, and both verifiers handled it consistently. There was no evidence loss or verifier miss. DOM used 3.7% fewer scoring tokens, but neither mode could verify the requested research result because the website blocked access.

### Artifacts

- [Frozen rubric](rubrics/browser_task_023-scholar-literature-search-20260909T075058Z.json)
- [Comparison report](results/browser_task_023-scholar-literature-search-20260909T075058Z/20260912T_task023_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_023-scholar-literature-search-20260909T075058Z/20260912T_task023_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_023-scholar-literature-search-20260909T075058Z/20260912T_task023_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_023-scholar-literature-search-20260909T075058Z/20260912T_task023_data_new/evidence_error_audit/evidence_error_report.md)



---

## Task 24 — Hacker News inspection

Task ID: `browser_task_024-hacker-news-inspection-20260909T075133Z`

Run: `20260912T_task024_data_new`

Frozen rubric: 4 criteria, 15 maximum points

Rubric SHA-256: `c3c7c4d619065b4c6191ec5934aa1368727ebecdba8fd35a44bb32f42ce4e196`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/15 (100.0%) | 7/15 (46.7%) |
| Rubric threshold | Pass | Fail |
| Final outcome | Pass | Fail |
| Overall verifier score | 1 | 0 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 16 |
| API attempts / retries | 12 / 0 | 16 / 0 |
| Duration | 68.682 s | 102.292 s |

Both evidence sources contain the full first-30 story range and identify the same sole GitHub-linked story. The screenshot verifier combined its two frames and awarded full credit. The DOM verifier found the GitHub story but failed to combine rows 3–7 from state 0 with rows through 30 from state 1, producing two confirmed verifier misses.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 66,973 | 7,307 | 2,432 | 74,280 |
| DOM model | 109,962 | 9,239 | 1,280 | 119,201 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 44,921 more scoring tokens, a 60.5% increase. Rubric generation was separate: 12,297 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry, and the DOM pipeline recorded no fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access Hacker News front page | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Inspect exactly the first 30 stories | Present across frames 0–1 / Yes | Present across states 0–1 / No | 4/4 / 1/4 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Identify GitHub count and title | Exactly one at #20 / Yes | Exactly one at #20 / No | 7/7 / 2/7 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Respect interaction constraints | Logged out; scroll only / Yes | Logged out; scroll only / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` shows stories 1–23 and `screenshot1.png` shows stories 11–30. The DOM source also has complete coverage: `dom_model0.txt` explicitly contains rows 1–26, including rows 3–7, and `dom_model1.txt` reaches row 30. Both modalities show only row 20 as GitHub-linked: “I-have-ADHD: A skill to stop coding agents from burying the answer” (`github.com/ayghri`).

The DOM deductions are not source-evidence loss. They are confirmed verifier aggregation misses: the evidence existed across the ordered DOM states, but the verifier incorrectly treated rows 3–7 as unavailable when deciding completeness and the total GitHub count.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/4 criteria**
- DOM-side asymmetric source-evidence loss: **0/4 criteria**
- Confirmed screenshot-verifier perception misses: **0/4 criteria**
- Confirmed DOM-verifier perception misses: **2/4 criteria**
- Screenshot catch rate on common evidence: **4/4 (100%)**
- DOM catch rate on common evidence: **2/4 (50%)**
- Screenshot recovery of confirmed DOM misses: **2/2 (100%)**

**Summary:** Both inputs preserved the necessary evidence. Screenshot scored 15/15; DOM scored 7/15 because its verifier failed to aggregate complementary evidence from states 0 and 1. DOM also used 60.5% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_024-hacker-news-inspection-20260909T075133Z.json)
- [Comparison report](results/browser_task_024-hacker-news-inspection-20260909T075133Z/20260912T_task024_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_024-hacker-news-inspection-20260909T075133Z/20260912T_task024_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_024-hacker-news-inspection-20260909T075133Z/20260912T_task024_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_024-hacker-news-inspection-20260909T075133Z/20260912T_task024_data_new/evidence_error_audit/evidence_error_report.md)


---

## Task 25 — Hacker News search

Task ID: `browser_task_025-hacker-news-search-20260909T075205Z`  
Run: `20260912T_task025_data_new`  
Frozen rubric: 5 criteria, 20 points  
Rubric SHA-256: `10d8137e689425c914ae0a893656b68a76d41e713d5413a3983bfa3b7d0fda40`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 19/20 (95.0%) | 19/20 (95.0%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 5 / 6 | 5 / 6 |
| LLM calls / retries | 19 / 0 | 28 / 0 |
| Duration | 73.799 s | 114.716 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 107,092 | 9,958 | 1,728 | 117,050 |
| DOM model | 161,210 | 20,284 | 1,344 | 181,494 |

*Reasoning tokens are included within completion tokens.* DOM used 64,444 more scoring tokens (+55.1%). Rubric generation was separate: 12,867 tokens in 2 calls; scoring reported `rubric_generation_calls: 0` in both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Search Algolia for “LLM” | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Apply Show HN and Past Year | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Sort by points descending | Indirect / Yes | Indirect / Yes | 2/3 / 2/3 | BOTH_CAUGHT |
| Report top results and fields | Yes / Yes | Yes / Yes | 6/6 / 6/6 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |

**Evidence-error result:** no source loss and no verifier miss (0/5 for both). Both modes recovered the same evidence and scored 19/20.

Artifacts: [rubric](rubrics/browser_task_025-hacker-news-search-20260909T075205Z.json) Â· [comparison](results/browser_task_025-hacker-news-search-20260909T075205Z/20260912T_task025_data_new/comparison.md) Â· [audit](results/browser_task_025-hacker-news-search-20260909T075205Z/20260912T_task025_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 26 — Amazon shopping constraints

Task ID: `browser_task_026-shopping-constraint-satisfaction-20260909T075313Z`  
Run: `20260912T_task026_data_new`  
Frozen rubric: 7 criteria, 18 points  
Rubric SHA-256: `b98cd8fd5da1831ceb7d0ff89fd58c491c1ee5ba1c2f9636ae58f15e809db13a`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6/18 (33.3%) | 6/18 (33.3%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 9 / 10 | 9 / 10 |
| LLM calls / retries | 25 / 0 | 33 / 0 |
| Duration | 104.394 s | 122.622 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 157,549 | 16,609 | 2,560 | 174,158 |
| DOM model | 213,918 | 22,759 | 1,728 | 236,677 |

*Reasoning tokens are included within completion tokens.* DOM used 62,519 more scoring tokens (+35.9%). Rubric generation: 13,849 tokens in 2 calls; scoring rubric calls were 0.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Search for wireless mouse | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Apply filters and sorting | Partial / Yes | Partial / Yes | 1/4 / 1/4 | BOTH_CAUGHT |
| Report product #1 | Not established / Yes | Not established / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Report product #2 | Not established / Yes | Not established / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Report product #3 | Not established / Yes | Not established / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Handle access block | No qualifying block / Yes | No qualifying block / Yes | 0/2 / 0/2 | BOTH_CAUGHT |

**Evidence-error result:** no source loss and no verifier miss (0/7 for both). Both verifiers scored the same incomplete trajectory identically.

Artifacts: [rubric](rubrics/browser_task_026-shopping-constraint-satisfaction-20260909T075313Z.json) Â· [comparison](results/browser_task_026-shopping-constraint-satisfaction-20260909T075313Z/20260912T_task026_data_new/comparison.md) Â· [audit](results/browser_task_026-shopping-constraint-satisfaction-20260909T075313Z/20260912T_task026_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 27 — eBay laptop constraints

Task ID: `browser_task_027-shopping-constraint-satisfaction-20260909T075513Z`  
Run: `20260912T_task027_data_new`  
Frozen rubric: 5 criteria, 18 points  
Rubric SHA-256: `2212291f68520b789f988e7484e561cb893b90ec6481965020f5f65c8540c648`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 8.5/18 (47.2%) | 7/18 (38.9%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 12 / 13 | 12 / 13 |
| LLM calls / retries | 30 / 0 | 36 / 0 |
| Duration | 80.363 s | 116.479 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 153,527 | 12,278 | 1,792 | 165,805 |
| DOM model | 284,622 | 19,654 | 1,600 | 304,276 |

*Reasoning tokens are included within completion tokens.* DOM used 138,471 more scoring tokens (+83.5%). Rubric generation: 12,935 tokens in 2 calls; scoring rubric calls were 0.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Browse without restricted actions | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Find price-qualified listing | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Verify RAM/SSD in item specifics | Fields absent / Yes | Fields absent / Yes | 1/6 / 0/6 | BOTH_CAUGHT |
| Report model, price, RAM, SSD | Partial / Yes | Partial / Yes | 1.5/3 / 0/3 | BOTH_CAUGHT |
| Stop and handle blocker | Incomplete / Yes | Incomplete / Yes | 0/3 / 1/3 | BOTH_CAUGHT |

**Evidence-error result:** no source loss and no verifier miss (0/5 for both). The 1.5-point difference is scoring variance, not missing evidence.

Artifacts: [rubric](rubrics/browser_task_027-shopping-constraint-satisfaction-20260909T075513Z.json) Â· [comparison](results/browser_task_027-shopping-constraint-satisfaction-20260909T075513Z/20260912T_task027_data_new/comparison.md) Â· [audit](results/browser_task_027-shopping-constraint-satisfaction-20260909T075513Z/20260912T_task027_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 28 — BBC Technology monitoring

Task ID: `browser_task_028-news-monitoring-20260909T075747Z`  
Run: `20260912T_task028_data_new`  
Frozen rubric: 5 criteria, 18 points  
Rubric SHA-256: `ecbe8f31750b2f052bb63998de33a2ea569f9d4c48902231f80cc943eac91636`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 4/18 (22.2%) | 4/18 (22.2%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 2 / 3 | 2 / 3 |
| LLM calls / retries | 14 / 0 | 31 / 0 |
| Duration | 82.231 s | 180.254 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 78,526 | 8,345 | 1,600 | 86,871 |
| DOM model | 117,611 | 20,861 | 2,880 | 138,472 |

*Reasoning tokens are included within completion tokens.* DOM used 51,601 more scoring tokens (+59.4%). Rubric generation: 12,774 tokens in 2 calls; scoring rubric calls were 0.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access BBC Technology | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record five newest headlines | Absent / Yes | Absent / Yes | 0/5 / 0/5 | BOTH_CAUGHT |
| Record exact timestamps | Absent / Yes | Absent / Yes | 0/6 / 0/6 | BOTH_CAUGHT |
| Stop after recording results | Not completed / Yes | Not completed / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Respect no-login/no-ad constraints | Ad interaction / Yes | Ad interaction / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

**Evidence-error result:** no source loss and no verifier miss (0/5 for both). Both captured the same incorrect navigation and scored it identically.

Artifacts: [rubric](rubrics/browser_task_028-news-monitoring-20260909T075747Z.json) Â· [comparison](results/browser_task_028-news-monitoring-20260909T075747Z/20260912T_task028_data_new/comparison.md) Â· [audit](results/browser_task_028-news-monitoring-20260909T075747Z/20260912T_task028_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 29 — Coursera course filtering

Task ID: `browser_task_029-course-search-and-filtering-20260909T075844Z`  
Run: `20260912T_task029_data_new`  
Frozen rubric: 7 criteria, 18 points  
Rubric SHA-256: `3daffb68fd3e0e8bf3aed4b5b7a36a638215f13377b5964ac7a3093aad4e3094`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/18 (94.4%) | 15/18 (83.3%) |
| Rubric / outcome | Pass / Fail | Pass / Fail |
| Actions / states | 18 / 19 | 18 / 19 |
| LLM calls / retries | 41 / 0 | 46 / 0 |
| Duration | 105.231 s | 123.692 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 238,915 | 19,414 | 1,920 | 258,329 |
| DOM model | 319,661 | 24,988 | 3,264 | 344,649 |

*Reasoning tokens are included within completion tokens.* DOM used 86,320 more scoring tokens (+33.4%). Rubric generation: 13,309 tokens in 2 calls; scoring rubric calls were 0.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access Coursera results | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Apply requested filters | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Identify highest-rated courses | Better alternatives visible / No | Alternatives explicit / Yes | 3/4 / 1/4 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Report Course #1 fields | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report Course #2 fields | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report Course #3 fields | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot12.png` visibly contains qualifying 4.8-rated alternatives, including “Prepare Data for Exploration” and “Prompt Engineering for ChatGPT,” while the chosen list includes a 4.6 course. `dom_model13.txt` explicitly lists the same alternatives. This is a screenshot-verifier miss, not screenshot source loss.

**Evidence-error result:** source loss 0/7 for both; screenshot-verifier miss 1/7; DOM-verifier miss 0/7; DOM recovered 1/1 confirmed screenshot miss.

Artifacts: [rubric](rubrics/browser_task_029-course-search-and-filtering-20260909T075844Z.json) Â· [comparison](results/browser_task_029-course-search-and-filtering-20260909T075844Z/20260912T_task029_data_new/comparison.md) Â· [audit](results/browser_task_029-course-search-and-filtering-20260909T075844Z/20260912T_task029_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 30 — Coursera course inspection

Task ID: `browser_task_030-course-detail-inspection-20260909T080218Z`  
Run: `20260912T_task030_data_new`  
Frozen rubric: 6 criteria, 16 points  
Rubric SHA-256: `d72d9b5be1488b333321130e761a98f676847890a290a6b5fe324b932028a2e6`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15.5/16 (96.9%) | 15/16 (93.8%) |
| Rubric / outcome | Pass / Fail | Pass / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 16 / 0 |
| Duration | 83.198 s | 108.341 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 72,207 | 8,102 | 2,176 | 80,309 |
| DOM model | 85,692 | 11,927 | 1,920 | 97,619 |

*Reasoning tokens are included within completion tokens.* DOM used 17,310 more scoring tokens (+21.6%). Rubric generation: 13,529 tokens in 2 calls; scoring rubric calls were 0.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access course page | Alternate page / Yes | Alternate page / Yes | 4/4 / 3/4 | BOTH_CAUGHT |
| Record instructor | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record institution | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record module count | Yes / Yes | Yes / Yes | 2.5/3 / 3/3 | BOTH_CAUGHT |
| Determine audit option | Qualified absence / Yes | Qualified absence / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Respect stopping constraints | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Evidence-error result:** no source loss and no verifier miss (0/6 for both). Both recovered the same evidence; the half-point difference is scoring severity.

Artifacts: [rubric](rubrics/browser_task_030-course-detail-inspection-20260909T080218Z.json) Â· [comparison](results/browser_task_030-course-detail-inspection-20260909T080218Z/20260912T_task030_data_new/comparison.md) Â· [audit](results/browser_task_030-course-detail-inspection-20260909T080218Z/20260912T_task030_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 31 — Nobel Physics table lookup

Task ID: `browser_task_031-table-lookup-and-extraction-20260909T080306Z`  
Run: `20260914T_task031_data_new`  
Frozen rubric: 4 criteria, 15 points  
Rubric SHA-256: `1f258ed34b24d9908e533b69708ef9ff958f65a514ffc2a461789d2905a7a372`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 3/15 (20.0%) | 1/15 (6.7%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 10 / 0 | 10 / 0 |
| Scoring tokens | 59,475 | 58,724 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Complete 1921 Nobel Physics entry | No / No | No / No | 0/4 / 0/4 | BOTH_CAUGHT |
| Complete 1922 Nobel Physics entry | No / No | No / No | 0/4 / 0/4 | BOTH_CAUGHT |
| Complete 1923 Nobel Physics entry | No / No | No / No | 0/4 / 0/4 | BOTH_CAUGHT |
| Constraints and stopping condition | Yes / Yes | Yes / Yes | 3/3 / 1/3 | BOTH_CAUGHT |

**Summary:** Both sources stopped above the requested 1921–1923 rows. The two-point difference is scoring interpretation, not asymmetric evidence loss.

Artifacts: [rubric](rubrics/browser_task_031-table-lookup-and-extraction-20260909T080306Z.json) · [comparison](results/browser_task_031-table-lookup-and-extraction-20260909T080306Z/20260914T_task031_data_new/comparison.md) · [criterion audit](results/browser_task_031-table-lookup-and-extraction-20260909T080306Z/20260914T_task031_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 32 — MDN container-type inspection

Task ID: `browser_task_032-technical-documentation-inspection-20260909T080346Z`  
Run: `20260914T_task032_data_new`  
Frozen rubric: 7 criteria, 20 points  
Rubric SHA-256: `694dab3808aea3a9751b6e53ef19bee73f42a8c06b3be48a3b1c415cd8170d46`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6/20 (30.0%) | 4/20 (20.0%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 12 / 0 | 23 / 0 |
| Scoring tokens | 86,653 | 146,914 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Formal-definition initial value | Partial / Yes | Partial / Yes | 0/3 / 1/3 | BOTH_CAUGHT |
| Formal-definition applies-to value | No / No | No / No | 0/3 / 0/3 | BOTH_CAUGHT |
| Current syntax keyword values | Yes / Yes | Yes / Yes | 4/4 / 2/4 | BOTH_CAUGHT |
| Earliest Chrome support | No / No | No / No | 0/2 / 0/2 | BOTH_CAUGHT |
| Earliest Firefox support | No / No | No / No | 0/2 / 0/2 | BOTH_CAUGHT |
| Earliest Safari support | No / No | No / No | 0/2 / 0/2 | BOTH_CAUGHT |
| Constraints and stopping condition | Yes / Yes | Yes / Yes | 2/4 / 1/4 | BOTH_CAUGHT |

**Summary:** Both modes received the syntax/default-value material but neither received the Formal definition or Browser compatibility tables. Score differences reflect judgment, not source loss.

Artifacts: [rubric](rubrics/browser_task_032-technical-documentation-inspection-20260909T080346Z.json) · [comparison](results/browser_task_032-technical-documentation-inspection-20260909T080346Z/20260914T_task032_data_new/comparison.md) · [criterion audit](results/browser_task_032-technical-documentation-inspection-20260909T080346Z/20260914T_task032_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 33 — PyPI package metadata

Task ID: `browser_task_033-software-package-metadata-20260909T080442Z`  
Run: `20260914T_task033_data_new`  
Frozen rubric: 7 criteria, 20 points  
Rubric SHA-256: `e987f50a1508388eff19029c26216ddd2da448997aefb8b1e786319631b301d5`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/20 (80.0%) | 17.5/20 (87.5%) |
| Outcome | Fail | Pass |
| LLM calls / retries | 12 / 0 | 18 / 0 |
| Scoring tokens | 81,497 | 102,926 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access Requests project page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Latest displayed release | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Version and upload date | Yes / Yes | Yes / Yes | 4/4 / 3/4 | BOTH_CAUGHT |
| Requires Python | No / No | No / No | 3/3 / 3/3 | BOTH_CAUGHT |
| License | No / No | No / No | 3/3 / 3/3 | BOTH_CAUGHT |
| Download-file count | No / No | Yes / Yes | 1/4 / 3/4 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints and no inference | Yes / Yes | Yes / Yes | 1/2 / 1.5/2 | BOTH_CAUGHT |

**Summary:** The screenshot showed one source-distribution row and the Built Distribution heading, but not the second file/count. DOM explicitly preserved the additional `Showing 1 of 1 file` evidence.

Artifacts: [rubric](rubrics/browser_task_033-software-package-metadata-20260909T080442Z.json) · [comparison](results/browser_task_033-software-package-metadata-20260909T080442Z/20260914T_task033_data_new/comparison.md) · [criterion audit](results/browser_task_033-software-package-metadata-20260909T080442Z/20260914T_task033_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 34 — RubyGems dependency inspection

Task ID: `browser_task_034-dependency-inspection-20260909T080508Z`  
Run: `20260914T_task034_data_new`  
Frozen rubric: 9 criteria, 20 points  
Rubric SHA-256: `bff329749131a4a0d59fe780a228d6d7277fea87b8202c6904f5168b64267bf6`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 19/20 (95.0%) | 20/20 (100%) |
| Outcome | Fail | Pass |
| LLM calls / retries | 12 / 0 | 22 / 0 |
| Scoring tokens | 81,140 | 110,523 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access Rails gem page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| No sign-in or installation | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Latest Rails version | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Version, date, Ruby requirement, and license | Partial / Yes | Yes / Yes | 3/4 / 4/4 | SCREENSHOT_EVIDENCE_MISSING |
| Runtime dependency 1 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Runtime dependency 2 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Runtime dependency 3 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Runtime dependency 4 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Runtime dependency 5 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** The screenshot captured the version, date, and Ruby requirement but not the off-viewport license. DOM explicitly preserved `License: MIT`.

Artifacts: [rubric](rubrics/browser_task_034-dependency-inspection-20260909T080508Z.json) · [comparison](results/browser_task_034-dependency-inspection-20260909T080508Z/20260914T_task034_data_new/comparison.md) · [criterion audit](results/browser_task_034-dependency-inspection-20260909T080508Z/20260914T_task034_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 35 — Docker image-tag comparison

Task ID: `browser_task_035-container-image-tag-comparison-20260909T080532Z`  
Run: `20260914T_task035_data_new`  
Frozen rubric: 5 criteria, 20 points  
Rubric SHA-256: `003b90014d5fed37a6292b1c5ce248284dabbaa1bc85dec01fd756fba5b5bc02`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 10/20 (50.0%) | 11/20 (55.0%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 12 / 0 | 18 / 0 |
| Scoring tokens | 79,468 | 108,289 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access and search official Tags page | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Exact-prefix filtering | Partial / Yes | Partial / Yes | 2/3 / 2/3 | BOTH_CAUGHT |
| Three most recently updated tags | Partial / Yes | Partial / Yes | 2/8 / 3/8 | BOTH_CAUGHT |
| Required fields without guessing | Partial / Yes | Partial / Yes | 1/4 / 1/4 | BOTH_CAUGHT |
| No sign-in or image execution | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Neither representation proved three complete tag cards. DOM contained contradictory flattened tag/table relationships, and its verifier explicitly reported that limitation; no asymmetric source loss was confirmed.

Artifacts: [rubric](rubrics/browser_task_035-container-image-tag-comparison-20260909T080532Z.json) · [comparison](results/browser_task_035-container-image-tag-comparison-20260909T080532Z/20260914T_task035_data_new/comparison.md) · [criterion audit](results/browser_task_035-container-image-tag-comparison-20260909T080532Z/20260914T_task035_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 36 — Debian curl dependency lookup

Task ID: `browser_task_036-package-dependency-lookup-20260909T080606Z`  
Run: `20260914T_task036_data_new`  
Frozen rubric: 5 criteria, 16 points  
Rubric SHA-256: `21c4811a4e548e87e00a1e3531cb01097dc7c0680f13eb540ec9481d4dd05203`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/16 (100%) | 16/16 (100%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 12 / 0 | 14 / 0 |
| Scoring tokens | 76,100 | 82,571 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Debian Bookworm curl page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Package version | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Download architectures | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Required dependencies and constraints | Yes / Yes | Yes / Yes | 6/6 / 6/6 | BOTH_CAUGHT |
| Scope and stopping constraints | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both modes preserved and recovered all requested Debian package evidence.

Artifacts: [rubric](rubrics/browser_task_036-package-dependency-lookup-20260909T080606Z.json) · [comparison](results/browser_task_036-package-dependency-lookup-20260909T080606Z/20260914T_task036_data_new/comparison.md) · [criterion audit](results/browser_task_036-package-dependency-lookup-20260909T080606Z/20260914T_task036_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 37 — Homebrew ffmpeg availability

Task ID: `browser_task_037-package-platform-availability-20260909T080647Z`  
Run: `20260914T_task037_data_new`  
Frozen rubric: 7 criteria, 22 points  
Rubric SHA-256: `9d32a5e889be0c21958c7736140181e10f8caa992f0f6d4a53f28324d0e74646`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 22/22 (100%) | 22/22 (100%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 15 / 0 | 21 / 0 |
| Scoring tokens | 90,182 | 105,178 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access ffmpeg formula page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Stable version | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| License | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Regular dependencies | Yes / Yes | Yes / Yes | 8/8 / 8/8 | BOTH_CAUGHT |
| Apple Silicon bottle availability | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Linux bottle availability | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Constraints and stopping condition | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both representations and verifiers recovered the complete Homebrew formula evidence.

Artifacts: [rubric](rubrics/browser_task_037-package-platform-availability-20260909T080647Z.json) · [comparison](results/browser_task_037-package-platform-availability-20260909T080647Z/20260914T_task037_data_new/comparison.md) · [criterion audit](results/browser_task_037-package-platform-availability-20260909T080647Z/20260914T_task037_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 38 — GitLab Runner release inspection

Task ID: `browser_task_038-software-release-inspection-20260909T080722Z`  
Run: `20260914T_task038_data_new`  
Frozen rubric: 4 criteria, 14 points  
Rubric SHA-256: `ba30b78805709c6d54a42713b2764923163d272ac3e0bdf2f524ce31b6d06a9f`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/14 (100%) | 12/14 (85.7%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 12 / 0 | 12 / 0 |
| Scoring tokens | 72,959 | 75,790 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access GitLab Runner releases | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| First qualifying non-prerelease tag | Yes / Yes | Yes / Yes | 4/4 / 2/4 | BOTH_CAUGHT |
| Tag and created date | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| First three Other asset names | Yes / Yes | Yes / Yes | 5/5 / 5/5 | BOTH_CAUGHT |

**Summary:** Both sources contained the same visible release entry and asset evidence. The lower DOM score reflects confidence about proving global ordering, not missing evidence.

Artifacts: [rubric](rubrics/browser_task_038-software-release-inspection-20260909T080722Z.json) · [comparison](results/browser_task_038-software-release-inspection-20260909T080722Z/20260914T_task038_data_new/comparison.md) · [criterion audit](results/browser_task_038-software-release-inspection-20260909T080722Z/20260914T_task038_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 39 — Kubernetes parameter extraction

Task ID: `browser_task_039-technical-parameter-extraction-20260909T080752Z`  
Run: `20260914T_task039_data_new`  
Frozen rubric: 3 criteria, 12 points  
Rubric SHA-256: `e09a0ab5237e118cd5f3c386ff2a529e59b9248793cb3808834b1af12137779e`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 10/12 (83.3%) | 10/12 (83.3%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 18 / 0 | 21 / 0 |
| Scoring tokens | 102,351 | 121,212 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| `maxUnavailable` meaning and default | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| `maxSurge` meaning and default | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| `progressDeadlineSeconds` meaning/default | Partial / Yes | Partial / Yes | 2/4 / 2/4 | BOTH_CAUGHT |

**Summary:** Both modalities contained the first two parameters but lacked the complete `progressDeadlineSeconds` description/default. Evidence availability and scores matched.

Artifacts: [rubric](rubrics/browser_task_039-technical-parameter-extraction-20260909T080752Z.json) · [comparison](results/browser_task_039-technical-parameter-extraction-20260909T080752Z/20260914T_task039_data_new/comparison.md) · [criterion audit](results/browser_task_039-technical-parameter-extraction-20260909T080752Z/20260914T_task039_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 40 — OpenStreetMap entity inspection

Task ID: `browser_task_040-map-entity-inspection-20260909T080852Z`  
Run: `20260914T_task040_data_new`  
Frozen rubric: 10 criteria, 16 points  
Rubric SHA-256: `2f5a5cab05458d03a0e495ac223e152659863ab23a1d08ce8b9ad6bfd8dcac8e`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12.5/16 (78.1%) | 13/16 (81.2%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 13 / 0 | 15 / 0 |
| Scoring tokens | 87,501 | 94,169 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Search for British Museum | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Exact British Museum object page | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Object type and ID | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| `addr:street` | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| `addr:city` | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| `addr:postcode` | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| `tourism` tag | No / No | No / No | 0/1 / 0/1 | BOTH_CAUGHT |
| `museum` tag | No / No | No / No | 0/1 / 0/1 | BOTH_CAUGHT |
| `website` tag | No / No | No / No | 0/1 / 0/1 | BOTH_CAUGHT |
| Constraints and stopping condition | Yes / Yes | Yes / Yes | 1.5/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both sources contained the same object/address evidence and omitted the same three tags. The half-point difference is scoring severity, not evidence loss.

Artifacts: [rubric](rubrics/browser_task_040-map-entity-inspection-20260909T080852Z.json) · [comparison](results/browser_task_040-map-entity-inspection-20260909T080852Z/20260914T_task040_data_new/comparison.md) · [criterion audit](results/browser_task_040-map-entity-inspection-20260909T080852Z/20260914T_task040_data_new/evidence_error_audit/criterion_audit.json)

---

## Tasks 31–40 evidence-error summary

Across these ten completed tasks:

- Rubric criteria audited: **61**
- BOTH_CAUGHT: **59**
- SCREENSHOT_EVIDENCE_MISSING: **2**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**
- Screenshot scoring tokens: **817,326**
- DOM scoring tokens: **1,006,296**

---

## Task 41 — Standards metadata extraction

Task ID: `browser_task_041-standards-metadata-extraction-20260909T080918Z`  
Run: `20260914T_task041_data_new`  
Frozen rubric: 5 criteria, 20 points  
Rubric SHA-256: `390ac55adb7f6723236d47e498f5810fea3795edbb61e9dc073887d520bf5558`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 18.5/20 (92.5%) | 16/20 (80.0%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 12 / 0 | 24 / 0 |
| Scoring tokens | 84,735 | 159,687 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access RFC 9110 record | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Core metadata | Date absent; other fields visible / correctly limited | All fields explicit / Yes | 4.5/6 / 6/6 | SCREENSHOT_EVIDENCE_MISSING |
| List all obsoleted RFCs | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Preserve full vs partial obsolescence | Exact sentence visible / Yes | Same sentence explicit / verifier did not use it correctly | 6/6 / 3/6 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Constraints and stopping | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

The publication date is below the screenshot viewport but explicit in `dom_model1.txt`. Both sources contain the same “portions of 7230” sentence; the DOM criterion-4 deduction is a verifier interpretation miss, while criterion 5 differs only in scoring severity. Rubric generation used 12,772 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 74,952 more scoring tokens (88.5%).

Artifacts: [rubric](rubrics/browser_task_041-standards-metadata-extraction-20260909T080918Z.json) · [comparison](results/browser_task_041-standards-metadata-extraction-20260909T080918Z/20260914T_task041_data_new/comparison.md) · [audit](results/browser_task_041-standards-metadata-extraction-20260909T080918Z/20260914T_task041_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 42 — Domain registry lookup

Task ID: `browser_task_042-domain-registry-lookup-20260909T081023Z`  
Run: `20260914T_task042_data_new`  
Frozen rubric: 7 criteria, 15 points  
Rubric SHA-256: `44708721e982b01a34e3cbe39681e8a0cce591c3ea119bb299b4d51cb5019375`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/15 (100%) | 15/15 (100%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 12 / 0 | 25 / 0 |
| Scoring tokens | 70,762 | 107,524 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use IANA .museum page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| TLD type | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Sponsoring organization | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Registration date | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| WHOIS server | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Registration-services URL | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Constraints and stopping | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Both sources and verifiers preserve/recover every required IANA field. Rubric generation used 12,896 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 36,762 more scoring tokens (52.0%).

Artifacts: [rubric](rubrics/browser_task_042-domain-registry-lookup-20260909T081023Z.json) · [comparison](results/browser_task_042-domain-registry-lookup-20260909T081023Z/20260914T_task042_data_new/comparison.md) · [audit](results/browser_task_042-domain-registry-lookup-20260909T081023Z/20260914T_task042_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 43 — Vulnerability record inspection

Task ID: `browser_task_043-vulnerability-record-inspection-20260909T081051Z`  
Run: `20260914T_task043_data_new`  
Frozen rubric: 5 criteria, 20 points  
Rubric SHA-256: `7e5d21731cdafb6d81afa53ddfb0e64f8a842e2fe3cf70a3e5c5d9040dc003e7`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 18/20 (90.0%) | 18/20 (90.0%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 14 / 0 | 26 / 0 |
| Scoring tokens | 92,442 | 149,211 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access CVE.org CNA record | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Status, date, CNA, vendor, product | First three explicit; vendor/product fields absent / correctly limited | Same / correctly limited | 3/5 / 3/5 | BOTH_CAUGHT |
| Exact affected-version statement | Yes / Yes | Yes / Yes | 6/6 / 6/6 | BOTH_CAUGHT |
| First reference URL | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Constraints and stopping | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Both sources omit explicit Vendor/Product fields, and both verifiers recognize that limitation. Rubric generation used 13,098 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 56,769 more scoring tokens (61.4%).

Artifacts: [rubric](rubrics/browser_task_043-vulnerability-record-inspection-20260909T081051Z.json) · [comparison](results/browser_task_043-vulnerability-record-inspection-20260909T081051Z/20260914T_task043_data_new/comparison.md) · [audit](results/browser_task_043-vulnerability-record-inspection-20260909T081051Z/20260914T_task043_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 44 — Earthquake filtering and ranking

Task ID: `browser_task_044-earthquake-filtering-and-ranking-20260909T081131Z`  
Run: `20260914T_task044_data_new`  
Frozen rubric: 5 criteria, 16 points  
Rubric SHA-256: `91a73e9ce7cbb9cfa0fb89a1c190e63915795fb801c4c3a183f71d4b2fc9165d`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 7/16 (43.8%) | 11/16 (68.8%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 29 / 0 | 37 / 0 |
| Scoring tokens | 176,989 | 203,188 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct query filters | Final clean range hidden; earlier malformed fields visible / correctly limited | Final URL has clean dates and magnitude / Yes | 3/5 / 4/5 | SCREENSHOT_EVIDENCE_MISSING |
| Sort by magnitude | “Newest First” visible / Yes | “Newest First” explicit / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Three reported event records | Partial list; M5.1 row absent / correctly limited | All three rows explicit / Yes | 0/5 / 3/5 | SCREENSHOT_EVIDENCE_MISSING |
| Fewer-than-three handling | 16 results visible / Yes | 16 results explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Constraints and UTC | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

The final screenshot omits the clean query parameters and the M5.1 result row. The DOM contains both, while also preserving the contradictory “Newest First” control, so the DOM verifier correctly withholds full ranking credit. Rubric generation used 12,918 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 26,199 more scoring tokens (14.8%).

Artifacts: [rubric](rubrics/browser_task_044-earthquake-filtering-and-ranking-20260909T081131Z.json) · [comparison](results/browser_task_044-earthquake-filtering-and-ranking-20260909T081131Z/20260914T_task044_data_new/comparison.md) · [audit](results/browser_task_044-earthquake-filtering-and-ranking-20260909T081131Z/20260914T_task044_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 45 — Weather forecast extraction

Task ID: `browser_task_045-weather-forecast-extraction-20260909T081343Z`  
Run: `20260914T_task045_data_new`  
Frozen rubric: 5 criteria, 20 points  
Rubric SHA-256: `3ef97ba5958cfe041448d9d42a54ac4ad18b27d24a7a7bfbf0b4e4d15ec878ee`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 20/20 (100%) | 20/20 (100%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 19 / 0 | 26 / 0 |
| Scoring tokens | 112,863 | 133,465 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use Downtown Seattle NWS page | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Select first day/night pair | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Daytime fields | Yes / Yes | Yes / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Nighttime fields | Yes / Yes | Yes / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Constraints and stopping | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Both modalities and verifiers preserve/recover the same forecast evidence. Rubric generation used 13,020 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 20,602 more scoring tokens (18.3%).

Artifacts: [rubric](rubrics/browser_task_045-weather-forecast-extraction-20260909T081343Z.json) · [comparison](results/browser_task_045-weather-forecast-extraction-20260909T081343Z/20260914T_task045_data_new/comparison.md) · [audit](results/browser_task_045-weather-forecast-extraction-20260909T081343Z/20260914T_task045_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 46 — Park operational status

Task ID: `browser_task_046-park-operational-status-20260909T081451Z`  
Run: `20260914T_task046_data_new`  
Frozen rubric: 7 criteria, 20 points  
Rubric SHA-256: `e24fd31de542dbb9ecf85ffa9e52387f76f4eba36181c54daaeb2de5917686b9`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 2/20 (10.0%) | 4/20 (20.0%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 14 / 0 | 20 / 0 |
| Scoring tokens | 98,912 | 108,826 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Conditions page and Active Alerts | Page/Alerts label visible; module absent / Yes | Same / Yes | 1/2 / 2/2 | BOTH_CAUGHT |
| Active-alert count | Absent / correctly identified | Absent / correctly identified | 0/3 / 0/3 | BOTH_CAUGHT |
| First two alert titles | Absent / correctly identified | Absent / correctly identified | 0/3 / 0/3 | BOTH_CAUGHT |
| Tioga Road status | Absent / correctly identified | Absent / correctly identified | 0/2 / 0/2 | BOTH_CAUGHT |
| Entrance Reservations page | Absent / correctly identified | Absent / correctly identified | 0/1 / 0/1 | BOTH_CAUGHT |
| 2026 reservation requirement | Absent / correctly identified | Absent / correctly identified | 0/5 / 0/5 | BOTH_CAUGHT |
| Constraints and stopping | No prohibited flow / Yes | No prohibited flow / Yes | 1/4 / 2/4 | BOTH_CAUGHT |

Both sources contain the same page state and omit the same requested content. The score difference is judgment severity for access/stopping, not evidence loss. Rubric generation used 13,281 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 9,914 more scoring tokens (10.0%).

Artifacts: [rubric](rubrics/browser_task_046-park-operational-status-20260909T081451Z.json) · [comparison](results/browser_task_046-park-operational-status-20260909T081451Z/20260914T_task046_data_new/comparison.md) · [audit](results/browser_task_046-park-operational-status-20260909T081451Z/20260914T_task046_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 47 — Regulatory API search

Task ID: `browser_task_047-regulatory-api-search-20260909T100115Z`  
Run: `20260914T_task047_data_new_retry`  
Frozen rubric: 6 criteria, 20 points  
Rubric SHA-256: `77f681aa2e64f1e70e5391e7218bc122c01fbe9a0f59bdf56758b7fd900be0af`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 4/20 (20.0%) | 4/20 (20.0%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 18 / 0 | 29 / 0 |
| Scoring tokens | 140,984 | 162,972 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Exact Federal Register API | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Only top-level results | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| First three in order | Full records absent / correctly identified | Full records absent / correctly identified | 0/4 / 0/4 | BOTH_CAUGHT |
| Result 1 fields | Incomplete / correctly identified | Incomplete / correctly identified | 0/4 / 0/4 | BOTH_CAUGHT |
| Result 2 fields | Absent / correctly identified | Absent / correctly identified | 0/4 / 0/4 | BOTH_CAUGHT |
| Result 3 fields | Absent / correctly identified | Absent / correctly identified | 0/4 / 0/4 | BOTH_CAUGHT |

Both representations stop near the beginning of the response, and both verifiers identify the same limitation. The completed result is the `_retry` run; the interrupted first directory contains only staged inputs. Rubric generation used 13,768 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 21,988 more scoring tokens (15.6%).

Artifacts: [rubric](rubrics/browser_task_047-regulatory-api-search-20260909T100115Z.json) · [comparison](results/browser_task_047-regulatory-api-search-20260909T100115Z/20260914T_task047_data_new_retry/comparison.md) · [audit](results/browser_task_047-regulatory-api-search-20260909T100115Z/20260914T_task047_data_new_retry/evidence_error_audit/criterion_audit.json)

---

## Task 48 — Corporate filing filtering

Task ID: `browser_task_048-corporate-filing-filtering-20260909T081902Z`  
Run: `20260914T_task048_data_new`  
Frozen rubric: 6 criteria, 20 points  
Rubric SHA-256: `c8197d17535a38a70b94467043e3b15de71f9f6afc6ce6cacf16ebc253dfbecb`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 5/20 (25.0%) | 6/20 (30.0%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 12 / 0 | 14 / 0 |
| Scoring tokens | 81,951 | 85,384 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Tesco filing page | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Apply Accounts filter | Source confirmation absent / correctly identified | Source confirmation absent / correctly identified | 0/4 / 1/4 | BOTH_CAUGHT |
| Newest account filing 1 | Absent / correctly identified | Absent / correctly identified | 0/3 / 0/3 | BOTH_CAUGHT |
| Newest account filing 2 | Absent / correctly identified | Absent / correctly identified | 0/3 / 0/3 | BOTH_CAUGHT |
| Newest account filing 3 | Absent / correctly identified | Absent / correctly identified | 0/3 / 0/3 | BOTH_CAUGHT |
| Constraints and stopping | Yes / Yes | Yes / Yes | 2/4 / 2/4 | BOTH_CAUGHT |

The raw sources end at the company header and preserve neither filter state nor filing rows. DOM's extra point comes from the shared click action, not extra DOM evidence. Rubric generation used 13,262 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 3,433 more scoring tokens (4.2%).

Artifacts: [rubric](rubrics/browser_task_048-corporate-filing-filtering-20260909T081902Z.json) · [comparison](results/browser_task_048-corporate-filing-filtering-20260909T081902Z/20260914T_task048_data_new/comparison.md) · [audit](results/browser_task_048-corporate-filing-filtering-20260909T081902Z/20260914T_task048_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 49 — Economic time-series extraction

Task ID: `browser_task_049-economic-time-series-extraction-20260909T081927Z`  
Run: `20260914T_task049_data_new`  
Frozen rubric: 5 criteria, 15 points  
Rubric SHA-256: `e7d920165717bb854ffc6669291fce77cdb6a22a09c2c21c07c0bf59a111708c`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 10/15 (66.7%) | 11/15 (73.3%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 16 / 0 | 33 / 0 |
| Scoring tokens | 103,009 | 181,674 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access FRED UNRATE | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Correct UNRATE series | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Exact metadata wording | Exact visual punctuation / Yes | Extra-space normalization; exact form absent / No | 3/4 / 4/4 | DOM_EVIDENCE_MISSING |
| Three latest observations | Only one visible / correctly limited | Only one explicit / correctly limited | 2/5 / 2/5 | BOTH_CAUGHT |
| Constraints and stopping | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

The screenshot preserves the displayed punctuation/layout, while DOM serializes `Percent , Seasonally Adjusted`; the DOM scorer therefore treats the answer's normalized spacing as exact. Both sources show only the August 2026 observation. Rubric generation used 12,464 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 78,665 more scoring tokens (76.4%).

Artifacts: [rubric](rubrics/browser_task_049-economic-time-series-extraction-20260909T081927Z.json) · [comparison](results/browser_task_049-economic-time-series-extraction-20260909T081927Z/20260914T_task049_data_new/comparison.md) · [audit](results/browser_task_049-economic-time-series-extraction-20260909T081927Z/20260914T_task049_data_new/evidence_error_audit/criterion_audit.json)

---

## Task 50 — International data comparison

Task ID: `browser_task_050-international-data-comparison-20260909T082032Z`  
Run: `20260914T_task050_data_new`  
Frozen rubric: 7 criteria, 16 points  
Rubric SHA-256: `377507b06bf488f2fc4bdd475a2237f2433f27381fb1757339a5f7a3b9633638`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 3/16 (18.8%) | 4/16 (25.0%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 20 / 0 | 48 / 0 |
| Scoring tokens | 145,506 | 239,584 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Official World Bank API | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Latest common year | All three 2025 values visible / Yes | India/Nigeria omitted / correctly unavailable | 0/4 / 0/4 | DOM_EVIDENCE_MISSING |
| Exact India value | Yes / Yes | Absent / correctly unavailable | 0/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Exact Brazil value | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Exact Nigeria value | Yes / Yes | Absent / correctly unavailable | 0/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Rank three countries | Inputs visible / Yes | India/Nigeria omitted / correctly unavailable | 0/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Stopping condition | Data availability visible / Yes | Required values omitted / treated as unavailable | 0/1 / 1/1 | DOM_EVIDENCE_MISSING |

`screenshot0.png` contains complete 2020–2025 records for all three countries. Every DOM state is the same fixed 790-byte prefix ending during Brazil 2024, before India and Nigeria. This source truncation explains why the DOM verifier accepts the agent's unavailability claim. Rubric generation used 14,067 tokens across 2 separate calls; scoring generated no rubric calls. DOM used 94,078 more scoring tokens (64.7%).

Artifacts: [rubric](rubrics/browser_task_050-international-data-comparison-20260909T082032Z.json) · [comparison](results/browser_task_050-international-data-comparison-20260909T082032Z/20260914T_task050_data_new/comparison.md) · [audit](results/browser_task_050-international-data-comparison-20260909T082032Z/20260914T_task050_data_new/evidence_error_audit/criterion_audit.json)

---

## Tasks 41–50 evidence-error summary

- Criteria audited: **58**
- BOTH_CAUGHT: **48**
- SCREENSHOT_EVIDENCE_MISSING: **3**
- DOM_EVIDENCE_MISSING: **6**
- DOM_MISSED_SCREENSHOT_CAUGHT: **1**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **1**
- Screenshot scoring tokens: **1,108,153**
- DOM scoring tokens: **1,531,515**

The second source audit reconfirmed every non-`BOTH_CAUGHT` row against the raw inputs. Screenshot source loss was **3/58 (5.2%)** and DOM source loss was **6/58 (10.3%)**. Separately, the DOM verifier missed one criterion despite the relevant DOM sentence being present.

## Task 51 — Cultural object metadata

Task ID: `browser_task_051-cultural-object-metadata-20260909T082146Z`  
Run: `20260914T_task051_data_new`  
Frozen rubric: 8 criteria, 18 points  
Rubric SHA-256: `5a2c65783a6ed51812d8b45896ecebb899378a1aeb5f24f624b632a401658fbd`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/18 (66.7%) | 16/18 (88.9%) |
| Rubric / outcome | Fail / Fail | Pass / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 32 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 75,588 | 8,935 | 1,920 | 84,523 |
| DOM model | 110,865 | 18,327 | 2,816 | 129,192 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 13,675 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Exact Europeana record | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Title | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Creation date | No / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Providing institution | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Type of item | Yes / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Rights statement | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Identifier | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

**Evidence-error result:** screenshot source loss **1/8**; DOM source loss **0/8**; screenshot-verifier miss **1/8**; DOM-verifier miss **0/8**.

**Summary:** DOM preserved the hidden media creation date. The screenshot visibly showed `painting ; Art of painting`, but its verifier did not use it, creating one confirmed screenshot-verifier miss.

### Artifacts

- [Frozen rubric](rubrics/browser_task_051-cultural-object-metadata-20260909T082146Z.json)
- [Comparison report](results/browser_task_051-cultural-object-metadata-20260909T082146Z/20260914T_task051_data_new/comparison.md)
- [Offline evidence audit](results/browser_task_051-cultural-object-metadata-20260909T082146Z/20260914T_task051_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 52 — Museum object metadata

Task ID: `browser_task_052-museum-object-metadata-20260909T082214Z`  
Run: `20260914T_task052_data_new`  
Frozen rubric: 8 criteria, 22 points  
Rubric SHA-256: `c02904ee56b52f562119b176de2bac1fc28485b26acb5f9b7abc0bc96bd4a09e`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 22/22 (100%) | 21/22 (95.5%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 3 / 4 | 3 / 4 |
| LLM calls / retries | 16 / 0 | 35 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 95,407 | 9,201 | 1,728 | 104,608 |
| DOM model | 153,275 | 19,527 | 1,728 | 172,802 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 13,363 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Exact object record | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Object name | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Museum | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |
| Mission month and year | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Materials | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Dimensions | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Inventory number | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Evidence-error result:** no asymmetric source loss and no confirmed verifier evidence miss. The one-point difference on the museum criterion is scoring strictness about the added parenthetical, not missing source evidence.

---

## Task 53 — Book edition resolution

Task ID: `browser_task_053-book-edition-resolution-20260909T082309Z`  
Run: `20260914T_task053_data_new`  
Frozen rubric: 8 criteria, 13 points  
Rubric SHA-256: `e15710db7702bbbb56d6f2791c1fbc501b338de2f93ebe1f777dd4dc0b9e8735`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 9/13 (69.2%) | 13/13 (100%) |
| Rubric / outcome | Fail / Fail | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 27 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 69,454 | 7,915 | 1,920 | 77,369 |
| DOM model | 115,127 | 14,610 | 2,688 | 129,737 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 13,266 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Resolve the specified ISBN to the edition | No / No | Yes / Yes | 1/3 / 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Title | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Author | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Publish date | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Publisher | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Language | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Page count | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| ISBN-13 | No / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |

**Evidence-error result:** screenshot source loss **2/8**; DOM source loss **0/8**; no confirmed verifier misses.

**Summary:** The screenshots showed the edition metadata but not the ISBN tying it to the requested identifier; DOM explicitly preserved that relationship.

---

## Task 54 — Ebook format inspection

Task ID: `browser_task_054-ebook-format-inspection-20260909T082342Z`  
Run: `20260914T_task054_data_new`  
Frozen rubric: 9 criteria, 20 points  
Rubric SHA-256: `57a93ea7329943cb745b1d9a93d4314261802441f146263f525ee38ef06f7cf3`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 10/20 (50%) | 14/20 (70%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 28 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 81,712 | 10,408 | 2,240 | 92,120 |
| DOM model | 122,920 | 18,818 | 2,304 | 141,738 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 14,599 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Gutenberg page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Author | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Release date | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Last updated | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Language | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| EPUB3 availability | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Plain Text availability | No / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Download HTML zip availability | No / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Evidence-error result:** screenshot source loss **2/9**; DOM source loss **0/9**; no confirmed verifier misses.

---

## Task 55 — Archive item metadata

Task ID: `browser_task_055-archive-item-metadata-20260909T082419Z`  
Run: `20260914T_task055_data_new`  
Frozen rubric: 10 criteria, 21 points  
Rubric SHA-256: `eef1854613f6306024c699a31af39fe9e4a073bd967c6ebb96affd9f8e80b25d`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6.5/21 (31.0%) | 14/21 (66.7%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 18 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 81,282 | 10,492 | 2,752 | 91,774 |
| DOM model | 94,490 | 14,271 | 1,920 | 108,761 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 14,503 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Specified Internet Archive item | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Publication year | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Publisher | No / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Language | No / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| All displayed topics | No / No | Yes / Yes | 0/4 / 4/4 | SCREENSHOT_EVIDENCE_MISSING |
| EPUB availability | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| FULL TEXT availability | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| B/W PDF availability | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Constraints | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Stop after requested information | Yes / Yes | Yes / Yes | 0.5/1 / 0/1 | BOTH_CAUGHT |

**Evidence-error result:** screenshot source loss **3/10**; DOM source loss **0/10**; no confirmed verifier misses. The final half-point difference is scoring severity, not evidence loss.

---

## Task 56 — Biomedical literature filtering

Task ID: `browser_task_056-biomedical-literature-filtering-20260909T082457Z`  
Run: `20260914T_task056_data_new`  
Frozen rubric: 7 criteria, 20 points  
Rubric SHA-256: `83c4e2c84cb3b2f4835b4a922e0786ea608b99630dde345ce70b66463ede74ef`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 20/20 (100%) | 14/20 (70%) |
| Rubric / outcome | Pass / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 16 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 75,006 | 7,513 | 1,280 | 82,519 |
| DOM model | 77,321 | 11,682 | 1,408 | 89,003 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 13,593 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Exact PubMed title query | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Apply filters or document blocker | Blocker visible / correctly applied | Blocker explicit / not applied to rubric | 4/4 / 0/4 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Sort or document blocker | Blocker visible / correctly applied | Blocker explicit / not applied to rubric | 2/2 / 0/2 | DOM_MISSED_SCREENSHOT_CAUGHT |
| First result or blocker | Blocker visible / Yes | Blocker explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Second result or blocker | Blocker visible / Yes | Blocker explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Third result or blocker | Blocker visible / Yes | Blocker explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop without fabricated results | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Evidence-error result:** no asymmetric source loss; DOM-verifier misses **2/7**. Both inputs contained the same reCAPTCHA blocker, but the DOM scorer inconsistently failed to apply the rubric's blocker accommodation to the filters and sort criteria.

---

## Task 57 — Clinical trial filtering

Task ID: `browser_task_057-clinical-trial-filtering-20260909T082524Z`  
Run: `20260914T_task057_data_new`  
Frozen rubric: 6 criteria, 20 points  
Rubric SHA-256: `1ee0926b0edcdcc789f7b4f26568b5f9d84824be172b8387c267c7bef3072441`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 4/20 (20%) | 6/20 (30%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 53 / 54 | 53 / 54 |
| LLM calls / retries | 79 / 0 | 82 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 412,186 | 23,493 | 2,880 | 435,679 |
| DOM model | 541,237 | 26,081 | 2,304 | 567,318 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 13,591 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Search and filters | Partially present / Yes | Partially present / Yes | 2/4 / 2/4 | BOTH_CAUGHT |
| Newest-first sort | No final visible confirmation / No | URL parameter explicit / Yes | 0/3 / 2/3 | SCREENSHOT_EVIDENCE_MISSING |
| First result | Required evidence incomplete / Yes | Required evidence incomplete / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Second result | Required evidence incomplete / Yes | Required evidence incomplete / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Third result | Required evidence incomplete / Yes | Required evidence incomplete / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 2/4 / 2/4 | BOTH_CAUGHT |

**Evidence-error result:** screenshot source loss **1/6**; DOM source loss **0/6**; no confirmed verifier misses.

---

## Task 58 — Food product nutrition lookup

Task ID: `browser_task_058-food-product-nutrition-lookup-20260909T094500Z`  
Run: `20260914T_task058_data_new`  
Frozen rubric: 8 criteria, 20 points  
Rubric SHA-256: `ae2b0f4ffaaeffc8722627003c7d60317a3aa3d5479d92f2c544b84e631281ac`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 7/20 (35%) | 14/20 (70%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 16 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 81,479 | 9,983 | 2,112 | 91,462 |
| DOM model | 87,047 | 12,399 | 2,048 | 99,446 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 14,282 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Exact barcode record | Barcode absent / No | Barcode explicit / Yes | 3/3 / 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Product name and barcode | Name only / partial | Both explicit / Yes | 1/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Nutri-Score | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| NOVA classification and marker count | Classification only / partial | Both explicit / Yes | 1/3 / 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Energy per 100 g | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Sugars per 100 g | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Complete English ingredients | No / correctly scored unmet | No / incorrectly awarded full credit | 0/4 / 4/4 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 0/1 / 0/1 | BOTH_CAUGHT |

**Evidence-error result:** screenshot source loss **3/8**; DOM source loss **0/8**; DOM-verifier miss **1/8**.

**Summary:** DOM recovered the barcode and NOVA marker count hidden from the screenshots. Its four-point ingredients award was not source recovery: both modalities lacked the ingredients list, and the DOM scorer incorrectly treated acknowledging unavailability as criterion completion.

---

## Task 59 — Software product requirements

Task ID: `browser_task_059-software-product-requirements-20260909T083843Z`  
Run: `20260914T_task059_data_new`  
Frozen rubric: 5 criteria, 17 points  
Rubric SHA-256: `7435c18812ab17285e1090f30e18253e9571625c88d16876d37126706fdf9d97`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/17 (76.5%) | 12/17 (70.6%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 6 / 7 | 6 / 7 |
| LLM calls / retries | 22 / 0 | 33 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 122,303 | 12,167 | 2,368 | 134,470 |
| DOM model | 184,298 | 18,755 | 2,624 | 203,053 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 13,093 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Steam product page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Release date, developer, publisher | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Complete aggregate reviews summary | Percentage absent / correctly limited | Percentage explicit / correctly found omission | 1/3 / 1/3 | SCREENSHOT_EVIDENCE_MISSING |
| OS headings and minimum storage | Linux storage absent / correctly partial | Linux storage absent / correctly partial | 5/7 / 4/7 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Evidence-error result:** screenshot source loss **1/5**; DOM source loss **0/5**; no confirmed verifier misses. The DOM contained the 98% accessible-text detail, while the screenshot showed sentiment and counts but not the percentage.

---

## Task 60 — Discography chronology

Task ID: `browser_task_060-discography-chronology-20260909T084002Z`  
Run: `20260914T_task060_data_new`  
Frozen rubric: 6 criteria, 18 points  
Rubric SHA-256: `cd27cd3e128211e168513b2ec40fd1ad5174ff28626caad1b4176c6432d59dcd`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 5/18 (27.8%) | 4.5/18 (25.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 14 / 0 |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 78,264 | 8,834 | 1,984 | 87,098 |
| DOM model | 96,371 | 12,050 | 2,496 | 108,421 |

*Reasoning tokens are included within completion tokens.* Rubric generation was separate: 14,094 tokens; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct MusicBrainz artist scope | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| First three album release groups | Yes / Yes | Yes / Yes | 1/4 / 0/4 | BOTH_CAUGHT |
| First entry page and date | Partially present / Yes | Partially present / Yes | 1/3 / 1.5/3 | BOTH_CAUGHT |
| Second entry page and date | Incomplete / correctly rejected | Incomplete / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Third entry page and date | Incomplete / correctly rejected | Incomplete / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Stop after requested report | No / No | No / No | 0/2 / 0/2 | BOTH_CAUGHT |

**Evidence-error result:** no asymmetric source loss and no confirmed verifier miss. The half-point score difference is ordinary scoring variance over the same incomplete evidence.

---

## Task 61 — Npm Package Metadata

Task ID: `browser_task_061-npm-package-metadata-20260909T084033Z`  
Run: `20260912T_task061_data_new`  
Frozen rubric: 8 criteria, 14 points  
Rubric SHA-256: `51d85ccf1ea752a69f80236d568acd7c68dbea30f14b67afb334ca03e1873afe`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/14 (100.0%) | 9/14 (64.3%) |
| Rubric / outcome | Pass / Pass | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 27 / 0 |
| Duration | 69.115 s | 140.059 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 71,446 | 7,959 | 1,920 | 79,405 |
| DOM model | 98,633 | 18,848 | 2,048 | 117,481 |

*Reasoning tokens are included within completion tokens.* DOM used 38,076 more scoring tokens (+48.0%). Rubric generation was separate: 13,200 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use official npm Registry response at specified URL | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record package name | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Record latest version | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record license | Yes / Yes | No / No | 1/1 / 1/1 | DOM_EVIDENCE_MISSING |
| Record Node.js engine requirement from engines.node | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Record unpacked size in bytes from dist.unpackedSize | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Record file count from dist.fileCount | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Respect constraints and stopping condition | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **5**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **3**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Screenshot preserved all requested npm values. DOM clipped out license, engines.node, and dist.unpackedSize, causing three DOM source-evidence gaps.

### Artifacts

- [Frozen rubric](rubrics/browser_task_061-npm-package-metadata-20260909T084033Z.json)
- [Comparison report](results/browser_task_061-npm-package-metadata-20260909T084033Z/20260912T_task061_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_061-npm-package-metadata-20260909T084033Z/20260912T_task061_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_061-npm-package-metadata-20260909T084033Z/20260912T_task061_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_061-npm-package-metadata-20260909T084033Z/20260912T_task061_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 62 — Rust Crate Metadata

Task ID: `browser_task_062-rust-crate-metadata-20260909T084058Z`  
Run: `20260912T_task062_data_new`  
Frozen rubric: 10 criteria, 22 points  
Rubric SHA-256: `2139b52faa8bdae9dcac138b145be3103e9afb0237adea7d35a65b5878477ecd`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 22/22 (100.0%) | 22/22 (100.0%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 2 / 3 | 2 / 3 |
| LLM calls / retries | 14 / 0 | 28 / 0 |
| Duration | 71.034 s | 134.411 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 83,337 | 8,517 | 1,984 | 91,854 |
| DOM model | 129,025 | 18,418 | 3,072 | 147,443 |

*Reasoning tokens are included within completion tokens.* DOM used 55,589 more scoring tokens (+60.5%). Rubric generation was separate: 13,870 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use Serde crate landing page on crates.io | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report displayed latest version | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report displayed release-date wording | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report minimum Rust version | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report license | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report package size with exact units | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report repository link/value | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report all-time download count (Downloads all time) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report number of published versions | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Respect constraints and stopping condition | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **10**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Both modalities preserved and both verifiers recovered every requested crates.io field.

### Artifacts

- [Frozen rubric](rubrics/browser_task_062-rust-crate-metadata-20260909T084058Z.json)
- [Comparison report](results/browser_task_062-rust-crate-metadata-20260909T084058Z/20260912T_task062_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_062-rust-crate-metadata-20260909T084058Z/20260912T_task062_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_062-rust-crate-metadata-20260909T084058Z/20260912T_task062_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_062-rust-crate-metadata-20260909T084058Z/20260912T_task062_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 63 — Protein Structure Inspection

Task ID: `browser_task_063-protein-structure-inspection-20260909T084134Z`  
Run: `20260912T_task063_data_new`  
Frozen rubric: 9 criteria, 23 points  
Rubric SHA-256: `2b6d742bc4854ebed327a519c46a92c0e11d5a011131e16c97c5839cabd5f8ab`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/23 (65.2%) | 23/23 (100.0%) |
| Rubric / outcome | Fail / Fail | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 29 / 0 |
| Duration | 91.030 s | 126.336 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 76,024 | 10,322 | 3,328 | 86,346 |
| DOM model | 139,322 | 17,215 | 2,432 | 156,537 |

*Reasoning tokens are included within completion tokens.* DOM used 70,191 more scoring tokens (+81.3%). Rubric generation was separate: 14,223 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use the RCSB PDB 1TUP Structure Summary page as the source (or report access failure) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report complete structure title | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report released date exactly as displayed | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report experimental method | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report resolution with units exactly (if displayed) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report protein molecule name | No / No | Yes / Yes | 0/3 / 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Report protein source organism (exclude DNA rows with N/A) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| List every unique ligand ID displayed (deduplicated) | No / No | Yes / Yes | 0/5 / 5/5 | SCREENSHOT_EVIDENCE_MISSING |
| Stop after recording all requested fields | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **7**
- SCREENSHOT_EVIDENCE_MISSING: **2**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** The protein molecule name and ZN ligand were below/outside the captured screenshots but explicit in DOM, producing two screenshot source-evidence gaps.

### Artifacts

- [Frozen rubric](rubrics/browser_task_063-protein-structure-inspection-20260909T084134Z.json)
- [Comparison report](results/browser_task_063-protein-structure-inspection-20260909T084134Z/20260912T_task063_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_063-protein-structure-inspection-20260909T084134Z/20260912T_task063_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_063-protein-structure-inspection-20260909T084134Z/20260912T_task063_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_063-protein-structure-inspection-20260909T084134Z/20260912T_task063_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 64 — Legislation Structure Inspection

Task ID: `browser_task_064-legislation-structure-inspection-20260909T084207Z`  
Run: `20260912T_task064_data_new`  
Frozen rubric: 6 criteria, 20 points  
Rubric SHA-256: `29761b5dc27ac06d69d581fbc838bb739d73b4f0da27ce219174f8ebc715e525`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/20 (70.0%) | 13/20 (65.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 3 / 4 | 3 / 4 |
| LLM calls / retries | 16 / 0 | 21 / 0 |
| Duration | 81.135 s | 117.776 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 93,681 | 11,086 | 3,520 | 104,767 |
| DOM model | 115,937 | 16,534 | 4,288 | 132,471 |

*Reasoning tokens are included within completion tokens.* DOM used 27,704 more scoring tokens (+26.4%). Rubric generation was separate: 13,349 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access legislation.gov.uk and reach Data Protection Act 2018 in Original (As enacted) Introductory Text (or clearly report blocker) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record chapter number exactly as displayed (as enacted) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record complete long title exactly as displayed (as enacted) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record Royal Assent date exactly as displayed (as enacted) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Count top-level Parts in as-enacted table of contents (Parts only, exclude nested Parts in Schedules) | Yes / Yes | Yes / Yes | 2/4 / 1/4 | BOTH_CAUGHT |
| Count top-level Schedules in as-enacted table of contents (each counted once) | Yes / Yes | Yes / Yes | 0/4 / 0/4 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **6**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Both modes had the same criterion-relevant evidence. The one-point difference on the Parts count is scoring severity, not evidence loss.

### Artifacts

- [Frozen rubric](rubrics/browser_task_064-legislation-structure-inspection-20260909T084207Z.json)
- [Comparison report](results/browser_task_064-legislation-structure-inspection-20260909T084207Z/20260912T_task064_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_064-legislation-structure-inspection-20260909T084207Z/20260912T_task064_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_064-legislation-structure-inspection-20260909T084207Z/20260912T_task064_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_064-legislation-structure-inspection-20260909T084207Z/20260912T_task064_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 65 — Public Transport Interchange Inspection

Task ID: `browser_task_065-public-transport-interchange-inspection-20260909T084306Z`  
Run: `20260912T_task065_data_new`  
Frozen rubric: 8 criteria, 23 points  
Rubric SHA-256: `543008185397c93552f530d9f11bfcefcbae78868854f88a68ac4f0697038ac0`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 4/23 (17.4%) | 2/23 (8.7%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 38 / 39 | 38 / 39 |
| LLM calls / retries | 60 / 0 | 84 / 0 |
| Duration | 98.243 s | 143.896 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 295,496 | 19,583 | 2,240 | 315,079 |
| DOM model | 342,232 | 32,375 | 1,664 | 374,607 |

*Reasoning tokens are included within completion tokens.* DOM used 59,528 more scoring tokens (+18.9%). Rubric generation was separate: 13,688 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Retrieve/use the official TfL StopPoint response for HUBKGX (or report inability to access it) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report StopPoint ID | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Report common name | Yes / Yes | Yes / Yes | 1/2 / 0/2 | BOTH_CAUGHT |
| Report latitude and longitude | Yes / Yes | Yes / Yes | 1/3 / 0/3 | BOTH_CAUGHT |
| Report every top-level transport mode | Yes / Yes | Yes / Yes | 0/4 / 0/4 | BOTH_CAUGHT |
| Report Zone value from additionalProperties (key = Zone) | Yes / Yes | Yes / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Report every Tube line identifier from lineModeGroups where modeName = tube | Yes / Yes | Yes / Yes | 0/5 / 0/5 | BOTH_CAUGHT |
| Stopping condition satisfied (no extra fields beyond requested set) | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **8**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Neither modality exposed the required top-level TfL fields sufficiently; both verifiers caught the incomplete extraction. The two-point difference is scoring severity.

### Artifacts

- [Frozen rubric](rubrics/browser_task_065-public-transport-interchange-inspection-20260909T084306Z.json)
- [Comparison report](results/browser_task_065-public-transport-interchange-inspection-20260909T084306Z/20260912T_task065_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_065-public-transport-interchange-inspection-20260909T084306Z/20260912T_task065_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_065-public-transport-interchange-inspection-20260909T084306Z/20260912T_task065_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_065-public-transport-interchange-inspection-20260909T084306Z/20260912T_task065_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 66 — Mathematical Sequence Reference

Task ID: `browser_task_066-mathematical-sequence-reference-20260909T085130Z`  
Run: `20260912T_task066_data_new`  
Frozen rubric: 6 criteria, 16 points  
Rubric SHA-256: `968c547760de5254b62f0c731bf1ac922008b64893841d0bd4bc9c4da5c8b24c`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13.5/16 (84.4%) | 12/16 (75.0%) |
| Rubric / outcome | Pass / Fail | Fail / Fail |
| Actions / states | 4 / 5 | 4 / 5 |
| LLM calls / retries | 18 / 0 | 28 / 0 |
| Duration | 73.487 s | 151.344 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 108,790 | 11,269 | 2,304 | 120,059 |
| DOM model | 133,138 | 18,538 | 1,792 | 151,676 |

*Reasoning tokens are included within completion tokens.* DOM used 31,617 more scoring tokens (+26.3%). Rubric generation was separate: 13,126 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use MathWorld Fibonacci Number page as source | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record displayed Fibonacci recurrence (exact notation) | Yes / Yes | No / No | 3/3 / 1/3 | DOM_EVIDENCE_MISSING |
| Record initial conditions (exact notation) | Yes / Yes | No / No | 1/3 / 1/3 | DOM_EVIDENCE_MISSING |
| Report first eight positive-index Fibonacci numbers (F1–F8 only) | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Report linked OEIS identifier (exact as displayed) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Respect stopping condition and scope constraints | Yes / Yes | Yes / Yes | 1.5/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **4**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **2**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** The recurrence and initial-condition formulas were visible pixels, but the DOM text dropped the rendered mathematical notation, producing two DOM source-evidence gaps.

### Artifacts

- [Frozen rubric](rubrics/browser_task_066-mathematical-sequence-reference-20260909T085130Z.json)
- [Comparison report](results/browser_task_066-mathematical-sequence-reference-20260909T085130Z/20260912T_task066_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_066-mathematical-sequence-reference-20260909T085130Z/20260912T_task066_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_066-mathematical-sequence-reference-20260909T085130Z/20260912T_task066_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_066-mathematical-sequence-reference-20260909T085130Z/20260912T_task066_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 67 — Chemical Reference Data

Task ID: `browser_task_067-chemical-reference-data-20260909T085226Z`  
Run: `20260912T_task067_data_new`  
Frozen rubric: 4 criteria, 15 points  
Rubric SHA-256: `1cf91356f00e3863c1d3520912f1db9c10bd6dbb0ff4e94e142d2f02e4d2392e`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 7/15 (46.7%) | 8/15 (53.3%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 17 / 0 |
| Duration | 77.761 s | 97.108 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 67,102 | 7,736 | 2,112 | 74,838 |
| DOM model | 75,707 | 10,970 | 2,752 | 86,677 |

*Reasoning tokens are included within completion tokens.* DOM used 11,839 more scoring tokens (+15.8%). Rubric generation was separate: 12,674 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access the specified NIST Chemistry WebBook record for water (ID=C7732185) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report identity fields from the record: formula, molecular weight, IUPAC InChIKey, and CAS Registry Number | Yes / Yes | Yes / Yes | 4/4 / 3/4 | BOTH_CAUGHT |
| Report CODATA experimental gas-phase standard enthalpy of formation (with unit and reference) | Yes / Yes | Yes / Yes | 0/6 / 1/6 | BOTH_CAUGHT |
| Preserve exact transcription as feasible and stop after required fields | Yes / Yes | Yes / Yes | 0/2 / 1/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **4**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Both modalities preserved the same identity fields and both lacked the requested CODATA row. The one-point difference is scoring severity.

### Artifacts

- [Frozen rubric](rubrics/browser_task_067-chemical-reference-data-20260909T085226Z.json)
- [Comparison report](results/browser_task_067-chemical-reference-data-20260909T085226Z/20260912T_task067_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_067-chemical-reference-data-20260909T085226Z/20260912T_task067_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_067-chemical-reference-data-20260909T085226Z/20260912T_task067_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_067-chemical-reference-data-20260909T085226Z/20260912T_task067_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 68 — Vehicle Vin Decoding

Task ID: `browser_task_068-vehicle-vin-decoding-20260909T085259Z`  
Run: `20260912T_task068_data_new`  
Frozen rubric: 12 criteria, 16 points  
Rubric SHA-256: `0b31852b1b0027ad6fd0446aa26d8eab82e58cefa4dc503e87d599200e64de25`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/16 (81.2%) | 5/16 (31.2%) |
| Rubric / outcome | Pass / Fail | Fail / Fail |
| Actions / states | 6 / 7 | 6 / 7 |
| LLM calls / retries | 22 / 0 | 51 / 0 |
| Duration | 103.960 s | 173.158 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 137,117 | 15,322 | 3,584 | 152,439 |
| DOM model | 210,569 | 41,671 | 2,048 | 252,240 |

*Reasoning tokens are included within completion tokens.* DOM used 99,801 more scoring tokens (+65.5%). Rubric generation was separate: 14,599 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use the official NHTSA vPIC DecodeVinValues response for the specified VIN | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record Make from Results object | Yes / Yes | No / No | 1/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record Model from Results object | Yes / Yes | No / No | 1/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record ModelYear from Results object | Yes / Yes | No / No | 1/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record BodyClass from Results object | Yes / Yes | No / No | 0/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record EngineCylinders from Results object | Yes / Yes | No / No | 0/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record EngineHP from Results object | Yes / Yes | No / No | 0/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record PlantCity from Results object | Yes / Yes | No / No | 1/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record PlantState from Results object | Yes / Yes | No / No | 1/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record PlantCountry from Results object | Yes / Yes | No / No | 1/1 / 0/1 | DOM_EVIDENCE_MISSING |
| Record ErrorText exactly as returned | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Stopping condition compliance (stop after recording all requested fields) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **2**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **10**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** The screenshot sequence visibly preserved all ten requested VIN fields. Every DOM state clipped the JSON near AdditionalErrorText before those fields, producing ten DOM source-evidence gaps.

### Artifacts

- [Frozen rubric](rubrics/browser_task_068-vehicle-vin-decoding-20260909T085259Z.json)
- [Comparison report](results/browser_task_068-vehicle-vin-decoding-20260909T085259Z/20260912T_task068_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_068-vehicle-vin-decoding-20260909T085259Z/20260912T_task068_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_068-vehicle-vin-decoding-20260909T085259Z/20260912T_task068_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_068-vehicle-vin-decoding-20260909T085259Z/20260912T_task068_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 69 — Ip Network Registration

Task ID: `browser_task_069-ip-network-registration-20260909T085410Z`  
Run: `20260912T_task069_data_new`  
Frozen rubric: 9 criteria, 22 points  
Rubric SHA-256: `2e9f94d2e3c2b0d218506eacceb5a1cdbaf8c8feae59e06a46df40b539ee5e99`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 2/22 (9.1%) | 2/22 (9.1%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 14 / 0 |
| Duration | 85.669 s | 98.227 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 78,486 | 9,447 | 1,792 | 87,933 |
| DOM model | 76,410 | 12,108 | 2,560 | 88,518 |

*Reasoning tokens are included within completion tokens.* DOM used 585 more scoring tokens (+0.7%). Rubric generation was separate: 13,666 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Extract top-level network handle | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Extract top-level network name | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Extract top-level startAddress | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Extract top-level endAddress | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Extract top-level network type | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Extract every top-level network status value | Yes / Yes | Yes / Yes | 0/4 / 0/4 | BOTH_CAUGHT |
| Extract top-level parentHandle | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Extract registrant entity fn from vCard | Yes / Yes | Yes / Yes | 0/4 / 0/4 | BOTH_CAUGHT |
| Use only supplied ARIN RDAP response and stop after recording requested fields | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **9**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Both modalities exposed the same incomplete RDAP view, and both verifiers rejected the unreported requested fields consistently.

### Artifacts

- [Frozen rubric](rubrics/browser_task_069-ip-network-registration-20260909T085410Z.json)
- [Comparison report](results/browser_task_069-ip-network-registration-20260909T085410Z/20260912T_task069_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_069-ip-network-registration-20260909T085410Z/20260912T_task069_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_069-ip-network-registration-20260909T085410Z/20260912T_task069_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_069-ip-network-registration-20260909T085410Z/20260912T_task069_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 70 — Unicode Ideograph Inspection

Task ID: `browser_task_070-unicode-ideograph-inspection-20260909T085438Z`  
Run: `20260912T_task070_data_new`  
Frozen rubric: 10 criteria, 20 points  
Rubric SHA-256: `d0ffe495ad2e47d67d52c42148e989a21aba2a4aa8fd88b63ab4a62c2b792f5e`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/20 (60.0%) | 9/20 (45.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 18 / 0 |
| Duration | 90.621 s | 124.944 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 80,756 | 10,905 | 3,136 | 91,661 |
| DOM model | 103,510 | 18,442 | 3,328 | 121,952 |

*Reasoning tokens are included within completion tokens.* DOM used 30,291 more scoring tokens (+33.0%). Rubric generation was separate: 14,030 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access the Unicode Unihan record for U+4E00 (or clearly report access failure) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Respect task constraints (sole source, exact copying, no extra fields, stop at requested fields) | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |
| Record code-point identity and displayed glyph | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record numeric and encoding fields (decimal, UTF-8, UTF-16) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record total stroke count | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Record definition | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Record Mandarin reading | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Record Japanese On reading | Yes / Yes | Yes / Yes | 1/2 / 0/2 | BOTH_CAUGHT |
| Record Korean reading | Yes / Yes | Yes / Yes | 1/2 / 0/2 | BOTH_CAUGHT |
| Record Vietnamese reading | Yes / Yes | Yes / Yes | 1/2 / 0/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **10**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Both modalities preserved the same visible portion of the Unihan record and lacked the requested lower-page readings. The three-point difference is scoring severity.

### Artifacts

- [Frozen rubric](rubrics/browser_task_070-unicode-ideograph-inspection-20260909T085438Z.json)
- [Comparison report](results/browser_task_070-unicode-ideograph-inspection-20260909T085438Z/20260912T_task070_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_070-unicode-ideograph-inspection-20260909T085438Z/20260912T_task070_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_070-unicode-ideograph-inspection-20260909T085438Z/20260912T_task070_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_070-unicode-ideograph-inspection-20260909T085438Z/20260912T_task070_data_new/evidence_error_audit/evidence_error_report.md)
- [Offline evidence audit](results/browser_task_070-unicode-ideograph-inspection-20260909T085438Z/20260912T_task070_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 71 — Satellite Catalog Inspection

Task ID: `browser_task_071-satellite-catalog-inspection-20260909T085517Z`  
Run: `20260913T_task071_data_new`  
Frozen rubric: 7 criteria, 23 points  
Rubric SHA-256: `549ae13c1406f1148bdbc102555365301e39694363e504bdd26ea03262b5520b`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 23/23 (100.0%) | 23/23 (100.0%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 15 / 0 |
| Duration | 62.574 s | 79.931 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 71,233 | 6,715 | 1,408 | 77,948 |
| DOM model | 69,892 | 9,449 | 1,664 | 79,341 |

*Reasoning tokens are included within completion tokens.* DOM used 1,393 more scoring tokens (+1.8%). Rubric generation was separate: 13,120 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access the CelesTrak SATCAT record for CATNR=25544 (or clearly report access failure) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Use the CelesTrak SATCAT record only (no switching objects/sources; no expanding codes) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report identity fields (name, international designator, NORAD catalog number, object type) | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Report status/ownership fields using raw codes (operational status code, owner code) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report launch fields (launch date and launch-site code) using raw code | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report orbital parameters (period, inclination, apogee, perigee) with exact numbers/units | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Honor stopping condition (stop after recording all requested fields from the displayed record) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **7**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Both representations contained the complete compact SATCAT record, and both verifiers awarded identical full credit.

### Artifacts

- [Frozen rubric](rubrics/browser_task_071-satellite-catalog-inspection-20260909T085517Z.json)
- [Comparison report](results/browser_task_071-satellite-catalog-inspection-20260909T085517Z/20260913T_task071_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_071-satellite-catalog-inspection-20260909T085517Z/20260913T_task071_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_071-satellite-catalog-inspection-20260909T085517Z/20260913T_task071_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_071-satellite-catalog-inspection-20260909T085517Z/20260913T_task071_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 72 — Regional Calendar Comparison

Task ID: `browser_task_072-regional-calendar-comparison-20260909T085558Z`  
Run: `20260913T_task072_data_new`  
Frozen rubric: 6 criteria, 12 points  
Rubric SHA-256: `231a2296aa6a12b6ac225c3ca067a8b4ec03f032f694482c3b3796132483bfa7`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/12 (100.0%) | 2.5/12 (20.8%) |
| Rubric / outcome | Pass / Pass | Fail / Fail |
| Actions / states | 48 / 49 | 48 / 49 |
| LLM calls / retries | 67 / 0 | 79 / 0 |
| Duration | 83.323 s | 103.938 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 310,923 | 16,919 | 2,560 | 327,842 |
| DOM model | 302,482 | 22,354 | 1,920 | 324,836 |

*Reasoning tokens are included within completion tokens.* DOM used 3,006 fewer scoring tokens (−0.9%). Rubric generation was separate: 13,572 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use only the official GOV.UK bank-holidays JSON response at the supplied URL (or clearly report access failure) | Yes / Yes | Yes / Yes | 3/3 / 1.5/3 | BOTH_CAUGHT |
| Scotland 2026 — report '2nd January' date and bunting | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Scotland 2026 — report 'Summer bank holiday' date and bunting | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Scotland 2026 — report 'St Andrew’s Day' date and bunting | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| England and Wales 2026 — report 'Summer bank holiday' date | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Stopping condition adhered to (only required events recorded) | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **2**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **4**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Screenshots captured the requested 2026 events across scrolled frames; every DOM snapshot repeated a clipped 2019 prefix, creating four DOM source gaps.

### Artifacts

- [Frozen rubric](rubrics/browser_task_072-regional-calendar-comparison-20260909T085558Z.json)
- [Comparison report](results/browser_task_072-regional-calendar-comparison-20260909T085558Z/20260913T_task072_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_072-regional-calendar-comparison-20260909T085558Z/20260913T_task072_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_072-regional-calendar-comparison-20260909T085558Z/20260913T_task072_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_072-regional-calendar-comparison-20260909T085558Z/20260913T_task072_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 73 — Pageview Time-Series Analysis

Task ID: `browser_task_073-pageview-time-series-analysis-20260909T090358Z`  
Run: `20260913T_task073_data_new`  
Frozen rubric: 4 criteria, 15 points  
Rubric SHA-256: `d4a151184f452268c309515f8df93743958ec6050655eb59d4badc4a9368eb4f`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 4/15 (26.7%) | 5.5/15 (36.7%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 4 / 5 | 4 / 5 |
| LLM calls / retries | 18 / 0 | 21 / 0 |
| Duration | 74.826 s | 90.930 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 124,998 | 11,569 | 1,408 | 136,567 |
| DOM model | 120,150 | 15,840 | 1,984 | 135,990 |

*Reasoning tokens are included within completion tokens.* DOM used 577 fewer scoring tokens (−0.4%). Rubric generation was separate: 12,829 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Report daily date–viewcount pairs from the supplied API response (or report missing/unavailable data) | Yes / Yes | No / No | 2/6 / 2.5/6 | DOM_EVIDENCE_MISSING |
| Compute and show arithmetic for the total over the reported days | Yes / Yes | No / No | 1/3 / 1/3 | DOM_EVIDENCE_MISSING |
| Identify highest-view date and show maximum-selection logic over the reported days | Yes / Yes | No / No | 1/3 / 1.5/3 | DOM_EVIDENCE_MISSING |
| Adhere to task constraints (source fidelity, timestamp conversion, no re-aggregation) | Yes / Yes | No / No | 0/3 / 0.5/3 | DOM_EVIDENCE_MISSING |

### Evidence-error result

- BOTH_CAUGHT: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **4**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Screenshot3 contained all seven daily records, while every DOM state ended during the fourth record. DOM’s slightly higher score reflects scoring leniency over incomplete evidence, not better source coverage.

### Artifacts

- [Frozen rubric](rubrics/browser_task_073-pageview-time-series-analysis-20260909T090358Z.json)
- [Comparison report](results/browser_task_073-pageview-time-series-analysis-20260909T090358Z/20260913T_task073_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_073-pageview-time-series-analysis-20260909T090358Z/20260913T_task073_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_073-pageview-time-series-analysis-20260909T090358Z/20260913T_task073_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_073-pageview-time-series-analysis-20260909T090358Z/20260913T_task073_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 74 — Occupational Profile Analysis

Task ID: `browser_task_074-occupational-profile-analysis-20260909T090500Z`  
Run: `20260913T_task074_data_new`  
Frozen rubric: 9 criteria, 22 points  
Rubric SHA-256: `dd3422752f1fa816da9a0f682de0c82e2ba8cdb298e19108b5d9486950da0350`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 10/22 (45.5%) | 11/22 (50.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 2 / 3 | 2 / 3 |
| LLM calls / retries | 14 / 0 | 21 / 0 |
| Duration | 79.821 s | 127.853 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 90,408 | 9,591 | 1,792 | 99,999 |
| DOM model | 113,883 | 16,916 | 1,600 | 130,799 |

*Reasoning tokens are included within completion tokens.* DOM used 30,800 more scoring tokens (+30.8%). Rubric generation was separate: 14,069 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use correct O*NET Summary Report profile (15-1252.00 only) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record occupation title and code | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record Bright Outlook status | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record Job Zone title | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Record annual median wage (national Wages & Employment Trends value) | Yes / Yes | Yes / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Record current employment (national Wages & Employment Trends value) | Yes / Yes | Yes / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Record projected-growth wording and rate | Yes / Yes | Yes / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Record projected job openings | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Respect task constraints and stopping condition | Yes / Yes | Yes / Yes | 1/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **9**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Both modalities showed the same reached sections and the same missing wage/employment section. The one-point difference is stopping-criterion severity, not evidence loss.

### Artifacts

- [Frozen rubric](rubrics/browser_task_074-occupational-profile-analysis-20260909T090500Z.json)
- [Comparison report](results/browser_task_074-occupational-profile-analysis-20260909T090500Z/20260913T_task074_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_074-occupational-profile-analysis-20260909T090500Z/20260913T_task074_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_074-occupational-profile-analysis-20260909T090500Z/20260913T_task074_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_074-occupational-profile-analysis-20260909T090500Z/20260913T_task074_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 75 — Collectible Card Rules

Task ID: `browser_task_075-collectible-card-rules-20260909T090552Z`  
Run: `20260913T_task075_data_new`  
Frozen rubric: 6 criteria, 17 points  
Rubric SHA-256: `6f14affeb38c269013e39e45b0490af6aae0f1273b38089a71952b4518441c09`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/17 (82.4%) | 5/17 (29.4%) |
| Rubric / outcome | Pass / Fail | Fail / Fail |
| Actions / states | 6 / 7 | 6 / 7 |
| LLM calls / retries | 21 / 0 | 42 / 0 |
| Duration | 70.109 s | 125.164 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 117,521 | 10,122 | 1,408 | 127,643 |
| DOM model | 154,235 | 24,205 | 2,240 | 178,440 |

*Reasoning tokens are included within completion tokens.* DOM used 50,797 more scoring tokens (+39.8%). Rubric generation was separate: 13,319 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use only the exact-card Scryfall API response at the provided URL | Yes / Yes | Yes / Yes | 3/3 / 2/3 | BOTH_CAUGHT |
| Record card identity fields: name, mana_cost, type_line | Yes / Yes | No / No | 3/3 / 1/3 | DOM_EVIDENCE_MISSING |
| Record complete oracle_text | Yes / Yes | No / No | 0/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Record reserved flag | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Record format legalities: Vintage, Legacy, Commander | Yes / Yes | No / No | 4/4 / 0/4 | DOM_EVIDENCE_MISSING |
| Respect task constraints (no pricing/links; stop after requested fields) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **2**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **4**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Screenshots preserved the card identity, oracle text, reserved flag, and legalities; DOM clipped after early metadata, creating four criterion-level source gaps.

### Artifacts

- [Frozen rubric](rubrics/browser_task_075-collectible-card-rules-20260909T090552Z.json)
- [Comparison report](results/browser_task_075-collectible-card-rules-20260909T090552Z/20260913T_task075_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_075-collectible-card-rules-20260909T090552Z/20260913T_task075_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_075-collectible-card-rules-20260909T090552Z/20260913T_task075_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_075-collectible-card-rules-20260909T090552Z/20260913T_task075_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 76 — DOI Metadata

Task ID: `browser_task_076-doi-metadata-20260909T090704Z`  
Run: `20260913T_task076_data_new`  
Frozen rubric: 7 criteria, 20 points  
Rubric SHA-256: `256cf48db6dc6362d093dcf836d688dbfe7cc5f2c89f278d9c8a5c5b966e3a0b`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 3/20 (15.0%) | 9/20 (45.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 6 / 7 | 6 / 7 |
| LLM calls / retries | 20 / 0 | 75 / 0 |
| Duration | 88.435 s | 174.871 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 116,821 | 11,325 | 1,728 | 128,146 |
| DOM model | 259,650 | 48,106 | 1,600 | 307,756 |

*Reasoning tokens are included within completion tokens.* DOM used 179,610 more scoring tokens (+140.2%). Rubric generation was separate: 13,461 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use only the supplied Crossref response (message object fields) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report work title from message.title | Yes / Yes | No / No | 0/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Report publisher from message.publisher | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Report published date from message.published.date-parts | Yes / Yes | Yes / Yes | 0/3 / 2/3 | BOTH_CAUGHT |
| Report work type from message.type | Yes / Yes | No / No | 0/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Report complete ordered author list from message.author | Yes / Yes | No / No | 0/6 / 2/6 | DOM_EVIDENCE_MISSING |
| Stop after recording the requested fields (stopping condition) | Yes / Yes | Yes / Yes | 0/2 / 1/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **4**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **3**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Screenshots exposed title, type, and author content that DOM clipped before reaching. DOM’s six-point advantage is scoring leniency for omissions, not superior evidence coverage.

### Artifacts

- [Frozen rubric](rubrics/browser_task_076-doi-metadata-20260909T090704Z.json)
- [Comparison report](results/browser_task_076-doi-metadata-20260909T090704Z/20260913T_task076_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_076-doi-metadata-20260909T090704Z/20260913T_task076_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_076-doi-metadata-20260909T090704Z/20260913T_task076_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_076-doi-metadata-20260909T090704Z/20260913T_task076_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 77 — Unavailable

Task 77 was not run because no matching Task 77 folder exists under either `data-new/data-ss/` or `data-new/data-dom/`. No rubric, score, token, or audit values were fabricated.

---

## Task 78 — Cross-Endpoint Game Data

Task ID: `browser_task_078-cross-endpoint-game-data-20260909T094544Z`  
Run: `20260913T_task078_data_new`  
Frozen rubric: 6 criteria, 20 points  
Rubric SHA-256: `fc0553ae76f7d38f74791ed0b8d2518a353fa3a7bbc068449bdc7ffe0bd460e1`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/20 (70.0%) | 5/20 (25.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 70 / 71 | 70 / 71 |
| LLM calls / retries | 90 / 0 | 113 / 0 |
| Duration | 105.044 s | 138.650 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 404,496 | 19,763 | 2,496 | 424,259 |
| DOM model | 452,081 | 25,803 | 1,792 | 477,884 |

*Reasoning tokens are included within completion tokens.* DOM used 53,625 more scoring tokens (+12.6%). Rubric generation was separate: 13,608 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use only the supplied Pikachu PokÃ©mon response and its returned species.url | Yes / Yes | Yes / Yes | 1/3 / 0/3 | BOTH_CAUGHT |
| Report required PokÃ©mon fields (id, raw height, raw weight, base_experience) | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Report all types in slot order using exact API strings | Yes / Yes | No / No | 3/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Compute and report the highest base stat (include ties) from complete stats array | Yes / Yes | No / No | 4/4 / 0/4 | DOM_EVIDENCE_MISSING |
| Open species.url and report species fields (color.name, habitat.name, capture_rate, generation.name) | Yes / Yes | Yes / Yes | 0/4 / 0/4 | BOTH_CAUGHT |
| Stop after recording all requested fields (no extra/unrequested outputs) | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **4**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **2**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Screenshots reached the PokÃ©mon types and stats arrays; DOM repeatedly clipped within early abilities data. Neither modality evidenced a species-endpoint visit.

### Artifacts

- [Frozen rubric](rubrics/browser_task_078-cross-endpoint-game-data-20260909T094544Z.json)
- [Comparison report](results/browser_task_078-cross-endpoint-game-data-20260909T094544Z/20260913T_task078_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_078-cross-endpoint-game-data-20260909T094544Z/20260913T_task078_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_078-cross-endpoint-game-data-20260909T094544Z/20260913T_task078_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_078-cross-endpoint-game-data-20260909T094544Z/20260913T_task078_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 79 — Motor-Race Result Analysis

Task ID: `browser_task_079-motor-race-result-analysis-20260909T090855Z`  
Run: `20260913T_task079_data_new`  
Frozen rubric: 6 criteria, 20 points  
Rubric SHA-256: `ebb9b172975df6aba5a6fdef96a7a5c172e30600f78d7899c84c675fda1f2ce7`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/20 (65.0%) | 5/20 (25.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 3 / 4 | 3 / 4 |
| LLM calls / retries | 16 / 0 | 25 / 0 |
| Duration | 88.888 s | 151.071 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 97,613 | 11,315 | 2,816 | 108,928 |
| DOM model | 105,829 | 21,175 | 3,200 | 127,004 |

*Reasoning tokens are included within completion tokens.* DOM used 18,076 more scoring tokens (+16.6%). Rubric generation was separate: 13,087 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use only the supplied Jolpica/Ergast JSON and correct array selection | Yes / Yes | No / No | 1/3 / 1/3 | DOM_EVIDENCE_MISSING |
| Report race-level fields: raceName, date, circuitName | Yes / Yes | No / No | 3/3 / 2/3 | DOM_EVIDENCE_MISSING |
| Report winner identity: driver and constructor | Yes / Yes | No / No | 3/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Report winner result summary: grid, laps, status | Yes / Yes | No / No | 3/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Report complete FastestLap object with required separation of subfields | Yes / Yes | No / No | 1/6 / 0/6 | DOM_EVIDENCE_MISSING |
| Stopping condition met (no extra races/results beyond requested fields) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **1**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **5**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**

**Summary:** Screenshot2 contained the race date, winner result, and FastestLap object; all DOM states clipped in the Circuit object before those fields.

### Artifacts

- [Frozen rubric](rubrics/browser_task_079-motor-race-result-analysis-20260909T090855Z.json)
- [Comparison report](results/browser_task_079-motor-race-result-analysis-20260909T090855Z/20260913T_task079_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_079-motor-race-result-analysis-20260909T090855Z/20260913T_task079_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_079-motor-race-result-analysis-20260909T090855Z/20260913T_task079_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_079-motor-race-result-analysis-20260909T090855Z/20260913T_task079_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 80 — Protein Record Inspection

Task ID: `browser_task_080-protein-record-inspection-20260909T090935Z`  
Run: `20260913T_task080_data_new`  
Frozen rubric: 8 criteria, 17 points  
Rubric SHA-256: `da6c0c2e585c969c9e8a4722f03ca6e9a3c22ecc5bd5ce27271a367fa424c122`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/17 (88.2%) | 3/17 (17.6%) |
| Rubric / outcome | Pass / Fail | Fail / Fail |
| Actions / states | 0 / 1 | 0 / 1 |
| LLM calls / retries | 10 / 0 | 12 / 0 |
| Duration | 70.486 s | 83.830 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 58,075 | 5,798 | 1,408 | 63,873 |
| DOM model | 63,476 | 7,052 | 1,024 | 70,528 |

*Reasoning tokens are included within completion tokens.* DOM used 6,655 more scoring tokens (+10.4%). Rubric generation was separate: 13,486 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access the UniProtKB entry page for accession P04637 (or determine it is inaccessible) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record entry name | Yes / No | Yes / Yes | 2/2 / 0/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Record recommended protein name | Yes / No | Yes / Yes | 2/2 / 0/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Record primary gene name | Yes / No | Yes / Yes | 2/2 / 0/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Record organism | Yes / No | Yes / Yes | 2/2 / 0/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Record canonical sequence length | Yes / No | Yes / Yes | 2/2 / 0/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Record reviewed status (as displayed) | Yes / No | Yes / Yes | 2/2 / 0/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Stopping condition met (all six fields reported, then stop) | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **2**
- SCREENSHOT_MISSED_DOM_CAUGHT: **6**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**
- Confirmed screenshot-verifier misses: **6**
- Confirmed DOM-verifier misses: **0**

**Summary:** Both sources clearly contained all six UniProt values, but the agent's final answer contained only an API context-window error. The screenshot evidence analysis noticed the omissions and then contradicted itself by awarding full delivery credit for C2–C7 merely because the values were visible. The DOM verifier correctly assigned zero to those six output criteria. These are six confirmed screenshot-verifier evidence-use misses, not source-capture losses.

### Artifacts

- [Frozen rubric](rubrics/browser_task_080-protein-record-inspection-20260909T090935Z.json)
- [Comparison report](results/browser_task_080-protein-record-inspection-20260909T090935Z/20260913T_task080_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_080-protein-record-inspection-20260909T090935Z/20260913T_task080_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_080-protein-record-inspection-20260909T090935Z/20260913T_task080_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_080-protein-record-inspection-20260909T090935Z/20260913T_task080_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 81 — Lexical Entry Inspection

Task ID: `browser_task_081-lexical-entry-inspection-20260909T090959Z`  
Run: `20260913T_task081_data_new`  
Frozen rubric: 6 criteria, 18 points  
Rubric SHA-256: `3e3d33a6f5ea8e4d4e131ac6c0c0240e9d1ffcfcdb84761486dde623915d2793`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 18/18 (100.0%) | 13/18 (72.2%) |
| Rubric / outcome | Pass / Pass | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 24 / 0 |
| Duration | 93.669 s | 161.986 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 70,924 | 9,143 | 3,456 | 80,067 |
| DOM model | 131,247 | 19,441 | 2,880 | 150,688 |

*Reasoning tokens are included within completion tokens.* DOM used 70,621 more scoring tokens (88.2% increase). Rubric generation was separate: 13,335 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use only the English section of the Wiktionary entry | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report the four prose-etymology source-language stages (Middle English back to Arabic) | Yes / Yes | No / No | 4/4 / 1/4 | DOM_EVIDENCE_MISSING |
| Provide the first IPA transcription and the Standard Southern British IPA transcription (distinct) | Yes / Yes | Yes / No | 4/4 / 2/4 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Report UK and US hyphenation | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report noun countability label(s) and plural form | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stopping condition respected (no extra, unrequested content) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **4**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **1**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **1**

**Summary:** The screenshot preserved the prose etymology that DOM omitted. Separately, the DOM verifier misread the preserved Standard Southern British IPA label/value sequence; that is a verifier grounding miss, not source loss.

### Artifacts

- [Frozen rubric](rubrics/browser_task_081-lexical-entry-inspection-20260909T090959Z.json)
- [Comparison report](results/browser_task_081-lexical-entry-inspection-20260909T090959Z/20260913T_task081_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_081-lexical-entry-inspection-20260909T090959Z/20260913T_task081_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_081-lexical-entry-inspection-20260909T090959Z/20260913T_task081_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_081-lexical-entry-inspection-20260909T090959Z/20260913T_task081_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 82 — Chess Game Result Inspection

Task ID: `browser_task_082-chess-game-result-inspection-20260909T091031Z`  
Run: `20260913T_task082_data_new`  
Frozen rubric: 5 criteria, 20 points  
Rubric SHA-256: `2080808bbccbe3444a4d2234275a959221a249014904721553df11db85c833d6`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 20/20 (100.0%) | 19/20 (95.0%) |
| Rubric / outcome | Pass / Pass | Pass / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 14 / 0 |
| Duration | 66.201 s | 81.072 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 67,014 | 6,522 | 1,728 | 73,536 |
| DOM model | 66,345 | 8,285 | 1,344 | 74,630 |

*Reasoning tokens are included within completion tokens.* DOM used 1,094 more scoring tokens (1.5% increase). Rubric generation was separate: 12,973 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access the specified public Lichess game page (Z01xx8LK) only | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record time control, rated/casual status, and speed category as displayed | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record both players' names, ratings, and rating changes (correct association) | Yes / Yes | Yes / No | 5/5 / 4/5 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Record termination/victory statement, winner, and number of moves | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Respect constraints and stopping condition | Yes / Yes | Yes / Yes | 5/5 / 5/5 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **4**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **1**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**

**Summary:** Both modalities contained enough explicit facts to associate Reini with White, but the DOM verifier failed to combine “White is victorious” with “Reini won”; this is a confirmed DOM-verifier miss.

### Artifacts

- [Frozen rubric](rubrics/browser_task_082-chess-game-result-inspection-20260909T091031Z.json)
- [Comparison report](results/browser_task_082-chess-game-result-inspection-20260909T091031Z/20260913T_task082_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_082-chess-game-result-inspection-20260909T091031Z/20260913T_task082_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_082-chess-game-result-inspection-20260909T091031Z/20260913T_task082_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_082-chess-game-result-inspection-20260909T091031Z/20260913T_task082_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 83 — Marine Taxonomy

Task ID: `browser_task_083-marine-taxonomy-20260909T091056Z`  
Run: `20260913T_task083_data_new`  
Frozen rubric: 6 criteria, 16 points  
Rubric SHA-256: `220c4bbaf2708ab9dd1684f51db25d10dabb735d5bfbac6a340dd33641cd8d8e`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/16 (100.0%) | 14/16 (87.5%) |
| Rubric / outcome | Pass / Pass | Pass / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 16 / 0 |
| Duration | 69.667 s | 93.978 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 67,178 | 6,549 | 1,600 | 73,727 |
| DOM model | 77,213 | 9,710 | 2,624 | 86,923 |

*Reasoning tokens are included within completion tokens.* DOM used 13,196 more scoring tokens (17.9% increase). Rubric generation was separate: 13,368 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access the specified WoRMS taxon record (AphiaID 137106) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report identity fields: AphiaID and scientific name with authority (from the main record header) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report taxonomic status from the record (without substituting synonyms) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report genus and family from the Classification section | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report displayed environment states (affirmed vs struck-through) | Yes / Yes | No / No | 3/3 / 1/3 | DOM_EVIDENCE_MISSING |
| Stopping condition: stop after recording requested fields only | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **5**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **0**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **1**

**Summary:** Both verifiers used the available text correctly, but DOM flattened the normal-versus-struck-through Environment styling required by the task.

### Artifacts

- [Frozen rubric](rubrics/browser_task_083-marine-taxonomy-20260909T091056Z.json)
- [Comparison report](results/browser_task_083-marine-taxonomy-20260909T091056Z/20260913T_task083_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_083-marine-taxonomy-20260909T091056Z/20260913T_task083_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_083-marine-taxonomy-20260909T091056Z/20260913T_task083_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_083-marine-taxonomy-20260909T091056Z/20260913T_task083_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 84 — Exoplanet Discovery Record

Task ID: `browser_task_084-exoplanet-discovery-record-20260909T091127Z`  
Run: `20260913T_task084_data_new`  
Frozen rubric: 10 criteria, 14 points  
Rubric SHA-256: `86405cadd21cd92c4b3494960aa9c7d29a6466ae18e9c2484e3a5850e1ba7be8`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/14 (92.9%) | 13/14 (92.9%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 30 / 0 |
| Duration | 90.081 s | 158.059 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 76,404 | 9,433 | 2,752 | 85,837 |
| DOM model | 130,034 | 19,728 | 2,048 | 149,762 |

*Reasoning tokens are included within completion tokens.* DOM used 63,925 more scoring tokens (74.5% increase). Rubric generation was separate: 13,802 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access the NASA Exoplanet Archive overview page and locate the 'Architecture & Discovery Information' block | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Use only the Architecture & Discovery Information block (single row) and stop after reporting the eight requested fields | Yes / Yes | Yes / Yes | 2/2 / 1.5/2 | BOTH_CAUGHT |
| Report stellar-host name | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Report planet name | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Report value under Orbital Separation | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report value under Planet Size | Yes / Yes | Yes / Yes | 1/2 / 1.5/2 | BOTH_CAUGHT |
| Report discovery method | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Report discovery year | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Report reference | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report disposition | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **10**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **0**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**

**Summary:** Both representations contained all criterion evidence and both verifiers caught it. The equal total hides only minor differences in typography scoring.

### Artifacts

- [Frozen rubric](rubrics/browser_task_084-exoplanet-discovery-record-20260909T091127Z.json)
- [Comparison report](results/browser_task_084-exoplanet-discovery-record-20260909T091127Z/20260913T_task084_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_084-exoplanet-discovery-record-20260909T091127Z/20260913T_task084_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_084-exoplanet-discovery-record-20260909T091127Z/20260913T_task084_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_084-exoplanet-discovery-record-20260909T091127Z/20260913T_task084_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 85 — Asteroid Record

Task ID: `browser_task_085-asteroid-record-20260909T091202Z`  
Run: `20260913T_task085_data_new`  
Frozen rubric: 8 criteria, 20 points  
Rubric SHA-256: `30a92a02be1e3cbe99d28189166d1f6ad37b51219014af78d6ca5d00a9d40407`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 4/20 (20.0%) | 2/20 (10.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 5 / 6 | 5 / 6 |
| LLM calls / retries | 19 / 0 | 47 / 0 |
| Duration | 96.793 s | 154.356 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 109,574 | 11,765 | 2,112 | 121,339 |
| DOM model | 175,444 | 34,149 | 1,792 | 209,593 |

*Reasoning tokens are included within completion tokens.* DOM used 88,254 more scoring tokens (72.7% increase). Rubric generation was separate: 13,391 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use only the supplied NASA/JPL SBDB response (99942 Apophis, phys-par=1) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report object.fullname exactly | Yes / Yes | No / No | 0/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Report orbit class name and code from object.orbit_class | Yes / Yes | No / No | 0/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Report orbit.epoch exactly | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Report absolute magnitude (H) value and uncertainty from phys_par | Yes / Yes | No / No | 0/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Report diameter value, uncertainty, and unit from phys_par | Yes / Yes | No / No | 0/4 / 0/4 | DOM_EVIDENCE_MISSING |
| Report potentially hazardous asteroid flag from object.pha | Yes / Yes | No / No | 0/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Output scope: only requested fields; no extra SBDB fields | Yes / Yes | Yes / Yes | 2/2 / 0/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **3**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **0**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **5**

**Summary:** Screenshots exposed the requested SBDB object and physical-parameter fields, while every DOM state remained a short fixed prefix ending inside the orbit data; five criteria therefore have genuine DOM source loss.

### Artifacts

- [Frozen rubric](rubrics/browser_task_085-asteroid-record-20260909T091202Z.json)
- [Comparison report](results/browser_task_085-asteroid-record-20260909T091202Z/20260913T_task085_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_085-asteroid-record-20260909T091202Z/20260913T_task085_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_085-asteroid-record-20260909T091202Z/20260913T_task085_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_085-asteroid-record-20260909T091202Z/20260913T_task085_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 86 — Cross-Endpoint Tide Station Inspection

Task ID: `browser_task_086-cross-endpoint-tide-station-inspection-20260909T091255Z`  
Run: `20260913T_task086_data_new`  
Frozen rubric: 4 criteria, 15 points  
Rubric SHA-256: `fb4c8bce0a8e20dfd3bf5838b788bee3eb643563bcc1244ad72ea94a9b686a37`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/15 (80.0%) | 11/15 (73.3%) |
| Rubric / outcome | Pass / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 12 / 0 |
| Duration | 78.668 s | 73.683 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 72,634 | 7,842 | 1,792 | 80,476 |
| DOM model | 63,985 | 7,288 | 1,536 | 71,273 |

*Reasoning tokens are included within completion tokens.* DOM used 9,203 fewer scoring tokens (11.4% reduction). Rubric generation was separate: 12,788 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use only NOAA station 9414290 and its details.self URL (or clearly report access failure) | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report base-station fields (ID, name, state, lat/long, timezone abbreviation & correction) | Partial / Yes | Partial / Yes | 2/4 / 1/4 | BOTH_CAUGHT |
| Follow details.self and report required linked-details fields | Yes / Yes | Yes / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Respect task constraints on exactness and stopping condition | Yes / Yes | Yes / Yes | 2/3 / 2/3 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **4**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **0**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **0**

**Summary:** Both sources were incomplete for the bundled base-field criterion: the screenshot omitted longitude, while DOM omitted most base fields. Because neither modality contained the complete criterion, this mixed case is excluded from asymmetric evidence-loss counting.

### Artifacts

- [Frozen rubric](rubrics/browser_task_086-cross-endpoint-tide-station-inspection-20260909T091255Z.json)
- [Comparison report](results/browser_task_086-cross-endpoint-tide-station-inspection-20260909T091255Z/20260913T_task086_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_086-cross-endpoint-tide-station-inspection-20260909T091255Z/20260913T_task086_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_086-cross-endpoint-tide-station-inspection-20260909T091255Z/20260913T_task086_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_086-cross-endpoint-tide-station-inspection-20260909T091255Z/20260913T_task086_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 87 — River Monitoring

Task ID: `browser_task_087-river-monitoring-20260909T091320Z`  
Run: `20260913T_task087_data_new`  
Frozen rubric: 5 criteria, 13 points  
Rubric SHA-256: `d6936e2ce99610f826aa5b76541407e58617a7aeee59041b81839605a3a8d94d`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 9/13 (69.2%) | 8/13 (61.5%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 6 / 7 | 6 / 7 |
| LLM calls / retries | 22 / 0 | 46 / 0 |
| Duration | 88.216 s | 205.877 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 134,515 | 12,911 | 2,368 | 147,426 |
| DOM model | 217,140 | 30,370 | 2,560 | 247,510 |

*Reasoning tokens are included within completion tokens.* DOM used 100,084 more scoring tokens (67.9% increase). Rubric generation was separate: 13,253 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use the correct USGS monitoring location (USGS-01646500) and Continuous Data section | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report station name | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Latest Continuous Data observation: Discharge (cubic feet per second) | No / No | Yes / Yes | 0/3 / 0/3 | SCREENSHOT_EVIDENCE_MISSING |
| Latest Continuous Data observation: Gage height (feet) | Yes / Yes | Yes / Yes | 3/3 / 2/3 | BOTH_CAUGHT |
| Display both series if not initially shown; preserve provisional labels and stop after required reporting | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **4**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **0**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **1**
- DOM_EVIDENCE_MISSING: **0**

**Summary:** DOM state 2 preserved the latest Discharge readout (1980 ft^3/s with timestamp), while the screenshots showed only the series-selection state and never the numeric readout. Both verifiers otherwise used their available evidence correctly.

### Artifacts

- [Frozen rubric](rubrics/browser_task_087-river-monitoring-20260909T091320Z.json)
- [Comparison report](results/browser_task_087-river-monitoring-20260909T091320Z/20260913T_task087_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_087-river-monitoring-20260909T091320Z/20260913T_task087_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_087-river-monitoring-20260909T091320Z/20260913T_task087_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_087-river-monitoring-20260909T091320Z/20260913T_task087_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 88 — Television Season Analysis

Task ID: `browser_task_088-television-season-analysis-20260909T091436Z`  
Run: `20260913T_task088_data_new`  
Frozen rubric: 6 criteria, 22 points  
Rubric SHA-256: `d2fdb96b6054746d69994126190fbfb081d8e7b2a8f1e5d5a29a41f39492c3a2`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/22 (59.1%) | 9/22 (40.9%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 23 / 24 | 23 / 24 |
| LLM calls / retries | 42 / 0 | 61 / 0 |
| Duration | 98.329 s | 132.423 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 216,169 | 16,295 | 1,664 | 232,464 |
| DOM model | 237,152 | 28,488 | 2,176 | 265,640 |

*Reasoning tokens are included within completion tokens.* DOM used 33,176 more scoring tokens (14.3% increase). Rubric generation was separate: 12,549 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Restrict analysis to TVMaze episode list for show 82 and season = 1 only | Yes / Yes | No / No | 4/4 / 2/4 | DOM_EVIDENCE_MISSING |
| Report correct season-1 episode count | Yes / Yes | No / No | 3/3 / 1/3 | DOM_EVIDENCE_MISSING |
| Report boundary episodes (first and final) for season 1 with required fields | Yes / Yes | No / No | 4/4 / 2/4 | DOM_EVIDENCE_MISSING |
| Identify maximum non-null rating.average among season-1 episodes using rating.average for ranking | Yes / Yes | No / No | 0/4 / 1/4 | DOM_EVIDENCE_MISSING |
| Report all season-1 episodes tied for highest rating with required fields (no arbitrary tie-breaking) | Yes / Yes | No / No | 0/5 / 1/5 | DOM_EVIDENCE_MISSING |
| Stopping condition adherence (report only requested outputs) | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **1**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **0**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **5**

**Summary:** Screenshots preserved the episode sequence and ratings through the season boundary; all 24 DOM states repeated a prefix containing only S1E1. Five criteria therefore have genuine DOM source loss.

### Artifacts

- [Frozen rubric](rubrics/browser_task_088-television-season-analysis-20260909T091436Z.json)
- [Comparison report](results/browser_task_088-television-season-analysis-20260909T091436Z/20260913T_task088_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_088-television-season-analysis-20260909T091436Z/20260913T_task088_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_088-television-season-analysis-20260909T091436Z/20260913T_task088_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_088-television-season-analysis-20260909T091436Z/20260913T_task088_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 89 — Postcode Civic Geography

Task ID: `browser_task_089-postcode-civic-geography-20260909T091806Z`  
Run: `20260913T_task089_data_new`  
Frozen rubric: 4 criteria, 12 points  
Rubric SHA-256: `31a747cbdae946437d32ce2f8ae2ec81d89d1c630bd4ee658425f925b6985095`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/12 (100.0%) | 9/12 (75.0%) |
| Rubric / outcome | Pass / Pass | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 26 / 0 |
| Duration | 70.577 s | 139.009 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 65,895 | 6,965 | 2,304 | 72,860 |
| DOM model | 84,601 | 15,190 | 1,792 | 99,791 |

*Reasoning tokens are included within completion tokens.* DOM used 26,931 more scoring tokens (37.0% increase). Rubric generation was separate: 12,563 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Report 11 specific fields from the result object for SW1A2AA | Yes / Yes | No / No | 6/6 / 4.5/6 | DOM_EVIDENCE_MISSING |
| Use only result object fields (with sole exception of codes.admin_district) and keep fields distinct | Yes / Yes | No / No | 3/3 / 2/3 | DOM_EVIDENCE_MISSING |
| Preserve exact formatting/precision as returned | Yes / Yes | No / No | 2/2 / 1.5/2 | DOM_EVIDENCE_MISSING |
| Stopping condition: stop after recording all 11 requested fields | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **1**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **0**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **3**

**Summary:** Screenshots contained all eleven postcode fields, while both DOM states truncated before admin_district, admin_ward, and codes.admin_district, affecting three criteria.

### Artifacts

- [Frozen rubric](rubrics/browser_task_089-postcode-civic-geography-20260909T091806Z.json)
- [Comparison report](results/browser_task_089-postcode-civic-geography-20260909T091806Z/20260913T_task089_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_089-postcode-civic-geography-20260909T091806Z/20260913T_task089_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_089-postcode-civic-geography-20260909T091806Z/20260913T_task089_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_089-postcode-civic-geography-20260909T091806Z/20260913T_task089_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 90 — SI Defining Constant Table

Task ID: `browser_task_090-si-defining-constant-table-20260909T091833Z`  
Run: `20260913T_task090_data_new`  
Frozen rubric: 8 criteria, 16 points  
Rubric SHA-256: `316185411a39bbb1b56e98d74c7dbc4d4714dc2022a91c98a872a1b80669e08f`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 9/16 (56.2%) | 8/16 (50.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 11 / 0 | 16 / 0 |
| Duration | 109.726 s | 168.476 s |

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 70,652 | 9,802 | 3,392 | 80,454 |
| DOM model | 94,832 | 16,532 | 2,432 | 111,364 |

*Reasoning tokens are included within completion tokens.* DOM used 30,910 more scoring tokens (38.4% increase). Rubric generation was separate: 13,960 tokens in 2 calls; both scoring runs reported `rubric_generation_calls: 0`.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Report defining constant #1 (as displayed in BIPM table) | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |
| Report defining constant #2 (as displayed in BIPM table) | Yes / Yes | No / No | 1/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Report defining constant #3 (as displayed in BIPM table) | Yes / Yes | No / No | 1/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Report defining constant #4 (as displayed in BIPM table) | Yes / Yes | No / No | 1/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Report defining constant #5 (as displayed in BIPM table) | Yes / Yes | No / No | 1/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Report defining constant #6 (as displayed in BIPM table) | Yes / Yes | No / No | 1/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Report defining constant #7 (as displayed in BIPM table) | Yes / Yes | No / No | 1/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Report BIPM uncertainty statement about the numerical values | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

### Evidence-error result

- BOTH_CAUGHT: **2**
- SCREENSHOT_MISSED_DOM_CAUGHT: **0**
- DOM_MISSED_SCREENSHOT_CAUGHT: **0**
- BOTH_MISSED: **0**
- SCREENSHOT_EVIDENCE_MISSING: **0**
- DOM_EVIDENCE_MISSING: **6**

**Summary:** DOM preserved enough evidence for the first constant when the table row and surrounding BIPM text are read together. For constants 2–7, it omitted required powers or inverse-unit exponents that remain visible in the screenshot table.

### Artifacts

- [Frozen rubric](rubrics/browser_task_090-si-defining-constant-table-20260909T091833Z.json)
- [Comparison report](results/browser_task_090-si-defining-constant-table-20260909T091833Z/20260913T_task090_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_090-si-defining-constant-table-20260909T091833Z/20260913T_task090_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_090-si-defining-constant-table-20260909T091833Z/20260913T_task090_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_090-si-defining-constant-table-20260909T091833Z/20260913T_task090_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 91 — Cross-endpoint blockchain record

Task ID: `browser_task_091-cross-endpoint-blockchain-record-20260909T091909Z`  
Run: `20260913T_task091_data_new`  
Frozen rubric: 6 criteria, 21 points  
Rubric SHA-256: `c594cfe6a041f7fc5690e1f8f8f8fc13f658d4743fcc53b14c72a5bb8e16ba8f`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 21/21 (100%) | 21/21 (100%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 12 / 0 | 16 / 0 |
| Scoring tokens | 80,876 | 79,523 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Resolve hash with `/api/block-height/800000` | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Construct `/api/block/{hash}` URL | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Retrieve exact block record | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report requested block fields | Yes / Yes | Yes / Yes | 8/8 / 8/8 | BOTH_CAUGHT |
| Preserve exact values and distinctions | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop after requested fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

**Summary:** Both representations preserved the hash, endpoint sequence, and complete block record. No evidence loss or verifier miss was found.

---

## Task 92 — Legislative roll-call inspection

Task ID: `browser_task_092-legislative-roll-call-inspection-20260909T091934Z`  
Run: `20260913T_task092_data_new`  
Frozen rubric: 10 criteria, 30 points  
Rubric SHA-256: `a890f41cead00360c390707224de60ae9e238a221b233e127832d42e133e7ac6`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 0/30 (0%) | 30/30 (100%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 10 / 0 | 30 / 0 |
| Scoring tokens | 70,981 | 142,966 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Clerk vote-details page | Yes / Yes | Yes / Yes | 0/3 / 3/3 | BOTH_CAUGHT |
| Roll-call number | Yes / Yes | Yes / Yes | 0/2 / 2/2 | BOTH_CAUGHT |
| Bill number | Yes / Yes | Yes / Yes | 0/3 / 3/3 | BOTH_CAUGHT |
| Displayed date and time | Yes / Yes | Yes / Yes | 0/3 / 3/3 | BOTH_CAUGHT |
| Congress and session | Yes / Yes | Yes / Yes | 0/4 / 4/4 | BOTH_CAUGHT |
| Vote Question | Yes / Yes | Yes / Yes | 0/3 / 3/3 | BOTH_CAUGHT |
| Vote Type | Yes / Yes | Yes / Yes | 0/2 / 2/2 | BOTH_CAUGHT |
| Status | Yes / Yes | Yes / Yes | 0/2 / 2/2 | BOTH_CAUGHT |
| Aggregate vote totals | Yes / Yes | Yes / Yes | 0/6 / 6/6 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 0/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both verifiers extracted the page evidence correctly. The score difference comes from different treatment of the empty final response and is not source-evidence loss; both verifier analyses explicitly recovered the available page evidence.

---

## Task 93 — Supreme Court case analysis

Task ID: `browser_task_093-supreme-court-case-analysis-20260909T092007Z`  
Run: `20260913T_task093_data_new`  
Frozen rubric: 7 criteria, 16 points  
Rubric SHA-256: `c49eaa21d4a9edd5fde2cc07d823703bf25320782831a5f91ca52c9c0b249dbb`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/16 (100%) | 16/16 (100%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 14 / 0 | 26 / 0 |
| Scoring tokens | 89,682 | 119,905 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Brown v. Board page | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Docket and deciding Court | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Argued, reargued, and decided dates | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Displayed Question | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Decision split and prevailing side | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Majority-opinion author | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| One-line holding | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

**Summary:** Both modalities preserved and both verifiers recovered all required case metadata and conclusion evidence.

---

## Task 94 — EU regulation metadata

Task ID: `browser_task_094-eu-regulation-metadata-20260909T092042Z`  
Run: `20260913T_task094_data_new`  
Frozen rubric: 6 criteria, 15 points  
Rubric SHA-256: `dd3cc482d818e64a490ac97ab93402bf440a770eca29c4aca54cb37af6c25049`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/15 (100%) | 15/15 (100%) |
| Outcome | Pass | Pass |
| LLM calls / retries | 12 / 0 | 23 / 0 |
| Scoring tokens | 77,785 | 129,058 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| CELEX document number | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Official Journal citation | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Document information / Dates view | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Date of document | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Entry-into-force date | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Application date | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

**Summary:** Both representations and verifiers recovered all requested EUR-Lex metadata.

---

## Task 95 — Electricity generation mix

Task ID: `browser_task_095-electricity-generation-mix-20260909T092120Z`  
Run: `20260913T_task095_data_new`  
Frozen rubric: 4 criteria, 12 points  
Rubric SHA-256: `7d5a5a273e604a77efabed606d75705b44c94f7111244a300e7c2a6f2108eb8c`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6/12 (50.0%) | 6.5/12 (54.2%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 12 / 0 | 22 / 0 |
| Scoring tokens | 82,374 | 106,707 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Select exact requested interval | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| All fuel-percentage pairs in order | Yes / Yes | No / No | 1/4 / 1/4 | DOM_EVIDENCE_MISSING |
| All explicitly zero fuels | Yes / Yes | No / No | 1/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Sum all percentages | Yes / Yes | No / No | 0/2 / 0.5/2 | DOM_EVIDENCE_MISSING |

**Summary:** The screenshot sequence contained the complete nine-entry generation mix. DOM stopped after the first three entries, so three criteria have genuine DOM source loss.

---

## Task 96 — Medication label lookup

Task ID: `browser_task_096-medication-label-lookup-20260909T092144Z`  
Run: `20260913T_task096_data_new`  
Frozen rubric: 7 criteria, 20 points  
Rubric SHA-256: `f654e9ea48250723c3b05e69989ab730a13e96913fc51272cf10af7248e24db5`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/20 (85.0%) | 19/20 (95.0%) |
| Outcome | Fail | Pass |
| LLM calls / retries | 20 / 0 | 31 / 0 |
| Scoring tokens | 138,120 | 190,384 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Search DailyMed for LIPITOR | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Select non-repackaged Viatris label | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Label title and Packager | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Initial U.S. Approval year | No / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Dosage form and four strengths | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Route, ingredient, and basis of strength | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Scope and stopping condition | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

**Summary:** `Initial U.S. Approval: 1996` was explicit in the DOM but outside the captured screenshots. All other criterion evidence was present and recovered in both modes.

---

## Task 97 — DNS record resolution

Task ID: `browser_task_097-dns-record-resolution-20260909T092253Z`

**Status:** Not run. The paired dataset exists, but there is no frozen rubric, comparison result, scoring metrics, or evidence audit. Task 97 is excluded from all report aggregates.

---

## Task 98 — Solar/lunar ephemeris

Task ID: `browser_task_098-solar-lunar-ephemeris-20260909T092628Z`  
Run: `20260914T_task098_data_new`  
Frozen rubric: 8 criteria, 23 points  
Rubric SHA-256: `5ce36d2eff177b2341d7b5591e6c6cffe5385ac37029b1673c22a7e23f7d5b0e`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/23 (69.6%) | 21/23 (91.3%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 14 / 0 | 20 / 0 |
| Scoring tokens | 98,554 | 116,527 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Coordinates in returned order | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Date fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Timezone fields (`tz`, `isdst`) | Yes / Yes | No / No | 1/2 / 1/2 | DOM_EVIDENCE_MISSING |
| Lunar phase summary | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| All `closestphase` fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| All Moon events | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| All Sun events | Yes / Yes | No / No | 0/4 / 4/4 | DOM_EVIDENCE_MISSING |
| Constraints and stopping condition | Yes / Yes | No / No | 1/3 / 2/3 | DOM_EVIDENCE_MISSING |

**Summary:** DOM was truncated at the opening of `sundata` and omitted `tz`, so it could not prove three criteria. The higher DOM score on the Sun-events criterion does not represent additional DOM source evidence; the required Sun-event values are absent from the DOM input.

---

## Task 99 — Consumer-product recall inspection

Task ID: `browser_task_099-consumer-product-recall-inspection-20260909T092703Z`  
Run: `20260914T_task099_data_new`  
Frozen rubric: 8 criteria, 20 points  
Rubric SHA-256: `f525c5189c79ff820071b6074d55eef71ded39a4ffa09746ef1f5c23d9f8a218`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 7/20 (35.0%) | 5/20 (25.0%) |
| Outcome | Fail | Fail |
| LLM calls / retries | 14 / 0 | 21 / 0 |
| Scoring tokens | 109,014 | 129,758 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Retrieve RecallID 10000 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Core fields including full Title | Yes / Yes | No / No | 3/3 / 2/3 | DOM_EVIDENCE_MISSING |
| Products entries | Yes / Yes | No / No | 0/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Injuries entries | Yes / Yes | No / No | 0/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Retailers entries | Yes / Yes | No / No | 0/1 / 0/1 | DOM_EVIDENCE_MISSING |
| ManufacturerCountries entries | Yes / Yes | No / No | 2/2 / 0/2 | DOM_EVIDENCE_MISSING |
| Hazards, Remedies, and RemedyOptions | Yes / Yes | No / No | 0/4 / 0/4 | DOM_EVIDENCE_MISSING |
| Exact-transcription constraints | Yes / Yes | No / No | 0/3 / 1/3 | DOM_EVIDENCE_MISSING |

**Summary:** Every screenshot-required array was captured, while DOM states ended before the arrays and preserved only the leading recall fields. Seven criteria therefore have genuine DOM source loss.

---

## Task 100 — Earthquake impact record

Task ID: `browser_task_100-earthquake-impact-record-inspection-20260909T092735Z`  
Run: `20260914T_task100_data_new`  
Frozen rubric: 6 criteria, 18 points  
Rubric SHA-256: `09b96da6445a00cd31d5960838b5e2b955b3c8f8c71da1313c4436b2bfb6d3d3`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/18 (88.9%) | 17/18 (94.4%) |
| Outcome | Fail | Pass |
| LLM calls / retries | 12 / 0 | 15 / 0 |
| Scoring tokens | 77,510 | 88,936 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Event title and coordinates | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Did You Feel It? community MMI | No / No | Yes / Yes | 1/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| ShakeMap estimated MMI | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Landslide estimate | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Liquefaction estimate | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Origin-card fields | Yes / Yes | Yes / Yes | 4/5 / 4/5 | BOTH_CAUGHT |

**Summary:** The community MMI value was not legible in the screenshots but was explicit as `IX mmi` in DOM. All other required evidence was available and recovered in both modes.

---

## Tasks 91–100 evidence-error summary

Task 97 is unrun and excluded. Across the other nine tasks:

- Rubric criteria audited: **62**
- BOTH_CAUGHT: **47**
- SCREENSHOT_EVIDENCE_MISSING: **2**
- DOM_EVIDENCE_MISSING: **13**
- Confirmed screenshot-verifier misses: **0**
- Confirmed DOM-verifier misses: **0**
- Screenshot scoring tokens: **824,896**
- DOM scoring tokens: **1,103,764**

---

# Rerun Comparisons — Tasks 61–100

These results are intentionally separate from the canonical 98-task aggregate above. Tasks 61–76 and 78–90 reuse the exact criterion order, descriptions, maximum points, and normalized rubric hash from their original runs. Only the rubric wrapper task ID was rebound to each rerun ID. Task 77 had no original run or frozen rubric, so one new canonical rubric was generated for that task only; its Phase A usage is reported separately from scoring. Every scoring run reports `rubric_generation_calls: 0`.

## Rerun batch result — Tasks 61–70

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Tasks | 10 | 10 |
| Criteria | 82 | 82 |
| Aggregate process points | 130/191 (68.1%) | 139/191 (72.8%) |
| Scoring tokens | 1,125,142 | 1,467,574 |
| Asymmetric source-evidence loss | 3/82 (3.7%) | 0/82 (0.0%) |
| Confirmed verifier evidence-use misses | 0/82 (0.0%) | 1/82 (1.2%) |

DOM used 342,432 more scoring tokens than screenshots, a 30.4% increase. The three screenshot source gaps were the protein molecule name and ligand ID in Task 63 and the unrendered glyph in Task 70. The sole confirmed verifier miss was Task 64's DOM scorer awarding unsupported partial credit for a schedule count even though its own analysis confirmed that no schedule enumeration was present.

## Task 61 rerun — npm package metadata

Task ID: `browser_task_061-npm-package-metadata-20260914T083717Z`  
Run: `20260914T_task61_rerun_data_new`  
Reused rubric SHA-256: `51d85ccf1ea752a69f80236d568acd7c68dbea30f14b67afb334ca03e1873afe`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/14 (100%) | 14/14 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 20 / 0 |
| Duration | 75.561 s | 128.110 s |
| Scoring tokens | 77,401 | 110,913 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Official npm Registry response | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Package name | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Latest version | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| License | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Node.js engine requirement | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Unpacked size | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| File count | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both representations contained all requested npm fields and both verifiers recovered them correctly.

- [Comparison](results/task_61_rerun/20260914T_task61_rerun_data_new/comparison.md)
- [Offline audit](results/task_61_rerun/20260914T_task61_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 62 rerun — Rust crate metadata

Task ID: `browser_task_062-rust-crate-metadata-20260914T083832Z`  
Run: `20260914T_task62_rerun_data_new`  
Reused rubric SHA-256: `2139b52faa8bdae9dcac138b145be3103e9afb0237adea7d35a65b5878477ecd`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 22/22 (100%) | 22/22 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 2 / 3 | 2 / 3 |
| LLM calls / retries | 14 / 0 | 20 / 0 |
| Duration | 84.476 s | 110.173 s |
| Scoring tokens | 89,534 | 115,017 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Serde crates.io page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Latest version | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Release-date wording | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Minimum Rust version | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| License | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Package size | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Repository | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| All-time downloads | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Published versions | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

**Summary:** Both sources fully preserved the requested crate metadata and statistics.

- [Comparison](results/task_62_rerun/20260914T_task62_rerun_data_new/comparison.md)
- [Offline audit](results/task_62_rerun/20260914T_task62_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 63 rerun — Protein structure inspection

Task ID: `browser_task_063-protein-structure-inspection-20260914T083924Z`  
Run: `20260914T_task63_rerun_data_new`  
Reused rubric SHA-256: `2b6d742bc4854ebed327a519c46a92c0e11d5a011131e16c97c5839cabd5f8ab`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/23 (65.2%) | 23/23 (100%) |
| Rubric / outcome | Fail / Fail | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 40 / 0 |
| Duration | 110.217 s | 161.210 s |
| Scoring tokens | 87,569 | 208,193 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct RCSB 1TUP page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Structure title | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Released date | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Experimental method | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Resolution | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Protein molecule name | No / No | Yes / Yes | 0/3 / 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Protein organism | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Unique ligand IDs | No / No | Yes / Yes | 0/5 / 5/5 | SCREENSHOT_EVIDENCE_MISSING |
| Stop after requested fields | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

**Summary:** The screenshots stopped at the Macromolecules tabs and did not display the protein row or ligand ID. DOM explicitly preserved `PROTEIN (P53 TUMOR SUPPRESSOR)` and `Ligand Interaction (ZN)`.

- [Comparison](results/task_63_rerun/20260914T_task63_rerun_data_new/comparison.md)
- [Offline audit](results/task_63_rerun/20260914T_task63_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 64 rerun — Legislation structure inspection

Task ID: `browser_task_064-legislation-structure-inspection-20260914T084058Z`  
Run: `20260914T_task64_rerun_data_new`  
Reused rubric SHA-256: `29761b5dc27ac06d69d581fbc838bb739d73b4f0da27ce219174f8ebc715e525`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/20 (70%) | 15/20 (75%) |
| Rubric / outcome | Fail / Fail | Fail / Pass |
| Actions / states | 3 / 4 | 3 / 4 |
| LLM calls / retries | 16 / 0 | 25 / 0 |
| Duration | 117.979 s | 165.417 s |
| Scoring tokens | 100,704 | 145,202 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct as-enacted introduction | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Chapter number | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Long title | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Royal Assent date | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Top-level Parts count | Partial / correctly limited | Partial / correctly limited | 2/4 / 2/4 | BOTH_CAUGHT |
| Top-level Schedules count | No / correctly rejected | No / incorrectly awarded partial credit | 0/4 / 1/4 | DOM_MISSED_SCREENSHOT_CAUGHT |

**Summary:** Neither representation enumerated the Schedules, so the reported count of 20 was unsupported. The DOM scorer recognized that absence but still awarded one point merely because the correct page had been opened; this is a verifier evidence-use miss, not DOM source recovery.

- [Comparison](results/task_64_rerun/20260914T_task64_rerun_data_new/comparison.md)
- [Offline audit](results/task_64_rerun/20260914T_task64_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 65 rerun — Public transport interchange inspection

Task ID: `browser_task_065-public-transport-interchange-inspection-20260914T084230Z`  
Run: `20260914T_task65_rerun_data_new`  
Reused rubric SHA-256: `543008185397c93552f530d9f11bfcefcbae78868854f88a68ac4f0697038ac0`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/23 (65.2%) | 16/23 (69.6%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 48 / 49 | 48 / 49 |
| LLM calls / retries | 68 / 0 | 87 / 0 |
| Duration | 140.531 s | 181.688 s |
| Scoring tokens | 348,272 | 397,511 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Official TfL response | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| StopPoint ID | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Common name | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Latitude and longitude | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Every top-level mode | Yes / correctly found one omission | Yes / correctly found one omission | 2/4 / 3/4 | BOTH_CAUGHT |
| Zone value | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Tube line identifiers | Yes / Yes | Yes / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Stop after requested set | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** The one-point mode difference is partial-credit calibration, not evidence loss: both sources showed four modes and both verifiers caught that the final answer omitted `international-rail`.

- [Comparison](results/task_65_rerun/20260914T_task65_rerun_data_new/comparison.md)
- [Offline audit](results/task_65_rerun/20260914T_task65_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 66 rerun — Mathematical sequence reference

Task ID: `browser_task_066-mathematical-sequence-reference-20260914T084957Z`  
Run: `20260914T_task66_rerun_data_new`  
Reused rubric SHA-256: `968c547760de5254b62f0c731bf1ac922008b64893841d0bd4bc9c4da5c8b24c`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/16 (100%) | 15.5/16 (96.9%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 12 / 0 |
| Duration | 77.826 s | 94.910 s |
| Scoring tokens | 76,310 | 71,332 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| MathWorld source | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Fibonacci recurrence | Yes / Yes | Yes / Yes | 3/3 / 2.5/3 | BOTH_CAUGHT |
| Initial conditions | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| First eight values | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| OEIS identifier | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both sources contained the recurrence. The half-point difference reflects notation-format strictness, not missing evidence.

- [Comparison](results/task_66_rerun/20260914T_task66_rerun_data_new/comparison.md)
- [Offline audit](results/task_66_rerun/20260914T_task66_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 67 rerun — Chemical reference data

Task ID: `browser_task_067-chemical-reference-data-20260914T085132Z`  
Run: `20260914T_task67_rerun_data_new`  
Reused rubric SHA-256: `1cf91356f00e3863c1d3520912f1db9c10bd6dbb0ff4e94e142d2f02e4d2392e`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 8/15 (53.3%) | 7.5/15 (50%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 17 / 0 |
| Duration | 107.379 s | 140.602 s |
| Scoring tokens | 77,237 | 89,267 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct NIST water record | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Four identity fields | Yes / Yes | Yes / Yes | 4/4 / 3.5/4 | BOTH_CAUGHT |
| CODATA enthalpy entry | No / correctly rejected | No / correctly rejected | 0/6 / 0/6 | BOTH_CAUGHT |
| Exact transcription and stop | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

**Summary:** Both sources preserved the four identity fields and omitted the thermochemistry table. The half-point difference is formatting calibration around the formula, not asymmetric evidence loss.

- [Comparison](results/task_67_rerun/20260914T_task67_rerun_data_new/comparison.md)
- [Offline audit](results/task_67_rerun/20260914T_task67_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 68 rerun — Vehicle VIN decoding

Task ID: `browser_task_068-vehicle-vin-decoding-20260914T085208Z`  
Run: `20260914T_task68_rerun_data_new`  
Reused rubric SHA-256: `0b31852b1b0027ad6fd0446aa26d8eab82e58cefa4dc503e87d599200e64de25`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/16 (100%) | 16/16 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 20 / 0 |
| Duration | 102.239 s | 148.159 s |
| Scoring tokens | 91,429 | 124,310 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Official NHTSA response | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Make | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Model | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Model year | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Body class | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Engine cylinders | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Engine horsepower | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Plant city | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Plant state | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Plant country | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Error text | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Stop after requested fields | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both formats preserved and verified all requested VIN fields.

- [Comparison](results/task_68_rerun/20260914T_task68_rerun_data_new/comparison.md)
- [Offline audit](results/task_68_rerun/20260914T_task68_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 69 rerun — IP network registration

Task ID: `browser_task_069-ip-network-registration-20260914T085250Z`  
Run: `20260914T_task69_rerun_data_new`  
Reused rubric SHA-256: `2e9f94d2e3c2b0d218506eacceb5a1cdbaf8c8feae59e06a46df40b539ee5e99`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 2/22 (9.1%) | 2/22 (9.1%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 15 / 0 |
| Duration | 109.892 s | 125.389 s |
| Scoring tokens | 87,138 | 90,552 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Top-level handle | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Top-level name | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Top-level start address | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Top-level end address | Yes / correctly found agent omission | Yes / correctly found agent omission | 0/2 / 0/2 | BOTH_CAUGHT |
| Top-level type | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Top-level statuses | No / correctly rejected | No / correctly rejected | 0/4 / 0/4 | BOTH_CAUGHT |
| Top-level parent handle | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Registrant vCard name | No / correctly rejected | No / correctly rejected | 0/4 / 0/4 | BOTH_CAUGHT |
| Source constraint and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both captures stopped within nested entity data before most top-level fields and the registrant vCard. Both verifiers correctly rejected the final answer's claim that the visible `endAddress` could not be read.

- [Comparison](results/task_69_rerun/20260914T_task69_rerun_data_new/comparison.md)
- [Offline audit](results/task_69_rerun/20260914T_task69_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 70 rerun — Unicode ideograph inspection

Task ID: `browser_task_070-unicode-ideograph-inspection-20260914T085343Z`  
Run: `20260914T_task70_rerun_data_new`  
Reused rubric SHA-256: `d0ffe495ad2e47d67d52c42148e989a21aba2a4aa8fd88b63ab4a62c2b792f5e`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 8/20 (40%) | 8/20 (40%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 17 / 0 |
| Duration | 122.336 s | 165.164 s |
| Scoring tokens | 89,548 | 115,277 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct U+4E00 record | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Constraints and exact copying | Yes / Yes | Yes / Yes | 1/2 / 0/2 | BOTH_CAUGHT |
| Code point and glyph | Code point present; glyph rendered as an unreadable box / partial | Both explicit / Yes | 1/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Decimal and encodings | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stroke count | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Definition | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Mandarin | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Japanese On | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Korean | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Vietnamese | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |

**Summary:** The screenshot rendered the target glyph as a tofu/missing-font box, while DOM explicitly preserved `一`. Both representations lacked the requested definition and reading rows; the constraint-score difference is ordinary severity variance.

- [Comparison](results/task_70_rerun/20260914T_task70_rerun_data_new/comparison.md)
- [Offline audit](results/task_70_rerun/20260914T_task70_rerun_data_new/evidence_error_audit/criterion_audit.json)

---

## Rerun batch result — Tasks 71–80

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Tasks | 10 | 10 |
| Criteria | 71 | 71 |
| Aggregate process points | 138/196 (70.4%) | 144/196 (73.5%) |
| Scoring tokens | 1,023,038 | 1,363,629 |
| Asymmetric source-evidence loss | 1/71 (1.4%) | 1/71 (1.4%) |
| Confirmed verifier evidence-use misses | 0/71 (0.0%) | 6/71 (8.5%) |

DOM used 340,591 more scoring tokens than screenshots, a 33.3% increase. The screenshot source gap was Task 75's exact endpoint URL, which is explicit in the DOM header but absent from the screenshot viewport. The DOM source gap was Task 76's exact `message.published.date-parts` field, which is visible in screenshot 0 but omitted from the captured DOM text. The six DOM verifier-use misses were Task 80's six identity/status fields: both sources contained them, but the DOM scorer credited the visible page values even though the agent's final answer reported only an API context-length error and did not provide those fields.

Task 77 used a newly generated 12-criterion, 30-point rubric because no original frozen rubric existed. Phase A used 2 GPT-5.2 calls and 14,798 tokens; this usage is separate from the scoring totals above.

## Task 71 rerun — Satellite catalog inspection

Task ID: `browser_task_071-satellite-catalog-inspection-20260914T085508Z`  
Run: `20260914T_task71_rerun_data_new`  
Reused rubric SHA-256: `549ae13c1406f1148bdbc102555365301e39694363e504bdd26ea03262b5520b`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 23/23 (100%) | 23/23 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 17 / 0 |
| Duration | 82.236 s | 124.612 s |
| Scoring tokens | 78,790 | 85,729 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct SATCAT record | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Record/source constraints | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Identity fields | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Status and owner codes | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Launch fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Orbital parameters | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

**Summary:** Both representations preserved every requested SATCAT field and both verifiers recovered them correctly.

- [Comparison](results/task_71_rerun/20260914T_task71_rerun_data_new/comparison.md)
- [Offline audit](results/task_71_rerun/20260914T_task71_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 72 rerun — Regional calendar comparison

Task ID: `browser_task_072-regional-calendar-comparison-20260914T085604Z`  
Run: `20260914T_task72_rerun_data_new`  
Reused rubric SHA-256: `231a2296aa6a12b6ac225c3ca067a8b4ec03f032f694482c3b3796132483bfa7`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/12 (100%) | 12/12 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 15 / 0 |
| Duration | 95.369 s | 100.118 s |
| Scoring tokens | 82,289 | 98,763 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Official GOV.UK response | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Scotland: 2nd January | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Scotland: Summer bank holiday | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Scotland: St Andrew's Day | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| England and Wales: Summer bank holiday | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

**Summary:** Both sources contained the requested 2026 events and both verifiers recovered the values correctly.

- [Comparison](results/task_72_rerun/20260914T_task72_rerun_data_new/comparison.md)
- [Offline audit](results/task_72_rerun/20260914T_task72_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 73 rerun — Pageview time-series analysis

Task ID: `browser_task_073-pageview-time-series-analysis-20260914T085821Z`  
Run: `20260914T_task73_rerun_data_new`  
Reused rubric SHA-256: `d4a151184f452268c309515f8df93743958ec6050655eb59d4badc4a9368eb4f`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 0/15 (0%) | 0/15 (0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 0 / 1 | 0 / 1 |
| LLM calls / retries | 10 / 0 | 18 / 0 |
| Duration | 71.188 s | 138.757 s |
| Scoring tokens | 61,316 | 80,294 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Seven daily date/view pairs | Yes / correctly found agent omission | Yes / correctly found agent omission | 0/6 / 0/6 | BOTH_CAUGHT |
| Total arithmetic | Raw counts present / correctly rejected missing answer | Raw counts present / correctly rejected missing answer | 0/3 / 0/3 | BOTH_CAUGHT |
| Highest-view calculation | Raw counts present / correctly rejected missing answer | Raw counts present / correctly rejected missing answer | 0/3 / 0/3 | BOTH_CAUGHT |
| Constraints | Yes / correctly rejected missing answer | Yes / correctly rejected missing answer | 0/3 / 0/3 | BOTH_CAUGHT |

**Summary:** Both inputs contained the seven API records, but the agent produced only a generic execution-error response. Both verifiers correctly awarded zero.

- [Comparison](results/task_73_rerun/20260914T_task73_rerun_data_new/comparison.md)
- [Offline audit](results/task_73_rerun/20260914T_task73_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 74 rerun — Occupational profile analysis

Task ID: `browser_task_074-occupational-profile-analysis-20260914T085936Z`  
Run: `20260914T_task74_rerun_data_new`  
Reused rubric SHA-256: `dd3422752f1fa816da9a0f682de0c82e2ba8cdb298e19108b5d9486950da0350`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 7/22 (31.8%) | 5/22 (22.7%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 0 / 1 | 0 / 1 |
| LLM calls / retries | 10 / 0 | 11 / 0 |
| Duration | 109.614 s | 143.634 s |
| Scoring tokens | 76,454 | 79,238 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct O*NET profile | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Occupation title and code | Yes / correctly found weak reporting | Yes / correctly found weak reporting | 1/2 / 0/2 | BOTH_CAUGHT |
| Bright Outlook status | Yes / correctly found weak reporting | Yes / correctly found weak reporting | 2/2 / 1/2 | BOTH_CAUGHT |
| Job Zone title | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Annual median wage | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Current employment | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Projected growth | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Projected openings | No / correctly rejected | No / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

**Summary:** Both representations captured only the profile header fields and omitted the lower-page workforce values. The two-point score difference is partial-credit calibration, not evidence loss.

- [Comparison](results/task_74_rerun/20260914T_task74_rerun_data_new/comparison.md)
- [Offline audit](results/task_74_rerun/20260914T_task74_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 75 rerun — Collectible card rules

Task ID: `browser_task_075-collectible-card-rules-20260914T090059Z`  
Run: `20260914T_task75_rerun_data_new`  
Reused rubric SHA-256: `6f14affeb38c269013e39e45b0490af6aae0f1273b38089a71952b4518441c09`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/17 (94.1%) | 17/17 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 23 / 0 |
| Duration | 88.725 s | 128.740 s |
| Scoring tokens | 78,463 | 129,530 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Exact-card Scryfall endpoint | No / correctly limited | Yes / Yes | 2/3 / 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Card identity fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Complete Oracle text | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Reserved flag | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Format legalities | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both captured the card data. Only the DOM header preserved the exact request URL; the screenshot viewport did not expose browser chrome or the complete endpoint.

- [Comparison](results/task_75_rerun/20260914T_task75_rerun_data_new/comparison.md)
- [Offline audit](results/task_75_rerun/20260914T_task75_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 76 rerun — DOI metadata

Task ID: `browser_task_076-doi-metadata-20260914T090131Z`  
Run: `20260914T_task76_rerun_data_new`  
Reused rubric SHA-256: `256cf48db6dc6362d093dcf836d688dbfe7cc5f2c89f278d9c8a5c5b966e3a0b`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 19/20 (95%) | 16/20 (80%) |
| Rubric / outcome | Pass / Fail | Pass / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 26 / 0 |
| Duration | 84.157 s | 194.751 s |
| Scoring tokens | 75,857 | 154,363 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Supplied Crossref response | Yes / Yes | Yes / Yes | 3/3 / 2/3 | BOTH_CAUGHT |
| Work title | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Publisher | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| `message.published.date-parts` | Yes / Yes | No / correctly rejected | 3/3 / 0/3 | DOM_EVIDENCE_MISSING |
| Work type | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Complete ordered author list | Yes / Yes | Yes / Yes | 5/6 / 6/6 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Screenshot 0 visibly contains `message.published.date-parts: [[2024,1,17]]`; the DOM capture contains nearby `published-online` and `published-print` fields but omits the exact required `message.published` field. Other score differences are calibration, not evidence loss.

- [Comparison](results/task_76_rerun/20260914T_task76_rerun_data_new/comparison.md)
- [Offline audit](results/task_76_rerun/20260914T_task76_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 77 rerun — Patent record inspection

Task ID: `browser_task_077-patent-record-inspection-20260914T090247Z`  
Run: `20260914T_task77_rerun_data_new`  
Newly generated rubric SHA-256: `b074ef487637c1bc30d9d5aa9f3006c69baaff8696ed2f1abd51f4d6f943ecc6`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 26/30 (86.7%) | 24/30 (80%) |
| Rubric / outcome | Pass / Fail | Pass / Fail |
| Actions / states | 27 / 28 | 27 / 28 |
| LLM calls / retries | 54 / 0 | 57 / 0 |
| Duration | 159.183 s | 179.133 s |
| Scoring tokens | 342,741 | 383,230 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct patent and source | Yes / Yes | Yes / Yes | 3/3 / 2/3 | BOTH_CAUGHT |
| Title | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Publication number | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Application number | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Inventor | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Current assignees | Yes / Yes | Yes / Yes | 3/4 / 4/4 | BOTH_CAUGHT |
| Original assignee | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Priority date | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |
| Filing date | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Publication date | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |
| Legal status | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both sources preserved the same patent header, assignees, application details, event dates, and status; neither explicitly labeled an Original Assignee. The two-point total difference is strictness/format calibration, not asymmetric evidence loss.

- [Comparison](results/task_77_rerun/20260914T_task77_rerun_data_new/comparison.md)
- [Offline audit](results/task_77_rerun/20260914T_task77_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 78 rerun — Cross-endpoint game data

Task ID: `browser_task_078-cross-endpoint-game-data-20260914T090704Z`  
Run: `20260914T_task78_rerun_data_new`  
Reused rubric SHA-256: `fc0553ae76f7d38f74791ed0b8d2518a353fa3a7bbc068449bdc7ffe0bd460e1`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/20 (60%) | 12/20 (60%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 25 / 0 |
| Duration | 105.931 s | 162.363 s |
| Scoring tokens | 85,730 | 148,622 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Pokémon/species sources | Yes / Yes | Yes / Yes | 2/3 / 2/3 | BOTH_CAUGHT |
| Pokémon identity fields | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Types array | No / correctly rejected | No / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Complete stats array | No / correctly rejected | No / correctly rejected | 0/4 / 0/4 | BOTH_CAUGHT |
| Species fields | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both initial captures stop before the `types` and `stats` arrays, while both species captures contain the requested species values. Both verifiers handled those same limitations consistently.

- [Comparison](results/task_78_rerun/20260914T_task78_rerun_data_new/comparison.md)
- [Offline audit](results/task_78_rerun/20260914T_task78_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 79 rerun — Motor-race result analysis

Task ID: `browser_task_079-motor-race-result-analysis-20260914T090744Z`  
Run: `20260914T_task79_rerun_data_new`  
Reused rubric SHA-256: `ebb9b172975df6aba5a6fdef96a7a5c172e30600f78d7899c84c675fda1f2ce7`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 20/20 (100%) | 20/20 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 36 / 0 |
| Duration | 77.520 s | 149.419 s |
| Scoring tokens | 76,780 | 134,961 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct response and array selection | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Race fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Winner identity | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Winner result | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Complete FastestLap object | Yes / Yes | Yes / Yes | 6/6 / 6/6 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both formats preserved the complete single-race result and both verifiers recovered every requested field.

- [Comparison](results/task_79_rerun/20260914T_task79_rerun_data_new/comparison.md)
- [Offline audit](results/task_79_rerun/20260914T_task79_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 80 rerun — Protein record inspection

Task ID: `browser_task_080-protein-record-inspection-20260914T090913Z`  
Run: `20260914T_task80_rerun_data_new`  
Reused rubric SHA-256: `da6c0c2e585c969c9e8a4722f03ca6e9a3c22ecc5bd5ce27271a367fa424c122`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 3/17 (17.6%) | 15/17 (88.2%) |
| Rubric / outcome | Fail / Fail | Pass / Fail |
| Actions / states | 0 / 1 | 0 / 1 |
| LLM calls / retries | 10 / 0 | 11 / 0 |
| Duration | 82.295 s | 91.540 s |
| Scoring tokens | 64,618 | 68,899 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct UniProt record | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Entry name | Yes / correctly found agent omission | Yes / incorrectly credited absent output | 0/2 / 2/2 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Recommended protein name | Yes / correctly found agent omission | Yes / incorrectly credited absent output | 0/2 / 2/2 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Primary gene name | Yes / correctly found agent omission | Yes / incorrectly credited absent output | 0/2 / 2/2 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Organism | Yes / correctly found agent omission | Yes / incorrectly credited absent output | 0/2 / 2/2 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Canonical sequence length | Yes / correctly found agent omission | Yes / incorrectly credited absent output | 0/2 / 2/2 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Reviewed status | Yes / correctly found agent omission | Yes / incorrectly credited absent output | 0/2 / 2/2 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Stopping condition | Yes / correctly rejected | Yes / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |

**Summary:** Both inputs clearly show all six UniProt fields, but the agent's final answer contains only a context-length API error. The screenshot verifier correctly withheld credit; the DOM scorer found the page values but incorrectly treated source visibility as if the agent had reported them.

- [Comparison](results/task_80_rerun/20260914T_task80_rerun_data_new/comparison.md)
- [Offline audit](results/task_80_rerun/20260914T_task80_rerun_data_new/evidence_error_audit/criterion_audit.json)

---

## Rerun batch result — Tasks 81–90

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Tasks | 10 | 10 |
| Criteria | 62 | 62 |
| Aggregate process points | 152/166 (91.6%) | 155/166 (93.4%) |
| Scoring tokens | 855,024 | 1,209,828 |
| Asymmetric source-evidence loss | 1/62 (1.6%) | 0/62 (0.0%) |
| Confirmed verifier evidence-use misses | 2/62 (3.2%) | 2/62 (3.2%) |

DOM used 354,804 more scoring tokens than screenshots, a 41.5% increase. The screenshot source gap was Task 87's discharge observation: none of the seven screenshots displayed its latest value and timestamp, while DOM state 6 preserved them. Screenshot verifier-use misses occurred in Task 81's etymology transcription and Task 84's planet-size unit glyph. DOM verifier-use misses occurred in Task 82's explicit White/Black player mapping and Task 83's `marine` environment state in DOM state 0.

Task 87 used an isolated staged metadata correction because its rerun `task_data.json` declared a canonical station URL while both recorded evidence streams began at the older equivalent USGS URL. No source dataset file was changed.

## Task 81 rerun — Lexical entry inspection

Task ID: `browser_task_081-lexical-entry-inspection-20260914T091034Z`  
Run: `20260914T_task81_rerun_data_new`  
Reused rubric SHA-256: `3e3d33a6f5ea8e4d4e131ac6c0c0240e9d1ffcfcdb84761486dde623915d2793`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/18 (94.4%) | 18/18 (100%) |
| Rubric / outcome | Pass / Fail | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 14 / 0 |
| Duration | 111.861 s | 113.730 s |
| Scoring tokens | 79,466 | 88,597 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| English Wiktionary section | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Four etymology stages | Yes / No; transliteration misread | Yes / Yes | 3/4 / 4/4 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Two IPA transcriptions | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| UK and US hyphenation | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Noun labels and plural | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both sources contain the same etymology chain. The screenshot judge read `al-ḵawārizmiyy` as `al-kawārizmiyy` and deducted a point even though the four requested language stages were correctly reported; DOM preserved the exact text.

- [Comparison](results/task_81_rerun/20260914T_task81_rerun_data_new/comparison.md)
- [Offline audit](results/task_81_rerun/20260914T_task81_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 82 rerun — Chess game result inspection

Task ID: `browser_task_082-chess-game-result-inspection-20260914T091145Z`  
Run: `20260914T_task82_rerun_data_new`  
Reused rubric SHA-256: `2080808bbccbe3444a4d2234275a959221a249014904721553df11db85c833d6`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 18/20 (90%) | 17/20 (85%) |
| Rubric / outcome | Pass / Fail | Pass / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 17 / 0 |
| Duration | 95.251 s | 157.078 s |
| Scoring tokens | 77,239 | 108,363 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Lichess game | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Time control, status, and speed | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Players, ratings, and changes | Yes / Yes | Yes / No; mapping overlooked | 5/5 / 4/5 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Result, winner, and moves | Partial / correctly limited | Partial / correctly limited | 3/4 / 3/4 | BOTH_CAUGHT |
| Constraints and stop | Yes / Yes | Yes / Yes | 4/5 / 4/5 | BOTH_CAUGHT |

**Summary:** The DOM contains explicit PGN fields for White/Black names, ratings, and rating changes, but the DOM judge said the color association was unproven. Both verifiers correctly treated the reported move count as unsupported by the displayed summary.

- [Comparison](results/task_82_rerun/20260914T_task82_rerun_data_new/comparison.md)
- [Offline audit](results/task_82_rerun/20260914T_task82_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 83 rerun — Marine taxonomy

Task ID: `browser_task_083-marine-taxonomy-20260914T091225Z`  
Run: `20260914T_task83_rerun_data_new`  
Reused rubric SHA-256: `220c4bbaf2708ab9dd1684f51db25d10dabb735d5bfbac6a340dd33641cd8d8e`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/16 (100%) | 15/16 (93.8%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 16 / 0 |
| Duration | 70.797 s | 94.718 s |
| Scoring tokens | 72,761 | 85,329 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct WoRMS record | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| AphiaID and scientific name | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Taxonomic status | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Genus and family | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Environment states | Yes / Yes | Yes / No; state 0 overlooked | 3/3 / 2/3 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** DOM state 0 explicitly contains `marine, ~~terrestrial~~`. The DOM judge relied only on state 1, where `marine` had scrolled out of the captured text, and incorrectly treated the affirmed marine state as unsupported.

- [Comparison](results/task_83_rerun/20260914T_task83_rerun_data_new/comparison.md)
- [Offline audit](results/task_83_rerun/20260914T_task83_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 84 rerun — Exoplanet discovery record

Task ID: `browser_task_084-exoplanet-discovery-record-20260914T091337Z`  
Run: `20260914T_task84_rerun_data_new`  
Reused rubric SHA-256: `86405cadd21cd92c4b3494960aa9c7d29a6466ae18e9c2484e3a5850e1ba7be8`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/14 (92.9%) | 14/14 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 29 / 0 |
| Duration | 83.721 s | 181.530 s |
| Scoring tokens | 83,626 | 150,538 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct archive block | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Source and stopping scope | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Stellar host | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Planet name | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Orbital separation | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Planet size | Yes / No; unit glyph misread | Yes / Yes | 1/2 / 2/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Discovery method | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Discovery year | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Reference | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Disposition | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

**Summary:** The identical screenshots visibly show the planet-size unit, but the screenshot analyses inconsistently read it as `R♃` and `R⊕`. DOM explicitly preserves U+2A01 (`R⨁`), matching the final answer.

- [Comparison](results/task_84_rerun/20260914T_task84_rerun_data_new/comparison.md)
- [Offline audit](results/task_84_rerun/20260914T_task84_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 85 rerun — Asteroid record

Task ID: `browser_task_085-asteroid-record-20260914T091428Z`  
Run: `20260914T_task85_rerun_data_new`  
Reused rubric SHA-256: `30a92a02be1e3cbe99d28189166d1f6ad37b51219014af78d6ca5d00a9d40407`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 20/20 (100%) | 20/20 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 26 / 0 |
| Duration | 86.718 s | 147.415 s |
| Scoring tokens | 81,047 | 133,161 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct JPL response | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Full name | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Orbit class | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Orbit epoch | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Absolute magnitude | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Diameter | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Hazardous flag | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Output scope | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both representations preserved every requested asteroid field and both verifiers recovered them correctly.

- [Comparison](results/task_85_rerun/20260914T_task85_rerun_data_new/comparison.md)
- [Offline audit](results/task_85_rerun/20260914T_task85_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 86 rerun — Cross-endpoint tide-station inspection

Task ID: `browser_task_086-cross-endpoint-tide-station-inspection-20260914T091532Z`  
Run: `20260914T_task86_rerun_data_new`  
Reused rubric SHA-256: `fb4c8bce0a8e20dfd3bf5838b788bee3eb643563bcc1244ad72ea94a9b686a37`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/15 (93.3%) | 13/15 (86.7%) |
| Rubric / outcome | Pass / Fail | Pass / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 17 / 0 |
| Duration | 88.281 s | 120.859 s |
| Scoring tokens | 75,592 | 87,632 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct NOAA sources | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Base-station fields | Partial; longitude absent / correctly limited | Partial; longitude absent / correctly limited | 3/4 / 3/4 | BOTH_CAUGHT |
| Linked-detail fields | Yes / Yes | Yes / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Exactness and stopping | Yes / Yes | Yes / Yes | 3/3 / 2/3 | BOTH_CAUGHT |

**Summary:** Both captures omit longitude and both verifiers identify its omission from the final answer. The one-point stopping-condition difference is penalty calibration, not evidence loss.

- [Comparison](results/task_86_rerun/20260914T_task86_rerun_data_new/comparison.md)
- [Offline audit](results/task_86_rerun/20260914T_task86_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 87 rerun — River monitoring

Task ID: `browser_task_087-river-monitoring-20260914T091633Z`  
Run: `20260914T_task87_rerun_data_new`  
Reused rubric SHA-256: `d6936e2ce99610f826aa5b76541407e58617a7aeee59041b81839605a3a8d94d`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6/13 (46.2%) | 8.5/13 (65.4%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 6 / 7 | 6 / 7 |
| LLM calls / retries | 22 / 0 | 28 / 0 |
| Duration | 112.198 s | 154.333 s |
| Scoring tokens | 148,803 | 166,233 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct USGS station | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Station name | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Latest discharge observation | No / correctly rejected | Yes / Yes | 0/3 / 2.5/3 | SCREENSHOT_EVIDENCE_MISSING |
| Latest gage-height observation | Yes / correctly rejected wrong answer | Yes / correctly rejected wrong answer | 0/3 / 0/3 | BOTH_CAUGHT |
| Series controls and stop | Yes / Yes | Yes / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

**Summary:** None of the seven screenshots shows the discharge value or timestamp. DOM state 6 contains `1680 ft^3/s - Sep 14, 2026 04:50:00 AM EDT`; both sources show that the agent's separately reported gage-height value was wrong.

- [Comparison](results/task_87_rerun/20260914T_task87_rerun_data_new/comparison.md)
- [Offline audit](results/task_87_rerun/20260914T_task87_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 88 rerun — Television season analysis

Task ID: `browser_task_088-television-season-analysis-20260914T091851Z`  
Run: `20260914T_task88_rerun_data_new`  
Reused rubric SHA-256: `d2fdb96b6054746d69994126190fbfb081d8e7b2a8f1e5d5a29a41f39492c3a2`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 22/22 (100%) | 22/22 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 32 / 0 |
| Duration | 83.095 s | 139.559 s |
| Scoring tokens | 84,476 | 193,305 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct season-one source | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Episode count | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Boundary episodes | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Maximum rating | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| All tied episodes | Yes / Yes | Yes / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both formats preserved the complete season-one episode list and both verifiers recovered the count, boundaries, and rating maximum correctly.

- [Comparison](results/task_88_rerun/20260914T_task88_rerun_data_new/comparison.md)
- [Offline audit](results/task_88_rerun/20260914T_task88_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 89 rerun — Postcode civic geography

Task ID: `browser_task_089-postcode-civic-geography-20260914T092026Z`  
Run: `20260914T_task89_rerun_data_new`  
Reused rubric SHA-256: `31a747cbdae946437d32ce2f8ae2ec81d89d1c630bd4ee658425f925b6985095`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/12 (100%) | 12/12 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 24 / 0 |
| Duration | 64.367 s | 132.427 s |
| Scoring tokens | 71,235 | 100,211 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Eleven requested fields | Yes / Yes | Yes / Yes | 6/6 / 6/6 | BOTH_CAUGHT |
| Source and field separation | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Exact formatting | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

**Summary:** Both sources contained the complete postcode result object and both verifiers recovered every requested field.

- [Comparison](results/task_89_rerun/20260914T_task89_rerun_data_new/comparison.md)
- [Offline audit](results/task_89_rerun/20260914T_task89_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 90 rerun — SI defining constants

Task ID: `browser_task_090-si-defining-constant-table-20260914T092152Z`  
Run: `20260914T_task90_rerun_data_new`  
Reused rubric SHA-256: `316185411a39bbb1b56e98d74c7dbc4d4714dc2022a91c98a872a1b80669e08f`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/16 (87.5%) | 15.5/16 (96.9%) |
| Rubric / outcome | Pass / Fail | Pass / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 11 / 0 | 14 / 0 |
| Duration | 106.663 s | 128.347 s |
| Scoring tokens | 80,779 | 96,459 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Defining constant 1 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Defining constant 2 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Defining constant 3 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Defining constant 4 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Defining constant 5 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Defining constant 6 | Yes / correctly found malformed exponent | Yes / correctly found malformed exponent | 0/2 / 1.5/2 | BOTH_CAUGHT |
| Defining constant 7 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Uncertainty statement | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both verifiers identified that the final answer collapsed `× 10^23` into `x 1023`. The 1.5-point difference is partial-credit severity, not evidence loss.

- [Comparison](results/task_90_rerun/20260914T_task90_rerun_data_new/comparison.md)
- [Offline audit](results/task_90_rerun/20260914T_task90_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Rerun batch result — Tasks 91–100

All ten comparisons completed successfully. Tasks 91–96 and 98–100 reused their original frozen rubrics. Task 97 had not been run previously, so one canonical rubric was generated once and then reused unchanged by both scoring pipelines.

| Batch metric | Screenshot | DOM model |
|---|---:|---:|
| Process points | 118.5/189 (62.7%) | 149/189 (78.8%) |
| Scoring calls | 152 | 243 |
| Scoring tokens | 988,033 | 1,249,493 |
| Source-evidence loss | 2/68 criteria (2.9%) | 0/68 criteria (0%) |
| Verifier-use misses | 1/68 criteria (1.5%) | 0/68 criteria (0%) |

DOM scoring used 261,460 more tokens (+26.5%). Every scoring run reported zero rubric-generation calls and zero retries. Task 97 rubric generation was recorded separately: 2 calls and 13,578 tokens. Of 68 audited criteria, 65 were `BOTH_CAUGHT`, two were `SCREENSHOT_EVIDENCE_MISSING`, and one was `SCREENSHOT_MISSED_DOM_CAUGHT`.

## Task 91 rerun — Cross-endpoint blockchain record

Task ID: `browser_task_091-cross-endpoint-blockchain-record-20260914T092331Z`  
Run: `20260914T_task91_rerun_data_new`  
Reused rubric SHA-256: `c594cfe6a041f7fc5690e1f8f8f8fc13f658d4743fcc53b14c72a5bb8e16ba8f`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 21/21 (100%) | 21/21 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 18 / 0 |
| Duration | 99.747 s | 130.805 s |
| Scoring tokens | 84,283 | 87,078 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Resolve hash with `/api/block-height/800000` | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Construct `/api/block/{hash}` URL | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Retrieve exact block record | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report requested block fields | Yes / Yes | Yes / Yes | 8/8 / 8/8 | BOTH_CAUGHT |
| Preserve exact values and distinctions | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop after requested fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

**Summary:** Both representations preserved the endpoint sequence, resolved hash, and complete block record. No evidence loss or verifier miss was confirmed.

- [Comparison](results/task_91_rerun/20260914T_task91_rerun_data_new/comparison.md)
- [Offline audit](results/task_91_rerun/20260914T_task91_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 92 rerun — Legislative roll-call inspection

Task ID: `browser_task_092-legislative-roll-call-inspection-20260914T092512Z`  
Run: `20260914T_task92_rerun_data_new`  
Reused rubric SHA-256: `a890f41cead00360c390707224de60ae9e238a221b233e127832d42e133e7ac6`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 3/30 (10.0%) | 28/30 (93.3%) |
| Rubric / outcome | Fail / Fail | Pass / Fail |
| Actions / states | 0 / 1 | 0 / 1 |
| LLM calls / retries | 10 / 0 | 30 / 0 |
| Duration | 92.275 s | 185.739 s |
| Scoring tokens | 71,547 | 144,081 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Clerk vote-details page | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Roll-call number | Yes / Yes | Yes / Yes | 0/2 / 2/2 | BOTH_CAUGHT |
| Bill number | Yes / Yes | Yes / Yes | 0/3 / 3/3 | BOTH_CAUGHT |
| Displayed date and time | Yes / Yes | Yes / Yes | 0/3 / 3/3 | BOTH_CAUGHT |
| Congress and session | Yes / Yes | Yes / Yes | 0/4 / 4/4 | BOTH_CAUGHT |
| Vote Question | Yes / Yes | Yes / Yes | 0/3 / 3/3 | BOTH_CAUGHT |
| Vote Type | Yes / Yes | Yes / Yes | 0/2 / 2/2 | BOTH_CAUGHT |
| Status | Yes / Yes | Yes / Yes | 0/2 / 2/2 | BOTH_CAUGHT |
| Aggregate vote totals | Yes / Yes | Yes / Yes | 0/6 / 6/6 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |

**Summary:** Both verifier analyses recovered the visible roll-call evidence. The score gap comes from different treatment of the failed final response, not evidence loss.

- [Comparison](results/task_92_rerun/20260914T_task92_rerun_data_new/comparison.md)
- [Offline audit](results/task_92_rerun/20260914T_task92_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 93 rerun — Supreme Court case analysis

Task ID: `browser_task_093-supreme-court-case-analysis-20260914T092635Z`  
Run: `20260914T_task93_rerun_data_new`  
Reused rubric SHA-256: `c49eaa21d4a9edd5fde2cc07d823703bf25320782831a5f91ca52c9c0b249dbb`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/16 (93.8%) | 16/16 (100%) |
| Rubric / outcome | Pass / Fail | Pass / Pass |
| Actions / states | 2 / 3 | 2 / 3 |
| LLM calls / retries | 14 / 0 | 25 / 0 |
| Duration | 103.976 s | 126.623 s |
| Scoring tokens | 89,226 | 114,952 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Brown v. Board page | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Docket and deciding Court | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Argued, reargued, and decided dates | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Displayed Question | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Decision split and prevailing side | Yes / Yes | Yes / Yes | 1/2 / 2/2 | BOTH_CAUGHT |
| Majority-opinion author | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| One-line holding | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

**Summary:** Both sources and analyses contain the same conclusion-card wording. The one-point difference is interpretation of whether “unanimous” satisfies the rubric's requested vote-count detail, not evidence loss.

- [Comparison](results/task_93_rerun/20260914T_task93_rerun_data_new/comparison.md)
- [Offline audit](results/task_93_rerun/20260914T_task93_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 94 rerun — EU regulation metadata

Task ID: `browser_task_094-eu-regulation-metadata-20260914T092727Z`  
Run: `20260914T_task94_rerun_data_new`  
Reused rubric SHA-256: `dd3cc482d818e64a490ac97ab93402bf440a770eca29c4aca54cb37af6c25049`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 0.5/15 (3.3%) | 1/15 (6.7%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 30 / 0 |
| Duration | 85.898 s | 194.201 s |
| Scoring tokens | 76,335 | 153,378 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| CELEX document number | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Official Journal citation | Yes / Yes | Yes / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Document-information view | Yes / Yes | Yes / Yes | 0.5/2 / 1/2 | BOTH_CAUGHT |
| Date of document | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Entry-into-force date | Yes / Yes | Yes / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Application date | Yes / Yes | Yes / Yes | 0/3 / 0/3 | BOTH_CAUGHT |

**Summary:** Both inputs expose the requested EUR-Lex metadata and both analyses recover it. The near-zero scores reflect the agent's error-only final answer; the half-point difference is partial-credit calibration.

- [Comparison](results/task_94_rerun/20260914T_task94_rerun_data_new/comparison.md)
- [Offline audit](results/task_94_rerun/20260914T_task94_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 95 rerun — Electricity generation mix

Task ID: `browser_task_095-electricity-generation-mix-20260914T093058Z`  
Run: `20260914T_task95_rerun_data_new`  
Reused rubric SHA-256: `7d5a5a273e604a77efabed606d75705b44c94f7111244a300e7c2a6f2108eb8c`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/12 (100%) | 12/12 (100%) |
| Rubric / outcome | Pass / Pass | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 17 / 0 |
| Duration | 76.410 s | 125.318 s |
| Scoring tokens | 77,576 | 88,524 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Exact requested interval | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Ordered fuel-percentage pairs | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Explicit zero-percentage fuels | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Percentage sum | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

**Summary:** Both representations preserve the complete selected interval and both verifiers recover every requested value correctly.

- [Comparison](results/task_95_rerun/20260914T_task95_rerun_data_new/comparison.md)
- [Offline audit](results/task_95_rerun/20260914T_task95_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 96 rerun — Medication label lookup

Task ID: `browser_task_096-medication-label-lookup-20260914T093144Z`  
Run: `20260914T_task96_rerun_data_new`  
Reused rubric SHA-256: `f654e9ea48250723c3b05e69989ab730a13e96913fc51272cf10af7248e24db5`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 10/20 (50.0%) | 13/20 (65.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 4 / 5 | 4 / 5 |
| LLM calls / retries | 18 / 0 | 35 / 0 |
| Duration | 104.759 s | 175.070 s |
| Scoring tokens | 127,392 | 197,794 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| DailyMed search attempt | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Correct Viatris label | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Label title and packager | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Initial U.S. Approval year | No / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Section 3 dosage form and four strengths | No / No | Partial / Yes | 0/4 / 2/4 | SCREENSHOT_EVIDENCE_MISSING |
| Route, active ingredient, and basis of strength | Absent / correctly limited | Absent / correctly limited | 0/4 / 0/4 | BOTH_CAUGHT |
| Scope and stopping condition | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

**Summary:** Screenshots never show the approval year or Section 3 strengths. DOM state 3 explicitly preserves `Initial U.S. Approval: 1996` and the 10 mg/20 mg entries plus a truncated 40 mg entry, but not all four strengths. Neither modality contains the requested Ingredients and Appearance fields.

- [Comparison](results/task_96_rerun/20260914T_task96_rerun_data_new/comparison.md)
- [Offline audit](results/task_96_rerun/20260914T_task96_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 97 rerun — DNS record resolution

Task ID: `browser_task_097-dns-record-resolution-20260914T093312Z`  
Run: `20260914T_task97_rerun_data_new`  
New frozen rubric SHA-256: `654d46cb9a7cf409c8356499671fa0c4612b4a5d7216ce8501de2bd35f6df7fc`  
Frozen rubric maximum: 16 points; effective scored denominator: 14 points because the result-heading criterion was marked not applicable in both modes.

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/14 (92.9%) | 10.5/14 (75.0%) |
| Rubric / outcome | Pass / Fail | Fail / Fail |
| Actions / states | 18 / 19 | 18 / 19 |
| LLM calls / retries | 38 / 0 | 42 / 0 |
| Duration | 149.527 s | 138.296 s |
| Scoring tokens | 209,946 | 186,012 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use Google form and perform MX lookup | Yes / Yes | Yes / Yes | 3/3 / 2/3 | BOTH_CAUGHT |
| Complete MX result heading | Absent / correctly skipped | Absent / correctly skipped | 0/2 / 0/2 | BOTH_CAUGHT |
| Status number and mnemonic | Partial / Yes | Partial / Yes | 1/2 / 1/2 | BOTH_CAUGHT |
| TC, RD, RA, AD, and CD flags | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Question name and numeric/mnemonic type | Partial / Yes | Partial / Yes | 2/2 / 1/2 | BOTH_CAUGHT |
| Type-15 MX answer records | Partial / Yes | Partial / Yes | 4/4 / 3.5/4 | BOTH_CAUGHT |

**Summary:** Both final states contain the same DNS JSON and both verifiers recover it. The response explicitly contains numeric type 15 but not the `MX` mnemonic; score differences reflect inference and penalty severity, not evidence loss. The unsupported `select` log alias was normalized to canonical `type` only in the isolated staged copies.

- [Comparison](results/task_97_rerun/20260914T_task97_rerun_data_new/comparison.md)
- [Offline audit](results/task_97_rerun/20260914T_task97_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 98 rerun — Solar/lunar ephemeris

Task ID: `browser_task_098-solar-lunar-ephemeris-20260914T093705Z`  
Run: `20260914T_task98_rerun_data_new`  
Reused rubric SHA-256: `5ce36d2eff177b2341d7b5591e6c6cffe5385ac37029b1673c22a7e23f7d5b0e`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 18/23 (78.3%) | 18/23 (78.3%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 16 / 0 |
| Duration | 103.580 s | 160.954 s |
| Scoring tokens | 88,525 | 94,196 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Coordinates in returned order | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Date fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Timezone fields | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Lunar phase summary | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Exact `closestphase` object | Yes / Yes | Yes / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| All Moon events | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| All Sun events | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Constraints and stopping | Yes / Yes | Yes / Yes | 1/3 / 1/3 | BOTH_CAUGHT |

**Summary:** Both captures contain the complete returned object. Both verifiers identify the final answer's incorrect `closestphase` date and extra fields; no evidence loss was found.

- [Comparison](results/task_98_rerun/20260914T_task98_rerun_data_new/comparison.md)
- [Offline audit](results/task_98_rerun/20260914T_task98_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 99 rerun — Consumer-product recall inspection

Task ID: `browser_task_099-consumer-product-recall-inspection-20260914T093848Z`  
Run: `20260914T_task99_rerun_data_new`  
Reused rubric SHA-256: `f525c5189c79ff820071b6074d55eef71ded39a4ffa09746ef1f5c23d9f8a218`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 11/20 (55.0%) | 12/20 (60.0%) |
| Rubric / outcome | Fail / Fail | Fail / Fail |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 14 / 0 |
| Duration | 100.644 s | 117.168 s |
| Scoring tokens | 87,664 | 89,891 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Retrieve RecallID 10000 | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Core recall fields | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Product entries | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Injury entries | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Retailer entries | Yes / Yes | Yes / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Manufacturer-country entries | Yes / Yes | Yes / Yes | 0/2 / 0/2 | BOTH_CAUGHT |
| Hazards, remedies, and options | Yes / Yes | Yes / Yes | 0/4 / 0/4 | BOTH_CAUGHT |
| Exact-transcription constraints | Yes / Yes | Yes / Yes | 0/3 / 1/3 | BOTH_CAUGHT |

**Summary:** Both formats preserve the arrays that the final answer incorrectly labels absent, and both verifier analyses identify those contradictions. The one-point difference is scoring severity, not evidence loss.

- [Comparison](results/task_99_rerun/20260914T_task99_rerun_data_new/comparison.md)
- [Offline audit](results/task_99_rerun/20260914T_task99_rerun_data_new/evidence_error_audit/criterion_audit.json)

## Task 100 rerun — Earthquake impact record

Task ID: `browser_task_100-earthquake-impact-record-inspection-20260914T093938Z`  
Run: `20260914T_task100_rerun_data_new`  
Reused rubric SHA-256: `09b96da6445a00cd31d5960838b5e2b955b3c8f8c71da1313c4436b2bfb6d3d3`

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/18 (83.3%) | 17.5/18 (97.2%) |
| Rubric / outcome | Pass / Fail | Pass / Pass |
| Actions / states | 1 / 2 | 1 / 2 |
| LLM calls / retries | 12 / 0 | 16 / 0 |
| Duration | 76.826 s | 118.235 s |
| Scoring tokens | 75,539 | 93,587 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Event title and coordinates | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Did You Feel It? community MMI | Yes / No | Yes / Yes | 0/2 / 2/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| ShakeMap estimated MMI | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Landslide estimate | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Liquefaction estimate | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Origin-card fields | Yes / Yes | Yes / Yes | 4/5 / 4.5/5 | BOTH_CAUGHT |

**Summary:** Screenshot 0 clearly displays the red `IX` badge in the Did You Feel It? card, but the screenshot verifier states that no legible MMI value is shown. DOM explicitly exposes `IX mmi` and its verifier uses it correctly. This is a confirmed screenshot-verifier miss, not screenshot-source loss. The Origin-card difference is partial-credit calibration.

- [Comparison](results/task_100_rerun/20260914T_task100_rerun_data_new/comparison.md)
- [Offline audit](results/task_100_rerun/20260914T_task100_rerun_data_new/evidence_error_audit/criterion_audit.json)
