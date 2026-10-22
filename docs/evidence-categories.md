# Evidence categories

This guide explains the six source-evidence-loss categories used in
[Figure 3 of the benchmark report](../README.md#52-where-evidence-is-lost)
and the [missed-evidence table](missed_evidence_table.md). Categories identify
the primary missing item or relationship in a confirmed source gap.

## Scope and counting

A source gap requires concrete evidence that is absent from one recorded
representation and preserved in the other. An item absent from both
representations, or available in both, does not count as source loss.
Availability is assessed across the eligible ordered source states.

Each representation/criterion loss receives one primary category, even when
several required items are missing. A criterion can have a different loss
and category in each representation. For example, task_35 C5 has missing
architecture/size rows in screenshots (**Table entries**) and a disconnected
tag-to-size association in DOM (**Label–value links**).

The current report contains 154 affected criteria across 91 tasks. Its
151 screenshot losses and 5 DOM losses total 156 representation/criterion
losses because two criteria have losses in both representations. Rates
retain all 642 audited criteria across 100 tasks in the denominator.

## The six categories

### Exact text and values

Missing scalar text, dates, numbers, symbols, or exact displayed notation.
Use this category when the gap concerns a specific value within otherwise
preserved context. An isolated value can belong here even when clipping or
viewport position caused its absence.

**Example — task_19 C3, screenshot loss:** DOM preserves the release timestamp
“02 Sep 17:40,” while screenshots retain only a relative release date.
The missing item is the absolute date/time value.
[Saved finding](../evaluation/task_19/20261021T040737Z/evidence_audit.json#L1112).

### URLs

Missing exact URLs, endpoints, domains, or associations between a URL and
its page content. For criteria requiring exact website, record, or endpoint
identity, the audit requires URL evidence within the representation itself.
Branding and URLs in the shared action history do not substitute for that
evidence under this identity rule.

**Example — task_75 C0, screenshot loss:** both representations retain the
Black Lotus API response, but only DOM associates it with the required
Scryfall exact-card endpoint.
[Saved finding](../evaluation/task_75/20261021T040737Z/evidence_audit.json#L623).

### Control states

Missing checked, selected, enabled, disabled, or other explicit control
states. A control's name or label alone does not establish its state;
absence of state text does not establish that the control is unchecked.

**Example — task_56 C1, DOM loss:** screenshots show the PubMed “5 years”
radio button and “Review” checkbox empty. DOM retains their labels without
the states needed to establish that the filters were not applied.
[Saved finding](../evaluation/task_56/20261021T040737Z/evidence_audit.json#L1254).

### Table entries

Missing structured rows or row-level associations required to extract the
requested fields. Use this category when a specific row or its structured
field grouping is the missing evidence. Whole missing cards, sections, or
list boundaries generally belong to **Capture omissions**.

**Example — task_35 C4, screenshot loss:** screenshots preserve the
`3.12-slim-bookworm` tag and update time but omit its `linux/amd64` size
row. DOM preserves that row and its 43.33 MB value.
[Saved finding](../evaluation/task_35/20261021T040737Z/evidence_audit.json#L1463).

### Label–value links

Missing connections between a label or heading and its required value.
Seeing the value elsewhere on the page does not establish the required
association. This category covers disconnected field relationships,
including headings whose corresponding table is no longer associated.

**Example — task_02 C2, DOM loss:** screenshots connect “Published by” to
“Electronic Arts.” DOM exposes the label without its value; another
occurrence of “Electronic Arts” in product-summary text does not establish
the publisher relationship.
[Saved finding](../evaluation/task_02/20261021T040737Z/evidence_audit.json#L1199).

### Capture omissions

A whole record, list boundary, content region, or substantial field
description is absent from the retained representation. Use this category
when the missing scope prevents establishing coverage or completeness,
rather than recovering an isolated value or explicit table row.

**Example — task_24 C1, screenshot loss:** screenshots cover ranks 1–29 of
the first 30 Hacker News stories. DOM also preserves rank 30 and its
non-GitHub domain, which is needed to establish the complete GitHub count.
[Saved finding](../evaluation/task_24/20261021T040737Z/evidence_audit.json#L804).

## Choosing a primary category

1. Identify the confirmed missing item from the source-loss finding's
   `decisive_evidence` and citations. Classify that item rather than inferring
   a category from the criterion title. A date criterion can have a URL gap
   when both representations preserve the date but only one proves page identity.
2. Apply the scope distinctions above: an isolated value, an explicit
   control state, a structured row, a disconnected label/value relationship,
   an exact URL, or a broader capture omission.
3. When several gaps fit different categories, choose the primary gap and
   document the reason. The categories have no universal priority order.
   For task_24 C0, both URL identity and rank 30 are missing; the annotation
   chooses **Capture omissions** because the first-30 list boundary is the
   primary gap. Secondary gaps remain in the
   [saved finding](../evaluation/task_24/20261021T040737Z/evidence_audit.json#L579).
4. Assign each representation separately when both have a confirmed loss.
   Count the criterion once in each affected representation's category totals.

## Labels and annotation provenance

The table's **Category** names the evidence type. Its **Labels** column
identifies which representation loses evidence:
`SCREENSHOT_EVIDENCE_MISSING`, `DOM_EVIDENCE_MISSING`, or
`BOTH_EVIDENCE_INCOMPLETE`. These tags are derived from the confirmed
source-loss flags.

[evidence_categories.json](evidence_categories.json) stores the definitions
and individual assignments. Each assignment is keyed by task, zero-based
criterion index, and representation-loss flag, with a category, rationale,
and `finding_sha256`. The report generator checks that hash against the
saved criterion wording and full source-loss finding; missing or changed
annotations require review before export. Category assignments are explicit
annotations, rather than automatic keyword classifications.

These annotations interpret saved automated audit/adjudication statements.
The original screenshots and DOM states were not independently reviewed
for this classification export. The examples above summarize those saved
statements. Raw audit links require the local `evaluation/` runs, which are
excluded from Git; the missed-evidence table preserves the source-loss
statements and citation locations in readable form. Aggregate counts and
the selected run paths are in
[benchmark_statistics.json](benchmark_statistics.json).
