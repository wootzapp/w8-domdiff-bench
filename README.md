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

Each run writes the v8 flat DOM-diff verifier layout. A step directory has no subdirectories. The DOM diff is the primary verifier artifact; `page_state.json` and `agent_browser_final.json` are required verifier evidence.

```text
tasks/<task-id>/
├── manifest.json
├── log.jsonl
├── agent_browser_final.json
├── VERIFIER.md
├── step_001/
│   ├── action.json
│   ├── after.jpg
│   ├── before.jpg              # only with --screenshot-mode both
│   ├── dom_after.json.gz
│   ├── dom_before.json.gz
│   ├── dom_diff.json
│   └── page_state.json
└── final_state/
    ├── dom_full.json.gz
    ├── dom_state.json.gz
    ├── observation.json
    ├── page_state.json
    └── screenshot.jpg
```

Default `--screenshot-mode after_only` writes 6 files per step: `action.json`, `after.jpg`, `dom_after.json.gz`, `dom_before.json.gz`, `dom_diff.json`, and `page_state.json`. `--screenshot-mode both` adds `before.jpg`, for 7 files. No `evidence/` or `agent/` subdirectories are created.

File tiers:

| File | Tier | Meaning |
|---|---|---|
| `manifest.json` | Required | Run metadata: task id, runner, model/config, start health, and timing. |
| `log.jsonl` | Required | Unified trajectory/event log with model requests/responses, actions, cleanup/teardown events, capture notes, warnings, and final status. |
| `agent_browser_final.json` | Required | Final claim being verified: status, final answer, terminate action, termination reason, completed step count, and grounding check. |
| `VERIFIER.md` | Required | Human-readable guide for the task artifact folder. |
| `step_XXX/action.json` | Required | Human-readable action record, including normalized verifier action fields like `url` for navigation and `key` for keypresses. |
| `step_XXX/page_state.json` | Required | After-step URL/title/viewport state. This is the outcome state for the action. |
| `step_XXX/dom_diff.json` | Primary verifier artifact | Compact semantic DOM diff computed from real slim DOM projections. Includes cross-document mode, frame coverage, enrichment provenance, true totals, emitted counts, and `truncated`. |
| `step_XXX/dom_before.json.gz` / `dom_after.json.gz` | Supporting evidence | Slim DOM projections used to compute `dom_diff.json`. Both are kept for step self-containment. |
| `step_XXX/after.jpg` / `before.jpg` | Supporting evidence | Screenshots. `before.jpg` exists only with `--screenshot-mode both`. |
| `step_XXX/observation_before.json.gz` / `observation_after.json.gz` | Opt-in agent/debug evidence | Written only with `--keep-observations`; these are model-facing observations, not DOM snapshots. |
| `step_XXX/observation_diff.json` | Opt-in agent/debug evidence | Written only with `--keep-observations`; useful for progress/debugging only. |
| `final_state/dom_full.json.gz` | Final audit evidence | Raw final `ChromiumRL.saveDOMState`, gzipped. It contains full raw node payloads, including full `keyStyles`; it is not interchangeable with the slim projection. |
| `final_state/dom_state.json.gz` | Final audit evidence | Slim final DOM projection. It has reduced `keyStyles` to 6 properties and removed comments/scripts/styles/whitespace-only text nodes. |
| `final_state/page_state.json` | Required final evidence | Final URL/title/viewport state. |
| `final_state/observation.json` | Agent/debug evidence | Final `getAgentObservation` payload: interactive elements only, capped by `--observation-max-elements`. It is not a DOM snapshot under any setting. |
| `final_state/screenshot.jpg` | Supporting evidence | Final screenshot. Extension follows `--screenshot-format`. |

Final-state DOM diff is intentionally absent. Use the last step's `dom_diff.json`; it covers the final transition.

Canonical example on disk: `tasks/task-v7-books-check-003` has been migrated to the current flat v8 layout.

DOM and artifact options:

```text
--dom-capture slim            Default. Writes per-step slim DOM projections plus compact dom_diff.json.
--dom-capture full            Also writes per-step raw saveDOMState as dom_before_raw/dom_after_raw.json.gz.
--dom-capture none            Disables per-step DOM artifacts; use only for debugging, not verifier data.
--final-state-dom both        Default. Writes final_state/dom_full.json.gz and dom_state.json.gz.
--final-state-dom slim        Final state slim projection only.
--final-state-dom full        Final state raw DOM only.
--dom-diff-max-entries 200    Per-list emitted-entry cap; true totals are always reported.
--collapse-text-chars 500     Visible-text budget for collapsed subtree/document summaries. Raise to 2000 for audit runs.
--validate-diff               Compare local compact diff counts against ChromiumRL.compareDOMState operations.
--keep-observations           Write per-step observation_before/after and observation_diff at the step root.
--observation-max-elements 250 Raises ChromiumRL.getAgentObservation maxElements/maxInteractiveElements.
--verifier-bundle             Writes <task-id>_verifier_bundle.zip containing required and supporting verifier files.
--fresh-tab-mode new_tab      Default. Use current browser window with a fresh tab.
--no-preflight-cleanup        Preserve existing tabs before a non-resume task. Normally leave this off.
```

Browser tab hygiene:

- Non-resume runs close stale page targets before starting unless `--no-preflight-cleanup` is used.
- Every non-resume run closes its own task tab in teardown, including success, failure, max-steps, kill switches, exceptions, and Ctrl-C.
- If tasks start hanging or CPU is high, run `scripts/reset-browser.sh`.

Cross-document DOM diffs:

```text
Same-document step       node-level added/removed/changed over slim DOM projections
Cross-document step      document_removed + document_added + text_delta + interactive_added; no node-level changed entries
Iframe coverage          frames block declares child frames; same-origin iframe projected nodes are marked source=js_iframe
Form enrichment          attrs like value/checked/selected may be {"v":"...","src":"prop"}; see enrichment.ok
Scroll artifacts         active/current-only class churn on scroll is reported under flagged_changes, not changed
```

## Scripts inventory

| Script | Purpose |
|---|---|
| `scripts/run-agent-browser.sh` | Main wrapper for automated ChromiumRL-backed agent runs. |
| `scripts/doctor.sh` | Runs CDP/ChromiumRL health checks against the configured browser endpoint. |
| `scripts/container-start.sh` | Container entrypoint that starts Wootz Chrome/noVNC/CDP proxy. |
| `scripts/replay-log.py` | Reconstructs a readable trajectory from `log.jsonl`. |
| `scripts/run-diff-benchmarks.py` | Runs DOM-diff benchmark/assertion tasks. |
| `scripts/verify-example.py` | Validates that a task folder matches the current v8 verifier artifact layout. |
| `scripts/export-verifier-bundle.py` | Creates a verifier bundle zip from an existing task folder. |
| `scripts/reset-browser.sh` | Restarts the browser container and prints target count plus CPU/memory. |

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
