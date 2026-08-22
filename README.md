# Controlled Screenshot vs DOM-Diff-Text Verifier Benchmarks

This directory contains two self-contained verifier implementations for a
controlled browser-agent benchmark:

- `microsoft_verifier/` reproduces the screenshot-based Microsoft Universal
  Verifier path.
- `dom_diff_text/` evaluates the same logical trajectory using refined,
  action-aligned `dom_diffN.txt` evidence.

The packages do not import verifier code from each other or from the historical
`ms-paper-execution` implementation. The comparison runner holds the task,
semantic trajectory, final answer, frozen rubric, models, thresholds, scoring,
outcome, penalty, failure, validity, and token accounting constant. The intended
difference is screenshot evidence versus refined DOM-diff text, plus the
necessary coordinate-based versus semantic action-target representations.

## Repository layout

```text
.
├── microsoft_verifier/       # Standalone screenshot verifier and tests
├── dom_diff_text/             # Standalone refined DOM-text verifier and tests
├── scripts/                   # Preflight, rubric, execution, metrics, comparison
├── config/endpoints/openai/   # Non-secret GPT-5.2 and o4-mini endpoint configs
├── rubrics/                   # Shared canonical frozen rubric files
├── data/                      # Local paired datasets; contents are not committed
├── results/                   # Generated run artifacts; contents are not committed
├── tests/                     # Comparison/control-plane regression tests
├── RUNBOOK.md                 # Detailed operating and artifact contract
└── requirements.lock.txt      # Reproducible Python dependencies
```

## Requirements

- Python 3.12 (the audited environment used Python 3.12.3)
- An OpenAI API key with access to `gpt-5.2` and `o4-mini`
- Matching screenshot and refined-DOM task folders
- One canonical frozen rubric shared by both modes

From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps \
  -e microsoft_verifier \
  -e dom_diff_text
cp .env.example .env
chmod 600 .env
```

Set the key only in the ignored local file:

```text
OPENAI_API_KEY=...
```

Never commit `.env`.

## Dataset contract

Place one paired task under both modality roots:

```text
data/data-new-screenshot/taskN/
├── task_data.json
├── task_data_with_canonical_rubric.json   # optional provenance sidecar
├── final_answer.json
├── web_surfer.log
├── screenshot0.png
├── screenshot1.png
└── ...                                    # N actions -> N+1 states

data/data-new-short-dom/taskN/
├── task_data.json
├── task_data_with_canonical_rubric.json   # optional provenance sidecar
├── final_answer.json
├── web_surfer.log
├── dom_diff1.txt
├── dom_diff2.txt
└── ...                                    # one contiguous file per action
```

The DOM task must contain no screenshots or alternate browser-state evidence.
The two action logs may use different target representations, but preflight
requires the same semantic action sequence.

## Canonical frozen rubric

Both verifiers receive exactly one shared file:

```text
rubrics/taskN.json
```

Expected shape:

```json
{
  "task_id": "internal-task-id",
  "precomputed_rubric": {"items": []}
}
```

The comparison validates the rubric object, hash, criteria, and denominator
against both provenance sidecars before creating judge clients. Scoring never
silently falls back to a task-local sidecar and never generates separate rubrics
for the two modalities.

## Free preflight

This command makes no model calls and creates no result directory:

```bash
.venv/bin/python -m scripts.run_comparison --task taskN
```

Review the printed task ID, action/frame counts, rubric hash, denominator, models,
and generated commands before authorizing a paid run.

## Run the controlled paid comparison

`--execute` sends task evidence to the configured OpenAI endpoints and incurs
model usage:

```bash
.venv/bin/python -m scripts.run_comparison \
  --task taskN \
  --execute
```

The runner executes Microsoft screenshots first and DOM-diff text second, using
fresh output directories and `--redo-eval`. A failure stops the sequence.
Both verifiers run against disposable copies under the result directory, so
compatibility aliases and runtime artifacts cannot mutate the source datasets.


## Results

Each completed run writes:

```text
results/taskN/<UTC-run-id>/
├── run_manifest.json
├── _inputs/
│   ├── screenshot/            # Disposable copy used by Microsoft
│   └── dom/                   # Disposable copy used by DOM-text
├── microsoft_verifier/
│   ├── result.json
│   ├── run.log
│   └── run_metrics.json
├── dom_diff_text/
│   ├── verify_report_dom_diff_text.jsonl
│   ├── run.log
│   └── run_metrics.json
├── comparison.json
└── comparison.md
```

Metrics include criterion-level action and final scores, outcome/failure/validity
results, logical calls, API attempts, validation and transport retries, and
provider-reported prompt/completion/reasoning tokens. Reasoning tokens are a
subset of completion tokens and are not added twice.

## Offline verification

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q tests
.venv/bin/python -m pytest -q microsoft_verifier/tests
.venv/bin/python -m pytest -q dom_diff_text/tests
.venv/bin/python -m compileall -q \
  scripts \
  microsoft_verifier/src \
  dom_diff_text/src
```

For rubric generation, custom task paths, individual verifier commands, and the
complete artifact contract, see [RUNBOOK.md](RUNBOOK.md).
