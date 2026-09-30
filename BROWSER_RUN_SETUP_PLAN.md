# Browser Run Setup Plan

## Goal

Make the `w8-reproducible` branch usable by a third person who has only the
repository and its README. The documented flow must let that person start
w8-core, open the visible browser through noVNC, run a recorder task, watch the
browser while the task executes, find the generated recording, and stop the
runtime safely.

## Scope

The work is limited to the browser task-recorder setup and its documentation.
Existing verifier, benchmark, result, and evaluation folders must not change.
The work is performed in the isolated local worktree:

`/data/aayush/w8-domdiff-bench-reproducible`

The worktree tracks the existing `w8-reproducible` branch.

## Implementation steps

1. Read the root README, task-recorder README, Docker Compose configuration,
   launcher, and environment handling as one end-to-end setup.
2. Check the commands against the actual `wootzapp/w8-core` image rather than
   documenting assumed ports or component names.
3. Make the local and remote viewing paths explicit:
   - local noVNC URL;
   - SSH tunnel command for a remote server;
   - the URL to open after creating the tunnel.
4. Make environment setup copyable and explain the minimum values required to
   run the browser and a task.
5. Document how to start the browser, confirm it is healthy, run a task while
   watching noVNC, locate the output, and stop or destroy the container.
6. Keep repository-specific terminology and commands consistent with the
   checked-in Docker Compose service and recorder CLI.
7. Add troubleshooting only for failures a new user can realistically meet,
   such as an occupied port, an unhealthy container, an unreachable noVNC
   page, or missing API credentials.

## Validation steps

1. Validate the rendered Docker Compose configuration.
2. Start the checked-in Compose service using the documented commands.
3. Confirm the container health status.
4. Confirm CDP responds through the documented host port.
5. Confirm noVNC responds through the documented host port.
6. Confirm the image contains the browser runtime, ChromiumRL commands, and
   bundled agent-browser executable expected by the recorder.
7. Run the recorder unit test suite.
8. Run a dry-run task selection check and, where credentials permit, a small
   live task smoke test without adding recording data to the repository.
9. Review the final Git diff and confirm every changed path is intentional.

## Validation record

The completed implementation was tested from this isolated worktree on
September 30, 2026.

- The regular host ports were already occupied, so configuration selected
  free alternatives without changing or stopping the existing browser.
- The isolated container became healthy and exposed Chrome
  `152.0.7948.0` through CDP.
- Its noVNC page returned HTTP 200 and agent-browser reported version
  `0.27.3`.
- A manual `https://example.com/` recording completed successfully and wrote
  the sequential DOM, model-DOM, screenshot, action, final-answer, trajectory,
  and WebSurfer artifacts under `/tmp`.
- Catalog task selection passed in dry-run mode.
- The task-recorder unit suite ran 79 tests successfully; seven live-browser
  tests were skipped by their existing environment guards.
- The isolated validation container and network were removed afterward. The
  pre-existing `w8-core-browser-engine` container remained healthy and was not
  modified.
