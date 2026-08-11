# Browser Task Recorder

## Project Layout

- `agent_browser/`: adapter for browser observations, element references, tabs, and action execution;
- `runner.py`: task orchestration, ChromiumRL capture, snapshot-based DOM diffs, screenshots, and verifier artifacts;
- `prompts.py`: model instructions for browser actions and evidence-based termination review;
- `task_cli.py` and `run-task`: task-launch interface and prior-run process management;
- `recorder_errors.py`: shared recorder exceptions;
- `requirements.txt`: host-side Python dependencies;
- `scripts/render_chromiumrl_snapshot_full.py`: full structured-snapshot renderer;
- `scripts/render_chromiumrl_snapshot_model.py`: model-facing structured-snapshot renderer; and
- `tests/`: offline regression tests.

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

Run a numbered task from the configured task catalog and choose where its recording is stored:

```bash
cd /data/aayush/task-recorder-dom-diff

./run-task task1 \
  --output-dir "/path/to/recordings"
```

The selector may also use an exact catalog ID or a numeric form such as `1`. The launcher retrieves the instruction, starting URL, stopping condition, and constraints automatically.

Run a manually supplied task with the same interface:

```bash
./run-task my-task "Readable task name" \
  --task "TASK INSTRUCTION, STOPPING CONDITION, AND CONSTRAINTS" \
  --start-url "https://example.com/" \
  --output-dir "/path/to/recordings"
```

`--output-dir` is required. The recorder creates a unique timestamped run inside the chosen directory and never overwrites an existing run.

Add `--dry-run` to validate the task and print its planned path without starting the browser.

## Recording Files

A completed run contains:

- `task.json`: the task definition and source metadata;
- `manifest.json`: run status, capture configuration, and artifact inventory;
- `decisions.jsonl`: model proposals and termination reviews for auditing;
- `final.json`: the accepted final result;
- `trajectory.jsonl`: one row per successfully executed browser action; and
- `web_surfer.log`: one WebSurfer event per successfully executed browser action.

Every executed action creates a contiguous `steps/step_NNN/` directory containing `action.json`, before/after screenshots, before/after DOM captures, and `dom_diff.json` plus `dom_diff.txt`.

An absent trajectory or WebSurfer file indicates an interrupted or invalid run and should not be used as a completed verifier recording. A valid zero-action result may contain empty trajectory files when the initial page itself supplies a conclusive result or permitted stopping condition.

## Browser and Task Lifecycle

`run-task` starts the existing browser service with `--no-recreate` when needed. The browser profile remains available across tasks. At the beginning of each task, the launcher:

1. stops an earlier recorder process and its child processes;
2. creates and activates one fresh browser tab;
3. closes normal tabs left by earlier tasks; and
4. attaches action execution and ChromiumRL capture to the fresh tab.

Starting another task while one is running interrupts the older run. Its manifest is marked `interrupted`, and verifier trajectory files are not generated from that incomplete run. Ctrl+C performs the same graceful cleanup. The browser service remains running.

Do not use `docker compose down`, `docker compose rm`, or `--force-recreate` when browser profile state must persist. To start the browser manually without running a task:

```bash
docker compose --env-file .env up -d --no-recreate --wait wootz-desktop
```

Human intervention is enabled by default. If the runner pauses for a permitted visible challenge, complete only that challenge through noVNC, return to the task terminal, and press Enter. Type `abort` to stop. Use `--no-human-intervention` for unattended runs.
