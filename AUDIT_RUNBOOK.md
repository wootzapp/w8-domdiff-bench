# Existing-Output Evidence Audit Runbook

This audit reads completed verifier artifacts only. It does not import either verifier package, construct a client, change a prompt, or make an LLM call.

## Fields extracted from both verifier results

From `intermediate_mm_rubric_steps`:

- `step2_relevance_scores`
- `step3_grouped_screenshots`
- `step4_evidence_by_criterion[*].screenshot_idx`
- `step4_evidence_by_criterion[*].dom_model_state_idx` when present
- `step4_evidence_by_criterion[*].screenshot_evidence`
- `step4_evidence_by_criterion[*].criterion_analysis`
- `step4_evidence_by_criterion[*].discrepancies`
- `step4_evidence_by_criterion[*].environment_issues_confirmed`
- `step4_evidence_by_criterion[*].condition_verification` when present
- `step6_rescoring_summary[*].criterion`
- `step6_rescoring_summary[*].earned_points`
- `step6_rescoring_summary[*].post_image_earned_points`
- `step6_rescoring_summary[*].max_points`
- `step6_rescoring_summary[*].justification`
- `step6_rescoring_summary[*].applicable_evidence`
- `step6_rescoring_summary[*].post_image_justification`
- `step6_rescoring_summary[*].reality_notes`
- `step6_rescoring_summary[*].penalty` when present

The audit also records `task_id`, `rubric_sha256`, source filenames, file sizes, and SHA-256 hashes. Every verifier-generated evidence and justification string is retained verbatim.

## Create the side-by-side audit

```bash
cd /data/isha/msexecute/evidence-error-experiment
export PYTHONPATH="$PWD"

.venv/bin/python -m scripts.audit_existing_outputs \
  --run-dir results/task25/20260901T170000Z
```

Outputs are written to `RUN_DIR/evidence_error_audit/`:

- `criterion_audit.json`: side-by-side extracted fields and disagreement flags.
- `disagreement_review.json`: manual fields for flagged criteria.
- `evidence_error_metrics.json`: initial metrics; unreviewed criteria remain unclassified.
- `evidence_error_report.md`: compact side-by-side report.

## Confirm disagreements

For every flagged row in `disagreement_review.json`, inspect the listed screenshots and ordered `dom_modelN.txt` states. Set `evidence_available` and `caught_correctly` to booleans for both modes, add short source notes, and change `review_status` to `confirmed`.

Apply the decisions:

```bash
.venv/bin/python -m scripts.build_audit_review \
  --audit results/task25/20260901T170000Z/evidence_error_audit/criterion_audit.json \
  --review results/task25/20260901T170000Z/evidence_error_audit/disagreement_review.json \
  --output results/task25/20260901T170000Z/evidence_error_audit/criterion_audit_reviewed.json
```

## Calculate the final metrics

```bash
.venv/bin/python -m scripts.summarize_error_metrics \
  --audit results/task25/20260901T170000Z/evidence_error_audit/criterion_audit_reviewed.json \
  --output-dir results/task25/20260901T170000Z/evidence_error_audit
```

Only confirmed records receive one of the six classifications. Evidence-missing cases are excluded from the corresponding recovery denominator, and a zero denominator is reported as `null`/`N/A` rather than zero percent.
