# Evidence-Item Audit: browser_task_081-lexical-entry-inspection-20260909T090959Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | Use only the English section of the Wiktionary entry | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: English; Etymology; Pronunciation; Noun); verifier caught | Present (dom_model1.txt m1:L43-L43); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | Report the four prose-etymology source-language stages (Middle English back to Arabic) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: From Middle English … from Anglo-Norman … from Medieval Latin … from Arabic); verifier caught | Absent | `DOM_EVIDENCE_MISSING` | NOT_COMPARABLE |
| C2 | Provide the first IPA transcription and the Standard Southern British IPA transcription (distinct) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: IPA: /ˈælɡəɹɪðm̩/; (Standard Southern British) IPA: /ˈalɡəɹɪð(ə)m/); verifier caught | Present (dom_model1.txt m1:L44-L44); verifier missed | `DOM_MISSED_SCREENSHOT_CAUGHT` | SCREENSHOT |
| C3 | Report UK and US hyphenation | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: Hyphenation UK: al‧gorithm, US: al‧go‧rithm); verifier caught | Present (dom_model1.txt m1:L44-L44); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Report noun countability label(s) and plural form | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot0.png: algorithm (countable and uncountable, plural algorithms)); verifier caught | Present (dom_model1.txt m1:L48-L48); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Stopping condition respected (no extra, unrequested content) | Criterion-relevant evidence sufficient to evaluate the agent response | Present (screenshot1.png: Additional noun definitions remain on the page but are not included in the final answer); verifier caught | Present (dom_model1.txt m1:L50-L50); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 5.
- Screenshot catch rate on common evidence: 5/5 (100.0%).
- DOM catch rate on common evidence: 4/5 (80.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 1/1 (100.0%).
