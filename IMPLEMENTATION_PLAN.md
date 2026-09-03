# Existing-Output Evidence Error Audit — Implementation Plan

This experiment will compare what the existing Microsoft screenshot verifier and existing DOM-model verifier say they found for every rubric criterion. It will use their already-produced relevance, evidence-analysis, justification, and criterion-score outputs, then manually inspect source evidence only when the two modes disagree or one mode appears to miss evidence.

The experiment will be a standalone copy of `benchmarks-2/` under `evidence-error-experiment/`, with no runtime imports from `benchmarks-2/`. Verifier prompts, model calls, relevance, top-K selection, evidence analysis, scoring, retries, outcome logic, and reporting will initially remain unchanged; the only addition will be offline recording and auditing of existing outputs.

## 1. Scope and fixed boundaries

| Component | Role in this experiment | Evidence or planned status | How to verify | Implementation boundary |
|---|---|---|---|---|
| Microsoft verifier | Fixed screenshot baseline | Copied from the current `benchmarks-2/microsoft_verifier/` | Compare copied file manifest/hashes | No behavioral changes |
| DOM-model verifier | Existing DOM comparison mode | Copied from the current `benchmarks-2/dom_model/` | Compare copied file manifest/hashes | No behavioral changes |
| Shared runner/config | Runs both modes with one frozen rubric | Copied from the current `benchmarks-2/` setup | Existing offline parity/preflight tests | No runtime import from `benchmarks-2/` |
| Existing verifier outputs | Source of what each verifier caught or used | Read from criterion evidence, analysis, and final scoring fields | Preserve raw fields and source artifact paths | No new LLM prompt or call |
| Source evidence | Determines whether an apparent miss was a real miss | Screenshot files and ordered `dom_model0..N.txt` files | Manual inspection for disagreements | Source datasets remain read-only |
| Audit layer | Joins existing outputs and records classifications | New deterministic/offline scripts and reports | Offline tests and reproducible receipts | Must not feed back into either verifier |

Hard requirements:

- Do not modify `benchmarks-2/`.
- Do not modify `benchmarks/` or `ms-paper-execution/`.
- Do not import runtime code from `benchmarks-2/`.
- Do not add shadow observers, audit LLM calls, or new verifier prompts.
- Do not change either verifier’s scoring or evidence-handling behavior initially.
- Do not add atomic-claim decomposition or a separate annotation framework.
- Reuse the exact same frozen rubric for screenshot and DOM scoring.
- Keep source datasets read-only.
- Record the original evidence text verbatim instead of asking another model to reinterpret it.
- Do not make paid calls while implementing or testing the audit tooling.

## 2. Target standalone structure

After this plan is approved, the current contents and structure of `benchmarks-2/` will be copied into the new top-level experiment. The audit files will then be added only to the copy.

```text
evidence-error-experiment/
├── IMPLEMENTATION_PLAN.md
├── README.md
├── .env.example
├── requirements.txt
├── microsoft_verifier/          # standalone copy; screenshot behavior unchanged
├── dom_model/                   # standalone copy; DOM behavior unchanged
├── scripts/                     # copied runners plus new offline audit commands
│   ├── audit_existing_outputs.py
│   ├── build_audit_review.py
│   └── summarize_error_metrics.py
├── config/
├── data/
│   ├── data-new-screenshot/
│   └── data-new-dom-model/
├── rubrics/
├── manifests/
└── results/
    └── <task>/<run-id>/
        ├── microsoft_verifier/
        ├── dom_model/
        └── evidence_error_audit/
            ├── criterion_audit.json
            ├── disagreement_review.json
            ├── evidence_error_metrics.json
            └── evidence_error_report.md
```

The copied experiment must be independently runnable end to end using its own environment, configuration, data paths, rubrics, results, package manifests, and runners.

## 3. Experiment flow

```text
paired task data + one frozen rubric
                  │
                  ├──> unchanged screenshot verifier ──> existing screenshot result
                  │
                  └──> unchanged DOM verifier ─────────> existing DOM result
                                                        
existing result artifacts + original screenshot/DOM files
                  │
                  └──> deterministic offline audit extraction
                                      │
                            disagreement review file
                                      │
                          manual source check only where needed
                                      │
                         classifications and aggregate metrics
```

Nothing produced by the audit is passed back to either verifier.

## 4. Per-criterion audit record

For every task and frozen-rubric criterion, the audit will record only the information needed to compare the two existing outputs:

```json
{
  "task_id": "taskN",
  "rubric_sha256": "...",
  "criterion_index": 2,
  "criterion": "...",
  "max_points": 2,
  "screenshot": {
    "source_files": ["screenshot1.png", "screenshot2.png"],
    "selected_frames": [2, 1],
    "verifier_evidence": "verbatim existing screenshot_evidence/applicable_evidence",
    "verifier_justification": "verbatim existing final justification",
    "evidence_available": true,
    "caught_correctly": false,
    "review_note": "Required value is visibly present in screenshot2.png but was not identified."
  },
  "dom_model": {
    "source_files": ["dom_model0.txt", "dom_model1.txt", "dom_model2.txt"],
    "selected_states": [2, 1],
    "verifier_evidence": "verbatim existing DOM evidence/applicable_evidence",
    "verifier_justification": "verbatim existing final justification",
    "evidence_available": true,
    "caught_correctly": true,
    "review_note": "Verifier identified the required value from dom_model2.txt."
  },
  "screenshot_points": 0,
  "dom_model_points": 2,
  "classification": "SCREENSHOT_MISSED_DOM_CAUGHT",
  "manual_review_required": true,
  "manual_review_status": "confirmed"
}
```

This is an audit sidecar, not a replacement verifier result. The exact existing output field names may differ between the two packages; the extraction script will map them into this common record while also retaining their raw artifact paths.

## 5. What “caught” and “missed” mean

For one rubric criterion and one modality:

- **Caught correctly:** the existing verifier output identifies and uses evidence that correctly supports or contradicts the criterion.
- **Missed:** the required evidence was actually available in that modality’s source files, but the existing verifier failed to identify it, misread it, treated it as unknown, or failed to use it correctly.
- **Evidence missing:** the required evidence was not available in that modality’s source files. This is a capture/representation limitation, not a verifier miss.

A lower criterion score does not by itself mean evidence was missed. A higher criterion score does not by itself mean evidence was caught correctly. The audit must inspect what the verifier said it relied on.

## 6. Classification rules

The audit will use only the requested main classifications:

| Classification | Screenshot evidence | Screenshot verifier | DOM evidence | DOM verifier |
|---|---|---|---|---|
| `BOTH_CAUGHT` | Available | Caught correctly | Available | Caught correctly |
| `SCREENSHOT_MISSED_DOM_CAUGHT` | Available | Missed | Available | Caught correctly |
| `DOM_MISSED_SCREENSHOT_CAUGHT` | Available | Caught correctly | Available | Missed |
| `BOTH_MISSED` | Available | Missed | Available | Missed |
| `SCREENSHOT_EVIDENCE_MISSING` | Missing | Not counted as a verifier miss | Available or missing | Recorded separately in modality fields |
| `DOM_EVIDENCE_MISSING` | Available | Recorded separately in modality fields | Missing | Not counted as a verifier miss |

Classification precedence:

1. If screenshot evidence is missing, use `SCREENSHOT_EVIDENCE_MISSING`.
2. Otherwise, if DOM evidence is missing, use `DOM_EVIDENCE_MISSING`.
3. If evidence is available in both modalities, use one of the four caught/missed classifications.

If evidence is missing from both modalities, the record will use `SCREENSHOT_EVIDENCE_MISSING` under the precedence rule, while both modality fields will explicitly say `evidence_available: false`. Such records will be excluded from both recovery-rate denominators.

## 7. Existing outputs to extract

The offline extractor will read, where present:

- Frozen rubric task ID, hash, criterion order, descriptions, and maximum points.
- Screenshot and DOM relevance scores.
- Top-K frame/state selections and omission information.
- Existing per-frame/per-state evidence-analysis text.
- Existing `screenshot_evidence`, `criterion_analysis`, and `discrepancies` fields.
- Existing `applicable_evidence` and final/post-image justification fields.
- Action-only points, final criterion points, and maximum points.
- Result artifact path, run ID, source file paths, and source hashes.

The extractor will not semantically rewrite verifier evidence. It will preserve exact strings and organize them by task, criterion, and modality.

## 8. Lightweight manual review workflow

Manual inspection is required only when the existing outputs disagree or indicate a possible miss:

1. Generate the per-criterion audit table from the two existing result artifacts.
2. Automatically flag different evidence conclusions, different criterion points, `unknown`/missing statements, or evidence text that appears inconsistent.
3. Open the corresponding screenshots and `dom_modelN.txt` states.
4. Mark `evidence_available` for each modality.
5. Mark whether each verifier caught and used the available evidence correctly.
6. Add one short review note pointing to the relevant frame or DOM state.
7. Assign the classification deterministically from those four booleans.

Agreement cases may initially be marked `manual_review_status: not_required`. Because they are not manually verified, reports must distinguish “both verifiers agreed” from “human-confirmed BOTH_CAUGHT.” A small agreement sample may be checked later as a quality-control measure without changing the main workflow.

## 9. Primary metrics

### 9.1 Screenshot miss recovered by DOM

This is the main metric:

```text
DOM recovery of confirmed screenshot misses =
  SCREENSHOT_MISSED_DOM_CAUGHT
  / (SCREENSHOT_MISSED_DOM_CAUGHT + BOTH_MISSED)
```

Interpretation:

> Of all human-confirmed cases where screenshot evidence was available but the screenshot verifier missed it, what percentage did the DOM verifier correctly recover?

`SCREENSHOT_EVIDENCE_MISSING` is excluded because missing source evidence is not a screenshot-verifier perception error.

### 9.2 DOM miss recovered by screenshot

The reverse metric is:

```text
Screenshot recovery of confirmed DOM misses =
  DOM_MISSED_SCREENSHOT_CAUGHT
  / (DOM_MISSED_SCREENSHOT_CAUGHT + BOTH_MISSED)
```

Interpretation:

> Of all human-confirmed cases where DOM evidence was available but the DOM verifier missed it, what percentage did the screenshot verifier correctly recover?

`DOM_EVIDENCE_MISSING` is excluded.

Every reported percentage must include its numerator and denominator. If no confirmed misses exist, the metric is `not_applicable`, not zero.

## 10. Report format

The main Markdown report will contain one concise table:

| Task | Criterion | Screenshot evidence reported | DOM evidence reported | Screenshot source check | DOM source check | Screenshot result | DOM result | Classification |
|---|---|---|---|---|---|---:|---:|---|
| taskN | C2 | “No readable destination value” | “Destination value is Brandenburg Gate” | Present in frame 2; missed | Present in state 2; caught | 0/2 | 2/2 | `SCREENSHOT_MISSED_DOM_CAUGHT` |

The summary will report:

- Total audited tasks and rubric criteria.
- Count of each of the six classifications.
- Number of disagreements manually reviewed and confirmed.
- DOM recovery rate for confirmed screenshot misses.
- Screenshot recovery rate for confirmed DOM misses.
- Evidence-missing counts by modality.
- Unresolved records, if source evidence cannot be confidently judged.

## 11. Validation and offline tests

The future implementation will include offline tests proving that:

- The copied packages do not import from `benchmarks-2/`.
- The copied verifier manifests match the source copy at experiment creation time.
- Audit-disabled verifier outputs remain behaviorally unchanged.
- One frozen rubric/hash/order/denominator is shared by both modes.
- Existing evidence strings are retained verbatim.
- Criterion records join by task, rubric hash, and criterion index.
- Missing or mismatched result artifacts fail clearly.
- All six classifications follow the defined boolean rules.
- Screenshot-missing and DOM-missing cases are excluded from miss-recovery denominators.
- Audit scripts make no LLM client calls.
- Audit artifacts never become verifier inputs.
- Source datasets are not modified.

## 12. Implementation sequence after approval

1. Copy the complete current `benchmarks-2/` tree into `evidence-error-experiment/`, excluding machine-local transient files such as `.venv`, caches, and generated bytecode while preserving all source, configuration templates, data, rubrics, runners, manifests, tests, and result structure required for standalone execution.
2. Rewrite only experiment-root paths and package/environment setup needed for standalone execution; do not change verifier behavior.
3. Prove there are no runtime imports or path dependencies on `benchmarks-2/`.
4. Add deterministic audit extraction from existing screenshot and DOM result artifacts.
5. Add the lightweight disagreement-review record and classification logic.
6. Add metric calculation and Markdown/JSON reporting.
7. Run offline tests and dry-run preflights only.
8. Report copied files, added audit files, tests executed, failures, and confirmation that `benchmarks-2/` remained unchanged.

## 13. Verified, inferred, and unresolved boundaries

- **Directly verified before drafting:** the current experiment has separate screenshot and DOM packages, a shared frozen-rubric comparison workflow, existing criterion evidence-analysis text, criterion scores, and DOM evidence-selection instrumentation.
- **Planned but not yet implemented:** the standalone copy, common audit records, deterministic classification, manual review files, metrics, and reports.
- **Not inferred from score alone:** evidence presence, perception failure, or correctness of either verifier’s reasoning.
- **Denominator boundary:** only human-confirmed, evidence-available misses enter the two recovery-rate denominators.
- **Agreement boundary:** an unreviewed `BOTH_CAUGHT` classification represents verifier agreement, not independently verified ground truth.

## 14. Approval boundary

This file is a plan only. At this stage, do not copy `benchmarks-2/`, add audit code, run paid evaluations, or change either verifier. Implementation begins only after this simplified workflow is reviewed and explicitly approved.

The dominant design is therefore a standalone copy plus a deterministic audit of existing outputs, with manual source inspection limited to disagreements. The main remaining risk is misclassifying agreement cases without human review; the next concrete step after approval is to copy the experiment and build the offline extractor without changing verifier behavior.
