# w8-domdiff-bench

`w8-domdiff-bench` records browser tasks with DOM and screenshot observations.
Paired state artifacts support evidence-loss analysis alongside model turns,
token usage, tokens per model turn and independently graded task completion. Each actor receives its
selected page observation, while the recorder saves both formats for each state.

Tasks run in both arms with an explicit number of trials. A schedule ledger
records execution order and outcomes, and the comparison reports all scheduled
attempts. See the [datacard](docs/datacard.md) for observation policies and shared
settings, the [runbook](docs/runbook.md) for commands, and the
[architecture](docs/architecture.md), [evaluation protocol](docs/evaluation-protocol.md)
and [recording contract](docs/recordings.md) for implementation details.

## Setup

Requirements: Linux or WSL 2, Python 3.10+, Git, Docker Engine with Compose, and
network access for dependencies, browser images, task pages and model calls.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
[ -f .env ] || cp .env.example .env
```

Source and wheel distributions include the verifier integrity manifests in
`manifests/`. Verifier preflight checks these against the native packages and
their shared dependencies. Run benchmark commands from the repository root,
which supplies the catalog, configuration and Compose files.

Set the actor through `ACTOR_MODEL` in `.env`; it must be `gemini-3.1-pro-preview`.
Configure `OPENAI_API_KEY`, `GEMINI_API_KEY` and the audit models shown in
`.env.example`. Completion uses an explicit `gpt-6.1-sol` judge.
`GEMINI_BASE_URL` selects the actor endpoint; `OPENAI_BASE_URL` selects the
OpenAI endpoint.
Set `IMAGE` to a browser image tag or immutable digest. The hosted
`wootzapp/w8-core` image provides the browser runtime; the runbook also describes
[building an image](docs/runbook.md#browser-image-build).

The default container is `w8-turns-browser-engine`, with CDP on 49345, noVNC on
16291 and VNC on 16011. The launcher starts each attempt with a fresh browser
profile and verifies service ownership. Script wrappers use this directory's
`.venv/bin/python`. Check [browser status](docs/runbook.md#browser-runtime)
before recording.

| Component | Model |
| --- | --- |
| Browser actor, both arms | `gemini-3.1-pro-preview` |
| Rubric generation and dependency check | `gpt-5.2` |
| Screenshot verifier | `gemini-3.1-pro-preview`; action-only scoring and validity: `gemini-3.8-flash` |
| DOM verifier | `gemini-3.1-pro-preview`; action-only scoring and validity: `gemini-3.8-flash` |
| Evidence inventory | `gemini-3.1-pro-preview` |
| Evidence-loss adjudication | `gpt-6.1-sol` |
| Common completion judge | `gpt-6.1-sol` |

## Record tasks

The task catalog is [data/tasks.jsonl](data/tasks.jsonl), with IDs `task_01` through `task_25`.
See the [task catalog](data/README.md) and the
[collection and evaluation sequence](docs/runbook_next.md).

Set `BENCH_TRIALS` to a positive integer. Without positional task IDs, the command
selects every task in the explicit local catalog. Each batch requires frozen
rubrics and the completion judge. After each adjacent actor pair, every run gets
common completion, both auxiliary verifiers and a within-run evidence-loss audit.

```sh
: "${BENCH_TRIALS:?Set a positive trial count per arm}"
./scripts/run-task \
  --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl \
  --output-dir recordings --run-name benchmark \
  --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol
```

Use `--dry-run` to write and inspect the schedule without starting tasks. Repeat
the same command to resume; completed attempts, including failures, are retained.
Both actors of a task/trial run back to back, alternating which arm starts.

For a subset, add positional IDs such as `task_08 task_12 task_23`.
The launcher accepts any frozen local catalog and task IDs. The schedule binds
the selected definitions, rubric hashes, model settings, recorder source and
output paths. Use a distinct run name for a different task set or configuration.

## Outputs

```text
recordings/benchmark/ledger.jsonl
recordings/benchmark/logs/attempt_000001.log
recordings/benchmark/trial_0001/dom/<task>/
recordings/benchmark/trial_0001/screenshot/<task>/
```

| Artifact | Contents |
|---|---|
| `ledger.jsonl` | Task, arm, trial, order, configuration, output path, technical outcome and grading outcome. |
| `task.json`, `manifest.json`, `final.json` | Task definition, controls, browser provenance, captured states, actions and actor outcome. |
| `decisions.jsonl` | One row per actor request, including rejected proposals, malformed responses and termination. |
| `turns/turn_NNNNNN/` | Request, response and result, including usage, model ID, latency and output-limit status. Screenshot requests reference the saved image by path and SHA-256. |
| `steps/step_NNN/` | Screenshot, structured DOM, readable DOM projections, capture metadata and outgoing action record. DOM states also contain executable references. |
| `trajectory.jsonl`, `web_surfer.log` | Ordered actions and execution outcomes; trajectories include capture-artifact references. |
| `completion.json` | Primary independent completion grade using paired evidence from the run. |
| `completion_actor_native.json` | Optional secondary grade using the actor's observation format. |
| Sibling `evaluations/` tree | Hash-bound flat evidence inputs, rubric/import receipts, both verifier results, audit, quality diagnostics and separate judge usage. |

Capture metadata records timing, navigation and passive-capture errors. A usable
active observation allows the actor to continue when passive capture fails;
paired completeness is recorded separately. Technical outcomes, actor-reported
status and independently graded completion are separate result fields.

## Compare results

```sh
./scripts/run-comparison \
  --ledger recordings/benchmark/ledger.jsonl \
  --output reports/benchmark
```

Comparison runs offline and includes startup failures and missing recordings in
the scheduled denominator. Reports contain completion, turns, tokens, grading
coverage, unmatched arms, tokens per turn, directional losses by driver/category and pass@k. Shared settings, browser provenance, capture
policies and grading controls are checked across arms and trials.

Actor and judge usage are reported separately. Cached-input and reasoning tokens
are subsets of provider totals. Incomplete recordings or missing usage produce
cost lower bounds; exact averages require complete coverage.

## Tests

```sh
.venv/bin/python -m pytest -q tests
```

The suite uses offline browser/model fixtures. The runbook includes a
[browser capture check](docs/runbook.md#tests) for scroll and focus preservation.
