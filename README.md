# w8-domdiff-bench

`w8-domdiff-bench` compares browser task execution with DOM and screenshot
observations. Each task runs in both arms with an explicit positive number of
trials. The actors receive only their selected page observation; the recorder
privately saves both formats for each state.

The catalog contains 40 public, read-only tasks: 10 each at easy, medium, hard
and complex difficulty. Both arms use the same actor settings and frozen task
criteria. A ledger records paired alternating order, fresh-browser attempts,
technical outcomes and grading coverage.

Evaluation measures completion, model turns, token usage, tokens per model turn
and evidence loss. Completion uses common paired evidence. Each recording's evidence
loss compares only its own screenshots with its DOM; the two driving arms
remain separate. Actor usage and judge usage are accounted for separately.

## Documentation

| Read in order | What it covers |
| --- | --- |
| [Architecture](docs/architecture.md) | Components, execution flow and terminology. |
| [Datacard](docs/datacard.md) | Observation policies, model settings, limits and permitted arm differences. |
| [Task catalog](data/README.md) | Task schema, difficulty, constraints and catalog identity. |
| [Runbook](docs/runbook.md) | Setup, browser build, offline checks, rubric approval, pilot, collection, judging and reporting commands. |
| [Recordings](docs/recordings.md) | Ledgers, state artifacts, call receipts, provenance and export contracts. |
| [Evaluation protocol](docs/evaluation-protocol.md) | Completion, native profiles, evidence-loss decisions, denominators and metrics. |
| [Cost estimate](docs/cost-estimate.md) | Token and pricing assumptions, per-stage estimates and measured cost accounting. |
| [Browser protocol](protocol/README.md) | ChromiumRL source, binary and protocol pins. |

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

The [pilot](docs/runbook.md#record-the-pilot) uses `task_26`, `task_02`, `task_19`
and `task_25`, both arms, one trial each. Review it before the full collection.
Actor calls and rubric preparation use normal transport; judging defaults to
Batch. Pending judging returns 75; repeat the same evaluation command to poll.
The [judging instructions](docs/runbook.md#controls-and-outputs) cover profiles,
queue cancellation and uncertain submission receipts.

## Outputs

| Location | Contents |
| --- | --- |
| `recordings/<collection>/ledger.jsonl` | Scheduled tasks, arms, trials, attempts and execution/evaluation outcomes. |
| `recordings/<collection>/trial_NNNN/<arm>/<task>/` | Decisions, paired states, browser receipts and actor outcome. |
| `recording.parent.parent / "evaluations"` | Bound verifier inputs, common completion, profile-specific verifier and audit results, and Batch receipts. |
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
idle browser; their commands and approval gates are in the
[runbook](docs/runbook.md#tests).
