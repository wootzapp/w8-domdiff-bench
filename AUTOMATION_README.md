# Automation README

This document explains the automated browser setup in `task-recorder`: what runs,
which Docker image/container is used, what each script does, and how one
automated trajectory is produced.

## Short summary

The automated setup uses a desktop Wootz browser running in Docker. A Python
agent loop asks an AI model for the next browser action, performs that action in
the Wootz browser through CDP, and records ChromiumRL verifier artifacts before
and after every step.

High-level flow:

```text
task prompt
  ↓
scripts/run-agent-browser.sh
  ↓
agent_browser/desktop_agent.py
  ↓ asks model for one JSON action
OpenAI-compatible model API
  ↓ returns action
agent_browser/desktop_agent.py
  ↓ executes action through Wootz CDP
desktop Wootz browser in Docker
  ↓
recorder.py captures ChromiumRL before/after artifacts
  ↓
tasks/<task-id>/step_XXX/
```

## Main files

```text
task-recorder/
├── docker-compose.yml
├── scripts/
│   ├── container-start.sh
│   ├── doctor.sh
│   └── run-agent-browser.sh
├── agent_browser/
│   ├── __init__.py
│   └── desktop_agent.py
├── recorder.py
├── README.md
└── AUTOMATION_README.md
```

## What functionality `agent_browser` provides

The `agent_browser` package is the automation layer. It is the part that turns a
plain task prompt into a sequence of browser actions.

The browser itself does not know the task. The model API does not know how to
operate the local Wootz browser. `agent_browser` connects those pieces.

It provides these functions:

```text
1. Observe the current browser page.
2. Convert the page into a model-readable snapshot.
3. Send the task, snapshot, and recent action history to the model.
4. Require the model to return one structured JSON action.
5. Validate and normalize that action.
6. Execute the action in the Wootz browser through CDP.
7. Ask recorder.py to capture ChromiumRL before/after artifacts.
8. Store the decision and trajectory history.
9. Repeat until the model terminates, max steps are reached, or the run stops.
```

Without `agent_browser`, the setup can still start a browser and check CDP, but
it cannot automatically perform a task. `agent_browser` is the runtime controller
that repeatedly decides, acts, records, and continues.

The implementation is intentionally focused on this recorder workflow:

```text
Wootz desktop browser
  +
fixed local CDP endpoint
  +
OpenAI-compatible model call
  +
ChromiumRL verifier artifact capture
```

It does not add new browser protocol commands. It uses the commands exposed by
the Wootz browser:

```text
Standard CDP:
  Page.navigate
  Input.dispatchMouseEvent
  Input.insertText
  Input.dispatchKeyEvent
  Runtime.evaluate

ChromiumRL CDP:
  ChromiumRL.getAgentObservation
  ChromiumRL.saveDOMState
  ChromiumRL.compareDOMState
  ChromiumRL.getTouchTraces
  ChromiumRL.captureInteraction
  ChromiumRL.getVisualHash
```

The current ChromiumRL protocol provides observation, signal, and DOM-diff
commands. It does not expose direct action commands such as
`ChromiumRL.click`, `ChromiumRL.type`, or `ChromiumRL.scroll`. For that reason,
actual input actions are dispatched with standard CDP, while verifier data is
captured with ChromiumRL.

## Docker image and container

The automated desktop recorder uses this image:

```text
wootz-runtime:wootz-chrome
```

The automated recorder container is:

```text
wootz-desktop-browser-replay-001
```

It is defined in:

```text
docker-compose.yml
```

The compose service name is:

```text
wootz-desktop
```

Ports exposed on the server:

```text
CDP:   127.0.0.1:49325 -> container 9226
noVNC: 127.0.0.1:16181 -> container 6080
VNC:   127.0.0.1:15901 -> container 5900
```

Inside the container, the actual Wootz browser CDP port is:

```text
127.0.0.1:9225
```

The container also runs a CDP proxy:

```text
container 9226 -> container 9225
```

So the host talks to:

```text
http://127.0.0.1:49325
```

The image is expected to already exist locally on the server. This compose file
does not build the image. It runs the existing `wootz-runtime:wootz-chrome`
image, which contains:

```text
/opt/wootz/chrome/chrome
/usr/local/bin/wootz-vnc-start
noVNC/websockify tooling
ChromiumRL-enabled Wootz browser
```

Check the image locally:

```bash
docker images | grep wootz-runtime
```

Check the running container:

```bash
docker ps --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}' | grep wootz-desktop
```

<!-- ## Related containers

The automated desktop recorder is separate from the other browser containers.

```text
Automated desktop recorder:
  container: wootz-desktop-browser-replay-001
  image:     wootz-runtime:wootz-chrome
  CDP:       49325
  noVNC:     16181

Desktop authoring browser:
  container: wootz-runtime
  image:     wootz-runtime:wootz-chrome
  CDP:       9225
  noVNC:     16081

Android recorder:
  container: knowledge-work-workflow-browser-replay-001
  image:     devjangid/wootzapp-mobile-tablet
  CDP:       49224
  noVNC:     16080
```

The automation setup should use only:

```text
wootz-desktop-browser-replay-001
``` -->

## What each script does

### `docker-compose.yml`

Defines the desktop automated recorder service.

Main responsibilities:

- uses image `wootz-runtime:wootz-chrome`;
- creates container `wootz-desktop-browser-replay-001`;
- maps CDP/noVNC/VNC ports;
- mounts `scripts/container-start.sh` into the container;
- starts the container with `/usr/local/bin/wootz-desktop-start`;
- sets English browser locale defaults;
- adds a healthcheck against internal Wootz CDP;
- restarts the container if the browser process exits.

Important config:

```yaml
image: wootz-runtime:wootz-chrome
container_name: wootz-desktop-browser-replay-001
restart: unless-stopped
```

### `scripts/container-start.sh`

Runs inside the Docker container.

Main responsibilities:

- starts VNC/noVNC through `/usr/local/bin/wootz-vnc-start`;
- starts the Wootz desktop browser:

  ```text
  /opt/wootz/chrome/chrome
  ```

- enables browser CDP:

  ```text
  --remote-debugging-address=127.0.0.1
  --remote-debugging-port=9225
  ```

- sets the browser window size:

  ```text
  --window-size=1365,768
  ```

- sets English language headers:

  ```text
  --lang=en-US
  --accept-lang=en-US,en;q=0.9
  ```

- starts `socat` to proxy:

  ```text
  0.0.0.0:9226 -> 127.0.0.1:9225
  ```

- monitors both the Wootz browser process and the CDP proxy.

If the browser process dies, this script exits the container. Because compose
uses `restart: unless-stopped`, Docker restarts it cleanly.

### `scripts/doctor.sh`

Checks whether the automated desktop browser and ChromiumRL are usable.

It checks:

- `http://127.0.0.1:49325/json/version`;
- CDP connection;
- page attach;
- `Runtime.enable`;
- `DOM.enable`;
- `ChromiumRL.saveDOMState`;
- `ChromiumRL.compareDOMState`;
- `ChromiumRL.getAgentObservation`;
- `ChromiumRL.getTouchTraces`;
- `ChromiumRL.captureInteraction`.

Run it:

```bash
cd /data/aayush/task-recorder
./scripts/doctor.sh
```

### `scripts/run-agent-browser.sh`

This is the command you normally run for an automated task.

Example:

```bash
cd /data/aayush/task-recorder

./scripts/run-agent-browser.sh task1 \
  "go to flipkart and add a blue color adidas shoe to my cart." \
  --yes
```

Main responsibilities:

- changes into the `task-recorder` directory;
- loads `.env`;
- reads `CDP_HOST_PORT`, defaulting to `49325`;
- calls:

  ```bash
  python3 -m agent_browser.desktop_agent
  ```

- passes task id, task prompt, CDP URL, and extra CLI flags.

This script does not run the AI loop itself. It launches the Python agent loop.

## What `agent_browser/desktop_agent.py` does

`desktop_agent.py` is the automated agent controller.

Its job:

```text
model decision + browser action execution + task loop control
```

It does these things:

- loads model settings from `.env`;
- connects to desktop Wootz CDP;
- creates a fresh tab/context for new tasks;
- clears cookies/cache/storage for clean non-resume tasks;
- applies English locale/Accept-Language overrides through CDP;
- captures a model-facing page snapshot;
- sends task + recent history + current snapshot to the model;
- receives one JSON action from the model;
- optionally asks for approval;
- executes the action in the browser;
- calls `recorder.py` to capture before/after artifacts;
- writes trajectory files;
- detects repeated no-progress actions;
- handles resume mode.

How it performs one model turn:

```text
1. Calls ChromiumRL.getAgentObservation.
2. Adds visible text blocks from the current viewport.
3. Builds a compact snapshot with refs such as e1, e2, e3.
4. Sends this JSON payload to the model:
   - task prompt
   - recent approved/rejected actions
   - no-progress warnings
   - current page snapshot
5. Receives one JSON action.
6. Normalizes action aliases, for example:
   - open -> navigate
   - left_click -> click
   - key -> press
7. Resolves action target:
   - ref from ChromiumRL observation
   - CSS selector
   - coordinate fallback
8. Executes the action through CDP.
9. Records the step through recorder.py.
10. Adds the action outcome to history for the next model turn.
```

The snapshot refs are important. When ChromiumRL returns an observed element,
`desktop_agent.py` assigns it a short ref:

```text
[ref=e3] button "Add to cart" center=[842,611]
```

The model can then return:

```json
{"action":"click","ref":"e3","thoughts":"Click Add to cart"}
```

`desktop_agent.py` resolves `e3` back to the element center and dispatches the
click in the browser.

The model can return actions like:

```json
{"action":"navigate","url":"https://example.com","thoughts":"Open the site"}
{"action":"click","ref":"e3","thoughts":"Click a visible element"}
{"action":"fill","ref":"e4","text":"blue adidas shoe","thoughts":"Fill search"}
{"action":"press","key":"Enter","thoughts":"Submit search"}
{"action":"scroll","pixels":700,"thoughts":"Scroll down"}
{"action":"terminate","status":"success","final_answer":"Item added","thoughts":"Done"}
```

Action execution uses standard browser CDP input/navigation commands:

```text
Page.navigate
Input.dispatchMouseEvent
Input.insertText
Input.dispatchKeyEvent
Runtime.evaluate
```

ChromiumRL is used for observation and verifier capture:

```text
ChromiumRL.getAgentObservation
ChromiumRL.saveDOMState
ChromiumRL.compareDOMState
ChromiumRL.getTouchTraces
ChromiumRL.captureInteraction
ChromiumRL.getVisualHash
```

The current Wootz ChromiumRL protocol does not expose direct action commands
such as `ChromiumRL.click`, `ChromiumRL.type`, or `ChromiumRL.scroll`.

## What `recorder.py` does

`recorder.py` is the capture and verifier artifact layer.

Its job:

```text
CDP connection + ChromiumRL capture + before/after evidence + output files
```

It does not decide browser actions. It records what happened.

Main responsibilities:

- manages CDP WebSocket connection;
- attaches to page targets;
- enables `Runtime` and `DOM`;
- enables ChromiumRL tracing;
- captures before/after page state;
- captures screenshots;
- saves ChromiumRL refined DOM;
- compares before/after DOM;
- captures touch traces/interactions/signals;
- builds verifier-friendly action metadata;
- writes files into `tasks/<task-id>/step_XXX/`.

Important ChromiumRL calls:

```text
ChromiumRL.enable
ChromiumRL.saveDOMState
ChromiumRL.compareDOMState
ChromiumRL.getAgentObservation
ChromiumRL.getTouchTraces
ChromiumRL.captureInteraction
ChromiumRL.getVisualHash
```

## Runtime model configuration

Model access is configured through:

```text
.env
```

Required values:

```text
OPENAI_API_KEY=...
AGENT_BROWSER_MODEL=...
```

Optional value:

```text
OPENAI_BASE_URL=https://api.openai.com/v1
```

The API key does not control the browser. It only allows the runner to call the
model. The browser loop is controlled by `desktop_agent.py`.

## Real-time viewing

The agent controls the same browser visible through noVNC.

From your laptop:

```powershell
ssh -N -L "[::1]:39081:127.0.0.1:16181" ubuntu@static.235.31.55.162.clients.your-server.de
```

Open:

```text
http://[::1]:39081/vnc.html?resize=scale&autoconnect=1
```

Then start an automated task on the server. You should see the same browser
being controlled in real time.

## New task flow

Command:

```bash
cd /data/aayush/task-recorder

./scripts/run-agent-browser.sh task1 \
  "go to flipkart and add a blue color adidas shoe to my cart." \
  --yes
```

Flow:

```text
1. run-agent-browser.sh loads .env
2. run-agent-browser.sh calls python3 -m agent_browser.desktop_agent
3. desktop_agent.py initializes tasks/task1/
4. desktop_agent.py connects to http://127.0.0.1:49325
5. desktop_agent.py creates a fresh browser tab/context
6. desktop_agent.py clears browser data unless --keep-browser-data is used
7. desktop_agent.py captures current page observation
8. desktop_agent.py sends task + observation + history to the model
9. model returns one JSON action
10. desktop_agent.py executes the action through CDP
11. recorder.py captures before/after ChromiumRL artifacts
12. desktop_agent.py appends trajectory history
13. loop repeats until terminate, max steps, error, or user stop
```

## One trajectory step flow

For each model-approved action:

```text
step_XXX starts
  ↓
write action.json
  ↓
ChromiumRL trace reset
  ↓
capture before/
  - chromiumrl_dom.json
  - chromiumrl_agent_observation.json
  - chromiumrl_visual_hash.json
  - page_state.json
  - screenshot.png
  - state_index.json
  ↓
perform browser action
  ↓
wait settle seconds
  ↓
capture after/
  - chromiumrl_dom.json
  - chromiumrl_agent_observation.json
  - chromiumrl_visual_hash.json
  - page_state.json
  - screenshot.png
  - state_index.json
  ↓
ChromiumRL.compareDOMState
  ↓
write dom_diff.json
  ↓
write dom_diff_summary.json
  ↓
collect ChromiumRL signals
  ↓
write chromiumrl_signals.json
  ↓
write verifier_action.json
  ↓
write interaction_capture.json
  ↓
write step.json
  ↓
append trajectory.jsonl
```

## Output structure

Output directory:

```text
/data/aayush/task-recorder/tasks/<task-id>/
```

Typical structure:

```text
tasks/<task-id>/
├── actions.json
├── manifest.json
├── trajectory.jsonl
├── agent_browser_decisions.jsonl
├── agent_browser_final.json
└── step_001/
    ├── action.json
    ├── step.json
    ├── before/
    │   ├── chromiumrl_dom.json
    │   ├── chromiumrl_agent_observation.json
    │   ├── chromiumrl_visual_hash.json
    │   ├── page_state.json
    │   ├── screenshot.png
    │   └── state_index.json
    ├── after/
    │   ├── chromiumrl_dom.json
    │   ├── chromiumrl_agent_observation.json
    │   ├── chromiumrl_visual_hash.json
    │   ├── page_state.json
    │   ├── screenshot.png
    │   └── state_index.json
    ├── dom_diff.json
    ├── dom_diff_summary.json
    ├── verifier_action.json
    ├── interaction_capture.json
    └── chromiumrl_signals.json
```

Important files:

```text
actions.json
  Saved task metadata and prompt.

manifest.json
  Task status, timestamps, CDP URL, completed step count.

agent_browser_decisions.jsonl
  Model proposals and runner events.

trajectory.jsonl
  Completed action trajectory.

step_XXX/action.json
  The action actually executed.

step_XXX/step.json
  Step metadata, before/after page states, status, artifacts.

before/chromiumrl_dom.json
after/chromiumrl_dom.json
  ChromiumRL refined DOM before and after the action.

dom_diff.json
  Raw ChromiumRL.compareDOMState response.

dom_diff_summary.json
  Compact summary of visible/interactable changes.

verifier_action.json
  Verifier-friendly action record.

interaction_capture.json
  ChromiumRL captureInteraction result for the action target.

chromiumrl_signals.json
  Touch traces, CLS, compositor, visual hash, layout timings.

screenshot.png
  Visual evidence before/after the action.
```

## Resume flow

Resume command:

```bash
./scripts/run-agent-browser.sh task1 \
  "same exact task prompt as before" \
  --resume
```

Resume mode:

- keeps the current browser tab/session;
- does not clear cookies/cache/storage;
- does not create a fresh isolated context;
- loads recent completed actions from `trajectory.jsonl`;
- appends new steps after the last recorded step;
- requires the prompt to match the saved task prompt.

Use resume only for the same task. For a different task, use a new task id.

## Approval modes

Default mode asks before every action:

```text
Approve this action? [y/N/q]:
```

Meaning:

```text
y + Enter = execute and record
n + Enter = reject and ask model again
q + Enter = stop
```

Automatic mode:

```bash
./scripts/run-agent-browser.sh task1 "task prompt" --yes
```

With `--yes`, the model actions are executed without approval.

## Health and recovery

Check CDP and ChromiumRL:

```bash
./scripts/doctor.sh
```

If CDP gives:

```text
Server disconnected
```

it usually means the CDP proxy is reachable but the browser CDP backend died.
The current startup script monitors this and restarts the container through
Docker compose restart policy.

Restart only the automated desktop recorder:

```bash
cd /data/aayush/task-recorder
docker compose up -d --force-recreate wootz-desktop
./scripts/doctor.sh
```

This affects only:

```text
wootz-desktop-browser-replay-001
```

It does not stop the Android recorder or the desktop authoring container.
