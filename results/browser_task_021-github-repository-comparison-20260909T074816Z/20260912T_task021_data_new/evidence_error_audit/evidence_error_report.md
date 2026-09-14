# Evidence-Item Audit: browser_task_021-github-repository-comparison-20260909T074816Z

| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |
|---|---|---|---|---|---|---|
| C0 | vllm stars, forks, and open-issues counts | 91.3k stars; 21.9k forks; 2.4k open issues | Present (screenshot0.png: Star 91.3k; Fork 21.9k; Issues 2.4k); verifier caught | Present (dom_model0.txt m0:L43-L50; dom_model0.txt m0:L47-L50; dom_model0.txt m0:L80-L89); verifier caught | `BOTH_CAUGHT` | TIE |
| C1 | llama.cpp stars, forks, and open-issues counts | 127.6k stars; 22.9k forks; 896 open issues | Present (screenshot1.png: 127.6k stars; Fork 22.9k; Issues 896); verifier caught | Present (dom_model1.txt m1:L42-L49; dom_model1.txt m1:L46-L49; dom_model1.txt m1:L79-L88); verifier caught | `BOTH_CAUGHT` | TIE |
| C2 | sglang stars, forks, and open-issues counts | 35.7k stars; 8.7k forks; 862 open issues | Present (screenshot2.png: Star 35.7k; Fork 8.7k; Issues 862); verifier caught | Present (dom_model2.txt m2:L42-L49; dom_model2.txt m2:L46-L49; dom_model2.txt m2:L76-L85); verifier caught | `BOTH_CAUGHT` | TIE |
| C3 | Underlying nine repository metrics used in the final-answer table | Three correctly aligned metrics for each repository | Present (screenshot0.png: vllm metrics; screenshot1.png: llama.cpp metrics; screenshot2.png: sglang metrics); verifier caught | Present (dom_model0.txt m0:L43-L50; dom_model1.txt m1:L42-L49; dom_model2.txt m2:L42-L49); verifier caught | `BOTH_CAUGHT` | TIE |
| C4 | Star counts sufficient to verify descending repository ranking | llama.cpp 127.6k > vllm 91.3k > sglang 35.7k | Present (screenshot0.png: 91.3k stars; screenshot1.png: 127.6k stars; screenshot2.png: 35.7k stars); verifier caught | Present (dom_model0.txt m0:L80-L83; dom_model1.txt m1:L79-L82; dom_model2.txt m2:L76-L79); verifier caught | `BOTH_CAUGHT` | TIE |
| C5 | Unauthenticated, read-only browsing with no prohibited interaction | Signed out; only navigation actions; no repository modification | Present (screenshot0.png: Sign in; Sign up; screenshot2.png: Sign in; Sign up); verifier caught | Present (dom_model0.txt m0:L42-L46; dom_model1.txt m1:L41-L45; dom_model2.txt m2:L41-L45); verifier caught | `BOTH_CAUGHT` | TIE |

## Metrics

- Evidence items present in both: 6.
- Screenshot catch rate on common evidence: 6/6 (100.0%).
- DOM catch rate on common evidence: 6/6 (100.0%).
- DOM recovery of screenshot misses: 0/0 (N/A%).
- Screenshot recovery of DOM misses: 0/0 (N/A%).
