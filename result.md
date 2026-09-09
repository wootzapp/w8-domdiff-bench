
## Percentage results

| Representation | Evidence-loss criteria | Percentage | Definition |
|---|---:|---:|---|
| Screenshot | 9/126 | **7.1%** | Screenshot evidence was insufficient while DOM-model evidence was sufficient |
| DOM model | 4/126 | **3.2%** | DOM-model evidence was insufficient while screenshot evidence was sufficient |

These are evidence-availability percentages, not verifier-miss rates. Evidence absent from both representations is excluded.

## Task 29 — Requests release metadata

Selected result: Microsoft screenshot **16/20**; DOM model **20/20**.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Correct Requests release | Yes / Yes | Yes / Yes | 4 / 4 | BOTH_CAUGHT |
| Version 2.34.2 | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Upload date | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Requires Python unavailable | Not displayed / correctly caught | Not displayed / correctly caught | 2 / 2 | BOTH_CAUGHT |
| License unavailable | Not displayed / correctly caught | Not displayed / correctly caught | 2 / 2 | BOTH_CAUGHT |
| Two download files | Exact total not proven / N/A | Yes / Yes | 1 / 3 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints/stopping | Yes / Yes | Yes / Yes | 3 / 5 | BOTH_CAUGHT; scoring difference |

The screenshots show one source file and a separate wheel-detail page, but do not prove that only one wheel was listed. The DOM shows one source distribution and `Showing 1 of 1 file` for the built distribution, proving two total files.

## Task 33 — Homebrew ffmpeg

Selected result: Microsoft screenshot **12/20**; DOM model **20/20**. This is the renamed `test_1` rerun, not the superseded original Task 33 run.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Correct ffmpeg page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Stable version | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| License | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Regular dependencies | No / N/A | Yes / Yes | 0 / 6 | SCREENSHOT_EVIDENCE_MISSING |
| Bottle availability | Yes / Yes | Yes / Yes | 4 / 4 | BOTH_CAUGHT |
| Constraints/stopping | Partial / Yes | Yes / Yes | 2 / 4 | Source-coverage scoring difference |

Neither screenshot displays the regular `Depends on` section. `dom_model1.txt` contains all 11 regular dependencies and separates them from the build-only and `Uses from macOS` sections.

## Task 42 — Open Library ISBN-resolved edition

Selected result: Microsoft screenshot **12/15**; DOM model **15/15**. This is the renamed `test_6` rerun.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| ISBN-resolved edition proof | Insufficient / Partial | Yes / Yes | 2 / 3 | SCREENSHOT_EVIDENCE_MISSING |
| Title | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Author | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Publish Date | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Publisher | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Language | Yes / Yes | Yes / Yes | 1 / 1 | BOTH_CAUGHT |
| Page count | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| ISBN-13 | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints/stopping | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |

Neither screenshot displays ISBN-13 or visibly ties edition `OL37076991M` to the supplied ISBN. `dom_model1.txt` explicitly contains the edition identifier and `ISBN 13 9780141439518`. The shared resolved-edition URL provides partial support to the screenshot run, which is reflected in its 2/3 score for edition proof.

## Task 43 — Project Gutenberg format inspection

Selected result: Microsoft screenshot **10.5/20**; DOM model **14/20**. This is the renamed Task 43 data evaluated by the latest `test_7` scoring rerun.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Correct Gutenberg page | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Author | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Release Date | No / N/A | No / N/A | 0.5 / 0 | Missing in both; screenshot overcredit |
| Last Update | No / N/A | No / N/A | 0 / 0 | Missing in both; not a verifier miss |
| Language | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| EPUB3 | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| Plain Text (accessible) | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Download HTML (zip) | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Constraints/stopping | Partial / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT for observable constraints |

Neither screenshot displays `Plain Text (accessible)` or `Download HTML (zip)`, while `dom_model1.txt` contains both exact labels. Release Date and Last Update are missing from both representations and therefore do not count as asymmetric evidence loss.

## Task 47 — Open Food Facts nutrition lookup

Selected result: Microsoft screenshot **15/20**; DOM model **15.5/20**.

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Audit |
|---|---|---|---:|---|
| Exact product | Page visible; barcode in shared URL / Yes | Explicit name and barcode / Yes | 3 / 3 | BOTH_CAUGHT |
| Product name and barcode | Name visible; barcode absent from pixels / URL-supported | Both explicit / Yes | 2 / 2 | SCREENSHOT_EVIDENCE_MISSING; URL-qualified |
| Nutri-Score | Yes / Yes | Yes / Yes | 2 / 2 | BOTH_CAUGHT |
| NOVA classification and markers | Yes / Yes | Yes / Yes | 3 / 3 | BOTH_CAUGHT |
| Energy per 100 g | No / N/A | Yes / Yes | 0 / 3 | SCREENSHOT_EVIDENCE_MISSING |
| Sugars per 100 g | No / N/A | Yes / Yes | 0 / 2 | SCREENSHOT_EVIDENCE_MISSING |
| Complete English ingredients | No / incorrectly credited | No / correctly rejected | 4 / 0 | Missing in both; screenshot overcredit |
| Constraints/stopping | Partial / Yes | Partial / Yes | 1 / 0.5 | Scoring/reasoning difference |

The DOM contains the exact barcode, energy value `2252 kJ (539 kcal)`, and sugars value `56.3 g`. Neither screenshot shows the barcode or nutrition table. However, the barcode is available in the shared action URL, so it is a screenshot-pixel omission rather than evidence unavailable to the screenshot verifier's complete input.

## Interpretation

**Directly verified:** the nine screenshot-side and four DOM-side asymmetric omissions use one selected run per logical task. The current renamed task folders match the selected run inputs, including every screenshot, DOM state, action log, task file, and final answer for the five tasks above.

**Denominator caveat:** the primary **7.1%** screenshot result follows the representation-only definition used in `overall_comp.md`. If shared URL evidence is counted as part of screenshot evidence availability, exclude Task 47's barcode row and report the stricter full-input screenshot loss as **8/126 (6.3%)**.

**Conclusion:** under the experiment's representation-level definition, screenshot evidence loss is **7.1%**, while DOM-model evidence loss is **3.2%**. The listed differences are source-coverage gaps, not confirmed cases where a verifier ignored clearly available evidence.
