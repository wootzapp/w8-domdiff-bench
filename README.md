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
--observation-source cross_check ChromiumRL primary plus JS count logging every step.
--screenshot-format jpeg        Default screenshot encoding. Use png/webp if needed.
--screenshot-quality 70         Default JPEG/WebP quality.
--screenshot-mode after_only    Default; use both to write before+after images.
--step-timeout 120               Max seconds per recorded step.
--load-timeout 12                Max bounded page readiness wait after an action.
--max-duration-seconds 900       Max whole-run duration.
--enable-runtime-domain          Debug-only; default runs do not call Runtime.enable.
```

## Current artifact layout

Each run writes the v5 DOM-diff layout. The DOM diff is the primary verifier artifact; observations and screenshots are supporting evidence.

```text
tasks/<task-id>/
├── manifest.json
├── log.jsonl
├── step_001/
│   ├── action.json
│   ├── observation_before.json.gz
│   ├── observation_after.json.gz
│   ├── dom_before.json.gz
│   ├── dom_after.json.gz
│   ├── dom_diff.json
│   ├── observation_diff.json
│   └── after.jpg              # default; before.jpg also appears with --screenshot-mode both
└── final_state/
    ├── dom.json.gz
    ├── observation.json
    └── screenshot.jpg
```

File meanings:

| File | Meaning |
|---|---|
| `manifest.json` | Run metadata: task id, prompt, runner, model/config, start time. |
| `log.jsonl` | Unified trajectory/event log. Includes model requests/responses, actions, capture notes, warnings, and final status. |
| `step_XXX/action.json` | Human-readable action record, including normalized verifier action fields like `url` for navigation and `key` for keypresses. |
| `step_XXX/observation_before.json.gz` / `observation_after.json.gz` | Compressed model-facing observations before/after the action. These come from ChromiumRL observation or JS fallback and are not the DOM diff source. |
| `step_XXX/dom_before.json.gz` / `dom_after.json.gz` | Slim projections of `ChromiumRL.saveDOMState`. These preserve semantic text, semantic attributes, visibility, viewport flags, and selected state-ish styles/classes. |
| `step_XXX/dom_diff.json` | Compact semantic DOM diff computed from real slim DOM projections. This is the verifier artifact. It includes cross-document mode, frame coverage, enrichment provenance, true totals, emitted counts, and `truncated`. |
| `step_XXX/observation_diff.json` | Observation-based interactive-element diff. This replaces the old misleading `dom_diff_summary.json` name and is mainly useful for agent-loop/progress detection. |
| `step_XXX/after.jpg` | Default post-action screenshot. With `--screenshot-mode both`, `before.jpg` is also written. Extension follows `--screenshot-format`. |
| `final_state/dom.json.gz` | Final slim DOM projection. If `--dom-capture full` is used, `final_state/dom_raw.json.gz` is also written. |
| `final_state/observation.json` | Final observation. |
| `final_state/screenshot.jpg` | Final screenshot. Extension follows `--screenshot-format`. |

DOM options:

```text
--dom-capture slim            Default. Writes slim DOM projections plus compact dom_diff.json.
--dom-capture full            Also writes raw saveDOMState as dom_before_raw/dom_after_raw/final_state/dom_raw.
--dom-capture none            Disables DOM artifacts; use only for debugging, not verifier data.
--dom-diff-max-entries 200    Per-list emitted-entry cap; true totals are always reported.
--collapse-text-chars 500      Visible-text budget for collapsed subtree/document summaries. Raise to 2000 for audit runs.
--validate-diff               Compare local compact diff counts against ChromiumRL.compareDOMState operations.
--observation-max-elements 250 Raises ChromiumRL.getAgentObservation maxElements/maxInteractiveElements.
--fresh-tab-mode new_tab      Default. Use current browser window with a fresh tab. new_context isolates more but risks OS window ordering/occlusion.
```

Cross-document DOM diffs:

```text
Same-document step       node-level added/removed/changed over slim DOM projections
Cross-document step      document_removed + document_added + text_delta + interactive_added; no node-level changed entries
Iframe coverage          frames block declares child frames; same-origin iframe projected nodes are marked source=js_iframe
Form enrichment          attrs like value/checked/selected may be {"v":"...","src":"prop"}; see enrichment.ok
Scroll artifacts         active/current-only class churn on scroll is reported under flagged_changes, not changed
```

## ChromiumRL and CDP protocols used

Observation and evidence:

```text
ChromiumRL.getAgentObservation
ChromiumRL.saveDOMState        before/after every step when --dom-capture is slim/full
ChromiumRL.compareDOMState     called after each action; timing/summary stored in dom_diff.json source metadata
ChromiumRL.getTouchTraces      coordinate actions only
```

Recovery and fallback:

```text
Target.attachToTarget / Target.detachFromTarget
Page.enable
Page.captureScreenshot
Runtime.evaluate               page state, JS fallback, form-control state enrichment, scroll/fill verification
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
