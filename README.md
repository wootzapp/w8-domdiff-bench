# Evidence Error Experiment

This standalone experiment compares the Microsoft screenshot verifier with the DOM-model verifier using the same frozen rubric. It also supports an offline, human-confirmed audit of evidence that was available in each representation but missed by its verifier.

The audit reads completed result files and source evidence only. It does not change verifier prompts, model calls, relevance, top-K selection, scoring, retries, validity, evidence handling, or reporting, and audit decisions are never passed back into either verifier.

## Repository structure

```text
evidence-error-experiment/
├── .env.example                 # local API-key template
├── requirements.txt             # pinned Python dependencies
├── config/                      # endpoint and model configuration
├── data/
│   ├── data-new-screenshot/     # screenshot task folders
│   └── data-new-dom-model/      # matching DOM-model task folders
├── microsoft_verifier/          # standalone screenshot verifier
├── dom_model/                   # standalone DOM-model verifier
├── scripts/                     # rubric, comparison, audit, and report commands
├── rubrics/                     # frozen rubrics and Phase A usage metrics
├── manifests/                   # expected verifier-package hashes
└── results/                     # isolated run inputs, outputs, and audits
```

The package-level READMEs are retained because they document the two independent packages. Both `resources/error_taxonomy_analysis.md` files are required runtime resources loaded by verifier code. Markdown files under `results/` are generated experiment reports and should also be retained.

Neither verifier imports runtime code from `benchmarks-2/`, `benchmarks/`, `ms-paper-execution/`, or the other verifier package.

## Build the local environment

Requirements:

- Python 3.10 or newer
- Network access and an OpenAI API key only for an explicitly authorized paid run
- Enough storage for screenshots, DOM states, and isolated result copies

From the experiment root:

```bash
cd /path/to/evidence-error-experiment
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Add `OPENAI_API_KEY` to `.env`. Do not commit `.env`. Offline tests and preflights do not require the key.

Set the local import paths in every new shell:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD/microsoft_verifier/src:$PWD/dom_model/src:$PWD"
```

Keep the `PYTHONPATH` assignment on one line.

## Task-data format

Each task needs matching folders:

```text
data/data-new-screenshot/taskN/
├── task_data.json
├── web_surfer.log
├── final_answer.json
├── screenshot0.png
├── screenshot1.png
└── ...

data/data-new-dom-model/taskN/
├── task_data.json
├── web_surfer.log
├── final_answer.json
├── dom_model0.txt
├── dom_model1.txt
└── ...
```

For `N` actions, the validator requires `N+1` contiguous states in each modality. State 0 is initial, state `i` is after action `i`, and the last state is final. The paired task ID, action history, final answer, rubric, criterion order, denominator, and maximum points must match.

## Phase A: create one frozen rubric

Start with the offline preflight:

```bash
.venv/bin/python -m scripts.generate_frozen_rubric \
  --screenshot-task data/data-new-screenshot/taskN \
  --dom-task data/data-new-dom-model/taskN
```

After explicitly approving paid rubric-generation calls, repeat with `--execute`. To freeze an existing rubric without a model call, use `--import-rubric /path/to/rubric.json --execute`. Use `--overwrite` only when intentionally replacing existing Phase A artifacts.

Phase A writes:

- `rubrics/taskN.json`
- `rubrics/taskN_generation_metrics.json`
- `task_data_with_canonical_rubric.json` in both experiment-owned task folders

Rubric-generation calls and tokens remain separate from evaluation usage.

## Phase B: run a comparison

Always run the offline preflight first:

```bash
.venv/bin/python -m scripts.run_comparison --task taskN
```

It validates package manifests, paired inputs, `N+1` alignment, endpoint declarations, rubric sidecars and hashes, scoring-control parity, and use of the exact same frozen rubric. It performs no writes or model calls.

After explicitly approving paid calls and external submission, run:

```bash
.venv/bin/python -m scripts.run_comparison \
  --task taskN \
  --run-id manual-taskN-$(date -u +%Y%m%dT%H%M%SZ) \
  --execute
```

Each run ID must be unique. Results are stored in `results/taskN/<run-id>/`:

```text
├── _inputs/                         # isolated task and rubric copies
├── microsoft_verifier/
│   ├── result.json                  # raw screenshot-verifier output
│   ├── run_metrics.json             # normalized scores, calls, and tokens
│   └── run.log
├── dom_model/
│   ├── result.json                  # raw DOM-verifier output
│   ├── run_metrics.json             # normalized scores, calls, and tokens
│   ├── evidence_audit.json          # DOM evidence trace, when emitted
│   └── run.log
├── comparison.json                  # machine-readable comparison
├── comparison.md                    # readable score/token comparison
└── run_manifest.json                # inputs, controls, hashes, commands
```

Phase B scoring records zero rubric-generation calls; Phase A usage stays in the rubric-generation metrics file.

## Audit evidence misses

The audit uses existing outputs only and makes no model calls. Create the review workspace:

```bash
.venv/bin/python -m scripts.audit_evidence_items \
  --run-dir results/taskN/<run-id>
```

This creates `evidence_error_audit/criterion_audit.json` and `evidence_item_review.json`. For each concrete criterion value or state, review and record:

- whether the evidence is actually present in the screenshot source;
- whether the screenshot verifier caught and used it correctly;
- whether it is actually present in the DOM-model source;
- whether the DOM verifier caught and used it correctly;
- the screenshot filename and visual locator, or DOM filename and line range;
- a verbatim excerpt from the corresponding verifier output.

A score difference alone does not prove a miss. “Missed” means evidence was available in that representation but its verifier failed to identify or use it correctly. Absent source evidence is a capture/representation limitation, not a verifier miss. Disagreements require manual source inspection.

Finalize the completed review:

```bash
.venv/bin/python -m scripts.finalize_evidence_items \
  --audit results/taskN/<run-id>/evidence_error_audit/criterion_audit.json \
  --review results/taskN/<run-id>/evidence_error_audit/evidence_item_review.json \
  --output-dir results/taskN/<run-id>/evidence_error_audit
```

This validates citations and verifier excerpts, then writes `evidence_item_audit.json`, `evidence_error_metrics.json`, and `evidence_error_report.md`.

| Classification | Meaning |
|---|---|
| `BOTH_CAUGHT` | Evidence was present in both and both verifiers caught it. |
| `SCREENSHOT_MISSED_DOM_CAUGHT` | Both contained it; screenshot missed it and DOM caught it. |
| `DOM_MISSED_SCREENSHOT_CAUGHT` | Both contained it; DOM missed it and screenshot caught it. |
| `BOTH_MISSED` | Both contained it and both verifiers missed it. |
| `SCREENSHOT_EVIDENCE_MISSING` | The screenshot source did not contain it. |
| `DOM_EVIDENCE_MISSING` | The DOM source did not contain it. |

The primary metrics are DOM recovery of confirmed screenshot misses and screenshot recovery of confirmed DOM misses. Only human-confirmed, evidence-available items enter those denominators; a zero denominator is reported as `N/A`.

## Existing result fields extracted

The audit preserves existing text from:

- `intermediate_mm_rubric_steps.step2_relevance_scores`
- `intermediate_mm_rubric_steps.step3_grouped_screenshots`
- `intermediate_mm_rubric_steps.step4_evidence_by_criterion[*]`
- `intermediate_mm_rubric_steps.step6_rescoring_summary[*]`
- task/rubric identity, source filenames, file sizes, and SHA-256 hashes

These contain source indices, evidence text, criterion analysis, discrepancies, environment issues, condition verification, points, justifications, applicable evidence, reality notes, and penalties where emitted.

Some inherited schema fields contain the word `screenshot`. In a DOM result these are legacy field names, not evidence that screenshots were passed to the DOM verifier. The external audit layer labels each modality correctly.

## Offline tests

Run the suites separately because the two packages contain duplicate test-module names:

```bash
cd microsoft_verifier
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ../.venv/bin/python -m pytest -p no:cacheprovider -q

cd ../dom_model
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ../.venv/bin/python -m pytest -p no:cacheprovider -q

cd ..
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="microsoft_verifier/src:dom_model/src:." \
.venv/bin/python -m pytest -p no:cacheprovider -q scripts/tests
```

The suites cover verifier behavior, DOM alignment, frozen-rubric parity, package boundaries, normalization, audit classifications, citation validation, and offline preflight behavior.

## Interpretation limits

DOM text cannot prove pixel-only properties such as color, typography, spacing, geometry, overlap, clipping, z-order, responsive layout, or visual emphasis. It cannot prove image, canvas, video, shadow-DOM, cross-origin, or server-side state unless captured explicitly. Missing or truncated content is unproven, not false.

Agreement between verifiers is not automatically human-verified correctness. Evidence-error rates should only use completed manual source checks with explicit citations.
