# Desktop agent-browser task recorder

This folder is for automated desktop Wootz browser tasks only.

It uses a separate desktop recorder container:

```text
Image:      wootz-runtime:wootz-chrome
Container:  wootz-desktop-browser-replay-001
CDP:        http://127.0.0.1:49325
noVNC:      127.0.0.1:16181
VNC:        127.0.0.1:15901
```

Manual recording is not kept here. Use the Android recorder folder for manual task recording.

## Related containers

| Use | Container | CDP | noVNC | VNC |
| --- | --- | ---: | ---: | ---: |
| Android recorder | `knowledge-work-workflow-browser-replay-001` | `49224` | `16080` | existing Android config |
| Desktop authoring | `wootz-runtime` | `9225` | `16081` | `15900` |
| Desktop automated recorder | `wootz-desktop-browser-replay-001` | `49325` | `16181` | `15901` |

Use `wootz-desktop-browser-replay-001` for automated DOM recording. Do not use the desktop authoring container for recorder runs.

## What this runner does

The automated runner is in:

```text
/data/aayush/task-recorder/agent_browser/desktop_agent.py
```

It controls the desktop Wootz browser through CDP and records verifier artifacts through ChromiumRL. The model does not generate DOM files.

Implemented browser actions:

- `snapshot()` semantic, ref-based page view for the model.
- visible text blocks from the current viewport.
- `navigate` / `open`.
- `click` by snapshot ref, CSS selector, or coordinate.
- `type` and `fill`.
- `press`.
- `scroll`.
- `wait`.

Supported model action schema:

```json
{"action":"open","url":"https://example.com","thoughts":"Open the site"}
{"action":"navigate","url":"https://example.com","thoughts":"Open the site"}
{"action":"click","ref":"e12","thoughts":"Click a visible element"}
{"action":"click","selector":"input[name='q']","thoughts":"Click by selector"}
{"action":"left_click","coordinate":[500,300],"thoughts":"Fallback coordinate click"}
{"action":"type","text":"example query","thoughts":"Type text"}
{"action":"fill","ref":"e3","text":"example text","thoughts":"Fill input"}
{"action":"press","key":"Enter","thoughts":"Press key"}
{"action":"key","key":"Enter","thoughts":"Press key"}
{"action":"scroll","pixels":700,"thoughts":"Scroll down"}
{"action":"wait","seconds":2,"thoughts":"Wait for page update"}
{"action":"terminate","status":"success","final_answer":"Done","thoughts":"Task complete"}
```

Scroll direction:

```text
positive pixels = scroll down
negative pixels = scroll up
```

## Configure model access

Edit `.env`:

```bash
cd /data/aayush/task-recorder
nano .env
```

Add or update:

```text
OPENAI_API_KEY=sk-...
AGENT_BROWSER_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

Use a stronger model if needed:

```text
AGENT_BROWSER_MODEL=gpt-4.1
```

## Start browser and check CDP

```bash
cd /data/aayush/task-recorder
docker compose up -d
./scripts/doctor.sh
```

`doctor.sh` checks CDP and ChromiumRL availability.

## Open noVNC

From Windows PowerShell:

```powershell
ssh -N -L "[::1]:39081:127.0.0.1:16181" ubuntu@static.235.31.55.162.clients.your-server.de
```

Open:

```text
http://[::1]:39081/vnc.html?resize=scale&autoconnect=1
```

If the local port is blocked, change only the first port:

```powershell
ssh -N -L "[::1]:49181:127.0.0.1:16181" ubuntu@static.235.31.55.162.clients.your-server.de
```

Then open:

```text
http://[::1]:49181/vnc.html?resize=scale&autoconnect=1
```

Do not change the server-side port `16181`.

## Run a new automated task

```bash
cd /data/aayush/task-recorder
./scripts/run-agent-browser.sh task2 "Enter the task."
```

For a new non-resume task, the runner:

- creates a fresh browser tab;
- starts an isolated browser context when CDP supports it;
- otherwise falls back to clearing cookies/cache/storage;
- starts with empty model action history.

This prevents a new task from inheriting the previous task’s tab, cookies, login state, localStorage, sessionStorage, cache, or model history.

If you intentionally want a new task to reuse browser data:

```bash
./scripts/run-agent-browser.sh task2 "Enter the task." --keep-browser-data
```

## Approval flow

By default, every proposed action requires approval:

```text
y + Enter  = perform and record the action
n + Enter  = reject the action and ask the model again
q + Enter  = stop the run
```

Run without approvals only when you trust the model for that task:

```bash
./scripts/run-agent-browser.sh task2 "Enter the task." --yes
```

## Resume an existing task

```bash
cd /data/aayush/task-recorder
./scripts/run-agent-browser.sh task1 "Same task prompt as before." --resume
```

Resume mode:

- keeps the current browser tab/session;
- does not clear browser data;
- does not create a new isolated context;
- reloads recent completed actions from `trajectory.jsonl`;
- appends new steps after the last existing step.

Use resume only when continuing the same task.

## Step limits and timeouts

Default max steps:

```text
--max-steps 80
```

For longer tasks:

```bash
./scripts/run-agent-browser.sh task1 "Same task prompt as before." --resume --max-steps 120
```

Input events use a separate short timeout so a stuck mouse/keyboard CDP command does not block for the full DOM-capture timeout:

```bash
./scripts/run-agent-browser.sh task2 "Enter the task." --input-timeout 8
```

If CDP mouse-wheel scrolling times out, the runner reconnects CDP and performs a recorded `window.scrollBy` fallback. The step still writes verifier artifacts, and `action.json` will include:

```json
"_execution_method": "runtime_scroll_fallback"
```

## Output structure

Output is written to:

```text
/data/aayush/task-recorder/tasks/<task-id>/
```

Typical structure:

```text
tasks/<task-id>/
├── manifest.json
├── actions.json
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
    ├── verifier_action.json
    ├── interaction_capture.json
    ├── chromiumrl_signals.json
    ├── dom_diff.json
    └── dom_diff_summary.json
```

Important files:

- `before/chromiumrl_dom.json`: ChromiumRL refined DOM before the action.
- `after/chromiumrl_dom.json`: ChromiumRL refined DOM after the action.
- `dom_diff.json`: raw `ChromiumRL.compareDOMState` output.
- `dom_diff_summary.json`: summarized verifier-friendly DOM diff.
- `chromiumrl_agent_observation.json`: compact visible/interactable browser observation.
- `page_state.json`: URL, title, viewport, scroll, and target metadata.
- `screenshot.png`: visual state.
- `verifier_action.json`: action metadata from the automated agent action.
- `agent_browser_decisions.jsonl`: model proposals and runner events.
- `agent_browser_final.json`: final terminate output, if the model terminates.

## Stop only the desktop recorder

```bash
cd /data/aayush/task-recorder
docker compose stop
```

This stops only `wootz-desktop-browser-replay-001`. It does not stop the Android recorder, desktop authoring container, or other containers.
