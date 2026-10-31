# Recordings

The dataset’s [recordings directory](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/recordings)
contains the original browser-run artifacts captured by this repository’s
[`w8bench/task_recorder`](../w8bench/task_recorder/) package.
Tasks run in w8-core through `agent-browser`; the recorder saves an initial
browser state, captures subsequent states after actions, and records model
decisions, execution results, and the final answer. These files let readers
inspect what the agent observed and what happened during a run.
The benchmark's acting agent uses `gpt-5.6` for browser-action generation.

These recordings provide additional data for inspecting the collection
process. The verifier audit uses the prepared trajectory pairs in
[`trajectories/data-ss/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/trajectories/data-ss) and
[`trajectories/data-dom/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/trajectories/data-dom).
Use the recordings when you want more detail about a recorded run, its
observations, or its failures.

Each run has a folder such as
[task1-reddit-ranking-20261029T152819Z](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/recordings/task1-reddit-ranking-20261029T152819Z): a task identifier,
readable name, and UTC run timestamp. JSONL files contain one JSON object per
line; `web_surfer.log` also uses that format.

| Artifact | Purpose | Availability | How to inspect it | Key fields or related files |
|---|---|---|---|---|
| `task.json` | Identifies the task and collection setup. | Every run. | Read the instruction, constraints, start URL, and model. | `source_task_id`, `task_id`, `action_driver`. |
| `manifest.json` | Indexes the recording and its provenance. | Every run. | Check capture settings, browser/driver details, state paths, actions, warnings, and errors. | `states`, `steps`, `status`, `trajectory_export`, `browser_build_provenance`. |
| `final.json` | Stores the final answer and recorded outcome. | Every run. | Read the answer alongside any failure or error details. | `status`, optional `run_status`, `recorded_steps`. |
| `decisions.jsonl` | Records model decisions, including rejected proposals and termination. | When model decisions were recorded. | Inspect proposed actions, rejection reasons, memory updates, response metadata, and token usage. | `model_turn`, `decision`, `rejection_reason`. |
| `trajectory.jsonl` | Stores normalized executed browser actions. | When export is available; may be empty. | Follow each action's arguments, execution status, and state transition. | `source_step`, `next_step`, `execution_status`. |
| `web_surfer.log` | Expresses the exported actions as WebSurfer events. | When export is available; may be empty. | Read action messages and arguments in order. | Companion to `trajectory.jsonl`. |
| `steps/step_NNN/` | Holds one captured browser state. | When state capture succeeded. | Compare adjacent folders to inspect an action's effect. | State assets described below. |

`browser_build_provenance` records the container's exact image ID, available
repository digests and build labels for the overlay, Chromium and protocol.
Source revisions remain unknown for older images without those labels.
Direct CDP runs without managed-container metadata leave this field null.

Within each state folder:

- `screenshot.png` is the captured browser image. Screenshots were saved as
  audit artifacts; the acting model received text observations.
- `dom.json` is the ChromiumRL structured snapshot, and `dom_full.txt` is its
  detailed text rendering. “Full” refers to the captured snapshot: these runs
  use viewport filtering and capture limits, so it does not mean the entire
  page's HTML or all offscreen content.
- `dom_model.json` and `dom_model.txt` store the model-oriented ChromiumRL
  representation. `agent_browser.txt` stores the broader accessibility
  snapshot; `agent_browser_actions.txt` stores the interactive snapshot used
  for executable action references. ChromiumRL IDs and agent-browser refs
  belong to separate namespaces.
- `action.json`, when present, records the action taken **from this state**,
  including its target, timing, result, and model metadata.

For example, `steps/step_001/` is the initial captured state.
`steps/step_001/action.json` describes the action leading to `step_002/`, which
contains the resulting state. A terminal state normally has no `action.json`.
Model turns can include rejected proposals or termination, so decision-log
counts need not equal executed-action counts. Use the manifest and exported
state references to follow the sequence.

Successful, failed, and errored runs are all retained. A recorded `success`
is a collection outcome, not an independent verifier score. The file layout
and capture policy above are supported by the stored manifests and recorder
code; answer correctness and faithful live replay require separate checks,
especially because public web pages can change. For an independent
inspection, start with `task.json`, `manifest.json`, and
`final.json`, then follow the relevant actions and state folders.

Use task identifiers, timestamps, and manifests to match recordings with
prepared trajectories and evaluation artifacts. Evaluation folder IDs group
outputs; use the run manifest's scoring/audit times and saved logs for actual
execution dates. The
[technical report](technical-report.md#recorded-execution-failures)
separates recorded execution failures from completed evaluation audits.
For commands that create local recordings, see the
[runbook](runbook.md#record-a-task).
