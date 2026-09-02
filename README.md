# Browser Task Recorder

This recorder runs a model-directed browser task and stores each observed browser
state once. A state contains the structured DOM capture, readable DOM text,
model-facing DOM projection, screenshot, and agent-browser observations. The
action selected from a state is saved in that state directory, and the following
state records the result.

## How It Works

Two systems interact with the browser:

- **agent-browser** observes accessible controls and executes the model's chosen
  browser action. Its `@eN` references are executable only for the current
  interactive snapshot.
- **ChromiumRL** captures the structured DOM with
  `captureStructuredSnapshot`, provides action coordinates through
  `getAgentObservation`, and builds a structured model-facing projection with
  `getModelDOM`.

For every captured snapshot, the recorder saves `dom.json`. It runs the full
renderer to create `dom_full.txt`, saves the `getModelDOM` result as
`dom_model.json`, and uses the deterministic model renderer to create
`dom_model.txt`.

The model receives the task instruction, current `dom_model.txt`, the current
interactive agent-browser snapshot, task memory, and recent action outcomes.
Screenshots are captured as recording artifacts and are not attached to model
requests.

## Project Layout

- `run-task` — shell wrapper for the command-line task launcher.
- `task_cli.py` — loads a catalog or manual task, starts the browser service,
  and launches `runner.py`.
- `runner.py` — coordinates model decisions, validation, execution, capture,
  state transitions, finalization, and command-line options.
- `capture.py` — CDP connection, structured capture, screenshots, browser
  coordinates, language checks, and agent-browser synchronization.
- `trajectory.py` — validates recorded states and creates `trajectory.jsonl`
  plus `web_surfer.log`.
- `recorder_support.py` — common text normalization, URL helpers, timestamps,
  errors, and atomic file writers.
- `prompts.py` — model instructions and action policy.
- `agent_browser/` — the adapter around the official agent-browser CLI.
- `scripts/render_chromiumrl_snapshot_full.py` — turns `dom.json` into
  readable `dom_full.txt`.
- `scripts/render_chromiumrl_model_dom.py` — validates `dom_model.json` and
  joins its ordered sections into `dom_model.txt`.
- `scripts/render_chromiumrl_snapshot_model.py` — regression oracle for the
  browser-produced model projection.
- `chromium_files/` — prepared browser protocol source used for browser builds.
- `tests/` — recorder unit tests.

## View the Browser Through an SSH Tunnel

Run this on your local computer:

```bash
ssh -N -L "[::1]:39084:127.0.0.1:16191" ubuntu@static.235.31.55.162.clients.your-server.de
```

Then open:

```text
http://[::1]:39084/vnc.html?resize=scale&autoconnect=1&path=websockify
```

## Run a Task

Run a catalog task:

```bash
cd /data/aayush/task-recorder-dom-diff
./run-task task1 --output-dir /path/to/recordings
```

Run a manual task:

```bash
./run-task my-task "Readable task name" \
  --task "TASK INSTRUCTION, STOPPING CONDITION, AND CONSTRAINTS" \
  --start-url "https://example.com/" \
  --output-dir /path/to/recordings
```

`--output-dir` is required. A timestamped run directory is created and an
existing run is never overwritten. Use `--dry-run` to validate task selection
without starting the browser.

## State Layout

A run uses direct sequential state folders:

```text
<run>/
  task.json
  manifest.json
  decisions.jsonl
  final.json
  trajectory.jsonl
  web_surfer.log
  steps/
    step_001/
      dom.json
      dom_full.txt
      dom_model.json
      dom_model.txt
      screenshot.png
      agent_browser.txt
      agent_browser_actions.txt
      action.json                 # when an action is selected here
    step_002/
      ...                         # state reached by action.json in step_001
```

`step_001` is the initial captured page state. Each executed action lives in
its source state directory. The next sequential directory is the state reached
after that action. A final state can therefore have no `action.json`.

`action.json` records the chosen action, execution receipt, target identity,
coordinate lookup, progress signals, model response metadata, source-state
paths, and next-state paths. The manifest lists both captured states and
executed actions. `trajectory.jsonl` and `web_surfer.log` contain one row for
each executed non-human action.

Use this command to validate an existing run and regenerate only the two
exported action logs:

```bash
python runner.py --build-trajectory-run /path/to/recordings/<run-id>
```

## Evidence Boundaries

`dom.json` is the authoritative capture for the current viewport. The recorder
uses `inViewportOnly=true` and `includeOffscreen=false`; content becomes
eligible after scrolling brings it into view.

The recorder requests 7,000 nodes and 200,000 text characters. Chromium also
sets per-node direct text at 240 characters, subtree text at 500, selected
attribute values at 160, selected attributes at 12, and child references at
80. The host does not shorten a returned DOM snapshot or its text projections.

The renderers create readable projections only. They do not modify `dom.json`.
