# Standalone DOM-Model Universal Verifier

This package is a complete local verifier implementation. It retains the local
Microsoft rubric generation, criterion structure, process scoring, outcome
verification, first-failure classification, penalties, validity checks,
retries, metrics, and reporting. It imports no runtime code from the Microsoft
package, shared scripts, `benchmarks/`, `ms-paper-execution/`, or a DOM-diff
verifier.

The intentional evidence-only substitutions are:

- load complete ordered `dom_model0..N.txt` states instead of screenshots;
- score each complete state for criterion relevance and apply the same top-K
  control flow;
- analyze selected states using DOM-model text while returning compatibility
  fields expected by the unchanged downstream scoring pipeline.

The loader requires contiguous UTF-8 state files and exactly N+1 states for N
actions. Alignment binds state 0 to the task initial URL and each state i to the
post-state of action i. It records URLs, action transitions, refs, source hashes,
truncation flags, missing headers, and URL/ref mismatches without inventing
evidence.

Evidence packing preserves source order and prioritizes URL, title, snapshot,
dialogs, alerts, errors, validation, and truncation records. Any record omitted
for context limits is listed with state index, line range, character count,
estimated tokens, and reason. The evidence audit also records every state's
relevance score, selection/omission status, prompt estimate, warning, validation
retry, and fallback.

DOM-model text cannot establish pixel-only visual facts such as color,
typography, spacing, borders, exact geometry, overlap, clipping, z-order,
responsive layout, or unrepresented image/canvas/video content. Absence is
treated as unproven, especially when the source declares truncation.

Use the experiment-level scripts and [runbook](../RUNBOOK.md) so this verifier
and the Microsoft screenshot verifier receive the exact same frozen rubric.
