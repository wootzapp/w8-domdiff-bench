# DOM Evidence Issue Handoff

This document identifies the DOM-model source files involved in the confirmed DOM-side evidence gaps from the evidence-error audit. It is intended as a capture-pipeline handoff: each entry explains what the task required, what the DOM file preserved, what it failed to preserve, and what should be changed in capture.

The current audited denominator is 127 rubric criteria across 19 selected completed runs. Fourteen criteria (11.0%) had sufficient screenshot evidence but insufficient DOM evidence. These are representation or capture gaps, not confirmed cases of the DOM verifier overlooking evidence that was already available in its input.

## Summary

| Task | Files to send | Affected criteria | Failure pattern | Direct evidence | Suggested capture improvement |
|---|---|---:|---|---|---|
| Task 33 | `dom_model0.txt` through `dom_model4.txt` | 1 | Required stable version absent; three empty states | States 2–4 report `returnedNodes=0`; populated states contain package text but not stable version `9.0.1` | Retry zero-node captures and preserve the stable-version label/value near the formula heading |
| Task 37 | `dom_model0.txt` through `dom_model22.txt` | 3 | Registry fields never captured; 15 empty states | The populated states expose the Registry Information heading but omit date, WHOIS server, and registration URL | Retry zero-node states and preserve definition-list/table label–value pairs |
| Task 38 | `dom_model0.txt` through `dom_model6.txt` | 1 | Structured Vendor field omitted | DOM preserves `CNA: Apache Software Foundation`, but no `Vendor → Apache Software Foundation` field | Preserve the CVE affected-product table and its field labels instead of relying on narrative text |
| Task 40 | `dom_model0.txt` through `dom_model2.txt` | 1 | Label and value separated | `Units:` is empty while `Percent` appears later as chart-axis text | Preserve adjacent metadata as `Units: Percent` |
| Task 41 | `dom_model0.txt` and `dom_model1.txt` | 1 | Type-of-item field omitted | DOM preserves Format and material text but not the displayed Type-of-item value | Capture the metadata field name together with its value |
| Task 42 | `dom_model7.txt` | 1 | Truncation and flattened ISBN values | State says `truncated=True`; ISBN-10 and ISBN-13 digits appear without separate labels | Raise the node limit for truncated states and retain table headers/field labels |
| Task 43 | `dom_model0.txt` and `dom_model1.txt` | 2 | Formal Author and Language fields omitted | Informal `Jane Austen` and `English literature` text survives, but not the dedicated metadata values | Preserve all metadata-table rows and distinguish Language from classification text |
| Task 46 | `dom_model5.txt`, `dom_model10.txt`, `dom_model11.txt`, `dom_model12.txt`, `dom_model16.txt`, `dom_model17.txt`, and `dom_model20.txt` | 2 | Checked/selected control state lost | Filter names and counts appear, but Phase 3 checked state and active sort value do not | Serialize `checked`, `selected`, `active`, and current dropdown/radio values |
| Task 48 | `dom_model3.txt` | 2 | Entire relevant state empty | State reports `returnedNodes=0` while the aligned screenshot shows OS headings and storage requirements | Retry the state capture and fail the recording if the relevant post-action state remains empty |

## Detailed issues

### Task 33 — Homebrew ffmpeg metadata

**Files to send:**

- [`task33/dom_model0.txt`](data/data-new-dom-model/task33/dom_model0.txt)
- [`task33/dom_model1.txt`](data/data-new-dom-model/task33/dom_model1.txt)
- [`task33/dom_model2.txt`](data/data-new-dom-model/task33/dom_model2.txt)
- [`task33/dom_model3.txt`](data/data-new-dom-model/task33/dom_model3.txt)
- [`task33/dom_model4.txt`](data/data-new-dom-model/task33/dom_model4.txt)

**Issue:** The task required the stable ffmpeg version. The screenshots displayed `9.0.1`, but none of the DOM states preserved that value. `dom_model0.txt` and `dom_model1.txt` are populated and contain the formula name, alias, license, bottles, and dependencies, but not the stable-version label/value. `dom_model2.txt`, `dom_model3.txt`, and `dom_model4.txt` are complete capture failures with `returnedNodes=0`.

**Why this matters:** The DOM verifier cannot validate `9.0.1` from an alias such as `ffmpeg@9`; those are not equivalent claims.

**Capture fix:** Retry empty states, and preserve the stable-version metadata row next to the formula title.

### Task 37 — IANA .museum registry metadata

**Files to send:** all 23 files, [`task37/dom_model0.txt`](data/data-new-dom-model/task37/dom_model0.txt) through [`task37/dom_model22.txt`](data/data-new-dom-model/task37/dom_model22.txt).

**Zero-node files:**

- `dom_model2.txt`, `dom_model3.txt`, `dom_model4.txt`
- `dom_model6.txt`, `dom_model7.txt`
- `dom_model9.txt`, `dom_model10.txt`, `dom_model11.txt`
- `dom_model13.txt`, `dom_model14.txt`
- `dom_model16.txt`, `dom_model17.txt`
- `dom_model19.txt`, `dom_model20.txt`, `dom_model22.txt`

**Populated but incomplete files:**

- `dom_model0.txt`, `dom_model1.txt`, `dom_model5.txt`, `dom_model8.txt`
- `dom_model12.txt`, `dom_model15.txt`, `dom_model18.txt`, `dom_model21.txt`

**Issue:** The populated states preserve the `.museum` page, TLD type, sponsor information, name servers, and the `Registry Information` heading. They never preserve the three values visible in the screenshots: registration date `2001-10-20`, WHOIS server `whois.nic.museum`, and registration-services URL `https://about.museum`.

**Why this matters:** Repeated scrolling produced alternating populated and empty snapshots, but no state captured the definition-list values beneath the registry heading.

**Capture fix:** Retry zero-node states immediately and preserve definition-list or two-column metadata relationships as explicit label/value records.

### Task 38 — CVE-2021-44228 Vendor field

**Files to send:** [`task38/dom_model0.txt`](data/data-new-dom-model/task38/dom_model0.txt) through [`task38/dom_model6.txt`](data/data-new-dom-model/task38/dom_model6.txt).

**Issue:** The screenshots showed a structured affected-product table containing `Vendor: Apache Software Foundation` and `Product: Apache Log4j2`. The DOM states preserve the CNA label, description, references, and some narrative product text, but omit the structured Vendor field.

**Why this matters:** `CNA: Apache Software Foundation` does not prove that the Vendor field has the same value. Treating the CNA as the vendor caused unsupported DOM-side credit.

**Capture fix:** Preserve the affected-product table with explicit `Vendor` and `Product` headers and their associated cell values.

### Task 40 — FRED Units relationship

**Files to send:**

- [`task40/dom_model0.txt`](data/data-new-dom-model/task40/dom_model0.txt)
- [`task40/dom_model1.txt`](data/data-new-dom-model/task40/dom_model1.txt)
- [`task40/dom_model2.txt`](data/data-new-dom-model/task40/dom_model2.txt)

**Issue:** Each file contains an empty `Units:` label. The word `Percent` survives elsewhere as Highcharts axis text, but the DOM does not encode the relationship `Units → Percent`.

**Why this matters:** Having both words somewhere in a flattened state does not prove that Percent is the value belonging to the Units field.

**Capture fix:** Keep adjacent metadata together and serialize it as a label/value pair, such as `Units: Percent`.

### Task 41 — Europeana Type of item

**Files to send:**

- [`task41/dom_model0.txt`](data/data-new-dom-model/task41/dom_model0.txt)
- [`task41/dom_model1.txt`](data/data-new-dom-model/task41/dom_model1.txt)

**Issue:** The screenshots showed the Type-of-item value `painting ; Art of painting`. The DOM preserves other metadata—including dates, rights, identifiers, Format, and materials—but does not preserve the dedicated Type-of-item field/value.

**Why this matters:** Values such as `canvas` and `oil paint` belong to Format/material fields and cannot substitute for the missing Type-of-item value.

**Capture fix:** Capture every expanded metadata row with the row label attached to its complete value.

### Task 42 — Open Library ISBN-13

**File to send:** [`task42/dom_model7.txt`](data/data-new-dom-model/task42/dom_model7.txt).

**Issue:** This is the only explicitly truncated state among the inspected DOM-loss cases. It reports `truncated=True`. The flattened edition row contains `0141439513 9780141439518`, but does not identify the first as ISBN-10 and the second as ISBN-13.

**Why this matters:** The correct digits are present, but the required semantic relationship `ISBN-13 → 9780141439518` is not.

**Capture fix:** Increase the node budget or perform a targeted continuation only when `truncated=True`, and preserve table headers or field labels with each value.

### Task 43 — Project Gutenberg Author and Language

**Files to send:**

- [`task43/dom_model0.txt`](data/data-new-dom-model/task43/dom_model0.txt)
- [`task43/dom_model1.txt`](data/data-new-dom-model/task43/dom_model1.txt)

**Issue:** The screenshots preserved the formal metadata values `Austen, Jane, 1775-1817` and `Language: English`. The DOM contains informal title/link text such as `Jane Austen` and a Library of Congress classification containing `English literature`, but it omits the dedicated Author and Language metadata rows.

**Why this matters:** An informal display name is incomplete relative to the requested formal author field, and `English literature` is a classification rather than proof that the Language field equals English.

**Capture fix:** Preserve all metadata-table rows and their exact field names instead of deduplicating semantically similar text.

### Task 46 — ClinicalTrials.gov filter and sort state

**Files to send:**

- [`task46/dom_model5.txt`](data/data-new-dom-model/task46/dom_model5.txt): state after the first Phase 3 click attempt
- [`task46/dom_model10.txt`](data/data-new-dom-model/task46/dom_model10.txt): state after opening the Display control
- [`task46/dom_model11.txt`](data/data-new-dom-model/task46/dom_model11.txt): state after clicking Newest First
- [`task46/dom_model12.txt`](data/data-new-dom-model/task46/dom_model12.txt): state after another Phase 3 click
- [`task46/dom_model16.txt`](data/data-new-dom-model/task46/dom_model16.txt): state after clicking the Phase 3 checkbox directly
- [`task46/dom_model17.txt`](data/data-new-dom-model/task46/dom_model17.txt): later state showing `Phase 3 (30)` and `Clear Filters (3)` without checked state
- [`task46/dom_model20.txt`](data/data-new-dom-model/task46/dom_model20.txt): state after the final Phase 3 click attempt

**Issue:** The DOM records option names and filter counts but not the decisive control states. It does not prove whether Phase 3 is checked, and it does not preserve which sort radio/dropdown value is active. The URL contains Recruiting and United States parameters but no Phase 3 parameter, while the visible sort state is also absent.

**Why this matters:** `Phase 3 (30)` proves that the option exists, not that it is applied. `Clear Filters (3)` proves that three filters exist, not which three. Likewise, clicking Newest First does not prove it became selected.

**Capture fix:** Serialize control semantics explicitly—for example, `Phase 3: checked=false` and `Sort: Relevance (selected)`—and capture the post-action state only after the UI settles.

### Task 48 — Steam system requirements

**File to send:** [`task48/dom_model3.txt`](data/data-new-dom-model/task48/dom_model3.txt).

**Issue:** The state reports `returnedNodes=0 groups=0 truncated=False`. Its aligned screenshot visibly contains the System Requirements section, including Windows and SteamOS + Linux headings and the Windows minimum Storage value of 8 GB.

**Why this matters:** This was a complete capture failure for the exact state containing the required evidence, causing two DOM-side criterion losses: operating-system headings and per-OS storage.

**Capture fix:** Retry zero-node capture after a short readiness check. If retries still return zero nodes while the page is visibly rendered, mark the trajectory invalid or store a capture-error sidecar rather than treating the empty state as valid evidence.

## Directly verified facts

- The nine tasks above account for the 14 audited criteria where screenshot evidence was sufficient and DOM evidence was insufficient.
- Task 33 has three zero-node files; Task 37 has 15; Task 48 has one.
- Task 42 `dom_model7.txt` is the only explicitly truncated state among the inspected DOM-loss cases.
- The task 40, task 42, and task 46 files preserve relevant words while losing the label/value or selected-state relationship required to prove the criterion.

## Inferences and boundaries

- Increasing the node limit can directly help the truncated task 42 state, but it will not by itself repair zero-node captures or missing semantic relationships.
- Better node counts may expose additional content, but improvement must be measured by rerunning capture and repeating the same criterion-level audit.
- Task 38 also contains a verifier reasoning error: the DOM verifier inferred Vendor from CNA evidence. That overcredit is separate from the underlying DOM omission.
- Evidence absent from both screenshot and DOM is not listed as a DOM-side comparative loss.

The dominant failures are zero-node states and loss of structured relationships, not broad truncation. The first capture changes to validate are zero-node retries, explicit label/value preservation, table-header association, and checked/selected/active control-state serialization.
