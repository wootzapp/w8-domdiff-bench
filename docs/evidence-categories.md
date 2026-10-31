# Evidence categories

This guide explains the six source-evidence-loss categories used in
[technical report](technical-report.md). Categories identify
the primary missing item or relationship in a confirmed source gap.

## Scope and counting

A source gap requires concrete evidence that is absent from one recorded
representation and preserved in the other. An item absent from both
representations, or available in both, does not count as source loss.
Availability is assessed across the eligible ordered source states.

Each representation/criterion loss receives one primary category, even when several required items are missing. A criterion can lose different items in each representation. In task_37 C4, screenshots lose availability glyphs while DOM loses displayed label capitalization; each side contributes one Exact text and values loss.

The current report contains 50 affected criteria across 28 tasks. Its 41 screenshot losses and 10 DOM losses total 51 representation/criterion losses because one criterion has a loss on both sides. Rates retain all 589 audited criteria across 92 completed audits in the denominator.

## The six categories

### Exact text and values

Missing scalar text, dates, numbers, symbols, or exact displayed notation.
Use this category when the gap concerns a specific value within otherwise
preserved context. An isolated value can belong here even when clipping or
viewport position caused its absence.

**Example — task_08 C2, screenshot loss:** DOM preserves the absolute publication date Oct 14, 2026, while screenshots show only “released this 2 weeks ago.” [Saved finding](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/bench_fixes/evaluation/task_08/20261029T212045Z/evidence_audit.json).

### URLs

Missing exact URLs, endpoints, domains, or their association with page content. Observed URLs in the formatted action history count for both verifiers. Count URL loss only when decision-essential details are absent from that shared evidence and one representation but present in the other. Navigation intent is not proof of an observed destination.

**Example — task_75 C0, screenshot loss:** DOM preserves `?exact=Black%20Lotus`; the shared observed history preserves only the `/cards/named` path, and screenshots do not show the query. [Saved finding](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/bench_fixes/evaluation/task_75/20261029T212045Z/evidence_audit.json).

### Control states

Missing checked, selected, enabled, disabled, or other explicit control
states. A control's name or label alone does not establish its state;
absence of state text does not establish that the control is unchecked.

**Example — task_44 C2, DOM loss:** screenshots show the World radio option selected; DOM lists region names without checked states. [Saved finding](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/bench_fixes/evaluation/task_44/20261029T212045Z/evidence_audit.json).

### Table entries

Missing structured rows or row-level associations required to extract the
requested fields. Use this category when a specific row or its structured
field grouping is the missing evidence. Whole missing cards, sections, or
list boundaries generally belong to **Capture omissions**.

**Example — task_35 C2/C3/C4, screenshot loss:** the third tag’s Linux/amd64 size row is cropped in screenshots but retained in DOM. It affects the complete tag report, architecture check and stopping condition. [Saved finding](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/bench_fixes/evaluation/task_35/20261029T212045Z/evidence_audit.json).

### Label–value links

Missing connections between a label or heading and its required value.
Seeing the value elsewhere on the page does not establish the required
association. This category covers disconnected field relationships,
including headings whose corresponding table is no longer associated.

**Example — task_02 C2, DOM loss:** screenshots connect Published by with Microsoft Studios; DOM has the label without its value. Another occurrence in the page header does not preserve that association. [Saved finding](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/bench_fixes/evaluation/task_02/20261029T212045Z/evidence_audit.json).

### Capture omissions

A whole record, list boundary, content region, or substantial field
description is absent from the retained representation. Use this category
when the missing scope prevents establishing coverage or completeness,
rather than recovering an isolated value or explicit table row.

**Example — task_19 C2, screenshot loss:** screenshots stop at the Highlights heading, while DOM retains the complete ordered highlight list. [Saved finding](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/bench_fixes/evaluation/task_19/20261029T212045Z/evidence_audit.json).

## Choosing a primary category

1. Identify the confirmed missing item from the source-loss finding's
   `decisive_evidence` and citations. Classify that item rather than inferring
   a category from the criterion title. A date criterion can have a URL gap
   when both representations preserve the date but only one proves page identity.
2. Apply the scope distinctions above: an isolated value, an explicit
   control state, a structured row, a disconnected label/value relationship,
   an exact URL, or a broader capture omission.
3. When several gaps fit different categories, choose the primary gap and document the reason. There is no universal priority order. Task_35 C2 is assigned to **Table entries** because its missing architecture row is primary; missing absolute timestamps are an additional gap. Primary-category exclusion does not remove secondary gaps. The [annotations](../results/evidence_categories.tsv) preserve each choice and rationale.

4. Assign each representation separately when both have a confirmed loss.
   Count the criterion once in each affected representation's category totals.

## Labels and annotation provenance

The table's **Category** names the evidence type. Its **Labels** column
identifies which representation loses evidence:
`SCREENSHOT_EVIDENCE_MISSING`, `DOM_EVIDENCE_MISSING`, or
`BOTH_EVIDENCE_INCOMPLETE`. These tags are derived from the confirmed
source-loss flags.

The category assignments are explicit report annotations of the saved decisive evidence and citations, prepared by Codex. They do not alter the original automated audit/adjudication, and they are not evidence of completed internal human verification.

Assignments are keyed by task, zero-based criterion index and representation in [evidence_categories.tsv](../results/evidence_categories.tsv). Each includes a category, rationale, source path and `finding_sha256`. The hash covers the exact criterion wording and original per-representation loss object, using sorted compact UTF-8 JSON. The [technical report](technical-report.md) contains aggregate counts, sensitivity views and the six-column criterion table.

Selected aggregate statistics are available locally in
[results/summary.json](../results/summary.json).
