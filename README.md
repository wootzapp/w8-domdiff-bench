# Browser Task Recorder

Records what a model does in a browser, one action at a time, along with the
evidence for each action: a screenshot, a full DOM capture before and after, and
a deterministic diff between them. The output is a dataset a verifier can check.

## How It Works

Two separate systems drive the browser, and keeping them separate is the point.

The **agent-browser CLI** decides nothing — it observes the page and executes
actions. The model picks an action from an accessibility snapshot and refers to
elements by the `@eN` refs that snapshot provides.

**ChromiumRL** captures the evidence. Before and after every action, the recorder
takes a structured snapshot of the page through CDP, saves a screenshot, and
computes the semantic difference between the two snapshots.

The model never sees a page state that wasn't recorded, and every recorded
diff corresponds to exactly one executed action.

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
- `dom_diff.py` — compares two stored snapshots and produces the diff. Pure
  functions, no browser involved, which is why it can be tested offline
- `trajectory.py` — turns confirmed actions into `trajectory.jsonl` and
  `web_surfer.log`
- `backfill.py` — recomputes diffs for runs already on disk, without a browser
- `artifacts.py` — atomic JSON and text writers, so a crash can't leave a
  half-written file
- `prompts.py` — the model's instructions, and the separate termination reviewer
- `recorder_errors.py` — shared exception type

**Browser adapter**

- `agent_browser/client.py` — translates one model action into one agent-browser
  CLI command. See `agent_browser/README.md` for the details, especially the
  difference between agent-browser refs and ChromiumRL ids.

**Rendering and tests**

- `scripts/render_chromiumrl_snapshot_full.py` — turns a snapshot into readable
  text for inspection
- `scripts/render_chromiumrl_snapshot_model.py` — a shorter version of the same
  snapshot, written for the model
- `tests/` — offline regression tests, no browser or network needed
- `ChromiumRL.pdl` — protocol reference for the CDP domain used here

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
6. captures the new state into `steps/step_NNN/after/`
7. diffs the two snapshots and writes `dom_diff.json` and `dom_diff.txt`

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
`dom_diff.json` plus `dom_diff.txt`.

An absent trajectory or WebSurfer file means the run was interrupted or failed
validation and should not be used as a completed verifier recording. A valid
zero-action result may have empty trajectory files when the starting page itself
supplies a conclusive result or a permitted stopping condition.

## Diffs Without a Browser

Diffs are computed from the stored snapshots, not from browser state, so they can
be regenerated at any time:

```bash
python runner.py --backfill-run /path/to/recordings/<run-id>
python runner.py --build-trajectory-run /path/to/recordings/<run-id>
```

The first recomputes every `dom_diff.json`. The second revalidates a run and
regenerates its trajectory files. Neither needs a browser.

## Browser and Task Lifecycle

`run-task` starts the existing browser service with `--no-recreate` when needed.
The browser profile remains available across tasks. At the beginning of each
task, the launcher:

1. stops an earlier recorder process and its child processes;
2. creates and activates one fresh browser tab;
3. closes normal tabs left by earlier tasks; and
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
