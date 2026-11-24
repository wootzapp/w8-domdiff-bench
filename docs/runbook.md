# Runbook

This is the detailed operational guide for `w8-domdiff-bench`. It contains the
commands for browser setup, task recording, verifier-input preparation, and
verifier scoring. The [README](../README.md) presents the benchmark;
this runbook contains the full setup and execution steps, artifact details,
and troubleshooting.



Two workflows are available:

1. **Recording** writes independent DOM and screenshot attempts under `recordings/`.
2. **Evaluation** grades each attempt’s paired evidence with frozen rubrics.

| What you want to do | Sections to follow |
| --- | --- |
| Record a task | Requirements → Browser build → Get the benchmark and install Python → Create the local browser image → Environment configuration → Browser runtime → Record a task |
| Score saved recordings | Requirements → Get the benchmark and install Python → Environment configuration → Recording and evaluation inputs → Score a prepared task |


## Requirements

Evaluation requires 64-bit Linux or WSL 2, Git, Python 3.10 or
higher, network access for dependencies and executed model calls, and Google and OpenAI API
keys for executed model calls.

PNG figure rendering and the full test suite also require Cairo. On Ubuntu or
WSL, install it with `sudo apt install libcairo2`.

Recording additionally requires Docker Engine with Compose and Buildx,
`rsync`, approximately 32 GiB of RAM, and about 200 GiB of free disk space
for Chromium.

Keep the workspace on a Linux filesystem. Chromium builds under `/mnt/c` are
considerably slower and can encounter filesystem compatibility problems.

## Browser build

### 1. Create the build workspace and install `depot_tools`

Create the browser build workspace:

```bash
mkdir -p w8-browser-build
cd w8-browser-build
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$PATH:$(pwd)/depot_tools"
```

Run the `export` command in every terminal used for the Chromium build.

### 2. Fetch Chromium

```bash
mkdir -p chromium
cd chromium
fetch --nohooks --no-history chromium
gclient sync --nohooks \
  --revision src@refs/tags/152.0.7948.0 \
  --reset --upstream -D --force --no-history --shallow
```

If the download is interrupted, restore
the `depot_tools` path, return to the `chromium` directory, and run the same
`gclient sync` command again.

### 3. Build the pinned Chromium revision

```bash
cd src
./build/install-build-deps.sh
gclient runhooks
gn gen out/Release --args='is_debug=false
is_component_build=false
symbol_level=0
blink_symbol_level=0
v8_symbol_level=0
proprietary_codecs=true
ffmpeg_branding="Chrome"'
autoninja -C out/Release chrome
./out/Release/chrome --version
```

Do not continue unless this build succeeds.

### 4. Apply the overlay and rebuild

After the first build, return to the directory containing `w8-browser-build`
and copy the local Wootzapp Browser source overlay into Chromium:

```bash
cd ../../..
cp -r wootzapp-browser/src/. w8-browser-build/chromium/src/
```

Only files below `wootzapp-browser/src/` are applied. The destination must be
writable by the build user. Use a clean overlay checkout matching the source
revision in `protocol/browser-build.json`. The image build verifies the checked-out
revision and applied files without fetching or switching the overlay checkout.

```bash
cd w8-browser-build/chromium
gclient runhooks
cd src
gn gen out/Release
autoninja -C out/Release chrome
./out/Release/chrome --version
cd ../../..
```

The existing `out/Release` directory retains the arguments from the first
build. The final command returns to the shared workspace.

## Get the benchmark and install Python

The browser-build flow returns to the shared workspace containing
`w8-browser-build`. Evaluation-only users can run the following commands from
the directory where they want to keep the benchmark:

```bash
git clone --branch paired-capture https://github.com/wootzapp/w8-domdiff-bench.git
cd w8-domdiff-bench
```

Create the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
.venv/bin/python -m pip install -e ".[test]"
```

The `scripts/` wrappers use this checkout's `.venv/bin/python`. Source and wheel
distributions include the verifier integrity `manifests/`; preflight checks
both native packages and their shared dependencies. The checkout supplies the
catalog, configuration and Compose files.

## Create the local browser image

Use [`scripts/build-browser-image`](../scripts/build-browser-image) to package a
compiled Chromium Release build with the Wootzapp source overlay. Source,
version and protocol pins are in
[`protocol/browser-build.json`](../protocol/browser-build.json). The script checks
the overlay revision, applied source files, Chromium version/protocol and copied
Release binary against the pinned SHA-256 before building the image with the
[`Dockerfile`](../Dockerfile). Overlay verification reads the local checkout;
no overlay revision is fetched from a remote. The build receipt records the binary
hash and source identities.

From the benchmark repository, stage the Release runtime dependencies and
package the image. `build/` contains the disposable runtime payload:

```bash
bench_repo="$(pwd)"
bench_chromium_src="$bench_repo/../w8-browser-build/chromium/src"
bench_overlay="$bench_repo/../wootzapp-browser"
rm -rf "$bench_repo/build"
mkdir "$bench_repo/build"
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
one browser build throughout the comparison. The browser service grants `SYS_NICE`
to the assertion-enabled build for renderer-priority changes during tab switching.
Keep `cap_add: [SYS_NICE]` in Compose when recreating the service.

## Environment configuration

For recording, create the browser configuration from the repository root:

```bash
.venv/bin/python -m w8bench.task_recorder.browser_runtime configure
```

For evaluation without a browser, create the environment file if absent:

```bash
[ -f .env ] || cp .env.example .env
```

Edit `.env`. Keep credentials out of terminal output and version control.
Environment values take precedence over `.env`; conflicting actor models are
rejected. Executed model calls use these settings:

```text
GEMINI_API_KEY=your-google-api-key
OPENAI_API_KEY=your-openai-api-key
ACTOR_MODEL=gemini-3.8-flash
JUDGE_TRANSPORT=batch
NATIVE_JUDGE_PROFILE=primary
EVIDENCE_AUDIT_MODEL=gemini-3.1-pro-preview
EVIDENCE_ADJUDICATOR_MODEL=gpt-6.1-sol
TASK_CATALOG_FILE=data/tasks.jsonl
```

| Stage | Model |
| --- | --- |
| Both actors | `gemini-3.8-flash` |
| Rubric generation and dependency check | `gemini-3.1-pro-preview` |
| Both native verifiers, every stage, primary profile | `gemini-3.5-flash-lite` |
| Both native verifiers, every stage, Pro profile | `gemini-3.1-pro-preview` |
| Paired completion and optional actor-native grade | `gemini-3.6-flash` |
| Audit inventory | `gemini-3.1-pro-preview` |
| Audit adjudication | `gpt-6.1-sol` |

Judge endpoint settings remain in `config/`. Google credentials serve actors,
rubric preparation, completion, native verifiers and inventory. OpenAI credentials
serve audit adjudication. Dependencies are installed above.

| Setting | Purpose |
| --- | --- |
| `IMAGE` | Browser image tag or digest. |
| `COMPOSE_PROJECT_NAME`, `CONTAINER_NAME` | Docker service identity. |
| `CDP_HOST_PORT`, `NOVNC_HOST_PORT`, `VNC_HOST_PORT` | Published browser-control and viewing ports. |
| `CHROMIUM_HEADLESS` | Browser display mode. |
| `CHROMIUM_RESET_PROFILE` | `1` clears history, cookies and site storage at startup; `0` preserves the profile. Host recordings are separate. |
| `GEMINI_BASE_URL`, `OPENAI_BASE_URL` | Actor/normal completion and adjudication endpoints respectively. Batch completion uses the default Google endpoint. |
| `W8_RUN_NAME` | Default run name. |

Configuration prefers CDP 49335, noVNC 16191 and VNC 15911, choosing distinct
free ports when needed. Isolated identities use `w8-recorder-<checkout-id>` and
`w8-core-browser-<checkout-id>`, with a numeric collision suffix. The example
configuration names project `w8-recorder` and container `w8-core-browser-engine`.
Compose derives its network name from the project; no named volumes are configured.

## Browser runtime

Start the browser and verify every runtime component:

```bash
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d --wait w8-core
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
docker compose --env-file .env ps
```

Status prints the noVNC URL and checks the container, CDP, browser version and
bundled agent-browser. Headless status skips noVNC. Keep `cap_add: [SYS_NICE]`
for renderer-priority changes in the assertion-enabled build. Verify ChromiumRL
capture commands before recording.

The launcher recreates its service with a fresh profile before each attempt and
checks Compose ownership. Run one batch at a time; keep single-task commands and
fixture checks off that browser while a batch is active.

## Record a task

Commands that generate responses, start recordings or load browser fixtures
require explicit approval. Run preflight first, approve the frozen rubrics and
compatibility checks, then complete the pilot before the full collection.
A dry command makes no model calls. Stop at a failed check and inspect its
receipts before continuing. Commands use the repository root unless stated.
The diagnostic scripts support `--help` without opening the browser or contacting
a provider. Paid diagnostics require `--execute` after approval.

### Check the configuration and schedule

Configure `.env` using `.env.example` and install the project dependencies. Keep
credentials out of terminal output and version control. Environment values take
precedence over `.env`.

```bash
.venv/bin/python scripts/check-configuration.py
```

The [configuration check](../scripts/check-configuration.py) validates settings,
credential presence, catalog balance and package integrity locally.

A requested output name already on disk selects the next available numeric
suffix. Read the printed schedule path and use its actual run name for later
commands.

This checks configured identities and credential presence, not provider access,
credit balance or model compatibility. It does not print keys or contact a provider.
Check browser ownership and reachability without running an actor:

```bash
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
```

Choose `BENCH_TRIALS` explicitly in your shell, then require it before planning:

```bash
: "${BENCH_TRIALS:?Set a positive integer trial count per arm}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name collection \
  --judge-model gemini-3.6-flash --dry-run
```

When any required frozen rubric is missing, this writes only
`recordings/collection/catalog.jsonl` and
`recordings/collection/schedule_preview.jsonl`. Inspect all `80 × k` task/arm/trial
rows, alternating arm order, intended output paths and controls. It is not the
executable attempt ledger. Rubric-free planning cannot start an actor or judge.
Execution requires approved frozen rubrics and creates `ledger.jsonl` separately.
When all frozen rubrics exist, `--dry-run` creates or validates the ordinary
`ledger.jsonl`. To execute that schedule, remove `--dry-run` and add `--resume`,
using the run name printed by the planning command. A planning-only preview is not an execution ledger; do not rename it to
`ledger.jsonl`. After rubric approval, create and inspect an executable dry
schedule. This guide keeps that schedule under a separate collection name.

Task validity is checked against `internal/task_validity.json` using the UTC date.
Expired tasks stop planning/execution unless the operator explicitly supplies
`--allow-expired`. That override is recorded; it is not a claim of verified
readiness. Keep the same override on a resumed command. A broken task is replaced
only under the documented readiness rules, with a reason and receipt, never
because its actor score is poor.

Do not continue until the catalog identities, credential presence, pinned
settings, browser status and schedule preview have passed inspection. **Model calls: 0.**

### Generate and review rubrics

Draft generation uses the existing screenshot verifier's rubric-generation and
dependency-check prompts, with `gemini-3.1-pro-preview`. It receives the expanded catalog task and
start URL, not an actor trajectory or result. The action-judge client is configured
but is not normally called by these two preparation stages. The native JSON output contract is `native-rubric-output-contract/v3`; output
settings and response-repair budgets follow the verifier.

First run the read-only preflight:

```bash
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage draft --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics
```

Then, after authorizing the paid preparation requests:

```bash
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage draft --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Run one rubric preparation command at a time. The same command resumes preparation: completed drafts are reused, and failed or
interrupted draft attempts retain their call/usage receipts before another
attempt is made. A changed catalog/task binding is rejected. Do not use a separate
directory to conceal earlier costs. Frozen rubrics prevent drafting into the same
version; choose a distinct version for a deliberate task/rubric revision.
Authentication exhaustion marks that task ungraded and continues other tasks.
The workflow reports `partial` and exits nonzero until every task has a completed
draft. Resume preserves the failed attempt's calls and usage. Effective request
settings must match on resume; credentials and configuration file locations do
not define that behavioral contract.

Prepare the offline review document:

```bash
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage review --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Review `internal/rubrics/review.md`, each draft and its expanded instruction.
The review also includes dependency-check responses, per-model generation usage,
receipt paths and an explicitly unknown USD cost until a trusted price
configuration is supplied. Check coverage, stopping conditions, forbidden actions, observability in either
arm, criterion overlap and weights. Mutable values must be judged using the
values observed during the run and an observation date, rather than a frozen
answer. Correct criteria in `internal/rubrics/drafts/task_*.json` if necessary,
then regenerate the review document. Keep task identity, expanded instruction and
start URL unchanged. A changed draft resets its approval; unchanged approvals
are retained and prior review versions are archived.

Do not continue until all 40 drafts are valid and every criterion has been reviewed. Generation
normally needs **80 logical calls**: two per task, before existing retries or
repair iterations. Review needs **0**. Actual calls, transport attempts and token
usage are in each `task_XX.metrics.json`, including prior attempts; unknown usage
is not a measured zero.

### Approve and freeze rubrics

Approval is an explicit review action. In `internal/rubrics/review.json`, fill
`approved_by` and `approval_date` (`YYYY-MM-DD`), and set every task's `approved`
to `true` with nonempty `review_notes` after checking its listed requirements.
Do not alter binding hashes or substitute criteria in the approval file.

Validate approval without writing, then freeze offline:

```bash
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage freeze --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics

.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage freeze --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Freeze checks catalog/task/draft hashes, approval and unscored positive criterion
weights. It writes one `data/rubrics/task_XX.json` per task, bound to the approval
file hash, and `internal/rubrics/freeze.json`. An identical repeat is harmless;
a changed existing frozen rubric is refused. Reuse the same frozen criteria and
weights across both arms, all trials and every grading stage.

Do not continue until all 40 frozen rubrics match the task definitions and the
approved review hash. **Model calls: 0.**

### Recording controls

| Actor setting | Default |
|---|---:|
| Model turns | 200 |
| Maximum output tokens, including reasoning | 10,000 |
| Task memory | 8,000 characters |
| Reasoning effort | `medium` |
| Viewport | 1365 × 768 CSS pixels |
| Settle wait | 1 second |

Actor requests leave temperature unset. The screenshot actor uses HIGH media
resolution without changing viewport pixels.
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
[compatibility gate](#check-model-compatibility) includes
fixture calibration before collection.

A model turn counts a received response. Failed transport attempts have separate
receipts, duration and usage coverage. Transient failures allow two further
requests after 2 and 8 seconds plus up to 0.5 seconds of jitter. Auth, quota,
billing and other non-retryable errors stop without those retries.

Read-only observation failures use a 3-second target liveness probe and at most
one session reattachment/retry. Uncertain action delivery is never replayed.
Browser, renderer, CDP/capture, reference-snapshot and recorder failures allow one
fresh attempt. The final attempt supplies success,
turns and tokens; earlier technical-attempt costs stay separate.

### Check model compatibility

This **paid** command dispatches seven nominal logical requests: two actor
requests, two native/rubric model transport probes, one completion request and
one request through each actual inventory/adjudication transport. It uses
`gemini-3.1-pro-preview`, `gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.8-flash` and `gpt-6.1-sol`, with a
PNG, strict actor/completion schemas and configured Gemini settings. The two
audit probes use their actual system prompts with a synthetic marker response.
These are transport compatibility diagnostics; the pilot exercises full native
stage and audit payloads. The transport check launches no browser or action.

```bash
.venv/bin/python scripts/check-model-compatibility.py --execute
```

The [transport check](../scripts/check-model-compatibility.py) constructs the
synthetic requests and writes the receipts described below.

Do not continue unless all seven checks pass with permitted returned IDs, complete
responses, valid schema/JSON and readable image markers. Inspect
`internal/compatibility/check_NNNN/result.json` and the actor requests/responses. Normally
**7 logical calls**; existing SDK/client retry policies can increase HTTP attempts.
Each native transport probe lists all default native stage roles for its model,
including both rubric preparation roles. Every role records and prints its
configured ID, returned ID and the shared matcher's `exact`, `suffix` or `refused`
form. Completion, inventory and adjudication have separate role receipts. Missing
or refused IDs block real runs. This gate deliberately requires a matching native
transport ID; production native mismatches remain diagnostic.
This checks small request compatibility, not long-context limits, real browser
control or the complete audit protocol. The pilot checks those integration paths.
Stop on a model mismatch, unsupported parameter, incomplete response or malformed
output and resolve the configuration rather than changing the benchmark silently.

### Browser coordinate calibration

With the browser running and no task active, run the local fixture check. It uses
synthetic coordinates and makes **0 model calls**:

```bash
W8_CALIBRATION_CDP_URL="$(.venv/bin/python - <<'PY'
import os
from pathlib import Path
from w8bench.task_recorder.runner import load_env
load_env(Path('.env'))
print('http://127.0.0.1:' + os.environ['CDP_HOST_PORT'])
PY
)" .venv/bin/python -m pytest -q -s tests/capture/test_evidence.py \
  -k normalized_coordinate_calibration_in_w8
```

The fixture checks four corners, a small button and scrolled content through the
real executor, plus image dimensions and device pixel ratio 1. Inspect
`reports/browser_calibration/run_N/calibration.json`; all six targets must be hit.
The check opens a fresh page and closes other task pages.

After approval for paid compatibility checks, use the same fixture for **6
screenshot-actor responses**. The fixture is staged as a temporary file inside the browser
container and deleted afterward. Its file URL does not expose the HTML source. It supplies no DOM or target boxes to the actor; target detection is used
only to score the click afterwards. Run this before the pilot, with no task active:

```bash
.venv/bin/python scripts/calibrate-coordinates.py --execute
```

The [coordinate check](../scripts/calibrate-coordinates.py) uses the saved fixture
image, real actor request path and browser executor.

Do not continue unless all six targets are hit with valid normalized coordinates,
permitted returned model IDs and complete responses. Review `internal/coordinate_calibration/check_NNNN/result.json`
and saved requests, responses and transport receipts. The transport gate plus
coordinate calibration makes **13 nominal model checks**; transient failures
can add transport attempts. Complete the text calibration below before the pilot.

### Screenshot text calibration

With no task active, the following **paid** diagnostic reads four high-contrast
strings at 8, 10, 12 and 14 CSS pixels. The screenshot actor uses HIGH and sends
one saved PNG for **1 nominal actor response**. The model
receives only the image and the reading instruction; expected strings are used
only to score its response. No returned browser action is executed.

```bash
.venv/bin/python scripts/calibrate-text.py --execute
```

The [text check](../scripts/calibrate-text.py) writes exact-match and character
accuracy results for each font size.

Do not continue unless responses are complete, returned IDs match, saved requests
use HIGH, and per-size exact-match and character accuracy have been reviewed.
Inspect `internal/screenshot_text_calibration/check_NNNN/result.json` and the
request/response. This measures fixture OCR, not general page legibility. The
screenshot actor uses HIGH. The seven transport checks, six coordinate checks
and one text check make **14 nominal model checks**, plus any transport retries.
Actor generation uses local input estimation. Cached model metadata sets the
limit; estimates above 50% trigger `countTokens` requests with transport
retries and a recorded local-estimate fallback. Preflight requests do not consume
actor model turns.

### Check Batch transport

Set `JUDGE_TRANSPORT=batch` and `NATIVE_JUDGE_PROFILE=primary` before scheduling.
The ledger binds these settings. Native judging uses `gemini-3.5-flash-lite`;
`pro` selects `gemini-3.1-pro-preview` with separate result folders. Actor
requests, their input preflight and rubric generation use normal transport.
Judging can take hours to days across dependent rounds. Exit code 75 means a
judge command is pending. Repeating the same command polls existing jobs and never
resubmits an answered or still-submitted item.

Inspect the synthetic batch smoke plan offline:

```bash
.venv/bin/python -m w8bench.verifier.batch smoke \
  --output-dir .runtime/judge_batch_smoke
```

Obtain explicit approval before submitting the smoke batches. **Model calls: 0 for
preflight; after approval, five tiny generation requests: four Google, one
OpenAI.** These cover Flash-Lite and Pro OpenAI-compatible native requests,
Google GenerateContent inventory/completion and OpenAI Chat
adjudication, including images, JSON output and the actual reasoning settings.
After approval, submit and repeat later to poll:

```bash
.venv/bin/python -m w8bench.verifier.batch smoke \
  --output-dir .runtime/judge_batch_smoke --execute || [ "$?" -eq 75 ]
```

Inspect `.runtime/judge_batch_smoke/smoke.json`, provider job IDs, returned model
IDs and usage before approving pilot judging. Cancellation is explicit:

```bash
.venv/bin/python -m w8bench.verifier.batch smoke \
  --output-dir .runtime/judge_batch_smoke --cancel --execute
```

### Record the pilot

The pilot uses `task_26` (easy), `task_02` (medium), `task_19` (hard) and
`task_25` (complex),
both arms, one trial each. It is separate from the full collection.

```bash
./scripts/run-task task_26 task_02 task_19 task_25 --trials 1 \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gemini-3.6-flash --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name pilot --dry-run
```

Set `BENCH_PILOT_RUN` to the run name printed above, such as `pilot` or
`pilot_2`, before executing its ledger:

```bash
: "${BENCH_PILOT_RUN:?Set the printed pilot run name}"
export BENCH_PILOT_RUN
./scripts/run-task task_26 task_02 task_19 task_25 --trials 1 \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gemini-3.6-flash --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name "$BENCH_PILOT_RUN" --resume

./scripts/run-comparison --ledger "recordings/$BENCH_PILOT_RUN/ledger.jsonl" \
  --output "reports/$BENCH_PILOT_RUN"
```

Each actor attempt receives a fresh browser profile. Both arms finish before
their full evaluation starts: paired completion, screenshot verifier, DOM verifier
and a within-run audit with inventory/adjudication. These compare saved formats
from the same actor run; they do not pair the DOM actor's evidence with the
screenshot actor's evidence. Passive capture failure is recorded separately.

Check `capture.json` for `paired-capture/v2`, private readiness timing/state,
MIME type and raw `dom_export.stats`. Empty exports, including PDF wrappers, have
`[No exportable DOM content]` in the saved DOM model and remain paired-complete
when the screenshot was captured. They are not passive failures. Both arms use
the existing 90-second CDP navigation timeout for DOMContentLoaded or
interactive/complete and two animation frames; expiry captures as-is.
Same-document updates do not repeat the wait; the settle interval is unchanged.
The normal completion, native-verifier and same-run audit commands include these
states under their existing integrity and navigation eligibility rules.

Do not continue unless eight scheduled rows have recorded final technical/evaluation outcomes;
inspect request isolation, capture hashes/timings, actor returned IDs, grading
coverage, frozen rubric identity, judge receipts and the report. Genuine task
failure is a result, not permission to rewrite a task. Resolve generic setup
faults before authorizing the full collection. The pilot permits at most
**1,600 final-attempt actor responses** (eight × 200), plus up to 1,600 responses
from prior technical attempts. Up to three transport attempts per response gives
a 9,600-attempt upper bound. Judge calls depend on states, criteria, selected
evidence and existing retries; do not budget them as one per task.
Aggregation itself uses **0 model calls**.

### Record the collection

Supply any positive `BENCH_TRIALS`; omit positional selectors to use all 40 tasks:

```bash
: "${BENCH_TRIALS:?Set a positive integer trial count per arm}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gemini-3.6-flash --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name collection --dry-run
```

Set `BENCH_COLLECTION_RUN` to the printed run name, then execute that ledger:

```bash
: "${BENCH_COLLECTION_RUN:?Set the printed collection run name}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gemini-3.6-flash --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name "$BENCH_COLLECTION_RUN" --resume
```

The executable ledger has `80 × k` task/arm/trial rows, retaining startup
failures and missing recordings. A row can have two actor attempts when its first
attempt is technical. Task/arm/trial order alternates which arm runs first.
Execution uses `--resume` and the existing ledger's printed run name; completed final attempts are
retained and pending technical reruns continue from their recorded attempt. The command rejects changed catalog, rubric,
effective settings, browser source provenance or task/trial identities. Do not change the trial count
under an existing run name. Use a separate collection name for a different plan.

Without `--resume`, a command creates a separate run; `--resume` requires an existing
execution-capable ledger.

Both actors for a task/trial finish their final attempts before their judges.
A technical failure permits one fresh attempt; success, turns and tokens use the
final attempt. Prior technical-attempt costs remain separate. Transient actor
requests allow two further transport attempts, which do not consume model turns
until a response arrives. Website blocks, actor failures, turn caps and provider
auth/quota/billing errors do not trigger a technical rerun. Technical outcomes and
completion grades remain separate. Inspect ledger and logs before repeating any
command; do not treat missing usage as free work or erase failed-attempt receipts.

Do not continue unless all `80 × k` ledger rows and their attempt histories are accounted for,
with evaluation coverage reported. Final attempts permit at most **16,000 × k
actor responses** (40 tasks × two arms × k × 200). Prior technical attempts can
add the same number; the transport-attempt upper bound is **96,000 × k**. Full
evaluation adds one primary completion request per final recording, variable
native-verifier calls, and variable inventory/
adjudication requests; existing retries can add transport attempts. Rubrics stay
fixed and are not regenerated during evaluation. Exact totals come from receipts,
not from multiplying task counts by an assumed fixed judge-call count.


### Resume a recording

Add `--resume` to the execution command and use its printed run name. Completed
final attempts remain in place; pending technical reruns continue under their
recorded attempt number. The catalog, task/trial identities, frozen rubrics,
effective settings, browser source provenance and output bindings must match.
A different plan uses a separate run name. Without `--resume`, collisions reserve
the next numeric suffix. Use purpose and sequence identifiers only.

An orphaned started attempt is reconciled from its final recording or interruption
receipt. Stale ownership markers are discarded without signalling unrelated
processes. Reconciliation refuses to proceed while a verified recorder or
scheduled launcher/judge is active; finish or stop that process first. Use the
standalone evaluator to retry grading without repeating actor execution.

### Record one arm or a manual task

A single-task command selects one arm and keeps a local attempt ledger:

```bash
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

Run a manual task with an explicit instruction and start URL:

```bash
./scripts/run-task local-check \
  --task "Inspect the page and report the requested visible values." \
  --start-url "https://example.com/" --observation-mode dom \
  --output-dir recordings --run-name manual_check
```

Viewing is for observation; human intervention remains disabled. Positional
catalog IDs select a subset; omit them to select all 40 tasks. Every executed batch
requires a local frozen catalog, `--rubric-dir` and an explicit completion judge.
The expanded task comes from the scheduled catalog. The batch continues after
individual startup, recorder or grading errors. The current catalog is
`data/tasks.jsonl`, with IDs `task_01` through `task_40`.

## Recording and evaluation inputs

The recorder output and verifier input are different contracts.

The [recording guide](recordings.md#locate-an-attempt) describes the ledger,
attempt directories and [state artifacts](recordings.md#state-artifacts).
Both arms privately save both formats; only DOM states include executable refs.
Normally N actions supply N+1 states, starting before the first action.

Validate and stage flat verifier inputs from the recording tree:

```bash
.venv/bin/python -m w8bench.task_recorder.prepare_verifier_data \
  recordings/collection exported/collection
```

Exports are partitioned by trial/run name, arm, task and recording hash, with
`data-ss` and `data-dom` projections from the same source. Missing states retain
their original IDs. Ref actions retain real references; shared histories omit
DOM descriptions and actor notes. Navigation states stay in both verifiers and
are excluded only from directional audit decisions.
Use an output directory outside the source tree. See the
[recording contract](recordings.md#integrity-and-export) for
validation and incomplete-recording behavior.

Each bound task folder contains `input_receipt.json` and flat `data-ss/<task-id>/`
and `data-dom/<task-id>/` projections. The
[export contract](recordings.md#integrity-and-export) describes their files.

Add `--dry-run` to validate without staging. Keep each run's formats together;
never pair screenshots from one recording with another recording's DOM. Empty
exports are not missing captures. Genuine gaps retain state IDs and coverage;
available states stay in their own verifier. Initial URL aliases are accepted
only under the protocol's scheme, port, path and query checks.

## Score a prepared task

Full evaluation stages inputs from a finalized recording, imports its approved
frozen rubric, runs paired completion and both native verifiers, then audits that
same run's formats. Evaluation does not require the browser container.

### Use your recordings

To evaluate a finalized recording or resume its grading without repeating actor
execution, use the recording path stored in its ledger row:

```bash
: "${BENCH_RECORDING:?Set one completed recording path from ledger.jsonl}"
: "${BENCH_TASK_ID:?Set its task_XX catalog identity}"
.venv/bin/python -m w8bench.verifier.run_comparison \
  --run "$BENCH_RECORDING" --rubric "data/rubrics/$BENCH_TASK_ID.json" \
  --judge-model gemini-3.6-flash

.venv/bin/python -m w8bench.verifier.run_comparison \
  --run "$BENCH_RECORDING" --rubric "data/rubrics/$BENCH_TASK_ID.json" \
  --judge-model gemini-3.6-flash --execute
```

The first command is a read-only evaluation preflight. The second reuses completed
bound stages and preserves prior failed/interrupted attempt receipts. Resume the
batch command afterward to reconcile its ledger evaluation status. Do not modify
saved evidence, requests, hashes or completion files to force a cache hit.
The primary judge receives screenshots plus `dom_model.txt` from the same run,
with its task, frozen criteria, action records, final answer and technical status.
Use the same rubric and judge settings across arms and trials.

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

Use `--judge-profile primary` for Flash-Lite or `--judge-profile pro` for Pro.
Both profiles apply identical native rules and use separate result locations.
Actors, actor preflight and rubric preparation remain normal.

### Controls and outputs

The standalone evaluator and smoke command return 75 while Batch work is
pending. The task launcher can return 0 with pending judging recorded as
`judge_exit_code: 75`, `evaluation_outcome: batch_pending` and
`grade_completed: false`. Inspect the ledger rather than treating launcher exit
0 as completed evaluation.

For full evaluation or resume, select finalized recordings from the saved
ledger. Set `BENCH_EVALUATION_RUN` to the actual pilot or collection run name.
Inspect the selection without dispatching requests:

```bash
: "${BENCH_EVALUATION_RUN:?Set the saved pilot or collection run name}"
.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_EVALUATION_RUN/ledger.jsonl"
```

After approval, evaluate or poll the same selection:

```bash
.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_EVALUATION_RUN/ledger.jsonl" --execute
```

Continue only with approved rubrics and finalized pilot or collection recordings. **Model calls:** every
ready request from the full pipelines. Polling an existing item does not
resubmit it; a repeated controller command can submit dependent stages or
budgeted repairs as they become ready. Invalid answers and failed/expired items retain the existing retry budgets.
The command groups recordings by their existing queue and returns 75 while
any group is pending. Retain each group and its first recording when polling; do
not merge or reorder groups containing submitted jobs. Repeat until completed,
then resume the launcher to reconcile ledger status and aggregate. Use `--judge-transport normal` only for a separate evaluation with
matching effective settings; it cannot silently resume Batch results.
The [ledger evaluator](../scripts/evaluate-ledger.py) preserves ledger order and
queue groups for both primary evaluation and profile comparison. An error or
cancellation exit is passed through without starting another group.

For the pilot judge comparison, add `--compare-profiles`. Without `--execute`,
the command checks inputs without model calls:

```bash
: "${BENCH_PILOT_RUN:?Set the saved pilot run name}"
.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_PILOT_RUN/ledger.jsonl" --compare-profiles

.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_PILOT_RUN/ledger.jsonl" --compare-profiles --execute
```

Obtain explicit approval before evaluating both judge profiles. **Model calls:** the primary
full evaluation plus the Pro native pipelines and their own inventory/adjudication
for every selected recording. Common completion is shared; no actor or rubric is
rerun. The printed `profile_comparison.json` path contains per-arm/per-format
criterion agreement, disagreements, agreement on each audit's screenshot-only
subset and their union/intersection, each arm's two directional losses and coverage,
and profile-specific usage/cost streams. Quality counts include ungraded native
results, observed repair events, explicit refusals, audits blocked by an unavailable
native verifier and runs without loss values.
Primary and Pro outputs are never mixed in the primary aggregate.

To cancel outstanding judging, use the selected recording paths and rubric with
`--cancel --execute`. The controller records cancellation before requesting it
from each provider and refuses late results. If submission acknowledgement was
lost, do not recreate the job: reconcile its actual provider job ID in the saved
`submission_uncertain` receipt first. Never delete that receipt to force a retry.

Cancel the evaluation queue selected by the first recording path:

```bash
: "${BENCH_RECORDING:?Set a finalized recording path}"
: "${BENCH_TASK_ID:?Set its task_XX catalog identity}"
.venv/bin/python -m w8bench.verifier.run_comparison \
  --run "$BENCH_RECORDING" --rubric "data/rubrics/$BENCH_TASK_ID.json" \
  --judge-model gemini-3.6-flash --judge-transport batch --cancel --execute
```

Cancellation returns 130 and applies to the entire shared Batch queue, including
other recordings and native profiles using that queue. The queue is rooted at
`runs[0].parent.parent/evaluations/batch_jobs`. A single selected recording does
not restrict cancellation to its own requests. The cancellation receipt prevents
late imports and further work through that queue. Do not delete requests,
responses, settings or cancellation receipts to force continuation.

### Batch job reconciliation

If submission acknowledgement is lost, inspect the saved job receipt:

```bash
: "${BENCH_BATCH_RECEIPT:?Set the submission_uncertain jobs/job_NNNNNN.json path}"
export BENCH_BATCH_RECEIPT
.venv/bin/python - <<'PY'
import json, os
from pathlib import Path
receipt = json.loads(Path(os.environ['BENCH_BATCH_RECEIPT']).read_text())
assert receipt['status'] == 'submission_uncertain' and not receipt.get('job_id')
fields = ('provider', 'endpoint', 'model', 'stage', 'input_file_id', 'input_sha256', 'job_id')
print(json.dumps({key: receipt.get(key) for key in fields}, indent=2))
PY
```

Match the actual provider job to the uploaded `input_file_id`, model and request
input before placing its identifier in that receipt's `job_id`. Leave other
fields intact, including `submission_uncertain`. There is no reconciliation CLI
flag. Repeat the original command; its poll verifies the provider input file
before advancing the saved job. If the job cannot be identified, stop and retain
the receipt. A replacement submission could charge twice. Do not erase a receipt
to force another submission. Pending exit 75 requires repeating the same command
and paths; it is not a task or grading failure. Ready requests share Batch rounds
while stage dependencies retain their order.

### Compare recorded runs

Aggregation is local and makes no model calls. Use the selected collection name:

```bash
: "${BENCH_COLLECTION_RUN:?Set the printed collection run name}"
./scripts/run-comparison --ledger "recordings/$BENCH_COLLECTION_RUN/ledger.jsonl" \
  --output "reports/$BENCH_COLLECTION_RUN"
```

By default the report calculates supported pass@k values from the actual trial
count. `--pass-k` can restrict the requested positive k values to those supported
for every retained task. All-trial success reliability is reported separately.

| Measurement or receipt | Location |
| --- | --- |
| Full denominator, ordering, technical/grade/evaluation outcomes, logs and recording paths | `recordings/<collection-run>/ledger.jsonl` |
| Actor response turns, rejected proposals, termination responses, input/output usage, cached/reasoning subsets and output-limit flags | Recording `decisions.jsonl`, `turns/turn_*/request.json`, `response.json`, `result.json` |
| Actor transport attempts, durations, statuses, parser stage and usage coverage | Per-turn transport receipts and raw failed responses |
| Earlier technical-attempt costs | `cost_streams["technical_attempts:actor"]` and retained ledger `attempts` |
| Current paired artifacts, capture ordering/timing, navigation flags, hashes and passive failures | Recording `manifest.json`, `steps/step_*/capture.json` and state files |
| Frozen task settings, actor returned model IDs, action counts and final technical status | Recording `task.json`, `manifest.json`, `final.json` |
| Independent paired completion and its judge usage | Shared `evaluations/common/.../completion.json` and profile `paired_completion.json` |
| Screenshot/DOM auxiliary scores, model-call/usage receipts, logs and validity diagnostics | The `evaluation.json` path in the ledger and its stage subdirectories |
| Two within-run loss directions per actor run, four loss values across arms per task/trial, recovery and coverage | Evaluation `evidence_audit.json`, linked from `evaluation.json` |
| Rubric-generation costs including prior attempts | `internal/rubrics/drafts/task_XX.metrics.json`; workflow `generation.json` |
| Approval binding and immutable shared rubrics | `internal/rubrics/review.json`, `freeze.json`, `data/rubrics/task_XX.json` |
| Cross-arm task/trial pairs and per-task criteria/pass@k | `reports/<collection-run>/pairs.json`, `per_task.json` |
| Aggregate turns/tokens, token-per-turn distributions, completion, pass@k, auxiliary scores, audit directions, cost streams and coverage by arm/difficulty | `reports/<collection-run>/summary.json` and `report.md` |

The report retains every scheduled attempt, identifies unmatched arms and keeps
uncertain/ungraded outcomes distinct from definitive failures. Comparison and
aggregation require fresh launcher provenance. Use `--allow-nonfresh` only for
an explicit comparison of raw/reused sessions; the report records the override
without changing their provenance. Report all-attempt
and successful-pair costs together. Input/output token-per-turn metrics have
separate known-call denominators; unknown input/output usage makes exact totals
or means unavailable rather than zero. Cached input and reasoning tokens are
subsets, not extra tokens added to input plus output. Price-derived USD values
are estimates at the recorded price schedule, not provider invoices.

Do not continue until identities and controls are consistent, every scheduled
attempt is accounted for, and cost, grade and audit coverage are explicit. **Model calls: 0.** Preserve the ledger,
recordings, evaluation receipts, frozen rubrics and private preparation receipts
needed to reproduce these counts.

Browser build, profile freshness, runtime, capture and grading controls must
match. The [effective settings contract](evaluation-protocol.md#effective-settings-contract)
records the comparison fields; credentials, ports, deployment names and file
locations do not define behavioural settings. Public-web changes and model
aliases remain sources of variation.

The [evaluation protocol](evaluation-protocol.md#repeated-trial-results) defines
pass@k and uncertain-grade bounds. Configured pricing is defined in
[run_metrics.py](../w8bench/verifier/run_metrics.py).

## View a remote browser

Run status on the server and note the noVNC port:

```bash
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
```

Forward that port from the local computer:

```bash
ssh -o ExitOnForwardFailure=yes -N -L 39084:127.0.0.1:16191 user@server
```

Replace `16191` with the port printed on the server. Open:

```text
http://127.0.0.1:39084/vnc.html?resize=scale&autoconnect=1&path=websockify
```

If local port `39084` is occupied, choose another local port in both places.
Viewing is for observation; do not interact with a benchmark recording.

## Tests

Run all offline tests:

```bash
.venv/bin/python -m pytest -q tests
.venv/bin/python -m pip check
git diff --check
```

Run only recorder tests:

```bash
.venv/bin/python -m pytest -q tests/actors tests/capture tests/scheduling
```

Run only verifier and reporting tests:

```bash
.venv/bin/python -m pytest -q tests/evaluation tests/metrics
```

The divisions cover action policy and request isolation; CDP, capture and
rendering; catalog, ledger and resume; rubric preparation and judging; and
accounting, aggregation and reports. Shared fixtures live in `tests/conftest.py`;
division fixtures live in their own `conftest.py`. Offline cases mock model
responses, browser transports and process execution.

Browser-dependent tests require an idle isolated service and an explicit CDP
endpoint. Do not point these checks at a browser recording a task:

```bash
W8_CAPTURE_TEST_CDP="$(.venv/bin/python - <<'PY'
import os
from pathlib import Path
from w8bench.task_recorder.runner import load_env
load_env(Path('.env'))
print('http://127.0.0.1:' + os.environ['CDP_HOST_PORT'])
PY
)" .venv/bin/python -m pytest -q tests/capture -m live_browser
```

This selects the conflict-free configured port. The check opens a fixture page,
closes other task tabs and verifies scroll/focus preservation without model calls.
The coordinate fixture command appears in
[Browser coordinate calibration](#browser-coordinate-calibration).

## Runtime checks

Check browser status:

```bash
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
docker compose --env-file .env ps
```

Choose ports only after stopping this checkout:

```bash
docker compose --env-file .env down
.venv/bin/python -m w8bench.task_recorder.browser_runtime configure --refresh-ports
docker compose --env-file .env up -d --wait w8-core
```

If Docker cannot find `w8-core:domdiff-bench`, repeat
[Create the local browser image](#create-the-local-browser-image). Rebuild the
patched browser first only when its source or build configuration changed.
If noVNC refuses the connection, use the port printed by status instead of a
saved URL. Preserve Compose ownership and keep `SYS_NICE` when recreating the
service. A changed build or effective configuration requires a separate run.
