# Browser Task Recorder

This recorder runs a model-directed browser task and stores each observed browser
state once. A state contains the structured DOM capture, readable DOM text,
model-facing DOM projection, screenshot, and agent-browser observations. The
action selected from a state is saved in that state directory, and the following
state records the result.

## How It Works

Two systems interact with the browser:

- **agent-browser** observes accessible controls and executes the model's chosen
  browser action. Its `@eN` references are executable only for the current
  interactive snapshot.
- **ChromiumRL** captures the structured DOM with
  `captureStructuredSnapshot`, provides action coordinates through
  `getAgentObservation`, and builds a structured model-facing projection with
  `getModelDOM`.

w8-core, a new kind of browser engine, provides the Chromium browser runtime,
the ChromiumRL CDP domain, agent-browser 0.27.3, VNC, and noVNC in one Docker
image. The recorder reaches ChromiumRL through the host CDP port and invokes
agent-browser inside the same container. A host Node.js or npm installation is
not required.

For every captured snapshot, the recorder saves `dom.json`. It runs the full
renderer to create `dom_full.txt`, saves the `getModelDOM` result as
`dom_model.json`, and uses the deterministic model renderer to create
`dom_model.txt`.

The model receives the task instruction, current `dom_model.txt`, the current
interactive agent-browser snapshot, task memory, and recent action outcomes.
Screenshots are captured as recording artifacts and are not attached to model
requests.

## Project Layout

- `run-task` — shell wrapper for the command-line task launcher.
- `task_cli.py` — loads a catalog or manual task, starts the browser service,
  and launches `runner.py`.
- `runner.py` — coordinates model decisions, validation, execution, capture,
  state transitions, finalization, and command-line options.
- `capture.py` — CDP connection, structured capture, screenshots, browser
  coordinates, language checks, and agent-browser synchronization.
- `trajectory.py` — validates recorded states and creates `trajectory.jsonl`
  plus `web_surfer.log`.
- `recorder_support.py` — common text normalization, URL helpers, timestamps,
  errors, and atomic file writers.
- `prompts.py` — model instructions and action policy.
- `agent_browser/` — the adapter around the official agent-browser CLI.
- `scripts/render_chromiumrl_snapshot_full.py` — turns `dom.json` into
  readable `dom_full.txt`.
- `scripts/render_chromiumrl_model_dom.py` — validates `dom_model.json` and
  joins its ordered sections into `dom_model.txt`.
- `scripts/render_chromiumrl_snapshot_model.py` — regression oracle for the
  browser-produced model projection.
- `tests/` — recorder unit tests.

## Setup

### Requirements

- Docker Engine with Docker Compose.
- Python 3 with virtual environment support.
- An OpenAI API key and a supported model name.
- A machine capable of running a visible Chromium container. The default
  shared-memory allocation is 2 GiB.

The model runner executes on the host. The browser, VNC/noVNC server,
ChromiumRL CDP implementation, and agent-browser executable run inside the
w8-core container.

### Clone the reproducible branch

```bash
git clone --branch w8-reproducible https://github.com/wootzapp/w8-domdiff-bench.git
cd w8-domdiff-bench/task-recorder
```

All remaining commands in this guide are run from `task-recorder/` unless a
step explicitly says to run it on your local computer.

### Install the recorder dependency

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, run the recorder inside WSL or another Linux environment with
Docker access. The SSH tunnel command shown later can be run directly from
PowerShell when the recorder itself is hosted on a remote Linux server.

### Create an isolated browser configuration

Run:

```bash
./browser-runtime configure
```

This creates a private `.env` file for the checkout. The helper:

- chooses a checkout-specific Compose project and container name;
- uses ports `49335`, `16191`, and `15911` when they are free;
- selects other free loopback ports when any preferred port is occupied;
- keeps the ports bound to `127.0.0.1`, rather than exposing CDP or VNC to the
  network;
- refuses to overwrite an existing `.env` during a normal configure command.

The generated file is mode `0600` and ignored by Git. `.env.example` documents
all values without containing credentials.

Open `.env` in an editor and replace:

```text
OPENAI_API_KEY=replace-with-your-openai-api-key
OPENAI_MODEL=replace-with-a-supported-model-name
```

Do not add quotes unless they are part of the actual value. The browser can be
started without these values, but a model-directed task cannot.

### Start and verify w8-core

Download the image and start the service:

```bash
docker pull wootzapp/w8-core:latest
docker compose --env-file .env up -d --wait w8-core
```

The w8-core image includes the browser, ChromiumRL CDP commands,
agent-browser, VNC, and noVNC. No separate Node.js or agent-browser installation
is needed.

Verify every required browser interface:

```bash
./browser-runtime status
```

A successful check reports:

- the configured container name;
- `Running: yes` and `Health: healthy`;
- the browser version returned by CDP;
- the noVNC URL and HTTP readiness;
- the bundled agent-browser version.

Do not start a task until this command succeeds. This separates browser setup
problems from recorder or model failures.

## View the Browser

### Browser running on your local machine

`./browser-runtime status` prints a URL similar to:

```text
http://127.0.0.1:16191/vnc.html?resize=scale&autoconnect=1&path=websockify
```

The port can be different because configuration deliberately avoids occupied
ports. Open the exact printed URL in Chrome, Firefox, or another normal web
browser. Keep that tab open while the recorder runs. noVNC shows the live
w8-core desktop, including navigation, scrolling, clicks, and typed values.

The noVNC page is only a view of the browser. Closing the noVNC tab does not
stop the task or the container.

### Browser running on a remote server

First, verify w8-core on the server:

```bash
cd /path/to/w8-domdiff-bench/task-recorder
./browser-runtime status
grep '^NOVNC_HOST_PORT=' .env
```

Remember the numeric `NOVNC_HOST_PORT`. The service intentionally listens only
on the server's loopback interface, so it is not opened to the public network.

On your local computer, create the tunnel. Replace all three placeholders and
use the noVNC port printed on the server:


```bash
ssh -o ExitOnForwardFailure=yes -N \
  -L 127.0.0.1:39084:127.0.0.1:SERVER_NOVNC_PORT \
  SERVER_USER@SERVER_HOST
```

For example, if the server reports `NOVNC_HOST_PORT=16191`, substitute `16191`
for `SERVER_NOVNC_PORT`. On PowerShell, enter the same command on one line:

```powershell
ssh -o ExitOnForwardFailure=yes -N -L 127.0.0.1:39084:127.0.0.1:SERVER_NOVNC_PORT SERVER_USER@SERVER_HOST
```

Then open:

```text
http://127.0.0.1:39084/vnc.html?resize=scale&autoconnect=1&path=websockify
```

`ExitOnForwardFailure=yes` prevents SSH from appearing connected when the local
forward could not be created. If local port `39084` is already occupied, change
only the first port in `-L` to another unused local port, such as `39085`, and
open the matching URL. Do not change `SERVER_NOVNC_PORT` unless `.env` on the
server uses a different port.

If SSH prints `connect failed: Connection refused`, the tunnel reached the
server but no service was listening on the specified server port. Run
`./browser-runtime status` on the server and copy its noVNC port exactly before
trying again.

## Run a Task

Open noVNC before starting the task. In a second terminal, activate the Python
environment and return to the recorder directory:

```bash
cd /path/to/w8-domdiff-bench/task-recorder
source .venv/bin/activate
mkdir -p recordings
```

Run a catalog task:

```bash
./run-task task8 --output-dir ./recordings --no-human-intervention
```

The task ID is resolved through the configured task catalog. The launcher
prints the selected task, starting URL, output directory, and intervention
policy before the model starts.

Run a manual task:

```bash
./run-task my-task "Readable task name" \
  --task "TASK INSTRUCTION, STOPPING CONDITION, AND CONSTRAINTS" \
  --start-url "https://example.com/" \
  --output-dir /path/to/recordings
```

`--output-dir` is required. A timestamped run directory is created and an
existing run is never overwritten. Use `--dry-run` to validate task selection
without starting the browser.

### What happens while a task runs

1. The launcher ensures the configured w8-core container is available and
   restarts its browser process at the task boundary.
2. The initial URL opens in the visible browser.
3. ChromiumRL and agent-browser capture the current page state.
4. The model receives the task, model-facing DOM, interactive controls, memory,
   and recent action outcomes.
5. The selected action is validated and executed in w8-core.
6. The resulting browser state is captured in the next sequential step.
7. The loop continues until the model terminates, a limit is reached, or an
   unrecoverable error occurs.

The noVNC session may briefly reconnect when the browser process restarts at a
task boundary. The container itself is retained, so cookies, history, and
origin storage survive between tasks that use the same `.env` and container.

## Stop, Restart, or Remove the Browser

Stop the browser container while preserving its writable layer and browser
profile:

```bash
docker compose --env-file .env stop w8-core
```

Start the same container and profile again:

```bash
docker compose --env-file .env start w8-core
./browser-runtime status
```

Restart the service without recreating it:

```bash
docker compose --env-file .env restart w8-core
```

Remove the container and its container-lifetime browser profile:

```bash
docker compose --env-file .env down
```

There is intentionally no profile volume. `stop`, `start`, and `restart`
preserve the profile because they retain the container. `down` removes it.

## State Layout

A run uses direct sequential state folders:

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
      action.json                 # when an action is selected here
    step_002/
      ...                         # state reached by action.json in step_001
```

`step_001` is the initial captured page state. Each executed action lives in
its source state directory. The next sequential directory is the state reached
after that action. A final state can therefore have no `action.json`.

`action.json` records the chosen action, execution receipt, target identity,
coordinate lookup, progress signals, model response metadata, source-state
paths, and next-state paths. The manifest lists both captured states and
executed actions. `trajectory.jsonl` and `web_surfer.log` contain one row for
each executed non-human action.

Use this command to validate an existing run and regenerate only the two
exported action logs:

```bash
python runner.py --build-trajectory-run /path/to/recordings/<run-id>
```

## Evidence Boundaries

`dom.json` is the authoritative capture for the current viewport. The recorder
uses `inViewportOnly=true` and `includeOffscreen=false`; content becomes
eligible after scrolling brings it into view.

The recorder requests 7,000 nodes and 200,000 text characters. Chromium also
sets per-node direct text at 240 characters, subtree text at 500, selected
attribute values at 160, selected attributes at 12, and child references at
80. The host does not shorten a returned DOM snapshot or its text projections.

The renderers create readable projections only. They do not modify `dom.json`.

## Troubleshooting

### Docker reports that a container name or host port is already in use

For a new checkout, use `./browser-runtime configure` instead of copying a
configuration from another checkout. It chooses a unique container identity
and currently available ports.

If an existing `.env` points to ports that later became occupied, stop and
remove only this checkout's Compose service, then refresh its ports:

```bash
docker compose --env-file .env down
./browser-runtime configure --refresh-ports
docker compose --env-file .env up -d --wait w8-core
./browser-runtime status
```

The refresh preserves the configured image, container identity, API key, and
model while replacing the three host ports and the printed noVNC URL. Because
`down` removes the container, use this only when the service cannot start; it
also removes that container's browser profile.

### The noVNC page does not open locally

Run `./browser-runtime status`. If it fails, inspect the service without
guessing a different URL:

```bash
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=100 w8-core
```

Use the noVNC URL printed by the status command. A hard-coded port from another
checkout may point at the wrong container or at no service.

### The SSH tunnel asks for a password and then prints connection refused

This is a server-side noVNC reachability problem, not an SSH authentication
failure. On the server, run `./browser-runtime status` and verify the value of
`NOVNC_HOST_PORT` in `.env`. Use that exact number on the right side of the
local `-L` argument.

### SSH says the forwarding address is already in use

The local tunnel port is occupied. Keep the server port unchanged and choose a
different local port:

```bash
ssh -o ExitOnForwardFailure=yes -N \
  -L 127.0.0.1:39085:127.0.0.1:SERVER_NOVNC_PORT \
  SERVER_USER@SERVER_HOST
```

Then open the URL with port `39085`.

### The browser is healthy but a task will not start

Confirm that `.env` contains real values rather than placeholders:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

Run a dry check to separate catalog and argument validation from browser and
model execution:

```bash
./run-task task8 --output-dir ./recordings --no-human-intervention --dry-run
```

### Confirm exactly which Docker resources belong to this checkout

```bash
grep -E '^(COMPOSE_PROJECT_NAME|CONTAINER_NAME|CDP_HOST_PORT|NOVNC_HOST_PORT|VNC_HOST_PORT)=' .env
docker compose --env-file .env ps
```

Do not stop or remove another project's container to resolve a conflict. The
isolated names and ports in this checkout are designed to make that unnecessary.
