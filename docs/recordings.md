# Recordings

A recording is one actor attempt for a task, arm and trial. It contains the
actor's observations and decisions, executed actions, final answer and both saved
evidence formats. The [datacard](datacard.md#observation-modes) defines
which observations reach each actor; passive artifacts remain recorder and judge
data.

The batch ledger accounts for every scheduled run, including runs that create no
recording directory. Use it with the recording manifest to follow execution
order, technical outcomes, grading and available cost information. Output
directories use numeric collision suffixes. `--resume` selects an existing ledger
or schedule preview and never chooses a different run implicitly. A preview is
not an execution ledger; rubric availability determines whether scheduling can
create the executable ledger. Comparison
output records its `browser_profile_policy`, including any explicit nonfresh
override; other browser build and environment checks still apply.

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
`(task, arm, trial)` has a distinct recording path, retained for that attempt. A
standalone one-arm task uses `recordings/<run-name>/<arm>/<task-id>/` and a
local ledger under
`recordings/<run-name>/attempt_ledgers/<arm>/<task-id>.jsonl`. A technical rerun
has its own recording directory; neither attempt is overwritten. Batch reruns
use `<batch-name>/technical_attempt_02/<trial-name>/<arm>/<task-id>/`.
Standalone reruns use
`recordings/technical_attempt_02/<run-name>/<arm>/<task-id>/`.

`ledger.jsonl` contains one JSON object per scheduled `(task, arm, trial)` run;
technical attempts remain in that row’s `attempts` list. `sequence`, `task_id`,
`arm`, `trial`, `trials`, `arm_order`, `run_name` and `recording` identify its
place in the schedule. Rows also freeze expanded task data, catalog hash,
`configuration`, rubric path/file hash and judge model. Both arms of a
task/trial are adjacent and finish their final attempts before their judges.

`technical_outcome` and `completed` track actor execution. `grade_outcome` and
`grade_completed` track grading. Rows may also contain launcher PID, start/end
timestamps, exit codes, log paths, judge timestamps and errors. An interruption
during judging preserves the completed actor outcome.

Resume retains completed final attempts. A row's `attempts` list retains each
attempt number, recording path and outcome; one technical failure permits a
fresh attempt. Resume reconciles an orphaned attempt and continues a pending
rerun before moving to unstarted work. A live owned recorder or grader blocks
resume. Runtime ownership markers are checked for staleness before they are
used. See the [runbook](runbook.md#resume-a-recording) for commands.

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
| `turns/turn_NNNNNN/request.json` | Serialized text, instructions, schema and API settings, including global `MEDIA_RESOLUTION_HIGH`; images use a relative saved-artifact path/hash. | The API request encodes those image bytes as base64; the file avoids storing duplicate base64 per turn. |
| `turns/turn_NNNNNN/response.json` | Raw provider response, returned model, output items and usage. | Present when a response was received; no response is fabricated for a transport failure. |
| `turns/turn_NNNNNN/result.json` | Decision-log row, including response status, incomplete details and output-limit flag. | Mirrors the received-response decision. A request directory can exist even when dispatch did not occur. |
| `turns/turn_NNNNNN/input_preflight.json` | Local text/image estimate, model input limit, optional countTokens attempts, dispatch decision and status. | Estimates at or below 50% skip counting. Unavailable counting uses the recorded estimate; confirmed or estimated overflow above 95% prevents generation. |
| `turns/turn_NNNNNN/transport_pending.json` | In-flight attempt identity and unknown usage; retained on interruption without inventing a model response. | Pending work is reported separately. |
| `turns/turn_NNNNNN/transport_attempts.jsonl` | HTTP attempt number, status, duration, usage coverage, finish/parser metadata and sanitized failed response where available. | Failed transports do not add model turns; their usage is unknown unless reported. |
| `cdp_calls.jsonl`, `agent_browser_calls.jsonl` | Per-call timing, status and method metadata. | CDP parameters and CLI arguments are excluded. |
| `browser_events.jsonl`, `target_registry.json`, `observation_recovery.jsonl` | Crash/detach/dialog events, exact target/opener identities and liveness/reattachment outcomes. | Private identity metadata is not actor evidence; dialog text is excluded. |
| `failure_health.json`, `interruption.json` | Available container health, bounded log tail and interruption status. | Missing diagnostics remain unavailable; credentials are redacted. |
| `trajectory.jsonl` | Normalized action transitions, execution status/error, before/after observations, paired artifacts and capture metadata. | Exported during finalization; missing after-states make the export incomplete. |
| `web_surfer.log` | JSONL WebSurfer-style action events, model turns, arguments and delivery status. | Derived action log, not additional actor input or model calls. |
| `completion.json` | Primary `paired` grade, recording/rubric/prompt hashes, model IDs, criteria/verdict and judge usage. | Standalone completion can write beside the recording; controlled evaluation keeps the shared receipt outside the recording, as described below. Missing, uncertain and ungraded are distinct from confirmed failure. |
| `completion_actor_native.json` | Optional secondary grade using `actor_native` evidence. | The secondary policy writes beside the recording and does not overwrite the primary grade. Both saved grades contribute to separate judge cost accounting. |
| `capture_failures.jsonl` | Attempt, directory, timestamp, active error and partial capture metadata. | Failed after-action capture directories are retained under the next free `step_NNN_capture_attempt_XX` name before an existing transport retry. |
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
| `dom_full.txt` | Detailed rendering of the viewport-scoped snapshot, with a default 1,200-character display cap per text field in addition to snapshot limits. “Full” refers to that captured snapshot, not whole-page HTML or all offscreen content. |
| `dom_model.json` | Model-oriented projection under `result.modelDOM`, including the explicit marker for an empty export. |
| `dom_model.txt` | Text rendering of the model-oriented representation. Actor formatting masks ChromiumRL numeric IDs and filters its inactive targeting/scroll instructions; the saved text remains intact. |
| `screenshot.png` | Viewport PNG at device pixel ratio 1. The screenshot actor receives these exact bytes with global `MEDIA_RESOLUTION_HIGH`. |
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
The order is `structured_dom`, `screenshot`, DOM-arm `executable_refs`, then
`dom_model_artifacts` and the stored text projections.

`policy_version` is `paired-capture/v2`. The private `readiness` record contains
`target_id`, `frame_id`, `loader_id`, `timeout_seconds`, `wait_seconds`,
`ready_state`, `mime_type`, `animation_frames`, `navigation_changes` and a
status of `ready`, `timeout`, `same_document` or `unavailable`. A different
target/frame/loader waits for DOMContentLoaded or interactive/complete and then
two animation frames, within the existing CDP navigation timeout (90 seconds).
The settle interval is unchanged. Timeout permits capture as-is; same-document
updates skip the asynchronous wait. The interval duration includes readiness
waiting; individual phase durations start afterward. `navigation_changes`
identifies document-identity changes encountered during readiness.
Evidence-acquisition navigation has separate flags.

`document_mime_type` and `document_ready_state` describe the document before raw
acquisition. `dom_export` records `status` (`empty` or `content`), the empty marker
when applicable, and unmodified snapshot `stats`. An empty export still produces
`dom.json`, `dom_full.txt`, `dom_model.json` and `dom_model.txt`; the model text
contains `[No exportable DOM content]`. A saved screenshot plus that valid empty
export is paired-complete. Missing capture files remain incomplete. These rules
apply equally to active and passive evidence in both arms. MIME/readiness metadata
never enters actor requests.

The interval also records `url_before`, `url_after`, loader IDs,
`navigation_events` and `navigation_during_capture`. `metadata_errors`,
`setup_errors` and `url_metadata_complete` disclose metadata gaps. Available
`content_changed_during_capture` and `paint_changed_during_capture` record
observed activity without automatic recapture. Global flags are true on observed
activity and otherwise unknown. `content_change_monitor` identifies observed
main/known-frame contexts and discovered open shadow roots. Closed roots and
unreported remote frames are not covered; partial coverage does not prove
stability.
`document_language`, when available, is private capture metadata and is not
supplied to either actor.

Raw structured DOM, screenshot and DOM-arm references are captured before
stored DOM projections and bulk artifact writes. Per-call operational trace
writes remain durable during raw capture for crash receipts. Captures are sequential. Navigation flags identify observed navigation or URL
changes; they do not detect every DOM mutation or animation. Timing and flags
therefore matter when interpreting the two evidence formats for a state.

A passive capture error sets `paired_complete: false`, removes the failed
phase's partial files and records its error. When the active observation is
usable, the actor continues without that error entering memory, prompt, progress
or rejection feedback. Valid empty exports do not enter this failure path. Such
a state can lack passive artifacts. An active observation error can end the run
or trigger a bounded read-only transport retry. A capture retry does not replay
an executed action.

## Follow actions and model calls

`steps/step_001/action.json` leads to the next captured state, normally
`steps/step_002/`. A terminal state normally has no outgoing `action.json`.
Normally N action attempts produce N+1 states. An action remains recorded if its
after-state capture fails; `trajectory_export.status` and `errors` disclose the
missing transition.

`action_succeeded` confirms browser input delivery. Page progress and task
completion are assessed separately. Actor-facing history includes standardized
execution outcomes and observation-change diagnostics, with no private target
descriptions, private stall advisories or raw backend advice. Model turns can
exceed action counts because received rejected proposals, parsing failures and
termination consume model turns without executing browser actions. Failed
transport attempts do not consume a turn.

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

Call timing files record CDP and agent-browser method, status, duration and
error metadata. Browser events include target/renderer crashes, detach and
dialog notifications. Failure receipts include available container memory,
shared-memory use, process count and a bounded log tail; unavailable diagnostics
are recorded as unavailable. Interruption receipts preserve partial attempt
status. Credential values are sanitized from diagnostic output.

Read-only observation timeouts/internal errors permit a 3-second liveness probe
and one reattachment/retry for a live target. Crash events stop further calls to
the failed page. An action with uncertain delivery ends the attempt; no action is
replayed. The schedule retains one fresh technical rerun and uses its final
attempt for success, turns and tokens, with earlier technical costs separate.
Known target destruction or transport closure prevents another actor request
and prevents terminal acceptance. A response received before the failure check
remains in turn and usage accounting, while the attempt ends as technical failure.

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
`automated-evidence-audit/v8` and
`paired-capture-eligible-state-adjudication/v8`; an ungraded audit supplies no loss
rate. See the [effective settings contract](evaluation-protocol.md#effective-settings-contract)
for the settings compared across resumes, arms and trials.

## Judge profiles and batch receipts

Evaluation roots are relative to the selected recording: let `B` be
`recording_path.parent.parent / "evaluations"`. For a batch recording beneath
`recordings/<collection>/trial_0001/<arm>/<task-id>/`, `B` is
`recordings/<collection>/trial_0001/evaluations/`.

| Output | Location |
| --- | --- |
| Primary native evaluation | `B/profiles/primary/<run-name>/<arm>/<task-id>/<recording-hash>/` |
| Pro native evaluation | `B/profiles/pro/<run-name>/<arm>/<task-id>/<recording-hash>/` |
| Shared primary completion | `B/common/<run-name>/<arm>/<task-id>/<recording-hash>/completion.json` |
| Profile-bound copy of primary completion | Each profile's `paired_completion.json` |
| Batch queue | `B/batch_jobs/`, selected from the first recording passed to one evaluation command |
| Profile comparison | `B/profile_comparison.json`, with a numeric collision suffix when needed |

The two profiles preserve the same source hashes and validity date. Model
assignments belong in the [datacard](datacard.md#judge-delivery); invocation and
resume commands belong in the [runbook](runbook.md#controls-and-outputs).

The Batch queue contains unchanged request bodies, deterministic item IDs, input
JSONL files, provider job receipts and raw item responses. Functional submission
and completion timestamps stay inside receipts. Requests identify task, driving
arm, trial, recording hash, rubric source hash, profile, stage and attempt.
Keep evaluation selections grouped by their Batch queue root and retain the same
first recording when polling. Receipts in another group's queue are not searched;
combining already-submitted groups can submit the same work again. See the
[evaluation protocol](evaluation-protocol.md#batch-judging) for pending and
cancellation behavior.
Calls record `transport`, `batch_request_id`, `batch_job_id` and individual
`batch_items` for cost coverage.

Pending jobs are resumable. A cancellation applies to the entire selected shared
queue, including recordings and profiles using it, and is terminal for that
queue; late results cannot be imported. A submission whose acknowledgement is
uncertain blocks automatic resubmission until its actual provider job ID is
reconciled. The [evaluation protocol](evaluation-protocol.md#batch-judging)
defines these rules.
