# Evidence-Loss Audit: 44-Task Checkpoint

This file contains the 44 completed task-run audits from the checkpoint that produced **6.2% screenshot evidence loss** and **2.6% DOM-model evidence loss**. Every record is presented in one sequence and uses the same per-criterion score and evidence-audit format.

Each comparison used one frozen rubric for both verifier modes. Evidence missing from both representations is excluded, and a scoring or reasoning disagreement is not counted as evidence loss when the required evidence was available in both inputs.

| Evidence representation | Asymmetric evidence loss | Rate |
|---|---:|---:|
| Screenshots | 14/227 criteria | **6.2%** |
| DOM model | 6/227 criteria | **2.6%** |

## Task 1

Completed using all N+1 states: 2 screenshots and 2 DOM-model states.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Process score | 15/15 (100%) | 14/15 (93.3%) |
| Outcome | Pass | Fail |
| LLM calls | 12 | 19 |
| Evaluation tokens | 81,212 | 100,608 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | Score SS / DOM | Classification |
| --- | --- | --- | --- | --- |
| Course page accessed | Yes / Yes | Yes / Yes | 3/3 | BOTH_CAUGHT |
| Instructor | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| IBM partner | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Five modules | Yes / Yes | Yes / Yes | 3/2 | BOTH_CAUGHT |
| Audit availability | Yes / Yes | Yes / Yes | 3/3 | BOTH_CAUGHT |
| Constraints respected | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Unavailability | Page clearly available / caught | Page clearly available / caught | N/A | BOTH_CAUGHT |

There was no evidence missed by either verifier.

The one-point difference came from judgment, not missing DOM evidence. Both modalities
showed “5 modules,” but neither showed the five specific module titles claimed in the
final answer:

- Screenshot verifier noticed the unsupported titles but still gave 3/3 because the
    criterion only required the module count.

- DOM verifier noticed the same issue and deducted one point.
- The DOM outcome judge considered those unsupported titles serious enough to fail the
    overall outcome; the screenshot judge treated them as a minor issue.

So screenshot exceeded DOM by one point, but not because screenshot contained more
evidence.

## Task 2

Completed using all N+1 states: 4 screenshots and 4 DOM-model states.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Process score | 16/20 (80%) | 20/20 (100%) |
| Outcome | Fail | Pass |
| LLM calls | 16 | 25 |
| Evaluation tokens | 115,086 | 148,894 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | Score SS / DOM | Classification |
| --- | --- | --- | --- | --- |
| Correct Requests release | Yes / Yes | Yes / Yes | 4/4 | BOTH_CAUGHT |
| Version 2.34.2 | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Upload date | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Requires Python unavailable | Not displayed / correctly caught | Not displayed / correctly caught | 2/2 | BOTH_CAUGHT |
| License unavailable | Not displayed / correctly caught | Not displayed / correctly caught | 2/2 | BOTH_CAUGHT |
| Two download files | Exact count not visible / not proven | Yes / Yes | 1/3 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints/stopping | Yes / Yes | Yes / Yes | 3/5 | BOTH_CAUGHT |

The DOM contained the explicit text “Showing 1 of 1 file” for the built distribution,
plus one source distribution, proving two total files. The screenshots showed one
source file and a separate wheel-detail page, but did not visibly prove that only one
wheel was listed.

Therefore:

- Screenshot missed-available-evidence error rate: 0%
- DOM missed-available-evidence error rate: 0%
- One criterion had stronger source coverage in DOM.
- This was missing screenshot evidence, not the screenshot verifier overlooking clearly
    visible evidence.

## Task 3

Completed using all N+1 states: 2 screenshots and 2 DOM-model states.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Process score | 18/20 (90%) | 19/20 (95%) |
| Outcome | Fail | Fail |
| LLM calls | 12 | 25 |
| Evaluation tokens | 81,524 | 138,767 |

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | Score SS / DOM | Classification |
| --- | --- | --- | --- | --- |
| Access Rails page | Yes / Yes | Yes / Yes | 3/3 | BOTH_CAUGHT |
| Latest-version metadata | 3 fields present; license absent / caught | 3 fields present; license absent / caught | 3/4 | BOTH_CAUGHT |
| Dependency #1 | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Dependency #2 | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Dependency #3 | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Dependency #4 | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Dependency #5 | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |
| Stopping condition | Yes / Yes | Yes / Yes | 2/2 | BOTH_CAUGHT |

Both sources proved version 8.1.3.1, release date July 29, 2026, Ruby requirement >=
3.2.0, and the first five dependencies. Neither source displayed the license, while the
agent claimed MIT; both verifiers correctly caught that unsupported claim and failed
the outcome.

Therefore:

- Screenshot missed-available-evidence error rate: 0%
- DOM missed-available-evidence error rate: 0%
- DOM’s extra point came from more generous partial-credit allocation—not additional
    evidence or a screenshot miss.

- DOM used 57,243 more tokens (+70.22%) and had six response-validation retries with
    one fallback.

In short: both verifiers understood the evidence correctly and rejected the unsupported
license; only their partial-credit judgment differed.

## Task 4

Completed using all 3 screenshots and 3 DOM-model states.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Score | 11/18 (61.1%) | 8.5/18 (47.2%) |
| Outcome | Fail | Fail |
| LLM calls | 13 | 18 |
| Total tokens | 88,862 | 116,464 |
| Rubric-generation calls during scoring | 0 | 0 |

Rubric generation was separate: 2 calls, 13,467 tokens.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | Score SS / DOM | Classification |
| --- | --- | --- | --- | --- |
| Official page and filter | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Identify newest tags | Partial: slim, bookworm / Yes | Partial: trixie / Yes | 2 / 1 | BOTH_CAUGHT |
| Update times | Two visible / Yes | One explicit / Yes | 0.5 / 1.5 | BOTH_CAUGHT |
| Linux/amd64 sizes | Two visible / Yes | One tag-linked / Yes | 2.5 / 1.5 | BOTH_CAUGHT |
| Constraints | Yes / Yes | Yes / Yes | 3 / 1.5 | BOTH_CAUGHT |

The screenshot verifier exceeded DOM by 2.5 points. This was not caused by either
verifier missing available evidence. The representations exposed different tag records,
and criterion 5 also received different scoring interpretations despite both verifiers
recognizing the relevant evidence.

## Task 5

Completed using all 2 screenshots and 2 DOM-model states.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Score | 16/18 (88.9%) | 16/18 (88.9%) |
| Rubric threshold | Pass | Pass |
| Outcome | Fail | Fail |
| LLM calls | 12 | 26 |
| Total tokens | 74,211 | 121,092 |

Rubric generation was separate: 2 calls and 11,970 tokens.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | Score SS / DOM | Classification |
| --- | --- | --- | --- | --- |
| Correct Debian page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Package version | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Complete architecture list | No / correctly rejected | Partial: only amd64 / correctly rejected extras | 1 / 1 | BOTH_CAUGHT |
| Required dependencies | Yes / Yes | Yes / Yes | 7 / 7 | BOTH_CAUGHT |
| No download/install | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |

Both verifiers correctly identified that the claimed nine-architecture list was
unsupported. The screenshots did not show the “Download curl” table, while the DOM
contained only one explicit row: amd64. Neither verifier missed available evidence.

## Task 6

`test_1` is a fresh rerun of the same logical task family as Task 33 (`browser_task_037-package-platform-availability`), with a new capture timestamp. It replaces Task 33 in the rerun-selected aggregate.

| Verifier | Score | Outcome | Calls | Tokens |
|---|---:|:---:|---:|---:|
| Microsoft screenshot | 12/20 (60%) | False | 12 | 79,359 |
| DOM-model | 20/20 (100%) | True | 18 | 87,778 |

DOM used 8,419 more evaluation tokens (+10.61%). Frozen-rubric generation was separate: 2 calls and 13,062 tokens. Both scoring runs reported zero rubric-generation calls, zero API retries, and the same six-criterion, 20-point rubric hash.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Correct ffmpeg page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Stable version | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| License | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Regular dependencies | No / N/A | Yes / Yes | 0 / 6 | SCREENSHOT_EVIDENCE_MISSING |
| Bottle availability | Yes / Yes | Yes / Yes | 4 / 4 | BOTH_CAUGHT |
| Constraints/stopping | Partial / Yes | Yes / Yes | 2 / 4 | Source-coverage difference |

The score difference came from evidence availability, not a confirmed verifier miss. Neither screenshot displayed the regular `Depends on` section, and the screenshot verifier explicitly treated the reported dependency list as unsupported. `dom_model1.txt` contained all 11 regular dependencies and kept them separate from the build-only and `Uses from macOS` sections, so the DOM verifier credited them.

Manual review found no criterion where either verifier overlooked evidence clearly available in its own input. The screenshot source lacked sufficient evidence for 1/6 criteria (16.7%); the DOM source lacked sufficient evidence for 0/6. This is a representation-coverage difference, not a screenshot perception-error recovery case. Because the DOM state contained the dependency table below the area shown in the aligned screenshot, capture/viewport alignment should be checked before using this rerun as evidence of a fair viewport-only CUA advantage.

## Task 7

Completed with a fresh, task-aligned frozen rubric.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Score | 17/20 (85%) | 15/20 (75%) |
| Outcome | Failed | Failed |
| Evaluation calls | 12 | 18 |
| Evaluation tokens | 77,688 | 98,918 |
| Rubric-generation calls | 0 | 0 |

Rubric generation was separate: 2 calls and 13,253 tokens.

| Criterion | SS present/caught | DOM present/caught | SS / DOM | Audit |
| --- | --- | --- | --- | --- |
| C0 Open object | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| C1 Correct museum | Yes / Yes | Yes / Yes | 4 / 4 | BOTH_CAUGHT |
| C2 Relation ID/type | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| C3 Address tags | Yes / Yes | Yes / Yes | 4 / 4 | BOTH_CAUGHT |
| C4 Museum tags | Partially / Yes | Partially / Yes | 1 / 0 | Required tourism, museum, and website rows were missing from both sources |
| C5 Constraints/stop | Yes / Yes | Yes / Yes | 2 / 1 | Both caught; scoring interpretation differed |

The screenshot visibly showed building=museum, but not the requested tourism, museum, or website
tags. The DOM state contained the same limited tag table. Therefore, neither verifier missed
available evidence.

## Task 8

`test_2` is a fresh rerun of Task 37 (`browser_task_042-domain-registry-lookup`) and uses the same frozen rubric content. The rubric hash, seven-criterion order, and 16-point denominator are unchanged; only the outer task identifier was adapted to the new capture timestamp. No rubric-generation model calls or tokens were used for this rerun.

| Verifier | Score | Outcome | Calls | Tokens |
|---|---:|:---:|---:|---:|
| Microsoft screenshot | 16/16 (100%) | True | 12 | 73,612 |
| DOM-model | 16/16 (100%) | True | 28 | 119,898 |

DOM used 46,286 more evaluation tokens (+62.88%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Correct IANA page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| TLD type | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Sponsor | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Registration date | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| WHOIS server | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Registration URL | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Task constraints | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |

Both representations contained all required evidence, and both verifiers recovered it correctly. There was no evidence loss or confirmed verifier miss in this rerun; performance was identical, while DOM used substantially more calls and tokens.

## Task 9

`test_3` is a fresh rerun of Task 38 (`browser_task_043-vulnerability-record-inspection`) using the exact same frozen rubric content, hash, nine-criterion order, and 25-point denominator. Only the outer task identifier reflects the new capture timestamp. No rubric-generation model calls or tokens were used for this rerun.

| Verifier | Score | Outcome | Calls | Tokens |
|---|---:|:---:|---:|---:|
| Microsoft screenshot | 17.5/25 (70%) | False | 12 | 90,827 |
| DOM-model | 17/25 (68%) | False | 27 | 162,545 |

DOM used 71,718 more evaluation tokens (+78.96%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| CVE.org CNA source | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Status | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Publication date | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| CNA name | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Vendor field | No / N/A | No / N/A | 0 / 0 | Missing in both; not a verifier miss |
| Product | Narrative / Yes | Narrative / Yes | 1.5 / 1 | Scoring disagreement |
| Exact version statement | Yes / Yes | Yes / Yes | 5 / 5 | BOTH_CAUGHT |
| First reference URL | No / N/A | No / N/A | 0 / 0 | Missing in both; not a verifier miss |
| Constraints/stopping | Actions / Yes | Actions / Yes | 2 / 2 | BOTH_CAUGHT |

Neither representation contained the structured Vendor field or the CNA References section, and both verifiers correctly treated the agent's claimed vendor and first reference URL as unsupported. The 0.5-point difference came only from scoring interpretation of the product name “Apache Log4j2,” which appeared in narrative Title/Description text in both representations; it was not an evidence-recovery difference.

Unlike the earlier Task 38 capture, which exposed the vendor and first reference evidence, this rerun contains only two states and does not expose either field in screenshots or DOM. Therefore the lower rerun scores reflect reduced source coverage, not a verifier miss and not a DOM-versus-screenshot evidence-loss asymmetry. Screenshot-only evidence loss was 0/9 criteria, and DOM-only evidence loss was 0/9 criteria.

## Task 10

Completed with identical results.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Score | 14/14 (100%) | 14/14 (100%) |
| Rubric pass | Yes | Yes |
| Outcome | Passed | Passed |
| Evaluation calls | 19 | 36 |
| Evaluation tokens | 109,614 | 171,521 |

DOM used 61,907 more tokens (+56.48%). Rubric generation was separate: 2 calls and 12,898 tokens.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
| --- | --- | --- | --- | --- |
| C0 NWS Seattle page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| C1 First daytime period | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| C2 Following nighttime | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| C3 Daytime fields | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| C4 Nighttime fields | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| C5 Constraints/stop | Actions / Yes | Actions / Yes | 2 / 2 | BOTH_CAUGHT |

Both sources clearly contained the same forecast:

- This Afternoon: showers, high 68°F, 90%, SSE wind around 11 mph with gusts to 21 mph
- Tonight: rain mainly after 3am, low 54°F, 50%, south wind 6–10 mph with gusts to 20 mph

## Task 11

`test_4` is a fresh rerun of Task 40 (`browser_task_049-economic-time-series-extraction`) using the exact same frozen rubric content, hash, four-criterion order, and 15-point denominator. Only the outer task identifier reflects the new capture timestamp. No rubric-generation model calls or tokens were used for this rerun.

| Verifier | Score | Outcome | Calls | Tokens |
|---|---:|:---:|---:|---:|
| Microsoft screenshot | 15/15 (100%) | True | 12 | 70,575 |
| DOM-model | 15/15 (100%) | True | 22 | 102,206 |

DOM used 31,631 more evaluation tokens (+44.82%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Correct UNRATE page | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Series metadata | Yes / Yes | Yes / Yes | 4 / 4 | BOTH_CAUGHT |
| Latest three observations | Yes / Yes | Yes / Yes | 6 / 6 | BOTH_CAUGHT |
| Stop after requested work | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |

Both representations contained all required evidence, and both verifiers recovered it correctly. There was no screenshot-only or DOM-only evidence loss and no confirmed verifier miss in this rerun; performance was identical, while DOM used more calls and tokens.

Unlike the earlier Task 40 capture, this rerun's DOM explicitly preserves `Units: Percent, Seasonally Adjusted` together with `Frequency: Monthly`. The earlier one-point DOM deduction caused by a weak Units-to-Percent relationship therefore does not recur.

## Task 12

`test_8` is a fresh rerun of `test_5` (`browser_task_051-cultural-object-metadata`) using the exact same frozen rubric content, SHA-256, seven-criterion order, and 16-point denominator. No rubric-generation model calls or tokens were used.

| Verifier | Score | Rubric pass | Outcome | Calls | Tokens |
|---|---:|:---:|:---:|---:|---:|
| Microsoft screenshot | 13/16 (81.25%) | True | False | 18 | 113,555 |
| DOM-model | 13/16 (81.25%) | True | False | 49 | 204,908 |

DOM used 91,353 more evaluation tokens (+80.45%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Exact Europeana record | Actions / Yes | URL / Yes | 3 / 3 | BOTH_CAUGHT |
| Title | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Creation date | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Providing institution | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Type of item | Yes / Yes | Yes / No, incomplete exact-value check | 1 / 2 | DOM_MISSED_SCREENSHOT_CAUGHT |
| Rights statement | Yes / Yes | Yes / Yes | 3 / 2 | BOTH_CAUGHT; scoring interpretation differs |
| Identifier | No / N/A | No / N/A | 0 / 0 | Missing in both; correctly rejected |

The equal totals hide different attribution. Screenshot 5 visibly shows `Type of item: painting ; Art of painting`; `dom_model4.txt` also contains `Type of item`, `painting`, and `Art of painting`. The screenshot verifier correctly treated the agent's shorter `painting` answer as incomplete, while the DOM verifier cited only `painting` and awarded full credit. This is a DOM evidence-analysis/scoring miss, not DOM capture loss. Conversely, the DOM judge awarded 2/3 for rights because it considered the separately displayed public-domain URL, while the screenshot judge accepted the visible `Public Domain` wording for full credit.

Both verifiers correctly rejected the fabricated `Identifier: Canvas`: neither the screenshots nor DOM states contain an Identifier field or Canvas value. No asymmetric screenshot-versus-DOM capture loss was confirmed for the requested fields in this rerun. Both outcomes remained false because the identifier was a required core deliverable.

## Task 13

`test_6` is a fresh rerun of Task 42 (`browser_task_053-book-edition-resolution`) using the exact same frozen rubric content, hash, nine-criterion order, and 15-point denominator. The paired task metadata was corrected from the pre-redirect ISBN URL to the resolved edition URL so it matched `dom_model0`; no verifier code or evidence file was changed. No rubric-generation model calls or tokens were used for this rerun.

| Verifier | Rubric score | Rubric pass | Outcome | Calls | Tokens |
|---|---:|:---:|:---:|---:|---:|
| Microsoft screenshot | 12/15 (80%) | True | False | 12 | 80,445 |
| DOM-model | 15/15 (100%) | True | False | 13 | 87,844 |

DOM used 7,399 more evaluation tokens (+9.20%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| ISBN-resolved edition proof | No / N/A | Yes / Yes | 2 / 3 | SCREENSHOT_EVIDENCE_MISSING |
| Title | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Author | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Publish Date | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Publisher | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Language | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Page count | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| ISBN-13 | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints/stopping | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |

The three-point DOM rubric advantage came from genuine source coverage. Neither screenshot displayed ISBN-13 or otherwise visibly tied edition `OL37076991M` to the supplied ISBN, while `dom_model1.txt` explicitly displayed `ISBN 13 9780141439518` on that edition page. The screenshot verifier therefore did not miss visible evidence; the screenshot representation lacked it.

The `dom_model1.txt` capture declared truncation, but manual inspection confirmed that every required rubric field survived. Criterion-level screenshot-only asymmetric evidence loss was 2/9 (22.2%), DOM-only asymmetric evidence loss was 0/9, and neither criterion scorer missed evidence available in its own representation.

There was, however, a separate outcome-level DOM verifier error. The DOM outcome judge marked the task failed because it said the agent's extra statement “Published in London” was unsupported. That statement is explicitly present in `dom_model1.txt` under `Book Details → Edition Notes` as `Published in` / `London`. The screenshot also visibly shows the same field. Therefore this particular DOM outcome rationale is factually wrong: it is a confirmed evidence-grounding miss by the DOM outcome judge, not DOM capture loss. The screenshot outcome remained false for a different, evidence-consistent reason: the submitted screenshots did not show ISBN-13 or prove the ISBN-to-edition linkage.

## Task 14

This is a second independent scoring run for `test_7`. It reused the exact frozen rubric (SHA-256 `2dc6ea5c8c32703420ff5fe1ffccd592adb9904baa38622c211b44d89722b928`), the same two screenshots, the same two DOM states, the same action history, and the same final answer. Rubric generation remained at zero calls and zero tokens.

| Verifier | Score | Outcome | Calls | Tokens |
|---|---:|:---:|---:|---:|
| Microsoft screenshot | 10.5/20 (52.5%) | False | 12 | 90,582 |
| DOM-model | 14/20 (70%) | False | 20 | 124,272 |

DOM used 33,690 more evaluation tokens (+37.19%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Correct Gutenberg page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Author | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Release Date | No / N/A | No / N/A | 0.5 / 0 | Missing in both; screenshot scoring overcredit |
| Last Update | No / N/A | No / N/A | 0 / 0 | Missing in both; not a verifier miss |
| Language | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| EPUB3 | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Plain Text (accessible) | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Download HTML (zip) | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints/stopping | Partial / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT for observable constraints |

The evidence audit is unchanged from the first run. The DOM advantage still comes from the exact `Plain Text (accessible)` and `Download HTML (zip)` labels being present only in the DOM evidence. The screenshot score increased by 1.5 points because of judge variance, not newly available evidence: the screenshot scorer awarded 0.5 points for the unsupported Release Date and raised constraints/stopping from 1 to 2. DOM remained at 14/20. No case was found where a verifier failed to identify clearly available criterion evidence in its own modality.

## Task 15

Completed.

| Verifier | Score | Outcome | Calls | Tokens |
| --- | --- | --- | --- | --- |
| Microsoft screenshot | 18/18 (100%) | False | 14 | 91,213 |
| DOM-model | 18/18 (100%) | False | 21 | 108,842 |

DOM used 17,629 more tokens (+19.33%).

| Criterion | Screenshot evidence/caught | DOM evidence/caught | Audit |
| --- | --- | --- | --- |
| Title-field search | 403 visible / Yes | Title: 403 / Yes | BOTH_CAUGHT |
| Filters and sorting | 403 blocker / Yes | 403 blocker / Yes | BOTH_CAUGHT |
| Result #1 | Blocked / Yes | Blocked / Yes | BOTH_CAUGHT |
| Result #2 | Blocked / Yes | Blocked / Yes | BOTH_CAUGHT |
| Result #3 | Blocked / Yes | Blocked / Yes | BOTH_CAUGHT |
| Stopping condition | Reasonable stop / Yes | Reasonable stop / Yes | BOTH_CAUGHT |

All three screenshots were identical and visibly showed “403 Forbidden.” All three DOM states also explicitly
recorded Title: 403. Therefore:

## Task 16

`test_9` is a fresh rerun of Task 46 (`browser_task_057-clinical-trial-filtering`) using the exact same frozen rubric content, SHA-256 `479289d7d032e7abdc8d46509686bb8e09396b60bef1f2e8ea52f54458cf7265`, seven-criterion order, and 22-point denominator. No rubric-generation model calls or tokens were used.

| Verifier | Score | Rubric pass | Outcome | Calls | Tokens |
|---|---:|:---:|:---:|---:|---:|
| Microsoft screenshot | 8/22 (36.4%) | False | False | 41 | 265,454 |
| DOM-model | 12/22 (54.5%) | False | False | 51 | 371,551 |

DOM used 106,097 more evaluation tokens (+39.97%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Search term/results | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Recruiting + Phase 3 + US filters | Partial UI / Yes | URL all three; UI partial / Yes | 2 / 3 | Evidence-strength/scoring difference |
| Newest-first sort | No visible UI / N/A | URL parameter / Yes | 0 / 1 | SCREENSHOT_EVIDENCE_MISSING |
| Result #1 | NCT/title/status / Yes | NCT/title/status / Yes | 2 / 2 | BOTH_CAUGHT; dates missing both |
| Result #2 | NCT/title/status/order / Partially | NCT/status/order / Yes | 1 / 1.5 | Screenshot sequence miss; DOM title missing |
| Result #3 | NCT/title/status/order / No | NCT/status/order / Yes | 0 / 1.5 | SCREENSHOT_MISSED_DOM_CAUGHT for order; DOM title missing |
| Constraints/stopping | Partial / Yes | Partial / Yes | 1 / 1 | BOTH_CAUGHT |

The task genuinely remains incomplete in both modalities because none of the three required `Last Update Posted` dates appears in the captured evidence or final answer, and the sort is not visibly confirmed by an on-page control. The DOM can only partially support sorting through `sort=updated,desc` in its explicit URL.

A manual frame-sequence check also found a screenshot-verifier grounding error. `screenshot19.png` shows result #1 (`NCT07662213`), while `screenshot20.png` is the scrolled continuation showing result #2 (`NCT07664553`) followed by result #3 (`NCT06739122`). The screenshot verifier treated screenshot20 as if it began a fresh list, described the third study as the second visible card, and rejected the reported ordering. Thus the order evidence was available across consecutive screenshots but was not reconstructed correctly. DOM state 20 kept all three NCT IDs in one ordered text state and recovered that ordering, although it omitted the full titles for results #2 and #3.

The four-point DOM advantage therefore combines stronger explicit URL/order evidence with screenshot sequence-grounding loss; it is not four points of complete DOM evidence recovery. Both outcome failures are still valid because the Last Update Posted dates—the task's core required fields—were never captured or reported.

## Task 17

Completed.

| Verifier | Score | Outcome | Calls | Tokens |
| --- | --- | --- | --- | --- |
| Microsoft screenshot | 15/20 (75%) | False | 12 | 86,889 |
| DOM-model | 15.5/20 (77.5%) | False | 17 | 95,966 |

DOM used 9,077 more tokens (+10.45%).

| Criterion | Screenshot | DOM model | Audit |
| --- | --- | --- | --- |
| Exact product | Page visible; barcode from shared URL: 3/3 | Explicit name/barcode: 3/3 | BOTH_CAUGHT |
| Name/barcode | Name visible; barcode not visually shown: 2/2 | Both explicit: 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Nutri-Score | Visible and caught: 2/2 | Present and caught: 2/2 | BOTH_CAUGHT |
| NOVA/markers | Visible and caught: 3/3 | Present and caught: 3/3 | BOTH_CAUGHT |
| Energy | Not visible: 0/3 | Explicit table value caught: 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Sugars | Not visible: 0/2 | Explicit table value caught: 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| Ingredients | Absent; unavailable claim credited: 4/4 | Absent, but stopping early penalized: 0/4 | Reasoning disagreement |
| Constraints | Full credit: 1/1 | Incomplete ingredients caused deduction: 0.5/1 | Reasoning disagreement |

Key finding: DOM contained the energy and sugar values even though neither screenshot displayed them. Therefore,
the screenshot verifier did not miss visible evidence—the screenshot representation lacked that evidence.

Conversely, Microsoft overcredited the missing ingredients by treating “not currently displayed” as “unavailable,”
while the DOM verifier correctly recognized that the agent could have continued navigating.

## Task 18

Completed.

| Verifier | Score | Outcome | Calls | Tokens |
| --- | --- | --- | --- | --- |
| Microsoft screenshot | 13/22 (59.1%) | False | 24 | 157,620 |
| DOM-model | 16/22 (72.7%) | False | 37 | 243,674 |

DOM used 86,054 more tokens (+54.60%).

| Criterion | Screenshot | DOM model | Audit |
| --- | --- | --- | --- |
| Correct Portal 2 page | Present/caught: 3/3 | Present/caught: 3/3 | BOTH_CAUGHT |
| Release/developer/publisher | Present/caught: 4/4 | Present/caught: 4/4 | BOTH_CAUGHT |
| All Reviews | Absent; correctly penalized: 0/4 | Absent, but incorrectly credited: 4/4 | Reasoning disagreement |
| OS headings | Both headings visible/ caught: 3/3 | Headings absent from DOM: 1/3 | DOM_EVIDENCE_MISSING |
| Storage | Windows 8 GB visible; omission caught: 1/5 | Storage absent from DOM: 1/5 | DOM_EVIDENCE_MISSING |
| Constraints/stopping | Incomplete response: 2/3 | Full credit despite omissions: 3/3 | Reasoning disagreement |

The DOM verifier scored higher mainly because it overcredited the missing All Reviews summary by four points, not
because DOM recovered evidence missed by screenshots. It also gave one extra constraint point. Conversely, DOM
lost two points because its source omitted the OS headings that screenshot3 clearly displayed.

## Task 19

Completed.

| Verifier | Score | Outcome | Calls | Tokens |
| --- | --- | --- | --- | --- |
| Microsoft screenshot | 3/12 (25%) | False | 16 | 99,226 |
| DOM-model | 3/12 (25%) | False | 16 | 111,927 |

DOM used 12,701 more tokens (+12.80%).

| Criterion | Screenshot | DOM model | Audit |
| --- | --- | --- | --- |
| Correct artist/Album scope | Present and caught: 2/3 | Present and caught: 2/3 | BOTH_CAUGHT |
| Homework | Title/page present, full release date missing: 1/3 | Same evidence/result: 1/3 | BOTH_CAUGHT |
| Discovery | Listed initially, but never opened/ reported: 0/3 | Same omission caught: 0/3 | BOTH_CAUGHT |
| Human After All | Listed initially, but never opened/ reported: 0/3 | Same omission caught: 0/3 | BOTH_CAUGHT |

Both sources clearly showed the correct standalone Album chronology: Homework, Discovery, and Human After All.
However, the agent opened only Homework and never obtained its required complete “First release date.” It did not
process entries two or three.

## `data-new`: Tasks 1–19

## Task 20

Task ID: `browser_task_001-reddit-ranking-20260909T070105Z`

Run: `20260909T_task001_data_new`

Frozen rubric: 5 criteria, 17 maximum points

Rubric SHA-256: `08053dc4514113054566c6ea9f0a4a9e785428805d5e8f12c9f129ddcf7b8fbb`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/17 (100%) | 17/17 (100%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Failure | Environment blocker | Environment blocker |
| Actions / states | 0 / 1 screenshot | 0 / 1 DOM state |
| Scoring LLM calls | 10 | 11 |
| API attempts / retries | 10 / 0 | 11 / 0 |
| Duration | 74.605 s | 86.565 s |

Both verifiers gave full process credit because the rubric permits full credit when an external blocker is clearly reported. Both outcome checks still failed because the requested #1 post title and score were not delivered.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 55,544 | 5,626 | 1,600 | 61,170 |
| DOM model | 54,643 | 6,267 | 1,280 | 60,910 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 260 fewer scoring tokens, a 0.4% reduction. Rubric generation was separate: 12,591 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access r/LocalLLaMA without signing in | Blocker visible / Yes | Blocker explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Apply Top + This Week | Blocker proves controls unavailable / Yes | Blocker proves controls unavailable / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Report #1 post title and score | Blocker proves feed unavailable / Yes | Blocker proves feed unavailable / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Respect no-login/no-interaction constraints | Empty action history and blocked state / Yes | Empty action history and blocked state / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop at the appropriate point | Zero actions and blocker reported / Yes | Zero actions and blocker reported / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual source check confirmed that `screenshot0.png` visibly says “You've been blocked by network security,” and `dom_model0.txt` contains the same message, login/developer-token requirement, and absence of subreddit content. The blank DOM title warning did not remove relevant evidence, and the DOM source was not truncated.

### Evidence-error result

- Screenshot evidence misses: **0/5**
- DOM-model evidence misses: **0/5**
- Asymmetric evidence loss: **0/5**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both modalities and both verifiers behaved consistently. The task failed because of a genuine website access blocker, not because either evidence representation or verifier missed available information.

### Artifacts

- [Frozen rubric](rubrics/browser_task_001-reddit-ranking-20260909T070105Z.json)
- [Comparison report](results/browser_task_001-reddit-ranking-20260909T070105Z/20260909T_task001_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_001-reddit-ranking-20260909T070105Z/20260909T_task001_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_001-reddit-ranking-20260909T070105Z/20260909T_task001_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_001-reddit-ranking-20260909T070105Z/20260909T_task001_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 21

Task ID: `browser_task_002-cross-site-research-20260909T070119Z`

Run: `20260909T_task002_data_new`

Frozen rubric: 4 criteria, 15 maximum points

Rubric SHA-256: `2157f3abcd304f7618cb600205bd1f4ac17cb9bfeb93fd0b39f1da3c1e795d6a`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 8/15 (53.3%) | 11/15 (73.3%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 10 / 11 screenshots | 10 / 11 DOM states |
| Scoring LLM calls | 25 | 32 |
| API attempts / retries | 25 / 0 | 32 / 0 |
| Duration | 101.142 s | 116.420 s |

DOM scored three points higher because its final state explicitly preserved the developer and release date. Both modes failed the outcome because “Best sellers” provenance and the publisher field were not proven.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 126,243 | 10,769 | 1,792 | 137,012 |
| DOM model | 133,979 | 12,991 | 1,792 | 146,970 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 9,958 more scoring tokens, a 7.3% increase. Rubric generation was separate: 12,591 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Select a game from Best sellers | Positive provenance absent / correctly rejected | Positive provenance absent / correctly rejected | 2/4 / 2/4 | BOTH_CAUGHT |
| Open selected product page | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Publisher, developer, release date | Developer/date absent; publisher ambiguous / correctly limited | Developer/date explicit; publisher relation missing / correctly limited | 0/5 / 3/5 | SCREENSHOT_EVIDENCE_MISSING |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that no screenshot displays a “Best sellers” section. The product page is clearly visible in `screenshot9.png`, but `screenshot10.png` stops in the Gallery/Description area before the developer and release-date fields. In `dom_model10.txt`, the exact values `Developed by → Tiburon` and `Release date → 8/13/2026` are present. The DOM shows a `Published by` label without its associated value; `Electronic Arts` appears separately near the title, so neither verifier treated that as conclusive publisher evidence.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **1/4 criteria**
- DOM-side asymmetric evidence loss: **0/4 criteria**
- Confirmed verifier perception misses: **0/4 criteria**
- DOM recovery of screenshot source gaps: **1/1 eligible criterion**
- Verifier-miss recovery rate: **N/A (neither verifier overlooked available evidence)**

**Summary:** DOM recovered developer and release-date evidence that the screenshot sequence did not capture, producing the higher process score. This was screenshot capture loss, not a screenshot-verifier reading error. DOM used more tokens and still lacked a reliable publisher label–value relationship.

### Artifacts

- [Frozen rubric](rubrics/browser_task_002-cross-site-research-20260909T070119Z.json)
- [Comparison report](results/browser_task_002-cross-site-research-20260909T070119Z/20260909T_task002_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_002-cross-site-research-20260909T070119Z/20260909T_task002_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_002-cross-site-research-20260909T070119Z/20260909T_task002_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_002-cross-site-research-20260909T070119Z/20260909T_task002_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 22

Task ID: `browser_task_003-job-listing-extraction-20260909T070258Z`

Run: `20260909T_task003_data_new`

Frozen rubric: 7 criteria, 20 maximum points

Rubric SHA-256: `6cb1ce774b4da7e22243c6a0ae5ffb597dc341935f8a53dfbce2c309d01e3fb2`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/20 (85.0%) | 17/20 (85.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 36 / 37 screenshots | 36 / 37 DOM states |
| Scoring LLM calls | 58 | 70 |
| API attempts / retries | 58 / 0 | 70 / 0 |
| Duration | 101.738 s | 122.890 s |

Both verifiers produced the same criterion scores. The process rubric passed, but both outcome checks failed because the agent's two reported responsibilities did not match the listing's actual responsibility bullets.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 278,622 | 17,104 | 1,792 | 295,726 |
| DOM model | 383,016 | 22,506 | 1,536 | 405,522 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 109,796 more scoring tokens, a 37.1% increase. Rubric generation was separate: 13,370 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Search Applied Scientist in Redmond | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Open one relevant listing | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report job number | Yes: `200017828` / Yes | Yes: `200017828` / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report work-site arrangement | Yes: `3 days / week in-office` / Yes | Yes: `3 days / week in-office` / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report two responsibilities | Yes / Yes, but answer contradicted source | Yes / Yes, but answer contradicted source | 0/3 / 0/3 | BOTH_CAUGHT |
| Report two preferred qualifications | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Respect no-sign-in/no-application constraints | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |

Manual inspection confirmed the job metadata in `screenshot4.png` and `dom_model4.txt`, the actual responsibility bullets in `screenshot5.png` and `dom_model5.txt`, and preferred qualifications in `screenshot6.png` and `dom_model6.txt`. The final answer replaced the listing's explicit responsibilities—LLM fine-tuning with RLHF, agent adversarial evaluations/safety mitigations, and delivering mitigations with the Responsible AI engineering team—with unsupported generalized duties. Both verifiers detected that mismatch correctly. The automated audit's two wording-based disagreement flags did not correspond to score, evidence-presence, or verifier-catch disagreements.

### Evidence-error result

- Screenshot evidence misses: **0/7 criteria**
- DOM-model evidence misses: **0/7 criteria**
- Asymmetric evidence loss: **0/7 criteria**
- Confirmed verifier perception misses: **0/7 criteria**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both representations contained the required evidence and both verifiers interpreted it consistently. The task failed because the agent reported incorrect responsibilities, not because screenshot or DOM evidence was missing or overlooked. DOM used 37.1% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_003-job-listing-extraction-20260909T070258Z.json)
- [Comparison report](results/browser_task_003-job-listing-extraction-20260909T070258Z/20260909T_task003_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_003-job-listing-extraction-20260909T070258Z/20260909T_task003_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_003-job-listing-extraction-20260909T070258Z/20260909T_task003_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_003-job-listing-extraction-20260909T070258Z/20260909T_task003_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 23

Task ID: `browser_task_004-museum-film-lookup-20260909T071414Z`

Run: `20260909T_task004_data_new`

Frozen rubric: 5 criteria, 15 maximum points

Rubric SHA-256: `81ae2fa388b310f12bcd2015339158be8169f748f3fd281893eb5bec3606ab77`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 4/15 (26.7%) | 5/15 (33.3%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 12 |
| API attempts / retries | 12 / 0 | 12 / 0 |
| Duration | 98.152 s | 109.860 s |

Both modes failed because the agent returned only a structured-snapshot timeout and did not report a film title, synopsis, or showtimes. DOM received one additional navigation point even though both modalities captured the same relevant page state.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 66,195 | 7,809 | 2,304 | 74,004 |
| DOM model | 65,451 | 8,675 | 2,944 | 74,126 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 122 more scoring tokens, a 0.2% increase. Rubric generation was separate: 12,890 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Reach currently-playing information | “Now Showing” + “Sturm Theater” visible / Yes | Same page text explicit / Yes | 1/3 / 2/3 | BOTH_CAUGHT |
| Identify one current film title | Absent / correctly rejected | Absent / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Report film synopsis | Absent / correctly rejected | Absent / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Report showtimes | Absent / correctly rejected | Absent / correctly rejected | 0/4 / 0/4 | BOTH_CAUGHT |
| Respect constraints | Present / Yes | Present / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot1.png` visibly shows the DMNS “Films & Shows” page, a “Now Showing” heading, and a “Sturm Theater” section. `dom_model1.txt` preserves the same URL and text. Neither source contains a visible film title, film-specific synopsis, or showtime schedule. Both verifiers correctly identified those absences. Because the navigation evidence was materially the same, the screenshot 1/3 versus DOM 2/3 allocation is judge/scoring variance rather than DOM recovering evidence missed by the screenshot verifier.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **0/5 criteria**
- DOM-side asymmetric evidence loss: **0/5 criteria**
- Confirmed verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both modalities captured the same incomplete state and both verifiers correctly recognized what was and was not available. The one-point DOM advantage reflects scoring variance, not extra DOM evidence. Token usage was effectively equal, with DOM using 0.2% more.

### Artifacts

- [Frozen rubric](rubrics/browser_task_004-museum-film-lookup-20260909T071414Z.json)
- [Comparison report](results/browser_task_004-museum-film-lookup-20260909T071414Z/20260909T_task004_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_004-museum-film-lookup-20260909T071414Z/20260909T_task004_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_004-museum-film-lookup-20260909T071414Z/20260909T_task004_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_004-museum-film-lookup-20260909T071414Z/20260909T_task004_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 24

Task ID: `browser_task_005-event-lookup-20260909T094331Z`

Run: `20260909T_task005_data_new`

Frozen rubric: 4 criteria, 15 maximum points

Rubric SHA-256: `1d9fb62eb123094877e0d4f2d9defa7dfd985148ce7c88e3efa589b359e1671c`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/15 (80.0%) | 12/15 (80.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 2 / 3 screenshots | 2 / 3 DOM states |
| Scoring LLM calls | 14 | 17 |
| API attempts / retries | 14 / 0 | 17 / 0 |
| Duration | 80.029 s | 119.447 s |

The totals match, but the criterion allocation differs. DOM received one more point for establishing the earliest visible event, while screenshot received one more point for the incomplete event-details answer. Both outcome checks failed because the trajectory did not prove the event was the overall next event and inferred a location that the page did not label.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 73,136 | 7,084 | 1,664 | 80,220 |
| DOM model | 74,310 | 9,769 | 1,664 | 84,079 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 3,859 more scoring tokens, a 4.8% increase. Rubric generation was separate: 12,608 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Reach official events listing | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Determine the next upcoming event | Only 9:00 AM event visible / correctly limited | 9:00 AM and 11:00 AM events explicit / Yes | 2/4 / 3/4 | SCREENSHOT_EVIDENCE_MISSING |
| Report title, date, time, and location | Title/date/time present; location absent / Yes | Same fields present; location absent / Yes | 4/5 / 3/5 | BOTH_CAUGHT |
| Respect constraints | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot2.png` shows the September 11, 2026 event at 9:00 AM–11:00 AM but no second event in the viewport. `dom_model2.txt` contains that event plus another event on the same date at 11:00 AM–4:00 PM, providing evidence that 9:00 AM is earliest among the captured listings. Neither modality proves that the captured list is globally complete, so DOM still received only partial credit. Both sources contain the same title/date/time and omit a separately labeled location; the screenshot 4/5 versus DOM 3/5 difference on event details is judge/scoring variance, not evidence availability or a verifier miss.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **1/4 criteria**
- DOM-side asymmetric evidence loss: **0/4 criteria**
- Confirmed verifier perception misses: **0/4 criteria**
- DOM recovery of screenshot source gaps: **1/1 eligible criterion**
- Verifier-miss recovery rate: **N/A (neither verifier overlooked available evidence)**

**Summary:** DOM preserved a second event outside the screenshot viewport and therefore supported a stronger chronological comparison. Both verifiers correctly handled the evidence available to them; the equal 12/15 totals hide one genuine screenshot source gap and one offsetting point of scoring variance. DOM used 4.8% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_005-event-lookup-20260909T094331Z.json)
- [Comparison report](results/browser_task_005-event-lookup-20260909T094331Z/20260909T_task005_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_005-event-lookup-20260909T094331Z/20260909T_task005_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_005-event-lookup-20260909T094331Z/20260909T_task005_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_005-event-lookup-20260909T094331Z/20260909T_task005_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 25

Task ID: `browser_task_006-article-metadata-lookup-20260909T071913Z`

Run: `20260909T_task006_data_new`

Frozen rubric: 4 criteria, 12 maximum points

Rubric SHA-256: `fd4b6e5db6e3942d425c795d4667da54104038119a8cacb7e2817b6505e2c2a1`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6/12 (50.0%) | 6/12 (50.0%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 8 / 9 screenshots | 8 / 9 DOM states |
| Scoring LLM calls | 25 | 35 |
| API attempts / retries | 25 / 0 | 35 / 0 |
| Duration | 85.939 s | 125.444 s |

Both verifiers produced identical criterion scores. The agent paginated from the latest-posts archive through page 8, then returned only an agent-browser timeout without identifying an earliest article or reporting its title, date, and author.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 129,931 | 11,227 | 1,536 | 141,158 |
| DOM model | 174,515 | 18,782 | 2,304 | 193,297 |

`* Reasoning tokens are included within completion tokens and are not added again.`

DOM used 52,139 more scoring tokens, a 36.9% increase. Rubric generation was separate: 12,133 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Attempt on-site earliest-article search | Yes / Yes | Yes / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Identify earliest article and metadata | Required result absent / correctly rejected | Required result absent / correctly rejected | 0/5 / 0/5 | BOTH_CAUGHT |
| Stop after result or clear blocker | Condition unmet / correctly rejected | Condition unmet / correctly rejected | 0/1 / 0/1 | BOTH_CAUGHT |
| Respect constraints | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot8.png` shows a normally loaded Search Engine Land archive page titled “More from Search Engine Land: Page 8,” with articles dated July 24, 2026. `dom_model8.txt` preserves the same page and additionally identifies it as “Page 8 of 721.” Neither source shows the archive endpoint or the earliest article, and the final answer contains only a browser-timeout message with no article metadata. Both verifiers correctly determined that the task was incomplete. The DOM-only total-page count reinforces that page 8 is far from the archive end but does not supply the missing requested article, so it is not counted as asymmetric loss of required evidence.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **0/4 criteria**
- DOM-side asymmetric evidence loss: **0/4 criteria**
- Confirmed verifier perception misses: **0/4 criteria**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both modalities and verifiers reached the same conclusion: the agent made a valid on-site attempt but never found or reported the earliest article. There was no verifier perception miss or asymmetric loss of the required evidence. DOM used 36.9% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_006-article-metadata-lookup-20260909T071913Z.json)
- [Comparison report](results/browser_task_006-article-metadata-lookup-20260909T071913Z/20260909T_task006_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_006-article-metadata-lookup-20260909T071913Z/20260909T_task006_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_006-article-metadata-lookup-20260909T071913Z/20260909T_task006_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_006-article-metadata-lookup-20260909T071913Z/20260909T_task006_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 26

Task ID: browser_task_007-cross-site-recipe-lookup-20260909T072810Z

Run: 20260909T_task007_data_new

Frozen rubric: 6 criteria, 12 maximum points

Rubric SHA-256: 92aa9a35c900cfea9df77683c49e2d406af0a68c5cafd9169458a5c81323c15b

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12/12 (100%) | 12/12 (100%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 25 |
| API attempts / retries | 12 / 0 | 25 / 0 |
| Duration | 99.680 s | 148.904 s |

Both verifiers gave full credit. Amazon evidence confirms Tata Salt as the #2 Grocery & Gourmet Foods bestseller, and the AllRecipes request reaches a genuine Cloudflare verification interstitial. The task explicitly requires stopping and reporting such a bot check rather than bypassing it.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 71,091 | 7,567 | 1,984 | 78,658 |
| DOM model | 106,954 | 15,287 | 2,496 | 122,241 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 43,583 more scoring tokens, a 55.4% increase. Rubric generation was separate: 12,645 tokens across 2 calls; scoring reported rubric_generation_calls: 0 for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access Amazon India bestsellers | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Verify product ranked #2 | Tata Salt explicit / Yes | #2 Tata Salt explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Attempt AllRecipes recipe search | Cloudflare block visible / Yes | Interstitial explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report recipe title or valid blocker | Block correctly reported / Yes | Block correctly reported / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Report ingredients or valid blocker | Block correctly reported / Yes | Block correctly reported / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that screenshot0.png visibly shows the Amazon India Grocery & Gourmet Foods bestseller grid with “#2” above Tata Salt, while dom_model0.txt explicitly records the same rank and product. screenshot1.png shows Cloudflare “Verifying…”, and dom_model1.txt contains the corresponding verification/interstitial text with no recipe content. The final answer's claim that a specific “Verify you are human” checkbox appeared is not shown in either captured source, but both verifiers correctly treated this as a minor description mismatch rather than evidence against the genuine blocker.

### Evidence-error result

- Screenshot-side asymmetric evidence loss: **0/6 criteria**
- DOM-side asymmetric evidence loss: **0/6 criteria**
- Confirmed verifier perception misses: **0/6 criteria**
- DOM recovery of screenshot misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM misses: **N/A (0 eligible misses)**

**Summary:** Both evidence representations contained and recovered the same decisive facts: Tata Salt was ranked #2 and AllRecipes was blocked by a verification interstitial. Both verifiers scored the constrained task as successfully completed. DOM used 55.4% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_007-cross-site-recipe-lookup-20260909T072810Z.json)
- [Comparison report](results/browser_task_007-cross-site-recipe-lookup-20260909T072810Z/20260909T_task007_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_007-cross-site-recipe-lookup-20260909T072810Z/20260909T_task007_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_007-cross-site-recipe-lookup-20260909T072810Z/20260909T_task007_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_007-cross-site-recipe-lookup-20260909T072810Z/20260909T_task007_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 27

Task ID: `browser_task_008-software-release-research-20260909T072902Z`

Run: `20260909T_task008_data_new`

Frozen rubric: 6 criteria, 17 maximum points

Rubric SHA-256: `dbd97e8cc89d447ae6e4e451a73e26b3eacff43e05f39ea4d84a8ce8e496ffa0`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/17 (76.5%) | 14.5/17 (85.3%) |
| Rubric threshold | Fail | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 9 / 10 screenshots | 9 / 10 DOM states |
| Scoring LLM calls | 23 | 36 |
| API attempts / retries | 23 / 0 | 36 / 0 |
| Duration | 103.844 s | 145.545 s |

Both outcome checks failed because the agent reported an incorrect publication date. DOM scored 1.5 points higher: screenshot scoring was 0.5 points higher for stable-release identification, while DOM was 2 points higher for the three release-note changes.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 122,055 | 11,193 | 1,664 | 133,248 |
| DOM model | 183,566 | 18,865 | 2,304 | 202,431 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 69,183 more scoring tokens, a 51.9% increase. Rubric generation was separate: 12,743 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access official Releases page | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Identify newest stable release | `v1.63.0` + `Latest` visible / Yes | `v1.63.0` + `Latest` explicit / Yes | 2/2 / 1.5/2 | BOTH_CAUGHT |
| Report tag and publication date | Tag + relative age only / correctly rejected wrong date | Tag + Sep. 4, 2026 explicit / correctly contradicted wrong date | 1/3 / 1/3 | SCREENSHOT_EVIDENCE_MISSING |
| Extract three release-note changes | All three visible / No, third change overlooked | All three explicit / Yes | 2/4 / 4/4 | SCREENSHOT_MISSED_DOM_CAUGHT |
| Verify one change in official docs | Test-lock docs visible / Yes | Test-lock docs explicit / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed two distinct effects. First, the screenshots show only GitHub's relative “released this 4 days ago” text; the exact September 4, 2026 date is outside the captured viewport, while `dom_model0.txt` and `dom_model6.txt` preserve it. Both verifiers still correctly rejected the agent's incorrect 2025-01-07 date. Second, `screenshot3.png` visibly contains “Visible-only locators,” but the screenshot verifier said only two GitHub release-note changes were supported—even though that frame was selected. `dom_model3.txt` explicitly contains the same third change, and the DOM verifier recovered all three. The 2/2 versus 1.5/2 stable-release difference is scoring strictness/LLM variance: both verifiers found `v1.63.0` and its `Latest` marker.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **1/6 criteria**
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed verifier perception misses: **Screenshot 1/6; DOM 0/6**
- DOM recovery of screenshot verifier misses: **1/1 eligible criterion (100%)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** DOM recovered one third release-note change that was visibly present but overlooked by the screenshot verifier, and it preserved an exact date that was outside the screenshot viewport. The agent's date was nevertheless wrong, so both final outcomes failed. DOM used 51.9% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_008-software-release-research-20260909T072902Z.json)
- [Comparison report](results/browser_task_008-software-release-research-20260909T072902Z/20260909T_task008_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_008-software-release-research-20260909T072902Z/20260909T_task008_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_008-software-release-research-20260909T072902Z/20260909T_task008_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_008-software-release-research-20260909T072902Z/20260909T_task008_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 28

Task ID: `browser_task_009-nasa-mission-lookup-20260909T073151Z`

Run: `20260909T_task009_data_new`

Frozen rubric: 7 criteria, 20 maximum points

Rubric SHA-256: `d8501aa855b5b07aec67fd374fcfe17455c57c18ab59a631d96ed88fe1d6fe4d`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 16/20 (80.0%) | 19/20 (95.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Pass |
| Overall verifier score | 0 | 1 |
| Actions / states | 5 / 6 screenshots | 5 / 6 DOM states |
| Scoring LLM calls | 20 | 33 |
| API attempts / retries | 20 / 0 | 33 / 0 |
| Duration | 95.384 s | 139.027 s |

Both modalities contained the same decisive mission-status evidence. The screenshot verifier correctly treated Artemis II's completed status as a core failure; the DOM verifier acknowledged that status but still awarded 3/4 and passed the outcome.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 121,878 | 13,041 | 2,688 | 134,919 |
| DOM model | 144,408 | 19,182 | 1,664 | 163,590 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 28,671 more scoring tokens, a 21.3% increase. Rubric generation was separate: 13,423 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Use NASA as source | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Identify next planned mission | “Occurred 5 months ago” visible / correctly used | Same status explicit / found but used incorrectly | 0/4 / 3/4 | BOTH_CAUGHT |
| Report mission name | Artemis II visible / Yes | Artemis II explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report launch year | April 1, 2026 visible / Yes | April 1, 2026 explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report destination | Crewed Lunar Flyby visible / Yes | Crewed Lunar Flyby explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report primary objective | Objective text visible / Yes | Objective text explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Respect constraints and stop | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot5.png` and `dom_model5.txt` both state that Artemis II “occurred 5 months ago” and launched April 1, 2026. Therefore, Artemis II cannot satisfy the task's “next planned” requirement. The DOM verifier did not miss this evidence: its own analysis cited both “Occurred 5 months ago” and past-tense “LaunchED,” but it treated the completed mission as a defensible next mission and passed the outcome. This is a DOM verifier reasoning/scoring error, not DOM evidence loss. The screenshot verifier correctly applied the same evidence and failed the outcome.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/7 criteria**
- DOM-side asymmetric source-evidence loss: **0/7 criteria**
- Confirmed verifier perception misses: **0/7 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**
- Confirmed evidence-use/scoring errors: **DOM 1/7; Screenshot 0/7**

**Summary:** Both modalities preserved and both verifiers found the decisive evidence that Artemis II had already occurred. The 3-point and outcome disagreement came from DOM-side overcrediting after the evidence was found, not from a difference in evidence availability. DOM used 21.3% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_009-nasa-mission-lookup-20260909T073151Z.json)
- [Comparison report](results/browser_task_009-nasa-mission-lookup-20260909T073151Z/20260909T_task009_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_009-nasa-mission-lookup-20260909T073151Z/20260909T_task009_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_009-nasa-mission-lookup-20260909T073151Z/20260909T_task009_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_009-nasa-mission-lookup-20260909T073151Z/20260909T_task009_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 29

Task ID: `browser_task_010-official-documentation-lookup-20260909T073335Z`

Run: `20260909T_task010_data_new`

Frozen rubric: 7 criteria, 18 maximum points

Rubric SHA-256: `a8d84181ec0fe09d117995b4c001e182821ba5ac9631538a68d8a8bf32054f90`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 6/18 (33.3%) | 4.5/18 (25.0%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 3 / 4 screenshots | 3 / 4 DOM states |
| Scoring LLM calls | 16 | 35 |
| API attempts / retries | 16 / 0 | 35 / 0 |
| Duration | 90.867 s | 161.148 s |

Both verifiers correctly concluded that the agent was blocked by Google's unusual-traffic CAPTCHA before reaching Gemini documentation. The 1.5-point difference came from how generously the judges credited the search attempt, partial constraint compliance, and stopping behavior.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 97,792 | 10,476 | 1,728 | 108,268 |
| DOM model | 160,833 | 27,256 | 2,432 | 188,089 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 79,821 more scoring tokens, a 73.7% increase. Rubric generation was separate: 13,255 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Attempt Google Search | Query + CAPTCHA present / Yes | Query + CAPTCHA explicit / Yes | 3/3 / 2/3 | BOTH_CAUGHT |
| Official domain and no sign-in | No docs; no sign-in / Yes | No docs; no sign-in / Yes | 1/3 / 1.5/3 | BOTH_CAUGHT |
| Documentation title | Absent / correctly rejected | Absent / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Documentation domain | Absent / correctly rejected | Absent / correctly rejected | 0/2 / 0/2 | BOTH_CAUGHT |
| Python SDK | Absent / correctly rejected | Absent / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Example model | Absent / correctly rejected | Absent / correctly rejected | 0/3 / 0/3 | BOTH_CAUGHT |
| Stop at blocker | Yes / Yes | Yes / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot3.png` visibly shows the reCAPTCHA checkbox and “Our systems have detected unusual traffic,” while `dom_model3.txt` explicitly preserves the same blocker text and the intended search URL. No screenshot or DOM state contains an opened Gemini API documentation page, page title, documentation domain, Python SDK, or model identifier. Both verifiers correctly identified those facts as absent. The score differences on the search-attempt, official-domain, and stopping criteria are judge/scoring variance over the same evidence, not evidence loss or verifier perception failure.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/7 criteria**
- DOM-side asymmetric source-evidence loss: **0/7 criteria**
- Confirmed verifier perception misses: **0/7 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both representations captured the same Google CAPTCHA blocker and omitted the same unavailable documentation details. Both verifiers reached the correct failed outcome; the 1.5-point process-score difference reflects scoring variance only. DOM used 73.7% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_010-official-documentation-lookup-20260909T073335Z.json)
- [Comparison report](results/browser_task_010-official-documentation-lookup-20260909T073335Z/20260909T_task010_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_010-official-documentation-lookup-20260909T073335Z/20260909T_task010_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_010-official-documentation-lookup-20260909T073335Z/20260909T_task010_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_010-official-documentation-lookup-20260909T073335Z/20260909T_task010_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 30

Task ID: `browser_task_011-arxiv-literature-search-20260909T073439Z`

Run: `20260909T_task011_data_new`

Frozen rubric: 6 criteria, 20 maximum points

Rubric SHA-256: `8154a1385faa60d8797d38cd3790be785d2a99dc77c1de0f22ef29f1e639920b`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 5/20 (25.0%) | 6/20 (30.0%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 9 / 10 screenshots | 9 / 10 DOM states |
| Scoring LLM calls | 24 | 29 |
| API attempts / retries | 24 / 0 | 29 / 0 |
| Duration | 128.630 s | 169.511 s |

Both verifiers found that the search used the title phrase, date range, and newest-first ordering but applied broad Computer Science filtering rather than `cs.LG` only. They also found that the agent reported the visible second result as Paper #1 and supplied unsupported Papers #2 and #3. Both therefore failed the task.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 162,507 | 16,522 | 1,856 | 179,029 |
| DOM model | 208,544 | 21,137 | 2,176 | 229,681 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 50,652 more scoring tokens, a 28.3% increase. Rubric generation was separate: 13,538 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Required search filters | Query summary visible / Yes | Query summary explicit / Yes | 3/4 / 3/4 | BOTH_CAUGHT |
| Most recent paper | Top result `2609.08682`; agent used #2 / Yes | Same ordering explicit / Yes | 0/3 / 0.5/3 | BOTH_CAUGHT |
| Second paper | Actual #2 visible; claimed paper absent / Yes | Same; claimed paper absent / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Third paper | Claimed paper absent / Yes | Claimed paper absent / Yes | 0/3 / 0/3 | BOTH_CAUGHT |
| Per-paper verification | One reported paper partly verifiable / Yes | Same facts explicit / Yes | 0/5 / 1.5/5 | BOTH_CAUGHT |
| Stop and constraints | No prohibited action; three items reported / Yes | Same action history / Yes | 2/2 / 1/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot9.png` and `dom_model9.txt` both expose the decisive result ordering: `2609.08682` (`cs.AR`) is first and `2609.08663` (`cs.LG`, `cs.AI`) is second. Both also expose the broad Computer Science query, exact title term, date range, and newest-first sorting. Neither representation supports the agent's claimed Papers #2 and #3. The screenshot verifier explicitly recovered the same result IDs, titles, authors, categories, and ordering as the DOM verifier.

The 1-point process-score difference is not an evidence miss. The DOM judge awarded minimal metadata credit to the real but incorrectly ordered `2609.08663`, plus partial verification credit, while the screenshot judge treated those criterion failures more strictly. The stop/constraints criterion also differed by one point because the screenshot judge credited stopping after three items in form, while the DOM judge penalized stopping without three substantiated matches.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/6 criteria**
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed verifier perception misses: **0/6 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both modalities contained and both verifiers recovered the same decisive search and result evidence. The DOM verifier scored 1 point higher through more generous partial-credit judgments, not because it recovered evidence missed by the screenshot verifier. DOM used 28.3% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_011-arxiv-literature-search-20260909T073439Z.json)
- [Comparison report](results/browser_task_011-arxiv-literature-search-20260909T073439Z/20260909T_task011_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_011-arxiv-literature-search-20260909T073439Z/20260909T_task011_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_011-arxiv-literature-search-20260909T073439Z/20260909T_task011_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_011-arxiv-literature-search-20260909T073439Z/20260909T_task011_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 31

Task ID: `browser_task_012-arxiv-paper-metadata-20260909T073715Z`

Run: `20260909T_task012_data_new`

Frozen rubric: 6 criteria, 13 maximum points

Rubric SHA-256: `0ba8db17cb7a714de473b135020ece47b0a8098f986ce2fc4f86e50d3dde449f`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 12.5/13 (96.2%) | 12.5/13 (96.2%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 17 |
| API attempts / retries | 12 / 0 | 17 / 0 |
| Duration | 81.525 s | 116.384 s |

Both verifiers confirmed that the agent reached arXiv entry `1706.03762`, complied with the constraints, correctly reported seven versions, and reproduced the exact v1 and v7 submission-history strings. Both deducted 0.5 point because the final answer included redundant header-summary dates beyond the three requested items.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 71,458 | 7,760 | 1,664 | 79,218 |
| DOM model | 81,023 | 13,143 | 2,880 | 94,166 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 14,948 more scoring tokens, an 18.9% increase. Rubric generation was separate: 13,030 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct arXiv entry | ID and history visible / Yes | ID and history explicit / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| No sign-in/download/edit | Actions show scroll only / Yes | Actions show scroll only / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Total versions | `v1`–`v7` visible / Yes | `v1`–`v7` explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Exact v1 date | Visible / Yes | Explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Exact latest date | `v7` visible / Yes | `v7` explicit / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop after requested items | Extra text in answer / Yes | Extra text in answer / Yes | 0.5/1 / 0.5/1 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot1.png` visibly shows the complete submission history from `v1` through `v7`, including `Mon, 12 Jun 2017 17:57:34 UTC (1,102 KB)` and `Wed, 2 Aug 2023 00:41:18 UTC (1,124 KB)`. `dom_model1.txt` preserves the same version sequence and exact strings. Both verifier analyses cited these values correctly.

The audit script flagged minor wording differences about constraint evidence, but manual review found no substantive disagreement: both relied on the one scroll action and correctly found no sign-in, PDF opening/download, or edit action.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/6 criteria**
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed verifier perception misses: **0/6 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Screenshot and DOM contained the same required metadata, both verifiers recovered it correctly, and both produced the identical passing score. There was no evidence loss or verifier perception miss. DOM used 18.9% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_012-arxiv-paper-metadata-20260909T073715Z.json)
- [Comparison report](results/browser_task_012-arxiv-paper-metadata-20260909T073715Z/20260909T_task012_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_012-arxiv-paper-metadata-20260909T073715Z/20260909T_task012_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_012-arxiv-paper-metadata-20260909T073715Z/20260909T_task012_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_012-arxiv-paper-metadata-20260909T073715Z/20260909T_task012_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 32

Task ID: `browser_task_013-chess-profile-lookup-20260909T073812Z`

Run: `20260909T_task013_data_new`

Frozen rubric: 4 criteria, 13 maximum points

Rubric SHA-256: `1db9087c848d5ad336f7c063babff47c82c0d673cec6184a853a62ab5e162c17`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 11/13 (84.6%) | 13/13 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 2 / 3 screenshots | 2 / 3 DOM states |
| Scoring LLM calls | 15 | 32 |
| API attempts / retries | 15 / 0 | 32 / 0 |
| Duration | 93.296 s | 120.403 s |

Both verifiers confirmed that the agent reached Magnus Carlsen’s logged-out Chess.com profile, reported Blitz `3316` and Bullet `3184`, avoided prohibited interactions, and stopped. The score difference concerns whether the adjacent rating-change indicators were part of “exactly as displayed.”

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 76,260 | 8,575 | 2,880 | 84,835 |
| DOM model | 134,935 | 13,952 | 1,216 | 148,887 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 64,052 more scoring tokens, a 75.5% increase. Rubric generation was separate: 12,691 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. The DOM pipeline recorded 2 fallback invocations but no API retries.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct logged-out profile | Present / Yes | Present / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Blitz exactly displayed | `3316 ↓63` / Yes | `3316 63`; arrow semantics absent / Partial | 3/4 / 4/4 | DOM_EVIDENCE_MISSING |
| Bullet exactly displayed | `3184 ↓73` / Yes | `3184 73`; arrow semantics absent / Partial | 3/4 / 4/4 | DOM_EVIDENCE_MISSING |
| Constraints and stopping | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot2.png` visibly displays Blitz `3316` with a red `↓ 63` indicator and Bullet `3184` with a red `↓ 73` indicator. The screenshot verifier recovered these symbols and deducted one point from each exact-display criterion because the agent reported only the rating numbers.

`dom_model2.txt` preserves the core ratings and adjacent magnitudes as flattened text—`Blitz 3316 63` and `Bullet 3184 73`—but does not preserve the downward arrows, color, or the semantic relationship identifying those numbers as rating decreases. The DOM verifier therefore treated `3316` and `3184` as exact rating values and awarded full credit. This is partial DOM representation loss for the exact-formatting evidence, not a failure to recover the core rating values.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/4 criteria**
- DOM-side asymmetric source-evidence loss: **2/4 criteria**, limited to rating-change symbol semantics
- Confirmed screenshot-verifier perception misses: **0/4 criteria**
- Confirmed DOM-verifier perception misses: **0/4 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both modalities and verifiers recovered the correct Blitz and Bullet rating numbers. Screenshot evidence additionally preserved the downward-change indicators, while DOM flattened away their arrow semantics; this produced two extra DOM points under the rubric’s exact-display requirement. DOM used 75.5% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_013-chess-profile-lookup-20260909T073812Z.json)
- [Comparison report](results/browser_task_013-chess-profile-lookup-20260909T073812Z/20260909T_task013_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_013-chess-profile-lookup-20260909T073812Z/20260909T_task013_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_013-chess-profile-lookup-20260909T073812Z/20260909T_task013_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_013-chess-profile-lookup-20260909T073812Z/20260909T_task013_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 33

Task ID: `browser_task_014-reddit-post-lookup-20260909T073959Z`

Run: `20260909T_task014_data_new`

Frozen rubric: 5 criteria, 17 maximum points

Rubric SHA-256: `c8d413abd02711e0a624ff57822d29e0edd9802c5c75a62c9d86a86d76b9962a`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 17/17 (100.0%) | 17/17 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 0 / 1 screenshot | 0 / 1 DOM state |
| Scoring LLM calls | 10 | 11 |
| API attempts / retries | 10 / 0 | 11 / 0 |
| Duration | 81.392 s | 98.477 s |

Both verifiers confirmed that Reddit blocked the environment before the agent could access r/MachineLearning, apply the requested filters, open a post, or recover its metadata. The rubric awarded full process credit under its uncontrollable-blocker rules, while the outcome check correctly remained failed because the requested post details were not obtained.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 56,646 | 6,067 | 1,536 | 62,713 |
| DOM model | 55,639 | 8,671 | 3,264 | 64,310 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 1,597 more scoring tokens, a 2.5% increase. Rubric generation was separate: 12,783 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Apply Top + past month | Blocker present / Yes | Blocker explicit / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Open highest-ranked post | No listing due to blocker / Yes | No listing due to blocker / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Report post metadata | Metadata absent due to blocker / Yes | Metadata absent due to blocker / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| No sign-in/interactions | Logged-out blocker; no actions / Yes | Same / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop at blocker | Stopped with explanation / Yes | Same / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` clearly displays “You've been blocked by network security,” with only “Log in” and “File a ticket” options. `dom_model0.txt` preserves the same blocker message, Reddit URL, and options. Neither representation contains a subreddit post list, filtering controls, or post title/author/score/comment data.

The DOM file’s missing page-title warning did not remove any criterion-relevant evidence: the URL and complete blocker text were retained, and the DOM verifier cited them correctly.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/5 criteria**
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Screenshot and DOM captured the same Reddit network-security blocker, and both verifiers interpreted it consistently. Process scores were perfect under blocker-aware rubric rules, but both outcome checks failed because the requested post metadata was unavailable. There was no evidence loss or perception miss; DOM used 2.5% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_014-reddit-post-lookup-20260909T073959Z.json)
- [Comparison report](results/browser_task_014-reddit-post-lookup-20260909T073959Z/20260909T_task014_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_014-reddit-post-lookup-20260909T073959Z/20260909T_task014_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_014-reddit-post-lookup-20260909T073959Z/20260909T_task014_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_014-reddit-post-lookup-20260909T073959Z/20260909T_task014_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 34

Task ID: `browser_task_015-reddit-community-comparison-20260909T074040Z`

Run: `20260909T_task015_data_new`

Frozen rubric: 5 criteria, 15 maximum points

Rubric SHA-256: `002aa1d1eda9e7069a08c8bbb68a6d7c9e6e1ecf1dd4fd815d396f69641e6158`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 15/15 (100.0%) | 15/15 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 0 / 1 screenshot | 0 / 1 DOM state |
| Scoring LLM calls | 10 | 19 |
| API attempts / retries | 10 / 0 | 19 / 0 |
| Duration | 75.883 s | 132.279 s |

Both verifiers confirmed that Reddit’s network-security block prevented the agent from accessing r/Python, r/learnpython, and r/django, obtaining subscriber counts, or producing the requested ranking table. Blocker-aware rubric rules awarded full process credit, while both outcome checks failed because the requested comparison was not completed.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 56,220 | 6,521 | 2,240 | 62,741 |
| DOM model | 71,082 | 11,986 | 2,304 | 83,068 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 20,327 more scoring tokens, a 32.4% increase. Rubric generation was separate: 12,794 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. The DOM pipeline recorded 1 fallback invocation but no API retry.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| r/Python subscriber count | Blocker; count absent / Yes | Blocker; count absent / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| r/learnpython subscriber count | Shared blocker; count absent / Yes | Shared blocker; count absent / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| r/django subscriber count | Shared blocker; count absent / Yes | Shared blocker; count absent / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Ranking table | Inputs unavailable / Yes | Inputs unavailable / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Constraints and stop | No prohibited action; stopped / Yes | Same / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` clearly shows Reddit’s “You've been blocked by network security” page and only the “Log in” and “File a ticket” options. `dom_model0.txt` preserves the same blocker text and the r/Python URL. Neither source contains subscriber counts for any of the three communities or a ranking table.

The DOM file’s missing page-title warning does not affect criterion evidence because the platform URL and blocker text remain explicit. The audit script’s minor wording flags do not reflect a substantive disagreement; both verifiers reached the same evidence conclusions.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/5 criteria**
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both modalities captured and both verifiers recognized the same Reddit-wide access blocker. There was no evidence loss or perception miss. Both received full blocker-aware process credit but failed the outcome because no subscriber counts or ranking were obtained. DOM used 32.4% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_015-reddit-community-comparison-20260909T074040Z.json)
- [Comparison report](results/browser_task_015-reddit-community-comparison-20260909T074040Z/20260909T_task015_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_015-reddit-community-comparison-20260909T074040Z/20260909T_task015_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_015-reddit-community-comparison-20260909T074040Z/20260909T_task015_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_015-reddit-community-comparison-20260909T074040Z/20260909T_task015_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 35

Task ID: `browser_task_016-hugging-face-model-metadata-20260909T074128Z`

Run: `20260909T_task016_data_new`

Frozen rubric: 5 criteria, 13 maximum points

Rubric SHA-256: `3ae38854ed411b9031803fe22503d5d4c10c2cf432936e9016379e99e0ae71fd`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 13/13 (100.0%) | 13/13 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 15 |
| API attempts / retries | 12 / 0 | 15 / 0 |
| Duration | 61.647 s | 75.660 s |

Both verifiers confirmed that the agent was on the requested Hugging Face repository and correctly reported its visible license (`llama3.1`), likes count (`6.85k`), and gated status while remaining logged out and stopping without requesting access or downloading files.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 64,902 | 5,972 | 1,600 | 70,874 |
| DOM model | 88,114 | 7,437 | 1,472 | 95,551 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 24,677 more scoring tokens, a 34.8% increase. Rubric generation was separate: 12,599 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither scoring pipeline recorded an API retry or fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct Hugging Face repository | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| License name | `License: llama3.1` / Yes | `License: llama3.1` / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Current likes count | `6.85k` / Yes | `like 6.85k` / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Repository gated status | Access-agreement banner / Yes | Same banner text / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Constraints and stopping | Logged out; no prohibited action / Yes | Same plus wait-only history / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` and `screenshot1.png` visibly contain the exact repository slug, license badge, `6.85k` like count, and the banner stating that contact-information sharing must be agreed to before accessing the model. The logged-out controls are visible, and there is no indication of an access request or download.

`dom_model0.txt` and `dom_model1.txt` preserve the same evidence explicitly, including the URL/title, `License: llama3.1`, `like 6.85k`, the gating notice, and `Log In` / `Sign Up`. Neither DOM state was truncated and the run recorded no context omissions or evidence warnings.

The offline audit flagged two intermediate `environment_issues_confirmed` wording mismatches. These are not substantive evidence disagreements: both verifiers cited the same facts, awarded identical points, and reached the same final outcome.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/5 criteria**
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed screenshot-verifier perception misses: **0/5 criteria**
- Confirmed DOM-verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Screenshot and DOM contained the same required Hugging Face metadata, both verifiers recovered it correctly, and both produced the identical passing score. There was no evidence loss or verifier perception miss. DOM used 34.8% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_016-hugging-face-model-metadata-20260909T074128Z.json)
- [Comparison report](results/browser_task_016-hugging-face-model-metadata-20260909T074128Z/20260909T_task016_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_016-hugging-face-model-metadata-20260909T074128Z/20260909T_task016_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_016-hugging-face-model-metadata-20260909T074128Z/20260909T_task016_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_016-hugging-face-model-metadata-20260909T074128Z/20260909T_task016_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 36

Task ID: `browser_task_017-hugging-face-dataset-inspection-20260909T074239Z`

Run: `20260909T_task017_data_new`

Frozen rubric: 4 criteria, 12 maximum points

Rubric SHA-256: `432739090bfbc188d44079a449ae58637894eaf19a08f1d997ece6a4385e886c`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 3/12 (25.0%) | 7/12 (58.3%) |
| Rubric threshold | Fail | Fail |
| Final outcome | Fail | Fail |
| Overall verifier score | 0 | 0 |
| Actions / states | 0 / 1 screenshot | 0 / 1 DOM state |
| Scoring LLM calls | 10 | 13 |
| API attempts / retries | 10 / 0 | 13 / 0 |
| Duration | 73.538 s | 94.652 s |

Both verifiers found the correct `rajpurkar/squad` page, the rendered Dataset Viewer, and the visible train split count. The agent’s final answer reported only a generic action-generation failure and did not provide either requested split count, so both outcome checks failed. The DOM process score is higher because it incorrectly awarded the train-count criterion based on evidence availability alone.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 52,499 | 6,249 | 2,176 | 58,748 |
| DOM model | 78,381 | 7,940 | 2,368 | 86,321 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 27,573 more scoring tokens, a 46.9% increase. Rubric generation was separate: 12,522 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry, and the DOM pipeline recorded no fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct SQuAD page and viewer | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Train split count | `train · 87.6k rows` / Yes | `train`, `87.6k rows` / Yes | 0/4 / 4/4 | BOTH_CAUGHT |
| Validation split count | Absent / correctly identified | Absent / correctly identified | 0/4 / 0/4 | BOTH_CAUGHT |
| Constraints and stopping | Logged out; task incomplete / Yes | Same / Yes | 1/2 / 1/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` visibly shows the correct dataset page, a rendered Dataset Viewer, and the selected split as `train · 87.6k rows`. The validation split count is not visible because the split selector is not expanded. `dom_model0.txt` preserves the same page identity and train count on lines 74–76, but it likewise contains no validation split value.

Both verifiers correctly extracted the train evidence. The screenshot scorer then correctly gave 0/4 because the rubric requires the agent to record/report the value, and the final answer did not do so. The DOM scorer instead gave 4/4 merely because the value was present in the DOM, explicitly acknowledging that the agent did not report it. This is an overcrediting judgment by the DOM verifier, not a difference in evidence capture or recovery.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **0/4 criteria**
- DOM-side asymmetric source-evidence loss: **0/4 criteria**
- Confirmed screenshot-verifier perception misses: **0/4 criteria**
- Confirmed DOM-verifier perception misses: **0/4 criteria**
- DOM scoring/judgment errors: **1/4 criteria** (train count overcredited)
- DOM recovery of screenshot verifier misses: **N/A (0 eligible misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible misses)**

**Summary:** Both representations exposed the same relevant evidence and both verifiers recovered it. The 4-point score gap is not evidence loss: the DOM scorer overcredited a train count that the agent never reported. Both final outcomes correctly failed, and DOM used 46.9% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z.json)
- [Comparison report](results/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z/20260909T_task017_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z/20260909T_task017_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z/20260909T_task017_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_017-hugging-face-dataset-inspection-20260909T074239Z/20260909T_task017_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 37

Task ID: `browser_task_018-github-issue-search-20260909T074333Z`

Run: `20260909T_task018_data_new`

Frozen rubric: 5 criteria, 11 maximum points

Rubric SHA-256: `1070898bbbc7964a59520ec21c339408ad17d6faca93bcb2306f1ef43249e9a0`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 10.5/11 (95.5%) | 11/11 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Pass | Pass |
| Overall verifier score | 1 | 1 |
| Actions / states | 3 / 4 screenshots | 3 / 4 DOM states |
| Scoring LLM calls | 16 | 18 |
| API attempts / retries | 16 / 0 | 18 / 0 |
| Duration | 96.514 s | 94.019 s |

Both verifiers confirmed the correct repository issue search, exact filter query, count of 17 matching open issues, three newest issue numbers and titles, and compliance with the no-sign-in/no-interaction constraints. The screenshot verifier deducted 0.5 points because the agent additionally reported absolute opened dates that were not visible in the pixels; the DOM contained those exact dates.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 96,379 | 9,434 | 1,536 | 105,813 |
| DOM model | 109,237 | 10,460 | 1,472 | 119,697 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 13,884 more scoring tokens, a 13.1% increase. Rubric generation was separate: 12,679 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry, and the DOM pipeline recorded no fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Correct repo and date basis | Present / Yes | Present / Yes | 1/1 / 1/1 | BOTH_CAUGHT |
| Exact issue filters | Present / Yes | Present / Yes | 4/4 / 4/4 | BOTH_CAUGHT |
| Matching issue count | `Open 17` / Yes | `Open 17` / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Three newest issue records | Numbers/titles caught; exact dates absent | Numbers/titles and exact dates / Yes | 2.5/3 / 3/3 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints and stopping | Present / Yes | Present / Yes | 1/1 / 1/1 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot3.png` shows the final filtered list ordered by Newest, `Open 17`, and the first three matching issues as #48633, #48630, and #48626 with the titles reported by the agent. It displays only relative timestamps: `opened 2h ago`, `opened 8h ago`, and `opened 12h ago`.

`dom_model3.txt` preserves the same filter, count, issue ordering, numbers, and titles, but also exposes the corresponding absolute dates: #48633 opened Sep 9, 2026; #48630 and #48626 opened Sep 8, 2026. Thus, the screenshot verifier did not overlook visible text; the pixel representation lacked the exact dates that were available in DOM evidence.

The differing action-only points for the count and newest-issues criteria are independent judge variance. Both evidence stages recovered the required count and issue records. The remaining final 0.5-point difference is attributable to the screenshot-only absence of absolute date metadata.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **1/5 criteria** (absolute opened dates)
- DOM-side asymmetric source-evidence loss: **0/5 criteria**
- Confirmed screenshot-verifier perception misses: **0/5 criteria**
- Confirmed DOM-verifier perception misses: **0/5 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible perception misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible perception misses)**

**Summary:** Both verifiers recovered all rubric-required issue-search evidence and passed the task. DOM additionally preserved exact opened dates that the screenshot represented only as relative times, avoiding a 0.5-point screenshot deduction. This is screenshot representation loss, not a screenshot-verifier perception miss. DOM used 13.1% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_018-github-issue-search-20260909T074333Z.json)
- [Comparison report](results/browser_task_018-github-issue-search-20260909T074333Z/20260909T_task018_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_018-github-issue-search-20260909T074333Z/20260909T_task018_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_018-github-issue-search-20260909T074333Z/20260909T_task018_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_018-github-issue-search-20260909T074333Z/20260909T_task018_data_new/evidence_error_audit/evidence_error_report.md)

---

## Task 38

Task ID: `browser_task_019-github-release-research-20260909T074525Z`

Run: `20260909T_task019_data_new`

Frozen rubric: 6 criteria, 16 maximum points

Rubric SHA-256: `b6de0067c9d19eb4956371b6c427ccb33bacfad0dbf9df5d089946db8cfcac71`

### Result

| Metric | Screenshot | DOM model |
|---|---:|---:|
| Process score | 14/16 (87.5%) | 16/16 (100.0%) |
| Rubric threshold | Pass | Pass |
| Final outcome | Fail | Pass |
| Overall verifier score | 0 | 1 |
| Actions / states | 1 / 2 screenshots | 1 / 2 DOM states |
| Scoring LLM calls | 12 | 23 |
| API attempts / retries | 12 / 0 | 23 / 0 |
| Duration | 80.199 s | 117.278 s |

Both verifiers confirmed the latest PyTorch release, tag, first three highlight bullets, and stopping behavior. The screenshot verifier could not validate the agent’s exact release date because the pixel evidence displayed only a relative time. The DOM preserved the exact timestamp and therefore passed the outcome.

### Token usage

| Mode | Prompt | Completion | Reasoning* | Total |
|---|---:|---:|---:|---:|
| Screenshot | 68,481 | 7,646 | 1,920 | 76,127 |
| DOM model | 103,171 | 12,413 | 1,152 | 115,584 |

*Reasoning tokens are included within completion tokens and are not added again.*

DOM used 39,457 more scoring tokens, a 51.8% increase. Rubric generation was separate: 12,644 tokens across 2 calls; scoring reported `rubric_generation_calls: 0` for both modes. Neither mode recorded an API retry. The DOM pipeline recorded one fallback invocation.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Access releases listing | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Latest release | `PyTorch 2.14.0`, Latest / Yes | Same / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Release tag | `v2.14.0` / Yes | `v2.14.0` / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Exact release date | Only `last week`; exact date absent | `02 Sep 17:40` / Yes | 0/2 / 2/2 | SCREENSHOT_EVIDENCE_MISSING |
| First three highlights | Present / Yes | Present / Yes | 5/5 / 5/5 | BOTH_CAUGHT |
| Stopping condition | Present / Yes | Present / Yes | 2/2 / 2/2 | BOTH_CAUGHT |

Manual inspection confirmed that `screenshot0.png` displays the release as `PyTorch 2.14.0 Release`, marks it `Latest`, shows tag `v2.14.0`, but gives only the relative timestamp `ethche released this last week`. `screenshot1.png` clearly shows the first three Highlights in the same order reported by the agent.

`dom_model0.txt` preserves the same release metadata and additionally exposes `ethche released this 02 Sep 17:40` and `02 Sep 17:40`, exactly matching the agent’s final answer. Both DOM states preserve the highlight text. The exact date was therefore available only in the DOM representation.

The action-only point differences are independent judge variance and were resolved by evidence for every criterion except the release date. The final 2-point and outcome difference is attributable to the exact timestamp being absent from the screenshot pixels but present in DOM evidence.

### Evidence-error result

- Screenshot-side asymmetric source-evidence loss: **1/6 criteria** (exact release timestamp)
- DOM-side asymmetric source-evidence loss: **0/6 criteria**
- Confirmed screenshot-verifier perception misses: **0/6 criteria**
- Confirmed DOM-verifier perception misses: **0/6 criteria**
- DOM recovery of screenshot verifier misses: **N/A (0 eligible perception misses)**
- Screenshot recovery of DOM verifier misses: **N/A (0 eligible perception misses)**

**Summary:** Both verifiers recovered all shared release evidence correctly. DOM additionally preserved the exact absolute release timestamp, while the screenshot showed only “last week”; this caused the screenshot’s 2-point deduction and failed outcome. It is screenshot representation loss, not verifier perception failure. DOM used 51.8% more scoring tokens.

### Artifacts

- [Frozen rubric](rubrics/browser_task_019-github-release-research-20260909T074525Z.json)
- [Comparison report](results/browser_task_019-github-release-research-20260909T074525Z/20260909T_task019_data_new/comparison.md)
- [Screenshot metrics](results/browser_task_019-github-release-research-20260909T074525Z/20260909T_task019_data_new/microsoft_verifier/run_metrics.json)
- [DOM metrics](results/browser_task_019-github-release-research-20260909T074525Z/20260909T_task019_data_new/dom_model/run_metrics.json)
- [Offline evidence audit](results/browser_task_019-github-release-research-20260909T074525Z/20260909T_task019_data_new/evidence_error_audit/evidence_error_report.md)


---

## Task 39

Completed using all 5 screenshots and 5 DOM-model states.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Score | 10/18 (55.6%) | 10/18 (55.6%) |
| Outcome | Fail | Fail |
| LLM calls | 18 | 26 |
| Total tokens | 112,647 | 138,127 |
| Validation retries | — | 8 |
| Fallbacks | — | 0 |

Rubric generation was separate: 2 calls and 13,479 tokens.

### Evidence audit

| Criterion | Screenshot present/caught | DOM present/caught | Score SS / DOM | Classification |
| --- | --- | --- | --- | --- |
| Correct Homebrew source | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Stable version | 9.0.1 visible / Yes | Missing / correctly unsupported | 0 / 0 | DOM_EVIDENCE_MISSING |
| License | GPL-3.0-or-later / Yes | Same / Yes | 0 / 0 | BOTH_CAUGHT |
| Regular dependencies | All 11 / Yes | All 11 / Yes | 6 / 6 | BOTH_CAUGHT |
| Apple Silicon bottles | Rows visible, status glyph unclear / Yes | Explicit checkmarks / Yes | 0 / 1 | SCREENSHOT_EVIDENCE_MISSING |
| Linux bottles | Rows visible, exact status unclear / Yes | Missing / correctly unsupported | 0 / 0 | BOTH_CAUGHT |
| Scope/stopping | Yes / Yes | Yes / Yes | 2 / 1 | BOTH_CAUGHT |

Neither verifier demonstrably missed evidence available in its representation:

- Screenshot evidence-miss rate: 0/7 = 0%
- DOM evidence-miss rate: 0/7 = 0%
- Recovery metric: not applicable

The equal totals hide different attribution: DOM gained one point for explicit Apple Silicon
checkmarks but lost one point on stopping/scope.

## Task 40

Completed.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Score | 12/16 (75%) | 8/16 (50%) |
| Outcome | Failed | Failed |
| Evaluation calls | 45 | 61 |
| Evaluation tokens | 232,672 | 243,687 |

DOM used 11,015 more tokens (+4.73%). Rubric generation was separate: 2 calls and 13,119 tokens.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
| --- | --- | --- | --- | --- |
| C0 IANA page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| C1 TLD type | Yes / Yes | Yes / Yes | 1.5 / 1.5 | BOTH_CAUGHT |
| C2 Sponsor | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| C3 Registration date | Yes / Yes | No / N/A | 0 / 0 | DOM_EVIDENCE_MISSING |
| C4 WHOIS server | Yes / Yes | No / N/A | 2 / 0 | DOM_EVIDENCE_MISSING |
| C5 Registration website | Yes / Yes | No / N/A | 2 / 0 | DOM_EVIDENCE_MISSING |
| C6 Constraints | Actions / Yes | Actions / Yes | 1.5 / 1.5 | BOTH_CAUGHT |

The screenshots clearly showed:

- Registration date: 2001-10-20
- WHOIS server: whois.nic.museum
- Registration-services URL: https://about.museum

The DOM-model states did not contain these three fields. Many corresponding DOM states had
returnedNodes=0, even though the screenshots visibly contained the page’s lower section.

The agent incorrectly reported the registration date as 2001-10-08, so both verifiers correctly gave
C3 zero. For C4 and C5, the screenshot verifier could validate the correct values, while the DOM
verifier correctly treated them as unsupported.

## Task 41

Completed.

| Metric | Screenshot | DOM model |
| --- | --- | --- |
| Score | 22.5/25 (90%) | 23/25 (92%) |
| Rubric pass | Yes | Yes |
| Outcome | Failed | Passed |
| Evaluation calls | 21 | 43 |
| Evaluation tokens | 141,830 | 244,050 |

DOM used 102,220 more tokens (+72.07%). Rubric generation was separate: 2 calls and 14,086 tokens.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
| --- | --- | --- | --- | --- |
| C0 CVE.org source | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| C1 Status | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| C2 Publication date | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| C3 CNA name | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| C4 Vendor | Yes / Yes | No / N/A | 0 / 0.5 | DOM_EVIDENCE_MISSING |
| C5 Product | Yes / Yes | Narrative / Yes | 1.5 / 1.5 | BOTH_CAUGHT |
| C6 Version statement | Yes / Yes | Yes / Yes | 5 / 5 | BOTH_CAUGHT |
| C7 First reference | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| C8 Constraints | Actions / Yes | Actions / Yes | 4 / 4 | BOTH_CAUGHT |

The screenshot explicitly showed:

- Vendor: Apache Software Foundation
- Product: Apache Log4j2

The agent answered Vendor: Apache, which is incorrect. The screenshot verifier caught this and correctly failed
the outcome.

The DOM states omitted the structured Vendor/Product table. Because the DOM only contained narrative text such as
“Apache Log4j2,” the DOM verifier inferred that Apache was plausible, awarded minimal vendor credit, and
incorrectly passed the overall outcome.

So this is not a case where the DOM verifier missed evidence available in DOM. It is a DOM source-evidence
omission that caused a false-positive/overcredit. All seven DOM files were passed to the verifier with no context
truncation or excluded states.

## Task 42

Completed successfully.

| Metric | Screenshot | DOM-model |
| --- | --- | --- |
| Score | 15/15 (100%) | 14/15 (93.3%) |
| Outcome success | Yes | No |
| LLM calls | 14 | 22 |
| Total tokens | 78,530 | 108,179 |
| Rubric-generation calls during scoring | 0 | 0 |

DOM used 29,649 more tokens (+37.75%). The separate frozen-rubric generation used 12,413 tokens.

| Criterion | Screenshot present/caught | DOM present/caught | Score SS / DOM | Classification |
| --- | --- | --- | --- | --- |
| Correct UNRATE page | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Metadata | Yes / Yes | Partial / Yes | 4 / 3 | DOM_EVIDENCE_MISSING |
| Latest 3 observations | Yes / Yes | Yes / Yes | 6 / 6 | BOTH_CAUGHT |
| Stop after requested work | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |

The DOM representation contained Frequency: Monthly and Seasonally Adjusted, but did not preserve a reliable
relationship between the Units: label and Percent. Percent appeared only in chart-axis text. Therefore, the DOM
verifier correctly withheld one point—it did not miss available evidence; the DOM source lacked the necessary
metadata association.

## Task 43

Completed.

| Metric | Screenshot | DOM-model |
| --- | --- | --- |
| Score | 8/16 (50%) | 13/16 (81.25%) |
| Rubric pass | No | Yes |
| Outcome success | No | No |
| LLM calls | 12 | 22 |
| Total tokens | 78,674 | 98,127 |

DOM used 19,453 more tokens (+24.73%). Rubric generation used another 13,147 tokens separately.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
| --- | --- | --- | --- | --- |
| Exact record | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Title | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Creation date | No | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Institution | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Type of item | Yes / Yes | No | 1 / 0 | DOM_EVIDENCE_MISSING |
| Rights | No/obscured | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Identifier | No | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |

There were no clear verifier evidence misses. The five-point DOM advantage came from evidence availability: the
DOM explicitly contained the creation date, rights, and identifiers that were not visible in the screenshots.
Conversely, the screenshot showed the full type value, while the DOM omitted it.

## Task 44

Completed after correcting both task42 dataset URLs to the resolved edition. No verifier code was changed.

| Metric | Screenshot | DOM-model |
| --- | --- | --- |
| Score | 15/15 (100%) | 13/15 (86.7%) |
| Rubric pass | Yes | Yes |
| Outcome success | Yes | No |
| LLM calls | 22 | 29 |
| Total tokens | 132,961 | 153,671 |

DOM used 20,710 more tokens (+15.58%). Rubric generation used 13,679 tokens separately.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
| --- | --- | --- | --- | --- |
| ISBN-resolved edition | Yes / Yes | Yes / Yes | 3 / 2 | BOTH_CAUGHT; scoring disagreement |
| Title | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Author | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Publish Date | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Publisher | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Language | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Page count | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| ISBN-13 | Yes / Yes | Partial / Yes | 2 / 1 | DOM_EVIDENCE_MISSING |
| Constraints/stopping | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |

Why DOM lost two points:

- It found the correct edition and ISBN but deducted one point because the original ISBN redirect was not
    demonstrated. The screenshot verifier accepted the starting context plus displayed ISBN. This is a scoring-
    judgment difference, not missed evidence.

- The DOM contained 9780141439518 inside an editions-table row, but lost the explicit ISBN 13 → value field
    relationship that was clearly visible in screenshots. The DOM verifier caught the digits but awarded partial
    credit. This is a DOM representation limitation, not a verifier miss.
