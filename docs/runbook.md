# w8-domdiff-bench runbook

Use the [datacard](datacard.md) for observation policies and shared settings,
the [evaluation protocol](evaluation-protocol.md) for grading and metrics, and
the [recording contract](recordings.md) for file definitions.
The [collection and evaluation sequence](runbook_next.md) covers preparation,
rubric approval, compatibility checks, collection and aggregation in order.

## Browser runtime

Install the package into `.venv` as shown in [README](../README.md#setup).
Commands run from the repository root; the script wrappers use `.venv/bin/python`.
The runtime requires Linux or WSL 2 and Docker Engine with Compose.

Configure `.env` with the browser image, container identity, ports and model
settings. To select available ports for an isolated installation:

```sh
.venv/bin/python -m w8bench.task_recorder.browser_runtime configure
```

Start and inspect the browser service:

```sh
docker compose --env-file .env up -d --wait w8-core
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
docker compose --env-file .env ps
```

Status checks the container, CDP, noVNC and bundled agent-browser and prints their
URLs. Default ports are CDP 49345, noVNC 16291 and VNC 16011. The task launcher
recreates its own service with a fresh profile for each attempt and checks Compose
ownership. Run one batch at a time and keep separate single-task commands off the
same browser while a batch is active.

Environment values take precedence over `.env`; conflicting actor-model values
are rejected. Set `GEMINI_API_KEY` and `OPENAI_API_KEY`; keep
`ACTOR_MODEL` consistent with `.env.example`. Pin the browser image by digest
for comparisons with a consistent build.

The actor configuration must name `gemini-3.1-pro-preview`. Completion requires an
explicit `--judge-model gpt-6.1-sol`. Configure
`EVIDENCE_AUDIT_MODEL=gemini-3.1-pro-preview` and
`EVIDENCE_ADJUDICATOR_MODEL=gpt-6.1-sol` for full evaluation.

| Setting | Purpose |
| --- | --- |
| `IMAGE` | Browser image tag or digest. |
| `COMPOSE_PROJECT_NAME`, `CONTAINER_NAME` | Docker service identity. |
| `CDP_HOST_PORT`, `NOVNC_HOST_PORT`, `VNC_HOST_PORT` | Published browser-control and viewing ports. |
| `CHROMIUM_HEADLESS` | Browser display mode. |
| `CHROMIUM_RESET_PROFILE` | `1` clears the Chromium profile at startup; `0` preserves it. Browser history, cookies and site storage belong to this profile. Host-side recordings are separate. |
| `ACTOR_MODEL`, `GEMINI_API_KEY`, `GEMINI_BASE_URL` | Actor model, Google credentials and endpoint. The key also serves the verifier and inventory stages. |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | OpenAI credentials and endpoint for rubric preparation, completion and evidence-loss adjudication. |
| `EVIDENCE_AUDIT_MODEL`, `EVIDENCE_ADJUDICATOR_MODEL` | Explicit inventory and adjudication models. |
| `TASK_CATALOG_FILE` | Default local task catalog. |
| `W8_RUN_NAME` | Default output run name. |

## Record a batch

Choose the local catalog, selected tasks, positive trial count and task-specific
rubrics. Rubrics must match the expanded task instruction and start URL and stay
fixed across arms and trials.

```sh
: "${BENCH_TRIALS:?Set a positive trial count per arm}"
./scripts/run-task \
  --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl \
  --output-dir recordings --run-name benchmark \
  --rubric-dir data/rubrics \
  --judge-model gpt-6.1-sol --dry-run
```

With all frozen rubrics present, this writes `recordings/benchmark/ledger.jsonl`
without starting actors or judges. Otherwise, it writes a planning-only
`schedule_preview.jsonl`; execution remains blocked until rubrics are frozen.
Inspect task identities, trial count, arm order, configuration, rubric paths and
output paths. Add positional catalog IDs such as `task_08 task_12 task_23` to
select a subset; omit them to select all tasks. `TASK_CATALOG_FILE` defaults to
`data/tasks.jsonl`, whose task IDs run from `task_01` through `task_25`.

Remove `--dry-run` to record. Both actors of a task/trial run back to back, with
alternating first-arm order. Every batch requires `--rubric-dir` and an explicit
judge and performs full evaluation after both actors finish. Logs and technical
outcomes are recorded for every scheduled attempt, and the batch continues after
individual startup, recorder or grading errors.

## Resume

Repeat the same command and run name. The saved schedule must match the requested
catalog, task definitions, trial count, rubric hashes, model settings, recorder
source and output paths. Select a distinct run name for a different configuration.

Resume retains completed actor attempts, including failures, and continues
unstarted work in order. An orphaned started attempt is reconciled from its final
recording or marked interrupted. Completed attempts are not retried under the
same trial identity or copied into automatic `-2` directories. Use the standalone
grader to retry grading without repeating actor execution.

Stale ownership markers are discarded without signalling unrelated processes.
Resume refuses reconciliation while a verified recorder or scheduled
launcher/judge is active; finish or stop that process first.

## Record one task

A single-task command selects one arm and writes a recording without a batch
ledger:

```sh
./scripts/run-task task_08 --observation-mode dom \
  --catalog-file data/tasks.jsonl \
  --output-dir recordings --run-name single_task
```

Use `--observation-mode screenshot` for the other arm. Manual tasks use both
`--task` and `--start-url`. A single task can use a remote `--catalog-url`;
batches require a frozen local catalog. `--dry-run` validates a single task
without creating its recording.

| Actor setting | Default |
|---|---:|
| Model turns | 200 |
| Maximum output tokens, including reasoning | 10,000 |
| Task memory | 8,000 characters |
| Reasoning effort | `medium` |
| Viewport | 1365 × 768 CSS pixels |
| Settle wait | 1 second |

Actor requests leave temperature unset. The output limit is exactly 10,000;
turn budgets may be lower than 200 but cannot exceed it. Budgets and viewport
options must match across compared attempts. Model IDs, shared
settings and output-limit hits are recorded. Both actors receive the current URL;
the datacard defines the [arm differences](datacard.md#observation-modes).

## Evaluate a run

The primary judge receives screenshots plus `dom_model.txt` from the same run,
with its task, frozen criteria, action records, final answer and technical status.
Use the same rubric and judge settings across arms and trials.

```sh
.venv/bin/python -m w8bench.verifier.run_comparison \
  --run recordings/benchmark/trial_0001/dom/task_08 \
  --rubric data/rubrics/task_08.json \
  --judge-model gpt-6.1-sol --execute
```

The primary grade is saved in `completion.json`. Full evaluation stages both
formats from that run outside its immutable recording tree, imports its frozen
rubric, runs both verifiers, then audits their source evidence. Results bind task,
driver, trial, recording/rubric/source hashes and a frozen validity date.
Without `--execute`, the command inspects inputs without model calls or writes.

Add `--judge-evidence-policy actor_native` to request a secondary grade in
`completion_actor_native.json`. This policy uses the actor's observation format
and leaves the primary grade intact. Primary comparisons require matching grade
policies. Uncertain and ungraded results stay separate from confirmed failures;
judge usage stays separate from actor usage.

## Compare results

```sh
./scripts/run-comparison \
  --ledger recordings/benchmark/ledger.jsonl \
  --output reports/benchmark
```

The ledger supplies the denominator, including attempts without recordings.
Reports show technical outcomes, independent completion, grading coverage,
unmatched arms, actor turns, action attempts, output-limit hits and token usage.
Browser builds, profile freshness, runtime environments, capture policies and
shared run controls must match.

Partial recordings retain recoverable usage as lower bounds. Missing usage is
unknown cost; exact all-attempt means and medians require complete coverage.
Startup failures with no actor request and unstarted schedule rows are reported
separately. Success-conditioned costs and same-task/trial successful-pair deltas
are reported alongside all-attempt costs.

For n scheduled trials, c confirmed successes and `1 <= k <= n`:

```text
pass@k = 1 - C(n-c, k) / C(n, k)
```

The numerator is zero when `n-c < k`. Unknown grades give lower and upper bounds
using c and c+u. Results are averaged over the same scheduled tasks. All-trials
success reliability is a separate measure. Public-web changes and model aliases
remain sources of variation between attempts.

## Export recordings

Validate and stage flat verifier inputs from the recording tree:

```sh
.venv/bin/python -m w8bench.task_recorder.prepare_verifier_data \
  recordings/benchmark exported/benchmark
```

Exports are partitioned by trial/run name, arm, task and recording hash, with
`data-ss` and `data-dom` projections from the same source. Missing states retain
their original IDs. Ref actions retain real references; shared histories omit
DOM descriptions and actor notes. Navigation states stay in both verifiers and
are excluded only from directional audit decisions.
Use an output directory outside the source tree. See the
[recording contract](recordings.md#integrity-and-export) for
validation and incomplete-recording behavior.

## View a remote browser

Run browser status on the server and use the printed noVNC port. Forward that
port from the local computer:

```sh
ssh -o ExitOnForwardFailure=yes -N -L 39084:127.0.0.1:16291 user@server
```

Open `http://127.0.0.1:39084/vnc.html?resize=scale&autoconnect=1&path=websockify`
locally. Adjust the remote port to match status and select a free local port.
Viewing is for observation; benchmark runs do not permit human interaction.

## Browser image build

Use [`scripts/build-browser-image`](../scripts/build-browser-image) to package a
compiled Chromium Release build with the Wootzapp source overlay. Source,
version and protocol pins are in
[`protocol/browser-build.json`](../protocol/browser-build.json). The script checks
the overlay revision, applied source files, Chromium version/protocol and copied
Release binary before building the image with the [`Dockerfile`](../Dockerfile).

With the patched Release build prepared, stage its runtime dependencies into an
empty `build/` directory and package it:

```sh
bench_repo="$(pwd)"
bench_chromium_src=/path/to/chromium/src
bench_overlay=/path/to/wootzapp-browser
mkdir -p "$bench_repo/build"
(
  cd "$bench_chromium_src"
  gn desc out/Release //chrome:chrome runtime_deps | \
    rsync -aR --files-from=- out/Release/ "$bench_repo/build/"
)
test -x "$bench_repo/build/chrome"
CHROMIUM_IMAGE_NAME=w8-core:paired-capture \
  ./scripts/build-browser-image "$bench_chromium_src" "$bench_overlay"
docker image inspect w8-core:paired-capture
```

This path requires the compiled source workspace, `gn`, `rsync` and Docker
Buildx. The script writes `build/browser-build.json` and browser source labels.
Its `VCS_REF` label describes Git HEAD; run manifests separately record the
recorder source hash.

Set `IMAGE` in `.env` to the resulting tag or digest before scheduling tasks.
Verify browser status and the required ChromiumRL capture commands, and keep
one browser build throughout the comparison.

## Tests

```sh
.venv/bin/python -m pytest -q tests
W8_CAPTURE_TEST_CDP=http://127.0.0.1:49345 \
  .venv/bin/python -m pytest -q tests/turn_benchmark -k live_capture
```

The first command uses offline fixtures. The second checks scroll/focus
preservation against a synthetic page without actor or judge calls. Use an idle
isolated browser: the capture check creates a task tab, closes stale task tabs
and writes the fixture page.
