# Evidence-Item Audit: browser_task_070-unicode-ideograph-inspection-20260909T085438Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Access the Unicode Unihan record for U+4E00 (or clearly report access failure) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Access the Unicode Unihan record for U+4E00 (or clearly report access failure)); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Respect task constraints (sole source, exact copying, no extra fields, stop at requested fields) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Respect task constraints (sole source, exact copying, no extra fields, stop at requested fields)); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | Record code-point identity and displayed glyph | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Record code-point identity and displayed glyph); verifier caught | Present (dom_model0.txt m0:L2-L2); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Record numeric and encoding fields (decimal, UTF-8, UTF-16) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Record numeric and encoding fields (decimal, UTF-8, UTF-16)); verifier caught | Present (dom_model0.txt m0:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Record total stroke count | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Record total stroke count); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Record definition | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Record definition); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C6 | Record Mandarin reading | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Record Mandarin reading); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C7 | Record Japanese On reading | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Record Japanese On reading); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C8 | Record Korean reading | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Record Korean reading); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |
| C9 | Record Vietnamese reading | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Record Vietnamese reading); verifier caught | Present (dom_model1.txt m1:L1-L1); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 10.
- Screenshot catch rate on common evidence: 10/10 (100.0%).
- DOM catch rate on common evidence: 10/10 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
