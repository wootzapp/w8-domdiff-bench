# Screenshot and DOM-diff verifier comparison

## Structure

```text
verifier/
├── dom_diff/              # Standalone DOM-evidence verifier package
├── microsoft_verifier/    # Fixed Microsoft screenshot baseline
├── manifests/             # Verifier-package integrity receipts
├── scripts/               # Frozen-rubric and comparison orchestration
├── config/                # Judge endpoint configuration
├── run-comparison         # One-command launcher
└── requirements.txt
```

Paired task inputs are resolved from Hugging Face into the ignored
repository-level `.cache/hf-trajectories/` directory. They are not sourced from
Git or from a repository-local dataset folder. Generated runs are written to
the repository-level `evaluation/` folder.

The recorded trajectories are hosted in the
[`WootzappLab/browser-agent-tasks`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks)
dataset under `trajectories/`. The Dataset Viewer remains restricted to
`tasks.jsonl`; trajectory files are available through Files and versions but do
not become rows on the dataset card.

## Set up the comparison

Python 3.10 or newer is required. From a fresh clone, enter the verifier
folder, create its virtual environment, and install the pinned dependencies:

```bash
cd path/to/your/folder/verifier

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Fetch trajectory data

Download one paired screenshot/DOM trajectory into the ignored cache:

```bash
./dataset-sync fetch --task task_01
```

Download every paired trajectory:

```bash
./dataset-sync fetch --all
```

Public downloads require no Hugging Face login. Set `HF_TOKEN` only if the
dataset later becomes private or gated. `W8_BENCH_DATASET_REPO` can override
the default repository.

Create the local environment file, then set its API key with your preferred
text editor:

```bash
cp .env.example .env
```

Set the OpenAI API key in `.env`:

```text
OPENAI_API_KEY=your-api-key
```

The launcher reads this file automatically. `.env` is ignored by Git and must
not be committed.

## Run a complete comparison

Tasks are selected by their Hugging Face folder alias. To evaluate `task_01`,
run:

```bash
./run-comparison --task task_01 --execute
```

The launcher always resolves the selected trajectory from Hugging Face before
rubric generation. There is no local-dataset fallback or public local-task
override. Downloaded files are cached only to provide concrete inputs to the
unchanged verifier packages.

This command generates one fresh Microsoft rubric, passes that exact frozen
rubric to both verifiers, scores both evidence formats, and then runs an
independent automated pairwise evidence audit. The first audit call inventories
every rubric criterion against every screenshot, DOM state, and the normalized
shared action trajectory. A second call adjudicates every proposed loss and
verifier miss under stricter materiality and temporal-continuity rules. Only
confirmed adjudications contribute to modality-specific evidence loss. The
classification label is derived deterministically from the validated findings;
the audit model is not asked to invent or reproduce classification names. The
audit uses `gpt-5.6-sol` by default; this does not change the models
used by either verifier. It makes paid model calls and submits the supplied task
evidence to the configured API endpoint.

The command automatically resolves:

```text
Screenshot input: ../.cache/hf-trajectories/data-ss/task_01
DOM input:        ../.cache/hf-trajectories/data-dom/task_01
Judge config:     config/
Run output:       ../evaluation/task_01/<run-id>/
```

To validate configuration and paths without writing results or making paid
calls, omit `--execute`. This may populate the ignored Hugging Face cache:

```bash
./run-comparison --task task_01
```

Completed runs are stored under `../evaluation/<task>/<run-id>/`. The final
`comparison.json` and `comparison.md` contain verifier scores and the automated
evidence-loss summary. Detailed criterion decisions and citations are stored in
`evidence_audit.json` and `evidence_audit.md`. Raw verifier artifacts remain in
the `microsoft_verifier/` and `dom_diff/` subfolders.

If the audit model still returns invalid JSON after its bounded correction
attempts, the completed verifier comparison is preserved. The run is marked
`complete_with_audit_error`, and `evidence_audit_error.json` records every raw
invalid response and validation error. The isolated inputs are retained for
debugging or a later audit retry.

To freshly evaluate and audit every paired task:

```bash
./run-comparison --all --execute
```

The aggregate report is written under
`../evaluation/batches/<run-id>/evidence_loss_summary.{json,md}`. Tasks that
fail during rubric generation, verification, or auditing are reported
separately and are not silently included in the evidence-loss denominator.

The audit is fully automated and requires no human decisions. Its percentages
are therefore **LLM-audited evidence-loss rates**, not human-confirmed ground
truth. Neither verifier's prompts, evidence handling, nor scoring behavior is
changed by the post-verification audit.

## Maintainer upload

An authenticated maintainer can validate and upload all paired local
trajectories without changing the dataset-card viewer configuration:

```bash
hf auth login
./dataset-sync upload
```

The upload changes only `trajectories/data-ss/` and
`trajectories/data-dom/`. It does not upload verifier results, API keys, or the
local `.env` file.
