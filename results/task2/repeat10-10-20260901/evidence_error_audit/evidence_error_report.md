# Evidence-Item Audit: viewport-modern-2-job-listing-extraction-20260829T074612Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Search query targets Applied Scientist in Redmond, Washington | Applied Scientist; Redmond, Washington | Present (screenshot4.png: Applied Scientist / Redmond, Washington); verifier caught | Present (dom_model12.txt m12:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C0 | Search reaches results or a relevant Applied Scientist job page | Relevant Microsoft Careers results/listing reached | Present (screenshot4.png: 25 jobs; Applied Scientist II / Senior Applied Scientist - Responsible AI (CoreAI)); verifier caught | Present (dom_model12.txt m12:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | A specific Applied Scientist listing is opened | Applied Scientist II / Senior Applied Scientist - Responsible AI (CoreAI) | Present (screenshot4.png: Applied Scientist II / Senior Applied Scientist - Responsible AI (CoreAI)); verifier caught | Present (dom_model12.txt m12:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | The opened listing explicitly includes Redmond, Washington | United States, Washington, Redmond + 4 more | Present (screenshot4.png: United States, Washington, Redmond + 4 more); verifier caught | Present (dom_model4.txt m4:L28-L30); verifier missed | `DOM_MISSED_SCREENSHOT_CAUGHT` | SCREENSHOT |
| C2 | Job number from the opened listing | 200017828 | Absent | Present (dom_model4.txt m4:L34-L36); verifier caught | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Work-site arrangement from the opened listing | 3 days / week in-office | Absent | Present (dom_model4.txt m4:L82-L84); verifier caught | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C4 | Two distinct responsibilities supported by the opened listing | Two explicit or concrete duty statements | Absent | Absent | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C5 | Two distinct explicitly preferred qualifications | Two qualifications clearly identified as preferred | Absent | Absent | `SCREENSHOT_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C6 | Browsing remains on one listing without entering sign-in, application, or form-submission UI | Constraint-respecting listing-view sequence | Present (screenshot12.png: Similar jobs; Microsoft Careers footer); verifier caught | Present (dom_model12.txt m12:L1-L2); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 5.
- Screenshot catch rate on common evidence: 5/5 (100.0%).
- DOM catch rate on common evidence: 4/5 (80.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 1/1 (100.0%).
