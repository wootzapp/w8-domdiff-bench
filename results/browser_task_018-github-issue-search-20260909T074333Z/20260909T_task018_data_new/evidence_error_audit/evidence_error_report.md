# Evidence Error Audit: browser_task_018-github-issue-search-20260909T074333Z

Run: `20260909T_task018_data_new`  
Rubric SHA-256: `1070898bbbc7964a59520ec21c339408ad17d6faca93bcb2306f1ef43249e9a0`

| Criterion | Screenshot evidence reported | DOM evidence reported | Screenshot points | DOM points | Review | Classification |
|---|---|---|---:|---:|---|---|
| 0: Access GitHub issues for huggingface/transformers and verify the date basis for the 30-day window | Latest relevant evidence: Screenshot 3 shows a date dropdown with a specific date option “September 9, 2026,” which can serve as the browser/UI current date basis. Earlier screenshots don’t show a current-date cue. | DOM-model state 2 (latest relevant showing date context) explicitly shows a visible date reference in the UI: “September 9, 2026” (along with Today/Yesterday). It also shows the repo issues page title “Issues · huggingface/transformers ·... | 1.0/1 | 1.0/1 | pending | PENDING |
| 1: Apply exact GitHub issue search filters (open + label: bug + created in last 30 days) for huggingface/transformers | Latest relevant evidence: Screenshot 4 shows the query in the issues search box: `is:issue state:open is:issue state:open label:bug created:>=2026-08-10` on the huggingface/transformers Issues page. Screenshot 3 also shows the same query... | DOM-model state 3 (latest) shows the URL includes the query parameters with: `is:issue state:open is:issue state:open label:bug created:>=2026-08-10`, and the Search Issues box contains the same text. The page is under `https://github.co... | 4.0/4 | 4.0/4 | not_required | PENDING |
| 2: Report total count of matching issues | Latest relevant evidence: Screenshot 4 shows the filtered tab counts “Open 17” and “Closed 14,” indicating the matching open-issues count under the active query. | DOM-model state 3 (latest) shows the results header/tab count as `Open 17 (17)` for the filtered view. | 2.0/2 | 2.0/2 | pending | PENDING |
| 3: Provide the three newest matching issue records (issue number + title) | Latest relevant evidence: Screenshot 4 shows the top of the filtered, ‘Newest’ list with the first three issues as #48633, #48630, #48626 and their titles exactly as in the agent output. (Screenshot 3 had some ambiguity, but Screenshot 4... | DOM-model state 3 (latest) shows the top three results (in order) with issue numbers and titles: #48633 “use_gqa_in_sdpa doesn't check GPU architecture: up to 28% slower decode on pre-sm80 GPUs”; #48630 “GPTNeoXJapanese crashes for any r... | 2.5/3 | 3.0/3 | pending | PENDING |
| 4: Comply with constraints (no sign-in; no issue interactions; stop after verification) | Latest relevant evidence: Screenshot 4 shows ‘Sign in’/‘Sign up’ buttons (not signed in) and only searching/filtering activity; no UI indicating commenting/labeling/closing/creating issues was used. Action history shows only clicks/types... | DOM-model state 3 (latest) shows a visible “Sign in” link and “You must be signed in…” notices, consistent with not being signed in. Action history shows only search-box interactions (click/type/search) and no issue interactions (no comm... | 1.0/1 | 1.0/1 | not_required | PENDING |

## Recovery metrics

- DOM recovery of confirmed screenshot misses: 0/0 (N/A%).
- Screenshot recovery of confirmed DOM misses: 0/0 (N/A%).
- Classified criteria: 0/5.
