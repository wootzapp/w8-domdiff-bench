# Evaluation protocol

Evaluation compares two independent browser actors on the same task, with an
explicit positive trial count per arm. Each actor has its own action history,
observations, memory and final answer. Completion is graded against the same
frozen task criteria, using evidence saved within the run being assessed.

The [datacard](datacard.md#observation-modes) defines permitted arm
differences and shared controls. The [recordings guide](recordings.md) describes
artifacts and provenance, and the [runbook](runbook.md) provides commands.

## Task and rubric contract

A task consists of an instruction, start URL, stopping condition and
constraints. The [terminology](architecture.md#terminology) distinguishes a
scheduled run from its actor attempts, a trial and a paired state. The launcher
combines the instruction, stopping condition and constraints into the
instruction stored in `task.json`. A rubric must match that expanded text, the
source task ID and the start URL.

Freeze one rubric per task before collection and reuse it across arms and trials.
Criterion IDs and descriptions remain unchanged. Rubrics are neither inferred
from an actor's final answer nor supplied as additional actor context. Criteria
with matching IDs in different tasks remain separate criteria.

The configured actor settings, browser build, capture policy and grading settings
must remain consistent across the selected tasks and trials. Requested model IDs
and returned model IDs are both retained. Environment variables take precedence
over `.env` values.

## Empty observations and readiness

`paired-capture/v2` accepts empty structured exports as valid observations in
both arms. Their saved DOM model contains `[No exportable DOM content]`; no OCR
or PDF text extraction supplements it. MIME type, readiness and wait duration
stay private. Both arms retain the settle interval and use the existing CDP
navigation timeout for a different target/frame/loader to reach DOMContentLoaded
or interactive/complete, followed by two animation frames. Expiry captures the
current state; same-document updates do not repeat the wait.

Empty DOM content is not a missing capture. A complete pair remains eligible
under the ordinary navigation and integrity rules. Completion and both native
verifiers receive the saved empty DOM model and/or screenshot under their normal
evidence policies. The audit compares the same recording's formats: criterion-required
facts established only by screenshots can yield DOM loss, while facts absent
from both formats yield no directional loss. No score or loss is forced solely
because an export is empty; shared context and evidence from other states still
apply. Genuine missing captures remain gaps and are excluded from directional
loss decisions under the existing coverage policy.

## Effective settings contract

`effective-settings/v1` records the behavior that must remain consistent on
resume and across compared arms/trials: configured models and providers, routes
and normalized base URLs, reasoning and temperature, output caps, turn and
memory limits, actor transport and browser recovery policies, global screenshot
media resolution, actor input preflight and observation contracts, prompt/schema
hashes and versions, frozen rubric hashes, normalized endpoint-configuration
content hashes, browser protocol pins and available actual browser source
revisions. Rubric hashes bind one task; different tasks naturally have different
rubric hashes.

Credentials, connection ports, container and Compose names, image names/tags and
file locations do not define behavioral settings. Normalization excludes those
deployment details while preserving the endpoint host/path and actual browser
source provenance. Source receipts and artifact hashes remain available for
integrity checks. A changed effective contract is refused before execution or a
cached stage is reused, with the differing fields identified. Relocating an
identical configuration does not change its normalized content hash.

## Scheduling and execution

Trial count is a positive integer supplied through `--trials`; it has no
default. Before launching child processes, `task_cli.main()` writes one
`ledger.jsonl` row per scheduled `(task, arm, trial)` run. Rows bind
task/configuration identity, catalog and rubric file hashes, intended recording
paths and execution order.

Both arms of a task/trial run back to back, alternating which arm starts by task
and trial. Each actor attempt requires launcher recreation, profile reset and no
prior task use to establish a fresh browser profile. Both final actor attempts
finish before their judges start.

A row remains in the schedule regardless of its outcome. A technical failure
permits one fresh attempt with the same task, arm and trial. Both attempts
remain recorded. Resume reconciles interrupted work and continues a pending
rerun; it skips completed final attempts. Website blocks, actor failures, turn
caps and provider auth/quota/billing outcomes do not trigger this rerun. A
changed task set, trial count or frozen configuration requires a separate batch
name. Output-name collisions reserve the next free numeric suffix. `--resume` is
explicit and requires an existing ledger or schedule preview in the selected
directory. A planning-only preview is not an execution ledger and must not be
renamed as one; with the approved rubric files present, scheduling creates or
validates the executable ledger.

Success, turns and tokens use the final attempt. Prior technical-attempt costs
remain separate. A final technical outcome is reported separately from actor
failure and definitive completion failure. Collection reporting exposes its
primary completion as ungraded and retains any saved grade as
`technical_completion_diagnostic`. `confirmed_success_rate_agent_eligible`
excludes final technical outcomes while schedule-wide bounds preserve their
uncertainty. Failed actor transport attempts are counted separately from model
turns, which count received responses.

## Execution guards

| Guard or outcome | Handling |
| --- | --- |
| Duplicate activation or stalled cycle | Private advisory only in both arms; it never rejects a proposal or enters actor history. Counts and reasons are available per run and arm. |
| Invalid action proposal | Schema, reference, coordinate, value and termination checks can reject it. Four consecutive rejections end with `invalid_action_limit`; this is not the stall advisory. |
| Actor transport | Timeouts, connection failures and HTTP 429/500/502/503/504 allow two further attempts with the configured backoffs. Auth, quota, billing and other non-retryable errors do not use them. |
| Read-only browser observation | A timeout/internal CDP error can use the existing liveness probe and one reattachment/retry; browser actions are never replayed after uncertain delivery. |
| Technical failure | Browser/renderer crash, target or CDP failure, active capture failure, reference-snapshot exhaustion and recorder errors end technically. Actor input overflow/preflight faults and exhausted retryable actor transport also have technical classes. The launcher permits one fresh actor attempt. |
| Nontechnical outcome | Website blocks, actor-reported failure, turn cap, invalid-action limit and provider auth/quota/billing errors do not receive that technical rerun. |
| Empty export / readiness expiry | Capture continues under the shared empty-observation/readiness contract; neither condition alone is technical failure. |

The thought field is limited to 1,200 characters. Limits, retry values and model
settings are listed in the [datacard](datacard.md#shared-controls); this table
defines how those guards affect evaluation, rather than a separate settings set.

## Validation

[`inspect_recording()`](../w8bench/task_recorder/prepare_verifier_data.py) checks
finalized recordings before grading or export. It validates task/final metadata,
state and turn numbering, action records, local paths, artifact hashes,
screenshot dimensions and the selected observation hash. Actor request text is
reconstructed from permitted sources; instructions, schema and request settings
must match the frozen policy. Passive files on disk are not actor input.
Screenshot progress must agree with screenshot change.

[`run_full_comparison.main()`](../w8bench/verifier/run_full_comparison.py) validates
the scheduled task/arm/trial set and unique recording paths. Finalized recordings
must match their scheduled task, arm, run name and controls. The comparison also
checks returned actor models, fresh-profile provenance, browser builds/runtime
environments, capture policies and grading controls. Within each arm, its actor
policy must remain consistent across trials.

A finalized recording that fails validation stops comparison. A missing or
unfinished recording remains represented by its ledger outcome and recoverable
usage. Public page content and model aliases can change independently of these
recorded settings.

## Completion grading

[`grade_run()`](../w8bench/verifier/completion.py) uses the `paired` primary
evidence policy for both actor arms. The judge receives the task, start URL,
frozen criteria, ordered `dom_model.txt` states and screenshots, executed-action
records, final answer and technical run status from the same recording. Primary
grading does not add executable-reference snapshots or another run's evidence.
Missing passive artifacts are identified as unavailable rather than substituted.

The judge is explicitly selected as `--judge-model gemini-3.6-flash`; it never derives
from the actor. Model grading uses medium reasoning, a 10,000-token output budget
and no action tools. Completion has one request per grading attempt and no
automatic response-repair loop. `--execute` enables full evaluation;
without it, the command performs a read-only preflight.

Each criterion receives `success`, `failure` or `uncertain`, a reason and existing
state references. Success requires an observation citation. Changed criterion
IDs/order, invalid verdicts or nonexistent cited states are rejected. The overall
verdict is failure if any criterion fails, otherwise uncertain if any criterion
is uncertain, otherwise success.

A rubric containing an author-designated `expected_answer` uses an offline exact
answer check. It passes only when the run completed normally and the stripped
answer matches exactly. This checks the designated answer, not browser side
effects, and makes no judge call.

`completion.json` binds the grade to the recording fingerprint, rubric hash,
evidence policy, judge prompt/schema hashes, model IDs, endpoint and output budget.
It stores criterion verdicts, response ID and returned usage. The recording is
checked again before saving the grade. A failed, malformed or incomplete judge
response yields an ungraded result with `judge_error` and any returned usage.
The shared `returned-model-acceptance/v2` policy accepts the exact case-sensitive
configured ID or that ID with a numeric/date/version suffix, such as
`gemini-3.6-flash-001`. A different family such as
`gemini-3.6-flash-mini`, an absent ID, incomplete status or truncation is refused.
Refused attempts retain their usage and reason. An explicit evaluation resume may
retry the ungraded stage under the same effective settings.

The optional `actor_native` policy uses the actor's observation type: DOM-model
text plus interactive references, or screenshots. It writes
`completion_actor_native.json` and leaves the primary grade intact. It does not
replay the actor's complete prompt or memory. Primary success comparisons continue
to use `completion.json`; evidence policies and grading controls cannot be mixed.

## Measurements

Primary completion, native rubric/process scores, native outcome judgments and
evidence loss are separate results. They must not be substituted for one
another.


Each final actor recording in each trial receives both auxiliary verifiers and
one evidence audit within that recording when its inputs permit evaluation. Thus one
`(task, trial)` has two independent audits, one per driving arm. Verifier
process scores, threshold success (`rubric_is_success` at 0.8), outcome success
and full points on frozen criteria are auxiliary signals. Runtime side-effect
penalties remain separate from that frozen full-score check and never change the
primary completion rubric.

The audit compares only the same recording's screenshots and DOM-model text. Available
states remain in their own verifier even if the other format is missing.
Directional decisions use shared state IDs with complete captures and no
navigation within the evidence-acquisition interval. Content/paint-instability
flags are diagnostic and do not add an eligibility exclusion. Missing URL
metadata is explicitly unavailable in the shared timeline. Report gaps,
navigation, eligible states and coverage; retain failed actor runs with usable
evidence. No eligible states or failed auxiliary results produce a missing audit
with a reason, not zero loss. Preserve both directions for each driver arm.

All judges receive the same verified observed-URL timeline, including the initial
state. Auxiliary verifiers and the audit use the recorded task-validity date.
Shared history contains execution facts, not actor notes or DOM-derived target
descriptions. Evidence selection,
scoring and penalties use the native rubric policies. Native returned-model
mismatches are diagnostic and do not themselves refuse a grade. Every native
call retains configured/requested/returned IDs and its stage path.

Baseline, rescore and penalty earned points must be finite nonboolean numbers
within `0..max_points`, with a positive finite nonboolean weight. Missing or
invalid values enter the existing response-repair loop. Exhausted scoring writes
an ungraded result with null scores and a `judge_fallback` reason; it cannot
reuse a baseline or invent zero. Authentication exhaustion is terminal for the
stage, retains all attempt usage and permits the batch to continue. Rubric draft
generation similarly records an ungraded task, continues other tasks and reports
a partial catalog with a nonzero exit status.

Native prompts identify their JSON output contract as
`native-rubric-output-contract/v3`. Unmet conditional criteria remain in
response order and are excluded from score totals. DOM `citation_checks` record
supplied state identity and exact quoted-text checks without changing accepted
analyses, requests, scores or audit feedback. Diagnostic records bypass score
normalization; the evaluation controller copies them directly into the stage
record for reporting. Quote coverage is explicit when citations contain only
free prose. The DOM verifier remains restricted to supplied textual evidence;
diagnostic citation checks do not turn a score into a visual observation.

Inventory and adjudication each have three validation attempts. Their returned
IDs and completion status use the shared acceptance policy. Failed/refused
attempts keep usage and error receipts; ungraded results have no evidence-loss
rate and cannot enter pooled loss denominators. Audit schema
`automated-evidence-audit/v8` and prompt
`paired-capture-eligible-state-adjudication/v8` identify this contract. Judge repair
calls, ungraded stages, citation diagnostics and unknown usage are reported
separately.

| Measurement | Definition | Artifacts |
|---|---|---|
| Model turns | Received actor responses, including rejected proposals, malformed/incomplete responses and termination. Failed transport attempts do not count as model turns. | `decisions.jsonl`, per-turn `result.json`, manifest/final `model_turns`. |
| Action attempts | Accepted executable actions delivered to the browser, including execution errors. Rejections and termination execute no browser action. | Manifest `steps`, state `action.json`, trajectory. |
| Captured states | Committed active observations. Normally N actions produce N+1 states; capture errors can leave an incomplete transition. | Manifest `states`, `trajectory_export`. |
| Completion | Independent rubric verdict, separate from actor claims and technical status. | `completion.json`. |
| Transport attempts | Each actor generation HTTP attempt, its duration, status and reported usage, separately from received responses. Input-preflight attempts are recorded separately and are not model turns. | Per-turn `transport_attempts.jsonl`; raw failed response and parser receipts. |
| Technical attempt cost | Earlier technical attempts retained separately from final-attempt success/turn/token metrics. | Ledger `attempts`, `technical_attempts`, `cost_streams["technical_attempts:actor"]`. |
| Actor usage | Returned input/output totals, plus cached-input and reasoning subsets. | Provider response and decision `usage`. |
| Tokens per model turn | Input and output separately over received actor responses. Each component uses its own known-response denominator when usage is missing; its exact mean is unavailable until coverage is complete. Failed transports are separate. | Per-run `tokens_per_turn`, arm/category distributions. |
| Judge usage | Paired/actor-native completion, each verifier and audit inventory/adjudication, separate from actor usage. Rubric preparation is a separate once-per-task stream, not charged again as trial work. | Completion/evaluation receipts and named usage streams. |
| Timing | Decision-call latency, action delivery duration and recorder capture durations. | Decision `latency_seconds`, action `duration_seconds`, state `capture`. |

The [datacard](datacard.md#shared-controls) is the settings reference. Cached
input is a subset of input tokens; reasoning is a subset of output tokens.
Neither is added again to input-plus-output totals. Local file token estimates
are not provider itemization. Passive recording consumes no model tokens; judge
requests using that evidence have separate usage. Actor cost includes received
responses and any reported failed-transport usage; the response-only
token-per-turn denominator is not extended by those transport attempts.

Decisions record `response_status`, `incomplete_details`, `returned_model`,
`reasoning` and `output_limit_hit`. The limit flag is true when the provider reports
`max_output_tokens` as the incomplete reason or output at the configured budget;
it is null without a response. Inspect status and incomplete details before
interpreting the flag as truncation. An incomplete actor response executes no
action, while its call and returned usage remain counted.

Decision latency includes request preparation and response handling; it is not
total browser-task wall time. Action durations and settling/capture work are
separate. Capture phases are sequential, so their durations and navigation flags
matter when interpreting the paired evidence.

## Denominators and coverage

Technical outcomes, actor-reported status and completion grades are separate.
`completed` means normal actor-loop termination, not verified task success.
Startup errors, API/recorder errors, interruptions and turn limits remain
scheduled runs. Technical status alone is not substituted for a completion
grade.

Completion labels are success, failure, uncertain and ungraded. Uncertain and
ungraded are not confirmed failures. Report grading coverage together with
`confirmed_success_rate_all_attempts` and `success_rate_definitively_graded`.
The all-attempt confirmed-success fraction is a lower bound when grades remain
unknown. Both `definitively_graded_runs` and `definitively_graded_tasks` count
definitively graded scheduled runs.

`scheduled_attempts`, `scheduled_pairs` and `scheduled_tasks` describe the full
ledger; `scheduled_attempts` counts scheduled run rows, while each row’s
technical attempt history is retained separately. `paired_attempts` counts
task/trial pairs with both finalized recordings; `paired_tasks` counts tasks
with at least one such pair. `unmatched_arms` lists missing or unfinalized
recordings. Paired-only counts do not replace the full scheduled denominator.

Interrupted or partial recordings retain known decision usage as lower bounds.
`cost_coverage`, `tokens_complete`, `turns_complete` and `turns_missing_usage`
identify gaps. Exact all-attempt means/medians are null when coverage is incomplete;
`mean_tokens_all_attempts_lower_bound` and `mean_turns_all_attempts_lower_bound`
use known totals divided by all scheduled attempts. A startup failure with no
request is a known-zero actor cost; an unknown interrupted request is not.
Response-token coverage and USD-cost coverage are distinct: an unreported failed
transport can leave cost unknown without adding a response to the token-per-turn
denominator. Per-stream `cost.coverage` records that distinction.

Saved judge costs include primary and optional secondary grades.
`judge_calls_missing_usage` and `judge_processes_without_usage` disclose missing
receipts. A judge process without a saved result does not establish a zero-cost
request. Regrading writes the selected grade file again; saved files alone are
not an append-only history of every manual grading invocation.

Normal comparisons require fresh browser provenance. The
[`compare_results`](../w8bench/verifier/compare_results.py),
[`run_full_comparison`](../w8bench/verifier/run_full_comparison.py) and
[`aggregate_runs`](../w8bench/verifier/aggregate_runs.py) modules accept
nonfresh recordings only with `--allow-nonfresh`; the report records that
policy. A raw runner or reused browser profile must not be described as a fresh
run solely because a task counter is zero.

## Repeated-trial results

For n scheduled trials, c confirmed successes and an evaluated k with
`1 <= k <= n`, the estimator is:

```text
pass@k = 1 - C(n-c, k) / C(n, k)
```

The numerator is zero when `n-c < k`. With u uncertain/ungraded outcomes, c gives
the confirmed lower bound and c+u the possible upper bound. `estimate` is null
when those bounds differ. Results are task-macro averages over the same scheduled
tasks, with task-specific criterion results retained separately. Unsupported k
values are rejected. All-trials-success reliability measures a different event
from at least one success among k attempts.

All-attempt costs include failed trials. Success-conditioned means can use
different task sets in each arm. Paired successful deltas use the same task/trial
with both primary grades successful; positive screenshot-minus-DOM deltas mean
more screenshot cost or turns. These summaries do not calculate confidence
intervals or verify completion through an application-state oracle.

## Verification checks

Offline tests cover actor request isolation, artifact binding, counters, grading,
and ledger scheduling/resume/failure handling with synthetic responses. Browser
capture checks test scroll/focus preservation on a synthetic page. These establish
specific file and execution contracts; completion on public tasks is assessed
through recorded runs and independent grades. Sequential capture, page changes,
grounding differences and judge uncertainty remain relevant when interpreting
results.

## Batch judging

Judges use `JUDGE_TRANSPORT=batch` by default; `normal` sends the same request
bodies synchronously. Actor requests and countTokens preflight, plus rubric
preparation, stay normal. Both native pipelines use `gemini-3.5-flash-lite` for
every stage. The isolated `pro` comparison profile uses `gemini-3.1-pro-preview`.
Completion and audit assignments are listed in the [datacard](datacard.md#judge-delivery).

The controller collects ready requests across selected recordings, preserving
all evidence-selection and validation dependencies. Submission, provider job
identity and item responses are durable. The standalone evaluator and synthetic
smoke command return 75 for pending work; repeat the same command to poll it and
advance ready stages. The task launcher can return 0 after recording while its
ledger still has `judge_exit_code=75`, `evaluation_outcome=batch_pending` and
`grade_completed=false`. Its exit status does not establish completed judging.
The first recording selects the Batch queue at
`recording_path.parent.parent / "evaluations" / "batch_jobs"`. Keep recordings
grouped by that queue root and retain the same first recording when polling.
Combining groups that already submitted to separate queues can leave their
receipts undiscovered and cause duplicate submission; do not combine them.
Replaying a saved answer does not make another provider call. Invalid answers
and failed items enter the existing validation/transport retry budgets, with
distinct attempt IDs. Expiration keeps completed items and retries only
unanswered work. No acceptance, citation, scoring, penalty or voting rule
depends on transport.

Creation acknowledgement can be uncertain because provider batch creation is not
idempotent. Such a receipt blocks automatic resubmission until its job ID is
reconciled. Cancellation records a terminal marker before cancelling known jobs;
late results cannot be published. Its scope is the entire shared Batch queue
selected from the first recording, including other recordings/profiles using it.
It returns 130 and is terminal for that queue, rather than a pause/resume
action. Unknown job IDs require provider reconciliation. There is no CLI switch
that clears a cancellation or identifies an unacknowledged job automatically.
Batch job files are split at provider file/request limits without dropping or
truncating items. A single request that exceeds a provider's batch file limit is
refused rather than altered; the operator can select normal transport in a
separate evaluation with matching settings. Neither transport enlarges a model's
input context or changes the 115,000-token native input guard.

Primary and Pro outputs have separate profile roots, bound to the same recording
and rubric. Common completion is shared because native results cannot affect it.
Each profile repeats inventory and adjudication, since native evidence analyses
and scores do reach those prompts. The comparison reports exact per-criterion
point agreement and disagreements on each audit's screenshot-only subset and
on their union and intersection, per-arm directional losses and coverage, and
profile-specific tokens/costs. It also reports ungraded native results, observed
repair events, explicit refusals, audits blocked by an unavailable native verifier
and runs without loss values, including per-run receipts and per-arm counts. It
does not infer accuracy from agreement alone. Missing/ungraded profile judgments
remain unavailable rather than disagreements or zero loss.

Google Chat results accept snake_case and camelCase finish-reason and token
fields. Native audit response validation retains all supported usage fields;
unrecognized usage metadata is preserved in receipt diagnostics and excluded
from SDK validation. Original provider responses remain unchanged.

Costs use the recorded delivery mode and keep actor spending separate. Batch
rates apply to actual batch items, including repeated paid attempts. Missing
item usage prevents an exact total; known spending remains a labelled lower
bound. Pricing is defined in [run_metrics.py](../w8bench/verifier/run_metrics.py).
