# Task Recorder

This repository runs the Wootz desktop browser container and records automated browser trajectories with ChromiumRL evidence.

The current default runner is `agent_browser/desktop_agent.py`. Despite the historical folder name, it does not shell out to an external `agent-browser` binary. It uses:

- an LLM for next-action selection;
- ChromiumRL / JS observations for model-visible page state;
- raw CDP `Input.*` and `Page.navigate` commands for execution;
- real ChromiumRL DOM snapshots for verifier-facing `dom_diff.json`.

`dom_diff.json` is the primary verifier artifact.

## QUICKSTART

From a clean checkout:

```bash
cd /data/aayush/task-recorder
docker compose --env-file .env.agent-browser up -d
```

Wait for the container healthcheck, then run the doctor:

```bash
for i in {1..60}; do
  health_status=$(docker inspect -f '{{.State.Health.Status}}' wootz-desktop-browser-replay-001 2>/dev/null || true)
  [ "$health_status" = healthy ] && break
  sleep 1
done

docker compose --env-file .env.agent-browser ps
./scripts/doctor.sh
```

Default endpoints:

| Endpoint | Host URL / port | Container port | Purpose |
|---|---:|---:|---|
| CDP | `http://127.0.0.1:49325` | `9226` proxy to internal `9225` | Recorder / automation control |
| noVNC | `http://127.0.0.1:16181/vnc.html?resize=scale&autoconnect=1&path=websockify` | `6080` | Visual browser access |
| VNC | `127.0.0.1:15901` | `5900` | Direct VNC client access |

If you are viewing the browser from your laptop, create the SSH tunnel from Windows CMD or PowerShell:

```powershell
ssh -N -L "[::1]:39081:127.0.0.1:16181" ubuntu@static.235.31.55.162.clients.your-server.de
```

Then open:

```text
http://[::1]:39081/vnc.html?resize=scale&autoconnect=1&path=websockify
```

If Windows refuses that local port, change only the first port, for example:

```powershell
ssh -N -L "[::1]:39082:127.0.0.1:16181" ubuntu@static.235.31.55.162.clients.your-server.de
```

Then open:

```text
http://[::1]:39082/vnc.html?resize=scale&autoconnect=1&path=websockify
```

Configure model access:

```bash
nano .env.agent-browser
```

Set:

```text
AGENT_BROWSER_MODEL=gpt-4.1
OPENAI_API_KEY=<your key>
```

Do not commit `.env.agent-browser` if it contains secrets.

Run a task:

```bash
./scripts/run-agent-browser.sh \
  --task-id task-example \
  --task "Go to books.toscrape.com, open the first book in Travel, and report its price." \
  --yes
```

The wrapper also supports the older positional form, but new usage should prefer flags:

```bash
./scripts/run-agent-browser.sh task-example \
  "Go to books.toscrape.com, open the first book in Travel, and report its price." \
  --yes
```

Output lands in:

```text
tasks/<task-id>/
```

Resume semantics:

- Use `--resume` only when continuing the same task folder.
- Reuse the exact same `--task-id`.
- Reuse the exact same task prompt. The runner validates against the existing task directory; changing the prompt while resuming makes the trajectory ambiguous.
- Resume preserves the existing browser target instead of doing preflight tab cleanup.

Example:

```bash
./scripts/run-agent-browser.sh \
  --task-id task-example \
  --task "Go to books.toscrape.com, open the first book in Travel, and report its price." \
  --resume \
  --yes
```

## CLI FLAGS

This section is generated from the current `argparse` surface in `agent_browser/desktop_agent.py`. Defaults are parser defaults unless noted. `scripts/run-agent-browser.sh` additionally supplies `--cdp-url http://127.0.0.1:49325`, `--max-steps 80`, and `--yes` when omitted.

### Required task flags

| Flag | Default | Meaning |
|---|---:|---|
| `--task-id` | required | Task folder name under `--output-root`. |
| `--task` | required | Natural-language task prompt sent to the model. |
| `--help` | n/a | Show parser help and exit. |

### Browser / target / output

| Flag | Default | Meaning |
|---|---:|---|
| `--cdp-url` | `http://127.0.0.1:49325` | CDP endpoint. |
| `--target-url-contains` | `""` | Optional target-selection filter. |
| `--output-root` | `tasks` | Parent directory for task outputs. |
| `--resume` | `false` | Append to an existing task directory and reuse the current target. |
| `--fresh-tab-url` | `about:blank` | Initial URL for a new non-resume task tab. |
| `--fresh-tab-mode` | `new_tab` | `new_tab`, `new_context`, or `reuse`. `new_tab` keeps one browser window; `new_context` isolates browser data but may create another OS window. |
| `--keep-browser-data` | `false` | Preserve browser data instead of using the runner's default isolation behavior. |
| `--no-preflight-cleanup` | `false` | Preserve existing tabs before a non-resume task. Normally leave this off. |
| `--browser-locale` | `$BROWSER_LANG` or `en-US` | Locale override applied once per target. |
| `--accept-language` | `$BROWSER_ACCEPT_LANGUAGE` or `en-US,en;q=0.9` | Accept-Language override applied once per target. |

### Model / action loop

| Flag | Default | Meaning |
|---|---:|---|
| `--yes` | `false` parser, auto-added by wrapper | Execute model actions without interactive approval. |
| `--max-steps` | `80` | Maximum action steps. |
| `--max-duration-seconds` | `900.0` | Whole-run duration cap. |
| `--step-timeout` | `120.0` | Per-step timeout. |
| `--load-timeout` | `12.0` | Bounded readiness wait after each action. |
| `--settle-seconds` | `1.0` | Deprecated; load readiness is controlled by `--load-timeout`. |
| `--model-timeout` | `120.0` | LLM request timeout. |
| `--input-timeout` | `8.0` | CDP input/action command timeout. |
| `--command-timeout` | `90.0` | General CDP connection/fetch timeout. Individual commands use stricter budgets internally. |

### Observation

| Flag | Default | Meaning |
|---|---:|---|
| `--observation-source` | `auto` | `auto`, `chromiumrl`, `js`, or `cross_check`. `auto` uses ChromiumRL with JS fallback. |
| `--observation-max-elements` | `250` | Max elements requested from `ChromiumRL.getAgentObservation`. |
| `--max-elements` | `120` | Max rendered elements in the model-facing snapshot. |
| `--strict-chromiumrl-observation` | `false` | Send only the primary observation text; disables supplemental visible text. |

### DOM capture and diff

| Flag | Default | Meaning |
|---|---:|---|
| `--dom-capture` | `slim` | `slim`, `full`, or `none`. `slim` writes projected DOM states and `dom_diff.json`. `full` additionally writes raw per-step DOM audit files. `none` is debug-only and not verifier-safe. |
| `--final-state-dom` | `both` | `full`, `slim`, or `both` for final-state DOM capture. |
| `--dom-diff-max-entries` | `200` | Per-list emitted-entry cap. True totals are still recorded. |
| `--dom-diff-verbosity` | `compact` | `compact` writes the short-id compact diff. `full` writes the expanded debug form. |
| `--collapse-text-chars` | `2000` | Text budget for collapsed subtree/document summaries. |
| `--validate-diff` | `false` | Compare local compact diff counts against ChromiumRL `compareDOMState` operations. |
| `--keep-observations` | `false` | Write per-step model-facing observations and observation diff files. |
| `--capture-all-targets` | `false` | Legacy debug option; ignored by the reduced current layout. |
| `--chromiumrl-full-tracing` | `false` | Enable legacy heavier ChromiumRL tracing probes. |

There is no `--dom-capture-format` flag in the current parser. DOM state files are written as gzip JSON. For uncompressed debugging, decompress them with `gzip -dc` or Python as shown in [READING THE ARTIFACTS](#reading-the-artifacts).

### Screenshots and bundles

| Flag | Default | Meaning |
|---|---:|---|
| `--screenshot-source` | `cdp` | `cdp` or `none`. |
| `--screenshot-format` | `jpeg` | `jpeg`, `png`, or `webp`. |
| `--screenshot-quality` | `70` | JPEG/WebP quality. |
| `--screenshot-mode` | `after_only` | `after_only` writes `after.jpg`; `both` also writes `before.jpg`. |
| `--screenshot-container` | `wootz-desktop-browser-replay-001` | Container used for health/diagnostic screenshot context. |
| `--verifier-bundle` | `false` | Write `<task-id>_verifier_bundle.zip`. |

### Debug-only CDP behavior

| Flag | Default | Meaning |
|---|---:|---|
| `--enable-runtime-domain` | `false` | Debug only. Default runs do not call `Runtime.enable`. |

## ARTIFACT LAYOUT

Each run writes a flat verifier layout. A step directory has no subdirectories.

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
│   ├── dom_diff.txt
│   └── page_state.json
└── final_state/
    ├── dom_full.json.gz
    ├── dom_state.json.gz
    ├── observation.json
    ├── page_state.json
    └── screenshot.jpg
```

Default `--screenshot-mode after_only` writes 7 files per step: `action.json`, `after.jpg`, `dom_after.json.gz`, `dom_before.json.gz`, `dom_diff.json`, `dom_diff.txt`, and `page_state.json`. `--screenshot-mode both` adds `before.jpg`, for 8 files.

`--keep-observations` adds these optional top-level step files:

```text
observation_before.json.gz
observation_after.json.gz
observation_diff.json
```

### File-tier table

| File | Tier | Meaning |
|---|---|---|
| `manifest.json` | Required | Run metadata: task id, runner, config, browser health at start, and completion metadata. |
| `log.jsonl` | Required | Unified event stream: model requests/responses, actions, cleanup/teardown, capture notes, warnings, and final status. |
| `agent_browser_final.json` | Required | Final claim being verified: status, final answer, terminate action, termination reason, completed steps, and grounding check. |
| `VERIFIER.md` | Required | Human-readable guide included with each task folder. |
| `step_NNN/action.json` | Required | Normalized action record and verifier-action fields, including `url` for navigation and `key` for keypresses. |
| `step_NNN/page_state.json` | Required | After-step URL/title/viewport state. This is the state resulting from the action. |
| `step_NNN/dom_diff.json` | Required / primary verifier artifact | Refined real DOM diff for this step. |
| `step_NNN/dom_diff.txt` | Required / human-readable verifier artifact | Text rendering generated from the same diff builder as `dom_diff.json`; useful for review and quick greps. |
| `step_NNN/dom_before.json.gz` / `dom_after.json.gz` | Fallback verifier evidence | Slim DOM projections used to compute `dom_diff.json`. Kept for step self-containment. |
| `step_NNN/after.jpg` / `before.jpg` | Human-review evidence | Screenshots. `before.jpg` exists only with `--screenshot-mode both`. |
| `step_NNN/observation_before.json.gz` / `observation_after.json.gz` | Not verifier-facing | Model-facing observations, written only with `--keep-observations`. These are not DOM snapshots. |
| `step_NNN/observation_diff.json` | Not verifier-facing | Observation-based progress/debug diff, written only with `--keep-observations`. |
| `final_state/dom_full.json.gz` | Fallback verifier evidence | Raw final `ChromiumRL.saveDOMState`, gzipped. Contains full raw node payloads and full `keyStyles`. |
| `final_state/dom_state.json.gz` | Fallback verifier evidence | Slim final DOM projection. Not interchangeable with the raw DOM. |
| `final_state/page_state.json` | Required final evidence | Final URL/title/viewport state. |
| `final_state/observation.json` | Not verifier-facing by default | Final `getAgentObservation` payload: interactive elements only, capped by `--observation-max-elements`. |
| `final_state/screenshot.jpg` | Human-review evidence | Final screenshot. Extension follows `--screenshot-format`. |

Final-state DOM diff is intentionally absent. Use the last step's `dom_diff.json`; it covers the final transition.

Canonical example on disk:

```text
tasks/task-v7-books-check-003
```

Validate a task folder:

```bash
python3 scripts/verify-example.py tasks/<task-id>
```

## DOM DIFF: WHAT IT IS AND HOW IT IS REFINED

`dom_diff.json` is the refined compact DOM diff. `dom_diff.txt` is the human-readable rendering of the same facts, generated from the same builder. There is no separate compacted diff file.

Do not confuse these:

- `dom_before.json.gz`, `dom_after.json.gz`, and `final_state/dom_state.json.gz` are compressed slim DOM projections.
- `final_state/dom_full.json.gz` is a compressed raw DOM snapshot.
- `dom_diff.json` is the compact semantic diff computed from DOM projections.
- `dom_diff.txt` is a line-oriented rendering of `dom_diff.json`, not a separate evidence source.

### 1. Capture: `capture_state()` and `chromiumrl_call()`

The runner captures DOM state with `ChromiumRL.saveDOMState` through `capture_state()` in `recorder.py`. ChromiumRL calls go through `chromiumrl_call()`, which can rebind/retry and records failures instead of silently hanging the run.

Measured examples from existing benchmark runs:

| Page | Raw `saveDOMState` JSON | Raw gzip | Slim gzip |
|---|---:|---:|---:|
| books.toscrape.com final page | 326,535 bytes | 15,235 bytes | 7,135 bytes |
| Wikipedia article final page | 9,703,807 bytes | 339,239 bytes | 189,752 bytes |

Exact sizes depend on the page and step. `dom_diff.json` is usually much smaller because it only emits semantic changes.

### 2. Slim projection: `project_dom_state()`

`project_dom_state()` turns raw ChromiumRL nodes into a verifier-focused projection.

Kept per node:

- key `k`;
- `tag`;
- normalized `text`, capped at 200 characters;
- semantic `attrs`;
- visibility booleans `vis` and `vp`;
- six style properties: `display`, `visibility`, `opacity`, `color`, `backgroundColor`, `textDecoration`;
- structural fields used for collapse/debug: `nodeId`, `parentId`, `siblingIndex`, `parent`.

Discarded:

- comments, scripts, styles, noscript, template nodes;
- whitespace-only text nodes;
- geometry/bounds;
- z-index/layout details;
- most CSS;
- raw `keyStyles` bulk.

The raw DOM can carry roughly 19 `keyStyles` properties per node. The slim projection keeps 6 because verifier assertions usually need visibility/color/text-decoration state, not layout typography such as margins, padding, font size, or line height.

### 3. Diff key: `_node_raw_key()` and `build_structural_paths()`

The key order is:

```text
stablePath -> cssSelector -> xpath -> structural parentId/siblingIndex path
```

`_node_raw_key()` chooses the best explicit key. `build_structural_paths()` reconstructs a fallback structural path when explicit keys are missing. Duplicate keys get a numeric suffix so the projection remains addressable.

### 4. Semantic attributes and state classes: `semantic_attrs()`

`semantic_attrs()` keeps attributes that are useful for verification:

```text
id, href, src, value, checked, selected, disabled, readonly, required,
type, name, placeholder, title, alt, role, data-testid, and every aria-*
```

Most `class` values are discarded. Only state-like class tokens are kept:

```text
active, current, selected, checked, open, expanded, collapsed, disabled,
error, invalid, success, hidden, show, star, rating
```

This keeps common state evidence such as selected tabs, active pagination, error states, and star ratings while discarding styling classes that are not verifier evidence.

### 5. Form property enrichment: `collect_form_control_state()` and `enrich_dom_with_form_state()`

Some important form state is a live DOM property, not an HTML attribute. Examples: input `value`, checkbox `checked`, option `selected`.

The recorder collects this through `Runtime.evaluate` in `collect_form_control_state()`, then merges it into the DOM before projection with `enrich_dom_with_form_state()`.

Enriched values carry provenance:

```json
{"v": "true", "src": "prop"}
```

Each `dom_diff.json` has an `enrichment` block. If `enrichment.ok` is false for a form step, a verifier should treat missing form-property changes as inconclusive rather than proof that nothing changed.

Sensitive values whose field metadata looks like token/session/auth/password data are redacted.

### 6. Geometry suppression: `classify_projected_change()`

Geometry is intentionally excluded from semantic change detection. Bounds and center points change constantly during scroll, reflow, responsive layout, lazy loading, and animation. Including them makes a scroll look like thousands of changed nodes.

The diff compares text, semantic attributes, selected visibility state, and the small style subset. Viewport membership alone is not treated as a semantic DOM change.

### 7. Subtree collapse: `collapse_subtree_entry()`

When an entire subtree is added or removed, the diff emits the root instead of every descendant.

Example: a cookie modal appears with 487 descendant nodes. Instead of emitting hundreds of nodes, `dom_diff.json` emits one collapsed root like:

```json
{
  "k": "html > body > div#cookie-dialog",
  "tag": "div",
  "role": "dialog",
  "descendant_count": 487,
  "visible_text": "We use cookies ... Accept all Manage preferences",
  "interactive_descendants": [
    {"tag": "button", "text": "Accept all"},
    {"tag": "button", "text": "Reject all"}
  ]
}
```

The text budget is controlled by `--collapse-text-chars`.

### 8. Cross-document short-circuit: `detect_cross_document()`

For a cross-document navigation, structural node paths can collide across unrelated pages. A product listing and a product detail page may both contain paths like `html > body > div.container > ...`, but those nodes do not represent the same content.

When `detect_cross_document()` sees a loader change or URL path/origin change, node-level matching is abandoned. In compact mode the diff emits:

- `cross_document: true`;
- `navigation` metadata;
- `document` counts for removed/added nodes;
- `text_delta`;
- `top_actions`;
- no node-level `changed` entries.

For same-document steps, node-level added/removed/changed diffing is used. Use `--dom-diff-verbosity full` only for debugging the expanded internal representation.

### 9. Scroll-artifact flagging: `classify_projected_change()`

`active` and `current` classes are useful verifier evidence for tabs/nav/pagination, so they are kept. But on scroll, some pages update `active` / `current` only because a scroll-spy nav changed.

If the action is `scroll` and the only change is active/current class churn, the entry is emitted under `flagged_changes` with `likely_scroll_artifact: true`, not under semantic `changed`.

### 10. Honest truncation: `build_compact_dom_diff()`

`--dom-diff-max-entries` caps emitted entries per list, but totals are always reported:

```json
{
  "stats": {
    "added_total": 512,
    "added_emitted": 200,
    "removed_total": 3,
    "removed_emitted": 3,
    "changed_total": 41,
    "changed_emitted": 41,
    "truncated": true
  }
}
```

A verifier can tell whether it is seeing the complete diff or a semantic top slice.

## COVERAGE LIMITATIONS

Native ChromiumRL DOM and observation traversal are main-frame scoped. Source review found `saveDOMState` and `getAgentObservation` start from `inspected_frames_->Root()->GetDocument()` in Chromium source:

```text
third_party/blink/renderer/core/inspector/inspector_chromiumrl_agent.cc:1403
third_party/blink/renderer/core/inspector/inspector_chromiumrl_agent.cc:2959-3020
```

The recorder declares this in every `dom_diff.json` under `frames`.

Frame behavior:

- main frame: captured by ChromiumRL;
- same-origin iframes: merged through JS projection when available and marked `source: "js_iframe"`;
- cross-origin iframes: declared in `frames.child_frame_urls`, but their DOM is not captured;
- frame coverage is reported as `main_frame_only` or `main_frame_plus_same_origin_iframes`.

Shadow DOM:

- current probe result is `shadow_dom: "none"`;
- open and closed shadow-root content should be treated as not captured by verifier evidence unless a future probe/source change says otherwise.

Observation files:

- `getAgentObservation` is not DOM evidence;
- it is model-facing, interactive-element-focused, and capped by `--observation-max-elements`;
- `observation_diff.json` is for agent-loop debugging, not verifier proof;
- do not use `observation_diff.json` as a replacement for `dom_diff.json`.

## READING THE ARTIFACTS

`.json.gz` files are normal JSON compressed with gzip.

Read with shell tools:

```bash
gzip -dc tasks/<task-id>/step_001/dom_before.json.gz | jq '.url, .nodes[0]'
gzip -dc tasks/<task-id>/final_state/dom_full.json.gz | jq '.nodes | length'
```

If your system has `zcat` wired to gzip:

```bash
zcat tasks/<task-id>/step_001/dom_after.json.gz | jq '.key_population'
```

Python one-liner:

```bash
python3 -c 'import gzip,json,sys; print(json.load(gzip.open(sys.argv[1],"rt"))["url"])' \
  tasks/<task-id>/step_001/dom_after.json.gz
```

There is no `--dom-capture-format json` flag in the current runner. For uncompressed debugging, decompress a `.json.gz` file into `/tmp`:

```bash
gzip -dc tasks/<task-id>/step_001/dom_after.json.gz > /tmp/dom_after.json
```

Raw vs slim final DOM:

- `final_state/dom_full.json.gz` is the raw ChromiumRL DOM snapshot. It can contain comments, script/style nodes, and full raw `keyStyles`.
- `final_state/dom_state.json.gz` is the slim projection. It has reduced CSS/style state and removed non-semantic nodes.
- They are not interchangeable.

Validate a task folder:

```bash
python3 scripts/verify-example.py tasks/<task-id>
```

Create a verifier bundle:

```bash
python3 scripts/export-verifier-bundle.py tasks/<task-id>
```

Or generate it during a run:

```bash
./scripts/run-agent-browser.sh \
  --task-id task-example \
  --task "..." \
  --verifier-bundle \
  --yes
```

## TROUBLESHOOTING

### Tasks hang or browser CPU is high

Run:

```bash
./scripts/reset-browser.sh
```

That restarts the browser container, waits for CDP, then prints target count and CPU/memory.

Manual checks:

```bash
curl -fsS http://127.0.0.1:49325/json/list | jq 'length'
docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' wootz-desktop-browser-replay-001
```

The runner also performs a health preflight before connecting. If page target count is over 20 or container CPU is above 150%, it prints and logs a warning.

### Existing tabs and preflight cleanup

Before a non-resume task, the runner enumerates page targets and closes stale page tabs, keeping one active page target. This prevents abandoned renderers from accumulating across task runs.

Use this only if you deliberately need to preserve existing tabs:

```bash
--no-preflight-cleanup
```

`--resume` skips cleanup because it depends on the existing task target.

### CDP / ChromiumRL health

Run:

```bash
./scripts/doctor.sh
```

Doctor checks CDP reachability and ChromiumRL methods. Use it after restarting the container or when captures begin timing out.

### Resume after a crash

Use the same task id and exact same prompt with `--resume`.

If a crash left an incomplete step directory, the runner renames it to:

```text
step_NNN.partial.<timestamp>
```

Then it continues at the next clean step number. Do not manually merge partial step directories into verifier data.

### See what happened in a run

```bash
python3 scripts/replay-log.py tasks/<task-id>
```

This reconstructs a readable trajectory from `log.jsonl`.

## SCRIPTS INVENTORY

| Script | Purpose |
|---|---|
| `scripts/run-agent-browser.sh` | Main wrapper for automated ChromiumRL-backed agent runs. Accepts flag form and deprecated positional form. |
| `scripts/doctor.sh` | CDP/ChromiumRL health check against the configured browser endpoint. |
| `scripts/container-start.sh` | Container entrypoint that starts Wootz Chrome, noVNC, VNC, and the CDP proxy. |
| `scripts/replay-log.py` | Reconstructs a readable trajectory from `log.jsonl`. |
| `scripts/run-diff-benchmarks.py` | Runs DOM-diff benchmark/assertion tasks. |
| `scripts/verify-example.py` | Validates that a task folder matches the current verifier artifact layout. |
| `scripts/export-verifier-bundle.py` | Creates a verifier bundle zip from an existing task folder. |
| `scripts/reset-browser.sh` | Restarts the browser container and prints target count plus CPU/memory once healthy. |

## PROTOCOLS USED

Observation and evidence:

```text
ChromiumRL.getAgentObservation
ChromiumRL.saveDOMState
ChromiumRL.compareDOMState
ChromiumRL.getTouchTraces
```

Recovery and fallback:

```text
Target.getTargets
Target.createTarget
Target.activateTarget
Target.closeTarget
Target.attachToTarget
Target.detachFromTarget
Page.enable
Page.bringToFront
Page.captureScreenshot
Page.getFrameTree
Runtime.evaluate
```

Action execution:

```text
Page.navigate
Input.dispatchMouseEvent
Input.dispatchKeyEvent
Input.insertText
```

Default runs intentionally do not call `Runtime.enable`.

## CURRENT DOCUMENTATION VS HISTORY

`README.md` and `MIGRATION.md` are the current operational documents. Historical build reports live under:

```text
docs/history/
```

If a historical report contradicts this README, this README describes the current code.
