# Runbook

Follow this guide to build the browser, record tasks and evaluate their paired
DOM/screenshot evidence. Use the [README](../README.md) for the project overview.

| Workflow | Sections |
| --- | --- |
| Record tasks | Requirements → Browser build → Get the benchmark and install Python → Create the local browser image → Environment configuration → Browser runtime → Record a task |
| Evaluate recordings | Requirements → Get the benchmark and install Python → Environment configuration → Recording and evaluation inputs → Score a prepared task |

## Requirements

Use 64-bit Linux or WSL 2, Git, Python 3.10 or higher, network access, and a Google
API key for paid model calls. Install Cairo with `sudo apt install libcairo2`.
Recording also requires Docker Engine with Compose and Buildx, `rsync`, about
32 GiB RAM and 200 GiB free disk space for Chromium. Keep the build on a Linux
filesystem; `/mnt/c` is slower and can cause filesystem compatibility problems.

## Browser build

### 1. Create the build workspace and install `depot_tools`

Create the workspace:

```bash
mkdir -p w8-browser-build
cd w8-browser-build
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$(pwd)/depot_tools:$PATH"
```

Run the `export` command from `w8-browser-build` in every build terminal.

### 2. Fetch Chromium

```bash
mkdir -p chromium
cd chromium
fetch --nohooks --no-history chromium
gclient sync --nohooks \
  --revision src@refs/tags/152.0.7948.0 \
  --reset --upstream -D --force --no-history --shallow
```

If interrupted, restore the `depot_tools` path and repeat `gclient sync` from
`chromium`. For an HTTP 429, allow a cooldown and retry with `--jobs=1`.

### 3. Apply the browser overlay

From `w8-browser-build/chromium`, return to the shared workspace, clone
Wootzapp Browser and copy its `src/` overlay:

```bash
cd ../..
git clone https://github.com/wootzapp/wootzapp-browser.git
sudo chmod -R u+w w8-browser-build/chromium/src
cp -r wootzapp-browser/src/. w8-browser-build/chromium/src/
```

### 4. Build Chromium

Compile the overlaid source:

```bash
(
  set -euo pipefail
  export PATH="$(pwd)/w8-browser-build/depot_tools:$PATH"
  cd w8-browser-build/chromium/src
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
)
```

Require a successful build. The shell stays in the shared workspace.

## Get the benchmark and install Python

From the directory containing `w8-browser-build`, or your chosen workspace for
evaluation-only use:

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

The wrappers use this checkout's `.venv/bin/python`. Installations include the
verifier integrity manifests; preflight verifies both packages and shared dependencies.

Install the Hugging Face CLI and download the catalog and frozen rubrics:

```bash
curl -LsSf https://hf.co/cli/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
hf download WootzappLab/browser-agent-tasks tasks.jsonl \
  --type dataset --revision paired-capture --local-dir data
hf download WootzappLab/browser-agent-tasks --include "rubrics/*.json" \
  --type dataset --revision paired-capture --local-dir data
```

The [dataset branch](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/paired-capture)
stores published data. The launcher fetches tasks from `TASK_CATALOG_URL` and
freezes the catalog once per batch. `--catalog-file` selects an explicit local
snapshot; the local `data/` copy serves offline checks and rubric preparation.

## Create the local browser image

From the benchmark repository, stage the Release runtime files and build the image:

```bash
(
  set -euo pipefail
  bench_repo="$(pwd)"
  bench_chromium_src="$bench_repo/../w8-browser-build/chromium/src"
  bench_overlay="$bench_repo/../wootzapp-browser"
  export PATH="$bench_repo/../w8-browser-build/depot_tools:$PATH"
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
)
```

The [build script](../scripts/build-browser-image) verifies the local source/protocol
[pins](../protocol/browser-build.json) and copied binary. It launches the staged
executable with a temporary profile and checks structured capture, model DOM and
screenshot capture on a local fixture before building the image. The image's
`browser-build.json` records the binary SHA-256 and capability result. The script
does not fetch or switch the overlay.
Set `.env`'s `IMAGE` to the built tag/digest, retain `SYS_NICE` in Compose, and keep
one browser build throughout the comparison.

## Environment configuration

Create the recording configuration from the repository root:

```bash
.venv/bin/python -m w8bench.task_recorder.browser_runtime configure
```

For evaluation without a browser:

```bash
[ -f .env ] || cp .env.example .env
```

Edit `.env`; keep keys out of terminal output and Git. Shell environment values
take precedence over `.env`, and conflicting actor models are rejected.

```text
GEMINI_API_KEY=your-google-api-key
ACTOR_MODEL=gemini-3.8-flash
NATIVE_JUDGE_PROFILE=primary
EVIDENCE_AUDIT_MODEL=gemini-3.1-pro-preview
EVIDENCE_ADJUDICATOR_MODEL=gemini-4-argon
TASK_CATALOG_URL=https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/resolve/paired-capture/tasks.jsonl
```

Models and judge endpoints are listed in the [datacard](datacard.md#judge-delivery)
and `config/`. Model stages use Google's GenerateContent API through direct requests.

| Setting | Purpose |
| --- | --- |
| `IMAGE` | Browser tag or digest |
| `COMPOSE_PROJECT_NAME`, `CONTAINER_NAME` | Isolated service identities |
| `CDP_HOST_PORT`, `NOVNC_HOST_PORT`, `VNC_HOST_PORT` | Browser-control and viewing ports |
| `CHROMIUM_HEADLESS` | Display mode |
| `CHROMIUM_RESET_PROFILE` | `1` clears browser history, cookies and storage at startup; host recordings are separate |
| `GEMINI_BASE_URL` | Actor and normal completion endpoint |
| `TASK_CATALOG_URL` | Hugging Face catalog source for task selection |
| `W8_RUN_NAME` | Default recording name |

Configure creates isolated service names and free ports, preferring CDP 49335,
noVNC 16191 and VNC 15911. Use its printed names and URLs.

## Browser runtime

Start and check the service:

```bash
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d --wait --force-recreate w8-core
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
docker compose --env-file .env ps
```

Require healthy status and `ChromiumRL: ready`. Runtime health and status check
the required ChromiumRL commands as well as CDP reachability. The launcher checks
Compose ownership and creates a fresh browser per attempt. Run one batch at a time without other
recordings or fixture checks on its browser; headless status skips noVNC.

## Record a task

Commands below use the repository root. Scheduled paired runs require frozen rubrics.
Diagnostics use `--execute` to submit provider requests; `--help` makes no browser
or provider calls.

### Check the configuration and schedule

```bash
.venv/bin/python scripts/check-configuration.py
```

This [local check](../scripts/check-configuration.py) validates settings, key presence,
catalog balance and package integrity without testing credit balance or provider access.
Check browser ownership and reachability:

```bash
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
```

Set `BENCH_TRIALS` to any positive integer and inspect the schedule:

```bash
: "${BENCH_TRIALS:?Set a positive integer trial count per arm}"
./scripts/run-task --trials "$BENCH_TRIALS" --catalog-file data/tasks.jsonl \
  --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name collection \
  --judge-model gemini-3.6-flash --dry-run
```

Use the printed run name, including any collision suffix. This command omits
`--rubric-dir`, so it writes a planning preview, not an executable ledger.
After freezing, the pilot/collection commands below supply `--rubric-dir` to create
`ledger.jsonl`. Inspect all `80 × k` rows, alternating order, paths and settings;
never rename `schedule_preview.jsonl` to `ledger.jsonl`.

Expiry uses the inclusive UTC date in `internal/task_validity.json`; an explicit
`--allow-expired` override must also be retained on resume. Broken-task replacements
need a readiness reason/receipt, never a poor score. **Model calls: 0.**

### Generate and review rubrics

The catalog's frozen rubrics are in `data/rubrics` and are reused for recording
and evaluation. Preparation requires an empty frozen-output directory. For a
separate rubric version, use separate draft and rubric directories consistently
in preparation, recording and evaluation commands.

The generator sends expanded task text and start URL to `gemini-3.1-pro-preview`,
using the native rubric and dependency prompts without actor results.
Start with the read-only preflight:

```bash
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage draft --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics
```

Generate rubric drafts:

```bash
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage draft --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Run one preparation command at a time; repeat it with matching tasks/settings to
resume, retaining prior usage. Authentication exhaustion leaves a partial catalog
and nonzero exit. Frozen versions refuse drafting; revisions need a distinct version.

Create the offline review file:

```bash
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage review --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Review coverage, constraints, observability, weights, overlap and run-time values in
`internal/rubrics/review.md`. Correct drafts without changing task identity/text/URL,
then regenerate the review; changed drafts lose approval. Generation uses
**80 nominal calls** before retries; review uses **0**. `task_XX.metrics.json`
retains usage and unknown costs.

### Approve and freeze rubrics

In `internal/rubrics/review.json`, fill `approved_by`, `approval_date` (`YYYY-MM-DD`)
and every task's `approved: true` and nonempty `review_notes`. Leave binding hashes intact.
Validate, then freeze offline:

```bash
.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage freeze --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics

.venv/bin/python -m w8bench.verifier.generate_frozen_rubric \
  --stage freeze --catalog-file data/tasks.jsonl \
  --draft-dir internal/rubrics/drafts --rubric-dir data/rubrics --execute
```

Require 40 valid rubrics. Freeze verifies bindings/weights and writes
`data/rubrics/task_XX.json` plus `internal/rubrics/freeze.json`; changed frozen files
are refused. Reuse them across arms, trials and judges. **Model calls: 0.**

### Recording controls

| Setting | Value |
| --- | --- |
| Actor | `gemini-3.8-flash`, MEDIUM thinking, temperature unset |
| Model turns | At most 200 |
| Output limit, including reasoning | Exactly 10,000 tokens |
| Memory | 8,000 characters |
| Viewport | 1365 × 768 CSS pixels, device pixel ratio 1 |
| Screenshot media | HIGH; 1,100-token local image allowance |
| Settle wait | 1 second |
| Stall matches | Private advisories; proposals are not rejected |

Keep controls equal; see [arm differences](datacard.md#observation-modes).
Screenshot coordinates are 0–1000 integers, converted once to CSS pixels.
Estimates above 50% input capacity trigger `countTokens` with a recorded fallback;
confirmed/estimated overflow above 95% stops technically without truncation.
Received responses count as turns; preflight/failed transport attempts do not.
[Recovery rules](datacard.md#browser-recovery) allow transient request retries and
one fresh technical rerun, without replaying actions. Website blocks, actor failures,
turn caps and provider auth/quota/billing do not trigger that rerun. Final-attempt
success/turns/tokens and earlier technical-attempt costs are reported separately.

### Check model compatibility

The compatibility check makes **7 nominal paid requests** covering both actors, native/rubric
transports, completion, inventory and adjudication:

```bash
.venv/bin/python scripts/check-model-compatibility.py --execute
```

Require permitted IDs, complete responses, valid schema/JSON and readable markers in
`internal/compatibility/check_NNNN/result.json`. Stop on mismatches/unsupported settings.
The native ID gate is stricter than production diagnostics; the pilot checks long-context fit.

### Browser coordinate calibration

Use an idle browser: the fixture opens a page and closes other task tabs.
This synthetic check makes **0 model calls**:

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

Require all six hits, matching viewport/image dimensions and DPR 1 in
`reports/browser_calibration/run_N/calibration.json`.
Test the real screenshot actor/executor (**6 responses**):

```bash
.venv/bin/python scripts/calibrate-coordinates.py --execute
```

Require six hits, valid coordinates/IDs and complete responses in
`internal/coordinate_calibration/check_NNNN/result.json`. The actor sees only its screenshot.

### Screenshot text calibration

With the browser idle, read fixture strings at 8, 10, 12 and 14 CSS pixels
using HIGH (**1 paid response**, no actor action executed):

```bash
.venv/bin/python scripts/calibrate-text.py --execute
```

Review accuracy, ID, completeness and HIGH in
`internal/screenshot_text_calibration/check_NNNN/result.json`; fixture accuracy does
not guarantee general legibility. All three diagnostics use **14 nominal requests**, before retries.

### Record the pilot

Use task_01 (easy), task_12 (medium), task_29 (hard) and task_35 (complex), both
arms, one trial each. Plan first:

```bash
./scripts/run-task task_01 task_12 task_29 task_35 --trials 1 \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gemini-3.6-flash --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name pilot --dry-run
```

Set `BENCH_PILOT_RUN` to the printed name, then execute and inspect:

```bash
: "${BENCH_PILOT_RUN:?Set the printed pilot run name}"
export BENCH_PILOT_RUN
./scripts/run-task task_01 task_12 task_29 task_35 --trials 1 \
  --rubric-dir data/rubrics \
  --judge-model gemini-3.6-flash --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name "$BENCH_PILOT_RUN" --resume

./scripts/run-comparison --ledger "recordings/$BENCH_PILOT_RUN/ledger.jsonl" \
  --output "reports/$BENCH_PILOT_RUN"
```

Each task/trial records both arms before completion, native verification and
inventory; formats are paired only within a run. The
[ledger evaluator](#controls-and-outputs) resumes evaluation, and loss decisions use
[final adjudication](#final-adjudication). The ledger contains eight scheduled rows,
with technical rerun attempts nested in each row. Per-run artifacts record
isolation, capture integrity, returned IDs, rubric bindings, grades, coverage
and costs. The pilot allows up to
1,600 final-attempt responses, another 1,600 for technical reruns and 9,600 transport
attempts; judge calls vary. Check [capture receipts](recordings.md#capture-intervals)
for readiness/paired coverage: both arms reuse the 90-second navigation bound,
and empty exports—including PDFs—remain valid paired observations with a screenshot.

### Record the collection

Use any positive `BENCH_TRIALS`; omit task selectors for all 40 tasks:

```bash
: "${BENCH_TRIALS:?Set a positive integer trial count per arm}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --catalog-file data/tasks.jsonl --rubric-dir data/rubrics \
  --judge-model gemini-3.6-flash --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name collection --dry-run
```

Set `BENCH_COLLECTION_RUN` to the printed name and execute its ledger:

```bash
: "${BENCH_COLLECTION_RUN:?Set the printed collection run name}"
./scripts/run-task --trials "$BENCH_TRIALS" \
  --rubric-dir data/rubrics \
  --judge-model gemini-3.6-flash --max-turns 200 --max-output-tokens 10000 \
  --output-dir recordings --run-name "$BENCH_COLLECTION_RUN" --resume
```

The ledger retains all `80 × k` rows and attempts, alternates arm order and continues
after individual errors. Reconcile every row and evaluation coverage. The response
budget is 16,000 × k for final attempts plus the same for technical reruns, with up
to 96,000 × k actor-generation transport attempts. Every final recording gets completion, native
verification and inventory with frozen rubrics. The [final adjudication command](#final-adjudication)
uses saved inventories; evidence and retries determine judge work.

### Resume a recording

Repeat execution with `--resume` and its printed name to retain completed attempts
and continue technical reruns. Catalog, trials, rubrics, settings and browser must
match. Use a separate purpose/sequence name for another plan, without dates/times.
Without `--resume`, collisions select a suffix. Interrupted attempts reconcile from
receipts; active recorders/launchers/judges must finish or stop first. Retry judging
[separately](#controls-and-outputs) without repeating actors or discarding receipts.

### Record one arm or a manual task

A single-task command selects one arm and keeps a local attempt ledger:

```bash
./scripts/run-task task_12 --observation-mode dom \
  --output-dir recordings --run-name single_task
```

Use `--observation-mode screenshot` for the other arm. Single tasks support
`--catalog-url` and non-reserving `--dry-run`. `--no-browser-start` marks the initial
attempt nonfresh; technical reruns start fresh. Manual tasks require instruction and URL:

```bash
./scripts/run-task local-check \
  --task "Inspect the page and report the requested visible values." \
  --start-url "https://example.com/" --observation-mode dom \
  --output-dir recordings --run-name manual_check
```

Human intervention is disabled. IDs select subsets of `task_01`–`task_40`; batches
use scheduled catalog text, frozen rubrics and the explicit judge shown above.

## Recording and evaluation inputs

Validate and stage same-run verifier inputs outside the immutable source tree:

```bash
.venv/bin/python -m w8bench.task_recorder.prepare_verifier_data \
  recordings/collection exported/collection
```

Add `--dry-run` to validate only. Exports retain task/arm/trial/hash identity, state
IDs, format gaps and `input_receipt.json`. Navigation states stay in verifiers but
not directional audits; empty exports stay valid. Follow [export rules](recordings.md#integrity-and-export)
for shared histories, URL checks and incomplete recordings. Never pair across runs.

## Score a prepared task

Evaluation uses finalized same-run evidence and frozen rubrics, without a browser:
common completion → both native verifiers → audit, with identity and validity-date bindings.

### Use your recordings

Set the recording path from its ledger row and the matching task ID. Preflight,
then execute or resume grading:

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

Without `--execute`, this makes no calls or writes. Completed bound stages are
reused; ungraded stages can retry with prior costs retained. The ledger evaluator
reconciles bound stage receipts without repeating actors. Keep evidence, settings
and receipts intact.

Primary `completion.json` uses paired screenshots/DOM. Optional
`--judge-evidence-policy actor_native` writes `completion_actor_native.json` separately.
Use matching primary policies; `--judge-profile primary` and `pro` have separate roots.
See [grading/repair rules](evaluation-protocol.md#completion-grading): completion/audit
refusals and exhausted judgments stay ungraded; native ID mismatches are diagnostic.

### Controls and outputs

The default `--stage evaluate` runs completion, both native verifiers and
inventory through direct requests. It returns **0** when inventory is ready with
`evaluation_outcome: awaiting_adjudication`. The launcher uses this stage.
Evaluation failures retain their status and usage in the ledger.

Set `BENCH_EVALUATION_RUN` to the saved pilot/collection name and preview selection:

```bash
: "${BENCH_EVALUATION_RUN:?Set the saved pilot or collection run name}"
.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_EVALUATION_RUN/ledger.jsonl"
```

Evaluate:

```bash
.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_EVALUATION_RUN/ledger.jsonl" --stage evaluate --execute
```

The [ledger evaluator](../scripts/evaluate-ledger.py) retains ledger order and
reconciles bound stage receipts. Completed stages are reused without repeating
actors; failed stages retain earlier usage when retried.

Preview and execute the Flash-Lite/Pro comparison on the saved pilot recordings:

```bash
: "${BENCH_PILOT_RUN:?Set the saved pilot run name}"
.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_PILOT_RUN/ledger.jsonl" --compare-profiles

.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_PILOT_RUN/ledger.jsonl" --compare-profiles --execute
```

`profile_comparison.json` reports agreement, both audits' screenshot-only subsets
and union/intersection, losses, costs and quality coverage; see [profile rules](evaluation-protocol.md#judge-delivery-and-profiles).
Completion is shared; native verifiers/audits repeat, actors/rubrics do not.
Primary and Pro results never mix in primary aggregation.

### Final adjudication

Run final adjudication after all scheduled actors and technical reruns finish.
The command checks the saved inventories before dispatch. It sends adjudication requests
only; saved completion, native-verifier and inventory results are reused.

```bash
: "${BENCH_EVALUATION_RUN:?Set the saved pilot or collection run name}"
.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_EVALUATION_RUN/ledger.jsonl" --stage adjudicate

.venv/bin/python scripts/evaluate-ledger.py \
  --ledger "recordings/$BENCH_EVALUATION_RUN/ledger.jsonl" --stage adjudicate --execute
```

`--compare-profiles` adjudicates both profiles' inventories and refreshes their
comparison. Final loss values appear only after accepted adjudication; unavailable
audits have no loss rate.

### Compare recorded runs

Aggregate locally (**0 model calls**):

```bash
: "${BENCH_COLLECTION_RUN:?Set the printed collection run name}"
./scripts/run-comparison --ledger "recordings/$BENCH_COLLECTION_RUN/ledger.jsonl" \
  --output "reports/$BENCH_COLLECTION_RUN"
```

Supported pass@k values follow the actual trial count; `--pass-k` restricts them.
All-trial reliability is separate. Every attempt/unmatched arm remains visible;
unknown/ungraded outcomes are distinct from failures. Fresh launcher provenance
is required unless an explicit `--allow-nonfresh` comparison is requested.

| Output | Location |
| --- | --- |
| Schedule, attempts, outcomes, logs and recording paths | `recordings/<run>/ledger.jsonl` |
| Actor turns, input/output tokens, cache/reasoning subsets and limit hits | Recording `decisions.jsonl`, `turns/turn_*/request.json`, `response.json`, `result.json` |
| Arm comparison tokens: actor plus matching native verifier | Per-run `arm_token_usage` and arm/category summaries; actor-only `token_usage` and `tokens_per_turn` remain separate |
| Transport failures, durations, parser stage and usage coverage | Per-turn transport receipts and raw responses |
| Paired artifacts, timing, hashes and capture gaps | `manifest.json`, `steps/step_*/capture.json`; see [recording files](recordings.md#run-level-artifacts) |
| Completion, native scores, validity, both audit directions and coverage | Ledger-linked `evaluation.json` and stage files, including `completion.json` and `evidence_audit.json` |
| Rubric preparation/approval | `internal/rubrics/drafts/task_XX.metrics.json`, `generation.json`, `review.json`, `freeze.json`; `data/rubrics/task_XX.json` |
| Pair/task results, pass@k, arm/difficulty metrics and costs | `reports/<run>/pairs.json`, `per_task.json`, `summary.json`, `report.md` |

Separate actor/judge and technical-attempt costs, plus all-attempt/successful-pair
costs. Unknown usage is not zero; cache/reasoning are subsets and per-turn means
use known-call denominators. Report both losses per run (four per task/trial) with
coverage. Preserve receipts; see [metrics](evaluation-protocol.md#measurements),
[pass@k](evaluation-protocol.md#repeated-trial-results) and [pricing](../w8bench/verifier/run_metrics.py).
Arm token comparison includes DOM actors plus DOM verification, or screenshot
actors plus screenshot verification. Both native formats still run for the
same-run audit. The opposite verifier and all other evaluation streams remain
visible as overhead, with all cost streams retained for full-experiment accounting; see the
[token accounting contract](evaluation-protocol.md#token-accounting).
USD figures are estimates, not invoices.

Publish finalized collections using the [data storage commands](../data/README.md#storage).

## View a remote browser

Run status on the server and note its noVNC port:

```bash
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
```

Forward it from your computer:

```bash
ssh -o ExitOnForwardFailure=yes -N -L 39084:127.0.0.1:16191 user@server
```

Replace `16191` with the printed server port and open:

```text
http://127.0.0.1:39084/vnc.html?resize=scale&autoconnect=1&path=websockify
```

If local port 39084 is occupied, use another port in both places. Viewing is for
observation; do not interact with a recording.

## Tests

Run all offline checks:

```bash
.venv/bin/python -m pytest -q tests
.venv/bin/python -m pip check
git diff --check
```

Recorder divisions:

```bash
.venv/bin/python -m pytest -q tests/actors tests/capture tests/scheduling
```

Verifier and reporting divisions:

```bash
.venv/bin/python -m pytest -q tests/evaluation tests/metrics
```

Offline tests mock model/browser/process calls; shared fixtures are in
`tests/conftest.py`. Browser tests require an idle isolated service:

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

This fixture closes other tabs and verifies scroll/focus preservation. The
[coordinate fixture](#browser-coordinate-calibration) has its own command.

## Runtime checks

Check status:

```bash
.venv/bin/python -m w8bench.task_recorder.browser_runtime status
docker compose --env-file .env ps
```

Refresh ports only after stopping this checkout:

```bash
docker compose --env-file .env down
.venv/bin/python -m w8bench.task_recorder.browser_runtime configure --refresh-ports
docker compose --env-file .env up -d --wait w8-core
```

For a missing image, follow [Create the local browser image](#create-the-local-browser-image).
Recompile Chromium when source/build settings change. For noVNC connection errors,
use the URL printed by status. Keep Compose ownership and `SYS_NICE`; changed
browser builds or effective settings require separate runs.
