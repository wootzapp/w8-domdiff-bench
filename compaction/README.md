# DOM-Diff-Summary Compaction

This directory contains the deterministic compaction and retrieval components
used by the DOM-diff-summary verifier. They reduce the amount of semantic DOM
evidence sent to the verifier LLM without modifying the source
`dom_diff_summary.json` files.

## Files

### `dom_diff_summary_compaction.py`

This module converts each recorder-produced `dom_diff_summary.json` into a
smaller, auditable semantic projection. It:

- preserves page transitions, visible-text changes, accessible names, links,
  values, and meaningful interactive-state changes;
- removes geometry-only changes such as coordinates, bounds, width, and height;
- normalizes whitespace and Unicode;
- removes exact duplicate text and fragments already contained in longer text;
- removes duplicate interactive elements;
- avoids repeating unchanged URLs and page titles;
- limits oversized individual records at complete record boundaries; and
- records hashes, source sizes, and explicit omission receipts.

### `dom_diff_summary_retrieval.py`

This module decides which compact evidence is most relevant to each rubric
criterion and packs it into bounded verifier requests. It:

1. Builds retrieval terms from the task, rubric criteria, and agent answer.
2. Scores action-aligned summary frames for criterion relevance.
3. Selects the highest-relevance frames for each criterion.
4. Packs all frames into a bounded relevance request.
5. Packs the selected frames into a bounded final-analysis request.
6. Records selected steps, relevance scores, hard-retention reasons, and the
   number of records omitted by token budgets.

## Compression pipeline

```text
dom_diff_summary.json
        |
        v
deterministic semantic compaction
        |
        v
criterion-aware frame retrieval
        |
        v
token-budgeted evidence packing
        |
        v
verifier LLM
```

The current S3 experiments use the following configurable limits:

- maximum individual record length: 600 characters;
- rendered frame budget: 1,500 tokens;
- batched trajectory relevance budget: 16,000 tokens;
- packed final-analysis budget: 24,000 tokens; and
- maximum evidence frames per rubric criterion: 5.

## Auditability and limitations

The raw summary files remain authoritative and unchanged. Each compact frame
retains the source path, SHA-256 hash, source byte size, source schema version,
and a receipt describing geometry removal, deduplication, truncation, source
truncation, and budget-based omissions.

Compaction can still omit evidence that later proves relevant. Matching verifier
scores therefore do not by themselves establish screenshot/DOM evidence parity.
Compaction receipts, selection receipts, and criterion-level score differences
should always be reviewed.

These files are copied from the DOM-diff-summary verifier implementation for
reproducibility. Their imports expect the FARA `webeval` package structure, so
they are reference components rather than standalone scripts.
