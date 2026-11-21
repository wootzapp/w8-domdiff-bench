# Datacard

`w8-domdiff-bench` records paired browser evidence and compares task completion,
model turns, token usage and evidence loss. Each task has independent DOM and
screenshot arms, with an explicitly chosen positive trial count per arm. Task
contracts and completion rubrics are fixed before execution.

Each run privately records both formats; its actor receives only the permitted
observation. Browser profiles, memory and action histories are independent.
The [architecture glossary](architecture.md#terminology) defines the terms used
throughout the documentation. The [runbook](runbook.md) gives the execution order
and commands.

## Observation modes

This table defines the permitted differences. Other effective settings must
match across the compared arms.

| Difference | DOM arm | Screenshot arm |
| --- | --- | --- |
| Page observation | Formatted `dom_model.txt` and viewport-filtered interactive reference text. Numeric ChromiumRL IDs are masked in actor text. | The saved `screenshot.png`, sent once per call with global `MEDIA_RESOLUTION_HIGH`; no extracted DOM, accessibility text, selectors or references. |
| Targeting | Current agent-browser `e` references for reference-targeted actions. | Integer coordinates from 0 to 1000, relative to screenshot width and height, converted once to CSS pixels for raw CDP input. |
| Ref-click scrolling | The CLI can scroll a referenced target into view while resolving and clicking it. Supplied references pass viewport bounding-box filtering. | Coordinate clicks operate at the selected viewport point without reference-based scroll-into-view. |
| Observation-change source | DOM text and reference text, ignoring ref-only renumbering. | Decoded screenshot pixels. |
| Content extent | Intersecting nodes and accessible labels can include text outside the painted viewport or from hidden/collapsed descendants. | Painted viewport pixels, including visual content without a text equivalent. |
| Scrolled inline paragraphs | Visible-text extraction for clipped inline-rich `<p>` elements follows visible characters; other inline-rich blocks can retain a text prefix. | Painted text follows the viewport regardless of its containing element. |
| PDFs | A valid empty structured export is shown as `[No exportable DOM content]`; no OCR or PDF text is extracted. | The rendered PDF viewport is available as pixels. |
| Page structures | Frame and shadow-tree coverage follows the DOM and reference exporters. Canvas, images and CSS-generated content can have labels or no text representation. | Rendered frame, shadow-tree, canvas, image and CSS content appears where painted. |

Both actors receive the task instruction, current URL, turn budget, viewport,
actor-maintained memory and up to six recent action/rejection outcomes. Shared
URL changes count as observation changes in both arms. Modality-specific changes
are diagnostics, not proof of task progress. Actor history omits private target
context, raw backend diagnostics and stall advisories; document language stays
in records. Navigation, keyboard input and non-reference primitives use the
shared action driver.

## Shared controls

| Control | Configuration |
| --- | --- |
| Actor model | The sole `ACTOR_MODEL` value must identify `gemini-3.8-flash` in both arms. Returned IDs must satisfy the configured-model acceptance contract. |
| Actor endpoint | `GEMINI_BASE_URL`, with `models/{model}:generateContent`. |
| Model-turn budget | 200 by default and at most 200; lower positive budgets must match across compared runs. |
| Maximum actor output | Exactly 10,000 tokens, including thinking. |
| Task memory | At most 8,000 characters. |
| Action thought | At most 1,200 characters, separate from memory. |
| Consecutive rejected proposals | Four end the run as `invalid_action_limit`; advisory matches do not contribute. |
| Thinking | `MEDIUM`, recorded as `medium`. |
| Screenshot resolution | HIGH only, through global `MEDIA_RESOLUTION_HIGH`. No per-image override. |
| Actor image allowance | 1,100 tokens per image for local input estimation; not measured provider usage. |
| Temperature | Omitted. |
| Viewport | 1365 × 768 CSS pixels by default, device pixel ratio 1; screenshot dimensions must match. |
| Settling interval | One second by default, for initial and post-action capture. |
| Readiness | Wait for the exact target/frame/loader to reach DOMContentLoaded or interactive/complete, then two animation frames. Same-document updates skip the asynchronous wait. |
| Readiness deadline | Reuses the CDP navigation timeout, 90 seconds by default. Expiry permits capture as-is. |
| CDP / agent-browser timeout | 90 seconds each by default. |
| Actor HTTP timeout | 180 seconds per request. |
| Browser locale | `en-US`, with `en-US,en;q=0.9` accepted. |
| Browser state | Launcher recreation, profile reset and zero prior tasks establish freshness; raw/reused sessions are nonfresh. |
| Action contract | One strict JSON action per received response, with modality-specific target fields. |
| Intervention | No human intervention or automatic language redirects. |

Comparison checks models, task contracts, budgets, schemas, capture policy,
browser build/environment, freshness and grading settings. Matching controls do
not freeze public-web content or model aliases. Credentials, ports, deployment
names and file locations are excluded from the
[effective settings contract](evaluation-protocol.md#effective-settings-contract).

The browser build is pinned by [protocol/browser-build.json](../protocol/browser-build.json).

| Browser setting | Value |
| --- | --- |
| Image tag | `w8-core:domdiff-bench`; run provenance also records the immutable image ID. |
| Chromium version | `152.0.7948.0` |
| Overlay revision | `79ef492157bd3089f27ab0f8453ecc5227677252` |
| Release binary SHA-256 | `d1f8152bb72a0bca10d8b947bbb1128b77d45a52c07a05eb476f0e067846a53b` |
| Preferred host ports | CDP 49335, noVNC 16191, VNC 15911; configure selects distinct free ports. |
| Browser service capability | `SYS_NICE`, for renderer-priority changes in the assertion-enabled build. |

## Recording contract

A paired-complete state contains `dom.json`, `dom_full.txt`, `dom_model.json`,
`dom_model.txt` and `screenshot.png`. DOM-arm states also contain filtered
`agent_browser_actions.txt`. The [recording guide](recordings.md) is the artifact
schema and export reference.

| Capture property | Contract |
| --- | --- |
| Policy | `paired-capture/v2`, including `document-readiness/v1`. |
| Acquisition order | Readiness, raw structured DOM, screenshot, DOM-arm references, then stored DOM projections and bulk writes. Operational traces remain durable during capture. |
| Raw DOM budgets | 7,000 nodes and 200,000 requested text characters by default. The aggregate text threshold can mark overflow rather than make every projection an exact slice. |
| Browser text fields | Direct text up to 240 characters, subtree text up to 500 and selected attribute values up to 160, subject to browser selection and truncation rules. |
| Full text projection | `dom_full.txt` renders the captured viewport-scoped snapshot, with a default 1,200-character display cap per field. It is not an unbounded whole-page dump and is not the actor observation. |
| Screenshot identity | The actor image is the saved PNG, verified against viewport dimensions. |
| Empty export | A valid observation with the marker in model text and raw statistics retained; a captured screenshot plus the empty DOM export is paired-complete. |
| Private readiness metadata | Target/frame/loader identity, MIME type, readiness state and wait duration. None becomes actor context or feedback. |
| Missing capture | A failed phase remains distinct from an empty export and makes paired evidence incomplete. A usable active observation can continue after a passive failure. |
| Instability | Navigation, content and paint activity are recorded without automatic recapture. Global absence of activity remains unknown where coverage is incomplete. |

Mutation monitoring covers known frame contexts and discovered open shadow roots.
Closed roots and unreported remote frames remain unobserved. Passive artifacts
and their errors never enter actor prompts, memory, progress, stall checks or
rejection feedback. Missing or unverified URL metadata is explicit.

Actor input preflight estimates the UTF-8 byte length of text and structural
fields, excluding base64 image bytes, plus 1,100 tokens per image. It is a
conservative estimate, not measured token usage. Successful model metadata is
cached for that client; 1,048,576 input tokens is the configured fallback.

| Input preflight condition | Behaviour |
| --- | --- |
| Local estimate at most 50% of the model limit | Skip `countTokens`. |
| Local estimate above 50% | Request exact counting with the same transient transport retry policy. |
| Counting remains unavailable | Use the local estimate and record `local_fallback`. |
| Confirmed or estimated size above 95% | End technically with class `actor_input_limit`, without generation or truncation. |

For the fallback limit, the count trigger is above 524,288 tokens and the safe
limit is 996,147 tokens. Metadata/count requests consume neither actor model
turns nor generation tokens. Their attempts and failures remain recorded.

The ledger is written before execution with one row per `(task, arm, trial)` and
records ordering, bindings and outcomes. Resume retains completed final attempts
and reconciles interrupted work. Freshness and comparison overrides are defined
in the [recording guide](recordings.md) and
[evaluation protocol](evaluation-protocol.md); `--allow-nonfresh` records an
explicit inclusion policy rather than changing provenance.

## Completion and metrics

Primary completion uses the run's screenshots plus model DOM text, shared action
records, frozen criteria, final answer and technical status. The optional
`actor_native` grade uses the actor's evidence format; it is not a replay of the
exact actor prompt. Exact-final-answer controls support an offline answer check.
The [evaluation protocol](evaluation-protocol.md) defines scoring, denominators,
metric fields and the separation between technical outcomes, actor claims and
independent completion.

| Accounting rule | Contract |
| --- | --- |
| Model turn | A received actor response, including rejected proposals, parsing failures and termination. |
| Failed transport attempt | Separate from turns; retains duration/status and reported usage, with missing usage unknown. |
| Tokens per turn | Actor input/output are reported separately over received responses with known respective usage. Cached input and thinking are subsets. |
| Stall advisory | Exact duplicate activation, two-action cycle or recent-stall matches are private, advisory-only and symmetric. They neither reject nor stop a run. The first match contributes one count. |
| Costs | Actor, prior technical attempts and each judge stream stay separate; incomplete usage does not establish zero spend. |

## Browser recovery

Timed-out read-only observations and CDP internal errors use a liveness probe of
at most three seconds. A live target permits one reattachment and retry of that
observation. Actions are never replayed; uncertain delivery is technical failure.
Known target destruction or transport closure is checked before and after actor
responses and before accepting a terminal answer. Received responses and usage
remain recorded.

Browser/renderer crashes, CDP stalls, capture failures, exhausted reference
snapshots, recorder errors, exhausted transient actor transport retries and input
preflight technical errors can receive one fresh attempt. The final attempt
supplies success, turns and tokens; prior technical-attempt costs remain separate.
A second technical failure is not counted as an actor failure. Website blocks,
actor failure, turn caps and provider auth/quota/billing outcomes do not trigger
this technical rerun.

Actor timeouts, connection errors and temporary HTTP 429/500/502/503/504 allow two
further transport attempts with 2/8-second backoffs and up to 0.5 seconds of
jitter. Auth, quota, billing and other 4xx errors are not retried. Browser capture
components unregister during session disposal; crash evidence and rerun policy
remain shared between arms.

## Task catalog and provenance

The catalog [data/tasks.jsonl](../data/tasks.jsonl) contains `task_01` through
`task_40`, ten at each difficulty. Its SHA-256 is
`1b21a93282a438f638b70dabc427b6d6cda48b196af7ab46425b8241785cbf67`.
The [dataset README](../data/README.md) is the schema, constraints and difficulty
reference. Workload guidance does not change the shared turn cap or determine
success.

The pilot uses `task_26` (easy), `task_02` (medium), `task_19` (hard) and `task_25`
(complex), both arms with one trial each. The full collection accepts any positive
trial count per arm. Catalog and rubric hashes bind the schedule; run manifests
retain the catalog hash, or `null` for a manual task without a catalog.

Expiry metadata is committed in `internal/task_validity.json`. Scheduling refuses
an expired task unless `--allow-expired` is explicitly set; the deadline, check
and override remain recorded. Task scope and deliverables belong in the
instruction and stopping condition, while the six constraints are shared access,
browser and read-only policies.

## Scope

Tasks target public-web research and extraction. Full accessible labels, hidden
or collapsed descendants, `aria-label`/`aria-labelledby` and image alt text are
real DOM-format content that need not be painted in the viewport. Labels can
originate inside, near or outside the viewport while describing an intersecting
control. Viewport bounding boxes do not prove absence of clipping or occlusion.
Screenshots retain visible canvas, image, CSS, frame and shadow content that can
be absent from the DOM projection.

Visible-text extraction for scrolled inline-rich content covers `<p>` only.
Other inline-rich blocks can retain a first-500-character prefix and omit visible
lines after scrolling. Sequential capture does not prove simultaneous content;
instability records describe the acquisition interval. Results therefore include
targeting and action behaviour as well as observation interpretation.

## Verifiers and within-run audit

Every finalized actor trial receives paired completion, both auxiliary verifiers
and the audit when their required inputs and judgments are available. Failed
actors with usable evidence remain auditable. All stages use the same frozen
weighted rubric; native side-effect penalties stay separate from frozen-criterion
full-score checks.

Each native verifier receives every available state in its own format, preserving
state IDs and full action history across gaps. Navigation-flagged states remain
in both verifiers. Directional audit decisions use only same-ID states with
complete paired capture and no navigation during acquisition. Empty DOM exports
remain eligible. A screenshot-only required fact can establish DOM loss; shared
absence does not establish directional loss. The audit never pairs two actor
recordings. Each task/trial has four arm/direction values, with coverage retained.

The native input adaptation preserves top-five selection, scoring, penalties and
citation rules; contiguous states follow the same loader contract. Task-only
validity uses the run's frozen UTC date. DOM citation checks diagnose state IDs
and extractable exact quotes without changing scores or audit feedback. The
native JSON contract is `native-rubric-output-contract/v3`.

Completion, inventory and adjudication reject missing/mismatched returned model
IDs and incomplete responses. Native model mismatches are recorded as diagnostics.
Earned points must be finite nonboolean values in `0..max_points`; exhausted
numeric repair or authentication leaves an ungraded native result with null
scores and retained receipts. An unavailable native verifier blocks its audit.
An ungraded or missing audit has no pooled loss rate, not zero loss.
The [evaluation protocol](evaluation-protocol.md) defines response acceptance,
auxiliary scores, directional loss and coverage.

## Judge delivery

| Stage | Model | Transport | Thinking/reasoning | Output cap |
| --- | --- | --- | --- | --- |
| Actor, both arms | `gemini-3.8-flash` | Normal | MEDIUM | 10,000 |
| Rubric generation and dependency check | `gpt-5.2` | Normal | Unset | Unset |
| Native screenshot and DOM verifiers, all stages | `gemini-3.5-flash-lite` | Batch | Medium | Unset |
| Native Pro comparison profile, all stages | `gemini-3.1-pro-preview` | Batch | Medium | Unset |
| Paired completion and optional actor-native grade | `gpt-6.1-sol` | Batch | Medium | 10,000 |
| Audit inventory | `gemini-3.1-pro-preview` | Batch | Unset | Unset |
| Audit adjudication | `gpt-6.1-sol` | Batch | Unset | Unset |

`JUDGE_TRANSPORT` selects `batch` by default or `normal` for judging. Actors,
actor preflight and rubric preparation stay normal. Native stages retain the
115,000-token input guard. Judge image requests specify high detail. Temperature
is omitted in the listed configurations.

Batch items contain the normal request body inside the provider envelope. Ready
calls share provider/model/stage rounds; stage dependencies remain ordered.
Submitted IDs and raw responses are durable. Repeating the same command polls
saved jobs and replays answered items through the same validators. Pending work
is not an ungraded judgment or task failure. Cancellation forbids late imports;
uncertain submission acknowledgement blocks resubmission until its actual job ID
is reconciled. See the [Batch controls](runbook.md#controls-and-outputs).

Common completion has no native-result input and is shared across profiles.
Each profile runs its own native verifiers and audit on each identical actor
recording. The comparison reports criterion agreement, both audits' screenshot-
only subsets and their union/intersection, directional-loss differences,
usage/cost and judgment-quality counts. These subsets are judge-defined, not
human accuracy labels. Profiles are isolated in output and primary aggregation.

Completion allows one request per grading attempt; inventory and adjudication
allow three validation attempts each. Native repairs and endpoint retries retain
their receipts. Audit receipts identify `automated-evidence-audit/v8` and
`paired-capture-eligible-state-adjudication/v8`. Authentication refresh consumes
the endpoint attempt budget. Effective settings bind profile, transport and
output policy for resume and comparison. [Cost assumptions](cost-estimate.md)
are planning estimates, not measured results.
