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
| Page observation | Formatted `dom_model.txt` and viewport-filtered interactive reference text. Numeric ChromiumRL IDs are masked in actor text. | The saved `screenshot.png`, sent once per call at `detail: high`; no extracted DOM, accessibility text, selectors or references. |
| Targeting | Current agent-browser `e` references for reference-targeted actions. | CSS-pixel coordinates through raw CDP input events. |
| Ref-click scrolling | The action CLI can scroll a referenced target into view while resolving and clicking it. Supplied references pass viewport bounding-box filtering. | Coordinate clicks operate at the selected viewport point without reference-based scroll-into-view. |
| Progress source | DOM text, URL and interactive reference changes. | Screenshot change only. |
| Document language | Supplied from snapshot metadata, or `unknown` when unavailable. | Not supplied as a page-observation field. |

Both actors receive the current URL as plain text, the task instruction, turn
budget, viewport dimensions, actor-maintained memory and recent action/rejection
outcomes. Navigation, keyboard input and non-reference browser primitives use
the shared action driver.

## Shared controls

| Control | Configuration |
| --- | --- |
| Actor model and endpoint | `OPENAI_MODEL` is the sole actor-model configuration and must identify `gpt-6.1-terra`; the same value is used across arms. A non-Terra returned ID stops the run. `OPENAI_BASE_URL` selects the endpoint. |
| Model-turn budget | 200 by default and at most 200; lower positive budgets must match across compared runs. |
| Maximum actor output | Exactly 10,000 tokens, including reasoning. |
| Task memory | At most 8,000 characters. |
| Reasoning effort | Explicitly `medium`. |
| Temperature | Unset in both arms. |
| Viewport | 1365 × 768 CSS pixels by default. |
| Settling interval | One second by default. |
| Browser locale | English (`en-US`, `en-US,en;q=0.9`). |
| Browser state | Fresh profile per scheduled attempt, with build/environment provenance. |
| Action contract | One strict JSON action per response; common schema and vocabulary. |
| Intervention | No human intervention or automatic language redirects. |

Comparison checks shared model settings, task contracts, budgets, schema,
source/capture controls, browser build/environment, profile freshness and grading
controls. Browser images should be selected by immutable identity; recorded image
IDs establish the build used. Matching settings do not freeze live-site content.

## Recording contract

A complete state contains `dom.json`, `dom_full.txt`, `dom_model.json`,
`dom_model.txt` and `screenshot.png`. DOM actor states also contain the filtered
`agent_browser_actions.txt` reference snapshot. `dom_full.txt` renders the
captured viewport-scoped DOM; it is not an unbounded whole-page dump. Snapshot
limits default to 7,000 nodes and 200,000 text characters.

States record artifact paths/hashes, target and session identity, capture order,
phase start/end times, interval URLs and navigation status. The screenshot sent
to the actor is the saved file. Passive evidence and capture errors do not enter
actor prompts, memory, progress, stall checks or rejection feedback. A passive
failure marks paired evidence incomplete while allowing a usable active
observation to continue. Missing URL metadata is marked explicitly.

The schedule is written before a batch starts and contains one row per
`(task, arm, trial)`. It records task/configuration identity, trial count, arm
order, intended recording path and technical/grading outcomes. Resume retains
completed attempts, including failures, and reconciles orphaned started rows.
See the [recording guide](recordings.md) for the full artifact schema.

## Completion and metrics

The primary `paired` grading policy uses the run's screenshots and saved model
DOM text, action records, final answer and technical status. A frozen task rubric
is reused across arms and trials. `completion.json` records criterion verdicts,
evidence policy, rubric/prompt hashes, configured and returned judge models and
judge usage. The judge must be explicitly set to `gpt-5.6-sol`, with 10,000 maximum output tokens and `medium` reasoning. It never falls back to the actor model.

The optional `actor_native` policy uses the actor's observation type and writes
`completion_actor_native.json`. It is a modality policy rather than a replay of
the exact actor prompt. Exact-final-answer controls provide an offline answer check. Task rubrics are generated once from instruction and start URL, reviewed, then frozen for every arm and trial.

A model turn is one actual actor API call, including rejected proposals, parsing
failures and termination. Action attempts and captured states are counted
separately. Provider input/output usage is summed per run; cached-input and
reasoning tokens are subsets, not extra totals. Unavailable provider usage stays
marked missing. Actor and judge calls/tokens are accounted for separately.

Technical outcome, actor-reported success and independent completion remain
separate. Ungraded and uncertain outcomes are not confirmed failures. Aggregation
uses the full schedule, reports unmatched arms and grading coverage, and provides
all-attempt costs, definitive-grade success rates, successful-pair efficiency and
pass@k bounds. See the [evaluation protocol](evaluation-protocol.md).

## Task catalog and provenance

The default catalog is [data/tasks.jsonl](../data/tasks.jsonl), containing
`task_01` through `task_25`. Each row has eight fields: `task_id`, `task_name`,
`category`, `instruction`, `start_url`, `stopping_condition`, `constraints`,
and `difficulty`. Difficulty is a declared
`medium`, `hard` or `complex` label;
it does not determine success or change the 200-turn cap.

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
schedule and run manifest record the check date and any override. Historical search
windows retain their specified dates; rolling runtime values have no fixed expiry.

## Scope

Tasks target public-web research and extraction. Viewport limits, accessible
labels, rendering, dynamic content and live-site changes affect the available
evidence. Captures are sequential, so navigation flags and timestamps describe
the interval rather than prove simultaneous content. Benchmark results include
targeting and action behavior as well as page interpretation.

Retain source URLs, timestamps, task hashes and run provenance with exported
observations.

## Verifiers and within-run audit

Every actor trial receives common completion grading, both auxiliary verifiers
and the audit. Auxiliary stages use `gpt-5.2` for rubric/evidence/scoring work and
`gpt-5.6-terra` for action-only scoring and validity. Their original generation
limits remain unset; the 115,000-token input guard remains active. Inventory uses
`gpt-5.6-sol`; adjudication uses Google `gemini-3.1-pro-preview` at high media
resolution. Task-only validity uses a recorded UTC date frozen from the run.

Staged screenshot and DOM inputs always originate from one recording hash.
Each verifier sees every state available in its own format, including states
flagged for navigation. Missing-format states remain explicit gaps with their
original IDs; full action history and observed URLs are preserved. This declared
input-contract adaptation leaves top-K, scoring, penalties and citation rules
unchanged, and contiguous runs preserve original loader behavior.

Directional-loss decisions use the same state IDs for both formats, requiring a
complete paired capture and no navigation during capture. Unverified URLs remain explicitly unavailable in both shared inputs.
Record format gaps, navigation states, eligible IDs and coverage for each run.
No eligible states means an ungraded audit with a reason, never zero loss. Failed
actors with usable evidence remain auditable. Missing auxiliary results block the
full audit rather than being replaced with invented analyses.

Outcome grading interprets dates from the task and recorded evidence. Unresolved
years are disclosed in the reasoning rather than inferred from a collection year.

Audit receipts use `automated-evidence-audit/v6` with prompt version
`paired-capture-eligible-state-adjudication/v6`, identifying the shared-URL and
eligible-state input contract.

Screenshot loss and DOM loss are computed separately inside each actor run.
Report all four values per task/trial side by side, retaining actor identity.
Never pair observations across actor runs. Shared absence and temporal
inconsistency do not automatically establish directional loss.

Actor tokens per model turn include rejected, failed and termination calls.
Report input/output averages separately; cached input and reasoning are subsets.
Missing usage uses explicitly labelled known-usage denominators. Publish run
mean/median/distributions by arm and category. Common success, auxiliary process
scores, threshold success, outcome success and frozen full-score checks stay
separate; runtime penalties and judge fallbacks have their own fields. All judge
cost streams remain separate from actor costs.
