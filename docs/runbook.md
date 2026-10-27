# Runbook

This is the detailed operational guide for `w8-domdiff-bench`. It contains the
commands for browser setup, task recording, prepared dataset retrieval, and
verifier scoring. The [README operating section](../README.md#run-the-benchmark)
contains the complete end-to-end flow; this runbook adds focused checks,
artifact details, and troubleshooting.

Two workflows are available:

1. **Recording** writes a raw browser run under `recordings/`.
2. **Evaluation** scores a prepared screenshot/DOM pair under `dataset/`.

| What you want to do | Sections to follow |
| --- | --- |
| Record a task | Requirements → Browser build → Get the benchmark and install Python → Create the local browser image → Environment configuration → Browser runtime → Record a task |
| Score a prepared task | Requirements → Get the benchmark and install Python → Environment configuration → Score a prepared task |

There is no direct raw-recording-to-scoring command. The repository does not
currently convert a raw recording into a prepared verifier pair. The exact
boundary is described in
[Recording and evaluation inputs](#recording-and-evaluation-inputs).

## Requirements

Prepared-pair evaluation requires 64-bit Linux or WSL 2, Git, Python 3.10 or
newer, network access for dependencies and prepared data, and an OpenAI API
key for executed model calls.

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

The first download can take more than an hour. If it is interrupted, restore
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

### 4. Fetch the Wootzapp Browser source overlay

After the first build, return to the directory containing
`w8-browser-build`, then clone the public browser repository:

```bash
cd ../../..
git clone https://github.com/wootzapp/wootzapp-browser.git
```

### 5. Apply the overlay and rebuild

Copy the maintained source overlay into Chromium:

```bash
sudo chmod -R u+w w8-browser-build/chromium/src
cp -r wootzapp-browser/src/. w8-browser-build/chromium/src/
```

Only files below `wootzapp-browser/src/` are applied.

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

The browser-build flow is now back in the shared workspace containing
`w8-browser-build`. Evaluation-only users can run the following commands from
the directory where they want to keep the benchmark:

```bash
git clone https://github.com/wootzapp/w8-domdiff-bench.git
cd w8-domdiff-bench
```

Create the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
```

The `scripts/` wrappers use this checkout's `.venv/bin/python`.

## Create the local browser image

From the benchmark repository, prepare the browser runtime payload:

```bash
rm -rf build
mkdir build
cd ../w8-browser-build/chromium/src
gn desc out/Release //chrome:chrome runtime_deps | \
  rsync -aR --files-from=- out/Release/ ../../../w8-domdiff-bench/build/
test -x ../../../w8-domdiff-bench/build/chrome
cd ../../../w8-domdiff-bench
```

Build and inspect the image:

```bash
IMAGE_VERSION=chromium-152.0.7948.0 ./scripts/build-browser-image
docker image inspect w8-core:domdiff-bench
```

The image remains in the local Docker engine after the terminal closes. It
only needs to be rebuilt when Chromium, the Wootzapp Browser overlay, or image
runtime files change.

## Environment configuration

If you will record tasks, create the browser configuration from the
repository root:

```bash
python -m w8bench.task_recorder.browser_runtime configure
```

If you only need verifier scoring, create the environment file without
starting the browser:

```bash
cp .env.example .env
```

Edit `.env`. `OPENAI_API_KEY` is required for executed recording and scoring.
`OPENAI_MODEL` is also required for recording:

```text
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-supported-model
```

## Browser runtime

Start the browser and verify every runtime component:

```bash
docker compose --env-file .env up -d --wait w8-core
python -m w8bench.task_recorder.browser_runtime status
```

The status command prints the noVNC URL and checks the container, CDP,
browser version, and bundled agent-browser version.

## Record a task

Run a catalog task:

```bash
mkdir -p recordings
./scripts/run-task task8 --output-dir recordings --no-human-intervention
```

Run a manual task:

```bash
./scripts/run-task local-check "Readable task name" \
  --task "Inspect the page and report the requested visible values." \
  --start-url "https://example.com/" \
  --output-dir recordings \
  --no-human-intervention
```

Omit `--no-human-intervention` only when an operator may solve a CAPTCHA or
similar challenge. Human intervention is not recorded as an agent action.

Each run receives a timestamped directory:

```text
recordings/<run-id>/
  task.json
  manifest.json
  decisions.jsonl
  final.json
  trajectory.jsonl
  web_surfer.log
  steps/
    step_001/
      dom.json
      dom_full.txt
      dom_model.json
      dom_model.txt
      screenshot.png
      agent_browser.txt
      agent_browser_actions.txt
      action.json
```

The first step is the initial state. Each later step is the state after an
executed action. The final step can have no `action.json`.

## Recording and evaluation inputs

The recorder output and verifier input are different contracts.

The recorder writes numbered step directories. The verifier expects a paired
task bundle:

```text
dataset/
  data-ss/task_01/
    task_data.json
    final_answer.json
    web_surfer.log
    screenshot0.png
    screenshot1.png
  data-dom/task_01/
    task_data.json
    final_answer.json
    web_surfer.log
    dom_model0.txt
    dom_model1.txt
```

Both sides must contain the same task, action history, and final answer. The
state count must be the executed action count plus one.

The supported scoring command obtains these prepared pairs from the hosted
dataset. A raw directory under `recordings/` cannot be passed directly to
`run-comparison`. Preparing and publishing a newly recorded run is a separate
dataset-production operation and is not implemented by a public command in
this repository.

## Score a prepared task

Download and validate one prepared pair without making model calls:

```bash
./scripts/run-comparison --task task_01
```

Run rubric generation, both verifiers, and the evidence audit:

```bash
./scripts/run-comparison --task task_01 --execute
```

The executed command performs this sequence:

1. Load the paired task and verify its common files.
2. Generate or import one rubric.
3. Validate and freeze the rubric.
4. Score screenshot evidence.
5. Score DOM-model evidence with the same rubric and controls.
6. Normalize the two results.
7. Audit missing source evidence.

Results are stored under:

```text
evaluation/task_01/<run-id>/
```

Run all available prepared tasks with:

```bash
./scripts/run-comparison --all --execute
```

`run-comparison` downloads the selected prepared pair or pairs before
validation. Use `./scripts/dataset-sync fetch --task task_01` only when you
want to download a pair without running the comparison preflight.

## View a remote browser

Run the status command on the server and note the noVNC port:

```bash
python -m w8bench.task_recorder.browser_runtime status
```

Forward that port from the local computer:

```bash
ssh -o ExitOnForwardFailure=yes -N -L 39084:127.0.0.1:16191 ubuntu@your-server-address
```

Replace `16191` with the port printed on the server. Open:

```text
http://127.0.0.1:39084/vnc.html?resize=scale&autoconnect=1&path=websockify
```

If local port `39084` is occupied, choose another local port in both places.

## Tests

Run all offline tests:

```bash
python -m pytest
```

Run only recorder tests:

```bash
python -m pytest tests/task_recorder
```

Run only verifier tests:

```bash
python -m pytest tests/dom_model tests/screenshot_verifier tests/verifier
```

Browser-dependent tests require a disposable browser and an explicit CDP
endpoint:

```bash
EVIDENCE_TEST_CDP_URL="http://127.0.0.1:$(sed -n 's/^CDP_HOST_PORT=//p' .env)" \
  python -m pytest tests/task_recorder/test_browser_evidence.py
```

This reads the conflict-free host CDP port chosen during configuration. Do
not point these tests at a browser that is recording a task.

## Runtime checks

Check browser status:

```bash
python -m w8bench.task_recorder.browser_runtime status
docker compose --env-file .env ps
```

Choose new ports only after stopping this checkout:

```bash
docker compose --env-file .env down
python -m w8bench.task_recorder.browser_runtime configure --refresh-ports
docker compose --env-file .env up -d --wait w8-core
```

If Docker cannot find `w8-core:domdiff-bench`, repeat
[Create the local browser image](#create-the-local-browser-image). Rebuild the
patched browser first only when its source or build configuration changed. If
noVNC refuses the connection, use the current port printed by the status
command instead of a saved URL.
