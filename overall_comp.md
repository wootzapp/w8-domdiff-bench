# Overall Comparison

## Task 26

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

## Task 29

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

## Task 30

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

## Task 31

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

## Task 32

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

## Task 33

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

## Task 35

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

## Task 37

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

## Task 38

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

## Task 39

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

## Task 40

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

## Task 41

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

## Task 42

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

## Task 43

Completed.

| Metric | Screenshot | DOM-model |
| --- | --- | --- |
| Score | 13/20 (65%) | 12/20 (60%) |
| Rubric pass | No | No |
| Outcome success | No | No |
| LLM calls | 12 | 28 |
| Total tokens | 94,179 | 137,496 |

DOM used 43,317 more tokens (+45.99%). Rubric generation used 14,294 tokens separately.

| Criterion | Screenshot | DOM | SS / DOM | Audit |
| --- | --- | --- | --- | --- |
| Correct page | Caught | Caught | 2 / 2 | BOTH_CAUGHT |
| Author | Caught | Evidence incomplete | 2 / 0 | DOM_EVIDENCE_MISSING |
| Release Date | Evidence missing | Caught | 0 / 3 | SCREENSHOT_EVIDENCE_MISSING |
| Last Update | Evidence missing | Caught | 0 / 3 | SCREENSHOT_EVIDENCE_MISSING |
| Language | Caught | Evidence missing | 2 / 0 | DOM_EVIDENCE_MISSING |
| EPUB3 | Caught | Caught | 2 / 2 | BOTH_CAUGHT |
| Plain Text | Evidence missing | Caught | 2 / 0 | SCREENSHOT_EVIDENCE_MISSING |
| HTML ZIP | Evidence missing | Evidence missing | 2 / 0 | BOTH SOURCES MISSING |
| Constraints | Caught | Caught | 1 / 2 | Scoring disagreement |

Key finding: the screenshot verifier scored slightly higher mainly because it was more lenient when evidence was
missing. It awarded full credit for “Plain Text (accessible)” and “Download HTML (zip)” even though the requested
availability was not established visually.

The DOM explicitly contained the offscreen Plain Text (accessible) link, so it correctly identified the agent’s
“not visible/not listed” claim as wrong. It also recovered both exact dates absent from the screenshots.
Conversely, the DOM omitted the formal author value and dedicated Language field that were visible in screenshot
1.

## Task 45

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

## Task 46

Completed.

| Verifier | Score | Outcome | Calls | Tokens |
| --- | --- | --- | --- | --- |
| Microsoft screenshot | 5/22 (22.7%) | False | 44 | 269,979 |
| DOM-model | 5.5/22 (25%) | False | 53 | 399,226 |

DOM used 129,247 more tokens (+47.87%).

| Criterion | Screenshot | DOM model | Audit |
| --- | --- | --- | --- |
| Search term | Present and caught: 2/2 | Present and caught: 2/2 | BOTH_CAUGHT |
| Required filters | Phase 3 visibly unchecked; caught: 2/4 | Checkbox state not preserved; inferred unconfirmed: 2/4 | DOM_EVIDENCE_MISSING |
| Newest-first sort | Screenshot10 shows Relevance selected; caught: 0/2 | Dropdown state missing; attempt received 0.5/2 | DOM_EVIDENCE_MISSING |
| Result #1 | Partial card visible, but not reported: 0/4 | Partial card data present, but not reported: 0/4 | BOTH_CAUGHT |
| Result #2 | Not reported: 0/4 | Not reported: 0/4 | BOTH_CAUGHT |
| Result #3 | Not reported: 0/4 | Not reported: 0/4 | BOTH_CAUGHT |
| Constraints/stopping | Incomplete stop: 1/2 | Incomplete stop: 1/2 | BOTH_CAUGHT |

The DOM verifier’s extra 0.5 point was not recovered evidence. It gave minimal partial credit for attempting to
select “Newest First,” while the screenshot verifier gave zero because the screenshot explicitly showed that
Relevance remained selected.

Confirmed verifier misses:

- Screenshot verifier misses: 0
- DOM verifier misses: 0
- DOM source omissions: 2—the explicit Phase 3 checkbox state and sort-menu selection.
- Recovery rates: N/A, because neither verifier missed evidence that was available in its own representation.

## Task 47

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

## Task 48

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

## Task 49

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

## Test 1 rerun — Homebrew ffmpeg

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

## Test 2 rerun — IANA .museum registry lookup

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

## Test 3 rerun — CVE-2021-44228 CNA record

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

## Test 4 rerun — FRED UNRATE observations

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

## Test 5 rerun — Europeana The Milkmaid metadata

`test_5` is a fresh rerun of Task 41 (`browser_task_051-cultural-object-metadata`) using the exact same frozen rubric content, hash, seven-criterion order, and 16-point denominator. Only the outer task identifier reflects the new capture timestamp. No rubric-generation model calls or tokens were used for this rerun.

| Verifier | Score | Outcome | Calls | Tokens |
|---|---:|:---:|---:|---:|
| Microsoft screenshot | 10/16 (62.5%) | False | 16 | 108,674 |
| DOM-model | 12/16 (75%) | False | 43 | 169,147 |

DOM used 60,473 more evaluation tokens (+55.65%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Exact Europeana record | Actions / Yes | URL / Yes | 3 / 3 | BOTH_CAUGHT |
| Title | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Creation date | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Providing institution | No / N/A | No / N/A | 0 / 0 | Missing in both; not a verifier miss |
| Item type | No / N/A | No / N/A | 0 / 0 | Missing in both; not a verifier miss |
| Rights statement | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Identifier | Actions / Yes | URL / Yes | 2 / 2 | BOTH_CAUGHT |

The two-point DOM advantage came entirely from source coverage: every DOM state explicitly contained the title “The Milkmaid,” while none of the four screenshots displayed the title as text. The screenshot verifier therefore did not overlook visible evidence; the screenshot representation lacked it. Both representations lacked the providing-institution and item-type fields, and both verifiers correctly rejected those unsupported agent claims.

No verifier perception miss was confirmed. Screenshot-only asymmetric evidence loss was 1/7 criteria (14.3%), while DOM-only asymmetric evidence loss was 0/7. This rerun still used more DOM calls and tokens despite its title-coverage advantage.

## Test 6 rerun — Open Library ISBN-resolved edition

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

## Test 7 rerun — Project Gutenberg format inspection

`test_7` is a fresh rerun of Task 43 (`browser_task_054-ebook-format-inspection`) using the exact same frozen rubric content, hash, nine-criterion order, and 20-point denominator. Only the outer task identifier reflects the new capture timestamp. No rubric-generation model calls or tokens were used for this rerun.

| Verifier | Score | Outcome | Calls | Tokens |
|---|---:|:---:|---:|---:|
| Microsoft screenshot | 9/20 (45%) | False | 12 | 89,855 |
| DOM-model | 14/20 (70%) | False | 28 | 141,586 |

DOM used 51,731 more evaluation tokens (+57.57%). Both scoring runs reported zero rubric-generation calls and zero API retries.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Correct Gutenberg page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Author | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Release Date | No / N/A | No / N/A | 0 / 0 | Missing in both; not a verifier miss |
| Last Update | No / N/A | No / N/A | 0 / 0 | Missing in both; not a verifier miss |
| Language | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| EPUB3 | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Plain Text (accessible) | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Download HTML (zip) | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints/stopping | Partial / Yes | Yes / Yes | 1 / 2 | Source-coverage consequence |

The DOM rubric advantage came from genuine source coverage. `dom_model1.txt` explicitly contained `Plain Text (accessible)` and `Download HTML (zip)`, while neither label appeared in either screenshot. The additional constraints point reflects that DOM could verify all three claimed formats while screenshots could verify only EPUB3.

Both representations omitted the Gutenberg `Release Date` and `Last Update` fields, and both verifiers correctly rejected the agent's specific date claims as unsupported. No criterion-level or outcome-level verifier grounding miss was confirmed. Screenshot-only asymmetric evidence loss was 2/9 criteria (22.2%), DOM-only asymmetric evidence loss was 0/9, and two criteria were missing from both modalities and therefore do not count as asymmetric evidence error.

## Test 7 second scoring rerun — same frozen rubric and evidence

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

## Test 8 rerun — Europeana The Milkmaid metadata

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

## Test 9 rerun — ClinicalTrials.gov filtering

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

## Rerun-selected evidence-loss aggregate

The aggregate now keeps one selected run per logical task. It replaces Task 33, 37, 38, 40, 41, 42, 43, and 46 with their reruns. Task 41 uses `test_8`; `test_5` is excluded. Task 43 uses the latest `test_7` scoring rerun. Scores themselves are not used to label capture loss; the human-audited source evidence is used.

| Original task | Selected rerun | Criteria | Screenshot-only loss | DOM-only loss |
|---|---|---:|---:|---:|
| Task 33 | `test_1` | 6 | 1 | 0 |
| Task 37 | `test_2` | 7 | 0 | 0 |
| Task 38 | `test_3` | 9 | 0 | 0 |
| Task 40 | `test_4` | 4 | 0 | 0 |
| Task 41 | `test_8` | 7 | 0 | 0 |
| Task 42 | `test_6` | 9 | 2 | 0 |
| Task 43 | `test_7` latest | 9 | 2 | 0 |
| Task 46 | `test_9` | 7 | 0 | 2 |
| Replaced-task subtotal | — | 58 | 5 | 2 |
| Unchanged selected tasks | — | 68 | 4 | 2 |
| **Updated aggregate** | — | **126** | **9 (7.1%)** | **4 (3.2%)** |

The denominator falls from 127 to 126 because the original Task 33 rubric had seven criteria, while the selected `test_1` rubric has six. For `test_9`, the sort criterion is not counted as screenshot loss because the DOM had only an indirect URL parameter rather than the visibly applied UI required by the rubric, and the same URL was available in shared action history. DOM-only loss counts the full titles for results #2 and #3, which are visible in `screenshot20.png` but absent from `dom_model20.txt`. Evidence missing from both representations—such as all three Last Update Posted dates—is excluded.

The confirmed `test_8` DOM exact-value analysis miss and `test_9` screenshot scroll-sequence miss are verifier errors, not capture loss, so neither is added to these evidence-loss numerators.

## Cross-task conclusion and next steps

This experiment compares two evidence representations while keeping the verifier pipeline as closely aligned as possible: Microsoft’s screenshot evidence and the ordered DOM-model states. The audit must distinguish evidence that was never captured from evidence that was captured but missed by the verifier, and it must distinguish both from incorrect scoring or overcredit.

The current results do not establish that DOM is more reliable overall. They show a narrower advantage: DOM can preserve exact textual values that are absent or unreadable in screenshots. Screenshots can also preserve visual structure, control state, and label–value relationships that the current DOM capture loses. Reliability therefore remains an open empirical question requiring criterion-level human labels.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Evaluated sample | Current comparison denominator | 19 selected logical tasks and 126 rubric criteria | Count the task sections and frozen-rubric criteria used in the selected runs | Keep one selected run per task and do not mix superseded reruns |
| Screenshot-only evidence loss | Evidence absent from screenshots but present in DOM | 9/126 criteria (7.1%) | Inspect every supplied screenshot and corresponding DOM state | Human-label each source as present, absent, or unclear before reading verifier scores |
| DOM-only evidence loss | Evidence absent from DOM but present in screenshots | 4/126 criteria (3.2%) | Inspect every supplied DOM state and corresponding screenshot | Audit zero-node states, truncation, labels, values, tables, and selected/checked state |
| Confirmed perception misses | Evidence available in a modality but not recovered by its verifier | Two confirmed examples: test_8 DOM item-type exactness and test_9 screenshot result-order continuity | Compare the source with the saved criterion-level analysis and citation | Keep verifier misses separate from capture-loss counts across all 126 criteria before claiming a recovery-rate advantage |
| Scoring/reasoning errors | Evidence was interpreted or scored incorrectly rather than missed | Confirmed overcredit examples include task38 DOM Vendor, task43 screenshot formats, task47 screenshot ingredients, and task48 DOM All Reviews | Compare the analysis, cited evidence, rubric requirement, and awarded points | Report false support separately from capture loss and perception misses |
| Exact-text advantage | DOM exposes precise strings directly | Strong examples include task41 dates/rights/identifier, task43 dates and format text, and task47 barcode/energy/sugars | Verify exact values in dom_modelN.txt and their absence from submitted screenshots | Report this as a text-grounding advantage, not proof of overall superiority |
| Visual/state advantage | Screenshots preserve layout or visible UI state that DOM can omit | Examples include task46 filter/sort state and task48 OS headings/storage | Inspect the pixel frame and DOM semantics at the same state index | Improve capture of checked, selected, expanded, table, and label–value relationships |
| Earlier token-reduction precedent | DOM evaluation used fewer tokens in selected benchmarks-2 runs | task2 saved 9.4%; task6 saved 6.9% | Use scoring-time provider totals with rubric generation excluded | Treat these as isolated precedents, not an established rate for a task category |
| Similar current tasks | Single-record/exact-value extraction candidates | Current evidence-error runs did not reproduce a reduction | Compare identical frozen-rubric runs, models, retries, and calls | Do not claim 5–9% savings for this subset until measured repeatedly |
| Agent observation boundary | Potential training/evaluation confound | include_offscreen: false governed one structured snapshot, but recorded agent inputs also contained a full agent_browser accessibility snapshot that could expose text outside the pixel viewport | Inspect the recording manifest, decision input sizes, and steps/*/agent_browser.txt | For a viewport-only training claim, remove or viewport-filter every model input source |

### Current token-cost check for proposed exact-value candidates

These totals are scoring-time evaluation tokens only. Frozen-rubric generation is separate.

| Task | Type | Screenshot tokens | DOM tokens | DOM change | Current result |
|---|---|---:|---:|---:|---|
| task29 | Software-package metadata | 115,086 | 148,894 | +29.4% | DOM used more |
| task36 | Standards metadata | 87,735 | Incomplete | N/A | No completed paired comparison |
| task37 | Domain-registry metadata | 232,672 | 243,687 | +4.7% | DOM used more |
| task41 | Cultural-object metadata | 78,674 | 98,127 | +24.7% | DOM used more |
| task42 | Book-edition metadata | 132,961 | 153,671 | +15.6% | DOM used more |
| task47 | Nutrition exact-value lookup | 86,889 | 95,966 | +10.4% | DOM used more |

Task type alone did not predict token savings. Token use also depends on the number of criteria and calls, selected-state size, evidence repeated across criterion calls, generated-analysis length, retries, and majority voting. Of these candidates, task37 came closest, but it was still a 4.7% increase rather than a reduction.

### Required reliability audit

For every task and criterion, record:

| Field | Allowed value or content |
|---|---|
| Screenshot evidence availability | present, absent, or unclear |
| DOM evidence availability | present, absent, or unclear |
| Screenshot verifier recovery | caught, missed, incorrect, or not_applicable |
| DOM verifier recovery | caught, missed, incorrect, or not_applicable |
| Evidence value | Exact value, state, or contradiction required by the criterion |
| Evidence source | Exact screenshot number or dom_modelN.txt state |
| Existing criterion result | Awarded points, maximum points, and saved verifier explanation |
| Final classification | One of the six audit classifications below |

Apply these classifications strictly:

- BOTH_CAUGHT: sufficient evidence was available in both representations and both verifiers recovered it correctly.
- SCREENSHOT_MISSED_DOM_CAUGHT: sufficient evidence was available in both; the screenshot verifier missed or misread it and the DOM verifier caught it.
- DOM_MISSED_SCREENSHOT_CAUGHT: sufficient evidence was available in both; the DOM verifier missed or misread it and the screenshot verifier caught it.
- BOTH_MISSED: sufficient evidence was available in both, but both verifiers failed to recover it correctly.
- SCREENSHOT_EVIDENCE_MISSING: screenshot evidence was insufficient while DOM contained sufficient evidence.
- DOM_EVIDENCE_MISSING: DOM evidence was insufficient while screenshots contained sufficient evidence.

A verifier miss must not be assigned merely because its score is lower. A miss requires direct confirmation that sufficient evidence was present in that verifier’s own input and that its saved analysis failed to identify or use it correctly. If evidence is absent from the input, that is a representation/capture omission, not a verifier miss.

### Metrics to report

1. **Representation coverage:** criteria with sufficient modality evidence / criteria with sufficient evidence in either modality.
2. **Conditional verifier recovery:** available modality evidence correctly caught / criteria with available evidence in that modality.
3. **DOM recovery of screenshot misses:** screenshot verifier misses correctly caught by DOM / screenshot verifier misses for which DOM evidence was available.
4. **Screenshot recovery of DOM misses:** DOM verifier misses correctly caught by screenshot / DOM verifier misses for which screenshot evidence was available.
5. **False-support rate:** credited criteria without sufficient or correct supporting evidence / criteria credited by that verifier.

Report both criterion-level and task-level percentages because criteria within a task are not statistically independent. Also stratify text/metadata, tables, forms and filters, dynamic state, and pixel-only visual criteria; aggregating these categories can hide where each modality actually performs well.

### What can be done next

1. Freeze one selected run and identical rubric per task; do not change verifier prompts, scoring, relevance, retries, or evidence handling during this audit.
2. Human-label evidence presence from the raw screenshots and DOM states before looking at the verifier result, then inspect the existing criterion-level analysis to label recovery.
3. Manually adjudicate every disagreement and store the exact screenshot or DOM-state citation supporting the decision.
4. Complete task36’s paired run or exclude it explicitly from token-cost comparisons.
5. Build a larger subset of single-page, text-heavy exact-value tasks and report the median token change, range, and proportion of tasks achieving a 5–9% reduction.
6. Investigate token usage by stage—calls, selected evidence bytes, repeated evidence, completion length, and retries—before attributing cost to the evidence representation itself.
7. Fix DOM capture completeness separately from this unchanged-verifier audit: zero-node retries, truncation, label–value association, table structure, and control-state semantics are the highest-value targets.
8. If evaluating DOM for agent training, run a controlled screenshot-only versus viewport-grounded-DOM-only study with no full offscreen accessibility snapshot available to either agent.

### Evidence status and limitations

**Directly verified:** the selected-run scores and token totals recorded above; the 9 screenshot-side and 4 DOM-side asymmetric source omissions in the rerun-selected aggregate; the inspected exact-text and UI-state examples; and the listed scoring-overcredit cases.

**Inference:** single-record exact-value tasks may be better candidates for compact DOM evidence, but their current runs do not show savings. This remains a hypothesis rather than a result.

**Unverified:** conditional recovery and false-support percentages across all 126 criteria, statistical confidence on the 19-task sample, and whether capture fixes would reduce DOM’s 3.2% asymmetric omission rate without increasing token cost.

**Denominator caveat:** 9/126 and 4/126 measure asymmetric evidence availability, not verifier error rates. Evidence absent from both modalities is excluded from those counts, and overlapping task-level categories must not be added as if they were exclusive.

The dominant finding is that DOM provides stronger grounding for some exact textual facts, while the current screenshot and DOM pipelines each omit different kinds of evidence and DOM usually costs more tokens. The next concrete check is a complete human-labelled criterion audit, followed by repeated paired runs on a predeclared exact-value subset; only then can the experiment support a reliable percentage claim for recovery or token savings.
