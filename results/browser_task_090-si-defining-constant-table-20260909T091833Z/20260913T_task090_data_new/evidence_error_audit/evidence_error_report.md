# Evidence-Item Audit: browser_task_090-si-defining-constant-table-20260909T091833Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Report defining constant #1 (as displayed in BIPM table) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: ΔνCs \| 9 192 631 770 \| Hz); verifier caught | Present (dom_model1.txt m1:L9-L9; dom_model1.txt m1:L25-L25); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report defining constant #2 (as displayed in BIPM table) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: c \| 299 792 458 \| m s⁻¹); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Report defining constant #3 (as displayed in BIPM table) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: h \| 6.626 070 15 × 10⁻³⁴ \| J s); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C3 | Report defining constant #4 (as displayed in BIPM table) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: e \| 1.602 176 634 × 10⁻¹⁹ \| C); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C4 | Report defining constant #5 (as displayed in BIPM table) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: k \| 1.380 649 × 10⁻²³ \| J K⁻¹); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C5 | Report defining constant #6 (as displayed in BIPM table) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Nₐ \| 6.022 140 76 × 10²³ \| mol⁻¹); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C6 | Report defining constant #7 (as displayed in BIPM table) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Kcd \| 683 \| lm W⁻¹); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C7 | Report BIPM uncertainty statement about the numerical values | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: The numerical values of the seven defining constants have no uncertainty.); verifier caught | Present (dom_model1.txt m1:L37-L37); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 2.
- Screenshot catch rate on common evidence: 2/2 (100.0%).
- DOM catch rate on common evidence: 2/2 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
