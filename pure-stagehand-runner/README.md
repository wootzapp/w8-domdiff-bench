# Pure Stagehand Runner

This folder runs Stagehand exactly as a normal Stagehand user would run it.

It is an isolated subfolder inside `/data/aayush/task-recorder` and does not use Wootz ChromiumRL, Wootz CDP, `ChromiumRL.getAgentObservation`, `ChromiumRL.saveDOMState`, or `ChromiumRL.compareDOMState`.

## What this runner uses

```text
User task
  → Stagehand agent
  → Stagehand native DOM / ARIA / screenshot tools
  → Stagehand internal act / observe / extract LLM calls
  → Stagehand local browser
  → task artifacts in tasks/<task-id>/
```

Stagehand does not natively create ChromiumRL-style DOM diff files. This runner therefore records Stagehand's real inputs, outputs, observations, screenshots, and inference logs instead of inventing a fake `dom_diff.json`.

No shortcuts are used here:

- no ChromiumRL calls;
- no fake DOM diff;
- no replacement DOM/refinement logic;
- no hardcoded task behavior;
- no invented model-context files.

Internal Stagehand LLM calls for `act`, `observe`, and `extract` are recorded by Stagehand's own `logInferenceToFile` mechanism. The outer browser-agent model prompt is saved per step as `model_request.json` and `model_prompt.txt`. The outer browser-agent step payload is captured through Stagehand/AI SDK callbacks. `STAGEHAND_EXPERIMENTAL=true` is used only because Stagehand requires it for callbacks; it does not replace Stagehand's native page-understanding logic.

## Setup

```bash
cd /data/aayush/task-recorder/pure-stagehand-runner
npm install
cp .env.example .env
nano .env
```

Set at least:

```text
OPENAI_API_KEY=sk-...
STAGEHAND_MODEL=openai/gpt-4.1-mini
BROWSER_LANG=en-US
BROWSER_ACCEPT_LANGUAGE=en-US,en;q=0.9
STAGEHAND_MAX_STEPS=80
```

If you use an OpenAI-compatible gateway, also set:

```text
OPENAI_BASE_URL=...
```

The default `.env.example` also includes `STAGEHAND_SYSTEM_PROMPT`. It is a generic instruction for Stagehand's normal agent to clear blocking cookie/privacy/sign-in/ad/newsletter overlays using visible controls. It is not task-specific logic and does not use hardcoded website selectors.

## Run a task

Visible browser mode is the default. If no display exists, the run script starts Xvfb/openbox/x11vnc automatically.

The default step budget is 80. Override it per run with `--max-steps <number>`.

```bash
cd /data/aayush/task-recorder/pure-stagehand-runner
./scripts/run-task.sh task1 "Go to example.com and summarize the page." --max-steps 80
```

From Windows, open a second CMD window and run the SSH tunnel printed by the script. By default it is:

```powershell
ssh -N -L "[::1]:3992:127.0.0.1:16092" ubuntu@static.235.31.55.162.clients.your-server.de
```

Then open this URL:

```text
http://[::1]:3992/vnc.html?resize=scale&autoconnect=1&path=websockify
```

Keep the browser open after completion:

```bash
./scripts/run-task.sh task1 "Your task here" --max-steps 80 --keep-open
```

## Output structure

Each run creates:

```text
tasks/<task-id>/
├── task.json
├── trajectory.jsonl
├── evidence.jsonl
├── stagehand_logs.jsonl
├── result.json
├── final_answer.json
├── final_page_state.json
├── final_screenshot.png
├── inference_summary/
│   ├── act_summary/
│   ├── observe_summary/
│   └── extract_summary/
└── step_001/
    ├── agent_input.json
    ├── agent_output.json
    ├── model_request.json
    ├── model_prompt.txt
    ├── action.json
    ├── tool_result.json
    ├── page_state.json
    ├── screenshot.png
    ├── evidence.png
    └── aria.txt
```

## File meanings

| File | Meaning |
|---|---|
| `task.json` | Run metadata: task id, prompt, model, mode, max steps. |
| `trajectory.jsonl` | One JSONL record per Stagehand browser-agent step. |
| `evidence.jsonl` | Raw Stagehand evidence events: screenshots, tool completions, observations, final answer. |
| `stagehand_logs.jsonl` | Stagehand logger output. |
| `result.json` | Final `agent.execute()` result returned by Stagehand. |
| `final_answer.json` | Final answer evidence event if Stagehand emitted one. |
| `final_page_state.json` | URL/title/scroll/text preview after the run. |
| `final_screenshot.png` | Final viewport screenshot. |
| `step_XXX/agent_input.json` | Model-step input visible to Stagehand before the outer browser-agent LLM call. |
| `step_XXX/agent_output.json` | Browser-agent LLM/tool result for that step. This also contains the raw request/response event. |
| `step_XXX/model_request.json` | Exact browser-agent model request captured from Stagehand/AI SDK for that step. |
| `step_XXX/model_prompt.txt` | Readable flattened prompt/messages sent to the outer browser-agent model for that step. |
| `step_XXX/action.json` | Stagehand tool/action name, args, and reasoning for the step. |
| `step_XXX/tool_result.json` | Return value from the Stagehand tool. For `act`, this includes the action result sent back to the browser agent. |
| `step_XXX/page_state.json` | URL/title/scroll/text preview after that step. |
| `step_XXX/screenshot.png` | Screenshot captured by this runner after that step. |
| `step_XXX/evidence.png` | Latest screenshot emitted by Stagehand evidence callback, when available. |
| `step_XXX/aria.txt` | Latest Stagehand ARIA/hybrid tree observation, when Stagehand emits it. |
| `inference_summary/*` | Stagehand internal LLM call logs for `act`, `observe`, and `extract`. These are generated by Stagehand's `logInferenceToFile` option. |

## Browser launch troubleshooting

If you see an error like:

```text
connect ECONNREFUSED 127.0.0.1:<port>
```

it usually means Stagehand launched local Chromium but Chromium exited before its DevTools port became available.

On a remote Linux server, the common cause is visible Chrome without a display:

```text
HEADLESS=false
```

without a GUI display. This runner starts Xvfb automatically when `HEADLESS=false` and no `DISPLAY` is set.

It also starts noVNC automatically, so you can watch the browser through a URL instead of a VNC app.

Use:

```bash
./scripts/run-task.sh <task-id> "<task>" --max-steps 80
```

If you already have a display, export `DISPLAY` before running the task and the script will use it instead of starting its own Xvfb.

## Language and blocker handling

This runner sets browser language through normal Chromium launch options:

```text
BROWSER_LANG=en-US
BROWSER_ACCEPT_LANGUAGE=en-US,en;q=0.9
STAGEHAND_MAX_STEPS=80
```

This reduces cases where Google or shopping/travel sites open in German because the server is in Germany. It does not guarantee English if the website ignores browser language or uses account/location settings.

For popups, the runner passes a generic `STAGEHAND_SYSTEM_PROMPT` to Stagehand's agent. This tells the agent to handle blocking cookie/privacy/sign-in/ad/newsletter overlays before continuing. It does not click fixed selectors and does not contain website-specific rules.

## Why there is no Stagehand `third_party/` folder here

This pure runner uses the official `@browserbasehq/stagehand` npm package from `node_modules`, which is how a normal Stagehand project is expected to run.

The repo-level `third_party/stagehand` folder is used by the separate ChromiumRL-based Stagehand runner. It is patched for Wootz/ChromiumRL integration. Using that patched folder here would mix ChromiumRL behavior into the pure Stagehand comparison runner, so this folder intentionally does not use it.

## Important difference from ChromiumRL runner

Pure Stagehand:

```text
Stagehand native page context → Stagehand agent decisions → Stagehand local browser actions
```

ChromiumRL Stagehand runner:

```text
ChromiumRL page context → Stagehand agent decisions → Wootz browser actions → ChromiumRL verifier artifacts
```

Use this folder only when you want pure Stagehand behavior for comparison or standalone Stagehand runs.
