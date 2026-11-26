# w8-domdiff-bench

`w8-domdiff-bench` compares browser task execution with DOM and screenshot
observations. Each task runs in both arms with an explicit positive number of
trials. The actors receive only their selected page observation; the recorder
privately saves both formats for each state.

The catalog contains 40 public, read-only tasks: 10 each at easy, medium, hard
and complex difficulty. Both arms use the same actor settings and frozen task
criteria. A ledger records paired alternating order, fresh-browser attempts,
technical outcomes and grading coverage.

The [published dataset](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/paired-capture)
contains the catalog, frozen rubrics, recordings, trajectories and evaluations.
Download the catalog and rubrics through the [runbook](docs/runbook.md#get-the-benchmark-and-install-python)
before recording or running the offline checks.

Evaluation measures completion, model turns, token usage, tokens per model turn
and evidence loss. Completion uses common paired evidence. Each recording's evidence
loss compares only its own screenshots with its DOM; the two driving arms
remain separate. Arm token comparison includes the actor and its matching native
verifier: DOM plus DOM verification, or screenshots plus screenshot verification.
Actor-only usage and tokens per turn remain separate. All evaluation usage and
cost streams remain visible for full-experiment accounting.

## Documentation

| Read in order | What it covers |
| --- | --- |
| [Architecture](docs/architecture.md) | Components, execution flow and terminology. |
| [Datacard](docs/datacard.md) | Observation policies, model settings, limits and permitted arm differences. |
| [Task catalog](data/README.md) | Task schema, difficulty, constraints and catalog identity. |
| [Runbook](docs/runbook.md) | Setup, browser build, offline checks, rubric approval, pilot, collection, judging and reporting commands. |
| [Recordings](docs/recordings.md) | Ledgers, state artifacts, call receipts, provenance and export contracts. |
| [Evaluation protocol](docs/evaluation-protocol.md) | Completion, native profiles, evidence-loss decisions, denominators and metrics. |
| [Browser protocol](protocol/README.md) | ChromiumRL source and protocol pins, and binary build records. |

## Setup

Use Linux or WSL 2, Python 3.10 or higher, Git and Docker Engine with Compose.
Run commands from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
[ -f .env ] || cp .env.example .env
```

Set credentials and models in `.env`, using `.env.example` as a reference,
then follow the
[runbook](docs/runbook.md#environment-configuration) for isolated browser names
and ports. The browser image is `w8-core:domdiff-bench`; its build uses the local
Chromium and overlay checkouts bound by
[protocol/browser-build.json](protocol/browser-build.json).

The [pilot](docs/runbook.md#record-the-pilot) uses `task_01`, `task_12`, `task_29`
and `task_35`, both arms, one trial each.
Model requests use Google's GenerateContent API. Actor calls and rubric preparation
use direct requests, as do completion, both native verifiers and the evidence audit.
Evaluation uses `--stage evaluate` for completion, native verification and
inventory, then `--stage adjudicate` for final audit decisions from saved
inventories. The [judging instructions](docs/runbook.md#controls-and-outputs) cover profiles,
evaluation stages, resume and result bindings.

## Outputs

| Location | Contents |
| --- | --- |
| `recordings/<collection>/ledger.jsonl` | Scheduled tasks, arms, trials, attempts and execution/evaluation outcomes. |
| `recordings/<collection>/trial_NNNN/<arm>/<task>/` | Decisions, paired states, browser receipts and actor outcome. |
| `recording.parent.parent / "evaluations"` | Bound verifier inputs, common completion and profile-specific verifier and audit results. |
| `reports/<collection>/` | Offline aggregation, paired comparisons, metrics, costs and coverage. |

The [recording guide](docs/recordings.md) defines exact paths, including technical
attempts. The [evaluation protocol](docs/evaluation-protocol.md) defines what the
reports calculate. Results require completed recordings and grading; task success
is not inferred from an actor's terminal response alone.

## Tests

```sh
.venv/bin/python -m pytest -q tests
```

The suite uses offline fixtures. Browser checks require an explicitly selected
idle browser; their commands are in the
[runbook](docs/runbook.md#tests).
