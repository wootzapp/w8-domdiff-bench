## Task 26

Completed using all N+1 states: 2 screenshots and 2 DOM-model states.

```text
 Metric                 Screenshot        DOM model
━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━
 Process score        15/15 (100%)    14/15 (93.3%)
───────────────────  ──────────────  ───────────────
 Outcome                      Pass             Fail
───────────────────  ──────────────  ───────────────
 LLM calls                      12               19
───────────────────  ──────────────  ───────────────
 Evaluation tokens          81,212          100,608
```

### Evidence audit

```text
 Criterion          Screenshot          DOM present/           Score    Classification
                    present/caught      caught                SS/DOM
━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━━━━
 Course page        Yes / Yes           Yes / Yes                3/3    BOTH_CAUGHT
 accessed
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Instructor         Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 IBM partner        Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Five modules       Yes / Yes           Yes / Yes                3/2    BOTH_CAUGHT
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Audit              Yes / Yes           Yes / Yes                3/3    BOTH_CAUGHT
 availability
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Constraints        Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
 respected
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Unavailability     Page clearly        Page clearly             N/A    BOTH_CAUGHT
                    available /         available /
                    caught              caught
```

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

```text
 Metric                Screenshot       DOM model
━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━  ━━━━━━━━━━━━━━
 Process score        16/20 (80%)    20/20 (100%)
───────────────────  ─────────────  ──────────────
 Outcome                     Fail            Pass
───────────────────  ─────────────  ──────────────
 LLM calls                     16              25
───────────────────  ─────────────  ──────────────
 Evaluation tokens        115,086         148,894
```

### Evidence audit

```text
 Criterion           Screenshot          DOM present/       Score    Classification
                     present/caught      caught            SS/DOM
━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━  ━━━━━━━━  ━━━━━━━━━━━━━━━━━━━
 Correct Requests    Yes / Yes           Yes / Yes            4/4    BOTH_CAUGHT
 release
──────────────────  ──────────────────  ────────────────  ────────  ───────────────────
 Version 2.34.2      Yes / Yes           Yes / Yes            2/2    BOTH_CAUGHT
──────────────────  ──────────────────  ────────────────  ────────  ───────────────────
 Upload date         Yes / Yes           Yes / Yes            2/2    BOTH_CAUGHT
──────────────────  ──────────────────  ────────────────  ────────  ───────────────────
 Requires Python     Not displayed /     Not                  2/2    BOTH_CAUGHT
 unavailable         correctly caught    displayed /
                                         correctly
                                         caught
──────────────────  ──────────────────  ────────────────  ────────  ───────────────────
 License             Not displayed /     Not                  2/2    BOTH_CAUGHT
 unavailable         correctly caught    displayed /
                                         correctly
                                         caught
──────────────────  ──────────────────  ────────────────  ────────  ───────────────────
 Two download        Exact count not     Yes / Yes            1/3    SCREENSHOT_EVIDEN
 files               visible / not                                   CE_MISSING
                     proven
──────────────────  ──────────────────  ────────────────  ────────  ───────────────────
 Constraints/        Yes / Yes           Yes / Yes            3/5    BOTH_CAUGHT
 stopping
```

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

```text
 Metric                Screenshot      DOM model
━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━  ━━━━━━━━━━━━━
 Process score        18/20 (90%)    19/20 (95%)
───────────────────  ─────────────  ─────────────
 Outcome                     Fail           Fail
───────────────────  ─────────────  ─────────────
 LLM calls                     12             25
───────────────────  ─────────────  ─────────────
 Evaluation tokens         81,524        138,767
```

### Evidence audit

```text
 Criterion          Screenshot          DOM present/           Score    Classification
                    present/caught      caught                SS/DOM
━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━━━━
 Access Rails       Yes / Yes           Yes / Yes                3/3    BOTH_CAUGHT
 page
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Latest-version     3 fields            3 fields                 3/4    BOTH_CAUGHT
 metadata           present; license    present; license
                    absent / caught     absent / caught
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Dependency #1      Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Dependency #2      Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Dependency #3      Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Dependency #4      Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Dependency #5      Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
─────────────────  ──────────────────  ──────────────────  ──────────  ────────────────
 Stopping           Yes / Yes           Yes / Yes                2/2    BOTH_CAUGHT
 condition
```

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

```text
 Metric                                       Screenshot         DOM model
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━
 Score                                     11/18 (61.1%)    8.5/18 (47.2%)
────────────────────────────────────────  ───────────────  ────────────────
 Outcome                                            Fail              Fail
────────────────────────────────────────  ───────────────  ────────────────
 LLM calls                                            13                18
────────────────────────────────────────  ───────────────  ────────────────
 Total tokens                                     88,862           116,464
────────────────────────────────────────  ───────────────  ────────────────
 Rubric-generation calls during scoring                0                 0
```

Rubric generation was separate: 2 calls, 13,467 tokens.

### Evidence audit

```text
 Criterion        Screenshot           DOM present/            Score    Classification
                  present/caught       caught               SS / DOM
━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━━━━
 Official page    Yes / Yes            Yes / Yes               3 / 3    BOTH_CAUGHT
 and filter
───────────────  ───────────────────  ───────────────────  ──────────  ────────────────
 Identify         Partial: slim,       Partial: trixie /       2 / 1    BOTH_CAUGHT
 newest tags      bookworm / Yes       Yes
───────────────  ───────────────────  ───────────────────  ──────────  ────────────────
 Update times     Two visible / Yes    One explicit /          0.5 /    BOTH_CAUGHT
                                       Yes                       1.5
───────────────  ───────────────────  ───────────────────  ──────────  ────────────────
 Linux/amd64      Two visible / Yes    One tag-linked /        2.5 /    BOTH_CAUGHT
 sizes                                 Yes                       1.5
───────────────  ───────────────────  ───────────────────  ──────────  ────────────────
 Constraints      Yes / Yes            Yes / Yes             3 / 1.5    BOTH_CAUGHT
```

The screenshot verifier exceeded DOM by 2.5 points. This was not caused by either
verifier missing available evidence. The representations exposed different tag records,
and criterion 5 also received different scoring interpretations despite both verifiers
recognizing the relevant evidence.

## Task 32

Completed using all 2 screenshots and 2 DOM-model states.

```text
 Metric                 Screenshot        DOM model
━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━
 Score               16/18 (88.9%)    16/18 (88.9%)
──────────────────  ───────────────  ───────────────
 Rubric threshold             Pass             Pass
──────────────────  ───────────────  ───────────────
 Outcome                      Fail             Fail
──────────────────  ───────────────  ───────────────
 LLM calls                      12               26
──────────────────  ───────────────  ───────────────
 Total tokens               74,211          121,092
```

Rubric generation was separate: 2 calls and 11,970 tokens.

### Evidence audit

```text
 Criterion            Screenshot         DOM present/          Score    Classification
                      present/caught     caught                 SS /
                                                                 DOM
━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━  ━━━━━━━━━━━━━━━━
 Correct Debian       Yes / Yes          Yes / Yes             2 / 2    BOTH_CAUGHT
 page
───────────────────  ─────────────────  ──────────────────  ─────────  ────────────────
 Package version      Yes / Yes          Yes / Yes             3 / 3    BOTH_CAUGHT
───────────────────  ─────────────────  ──────────────────  ─────────  ────────────────
 Complete             No / correctly     Partial: only         1 / 1    BOTH_CAUGHT
 architecture list    rejected           amd64 /
                                         correctly
                                         rejected extras
───────────────────  ─────────────────  ──────────────────  ─────────  ────────────────
 Required             Yes / Yes          Yes / Yes             7 / 7    BOTH_CAUGHT
 dependencies
───────────────────  ─────────────────  ──────────────────  ─────────  ────────────────
 No download/         Yes / Yes          Yes / Yes             3 / 3    BOTH_CAUGHT
 install
```

Both verifiers correctly identified that the claimed nine-architecture list was
unsupported. The screenshots did not show the “Download curl” table, while the DOM
contained only one explicit row: amd64. Neither verifier missed available evidence.

## Task 33

Completed using all 5 screenshots and 5 DOM-model states.

```text
 Metric                   Screenshot        DOM model
━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━
 Score                 10/18 (55.6%)    10/18 (55.6%)
────────────────────  ───────────────  ───────────────
 Outcome                        Fail             Fail
────────────────────  ───────────────  ───────────────
 LLM calls                        18               26
────────────────────  ───────────────  ───────────────
 Total tokens                112,647          138,127
────────────────────  ───────────────  ───────────────
 Validation retries                —                8
────────────────────  ───────────────  ───────────────
 Fallbacks                         —                0
```

Rubric generation was separate: 2 calls and 13,479 tokens.

### Evidence audit

```text
 Criterion             Screenshot          DOM present/caught        Score    Classification
                       present/caught                             SS / DOM
━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━
 Correct Homebrew      Yes / Yes           Yes / Yes                 2 / 2    BOTH_CAUGHT
 source
────────────────────  ──────────────────  ────────────────────  ───────────  ───────────────────────
 Stable version        9.0.1 visible /     Missing /                 0 / 0    DOM_EVIDENCE_MISSING
                       Yes                 correctly
                                           unsupported
────────────────────  ──────────────────  ────────────────────  ───────────  ───────────────────────
 License               GPL-3.0-or-         Same / Yes                0 / 0    BOTH_CAUGHT
                       later / Yes
────────────────────  ──────────────────  ────────────────────  ───────────  ───────────────────────
 Regular               All 11 / Yes        All 11 / Yes              6 / 6    BOTH_CAUGHT
 dependencies
────────────────────  ──────────────────  ────────────────────  ───────────  ───────────────────────
 Apple Silicon         Rows visible,       Explicit                  0 / 1    SCREENSHOT_EVIDENCE_M
 bottles               status glyph        checkmarks / Yes                   ISSING
                       unclear / Yes
────────────────────  ──────────────────  ────────────────────  ───────────  ───────────────────────
 Linux bottles         Rows visible,       Missing /                 0 / 0    BOTH_CAUGHT
                       exact status        correctly
                       unclear / Yes       unsupported
────────────────────  ──────────────────  ────────────────────  ───────────  ───────────────────────
 Scope/stopping        Yes / Yes           Yes / Yes                 2 / 1    BOTH_CAUGHT
```

Neither verifier demonstrably missed evidence available in its representation:

- Screenshot evidence-miss rate: 0/7 = 0%
- DOM evidence-miss rate: 0/7 = 0%
- Recovery metric: not applicable

The equal totals hide different attribution: DOM gained one point for explicit Apple Silicon
checkmarks but lost one point on stopping/scope.

## Task 35

Completed with a fresh, task-aligned frozen rubric.

```text
 Metric                      Screenshot      DOM model
━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━  ━━━━━━━━━━━━━
 Score                      17/20 (85%)    15/20 (75%)
─────────────────────────  ─────────────  ─────────────
 Outcome                         Failed         Failed
─────────────────────────  ─────────────  ─────────────
 Evaluation calls                    12             18
─────────────────────────  ─────────────  ─────────────
 Evaluation tokens               77,688         98,918
─────────────────────────  ─────────────  ─────────────
 Rubric-generation calls              0              0
```

Rubric generation was separate: 2 calls and 13,253 tokens.

```text
 Criterion              SS present /        DOM present /        SS / DOM    Audit
                        caught              caught
━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━
 C0 Open object         Yes / Yes           Yes / Yes               3 / 3    BOTH_CAUGHT
─────────────────────  ──────────────────  ───────────────────  ──────────  ────────────────────────
 C1 Correct museum      Yes / Yes           Yes / Yes               4 / 4    BOTH_CAUGHT
─────────────────────  ──────────────────  ───────────────────  ──────────  ────────────────────────
 C2 Relation ID/type    Yes / Yes           Yes / Yes               3 / 3    BOTH_CAUGHT
─────────────────────  ──────────────────  ───────────────────  ──────────  ────────────────────────
 C3 Address tags        Yes / Yes           Yes / Yes               4 / 4    BOTH_CAUGHT
─────────────────────  ──────────────────  ───────────────────  ──────────  ────────────────────────
 C4 Museum tags         Partially / Yes     Partially / Yes         1 / 0    Required tourism,
                                                                             museum, and website
                                                                             rows were missing from
                                                                             both sources
─────────────────────  ──────────────────  ───────────────────  ──────────  ────────────────────────
 C5 Constraints/stop    Yes / Yes           Yes / Yes               2 / 1    Both caught; scoring
                                                                             interpretation
                                                                             differed
```

The screenshot visibly showed building=museum, but not the requested tourism, museum, or website
tags. The DOM state contained the same limited tag table. Therefore, neither verifier missed
available evidence.

## Task 37

Completed.

```text
 Metric                Screenshot     DOM model
━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━  ━━━━━━━━━━━━
 Score                12/16 (75%)    8/16 (50%)
───────────────────  ─────────────  ────────────
 Outcome                   Failed        Failed
───────────────────  ─────────────  ────────────
 Evaluation calls              45            61
───────────────────  ─────────────  ────────────
 Evaluation tokens        232,672       243,687
```

DOM used 11,015 more tokens (+4.73%). Rubric generation was separate: 2 calls and 13,119 tokens.

```text
 Criterion            Screenshot present/    DOM present/caught    SS / DOM    Audit
                      caught
━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━
 C0 IANA page         Yes / Yes              Yes / Yes                2 / 2    BOTH_CAUGHT
───────────────────  ─────────────────────  ────────────────────  ──────────  ──────────────────────
 C1 TLD type          Yes / Yes              Yes / Yes                1.5 /    BOTH_CAUGHT
                                                                        1.5
───────────────────  ─────────────────────  ────────────────────  ──────────  ──────────────────────
 C2 Sponsor           Yes / Yes              Yes / Yes                3 / 3    BOTH_CAUGHT
───────────────────  ─────────────────────  ────────────────────  ──────────  ──────────────────────
 C3 Registration      Yes / Yes              No / N/A                 0 / 0    DOM_EVIDENCE_MISSING
 date
───────────────────  ─────────────────────  ────────────────────  ──────────  ──────────────────────
 C4 WHOIS server      Yes / Yes              No / N/A                 2 / 0    DOM_EVIDENCE_MISSING
───────────────────  ─────────────────────  ────────────────────  ──────────  ──────────────────────
 C5 Registration      Yes / Yes              No / N/A                 2 / 0    DOM_EVIDENCE_MISSING
 website
───────────────────  ─────────────────────  ────────────────────  ──────────  ──────────────────────
 C6 Constraints       Actions / Yes          Actions / Yes            1.5 /    BOTH_CAUGHT
                                                                        1.5
```

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

```text
 Metric                  Screenshot      DOM model
━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━
 Score                22.5/25 (90%)    23/25 (92%)
───────────────────  ───────────────  ─────────────
 Rubric pass                    Yes            Yes
───────────────────  ───────────────  ─────────────
 Outcome                     Failed         Passed
───────────────────  ───────────────  ─────────────
 Evaluation calls                21             43
───────────────────  ───────────────  ─────────────
 Evaluation tokens          141,830        244,050
```

DOM used 102,220 more tokens (+72.07%). Rubric generation was separate: 2 calls and 14,086 tokens.

```text
 Criterion               Screenshot present/caught    DOM present/caught     SS / DOM    Audit
━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━
 C0 CVE.org source       Yes / Yes                    Yes / Yes                 3 / 3    BOTH_CAUGHT
──────────────────────  ───────────────────────────  ────────────────────  ───────────  ──────────────────────
 C1 Status               Yes / Yes                    Yes / Yes                 2 / 2    BOTH_CAUGHT
──────────────────────  ───────────────────────────  ────────────────────  ───────────  ──────────────────────
 C2 Publication date     Yes / Yes                    Yes / Yes                 2 / 2    BOTH_CAUGHT
──────────────────────  ───────────────────────────  ────────────────────  ───────────  ──────────────────────
 C3 CNA name             Yes / Yes                    Yes / Yes                 2 / 2    BOTH_CAUGHT
──────────────────────  ───────────────────────────  ────────────────────  ───────────  ──────────────────────
 C4 Vendor               Yes / Yes                    No / N/A                0 / 0.5    DOM_EVIDENCE_MISSING
──────────────────────  ───────────────────────────  ────────────────────  ───────────  ──────────────────────
 C5 Product              Yes / Yes                    Narrative / Yes       1.5 / 1.5    BOTH_CAUGHT
──────────────────────  ───────────────────────────  ────────────────────  ───────────  ──────────────────────
 C6 Version statement    Yes / Yes                    Yes / Yes                 5 / 5    BOTH_CAUGHT
──────────────────────  ───────────────────────────  ────────────────────  ───────────  ──────────────────────
 C7 First reference      Yes / Yes                    Yes / Yes                 3 / 3    BOTH_CAUGHT
──────────────────────  ───────────────────────────  ────────────────────  ───────────  ──────────────────────
 C8 Constraints          Actions / Yes                Actions / Yes             4 / 4    BOTH_CAUGHT
```

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

```text
 Metric                 Screenshot       DOM model
━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━
 Score                14/14 (100%)    14/14 (100%)
───────────────────  ──────────────  ──────────────
 Rubric pass                   Yes             Yes
───────────────────  ──────────────  ──────────────
 Outcome                    Passed          Passed
───────────────────  ──────────────  ──────────────
 Evaluation calls               19              36
───────────────────  ──────────────  ──────────────
 Evaluation tokens         109,614         171,521
```

DOM used 61,907 more tokens (+56.48%). Rubric generation was separate: 2 calls and 12,898 tokens.

```text
 Criterion                  Screenshot present/caught    DOM present/caught    SS / DOM    Audit
━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━
 C0 NWS Seattle page        Yes / Yes                    Yes / Yes                2 / 2    BOTH_CAUGHT
─────────────────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────
 C1 First daytime period    Yes / Yes                    Yes / Yes                2 / 2    BOTH_CAUGHT
─────────────────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────
 C2 Following nighttime     Yes / Yes                    Yes / Yes                2 / 2    BOTH_CAUGHT
─────────────────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────
 C3 Daytime fields          Yes / Yes                    Yes / Yes                3 / 3    BOTH_CAUGHT
─────────────────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────
 C4 Nighttime fields        Yes / Yes                    Yes / Yes                3 / 3    BOTH_CAUGHT
─────────────────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────
 C5 Constraints/stop        Actions / Yes                Actions / Yes            2 / 2    BOTH_CAUGHT
```

Both sources clearly contained the same forecast:

- This Afternoon: showers, high 68°F, 90%, SSE wind around 11 mph with gusts to 21 mph
- Tonight: rain mainly after 3am, low 54°F, 50%, south wind 6–10 mph with gusts to 20 mph

## Task 40

Completed successfully.

```text
 Metric                                      Screenshot        DOM-model
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━
 Score                                     15/15 (100%)    14/15 (93.3%)
────────────────────────────────────────  ──────────────  ───────────────
 Outcome success                                    Yes               No
────────────────────────────────────────  ──────────────  ───────────────
 LLM calls                                           14               22
────────────────────────────────────────  ──────────────  ───────────────
 Total tokens                                    78,530          108,179
────────────────────────────────────────  ──────────────  ───────────────
 Rubric-generation calls during scoring               0                0
```

DOM used 29,649 more tokens (+37.75%). The separate frozen-rubric generation used 12,413 tokens.

```text
 Criterion                Screenshot present/        DOM present/caught    Score SS / DOM    Classification
                          caught
━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━
 Correct UNRATE page      Yes / Yes                  Yes / Yes                      3 / 3    BOTH_CAUGHT
───────────────────────  ─────────────────────────  ────────────────────  ────────────────  ──────────────────────
 Metadata                 Yes / Yes                  Partial / Yes                  4 / 3    DOM_EVIDENCE_MISSING
───────────────────────  ─────────────────────────  ────────────────────  ────────────────  ──────────────────────
 Latest 3 observations    Yes / Yes                  Yes / Yes                      6 / 6    BOTH_CAUGHT
───────────────────────  ─────────────────────────  ────────────────────  ────────────────  ──────────────────────
 Stop after requested     Yes / Yes                  Yes / Yes                      2 / 2    BOTH_CAUGHT
 work
```

The DOM representation contained Frequency: Monthly and Seasonally Adjusted, but did not preserve a reliable
relationship between the Units: label and Percent. Percent appeared only in chart-axis text. Therefore, the DOM
verifier correctly withheld one point—it did not miss available evidence; the DOM source lacked the necessary
metadata association.

## Task 41

Completed.

```text
 Metric             Screenshot         DOM-model
━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━
 Score              8/16 (50%)    13/16 (81.25%)
─────────────────  ────────────  ────────────────
 Rubric pass                No               Yes
─────────────────  ────────────  ────────────────
 Outcome success            No                No
─────────────────  ────────────  ────────────────
 LLM calls                  12                22
─────────────────  ────────────  ────────────────
 Total tokens           78,674            98,127
```

DOM used 19,453 more tokens (+24.73%). Rubric generation used another 13,147 tokens separately.

```text
 Criterion        Screenshot present/caught    DOM present/caught    SS / DOM    Audit
━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Exact record     Yes / Yes                    Yes / Yes                3 / 3    BOTH_CAUGHT
───────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────────────────────
 Title            Yes / Yes                    Yes / Yes                2 / 2    BOTH_CAUGHT
───────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────────────────────
 Creation date    No                           Yes / Yes                0 / 2    SCREENSHOT_EVIDENCE_MISSING
───────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────────────────────
 Institution      Yes / Yes                    Yes / Yes                2 / 2    BOTH_CAUGHT
───────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────────────────────
 Type of item     Yes / Yes                    No                       1 / 0    DOM_EVIDENCE_MISSING
───────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────────────────────
 Rights           No/obscured                  Yes / Yes                0 / 2    SCREENSHOT_EVIDENCE_MISSING
───────────────  ───────────────────────────  ────────────────────  ──────────  ─────────────────────────────
 Identifier       No                           Yes / Yes                0 / 2    SCREENSHOT_EVIDENCE_MISSING
```

There were no clear verifier evidence misses. The five-point DOM advantage came from evidence availability: the
DOM explicitly contained the creation date, rights, and identifiers that were not visible in the screenshots.
Conversely, the screenshot showed the full type value, while the DOM omitted it.

## Task 42

Completed after correcting both task42 dataset URLs to the resolved edition. No verifier code was changed.

```text
 Metric               Screenshot        DOM-model
━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━
 Score              15/15 (100%)    13/15 (86.7%)
─────────────────  ──────────────  ───────────────
 Rubric pass                 Yes              Yes
─────────────────  ──────────────  ───────────────
 Outcome success             Yes               No
─────────────────  ──────────────  ───────────────
 LLM calls                    22               29
─────────────────  ──────────────  ───────────────
 Total tokens            132,961          153,671
```

DOM used 20,710 more tokens (+15.58%). Rubric generation used 13,679 tokens separately.

```text
 Criterion                Screenshot present/        DOM present/caught    SS / DOM    Audit
                          caught
━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ISBN-resolved edition    Yes / Yes                  Yes / Yes                3 / 2    BOTH_CAUGHT; scoring
                                                                                       disagreement
───────────────────────  ─────────────────────────  ────────────────────  ──────────  ────────────────────────────
 Title                    Yes / Yes                  Yes / Yes                1 / 1    BOTH_CAUGHT
───────────────────────  ─────────────────────────  ────────────────────  ──────────  ────────────────────────────
 Author                   Yes / Yes                  Yes / Yes                1 / 1    BOTH_CAUGHT
───────────────────────  ─────────────────────────  ────────────────────  ──────────  ────────────────────────────
 Publish Date             Yes / Yes                  Yes / Yes                2 / 2    BOTH_CAUGHT
───────────────────────  ─────────────────────────  ────────────────────  ──────────  ────────────────────────────
 Publisher                Yes / Yes                  Yes / Yes                1 / 1    BOTH_CAUGHT
───────────────────────  ─────────────────────────  ────────────────────  ──────────  ────────────────────────────
 Language                 Yes / Yes                  Yes / Yes                1 / 1    BOTH_CAUGHT
───────────────────────  ─────────────────────────  ────────────────────  ──────────  ────────────────────────────
 Page count               Yes / Yes                  Yes / Yes                2 / 2    BOTH_CAUGHT
───────────────────────  ─────────────────────────  ────────────────────  ──────────  ────────────────────────────
 ISBN-13                  Yes / Yes                  Partial / Yes            2 / 1    DOM_EVIDENCE_MISSING
───────────────────────  ─────────────────────────  ────────────────────  ──────────  ────────────────────────────
 Constraints/stopping     Yes / Yes                  Yes / Yes                2 / 2    BOTH_CAUGHT
```

Why DOM lost two points:

- It found the correct edition and ISBN but deducted one point because the original ISBN redirect was not
  demonstrated. The screenshot verifier accepted the starting context plus displayed ISBN. This is a scoring-
  judgment difference, not missed evidence.

- The DOM contained 9780141439518 inside an editions-table row, but lost the explicit ISBN 13 → value field
  relationship that was clearly visible in screenshots. The DOM verifier caught the digits but awarded partial
  credit. This is a DOM representation limitation, not a verifier miss.

## Task 43

Completed.

```text
 Metric              Screenshot      DOM-model
━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━  ━━━━━━━━━━━━━
 Score              13/20 (65%)    12/20 (60%)
─────────────────  ─────────────  ─────────────
 Rubric pass                 No             No
─────────────────  ─────────────  ─────────────
 Outcome success             No             No
─────────────────  ─────────────  ─────────────
 LLM calls                   12             28
─────────────────  ─────────────  ─────────────
 Total tokens            94,179        137,496
```

DOM used 43,317 more tokens (+45.99%). Rubric generation used 14,294 tokens separately.

```text
•  Criterion       Screenshot          DOM                    SS / DOM    Audit
━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Correct page    Caught              Caught                    2 / 2    BOTH_CAUGHT
──────────────  ──────────────────  ─────────────────────  ──────────  ─────────────────────────────
 Author          Caught              Evidence incomplete       2 / 0    DOM_EVIDENCE_MISSING
──────────────  ──────────────────  ─────────────────────  ──────────  ─────────────────────────────
 Release Date    Evidence missing    Caught                    0 / 3    SCREENSHOT_EVIDENCE_MISSING
──────────────  ──────────────────  ─────────────────────  ──────────  ─────────────────────────────
 Last Update     Evidence missing    Caught                    0 / 3    SCREENSHOT_EVIDENCE_MISSING
──────────────  ──────────────────  ─────────────────────  ──────────  ─────────────────────────────
 Language        Caught              Evidence missing          2 / 0    DOM_EVIDENCE_MISSING
──────────────  ──────────────────  ─────────────────────  ──────────  ─────────────────────────────
 EPUB3           Caught              Caught                    2 / 2    BOTH_CAUGHT
──────────────  ──────────────────  ─────────────────────  ──────────  ─────────────────────────────
 Plain Text      Evidence missing    Caught                    2 / 0    SCREENSHOT_EVIDENCE_MISSING
──────────────  ──────────────────  ─────────────────────  ──────────  ─────────────────────────────
 HTML ZIP        Evidence missing    Evidence missing          2 / 0    BOTH SOURCES MISSING
──────────────  ──────────────────  ─────────────────────  ──────────  ─────────────────────────────
 Constraints     Caught              Caught                    1 / 2    Scoring disagreement
```

Key finding: the screenshot verifier scored slightly higher mainly because it was more lenient when evidence was
missing. It awarded full credit for “Plain Text (accessible)” and “Download HTML (zip)” even though the requested
availability was not established visually.

The DOM explicitly contained the offscreen Plain Text (accessible) link, so it correctly identified the agent’s
“not visible/not listed” claim as wrong. It also recovered both exact dates absent from the screenshots.
Conversely, the DOM omitted the formal author value and dedicated Language field that were visible in screenshot
1.

## Task 45

Completed.

```text
 Verifier                       Score    Outcome    Calls     Tokens
━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━  ━━━━━━━━━  ━━━━━━━  ━━━━━━━━━
 Microsoft screenshot    18/18 (100%)     False        14     91,213
──────────────────────  ──────────────  ─────────  ───────  ─────────
 DOM-model               18/18 (100%)     False        21    108,842
```

DOM used 17,629 more tokens (+19.33%).

```text
 Criterion              Screenshot evidence/caught    DOM evidence/caught      Audit
━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━
 Title-field search     403 visible / Yes             Title: 403 / Yes         BOTH_CAUGHT
─────────────────────  ────────────────────────────  ───────────────────────  ─────────────
 Filters and sorting    403 blocker / Yes             403 blocker / Yes        BOTH_CAUGHT
─────────────────────  ────────────────────────────  ───────────────────────  ─────────────
 Result #1              Blocked / Yes                 Blocked / Yes            BOTH_CAUGHT
─────────────────────  ────────────────────────────  ───────────────────────  ─────────────
 Result #2              Blocked / Yes                 Blocked / Yes            BOTH_CAUGHT
─────────────────────  ────────────────────────────  ───────────────────────  ─────────────
 Result #3              Blocked / Yes                 Blocked / Yes            BOTH_CAUGHT
─────────────────────  ────────────────────────────  ───────────────────────  ─────────────
 Stopping condition     Reasonable stop / Yes         Reasonable stop / Yes    BOTH_CAUGHT
```

All three screenshots were identical and visibly showed “403 Forbidden.” All three DOM states also explicitly
recorded Title: 403. Therefore:

## Task 46

Completed.

```text
 Verifier                       Score    Outcome    Calls     Tokens
━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━  ━━━━━━━━━  ━━━━━━━  ━━━━━━━━━
 Microsoft screenshot    5/22 (22.7%)     False        44    269,979
──────────────────────  ──────────────  ─────────  ───────  ─────────
 DOM-model               5.5/22 (25%)     False        53    399,226
```

DOM used 129,247 more tokens (+47.87%).

```text
 Criterion               Screenshot                        DOM model                         Audit
━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━
 Search term             Present and caught: 2/2           Present and caught: 2/2           BOTH_CAUGHT
──────────────────────  ────────────────────────────────  ────────────────────────────────  ──────────────────────
 Required filters        Phase 3 visibly unchecked;        Checkbox state not preserved;     DOM_EVIDENCE_MISSING
                         caught: 2/4                       inferred unconfirmed: 2/4
──────────────────────  ────────────────────────────────  ────────────────────────────────  ──────────────────────
 Newest-first sort       Screenshot10 shows Relevance      Dropdown state missing;           DOM_EVIDENCE_MISSING
                         selected; caught: 0/2             attempt received 0.5/2
──────────────────────  ────────────────────────────────  ────────────────────────────────  ──────────────────────
 Result #1               Partial card visible, but not     Partial card data present, but    BOTH_CAUGHT
                         reported: 0/4                     not reported: 0/4
──────────────────────  ────────────────────────────────  ────────────────────────────────  ──────────────────────
 Result #2               Not reported: 0/4                 Not reported: 0/4                 BOTH_CAUGHT
──────────────────────  ────────────────────────────────  ────────────────────────────────  ──────────────────────
 Result #3               Not reported: 0/4                 Not reported: 0/4                 BOTH_CAUGHT
──────────────────────  ────────────────────────────────  ────────────────────────────────  ──────────────────────
 Constraints/stopping    Incomplete stop: 1/2              Incomplete stop: 1/2              BOTH_CAUGHT
```

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

```text
 Verifier                          Score    Outcome    Calls    Tokens
━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━  ━━━━━━━━━  ━━━━━━━  ━━━━━━━━
 Microsoft screenshot        15/20 (75%)     False        12    86,889
──────────────────────  ─────────────────  ─────────  ───────  ────────
 DOM-model               15.5/20 (77.5%)     False        17    95,966
```

DOM used 9,077 more tokens (+10.45%).

```text
 Criterion        Screenshot                        DOM model                         Audit
━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Exact product    Page visible; barcode from        Explicit name/barcode: 3/3        BOTH_CAUGHT
                  shared URL: 3/3
───────────────  ────────────────────────────────  ────────────────────────────────  ─────────────────────────────
 Name/barcode     Name visible; barcode not         Both explicit: 2/2                SCREENSHOT_EVIDENCE_MISSING
                  visually shown: 2/2
───────────────  ────────────────────────────────  ────────────────────────────────  ─────────────────────────────
 Nutri-Score      Visible and caught: 2/2           Present and caught: 2/2           BOTH_CAUGHT
───────────────  ────────────────────────────────  ────────────────────────────────  ─────────────────────────────
 NOVA/markers     Visible and caught: 3/3           Present and caught: 3/3           BOTH_CAUGHT
───────────────  ────────────────────────────────  ────────────────────────────────  ─────────────────────────────
 Energy           Not visible: 0/3                  Explicit table value caught:      SCREENSHOT_EVIDENCE_MISSING
                                                    3/3
───────────────  ────────────────────────────────  ────────────────────────────────  ─────────────────────────────
 Sugars           Not visible: 0/2                  Explicit table value caught:      SCREENSHOT_EVIDENCE_MISSING
                                                    2/2
───────────────  ────────────────────────────────  ────────────────────────────────  ─────────────────────────────
 Ingredients      Absent; unavailable claim         Absent, but stopping early        Reasoning disagreement
                  credited: 4/4                     penalized: 0/4
───────────────  ────────────────────────────────  ────────────────────────────────  ─────────────────────────────
 Constraints      Full credit: 1/1                  Incomplete ingredients caused     Reasoning disagreement
                                                    deduction: 0.5/1
```

Key finding: DOM contained the energy and sugar values even though neither screenshot displayed them. Therefore,
the screenshot verifier did not miss visible evidence—the screenshot representation lacked that evidence.

Conversely, Microsoft overcredited the missing ingredients by treating “not currently displayed” as “unavailable,”
while the DOM verifier correctly recognized that the agent could have continued navigating.

## Task 48

Completed.

```text
 Verifier                        Score    Outcome    Calls     Tokens
━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━  ━━━━━━━━━  ━━━━━━━  ━━━━━━━━━
 Microsoft screenshot    13/22 (59.1%)     False        24    157,620
──────────────────────  ───────────────  ─────────  ───────  ─────────
 DOM-model               16/22 (72.7%)     False        37    243,674
```

DOM used 86,054 more tokens (+54.60%).

```text
 Criterion                      Screenshot                   DOM model                     Audit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━
 Correct Portal 2 page          Present/caught: 3/3          Present/caught: 3/3           BOTH_CAUGHT
─────────────────────────────  ───────────────────────────  ────────────────────────────  ────────────────────────
 Release/developer/publisher    Present/caught: 4/4          Present/caught: 4/4           BOTH_CAUGHT
─────────────────────────────  ───────────────────────────  ────────────────────────────  ────────────────────────
 All Reviews                    Absent; correctly            Absent, but incorrectly       Reasoning disagreement
                                penalized: 0/4               credited: 4/4
─────────────────────────────  ───────────────────────────  ────────────────────────────  ────────────────────────
 OS headings                    Both headings visible/       Headings absent from DOM:     DOM_EVIDENCE_MISSING
                                caught: 3/3                  1/3
─────────────────────────────  ───────────────────────────  ────────────────────────────  ────────────────────────
 Storage                        Windows 8 GB visible;        Storage absent from DOM:      DOM_EVIDENCE_MISSING
                                omission caught: 1/5         1/5
─────────────────────────────  ───────────────────────────  ────────────────────────────  ────────────────────────
 Constraints/stopping           Incomplete response: 2/3     Full credit despite           Reasoning disagreement
                                                             omissions: 3/3
```

The DOM verifier scored higher mainly because it overcredited the missing All Reviews summary by four points, not
because DOM recovered evidence missed by screenshots. It also gave one extra constraint point. Conversely, DOM
lost two points because its source omitted the OS headings that screenshot3 clearly displayed.

## Task 49

Completed.

```text
 Verifier                     Score    Outcome    Calls     Tokens
━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━  ━━━━━━━━━  ━━━━━━━  ━━━━━━━━━
 Microsoft screenshot    3/12 (25%)     False        16     99,226
──────────────────────  ────────────  ─────────  ───────  ─────────
 DOM-model               3/12 (25%)     False        16    111,927
```

DOM used 12,701 more tokens (+12.80%).

```text
 Criterion                     Screenshot                                DOM model                    Audit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━
 Correct artist/Album scope    Present and caught: 2/3                   Present and caught: 2/3      BOTH_CAUGHT
────────────────────────────  ────────────────────────────────────────  ───────────────────────────  ─────────────
 Homework                      Title/page present, full release date     Same evidence/result: 1/3    BOTH_CAUGHT
                               missing: 1/3
────────────────────────────  ────────────────────────────────────────  ───────────────────────────  ─────────────
 Discovery                     Listed initially, but never opened/       Same omission caught: 0/3    BOTH_CAUGHT
                               reported: 0/3
────────────────────────────  ────────────────────────────────────────  ───────────────────────────  ─────────────
 Human After All               Listed initially, but never opened/       Same omission caught: 0/3    BOTH_CAUGHT
                               reported: 0/3
```

Both sources clearly showed the correct standalone Album chronology: Homework, Discovery, and Human After All.
However, the agent opened only Homework and never obtained its required complete “First release date.” It did not
process entries two or three.

## Cross-task conclusion and next steps

This experiment compares two evidence representations while keeping the verifier pipeline as closely aligned as possible: Microsoft’s screenshot evidence and the ordered DOM-model states. The audit must distinguish evidence that was never captured from evidence that was captured but missed by the verifier, and it must distinguish both from incorrect scoring or overcredit.

The current results do not establish that DOM is more reliable overall. They show a narrower advantage: DOM can preserve exact textual values that are absent or unreadable in screenshots. Screenshots can also preserve visual structure, control state, and label–value relationships that the current DOM capture loses. Reliability therefore remains an open empirical question requiring criterion-level human labels.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Evaluated sample | Current comparison denominator | 19 reported tasks and 127 rubric criteria | Count the task sections and frozen-rubric criteria used in the selected runs | Keep one selected run per task and do not mix superseded reruns |
| Screenshot-only evidence loss | Evidence absent from screenshots but present in DOM | 11/127 criteria (8.7%) | Inspect every supplied screenshot and corresponding DOM state | Human-label each source as present, absent, or unclear before reading verifier scores |
| DOM-only evidence loss | Evidence absent from DOM but present in screenshots | 14/127 criteria (11.0%) | Inspect every supplied DOM state and corresponding screenshot | Audit zero-node states, truncation, labels, values, tables, and selected/checked state |
| Confirmed perception misses | Evidence available in a modality but not recovered by its verifier | No confirmed examples in the manually inspected disagreements so far | Compare the source with the saved criterion-level analysis and citation | Complete this check for all 127 criteria before claiming a recovery-rate advantage |
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

**Directly verified:** the selected-run scores and token totals recorded above; the 11 screenshot-side and 14 DOM-side asymmetric source omissions; the inspected exact-text and UI-state examples; and the listed scoring-overcredit cases.

**Inference:** single-record exact-value tasks may be better candidates for compact DOM evidence, but their current runs do not show savings. This remains a hypothesis rather than a result.

**Unverified:** conditional recovery and false-support percentages across all 127 criteria, statistical confidence on the 19-task sample, and whether capture fixes would reduce DOM’s 11.0% asymmetric omission rate without increasing token cost.

**Denominator caveat:** 11/127 and 14/127 measure asymmetric evidence availability, not verifier error rates. Evidence absent from both modalities is excluded from those counts, and overlapping task-level categories must not be added as if they were exclusive.

The dominant finding is that DOM provides stronger grounding for some exact textual facts, while the current screenshot and DOM pipelines each omit different kinds of evidence and DOM usually costs more tokens. The next concrete check is a complete human-labelled criterion audit, followed by repeated paired runs on a predeclared exact-value subset; only then can the experiment support a reliable percentage claim for recovery or token savings.
