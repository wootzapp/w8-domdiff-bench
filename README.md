# Task Recorder

This active folder is for Wootz browser task recording and ChromiumRL verifier artifacts.

## Browser

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

## Official Agent Browser runtime

The active automated runner uses the official Vercel Agent Browser native CLI (`agent-browser` 0.33.2) for browser input. Its Linux binary and version-matched skill files are stored under `agent_browser/official_runtime/`. The runner does not use a replacement action implementation.

The workflow is split deliberately:

- ChromiumRL supplies the model observation and all verifier artifacts (`getAgentObservation`, DOM state, DOM diff, screenshot, interactions, and touch traces).
- The official Agent Browser native CLI connects to the same Wootz CDP endpoint and executes navigation, clicks, typing, keys, scrolling, and waits.
- `agent_browser/desktop_agent.py` is only the bridge/recording loop: it translates the model JSON action into an official CLI command and records the resulting ChromiumRL state.

The vendored runtime came from the official repository: https://github.com/vercel-labs/agent-browser.

## Agent-browser + ChromiumRL

Configure the single environment file:

```bash
nano .env.agent-browser
```

Set at least:

```text
AGENT_BROWSER_MODEL=gpt-4.1
```

Start or update the desktop container (Compose must be told to use the single environment file):

```bash
docker compose --env-file .env.agent-browser up -d
```

Run the automated task:

```bash
./scripts/run-agent-browser.sh <task-id> "Your task prompt here."
```

Example:

```bash
./scripts/run-agent-browser.sh task-agentbrowser-test \
  "Go to Best Buy and find a 55-inch Samsung 4K smart TV available for pickup near ZIP code 10001. Report the product name, price, model number, and pickup availability."
```

## Recorded artifacts

Each recorded step stores ChromiumRL verifier artifacts under:

```text
tasks/<task-id>/step_XXX/
├── action.json
├── step.json
├── before/
│   ├── chromiumrl_dom.json
│   ├── chromiumrl_agent_observation.json
│   ├── page_state.json
│   └── screenshot.png
├── after/
│   ├── chromiumrl_dom.json
│   ├── chromiumrl_agent_observation.json
│   ├── page_state.json
│   └── screenshot.png
├── dom_diff.json
├── dom_diff_summary.json
└── verifier_action.json
```

Main ChromiumRL protocols used for verifier artifacts:

```text
ChromiumRL.getAgentObservation
ChromiumRL.saveDOMState
ChromiumRL.compareDOMState
ChromiumRL.getTouchTraces
```

