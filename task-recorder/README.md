# w8-core Browser Harness

This harness runs model-directed tasks in w8-core. It records each page state
once and lets you watch the live w8-core window through noVNC.

## Browser Setup

### Requirements

- A 64-bit Linux system, or WSL 2 on Windows.
- At least 32 GiB RAM and 200 GiB free disk space.
- Git, Python 3, `rsync`, Docker Engine, Docker Compose, and Docker Buildx.
- Network access to the public desktop `wootzapp/wootzapp-browser` repository.
- Python 3 with virtual environments.
- An OpenAI API key and supported model.
- At least 2 GiB shared memory for w8-core.

The model runner stays on the host. w8-core, ChromiumRL, agent-browser, VNC,
and noVNC run in Docker.

### 1. Clone This Repository

```bash
git clone https://github.com/wootzapp/w8-domdiff-bench.git
cd w8-domdiff-bench/task-recorder
export W8_RECORDER_ROOT="$PWD"
```

On WSL, keep the Chromium workspace in the Linux home directory rather than
under `/mnt/c`.

### 2. Fetch and Build Official Chromium

Install Chromium `depot_tools`:

```bash
export W8_BUILD_ROOT="$HOME/w8-browser-build"
mkdir -p "$W8_BUILD_ROOT"
cd "$W8_BUILD_ROOT"
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$W8_BUILD_ROOT/depot_tools:$PATH"
```

Fetch and pin the official desktop Chromium source:

```bash
mkdir -p "$W8_BUILD_ROOT/chromium"
cd "$W8_BUILD_ROOT/chromium"
fetch --nohooks --no-history chromium
gclient sync --nohooks \
  --revision src@refs/tags/152.0.7948.0 \
  --reset --upstream -D --force --no-history --shallow
```

Install Chromium's Linux dependencies and run its hooks:

```bash
cd "$W8_BUILD_ROOT/chromium/src"
./build/install-build-deps.sh
gclient runhooks
```

Configure the Release build. The arguments remain visible so they can be
reviewed and reproduced:

```bash
cd "$W8_BUILD_ROOT/chromium/src"
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

This first build contains official Chromium only. Do not continue if it fails.
If you open a new terminal, export `W8_RECORDER_ROOT`, `W8_BUILD_ROOT`, and
`PATH` again.

### 3. Apply the w8-core Desktop Modifications

Clone the public desktop repository:

```bash
git clone --depth 1 \
  https://github.com/wootzapp/wootzapp-browser.git \
  "$W8_BUILD_ROOT/wootzapp-browser"
```

Copy its patch over the official Chromium checkout:

```bash
rsync -a \
  "$W8_BUILD_ROOT/wootzapp-browser/chromium-patch/src/" \
  "$W8_BUILD_ROOT/chromium/src/"
```

The separate `chromium-desktop/` directory is not used as the build source.
Only `chromium-patch/src/` changes the official checkout.

### 4. Rebuild w8-core and Create the Docker Image

Run the hooks and build the patched source:

```bash
cd "$W8_BUILD_ROOT/chromium/src"
gclient runhooks
gn gen out/Release
autoninja -C out/Release chrome
./out/Release/chrome --version
```

The second build reuses the GN arguments already stored in `out/Release`.

Copy the patched runtime into the desktop repository's Docker context:

```bash
export W8_IMAGE_ROOT="$W8_BUILD_ROOT/wootzapp-browser/chromium-image-docker"
rm -rf -- "$W8_IMAGE_ROOT/build"
mkdir -p "$W8_IMAGE_ROOT/build"
cd "$W8_BUILD_ROOT/chromium/src"
gn desc out/Release //chrome:chrome runtime_deps | \
  rsync -aR --files-from=- out/Release/ "$W8_IMAGE_ROOT/build/"
test -x "$W8_IMAGE_ROOT/build/chrome"
```

Build the local image with the desktop repository's existing Docker script:

```bash
cd "$W8_IMAGE_ROOT"
CHROMIUM_IMAGE_NAME=w8-core:domdiff-bench \
IMAGE_VERSION=chromium-152.0.7948.0 \
IMAGE_VCS_REF="$(git -C "$W8_BUILD_ROOT/wootzapp-browser" rev-parse HEAD)" \
  ./scripts/build_image.sh
docker image inspect w8-core:domdiff-bench
```

The result is a local `w8-core:domdiff-bench` image. Compose is configured not
to pull a hosted substitute.

### 5. Set Up the Task Recorder

Install the recorder dependencies:

```bash
cd "$W8_RECORDER_ROOT"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, run the harness in WSL with Docker access. The later SSH command
also works directly in PowerShell.

Create an isolated `.env` with unused local ports:

```bash
python3 browser_runtime.py configure
```

This creates a private `.env`. It:

- gives this checkout unique Docker names;
- selects available CDP, noVNC, and VNC ports;
- binds those ports to `127.0.0.1`;
- never overwrites an existing `.env`.

The generated file is private and ignored by Git.

Open `.env` in an editor and replace:

```text
OPENAI_API_KEY=replace-with-your-openai-api-key
OPENAI_MODEL=replace-with-a-supported-model-name
```

Do not add quotes unless they belong in the value. w8-core can start without
these credentials, but a model-directed task cannot.

Start and verify w8-core:

```bash
docker compose --env-file .env up -d --wait w8-core
python3 browser_runtime.py status
```

Compose uses the locally built `w8-core:domdiff-bench` image and has pulling
disabled. `-d` runs in the background. `--wait` waits until w8-core reports
healthy.

A successful result shows:

- the container name;
- `Running: yes` and `Health: healthy`;
- the w8-core version;
- the noVNC URL;
- the agent-browser version.

Start tasks only after this check succeeds.

## How It Works

Two w8-core interfaces are used:

- **agent-browser** observes accessible controls and executes the chosen
  action. Its `@eN` references work only for the current interactive snapshot.
- **ChromiumRL** captures the structured DOM with
  `captureStructuredSnapshot`, provides action coordinates through
  `getAgentObservation`, and builds a structured model-facing projection with
  `getModelDOM`.

w8-core provides Chromium, ChromiumRL, agent-browser 0.27.3, VNC, and noVNC in
one locally built Docker image. The harness reaches ChromiumRL through CDP and
runs agent-browser inside the container. Host-side Node.js is not required.

For each state, the harness:

- saves ChromiumRL output as `dom.json`;
- creates `dom_full.txt`;
- saves `getModelDOM` output as `dom_model.json`;
- creates `dom_model.txt`.

The model receives the task, `dom_model.txt`, interactive controls, memory, and
recent action results. Screenshots are stored for evaluation and are not sent
to the model.

## Project Layout

- `run-task`: task command.
- `task_cli.py`: task loading and w8-core lifecycle.
- `runner.py`: decisions, validation, execution, and finalization.
- `capture.py`: ChromiumRL, screenshots, and synchronization.
- `trajectory.py`: creates `trajectory.jsonl` and `web_surfer.log`.
- `prompts.py`: model instructions and action policy.
- `agent_browser/`: adapter for the bundled agent-browser.
- `scripts/`: DOM text renderers.
- `browser_runtime.py`: creates an isolated runtime configuration and checks
  w8-core, CDP, noVNC, and agent-browser.
- `tests/`: harness unit tests.

## View w8-core

Choose the local or remote case below.

### w8-core is on your computer

Run:

```bash
python3 browser_runtime.py status
```

The last part of the output contains a line like this:

```text
noVNC: ready (http://127.0.0.1:16191/vnc.html?resize=scale&autoconnect=1&path=websockify)
```

Copy the URL inside the parentheses into your web browser. Keep it open to
watch navigation, scrolling, clicks, and typing.

Your port may not be `16191`. Always use the URL printed by the status command.

### w8-core is on a remote server

On the server, enter the task-recorder folder and run:

```bash
cd w8-domdiff-bench/task-recorder
python3 browser_runtime.py status
```

Suppose its noVNC URL uses port `16191`. Run this on your own computer:

```bash
ssh -o ExitOnForwardFailure=yes -N -L 39084:127.0.0.1:16191 ubuntu@your-server-address
```

Change:

- Replace `ubuntu@your-server-address` with the SSH login you normally use.
- Replace `16191` only if the server's `noVNC: ready` line shows a different
  port.

Keep SSH running. Open:

```text
http://127.0.0.1:39084/vnc.html?resize=scale&autoconnect=1&path=websockify
```

Port `16191` is on the server. Port `39084` is on your computer. If `39084` is
busy, use `39085` in both the command and URL.

If SSH prints `connect failed: Connection refused`, run
`python3 browser_runtime.py status` on the server. Check that w8-core is healthy and use
the noVNC port it prints.

The command works in PowerShell, macOS, and Linux. Closing noVNC or SSH closes
only the view. It does not stop the task.

## Run a Task

Open noVNC first. In another terminal:

```bash
cd w8-domdiff-bench/task-recorder
source .venv/bin/activate
mkdir -p recordings
```

Run a catalog task:

```bash
./run-task task8 --output-dir ./recordings
```

- Human intervention is enabled unless `--no-human-intervention` is added.
- Even when enabled, it may be used only for a visible CAPTCHA or similar
  verification challenge through noVNC.
- Enabled does not mean used. Any actual intervention is recorded.
- Use `--no-human-intervention` for fully autonomous CUA based runs.

Run a manual task:

```bash
./run-task my-task "Readable task name" \
  --task "TASK INSTRUCTION, STOPPING CONDITION, AND CONSTRAINTS" \
  --start-url "https://example.com/" \
  --output-dir ./recordings
```

Rules:

- `--output-dir` is required.
- Each run gets a new timestamped folder.
- Existing runs are never overwritten.
- `--dry-run` validates a task without starting w8-core or the model.
- The launcher prints the task, URL, output path, and intervention policy.

### What happens while a task runs

1. The launcher starts w8-core and opens the initial URL.
2. ChromiumRL and agent-browser capture the current state.
3. The model receives the task, model-facing DOM, interactive controls, memory,
   and recent action outcomes.
4. The chosen action is validated and executed.
5. The resulting state is captured in the next step.
6. The loop continues until the model terminates, a limit is reached, or an
   unrecoverable error occurs.

noVNC may briefly reconnect when a task starts. The container remains, so its
cookies, history, and origin storage survive between tasks.

## Stop or Remove w8-core

Stop w8-core and keep its profile:

```bash
docker compose --env-file .env stop w8-core
```

Start it again:

```bash
docker compose --env-file .env start w8-core
python3 browser_runtime.py status
```

Restart it:

```bash
docker compose --env-file .env restart w8-core
```

Remove the container and profile:

```bash
docker compose --env-file .env down
```

Profile rules:

- `stop`, `start`, and `restart` preserve cookies and history.
- `down` removes the container and profile.
- No profile volume is created.

## Recording Layout

```text
<run>/
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
    step_002/
      ...
```

- `step_001` is the initial state.
- `action.json` belongs to the state where the action was chosen.
- The next step is the state reached after that action.
- The final step can have no `action.json`.
- `trajectory.jsonl` and `web_surfer.log` have one row per executed agent
  action.

Validate a run and rebuild only its exported action logs:

```bash
python runner.py --build-trajectory-run /path/to/recordings/<run-id>
```

## Evidence Settings

- `dom.json` is the authoritative viewport capture.
- `inViewportOnly=true` and `includeOffscreen=false` are used.
- Scrolling makes new content eligible for capture.
- The harness requests up to 7,000 nodes and 200,000 text characters.
- Chromium limits direct text to 240 characters per node.
- Chromium limits subtree text to 500 characters per node.
- Attribute values are limited to 160 characters.
- Each node stores up to 12 attributes and 80 child references.
- Host renderers do not shorten `dom.json`.

## Troubleshooting

### A port or container name is already used

New checkout:

```bash
python3 browser_runtime.py configure
```

Existing `.env` with newly occupied ports:

```bash
docker compose --env-file .env down
python3 browser_runtime.py configure --refresh-ports
docker compose --env-file .env up -d --wait w8-core
python3 browser_runtime.py status
```

This preserves the API key and model but replaces the ports. `down` removes
this checkout's current container profile.

### noVNC does not open

```bash
python3 browser_runtime.py status
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=100 w8-core
```

Use the URL printed by `status`. Do not reuse a URL from another checkout.

### SSH prints `connect failed: Connection refused`

Run `python3 browser_runtime.py status` on the server. Confirm w8-core is healthy and
copy its noVNC port into the SSH command.

### The local SSH port is already used

Change `39084` to `39085` in both the SSH command and local noVNC URL. Keep the
server noVNC port unchanged.

### A task does not start

Check that `.env` has real `OPENAI_API_KEY` and `OPENAI_MODEL` values. Then run:

```bash
./run-task task8 --output-dir ./recordings --no-human-intervention --dry-run
```

### Docker says the local image does not exist

Check the expected image:

```bash
docker image inspect w8-core:domdiff-bench
```

If it is missing, complete Browser Setup steps 3 through 9 before starting
Compose.

### List this checkout's Docker resources

```bash
grep -E '^(COMPOSE_PROJECT_NAME|CONTAINER_NAME|CDP_HOST_PORT|NOVNC_HOST_PORT|VNC_HOST_PORT)=' .env
docker compose --env-file .env ps
```

Do not stop another project's container. This checkout has separate names and
ports.
