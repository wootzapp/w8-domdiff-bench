# Evidence-Item Audit: browser_task_030-course-detail-inspection-20260909T080218Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access the specified Coursera course page without signing in/enrolling (or record unavailability state) | Criterion-relevant browser state and final task claim | Present (screenshot1.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model0.txt m0:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Record instructor name(s) | Criterion-relevant browser state and final task claim | Present (screenshot0.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model1.txt m1:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Record institution/partner | Criterion-relevant browser state and final task claim | Present (screenshot0.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model1.txt m1:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Record number of modules/weeks shown in the syllabus | Criterion-relevant browser state and final task claim | Present (screenshot0.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model1.txt m1:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Determine whether a free audit option is available | Criterion-relevant browser state and final task claim | Present (screenshot0.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model0.txt m0:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Stop after recording overview and syllabus details (respect stopping condition and constraints) | Criterion-relevant browser state and final task claim | Present (screenshot1.png: Criterion-relevant visible browser state); verifier caught | Present (dom_model1.txt m1:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 6.
- Screenshot catch rate on common evidence: 6/6 (100.0%).
- DOM catch rate on common evidence: 6/6 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
