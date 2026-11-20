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

Source and wheel distributions carry the `manifests/` resources used by verifier
preflight. Both native package checks cover their shared verifier dependencies.
The checkout supplies the catalog, configuration and Compose files.

Configure `.env` with the browser image, container identity, ports and model
settings. The default image is `w8-core:domdiff-bench`; prepare it using the
[browser image build](#browser-image-build) before starting the service.
The example environment names the Compose project `w8-recorder` and the
container `w8-core-browser-engine`. Compose derives its default network name
from the project name; no named volumes are configured.
To select available ports for an isolated installation:

```sh
.venv/bin/python -m w8bench.task_recorder.browser_runtime configure
```

Configuration prefers CDP 49335, noVNC 16191 and VNC 15911, selecting distinct
free ports when a preferred port is occupied. A new isolated environment uses
`w8-recorder-<checkout-id>` and `w8-core-browser-<checkout-id>` for its project
and container, with a numeric suffix if that container name is occupied.

Start and inspect the browser service:

```sh
docker compose --env-file .env up -d --wait w8-core
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
docker compose --env-file .env ps
```

Status checks the container, CDP, noVNC and bundled agent-browser and prints their
URLs. Default ports are CDP 49335, noVNC 16191 and VNC 15911. The task launcher
recreates its own service with a fresh profile for each attempt and checks Compose
ownership. Run one batch at a time and keep separate single-task commands off the
same browser while a batch is active.

Environment values take precedence over `.env`; conflicting actor-model values
are rejected. Set `GEMINI_API_KEY` and `OPENAI_API_KEY`; keep
`ACTOR_MODEL` consistent with `.env.example`. Pin the browser image by digest
for comparisons with a consistent build.

The actor configuration must name `gemini-3.8-flash`. Completion requires an
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
| `ACTOR_MEDIA_RESOLUTION` | Screenshot per-image resolution: `HIGH` by default or `ULTRA_HIGH`; recorded in the shared actor settings. |
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
output paths. Add positional catalog IDs such as `task_26 task_02 task_19 task_25` to
select a subset; omit them to select all tasks. `TASK_CATALOG_FILE` defaults to
`data/tasks.jsonl`, whose task IDs run from `task_01` through `task_40`.

With an executable ledger present, remove `--dry-run`, add `--resume`, and use
the printed run name to record. A planning-only preview cannot be executed with
`--resume`; start a new named run after frozen rubrics are available. Both actors of a task/trial run back to back, with
alternating first-arm order. Every batch requires `--rubric-dir` and an explicit
judge and performs full evaluation after both actors finish. Logs and technical
outcomes are recorded for every scheduled attempt, and the batch continues after
individual startup, recorder or grading errors.

## Resume

Add `--resume` to the execution command and use the existing ledger's run name.
Without `--resume`, a command creates a new run and reserves the next free
numeric name when the requested directory already exists. Use purpose and
sequence names such as `pilot_2`; date/time-stamped output names are rejected. The saved schedule
must match the requested
catalog, task definitions, trial count, rubric hashes, effective settings, browser
source provenance and output paths. Select a separate run name for a different
configuration. A missing ledger is an error with `--resume`; it does not silently
create another run.

Resume retains completed final attempts and continues unstarted work in order.
A technical failure permits one fresh browser attempt under the same task, arm
and trial, with both attempts retained. An orphaned started attempt is reconciled
from its final recording or interruption receipt; a pending rerun continues from
its recorded attempt number. Actor failures, website blocks, turn caps and
provider auth/quota/billing outcomes do not receive a technical rerun. Use the
standalone grader to retry grading without repeating actor execution.

Stale ownership markers are discarded without signalling unrelated processes.
Resume refuses reconciliation while a verified recorder or scheduled
launcher/judge is active; finish or stop that process first.

## Record one task

A single-task command selects one arm and keeps a local attempt ledger:

```sh
./scripts/run-task task_02 --observation-mode dom \
  --catalog-file data/tasks.jsonl \
  --output-dir recordings --run-name single_task
```

Use `--observation-mode screenshot` for the other arm. Manual tasks use both
`--task` and `--start-url`. A single task can use a remote `--catalog-url`;
batches require a frozen local catalog. A single-task `--dry-run` previews the
next free run name without reserving directories, creating a recording or
starting an attempt ledger.
The `--no-browser-start` option applies to the initial attempt only; a permitted
technical rerun always starts a fresh browser. Reusing a browser is recorded as
nonfresh. A zero task counter alone does not establish freshness.

| Actor setting | Default |
|---|---:|
| Model turns | 200 |
| Maximum output tokens, including reasoning | 10,000 |
| Task memory | 8,000 characters |
| Reasoning effort | `medium` |
| Viewport | 1365 × 768 CSS pixels |
| Settle wait | 1 second |

Actor requests leave temperature unset. `ACTOR_MEDIA_RESOLUTION` controls
per-image `HIGH` or `ULTRA_HIGH` processing, without changing viewport pixels.
Each actor generation request uses a local size estimate. Estimates above 50%
of the model input limit trigger `countTokens`, with transient transport retries.
An unavailable tokenizer falls back to the recorded local estimate. Confirmed or
estimated overflow above 95% ends technically without
truncation or generation; the receipt remains available.

The output limit is exactly 10,000;
turn budgets may be lower than 200 but cannot exceed it. Budgets and viewport
options must match across compared attempts. Model IDs, shared
settings and output-limit hits are recorded. Both actors receive the current URL;
the datacard defines the [arm differences](datacard.md#observation-modes).

Screenshot click and point-scroll coordinates are integers from 0 to 1000,
relative to the saved image dimensions. The executor converts them once to CSS
pixels, clamps the image edges to the viewport, and records both coordinate
forms. Images match the viewport dimensions at device pixel ratio 1. The
[compatibility gate](runbook_next.md#4-small-model-compatibility-gate) includes
fixture calibration before collection.

A model turn counts a received response. Failed transport attempts have separate
receipts, duration and usage coverage. Transient failures allow two further
requests after 2 and 8 seconds plus up to 0.5 seconds of jitter. Auth, quota,
billing and other non-retryable errors stop without those retries.

Read-only observation failures use a 3-second target liveness probe and at most
one session reattachment/retry. Uncertain action delivery is never replayed.
Browser, renderer, CDP/capture, reference-snapshot and recorder failures allow one
fresh attempt. The known browser `InspectorChromiumRLAgent::UnregisterAgent`
teardown assertion follows this policy. The final attempt supplies success,
turns and tokens; earlier technical-attempt costs stay separate.

## Evaluate a run

The primary judge receives screenshots plus `dom_model.txt` from the same run,
with its task, frozen criteria, action records, final answer and technical status.
Use the same rubric and judge settings across arms and trials.

```sh
.venv/bin/python -m w8bench.verifier.run_comparison \
  --run recordings/benchmark/trial_0001/dom/task_02 \
  --rubric data/rubrics/task_02.json \
  --judge-model gpt-6.1-sol --execute
```

The primary grade is saved in `completion.json`. Full evaluation stages both
formats from that run outside its immutable recording tree, imports its frozen
rubric, runs both verifiers, then audits their source evidence. Results bind task,
driver, trial, recording/rubric/source hashes and a frozen validity date.
Without `--execute`, the command inspects inputs without model calls or writes.
Completed bound stages are reusable; ungraded stages may be retried explicitly
with their failed-attempt usage retained. Completion has one request per grading
attempt, while inventory and adjudication each allow three validation attempts.
Returned completion/audit IDs must satisfy the shared case-sensitive
exact-or-numeric/date/version matcher and responses must be complete. Native
returned-ID mismatches are diagnostics. Invalid native earned points use the
existing repair budget; exhaustion writes null scores and a `judge_fallback`
reason. Ungraded audits have no pooled evidence-loss rate.

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
shared run controls must match. Comparisons require fresh launcher provenance
by default. `--allow-nonfresh` explicitly includes reused/raw sessions and records
that policy in the report; it does not label them fresh.
The [effective settings contract](evaluation-protocol.md#effective-settings-contract)
compares request behavior, prompt/schema versions, normalized configuration
content, rubric bindings and browser source provenance. Credentials, ports,
container/Compose and image names/tags, and file locations are excluded.

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
ssh -o ExitOnForwardFailure=yes -N -L 39084:127.0.0.1:16191 user@server
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
CHROMIUM_IMAGE_NAME=w8-core:domdiff-bench \
  ./scripts/build-browser-image "$bench_chromium_src" "$bench_overlay"
docker image inspect w8-core:domdiff-bench
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
W8_CAPTURE_TEST_CDP=http://127.0.0.1:49335 \
  .venv/bin/python -m pytest -q tests/capture -m live_browser
```

The first command uses offline fixtures. The second checks scroll/focus
preservation against a synthetic page without actor or judge calls. Use an idle
isolated browser: the capture check creates a task tab, closes stale task tabs
and writes the fixture page.

| Division | Offline tests |
| --- | --- |
| Actors | [Actor tests](../tests/actors/): action policy, isolated requests, model responses, limits, memory and loop accounting. |
| Browser and capture | [Capture tests](../tests/capture/): runtime, CDP, paired observations, renderers, input delivery, export and staging. |
| Scheduling | [Scheduling tests](../tests/scheduling/): catalog validity and expiry, ownership, ledger, trials, arm order, interruption and settings checks on resume. |
| Evaluation | [Evaluation tests](../tests/evaluation/): frozen rubric preparation, completion, both native verifiers, response acceptance, prompts and evidence-loss audit. |
| Metrics and reporting | [Metrics tests](../tests/metrics/): usage coverage, tokens per turn, pass@k, costs, aggregation, reports and diagnostics. |

Each division contains unit and integration cases. Fixtures used across divisions
live in `tests/conftest.py`; fixtures used by one division live in its own
`conftest.py`. Select a division directory to run its tests. Model responses,
browser transports and process execution are mocked in offline cases. The
`live_browser` capture case runs only when `W8_CAPTURE_TEST_CDP` is explicitly set.
