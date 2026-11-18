# Recordings

A recording is one actor attempt for a task, arm and trial. It contains the
actor's observations and decisions, executed actions, final answer and both saved
evidence formats. The [datacard](datacard.md#observation-modes) defines
which observations reach each actor; passive artifacts remain recorder and judge
data.

The batch ledger accounts for every scheduled attempt, including attempts that
create no recording directory. Use it with the recording manifest to follow
execution order, technical outcomes, grading and available cost information.

## Locate an attempt

```text
recordings/<batch-name>/
  ledger.jsonl
  logs/attempt_000001_01.log
  trial_0001/
    dom/<task-id>/
    screenshot/<task-id>/
  ...
```

Trial count is an explicitly chosen positive integer with no default. Each
`(task, arm, trial)` has a distinct recording path, retained for that attempt.
A standalone one-arm task uses `recordings/<run-name>/<arm>/<task-id>/` and a
local ledger under `recordings/<run-name>/attempt_ledgers/<arm>/<task-id>.jsonl`.
A technical rerun has its own recording directory; neither attempt is overwritten.

`ledger.jsonl` contains one JSON object per scheduled attempt. `sequence`,
`task_id`, `arm`, `trial`, `trials`, `arm_order`, `run_name` and `recording` identify
its place in the schedule. Rows also freeze expanded task data, catalog hash,
`configuration`, rubric path/file hash and judge model. Both arms of a task/trial
are adjacent and finish their final attempts before their judges.

`technical_outcome` and `completed` track actor execution. `grade_outcome` and
`grade_completed` track grading. Rows may also contain launcher PID, start/end
timestamps, exit codes, log paths, judge timestamps and errors. An interruption
during judging preserves the completed actor outcome.

Resume retains completed final attempts. A row's `attempts` list retains each
attempt number, recording path and outcome; one technical failure permits a fresh
attempt. Resume reconciles an orphaned attempt and continues a pending rerun
before moving to unstarted work. A live owned recorder or grader blocks resume. Runtime
ownership markers are checked for staleness before they are used. See the
[runbook](runbook.md#resume) for commands.

## Run-level artifacts

Normally finalized recordings contain the files below. Startup failures may have
no directory, and hard interruptions may leave a subset. Those attempts remain
in the ledger.

| Artifact | Contents | Availability and interpretation |
|---|---|---|
| `task.json` | `task_id`, `source_task_id`, `run_name`, `task_name`, expanded `instruction`, `start_url`, `observation_mode`, configured `model`. | Written when the recorder initializes. Constraints and stopping conditions are included in instruction text. |
| `manifest.json` | Task identity, schema/timestamps, `status`, `controls`, `states`, `steps`, turn/model metadata, provenance and `trajectory_export`. | Indexes the recording; finalization embeds the same `final` object as `final.json`. |
| `final.json` | Actor `status`, technical `run_status`, final answer, action/turn counts, termination metadata or error when applicable. | Actor output and recorder outcome, separately from independent grading. Its `completion_grade` field remains an ungraded placeholder. |
| `decisions.jsonl` | One row per received actor response: turn/state, decision, acceptance/rejection/error, prior memory, usage, response metadata, latency and `model_input`. | Includes invalid proposals and termination. Transport failures have separate receipts and do not add a model turn. |
| `turns/turn_NNNNNN/request.json` | Serialized text, instructions, schema and API settings; images use a relative saved-artifact path/hash. | The API request encodes those image bytes as base64; the file avoids storing duplicate base64 per turn. |
| `turns/turn_NNNNNN/response.json` | Raw provider response, returned model, output items and usage. | Present when a response was received; no response is fabricated for a transport failure. |
| `turns/turn_NNNNNN/result.json` | Decision-log row, including response status, incomplete details and output-limit flag. | Mirrors the received-response decision. A request directory can exist even when dispatch did not occur. |
| `turns/turn_NNNNNN/transport_pending.json` | In-flight attempt identity and unknown usage; retained on interruption without inventing a model response. | Pending work is reported separately. |
| `turns/turn_NNNNNN/transport_attempts.jsonl` | HTTP attempt number, status, duration, usage coverage, finish/parser metadata and sanitized failed response where available. | Failed transports do not add model turns; their usage is unknown unless reported. |
| `cdp_calls.jsonl`, `agent_browser_calls.jsonl` | Per-call timing, status and method metadata. | CDP parameters and CLI arguments are excluded. |
| `browser_events.jsonl`, `target_registry.json`, `observation_recovery.jsonl` | Crash/detach/dialog events, exact target/opener identities and liveness/reattachment outcomes. | Private identity metadata is not actor evidence; dialog text is excluded. |
| `failure_health.json`, `interruption.json` | Available container health, bounded log tail and interruption status. | Missing diagnostics remain unavailable; credentials are redacted. |
| `trajectory.jsonl` | Normalized action transitions, execution status/error, before/after observations, paired artifacts and capture metadata. | Exported during finalization; missing after-states make the export incomplete. |
| `web_surfer.log` | JSONL WebSurfer-style action events, model turns, arguments and delivery status. | Derived action log, not additional actor input or model calls. |
| `completion.json` | Primary `paired` grade, recording/rubric/prompt hashes, model IDs, criteria/verdict and judge usage. | Produced by independent grading. Missing, uncertain and ungraded are distinct from confirmed failure. |
| `completion_actor_native.json` | Optional secondary grade using `actor_native` evidence. | Does not overwrite the primary grade. Both saved grades contribute to separate judge cost accounting. |
| `capture_failures.jsonl` | Attempt, directory, timestamp, active error and discarded capture metadata. | Written before discarding a failed after-action capture for retry; preserves errors from that interval. |
| `steps/step_NNN/` | One committed captured state. | `step_001` is the initial state; subsequent states follow executable action attempts. |

`manifest.controls` records requested model/endpoint, turn and output budgets,
viewport, settle interval, memory limit, reasoning, temperature setting, locale,
action vocabulary/schema and actor protocol/code/prompt hashes.
`returned_actor_models` records provider model IDs. `dom_capture_parameters` and
`renderer_versions` describe saved DOM scope and rendering in both arms. The
prompt hash is modality-specific; shared controls must match for comparison.

`browser_profile_provenance` contains container ID/creation time, freshness and
prior-task count. Its `browser_build` object records immutable image ID, reference,
repository digests and available overlay/Chromium/protocol source labels.
`browser_environment` records selected locale, screen and Chromium runtime
settings. Absent source labels remain unknown. Controlled comparisons require
verified fresh profiles and matching browser builds/runtime environments.

## State artifacts

A successfully paired state contains the five evidence files below, plus its
capture metadata. The DOM arm also saves executable reference text.

| File | Meaning |
|---|---|
| `dom.json` | ChromiumRL structured snapshot under `result.snapshot`. |
| `dom_full.txt` | Detailed rendering of the viewport-scoped snapshot, subject to node/text limits. “Full” refers to that captured snapshot, not whole-page HTML or all offscreen content. |
| `dom_model.json` | ChromiumRL model-oriented representation under `result.modelDOM`. |
| `dom_model.txt` | Text rendering of the model-oriented representation. Actor formatting masks ChromiumRL numeric IDs. |
| `screenshot.png` | Viewport PNG. In the screenshot arm, these exact bytes are supplied to the actor at high detail. |
| `capture.json` | Interval, phase timing, target identity and completeness metadata, also stored under the manifest state's `capture` field. |
| `agent_browser_actions.txt` | DOM arm only: viewport-filtered interactive snapshot supplying executable `e` references. It is recorded agent-browser output, not code written by the actor. |
| `action.json` | Action attempted **from this state**, model turn, delivery status/error, timing and subsequent progress/state link; DOM target metadata where applicable. Screenshot actions keep raw model coordinates and executed CSS coordinates. |

ChromiumRL IDs and agent-browser references are separate namespaces. Screenshot
states contain no reference snapshot; targeting comes from the saved image, while
both arms' generated actions are stored in decision/action files.

Each committed manifest state has `state`, `directory`, `observation`,
`observation_sha256`, `artifacts` and `capture`. `observation` selects actor input;
`artifacts` maps saved filenames to relative paths and SHA-256 hashes. DOM states
also contain `agent_browser_action_snapshot`. A passive artifact's presence and
hash do not make it actor input.

## Capture intervals

`capture` records `target_id`, `session_id`, `capture_order`, interval
`started_at`/`ended_at`/`duration_seconds`, and a `captures` list. Each phase has
`kind`, start/end time, duration and status, plus an error when it failed.
The order is `structured_dom`, `dom_model_artifacts`, `screenshot`, followed by
`executable_refs` in the DOM arm.

The interval also records `url_before`, `url_after`, loader IDs,
`navigation_events` and `navigation_during_capture`. `metadata_errors`,
`setup_errors` and `url_metadata_complete` disclose metadata gaps.
`document_language` is supplied as actor context only in the DOM arm.

Captures are sequential. Navigation flags identify observed navigation or URL
changes; they do not detect every DOM mutation or animation. Timing and flags
therefore matter when interpreting the two evidence formats for a state.

A passive capture error sets `paired_complete: false`, removes the failed phase's
partial files and records its error. When the active observation is usable, the
actor continues without that error entering memory, prompt, progress or rejection
feedback. Such a state can lack passive artifacts. An active observation error
can end the run or trigger a bounded read-only transport retry. A capture retry
does not replay an executed action.

## Follow actions and model calls

`steps/step_001/action.json` leads to the next captured state, normally
`steps/step_002/`. A terminal state normally has no outgoing `action.json`.
Normally N action attempts produce N+1 states. An action remains recorded if its
after-state capture fails; `trajectory_export.status` and `errors` disclose the
missing transition.

`action_succeeded` confirms browser input delivery. Page progress and task
completion are assessed separately. Model turns can exceed action counts because
received rejected proposals, parsing failures and termination consume model turns
without executing browser actions. Failed transport attempts do not consume a turn.

Each decision records `response_status`, `incomplete_details`, `output_limit_hit`,
`returned_model`, `reasoning` and `usage`. Inspect response status and incomplete
reason before interpreting a limit hit as truncation. Cached-input and reasoning
counts are subsets of input/output totals.

Actor request receipts contain the Gemini `systemInstruction`, `contents` and
`generationConfig`. Image parts reference the saved PNG by path and SHA-256;
the transport sends that file's bytes as inline image data. Response receipts
retain native provider metadata alongside normalized input/output usage.
Normalized output includes reasoning tokens once, with reasoning also recorded
as a subset for reporting.

Start an inspection with the ledger row and log, then read `task.json`,
`manifest.json` and `final.json`. Follow state/action/turn references to inspect
the sequence, and read `completion.json` separately for the judge's assessment.
`task.json` and `manifest.json` record `catalog_sha256` for the exact source
catalog bytes. Manual tasks without a catalog record `null`; comparison checks
the hash against the schedule and across arms and trials.
Date-sensitive catalog tasks also record `valid_until`, `expiry_checked_at` and
`expiry_override`; these scheduling controls are not actor instructions.

Call timing files record CDP and agent-browser method, status, duration and error
metadata. Browser events include target/renderer crashes, detach and dialog
notifications. Failure receipts include available container memory, shared-memory
use, process count and a bounded log tail; unavailable diagnostics are recorded
as unavailable. Interruption receipts preserve partial attempt status. Credentials
are excluded from these files.

Read-only observation timeouts/internal errors permit a 3-second liveness probe
and one reattachment/retry for a live target. Crash events stop further calls to
the failed page. An action with uncertain delivery ends the attempt; no action is
replayed. The schedule retains one fresh technical rerun and uses its final
attempt for success, turns and tokens, with earlier technical costs separate.

## Integrity and export

`inspect_recording()` validates hashes, paths, actor request reconstruction,
image identity and action/turn relationships. The recording fingerprint excludes
the two completion files, allowing grading without changing actor evidence
identity. Changing hashed evidence afterward invalidates its saved grade.

A missing `final.json` makes an attempt incomplete rather than absent from the
schedule. Comparison retains parseable decision usage as lower bounds and labels
`recording_available`, `partial_recording`, `cost_coverage` and `turns_complete`.
Exact all-attempt means/medians are null where coverage is incomplete; see the
[evaluation protocol](evaluation-protocol.md#denominators-and-coverage) for details.

`prepare_recording()` stages flat verifier inputs under
`<run-name>/<arm>/<task-id>/<recording-hash>/data-ss/<task-id>/` and matching
`data-dom/`. `input_receipt.json` binds both projections to source files,
observed URLs, validity date and per-state eligibility. Original state IDs and
full execution chronology survive gaps. Shared history carries no DOM target
descriptions or actor notes. Export output must remain outside its source recording.
Validation establishes file consistency, while answer correctness is assessed by
the independent completion grade.

Full evaluation writes `evaluation.json`, the imported/frozen rubric and its
receipt, `paired_completion.json`, both verifier result/metrics/log folders and
`evidence_audit.json` in the sibling evaluation tree. Completed result hashes are
checked before reuse. Primary completion, auxiliary signals, fallback quality,
audit coverage and every cost stream remain distinct.
Each stage also records its normalized effective settings and returned-model
diagnostics. Ungraded stages retain failure reasons and attempt usage for resume;
native score fields remain null after scoring exhaustion. DOM citation diagnostics
live in `citation_checks` and `dom_model_evidence_audit.citation_checks` in the
native result. The controller copies them directly into the evaluation stage;
normalization and audit inputs do not consume them. Audit receipts use
`automated-evidence-audit/v7` and
`paired-capture-eligible-state-adjudication/v7`; an ungraded audit supplies no loss
rate. See the [effective settings contract](evaluation-protocol.md#effective-settings-contract)
for the settings compared across resumes, arms and trials.
