# Screenshot vs DOM-model comparison: Task1–Task25

This is the cumulative comparison report for the paired benchmark tasks. Each completed task must use the same canonical frozen rubric, task, semantic trajectory, final answer, judge models, endpoint configuration, and scoring settings for both verifier modes.

Rubric-generation usage is reported separately and is never included in either verifier's scoring-token total. A task remains `Pending` until both verifier artifacts and the comparison receipt exist.

## Results summary

| Task | Status | Screenshot score | DOM-model score | Screenshot tokens | DOM-model tokens | DOM token change | Why DOM scored higher/lower/same | Result |
|---|---|---:|---:|---:|---:|---:|---|---|
| task1 | Complete | 9/15 (60%) | 9/15 (60%) | 122,609 | 118,998 | -3,611 (-2.95%) | Same total, but different criterion attribution: DOM lost 1 point on Best-sellers navigation and gained 1 point on product metadata. | [Report](task1/20260829T150935Z/comparison.md) |
| task2 | Complete | 11/20 (55%) | 13/20 (65%) | 180,312 | 163,442 | -16,870 (-9.36%) | DOM gained 4 points from explicit job-number/work-site text, but lost 2 points where screenshots better established the listing location and one preferred qualification. | [Report](task2/20260829T152115Z/comparison.md) |
| task3 | Complete | 14/18 (77.8%) | 14/18 (77.8%) | 127,838 | 132,865 | +5,027 (+3.93%) | Same criterion totals, but complementary evidence: screenshots proved the `Latest` status while DOM exposed the exact release timestamp; both only indirectly verified the documentation link. | [Report](task3/20260829T153037Z/comparison.md) |
| task4 | Complete | 10/18 (55.6%) | 13/18 (72.2%) | 69,340 | 76,709 | +7,369 (+10.63%) | DOM scored 3 points higher because its final state exposed the Artemis II date, destination/type, and objective; the screenshot evidence stopped at the general Artemis hub and did not show those fields. | [Report](task4/20260829T153936Z/comparison.md) |
| task5 | Complete | 2/17 (11.8%) | 12/17 (70.6%) | 77,006 | 79,339 | +2,333 (+3.03%) | DOM explicitly captured Google's unusual-traffic/CAPTCHA page; the screenshots ended on the search homepage, so only DOM could substantiate the blocker and receive cascading blocker credit. | [Report](task5/20260829T154829Z/comparison.md) |
| task6 | Complete | 6/14 (42.9%) | 6/14 (42.9%) | 174,208 | 162,111 | -12,097 (-6.94%) | Same total with shifted attribution: DOM gave 1 point for reaching a page containing Blitz-related rating evidence but deducted 1 stopping-condition point; screenshots assigned those points in the opposite way. | [Report](task6/20260829T155603Z/comparison.md) |
| task7 | Complete | 13/13 (100%) | 13/13 (100%) | 60,071 | 215,947 | +155,876 (+259.49%) | Exact scoring agreement: both modalities proved the repository, license, likes, gated notice, and constraints. DOM cost exploded because 17 response-validation repeats and 2 fallback invocations expanded it to 37 calls. | [Report](task7/20260829T160213Z/comparison.md) |
| task8 | Complete | 12/13 (92.3%) | 9.5/13 (73.1%) | 83,228 | 152,776 | +69,548 (+83.56%) | Screenshots visibly showed the validation dropdown option and its `10.6k rows`; DOM states never rendered validation as active or exposed that option text as page evidence, so DOM lost validation and stopping-condition points. | [Report](task8/20260829T160750Z/comparison.md) |
| task9 | Complete | 3/10 (30%) | 9/10 (90%) | 80,481 | 104,775 | +24,294 (+30.19%) | DOM's final state exposed the applied query, 12-result count, and three newest matching issues; the screenshots did not visibly confirm the filtered result set, so Microsoft rejected those reported facts. | [Report](task9/20260829T161750Z/comparison.md) |
| task10 | Complete | 8/14 (57.1%) | 12/14 (85.7%) | 65,254 | 87,944 | +22,690 (+34.77%) | DOM exposed the three requested highlight bullets while the screenshots showed only the release table of contents. Both modes rejected the agent's incorrect release date, so both outcome checks failed despite DOM passing the rubric threshold. | [Report](task10/20260829T162608Z/comparison.md) |
| task11 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task12 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task13 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task14 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task15 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task16 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task17 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task18 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task19 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task20 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task21 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task22 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task23 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task24 | Pending | — | — | — | — | — | Pending evaluation. | — |
| task25 | Pending | — | — | — | — | — | Pending evaluation. | — |

## Task1

Task ID: `viewport-modern-1-cross-site-research-20260829T074513Z`

- Frozen rubric: `fac623938e43e710f25c70350a0989e6d1ce38338113f171c5de38c6529c6a15`
- Denominator: 15 points across 4 criteria
- Screenshot: 9/15, outcome `false`, 22 calls, 122,609 scoring tokens
- DOM-model: 9/15, outcome `false`, 24 calls, 118,998 scoring tokens
- Rubric generation: 2 calls and 12,460 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 4

### Why the criterion scores differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Navigate to Best sellers | 1/3 | 0/3 | Neither modality explicitly showed a Best-sellers heading. Microsoft still analyzed its top screenshots and awarded partial credit for reaching the Xbox Games page. DOM states scored at most 1 for relevance and were all removed by the DOM-only `>3` relevance filter, so Criterion 0 received no DOM evidence analysis. |
| Open a game product page from Best sellers | 2/3 | 2/3 | Both proved that the Madden NFL 27 product page was opened, but neither proved that the game came from a Best-sellers list. |
| Report publisher, developer, and release date | 3/6 | 4/6 | Screenshots showed the publisher value `Electronic Arts`, making the final answer's claim that publisher was unavailable incorrect. DOM-model text showed the `Published by` label but omitted the value, so the DOM judge treated the agent's refusal to invent it more favorably. |
| Respect constraints | 3/3 | 3/3 | Both modalities confirmed no sign-in, purchase, or download. |

### Task1 comparison caveat

The DOM runner received `--min-relevance-threshold 3`, while the unchanged Microsoft runner used its default threshold of 0. This asymmetric filtering—not stronger screenshot proof of Best sellers—caused the Criterion 0 difference. Task1 should remain marked with this caveat when interpreting modality parity.

## Task2

Task ID: `viewport-modern-2-job-listing-extraction-20260829T074612Z`

- Frozen rubric: `a7e99908c99f87f84cb13fa8158e51519d08892dd942eae54246ec663b721b48`
- Denominator: 20 points across 7 criteria
- Screenshot: 11/20, outcome `false`, 29 calls, 163,886 prompt + 16,426 completion = 180,312 scoring tokens
- DOM-model: 13/20, outcome `false`, 35 calls, 146,589 prompt + 16,853 completion = 163,442 scoring tokens
- DOM-model token change: -16,870 tokens (-9.36%)
- Rubric generation: 2 calls and 13,452 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 6; fallback invocations: 0
- DOM evidence coverage: all 13 states loaded, no context omissions; state 3 had a missing-title warning

### Why the criterion scores differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Search Microsoft Careers for Applied Scientist in Redmond | 3/3 | 3/3 | Both modalities established the intended search and arrival at relevant results. |
| Open one relevant listing | 3/3 | 2/3 | Screenshots visibly showed Redmond in the selected listing's location line. DOM confirmed the Applied Scientist listing title, but Redmond appeared only in the search URL rather than the listing's own visible location field. |
| Report job number | 0/2 | 2/2 | DOM state 4 explicitly contained `Job number 200017828`, matching the final answer. The screenshots selected for analysis did not visibly expose a job number. |
| Report work-site arrangement | 0/2 | 2/2 | DOM state 4 explicitly contained `Work site 3 days / week in-office`, matching the answer's hybrid/three-days wording. The screenshots did not visibly show this field. |
| Extract two responsibilities | 0/3 | 0/3 | Neither modality ultimately verified two responsibilities. Screenshot reality checking overturned an earlier blocker-based award because visible bullets contradicted the claim that no content rendered, but those bullets were not clearly responsibilities. |
| Extract two preferred qualifications | 1/3 | 0/3 | Screenshots showed one preference-style statement (`Responsible AI is a big plus`), earning partial credit. No preferred-qualification text was present in the selected DOM evidence. |
| Respect constraints | 4/4 | 4/4 | Both showed browsing/scrolling only, with no sign-in, application, or form submission. |

### Task2 comparison caveats

The task's staged initial URL was normalized identically in both benchmark inputs before rubric generation/scoring so it matched the first DOM state. The DOM run again used the configured `--min-relevance-threshold 3`, whereas the unchanged Microsoft runner retained its default selection behavior. This did not create the principal score difference here: the decisive modality gap was that DOM state 4 exposed labeled job metadata that was not legible in the screenshot evidence, while screenshots exposed location and one preference-style bullet that the DOM-model states did not.

## Task3

Task ID: `viewport-modern-3-software-release-research-20260829T074724Z`

- Frozen rubric: `5fd39f2558fe7db4286f211ce92d185171d7ea648b004a8ed7c55f8c0bcb7db1`
- Denominator: 18 points across 5 criteria
- Screenshot: 14/18, outcome `false`, 20 calls, 117,763 prompt + 10,075 completion = 127,838 scoring tokens
- DOM-model: 14/18, outcome `false`, 22 calls, 122,093 prompt + 10,772 completion = 132,865 scoring tokens
- DOM-model token change: +5,027 tokens (+3.93%)
- Rubric generation: 2 calls and 12,953 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 2; fallback invocations: 0
- DOM evidence coverage: all 7 states loaded, approximately 10,786 evidence tokens, no context omissions or source warnings

### Why the criterion scores agreed or differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Navigate to Playwright Releases | 3/3 | 3/3 | Both showed the correct Microsoft Playwright Releases area and unauthenticated access. |
| Identify newest non-preview release and metadata | 2/4 | 2/4 | The modalities supported different halves of the claim. Screenshots showed `v1.62.1` marked `Latest` but only a relative date. DOM showed the exact `30 Jul 16:35` timestamp but did not expose enough list ordering or preview badges to prove it was the newest non-preview release. |
| Extract three release-note changes | 4/4 | 4/4 | Both explicitly showed the three reported v1.62.1 bug-fix entries. |
| Verify one change with official documentation | 2/4 | 2/4 | Both proved that official Playwright `page.evaluate` documentation was consulted, but the visible documentation only established the general argument contract and did not directly confirm the specific branded-primitive regression fix. |
| Respect constraints | 3/3 | 3/3 | Both supported unauthenticated, read-only browsing with no issue, PR, comment, or file-changing action. |

### Task3 comparison caveat

Although the total and per-criterion scores match, the evidence is not equivalent: screenshot and DOM supplied complementary proof for release metadata. DOM-model also cost 5,027 more tokens because it made two additional judge calls, corresponding to its two response-validation repeats. The DOM runner retained the configured `--min-relevance-threshold 3`; no material criterion loss was attributable to that threshold in this run.

## Task4

Task ID: `viewport-modern-4-nasa-mission-lookup-20260829T074852Z`

- Frozen rubric: `0f9dc5356a1403cc2467a32f218430edb430748c64ba1e9f1948b7a8ea05a6a8`
- Denominator: 18 points across 3 criteria
- Screenshot: 10/18, outcome `false`, 12 calls, 63,158 prompt + 6,182 completion = 69,340 scoring tokens
- DOM-model: 13/18, outcome `false`, 17 calls, 68,184 prompt + 8,525 completion = 76,709 scoring tokens
- DOM-model token change: +7,369 tokens (+10.63%)
- Rubric generation: 2 calls and 12,752 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 3; fallback invocations: 0
- DOM evidence coverage: all 3 states loaded, approximately 2,021 evidence tokens, no context omissions or source warnings

### Why the criterion scores differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Use NASA as source of truth | 3/3 | 3/3 | Both showed NASA-controlled pages and no sign-in or registration. |
| Identify the next Artemis mission and report details | 5/13 | 8/13 | Screenshots only showed the general Artemis landing content and did not visually corroborate Artemis II's year, destination, or objective. DOM state 2 explicitly exposed `LaunchED April 1, 2026`, `Crewed Lunar Flyby`, and the objective about returning to the Moon and future Mars missions. DOM still lost substantial credit because the same page said `Occurred 5 months ago`, contradicting the claim that Artemis II was the next planned mission; the agent did not resolve this conflict. |
| Stop after recording details | 2/2 | 2/2 | Both action histories ended after the Artemis II navigation with no additional browsing. |

### Task4 comparison caveat

The DOM advantage comes from materially richer final-state text, not different rubric criteria. The final screenshot did not expose the mission-detail section even though the recorded after-URL was the Artemis II page. Conversely, the DOM evidence revealed an internal status conflict that prevented full credit. DOM-model cost more despite only about 2,021 raw evidence tokens because it made five more scoring calls overall, including three response-validation repeats.

## Task5

Task ID: `viewport-modern-5-official-documentation-lookup-20260829T074921Z`

- Frozen rubric: `a94c72e687adb2f66a294d2b151bb27fc53f4888441e2875e0e17bf645bd20b1`
- Denominator: 17 points across 6 criteria
- Screenshot: 2/17, outcome `false`, 12 calls, 69,706 prompt + 7,300 completion = 77,006 scoring tokens
- DOM-model: 12/17, outcome `false`, 15 calls, 70,655 prompt + 8,684 completion = 79,339 scoring tokens
- DOM-model token change: +2,333 tokens (+3.03%)
- Rubric generation: 2 calls and 13,174 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 1; fallback invocations: 0
- DOM evidence coverage: all 3 states loaded, approximately 1,688 evidence tokens, no context omissions or source warnings

### Why the criterion scores differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Find/open official Gemini API documentation | 0/4 | 3/4 | Neither modality showed an opened docs page. DOM state 2 explicitly showed Google's unusual-traffic/robot-check blocker, earning substantial blocker credit, but not full credit because no alternative direct navigation was attempted. The screenshots showed only the search homepage/autocomplete and could not corroborate the claimed blocker. |
| Report documentation page title | 0/2 | 0/2 | Neither modality reached the official documentation page or exposed its title. |
| Report documentation domain | 0/2 | 0/2 | Neither modality showed a Gemini documentation source domain. |
| Identify Python SDK | 0/3 | 3/3 | DOM confirmed the uncontrollable search blocker, so the judge applied cascading-dependency blocker credit to this field. Screenshot evidence did not confirm the blocker and received no credit. |
| Identify example model | 0/3 | 3/3 | The same cascading blocker treatment produced the DOM-only credit; neither modality actually exposed a model string. |
| Respect constraints and stopping condition | 2/3 | 3/3 | Both avoided sign-in, API-key creation, and code execution. DOM additionally proved that stopping followed a real blocker; screenshots could not establish why the required fields were not collected. |

### Task5 comparison caveat

The ten-point score gap is primarily an evidence-capture difference amplified by the rubric's blocker/dependency rules. DOM did not retrieve more documentation facts; it proved the CAPTCHA state that justified credit for blocked downstream fields. The screenshot sequence omitted the post-search blocker frame despite its after-URL appearing in the trajectory. Therefore this run measures capture coverage as well as modality. DOM-model cost 2,333 more tokens and made three more scoring calls, including one response-validation repeat.

## Task6

Task ID: `viewport-modern-6-chess-profile-lookup-20260829T074948Z`

- Frozen rubric: `efecc4b2d2ac529ca72d2d1520667713c8836927304f465bdb0733988e59dadb`
- Denominator: 14 points across 4 criteria
- Screenshot: 6/14, outcome `false`, 35 calls, 162,360 prompt + 11,848 completion = 174,208 scoring tokens
- DOM-model: 6/14, outcome `false`, 38 calls, 151,247 prompt + 10,864 completion = 162,111 scoring tokens
- DOM-model token change: -12,097 tokens (-6.94%)
- Rubric generation: 2 calls and 11,821 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 3; fallback invocations: 0
- DOM evidence coverage: all 18 states loaded, approximately 18,640 evidence tokens, no context omissions or source warnings

### Why the criterion scores agreed or differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Open Magnus Carlsen's Chess.com profile | 3/3 | 3/3 | Both clearly proved the correct Chess.com player/member profile was opened while signed out. |
| Record Blitz rating exactly | 0/4 | 1/4 | The agent did not report a Blitz rating in either run. Earlier evidence contained a Blitz-labeled rating row, so DOM awarded minimal credit for reaching evidence where Blitz information appeared; screenshots gave no credit because the visible `2860 Blitz` was never transcribed and the final answer incorrectly said it could not be observed. |
| Record Bullet rating exactly | 0/4 | 0/4 | Neither modality showed or reported a Bullet value, and no uncontrollable blocker was established. |
| Respect constraints and stopping condition | 3/3 | 2/3 | Both confirmed no sign-in, challenge, or message. DOM deducted one point because the agent stopped without recording either required rating; the screenshot judge treated that failure as already covered by the rating criteria and retained full constraint credit. |

### Task6 comparison caveat

The equal total hides a one-point attribution swap, so it is not perfect scoring agreement. The trajectory repeatedly alternated between a small number of scroll states but never captured a Bullet rating. DOM-model used 12,097 fewer scoring tokens despite three validation repeats, but its reduction was only 6.94%, well below the broader research target.

## Task7

Task ID: `viewport-modern-7-hugging-face-model-metadata-20260829T075129Z`

- Frozen rubric: `9987bb9c357f375553c846717d9773950b4d02729bd79c7fa2effa5f2a614def`
- Denominator: 13 points across 5 criteria
- Screenshot: 13/13, outcome `true`, 10 calls, 54,789 prompt + 5,282 completion = 60,071 scoring tokens
- DOM-model: 13/13, outcome `true`, 37 calls, 199,389 prompt + 16,558 completion = 215,947 scoring tokens
- DOM-model token change: +155,876 tokens (+259.49%)
- Rubric generation: 2 calls and 11,899 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 17; fallback invocations: 2
- DOM evidence coverage: both states loaded, approximately 7,243 evidence tokens, no context omissions or source warnings

### Why the criterion scores agreed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Use the correct Hugging Face repository | 2/2 | 2/2 | Both explicitly showed `meta-llama/Llama-3.1-8B-Instruct` and visible repository metadata. |
| Report license | 3/3 | 3/3 | Both showed and matched the exact metadata label `License: llama3.1`. |
| Report likes | 3/3 | 3/3 | Both showed and matched the displayed `6.69k` likes count. |
| Determine gated status | 3/3 | 3/3 | Both showed the notice requiring agreement to share contact information before model access. |
| Respect constraints and stop | 2/2 | 2/2 | The only recorded action was a one-second wait; neither mode showed sign-in, access requests, or downloads. |

### Task7 comparison caveat

This is exact score and evidence agreement, but a severe cost failure for DOM-model. With only two states and roughly 7,243 evidence tokens, DOM still made 37 calls versus Microsoft's 10 because it recorded 17 response-validation repeats and invoked fallback behavior twice. The +259.49% token inflation is therefore primarily validation/call-topology overhead, not task complexity or missing evidence.

## Task8

Task ID: `viewport-modern-8-hugging-face-dataset-inspection-20260829T075200Z`

- Frozen rubric: `b30cca4160f9316369cb69cff961d935739ef98c998bd703d33ac0e3683ad8d6`
- Denominator: 13 points across 5 criteria
- Screenshot: 12/13, outcome `true`, 14 calls, 75,713 prompt + 7,515 completion = 83,228 scoring tokens
- DOM-model: 9.5/13, outcome `false`, 20 calls, 141,779 prompt + 10,997 completion = 152,776 scoring tokens
- DOM-model token change: +69,548 tokens (+83.56%)
- Rubric generation: 2 calls and 12,432 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 4; fallback invocations: 0
- DOM evidence coverage: all 4 states loaded, approximately 18,302 evidence tokens, no context omissions or source warnings

### Why the criterion scores differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Navigate to SQuAD dataset | 1/1 | 1/1 | Both proved the correct `rajpurkar/squad` Hugging Face dataset page. |
| Use Dataset Viewer | 2/2 | 2/2 | Both showed the Dataset Viewer and interaction with its split selector. |
| Record train split/count | 3/4 | 4/4 | Both supported `train` and `87.6k rows`. Screenshot scoring deducted for reporting the selected-state middle-dot formatting instead of the open-menu parentheses formatting; DOM accepted the accessible-name representation as exact enough. |
| Record validation split/count | 4/4 | 1/4 | Screenshots visibly showed `validation (10.6k rows)` in the open dropdown. The action target contained the same label, but no DOM-model state exposed validation as active or rendered the option/count as page-state evidence, so the DOM judge treated it as insufficiently confirmed. |
| Respect constraints and stopping condition | 2/2 | 1.5/2 | Both proved no sign-in or edits. DOM applied a small deduction because its evidence could not confirm validation selection/count before stopping. |

### Task8 comparison caveat

The 2.5-point score difference is an evidence-capture issue: the screenshot captured the open listbox while the DOM-model states remained identical after the option clicks and continued to show train selected. The action log knew the validation option label, but the DOM evidence-grounding policy did not accept action-target text as independent page-state proof. DOM-model also made six more calls, including four validation repeats, and used 83.56% more tokens despite only four states.

## Task9

Task ID: `viewport-modern-9-github-issue-search-20260829T075254Z`

- Frozen rubric: `5bf60a7a9d78ee3c7683bff9207e0e075ed78cc479341647685794795b8587e5`
- Denominator: 10 points across 4 criteria
- Screenshot: 3/10, outcome `false`, 12 calls, 71,871 prompt + 8,610 completion = 80,481 scoring tokens
- DOM-model: 9/10, outcome `true`, 16 calls, 95,316 prompt + 9,459 completion = 104,775 scoring tokens
- DOM-model token change: +24,294 tokens (+30.19%)
- Rubric generation: 2 calls and 12,659 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 2; fallback invocations: 0
- DOM evidence coverage: all 3 states loaded, approximately 7,472 evidence tokens, no context omissions or source warnings

### Why the criterion scores differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Apply exact GitHub filters | 2/4 | 3/4 | The DOM final URL explicitly encoded the repo, issue, open, bug-label, and created-date filters. Screenshots supported the attempted query but did not confirm the filtered page loaded. Both lacked browser-visible evidence that `2026-07-30` was derived from the current date, preventing full credit. |
| Report matching count | 0/2 | 2/2 | DOM state 2 exposed the filtered count of 12. The screenshots only exposed unrelated repository-wide counts and did not verify 12 for the requested filter set. |
| Provide three newest issues | 0/3 | 3/3 | DOM state 2 exposed the reported three titles/numbers in the filtered newest list. The screenshots did not show two reported issues or prove that the visible list was the filtered result set. |
| Respect constraints and stop | 1/1 | 1/1 | Both trajectories avoided signing in and made no issue modifications. |

### Task9 comparison caveat

The six-point score gap is primarily an evidence-capture difference: the DOM final state captured the post-search page, while the screenshot evidence did not visibly establish that the filtered results had loaded. Independent action-only judgments also differed, so the frozen rubric controls criteria and denominator but does not eliminate scoring stochasticity. DOM required four more calls, including two response-validation repeats, and consumed 30.19% more tokens.

## Task10

Task ID: `viewport-modern-10-github-release-research-20260829T075327Z`

- Frozen rubric: `94841ef8996547efe1534dcc890c5932b344e48b76633dc6a8fa3b45f49f52cd`
- Denominator: 14 points across 5 criteria
- Screenshot: 8/14, outcome `false`, 10 calls, 58,322 prompt + 6,932 completion = 65,254 scoring tokens
- DOM-model: 12/14, outcome `false`, 16 calls, 77,152 prompt + 10,792 completion = 87,944 scoring tokens
- DOM-model token change: +22,690 tokens (+34.77%)
- Rubric generation: 2 calls and 12,568 tokens, reported separately
- Transport/API retries: 0 for both
- DOM response-validation retries: 4; fallback invocations: 0
- DOM evidence coverage: both states loaded, approximately 2,232 evidence tokens, no context omissions or source warnings

### Why the criterion scores differed

| Criterion | Screenshot | DOM-model | Explanation |
|---|---:|---:|---|
| Identify the latest release | 3/3 | 3/3 | Both proved that `PyTorch 2.13.0 Release` was marked Latest. |
| Report the release tag | 2/2 | 2/2 | Both supported the exact tag `v2.13.0`. |
| Report the release date | 0/2 | 0/2 | Both contradicted the agent's `July 03 at 08:27PM`: screenshots showed `released this Jul 8`, while DOM showed `08 Jul 17:39`. |
| Record the first three highlights | 0/4 | 4/4 | DOM exposed the actual highlight bullets in their displayed order. Screenshots showed only a contents-style section list, not the bullet text, so Microsoft treated the detailed answer as unsupported. |
| Respect constraints and stop | 3/3 | 3/3 | The single scroll action neither signed in nor modified repository content. |

### Task10 comparison caveat

DOM passed the 80% rubric threshold, but both binary outcomes failed because the release date was a required deliverable and the agent reported it incorrectly. The four-point modality gap comes entirely from DOM capturing the highlight content that was absent from screenshots. DOM made six additional calls, including four response-validation repeats, and consumed 34.77% more tokens despite only two states and roughly 2,232 evidence tokens.

## Per-task update template

For each pending task, add:

- Frozen-rubric hash and denominator
- Screenshot score, outcome, calls, prompt/completion/total tokens
- DOM-model score, outcome, calls, prompt/completion/total tokens
- Token delta and percentage
- Criterion-by-criterion score differences
- Evidence-level explanation for every score difference
- Relevance selection, omitted evidence, validation retries, and material caveats
- Link to the immutable per-run comparison artifact
