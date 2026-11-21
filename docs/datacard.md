# Datacard

`w8-domdiff-bench` records paired browser evidence for evidence-loss analysis
and evaluates task completion, model turns and token usage under two
page-observation policies. Each selected task has two independent
actor arms and an explicitly chosen positive number of trials per arm. Task
contracts and completion rubrics are fixed before execution.

The recorder stores paired screenshot and DOM evidence in both arms. The actors
receive only their selected page observation, while the completion judge uses a
common evidence policy. Separate profiles, memory and action histories keep the
runs independent.

## Observation modes

This table defines the permitted differences. All other recorded controls must
match for a comparison.

| Difference | DOM arm | Screenshot arm |
| --- | --- | --- |
| Page observation | Formatted `dom_model.txt` and viewport-filtered interactive reference text. Numeric ChromiumRL IDs are masked in actor text. | The saved `screenshot.png`, sent once per call at the configured per-image media resolution; no extracted DOM, accessibility text, selectors or references. |
| Targeting | Current agent-browser `e` references for reference-targeted actions. | Integer coordinates from 0 to 1000, relative to screenshot width and height, converted once to CSS pixels for raw CDP input. |
| Ref-click scrolling | The action CLI can scroll a referenced target into view while resolving and clicking it. Supplied references pass viewport bounding-box filtering. | Coordinate clicks operate at the selected viewport point without reference-based scroll-into-view. |
| Observation-change source | DOM text and interactive reference changes. | Decoded screenshot pixels. |
| Content extent | Intersecting nodes and accessible labels can include text outside the painted viewport or from hidden/collapsed descendants. | Painted viewport pixels, including visual content without a text equivalent. |
| Scrolled inline paragraphs | Visible-text extraction for clipped inline-rich `<p>` elements follows the visible characters; other inline-rich blocks retain their existing prefix behavior. | Painted text follows the viewport regardless of the containing element. |
| PDFs | A valid empty structured export is shown as `[No exportable DOM content]`; no OCR or PDF text is extracted. | The rendered PDF viewport is available as pixels. |
| Page structures | Frame and shadow-tree coverage follows the DOM and reference exporters. Canvas/image/CSS-generated content may have only labels or no text representation. | Rendered frame, shadow-tree, canvas, image and CSS content appears where it is painted. |

Both actors receive the current URL as plain text, the task instruction, turn
budget, viewport dimensions, actor-maintained memory and recent action/rejection
outcomes. Both receive the same URL-change field. Observation-change fields are
modality-specific diagnostics, not proof of task progress. Recent outcomes omit
private target descriptions and raw tool diagnostics; document-language metadata
is not actor input. Navigation, keyboard input and non-reference browser
primitives use the shared action driver.

## Shared controls

| Control | Configuration |
| --- | --- |
| Actor model and endpoint | `ACTOR_MODEL` is the sole actor-model configuration and must identify `gemini-3.8-flash`; the same value is used across arms. Returned IDs must match the configured model under the returned-model acceptance contract. `GEMINI_BASE_URL` selects the endpoint. |
| Model-turn budget | 200 by default and at most 200; lower positive budgets must match across compared runs. |
| Maximum actor output | Exactly 10,000 tokens, including reasoning. |
| Task memory | At most 8,000 characters. |
| Reasoning effort | Explicitly `medium`. |
| Actor image resolution | The screenshot actor uses HIGH, recorded in effective settings. Only screenshot requests contain images. |
| Temperature | Unset in both arms. |
| Viewport | 1365 × 768 CSS pixels by default. |
| Settling interval | One second by default. |
| Browser locale | English (`en-US`, `en-US,en;q=0.9`). |
| Browser state | A launcher-recreated profile with reset enabled and no previous tasks, with build/environment provenance. |
| Action contract | One strict JSON action per response; shared vocabulary, with modality-specific coordinate fields. |
| Intervention | No human intervention or automatic language redirects. |

Comparison checks shared model settings, task contracts, budgets, schema,
source/capture controls, browser build/environment, profile freshness and grading
controls. Browser images should be selected by immutable identity; recorded image
IDs establish the build used. Matching settings do not freeze live-site content.
The [effective settings contract](evaluation-protocol.md#effective-settings-contract)
binds request behavior and browser source provenance while excluding credentials,
deployment names, ports and file locations.

## Recording contract

A complete state contains `dom.json`, `dom_full.txt`, `dom_model.json`,
`dom_model.txt` and `screenshot.png`. DOM actor states also contain the filtered
`agent_browser_actions.txt` reference snapshot. `dom_full.txt` renders the
captured viewport-scoped DOM; it is not an unbounded whole-page dump. Snapshot
limits default to 7,000 nodes and 200,000 requested text characters. The text
threshold can mark aggregate overflow without making every projection a strict
200,000-character slice.

States record artifact paths/hashes, target and session identity, capture order,
phase start/end times, interval URLs, navigation status and available
content/paint-instability metadata. `content_change_monitor` covers the main
document, known frame contexts and discovered open shadow roots; closed roots
and unreported frames remain unobserved. `content_changed_during_capture` and
`paint_changed_during_capture` are true when activity is observed and otherwise
unknown. Partial coverage never certifies an unchanged page. The screenshot sent
to the actor is the saved file. Passive evidence and capture errors do not enter
actor prompts, memory, progress, stall checks or rejection feedback. A passive
failure marks paired evidence incomplete while allowing a usable active
observation to continue. Missing URL metadata is marked explicitly. Capture
orders raw structured DOM, screenshot and DOM-arm references before producing
stored text projections. Content/paint changes flag the interval; they do not
automatically recapture it. Bulk artifact writes follow raw capture, while
per-call operational traces remain durable during capture for crash diagnosis.

Empty exports are valid observations, including PDF wrappers and loading or
blank documents. They retain all paired files, raw snapshot statistics and the
`[No exportable DOM content]` marker in `dom_model.txt`; they are not capture
failures or format gaps. Both arms use `paired-capture/v2`. Before acquiring raw
evidence for a new exact target/frame/loader, the recorder waits for
DOMContentLoaded or interactive/complete readiness and then two animation frames.
The existing 90-second CDP navigation timeout bounds this wait. Its expiry permits
capture of the current state. Same-document updates do not repeat the wait.
The existing settle interval remains in place. MIME type, readiness state and wait
duration are private records, never actor hints. Real transport, target and
capture faults retain their technical-failure handling.

Actor input preflight estimates tokens locally as UTF-8 bytes of the request's
text and structural fields, excluding base64 image data, plus 1,100 image tokens
at HIGH. One byte per text token is a conservative size
estimate, not measured usage. Requests estimated at 50% or less of the model
input limit skip `countTokens`. Larger estimates use the exact request tokenizer;
transient failures allow the same three attempts and 2/8-second backoffs with
jitter as actor transport. If token counting remains unavailable, the local
estimate determines dispatch and `local_fallback` records the uncertainty.
Confirmed or estimated input above 95% ends as `actor_input_limit`; evidence is
never truncated. Model metadata is cached, with the configured 1,048,576-token
limit as fallback. The 50% trigger is 524,288 and the 95% threshold is 996,147.
Metadata/count requests do not consume model turns or generation tokens.

The schedule is written before a batch starts and contains one row per
`(task, arm, trial)`. It records task/configuration identity, trial count, arm
order, intended recording path and technical/grading outcomes. Resume retains
completed final attempts and reconciles orphaned started rows. A technical
failure receives one fresh attempt under the same task, arm and trial; both
attempt records are retained. Freshness claims require launcher recreation,
profile reset and a zero prior-task count. Raw/reused browser sessions remain
nonfresh; pooled comparisons refuse them unless `--allow-nonfresh` is explicitly
selected and recorded.
See the [recording guide](recordings.md) for the full artifact schema.

## Completion and metrics

The primary `paired` grading policy uses the run's screenshots and saved model
DOM text, action records, final answer and technical status. A frozen task rubric
is reused across arms and trials. `completion.json` records criterion verdicts,
evidence policy, rubric/prompt hashes, configured and returned judge models and
judge usage. The judge must be explicitly set to `gpt-6.1-sol`, with 10,000 maximum output tokens and `medium` reasoning. It never falls back to the actor model.
Completion makes one request per grading attempt. Returned IDs use the shared
`returned-model-acceptance/v2` matcher: the exact case-sensitive configured ID or
that ID followed by a numeric, date or `-vN`/`-VN` version suffix. For example,
`gpt-6.1-sol-v2` matches; `gpt-6.1-sol-mini` does not.
Missing IDs, mismatches and incomplete/truncated responses are ungraded; returned
usage remains accounted for, and an explicit resume may retry the stage.

The optional `actor_native` policy uses the actor's observation type and writes
`completion_actor_native.json`. It is a modality policy rather than a replay of
the exact actor prompt. Exact-final-answer controls provide an offline answer check. Task rubrics are generated once from instruction and start URL, reviewed, then frozen for every arm and trial.

A model turn is one received actor response, including rejected proposals,
parsing failures and termination. Failed transport attempts are counted separately;
they do not consume a model turn. Timeouts, connection errors and temporary HTTP
429/500/502/503/504 responses allow two further transport attempts, with 2 and 8
second backoffs plus up to 0.5 seconds of jitter. Auth, quota, billing and other
4xx errors are not retried. Transport receipts preserve status, duration, parser
stage and reported usage; unavailable usage stays unknown.

Duplicate activation, two-action-cycle and recent-stall matches are advisory-only
and symmetric in both arms. They never reject a proposal, stop a run or reach the
actor through history, memory or rejection feedback. Action validation still
checks schema, target, values and termination requirements; the shared invalid-
proposal limit remains. Run reports expose `stall_advisory_matches` and reason
counts; arm/category summaries sum them and list the per-run counts. Each matched
proposal counts once, using the first matching advisory rule.

Action attempts and captured states are counted separately. Input/output tokens
per turn use received actor responses as the denominator. Cached input and
reasoning are subsets, not extra totals. Missing response usage uses the labelled
known-usage denominator. Actor costs disclose response and failed-transport components separately; judge costs remain separate.

Browser/renderer crashes, CDP stalls, capture failures, exhausted reference
snapshots, recorder errors and exhausted transient actor transport retries are
technical failures. Website blocks, actor failure, turn caps and provider auth,
quota or billing errors are separate outcomes. One fresh technical rerun is
allowed per scheduled task/arm/trial in both arms. Success, turns and tokens use
the final attempt; prior technical-attempt costs are retained separately. A second
technical failure remains a technical outcome, outside agent-failure counts.

Technical outcome, actor-reported success and independent completion remain
separate. Ungraded and uncertain outcomes are not confirmed failures. Aggregation
uses the full schedule, reports unmatched arms and grading coverage, and provides
all-attempt costs, definitive-grade success rates, successful-pair efficiency and
pass@k bounds. See the [evaluation protocol](evaluation-protocol.md).

## Browser recovery

Target and renderer crash/detach events stop calls to a failed page. A timed-out
read-only observation or CDP internal error triggers a target liveness probe of
at most 3 seconds. A live target permits one session reattachment and one retry
of that observation; a dead target ends the attempt. Actions are never replayed.
Uncertain action delivery ends the attempt as a technical failure. Known target
destruction or transport closure is checked before and after an actor response
and before a terminal answer is accepted. The received response and its usage
remain recorded; a browser failure ends the attempt under the same technical
rerun policy in both arms. No request is dispatched after a known failure.

The browser unregisters its capture component during session disposal. The
assertion-enabled build uses `SYS_NICE` for renderer-priority changes when tabs
switch. The recorder preserves crash evidence and applies the same fresh-attempt
policy in both arms for browser failures.

## Task catalog and provenance

The default catalog is [data/tasks.jsonl](../data/tasks.jsonl), containing
`task_01` through `task_40`. Each row has eight fields: `task_id`, `task_name`,
`category`, `instruction`, `start_url`, `stopping_condition`, `constraints`,
and `difficulty`. The catalog contains ten tasks at each level: `easy`, `medium`,
`hard` and `complex`. Difficulty does not determine success or change the
200-turn cap. Easy tasks use one site and one to three pages for a few facts or
a simple search or filter (about 5–15 turns). Medium tasks combine filters,
sorting or detail pages (about 15–40 turns). Hard tasks use deep navigation or
two to three sites with constraints (about 40–100 turns). Complex tasks compare
or calculate across many items and several sites, generally under 150 turns.
These are workload guidelines, not measured task lengths.

Constraints are shared browser, access and read-only policies. Task-specific
scope and checkable deliverables belong in the instruction and stopping condition.

The loader accepts any frozen local JSONL catalog using this task contract.
The dataset [README](../data/README.md) describes the task fields and scope.
Public, read-only tasks use bounded sets and
checkable outcomes; recorded observations establish changing page values.
Catalog and rubric hashes bind the schedule, and every run manifest retains
the exact catalog SHA-256. Manual tasks without a catalog record `null`.

Internal curation records date-sensitive task deadlines. Scheduling refuses a task
after its inclusive UTC `valid_until` date unless `--allow-expired` is set. The
schedule records the deadline and any override; the run manifest also records
the check date. Historical search windows retain their specified dates; rolling
runtime values have no preset expiry.

## Scope

Tasks target public-web research and extraction. Viewport limits, accessible
labels, rendering, dynamic content and live-site changes affect the available
evidence. Text from hidden or collapsed descendants, full accessible labels,
`aria-label`/`aria-labelledby` and image alt text are inherent DOM-format
properties; their text need not be painted in the viewport. A label may be
sourced inside, near or outside the viewport while describing an intersecting
control. Viewport bounding boxes do not prove absence of clipping or occlusion.
Screenshot pixels retain visible canvas, image, CSS, frame and shadow content
that can be absent from the DOM projection. These are inherent properties of
the recorded formats.

Visible-text extraction for scrolled inline-rich content covers `<p>` elements
only. Other inline-rich blocks retain their existing first-500-character prefix
behavior, which can omit visible lines after scrolling. Preserve the saved formats
and do not infer that all viewport text is represented. The within-run audit
uses paired source evidence to distinguish coverage from actor behaviour.
Captures are sequential, so navigation flags and timestamps describe
the interval rather than prove simultaneous content. Benchmark results include
targeting and action behavior as well as page interpretation.

Retain source URLs, timestamps, task hashes and run provenance with exported
observations.

## Verifiers and within-run audit

Every actor trial receives common completion grading, both auxiliary verifiers
and the audit. Rubric generation and dependency checking use `gpt-5.2`.
Both verifiers use `gemini-3.5-flash-lite` for relevance, evidence analysis,
disambiguation, reality checks, rescoring, side effects, outcome and failure
analysis, action-only scoring and both validity stages.
The named `pro` profile uses `gemini-3.1-pro-preview` for these same native
stages. Its outputs are isolated from primary results. The actor model is never
a judge. Native profiles keep the same prompts, selection, scoring, validation
and retry budgets.

Inventory uses `gemini-3.1-pro-preview`; evidence-loss adjudication and common
completion use `gpt-6.1-sol`. Verifier and audit output limits remain unset;
the 115,000-token verifier input guard remains active. Images use high detail.
Task-only validity uses a recorded UTC date frozen from the run.
Native verifier returned IDs are recorded for every call and compared with the
same matcher as diagnostics. A native mismatch does not itself refuse a grade;
completion, inventory and adjudication do refuse mismatches. Finite nonboolean
earned points must lie between zero and the criterion's positive finite weight.
Invalid numeric responses use the existing repair budget. Exhausted scoring or
authentication produces an ungraded result with an explicit `judge_fallback`
reason, null score fields and retained call/usage receipts; baseline scores never
substitute for an unavailable rescore. Authentication refresh consumes the
configured endpoint attempt budget and cannot loop indefinitely.

Staged screenshot and DOM inputs always originate from one recording hash.
Each verifier sees every state available in its own format, including states
flagged for navigation. Missing-format states remain explicit gaps with their
original IDs; full action history and observed URLs are preserved. This declared
input-contract adaptation leaves top-K, scoring, penalties and citation rules
unchanged, and contiguous runs preserve original loader behavior.
The native JSON output contract is `native-rubric-output-contract/v3`: examples
use single JSON braces, criterion bounds are rendered, and unmet conditional
criteria retain their response positions while contributing no points to totals.
DOM `citation_checks` record state-ID and extractable exact-quote diagnostics,
including quote coverage. Citations are not enforced. The diagnostic records
bypass score normalization and do not alter requests, scores or audit feedback.
DOM photo examples and taxonomy source headers retain their original text;
photo examples cannot establish pixel facts absent from the DOM text.
`action_definitions=None` is unsupported for programmatic calls outside the
CLI runners, which supply explicit action definitions.

Directional-loss decisions use the same state IDs for both formats, requiring a
complete paired capture and no navigation during capture. Unverified URLs remain explicitly unavailable in both shared inputs.
Record format gaps, navigation states, eligible IDs and coverage for each run.
No eligible states means an ungraded audit with a reason, never zero loss. Failed
actors with usable evidence remain auditable. Missing auxiliary results block the
full audit rather than being replaced with invented analyses.

Outcome grading interprets dates from the task and recorded evidence. Unresolved
years are disclosed in the reasoning rather than inferred from a collection year.

Audit receipts use `automated-evidence-audit/v8` with prompt version
`paired-capture-eligible-state-adjudication/v8`, identifying the shared-URL,
eligible-state and response-acceptance contracts. Inventory and adjudication each
allow three validation attempts; refusal, malformed output and exhausted repair
retain their attempt receipts and usage. An ungraded audit has no pooled loss
rate. Resume may retry it without repeating actor execution.

Screenshot loss and DOM loss are computed separately inside each actor run.
Report all four values per task/trial side by side, retaining actor identity.
Never pair observations across actor runs. Shared absence and temporal
inconsistency do not automatically establish directional loss.

Actor tokens per model turn include received responses for rejected proposals,
parsing failures and termination. Failed transport attempts have a separate count.
Report input/output averages separately; cached input and reasoning are subsets.
Missing usage uses explicitly labelled known-usage denominators. Publish run
mean/median/distributions by arm and category. Common success, auxiliary process
scores, threshold success, outcome success and frozen full-score checks stay
separate; runtime penalties and judge fallbacks have their own fields. All judge
cost streams remain separate from actor costs.

## Judge delivery

| Stage | Model | Transport |
| --- | --- | --- |
| Actor, both arms | gemini-3.8-flash | Normal; input preflight unchanged |
| Rubric generation and dependency check | gpt-5.2 | Normal |
| Native screenshot and DOM verifiers, all stages | gemini-3.5-flash-lite | Batch; medium thinking |
| Native Pro comparison profile, all stages | gemini-3.1-pro-preview | Batch; medium thinking |
| Common paired completion | gpt-6.1-sol | Batch; medium reasoning |
| Audit inventory | gemini-3.1-pro-preview | Batch; thinking unset |
| Audit adjudication | gpt-6.1-sol | Batch; reasoning unset |

`JUDGE_TRANSPORT` selects `batch` (default) or `normal` for judging. The actor,
its countTokens preflight and rubric preparation keep normal transport. Each
batch item contains the same request body as normal delivery. Ready calls share
provider/model/stage rounds; relevance precedes selected-state analysis and
global stages, and inventory precedes adjudication. Independent native verifiers
and completion can have requests ready in the same round. Dependent rounds can
take hours to days, even with each provider targeting a 24-hour window.

Every item binds a recording, rubric source, native profile, stage, call identity
and attempt. Submitted job IDs and raw responses are durable. Resume polls saved
jobs and replays answered items through the same validators. Pending work is not
an ungraded judgment or task failure. A cancelled collection cannot import late
results or publish grades. An uncertain submission acknowledgement blocks
resubmission until its actual provider ID is reconciled; batch creation is not
idempotent. Known outstanding jobs are cancelled; an unknown job ID is reported
for provider reconciliation.

Native output settings, profile and transport are included in the effective
settings guard. Common completion has no native-result input and is shared
across judge profiles. Native results influence both audit prompts and audit
availability, so the profile comparison repeats the audit independently under
each native profile, always within the same actor recording. Its screenshot-only
subsets are identified separately from each audit's screenshot-complete,
DOM-incomplete coverage and confirmed DOM loss. Agreement is reported on both
subsets, their union and intersection; missing audits leave those comparisons
unavailable. These are judge-defined subsets requiring review, not human accuracy
labels. Per-profile quality counts cover ungraded native results, observed repair
events, explicit refusals, blocked audits and missing loss values. Primary and Pro
grades never enter the same aggregate.

Batch receipts identify the pricing mode. Actor, completion, each native verifier,
inventory, adjudication and rubric preparation retain separate cost streams.
Unknown item usage stays unknown, including failed items before a successful
retry. [Cost assumptions](cost-estimate.md) are estimates, not measured spend.
