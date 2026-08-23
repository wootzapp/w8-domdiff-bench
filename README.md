# Browser Task Recorder

Records what a model does in a browser, one action at a time, along with the
evidence for each action: a screenshot, a full DOM capture before and after, and
a deterministic diff between them. The output is a dataset a verifier can check.

## How It Works

Two separate systems drive the browser, and keeping them separate is the point.

The **agent-browser CLI** decides nothing — it observes the page and executes
actions. The model picks an action from an accessibility snapshot and refers to
elements by the `@eN` refs that snapshot provides.

**ChromiumRL** captures the evidence and computes the live diff. Before an
action, the recorder calls `captureStructuredSnapshot`. After the action it
calls `captureSnapshotDiff`, which captures the after-state and compares both
snapshots inside the browser. Each captured snapshot is passed to `getModelDOM`,
which produces the fixed model-facing text projection inside the browser. The
host saves the returned snapshot, projection, and diff.

The model never sees a page state that wasn't recorded, and every recorded
diff corresponds to exactly one executed action.

## Model Input Policy

Both the action model and the termination reviewer are DOM-only. Their Responses
API payloads contain text evidence only: the executable agent-browser snapshot,
the masked ChromiumRL model projection, bounded DOM-diff evidence, task memory,
and recent action outcomes. Screenshots are never attached to either model call.

Screenshots are still captured before and after every action and stored unchanged
as baseline-verifier artifacts. They also remain available to the recorder's
byte-level `action_progress` signal; removing them from model context does not
change capture, progress detection, or the artifact layout. Manifests record `model_input_policy: "dom_only"`.

## Project Layout

**Task entry**

- `run-task` — small wrapper that starts the CLI and forwards signals correctly
- `task_cli.py` — fetches the task from the catalog or accepts a manual one,
  stops any previous runner, starts the browser service, launches `runner.py`

**Core**

- `runner.py` — orchestrates a run: asks the model for an action, validates it,
  executes it, captures evidence, and decides when the task is finished. Also
  handles human intervention and the CLI.
- `capture.py` — everything that touches the browser: the CDP connection,
  structured snapshots, screenshots, action coordinates, and keeping capture
  attached to the tab agent-browser is actually on
- `dom_diff.py` — renders browser-produced diffs and builds bounded model and
  reviewer projections; it never compares snapshots or writes artifacts
- `trajectory.py` — turns confirmed actions into `trajectory.jsonl` and
  `web_surfer.log`
- `recorder_support.py` — shared recorder exception, URL validation, timestamps,
  and atomic writers, so a crash can't leave a half-written file
- `prompts.py` — the model's instructions, and the separate termination reviewer

**Browser adapter**

- `agent_browser/client.py` — translates one model action into one agent-browser
  CLI command. See `agent_browser/README.md` for the details, especially the
  difference between agent-browser refs and ChromiumRL ids.

**Rendering and tests**

- `scripts/render_chromiumrl_snapshot_full.py` — turns a snapshot into readable
  text for inspection
- `scripts/render_chromiumrl_snapshot_model.py` — the unchanged regression
  oracle for the browser-produced model projection
- `tests/` — unit tests for recorder behavior and artifact persistence
- `chromium_files/` — the prepared browser `.cc`, `.h`, and sole authoritative
  `ChromiumRL.pdl` used by protocol-declaration checks and browser builds

## View the Browser Through an SSH Tunnel

Run this on your local computer:

```bash
ssh -N -L "[::1]:39084:127.0.0.1:16191" ubuntu@static.235.31.55.162.clients.your-server.de
```

Keep the terminal open, then visit:

```text
http://[::1]:39084/vnc.html?resize=scale&autoconnect=1&path=websockify
```

If the remote noVNC port changes, replace `16191` in the tunnel command.

## Run a Task

Run a numbered task from the configured task catalog and choose where its
recording is stored:

```bash
cd /data/aayush/task-recorder-dom-diff

./run-task task1 \
  --output-dir "/path/to/recordings"
```

The selector may also use an exact catalog ID or a numeric form such as `1`. The
launcher retrieves the instruction, starting URL, stopping condition, and
constraints automatically.

Run a manually supplied task with the same interface:

```bash
./run-task my-task "Readable task name" \
  --task "TASK INSTRUCTION, STOPPING CONDITION, AND CONSTRAINTS" \
  --start-url "https://example.com/" \
  --output-dir "/path/to/recordings"
```

`--output-dir` is required. The recorder creates a unique timestamped run inside
the chosen directory and never overwrites an existing run.

Add `--dry-run` to validate the task and print its planned path without starting
the browser.

## What One Step Looks Like

For each action the model proposes, the runner:

1. checks the action against the current snapshot — a ref that isn't there, or a
   strategy that already stalled, is rejected and the model tries again
2. resolves the element's coordinates from the page as it is *before* the action
3. copies the current evidence into `steps/step_NNN/before/`
4. runs the action through agent-browser
5. reattaches capture to whatever tab is now active
6. calls `ChromiumRL.captureSnapshotDiff`, which captures the new state and
   computes the diff in the browser
7. calls `ChromiumRL.getModelDOM` for the returned after-state
8. writes the returned after-state and model projection, `dom_diff.json`, and
   `dom_diff.txt`

When the model wants to finish, a second model call reviews the proposed answer
against the recorded evidence and can send the run back for more work. That
review is not an action and doesn't create a step.

## Recording Files

A completed run contains:

- `task.json` — the task definition and where it came from
- `manifest.json` — run status, capture settings, and artifact inventory
- `decisions.jsonl` — every model proposal and termination review, including
  rejected ones
- `final.json` — the accepted final result
- `trajectory.jsonl` — one row per successfully executed browser action
- `web_surfer.log` — one WebSurfer event per successfully executed action

Every executed action creates a contiguous `steps/step_NNN/` directory containing
`action.json`, before/after screenshots, before/after DOM captures, and
`dom_diff.json` plus `dom_diff.txt`. The action record and manifest step include
`dom_diff_engine`, identifying `ChromiumRL.captureSnapshotDiff` plus the browser
version.

An absent trajectory or WebSurfer file means the run was interrupted or failed
validation and should not be used as a completed verifier recording. A valid
zero-action result may have empty trajectory files when the starting page itself
supplies a conclusive result or a permitted stopping condition.

## Live Diff Persistence

Every step computes its diff inside the browser with
`ChromiumRL.captureSnapshotDiff`. The recorder has no post-run snapshot
comparison or diff-generation path. If the live command fails, that step's diff
remains missing.

```bash
python runner.py --build-trajectory-run /path/to/recordings/<run-id>
```

The trajectory command validates existing artifacts and regenerates only
`trajectory.jsonl` and `web_surfer.log`; it cannot create or replace a diff.

The browser response is normalized before persistence. `runner.py` orders known
top-level fields, restores floating-point types only at declared float paths,
rejects unknown top-level fields, and appends byte/line audit metadata. Nested
objects and arrays are preserved as returned by the browser.

## Evidence Capping Policy

`dom.json` is the authoritative DOM evidence. Chromium capture uses these ceilings: `maxNodes` and cumulative `maxTextChars`, direct text
at 240 characters, subtree text at 500, selected-attribute values at 160,
selected attributes at 12, and `childRefs` at 80. The recorder requests 7,000
nodes and 200,000 text characters. It does not apply another DOM cap after the
browser returns the snapshot.

Three capture losses are silent to artifact consumers: selected attributes
beyond the first 12 have no counter; values over 160 characters or matching
`LooksLikeLargeStructuredValue` are skipped entirely rather than truncated; and
nodes rejected by `IsStructuredSnapshotCandidate` have no counter. Per-node
direct/subtree clipping sets the node's `truncated` flag. Snapshot
`stats.truncated` is ambiguous: one boolean covers the 7,000-node request,
cumulative `maxTextChars`, and the 80-child clip.

The full-text renderer and Chromium's model-text renderer cap only the
`dom_full.txt` and `dom_model.txt` projections. They never modify `dom.json`.
The unchanged Python model renderer applies the same limits as a regression
oracle. Content may be absent from both text projections without a hidden-count
marker, but it remains present in the authoritative `dom.json` unless one of
the browser capture ceilings above removed it first.

The recorder maintains a no-post-capture-truncation invariant for persisted DOM
and diff payloads. `tests/test_browser_diff_persistence.py` checks the runner's
import graph and permits only the live per-step diff writer. Every current diff
has `entry_limit: null`, zero `entries_truncated`, and empty
`dropped_entries`. `MAX_DOM_DIFF_JSON_BYTES` is written as
`artifact.max_json_bytes` and drives `artifact.over_size_limit`; it is warning
metadata and never shortens JSON or TXT output.

## Browser and Task Lifecycle

`run-task` starts the existing browser service with `--no-recreate` when needed.
The browser profile remains available across tasks. At the beginning of each
task, the launcher:

1. stops any active recorder process and its child processes;
2. creates and activates one fresh browser tab;
3. closes normal tabs left by prior tasks; and
4. attaches action execution and ChromiumRL capture to the fresh tab.

Starting another task while one is running interrupts the older run. Its manifest
is marked `interrupted`, and verifier trajectory files are not generated from that
incomplete run. Ctrl+C performs the same graceful cleanup. The browser service
remains running.

Do not use `docker compose down`, `docker compose rm`, or `--force-recreate` when
browser profile state must persist. To start the browser manually without running
a task:

```bash
docker compose --env-file .env up -d --no-recreate --wait wootz-desktop
```

Human intervention is enabled by default. If the runner pauses for a permitted
visible challenge, complete only that challenge through noVNC, return to the task
terminal, and press Enter. Type `abort` to stop. Use `--no-human-intervention` for
unattended runs.

## Configuration

Host-side settings live in `.env` — model, API key, CDP URL, snapshot budgets,
step limits. Browser container settings are in `docker-compose.yml`. The model
runs host-side, so the API key is deliberately not passed into the container.
