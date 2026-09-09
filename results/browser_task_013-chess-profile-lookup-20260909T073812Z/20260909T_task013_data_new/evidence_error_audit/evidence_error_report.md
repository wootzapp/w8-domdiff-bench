# Evidence Error Audit: browser_task_013-chess-profile-lookup-20260909T073812Z

Run: `20260909T_task013_data_new`  
Rubric SHA-256: `1db9087c848d5ad336f7c063babff47c82c0d673cec6184a853a62ab5e162c17`

| Criterion | Screenshot evidence reported | DOM evidence reported | Screenshot points | DOM points | Review | Classification |
|---|---|---|---:|---:|---|---|
| 0: Access Magnus Carlsen’s Chess.com profile page (without signing in) | Screenshot 3 (latest) shows the Chess.com member profile page for username “MagnusCarlsen” with GM badge and Overview tab, and the sidebar includes “Sign Up” / “Log In,” indicating not signed in. This is direct evidence the correct profi... | LATEST relevant evidence is DOM_MODEL_STATE_INDEX: 2, which shows URL https://www.chess.com/member/magnuscarlsen with title “GM Magnus Carlsen (MagnusCarlsen) - Chess Profile - Chess.com” and logged-out controls (“Sign Up”, “Log In”). Ea... | 3.0/3 | 3.0/3 | pending | PENDING |
| 1: Record Blitz rating exactly as displayed | Screenshot 3 (latest) shows the Blitz card displaying “3316” with a red change indicator “↓ 63.” Screenshot 2 (earlier) showed a different context (top-players page) with “2860 Blitz,” but per the chronology and task focus, the member pr... | LATEST relevant evidence is DOM_MODEL_STATE_INDEX: 2 on https://www.chess.com/member/magnuscarlsen. It includes a rating block/link text “Blitz 3316 …” (e.g., link [313] shows “Blitz 3316 63 Created with Highcharts 9.1.2”), and visible c... | 3.0/4 | 4.0/4 | pending | PENDING |
| 2: Record Bullet rating exactly as displayed | Screenshot 3 (latest) shows the Bullet card displaying “3184” with a red change indicator “↓ 73.” No Bullet value is shown in earlier screenshots; the member profile in Screenshot 3 provides the needed evidence. | LATEST relevant evidence is DOM_MODEL_STATE_INDEX: 2, where link [322] text shows “Bullet 3184 73 Created with Highcharts 9.1.2” and the ratings area includes Bullet value 3184. | 3.0/4 | 4.0/4 | pending | PENDING |
| 3: Respect constraints: no sign-in and no interaction with another player; stop after recording ratings | Screenshot 3 (latest) shows logged-out state (“Sign Up” / “Log In” visible) and no evidence of any interaction actions (no challenge/message flow shown). Action history indicates only clicking through pages and dismissing the cookie banner. | DOM_MODEL_STATE_INDEX: 2 shows the profile page with “Sign Up”/“Log In” (logged out) and no evidence of challenge/message actions. Action history only includes clicking “Reject All” (cookie banner) and clicking the “MagnusCarlsen” profil... | 2.0/2 | 2.0/2 | not_required | PENDING |

## Recovery metrics

- DOM recovery of confirmed screenshot misses: 0/0 (N/A%).
- Screenshot recovery of confirmed DOM misses: 0/0 (N/A%).
- Classified criteria: 0/4.
