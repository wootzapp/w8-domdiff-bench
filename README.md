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

Set the actor through `ACTOR_MODEL` in `.env`; it must be `gemini-3.8-flash`.
Configure `OPENAI_API_KEY`, `GEMINI_API_KEY` and the audit models shown in
`.env.example`. Completion uses an explicit `gpt-6.1-sol` judge.
`ACTOR_MEDIA_RESOLUTION` accepts `HIGH` (default) or `ULTRA_HIGH` for screenshot
input. `GEMINI_BASE_URL` selects the actor endpoint; `OPENAI_BASE_URL` selects the
OpenAI endpoint.
Build the browser image as `w8-core:domdiff-bench`, the default `IMAGE` value,
using the [image build instructions](docs/runbook.md#browser-image-build).
An explicit tag or immutable digest can select another prepared browser build.

The default container is `w8-core-browser-engine`, with CDP on 49335, noVNC on
16191 and VNC on 15911. The launcher starts each attempt with a fresh browser
profile and verifies service ownership. Script wrappers use this directory's
`.venv/bin/python`. Check [browser status](docs/runbook.md#browser-runtime)
before recording.

| Component | Model |
| --- | --- |
| Browser actor, both arms | `gemini-3.8-flash` |
| Rubric generation and dependency check | `gpt-5.2` |
| Screenshot verifier | `gemini-3.1-pro-preview` |
| DOM verifier | `gemini-3.1-pro-preview` |
| Evidence inventory | `gemini-3.1-pro-preview` |
| Evidence-loss adjudication | `gpt-6.1-sol` |
| Common completion judge | `gpt-6.1-sol` |

## Record tasks

The task catalog is [data/tasks.jsonl](data/tasks.jsonl), with IDs `task_01` through `task_40`.
See the [task catalog](data/README.md) and the
[collection and evaluation sequence](docs/runbook_next.md).

Set `BENCH_TRIALS` to a positive integer. Without positional task IDs, the command
selects every task in the explicit local catalog. Each batch requires frozen
rubrics and the completion judge. After each adjacent actor pair, every run gets
common completion, both auxiliary verifiers and a within-run evidence-loss audit.
Returned completion/audit model IDs and complete responses are validated;
refusals remain ungraded with their usage retained. Native model mismatches and
DOM citation checks are diagnostics. Exhausted native scoring has null scores
with an explicit reason. See the [evaluation protocol](docs/evaluation-protocol.md)
for acceptance, repair budgets and coverage.

```sh
: "${BENCH_TRIALS:?Set a positive trial count per arm}"
./scripts/run-task \
  --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl \
  --output-dir recordings --run-name benchmark \
  --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol
```

Use `--dry-run` to write and inspect the schedule without starting tasks. A new
command reserves its output directory; name collisions choose the next numeric
suffix without overwriting prior runs. Add `--resume` and the printed run name
to continue an existing ledger; completed final attempts are retained. Technical failures receive at most one
fresh attempt; both attempts remain recorded.
Both actors of a task/trial run back to back, alternating which arm starts.

For a subset, add positional IDs such as `task_26 task_02 task_19 task_25`.
The launcher accepts any frozen local catalog and task IDs. The schedule binds
the selected definitions, rubric hashes, effective settings, browser source
provenance and output paths. Use a separate run name for a different task set or
configuration.

## Outputs

```text
recordings/benchmark/ledger.jsonl
recordings/benchmark/logs/attempt_000001.log
recordings/benchmark/trial_0001/dom/<task>/
recordings/benchmark/trial_0001/screenshot/<task>/
```

| Artifact | Contents |
|---|---|
| `ledger.jsonl` | Task, arm, trial, order, configuration, attempt history, final output path, technical outcome and grading outcome. |
| `task.json`, `manifest.json`, `final.json` | Task definition, controls, browser provenance, captured states, actions and actor outcome. |
| `decisions.jsonl` | One row per received actor response, including rejected proposals, malformed responses and termination. Transport attempts are counted separately. |
| `turns/turn_NNNNNN/` | Request, response and result, including usage, model ID, latency and output-limit status. Screenshot requests reference the saved image by path and SHA-256. |
| `cdp_calls.jsonl`, `agent_browser_calls.jsonl`, `browser_events.jsonl`, `failure_health.json`, `interruption.json` | Call timings, target/crash/detach/dialog events and available container diagnostics. |
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
The [effective settings contract](docs/evaluation-protocol.md#effective-settings-contract)
binds model routes, request limits, prompts, rubrics and browser source provenance;
credentials, ports, deployment names and file locations do not define that contract.

Actor and judge usage are reported separately. Cached-input and reasoning tokens
are subsets of provider totals. Incomplete recordings or missing usage produce
cost lower bounds; exact averages require complete coverage.

## Tests

```sh
.venv/bin/python -m pytest -q tests
```

Tests are grouped in `tests/actors`, `tests/capture`, `tests/scheduling`,
`tests/evaluation` and `tests/metrics`. Select one directory to run a division.
Shared fixtures live in `tests/conftest.py`; division fixtures live beside their
tests. Browser capture checks use the `live_browser` marker and require an
explicit `W8_CAPTURE_TEST_CDP`; the default suite stays offline.

The suite uses offline browser/model fixtures. The runbook includes a
[browser capture check](docs/runbook.md#tests) for scroll and focus preservation.
