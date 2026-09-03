# Evidence-Item Audit Runbook

The detailed audit reads existing verifier results and source evidence only. It makes no LLM calls and does not import or modify either verifier.

## 1. Create the review workspace

```bash
cd /data/isha/msexecute/evidence-error-experiment
export PYTHONPATH="$PWD"

.venv/bin/python -m scripts.audit_evidence_items \
  --run-dir results/task1/repeat10-10-20260901
```

This writes:

```text
RUN_DIR/evidence_error_audit/
├── criterion_audit.json
└── evidence_item_review.json
```

`criterion_audit.json` contains the existing screenshot and DOM verifier evidence, analysis, selected sources, justifications, and scores. `evidence_item_review.json` repeats that context under each criterion and provides an initially empty `evidence_items` list.

## 2. Add evidence items

For each concrete value or state required by the criterion, add one item:

```json
{
  "evidence_id": "C2-E1",
  "evidence_requirement": "Publisher shown on product page",
  "expected_value": "Electronic Arts",
  "review_status": "confirmed",
  "screenshot": {
    "source_present": true,
    "source_citations": [
      {
        "file": "screenshot6.png",
        "visible_text": "Published by Electronic Arts",
        "locator": "metadata row"
      }
    ],
    "verifier_caught": true,
    "verifier_evidence_excerpt": "Published by Electronic Arts",
    "review_note": "Visible and recovered."
  },
  "dom_model": {
    "source_present": true,
    "source_citations": [
      {
        "file": "dom_model4.txt",
        "line_range": "m4:L8-L10",
        "quoted_text": "Electronic Arts"
      }
    ],
    "verifier_caught": false,
    "verifier_evidence_excerpt": "publisher value is not visible",
    "review_note": "Value exists in source but was not recovered."
  }
}
```

Verifier excerpts must be copied verbatim from the existing context. DOM quotes must occur inside the cited line range. Screenshot citations are human-verified visible pixel evidence.

## 3. Validate and finalize

```bash
.venv/bin/python -m scripts.finalize_evidence_items \
  --audit results/task1/repeat10-10-20260901/evidence_error_audit/criterion_audit.json \
  --review results/task1/repeat10-10-20260901/evidence_error_audit/evidence_item_review.json \
  --output-dir results/task1/repeat10-10-20260901/evidence_error_audit
```

Final outputs:

```text
evidence_item_audit.json
evidence_error_metrics.json
evidence_error_report.md
```

Only confirmed evidence items enter the metrics. Items missing from either representation are excluded from common-evidence catch rates and directional recovery denominators.
