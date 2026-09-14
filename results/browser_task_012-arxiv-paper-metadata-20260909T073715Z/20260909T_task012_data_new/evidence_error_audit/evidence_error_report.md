# Evidence Error Audit: browser_task_012-arxiv-paper-metadata-20260909T073715Z

Run: `20260909T_task012_data_new`  
Rubric SHA-256: `0ba8db17cb7a714de473b135020ece47b0a8098f986ce2fc4f86e50d3dde449f`

| Criterion | Screenshot evidence reported | DOM evidence reported | Screenshot points | DOM points | Review | Classification |
|---|---|---|---:|---:|---|---|
| 0: Attempt to access the correct arXiv entry (1706.03762) using arXiv pages | Action History shows the agent started on https://arxiv.org/abs/1706.03762 and performed a scroll. Screenshots (latest is Screenshot 2) show the arXiv abstract page with identifier “arXiv:1706.03762 [cs.CL]” and the “Submission history” ... | DOM-model state 1 (latest) shows URL https://arxiv.org/abs/1706.03762 with page title "[1706.03762] Attention Is All You Need" and a visible "Submission history" section listing versions. Action history includes a scroll on that page. | 2.0/2 | 2.0/2 | not_required | PENDING |
| 1: Comply with constraints (no sign-in; do not download or edit the paper) | Screenshots show only the arXiv abstract page with links (e.g., “View PDF”) and a “Log in” link visible; no indication of logging in or opening/downloading the PDF. Action History includes only a scroll action. | Action history shows only a scroll action. DOM-model state 1 (latest) shows the abs page with a "View PDF" link present but no evidence of it being clicked; no sign-in UI is shown. | 1.0/1 | 1.0/1 | pending | PENDING |
| 2: Report total number of versions | Screenshots (latest is Screenshot 2) show “Submission history” entries labeled consecutively from [v1] through [v7], indicating 7 versions total. | DOM-model state 1 (latest) "Submission history" explicitly lists [v1] through [v7], indicating 7 total versions. Agent output states: "Total number of versions: 7." | 3.0/3 | 3.0/3 | not_required | PENDING |
| 3: Record the exact publication date string for version 1 | Screenshots (latest is Screenshot 2) show the v1 submission history line: “[v1] Mon, 12 Jun 2017 17:57:34 UTC (1,102 KB)”. The agent output includes this exact string. | DOM-model state 1 (latest) shows the v1 submission history line: "[v1] Mon, 12 Jun 2017 17:57:34 UTC (1,102 KB)". Agent output includes: "Mon, 12 Jun 2017 17:57:34 UTC (1,102 KB)" (and also an extra, less-supported header-style string). | 3.0/3 | 3.0/3 | pending | PENDING |
| 4: Record the exact publication date string for the latest version | Screenshots (latest is Screenshot 2) show the latest version v7 line: “[v7] Wed, 2 Aug 2023 00:41:18 UTC (1,124 KB)”. The agent output includes this exact string. | DOM-model state 1 (latest) shows the latest version line: "[v7] Wed, 2 Aug 2023 00:41:18 UTC (1,124 KB)". Agent output includes: "Wed, 2 Aug 2023 00:41:18 UTC (1,124 KB)" (and also an extra header-style string). | 3.0/3 | 3.0/3 | pending | PENDING |
| 5: Stopping condition satisfied (only version count + both dates, then stop) | Agent’s predicted final answer includes the required three items but also includes additional header-summary date strings and extra labeling beyond the minimal stopping condition. | Agent final output includes the requested version count and the v1 and latest-version date strings, but also includes additional redundant header-summary date lines. DOM-model state 1 confirms the minimal required items are present on-pa... | 0.5/1 | 0.5/1 | not_required | PENDING |

## Recovery metrics

- DOM recovery of confirmed screenshot misses: 0/0 (N/A%).
- Screenshot recovery of confirmed DOM misses: 0/0 (N/A%).
- Classified criteria: 0/6.
