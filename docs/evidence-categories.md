# Evidence categories

Evidence categories describe the missing information in an accepted source-loss
finding. They are reviewed report annotations of the audit's decisive evidence
and citations. They do not change loss flags, completion grades, verifier scores,
eligibility or denominators. See the [evaluation protocol](evaluation-protocol.md#measurements).

## Scope and counting

Compare only the screenshots and DOM from the same recording. A fact absent from
both formats is not source loss. A verifier overlooking available evidence is a
verifier miss, not source loss.

Assign one primary category per affected criterion and representation. Several
criteria can depend on the same missing fact; these remain separate criterion
observations, not independent missing facts. A criterion can lose different
evidence in both formats and receive a different category on each side.

## Categories

These categories describe common evidence gaps. The vocabulary is open: use a
different descriptive category when the missing evidence does not fit, with a
rationale explaining the distinction. Do not force a finding into a category
because of its task name or website.

| Category | Missing evidence |
| --- | --- |
| Exact text and values | A specific name, number, date, symbol or exact displayed wording within otherwise preserved context. |
| URLs | An exact URL, query parameter or its association with page content. |
| Control states | Whether a control is checked, selected, enabled, disabled or in another explicit state. A label alone does not establish state. |
| Table entries | A structured row, its fields or the row-level association needed to extract them. |
| Label–value links | The connection between a label or heading and its value, when disconnected text does not establish the association. |
| Capture omissions | A whole record, section, list boundary or substantial field description needed to establish coverage or completeness. |
| Rules and conditions | An operative requirement, exception, permission or restriction needed to decide what is allowed or required. |
| Explanations and limitations | A definition, causal explanation, methodological qualification or stated limitation needed to interpret the reported facts. |

Truncation, collapsed content, viewport clipping and text embedded in images are
capture mechanisms, not evidence categories. Classify the missing item: a clipped
date can be **Exact text and values**, a clipped table row **Table entries**, and
a missing explanatory section **Capture omissions**.

## Annotating findings

Read each confirmed finding's `decisive_evidence`, citations and explanation.
Check the cited artifacts when the explanation is ambiguous or contradicts its
flag. Record that concern in the rationale; assigning a category does not resolve
a disputed audit decision or constitute human verification of the loss.

Each profile's `evidence_categories.tsv` sits alongside its `evidence_audit.json`
under `evaluations/<run>/<arm>/<task>/<profile>/`. Use one row per annotated
criterion/representation, with these columns:

| Field | Meaning |
| --- | --- |
| `run_name`, `actor_arm`, `judge_profile`, `recording_sha256`, `task` | Recording and evaluation identity. |
| `criterion_index` | Zero-based index in the frozen rubric. |
| `representation` | `screenshot` or `dom_model`. |
| `category`, `rationale` | A descriptive evidence type and why the missing item fits it. |
| `finding_sha256` | SHA-256 of sorted compact UTF-8 JSON containing `criterion` and the original adjudicated `finding`. |
| `source` | Path to the accepted audit. |

The [comparison command](runbook.md#compare-recorded-runs) exports all accepted
loss findings to `evidence_categories.tsv`. Without an annotation, a finding stays
`Unclassified`; its loss still counts. Review those rows and place each task's
annotations beside its audit, then repeat comparison. Duplicate, stale or
mismatched annotations are rejected. Audit JSON and recording files remain intact.

Comparison writes category counts per actor arm and representation to
`summary.json` and `report.md`. The TSV retains each finding's identity and
rationale. Keep primary and Pro annotations in their respective profile folders.
