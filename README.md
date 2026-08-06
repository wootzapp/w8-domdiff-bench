# Task Recorder

This repository runs the Wootz desktop browser container and records automated browser trajectories with ChromiumRL evidence.

The current default runner is `agent_browser/desktop_agent.py`. Despite the historical folder name, it no longer shells out to an external `agent-browser` binary. It uses the model for next-action selection, ChromiumRL/JS observations for page state, and raw CDP `Input.*` / `Page.navigate` commands for execution.

## Start the desktop browser

```bash
cd /data/aayush/task-recorder
docker compose --env-file .env.agent-browser up -d
./scripts/doctor.sh
```

Desktop browser endpoints:

```text
CDP:   http://127.0.0.1:49325
noVNC: 127.0.0.1:16181
VNC:   127.0.0.1:15901
```

If you need to view the browser from your laptop, create the tunnel from Windows CMD/PowerShell:

```powershell
ssh -N -L "[::1]:39081:127.0.0.1:16181" ubuntu@static.235.31.55.162.clients.your-server.de
```

Then open:

```text
http://[::1]:39081/vnc.html?resize=scale&autoconnect=1&path=websockify
```

If that local port is blocked on Windows, change only the first port, for example `39082:127.0.0.1:16181`, and open `http://[::1]:39082/vnc.html?resize=scale&autoconnect=1&path=websockify`.

## Configure model access

Edit the environment file:

```bash
nano .env.agent-browser
```

Set at least:

```text
AGENT_BROWSER_MODEL=gpt-4.1
OPENAI_API_KEY=<your key>
```

Do not commit `.env.agent-browser` if it contains secrets.

## Run an automated task

Preferred flag form:

```bash
./scripts/run-agent-browser.sh \
  --task-id task-example \
  --task "Go to books.toscrape.com, open the first book in Travel, and report its price." \
  --max-steps 40 \
  --yes
```

Deprecated positional form still works:

```bash
./scripts/run-agent-browser.sh task-example \
  "Go to books.toscrape.com, open the first book in Travel, and report its price." \
  --max-steps 40 \
  --yes
```

Useful options:

```text
--observation-source auto        ChromiumRL observation with JS fallback. Default.
--observation-source chromiumrl  ChromiumRL only.
--observation-source js          JS-only observation for A/B debugging.
--step-timeout 120               Max seconds per recorded step.
--load-timeout 12                Max bounded page readiness wait after an action.
--max-duration-seconds 900       Max whole-run duration.
--enable-runtime-domain          Debug-only; default runs do not call Runtime.enable.
```

## Current artifact layout

Each run writes the reduced v3 layout:

```text
tasks/<task-id>/
├── manifest.json
├── log.jsonl
├── step_001/
│   ├── action.json
│   ├── observation_before.json.gz
│   ├── observation_after.json.gz
│   ├── diff.json
│   ├── before.png
│   └── after.png
└── final_state/
    ├── dom.json.gz
    ├── observation.json
    └── screenshot.png
```

File meanings:

| File | Meaning |
|---|---|
| `manifest.json` | Run metadata: task id, prompt, runner, model/config, start time. |
| `log.jsonl` | Unified trajectory/event log. Includes model requests/responses, actions, capture notes, warnings, and final status. |
| `step_XXX/action.json` | Human-readable action record, including normalized verifier action fields like `url` for navigation and `key` for keypresses. |
| `step_XXX/observation_before.json.gz` | Compressed model-facing observation before the action. |
| `step_XXX/observation_after.json.gz` | Compressed model-facing observation after the action. |
| `step_XXX/diff.json` | Recorder-computed diff between before/after observations. Movement-only scroll noise is excluded from interactive changes. |
| `step_XXX/before.png`, `after.png` | Screenshots around the action. |
| `final_state/dom.json.gz` | Final compressed ChromiumRL DOM snapshot, captured only once at the end. |
| `final_state/observation.json` | Final observation. |
| `final_state/screenshot.png` | Final screenshot. |

Removed old heavy artifacts include per-step `chromiumrl_dom.json`, `dom_diff.json` from `ChromiumRL.compareDOMState`, `chromiumrl_signals.json`, `interaction_capture.json`, `all_targets/`, `model_inputs/`, separate `step.json`, and separate `verifier_action.json`.

## ChromiumRL and CDP protocols used

Observation and evidence:

```text
ChromiumRL.getAgentObservation
ChromiumRL.saveDOMState        final_state only
ChromiumRL.getTouchTraces      coordinate actions only
```

Recovery and fallback:

```text
Target.attachToTarget / Target.detachFromTarget
Page.enable
Page.captureScreenshot
Runtime.evaluate               page state, JS fallback, scroll/fill verification
```

Action execution:

```text
Page.navigate
Input.dispatchMouseEvent
Input.dispatchKeyEvent
Input.insertText
```

Default runs intentionally do not call `Runtime.enable`.

## Replay a run log

```bash
python3 scripts/replay-log.py tasks/<task-id>
```

This reconstructs a readable trajectory from `log.jsonl` alone.

## Diagnostics and reports

V3 diagnostic evidence is stored in:

```text
diagnostics/v3/
```

The implementation report is:

```text
PHASE_V3_REPORT.md
```

The old-to-new artifact mapping is:

```text
MIGRATION.md
```
