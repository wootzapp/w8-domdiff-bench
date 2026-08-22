# Reproducible screenshot vs DOM-text benchmark runbook

This folder runs one controlled comparison at a time. Both verifier modes use
one canonical frozen rubric JSON, the same task/final answer/semantic action
sequence, `gpt-5.2`, `o4-mini`, and the same scoring controls. The only intended
differences are screenshot versus refined `dom_diffN.txt` evidence and their
necessary coordinate versus semantic action-target representations.

## Files used by the experiment

```text
.
├── config/endpoints/openai/canonical/
│   ├── openai_gpt5_2.json
│   └── openai_o4_mini.json
├── data/
│   ├── data-new-screenshot/taskN/
│   └── data-new-short-dom/taskN/
├── rubrics/taskN.json
├── scripts/
│   ├── generate_frozen_rubric.py
│   ├── validate_inputs.py
│   ├── run_comparison.py
│   ├── results.py
│   └── compare_results.py
├── microsoft_verifier/
├── dom_diff_text/
├── results/taskN/<run-id>/
├── requirements.lock.txt
└── requirements-dev.txt
```

Neither verifier implementation imports `ms-paper-execution` or the other
verifier. The orchestration scripts launch them as separate Python processes.

## Environment

Use Python 3.12.3 for exact parity with the audited old Task4 run:

```bash
cd <repository-root>
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps -e microsoft_verifier -e dom_diff_text
cp .env.example .env
chmod 600 .env
```

Put the key in `.env`; the control scripts load it without printing it:

```text
OPENAI_API_KEY=...
```

## Existing frozen rubric

Every scoring run requires exactly one file shaped as:

```json
{
  "task_id": "internal-task-id",
  "precomputed_rubric": {"items": []}
}
```

Both verifiers receive this same path through `--rubric-file`. They verify the
canonical SHA-256 before initializing judge clients. A task-local
`task_data_with_canonical_rubric.json` is optional provenance only and is never
an implicit scoring fallback.

## Generate a rubric for a new task

First perform the zero-call dataset/config preflight:

```bash
cd <repository-root>
.venv/bin/python -m scripts.generate_frozen_rubric \
  --screenshot-task data/data-new-screenshot/taskN \
  --dom-task data/data-new-short-dom/taskN
```

After reviewing that receipt and explicitly approving paid rubric generation:

```bash
.venv/bin/python -m scripts.generate_frozen_rubric \
  --screenshot-task data/data-new-screenshot/taskN \
  --dom-task data/data-new-short-dom/taskN \
  --execute
```

The generator makes one rubric-generation workflow using the local Microsoft
`MMRubricAgent`: GPT-5.2 generation plus its o4-mini dependency check. It
preserves the generated positive denominator, writes `rubrics/taskN.json`,
writes identical provenance sidecars, and records calls/attempts/retries/tokens
in `rubrics/taskN_generation_metrics.json`. It never generates separate rubrics
per modality.

## Preflight an existing frozen-rubric comparison

```bash
cd <repository-root>
.venv/bin/python -m scripts.run_comparison --task task4
```

Without `--execute`, this command makes no model calls and creates no run
directory. It checks:

- identical task data, instruction, initial URL, and semantic final answer;
- semantic action-sequence equivalence while allowing intentional coordinate
  screenshot actions and semantic DOM targets;
- intentional `N actions -> N+1 screenshots`;
- contiguous `dom_diff1.txt ... dom_diffN.txt` and no alternate DOM evidence;
- one canonical rubric object/hash/denominator;
- local, non-secret OpenAI configs containing exactly GPT-5.2 and o4-mini;
- all fixed comparison settings and fresh output paths.

## Run the paid comparison

After reviewing the preflight and explicitly approving the paid run:

```bash
.venv/bin/python -m scripts.run_comparison \
  --task task4 \
  --execute
```

The command runs Microsoft first and DOM-text second. Each gets a fresh output
directory and `--redo-eval`; a failure stops the sequence. Outputs are:

```text
results/task4/<UTC-run-id>/
├── run_manifest.json
├── _inputs/
│   ├── screenshot/
│   └── dom/
├── microsoft_verifier/{result.json,run.log,run_metrics.json}
├── dom_diff_text/{verify_report_dom_diff_text.jsonl,run.log,run_metrics.json,...}
├── comparison.json
└── comparison.md
```

The verifier processes run-local copies under `_inputs/`. This is deliberate:
the unchanged Microsoft compatibility adapter may create canonical screenshot
aliases, and those generated aliases must never modify the audited source
dataset under `data/`.

`run_metrics.json` records criterion attribution, process/outcome/failure and
validity results, logical calls, API attempts, retries, and exact provider
prompt/completion/reasoning totals. Reasoning tokens remain a subset of
completion tokens. `comparison.md` refuses mismatched task IDs, rubric hashes,
denominators, models, settings, or inconsistent token/call accounting.

## Offline verification before a paid run

```bash
cd <repository-root>
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest tests
.venv/bin/python -m pytest microsoft_verifier/tests
.venv/bin/python -m pytest dom_diff_text/tests
.venv/bin/python -m compileall -q \
  scripts \
  microsoft_verifier/src \
  dom_diff_text/src
```
