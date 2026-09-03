# Microsoft Universal Verifier / DOM Evidence Research Handoff

This workspace investigates whether browser-agent trajectories can be verified more cheaply and reliably with structured DOM evidence than with Microsoft Universal Verifier's screenshot path. The work evolved from reproducing the official screenshot verifier, through Stagehand, raw DOM-diff, compact DOM-summary, grep/read, full DOM-model, and compressed-DOM variants, into the current frozen-rubric comparison and offline evidence-item audit; the executable flow is diagrammed in [PROJECT_HANDOFF.mmd](PROJECT_HANDOFF.mmd).

The strongest operational result is a complete 106-trajectory screenshot-verifier execution, while the strongest modality result is still mixed: DOM often exposes text that screenshots miss, but it usually costs more, its criterion scores vary, and corrected final-screenshot alignment reversed an apparent DOM advantage on the manually audited NASA task. The root is not a Git repository, the historical `ms-paper-execution/` worktree is heavily dirty, several aggregate reports are stale, and no available artifact is an independent gold-label benchmark of verifier correctness.

## Primary handoff table

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| `ms-paper-execution/` | Historical 34 GB workbench: official baseline, recorders, early verifier variants, raw outputs, and curated reports | Nested Git worktree on branch `benchmarks`, HEAD `10f85ec7`; many tracked deletions/modifications and many untracked datasets/results | `git -C ms-paper-execution status --short`; read the curated summaries rather than assuming the worktree is clean | Treat as read-only history unless a change is explicitly intended |
| `benchmarks/` | First self-contained screenshot-versus-refined-`dom_diffN.txt` benchmark | 12 paired task folders; four run directories across tasks 2–4; all 113 offline tests pass | Run its three test suites separately; inspect `results/*/*/comparison.{json,md}` | Use when reproducing the refined DOM-diff arm, not the current full-DOM arm |
| `benchmarks-2/` | Full ordered `dom_model0..N.txt` experiment against a frozen Microsoft screenshot baseline | 25 paired task folders and 52 `comparison.json` files, including reruns; all 90 offline tests pass | Run its three suites separately; validate a task with `python -m scripts.run_comparison --task taskN` | Historical full-DOM baseline; do not assume its aggregates reflect current screenshot alignment |
| `benchmarks-token-reduction/` | Deterministic, extractive compressed-DOM experiment targeting 30–40% fewer scoring tokens | Three paid pilots exist despite README wording that says no paid run was part of implementation; all three missed the target; all 93 offline tests pass | Inspect `results/task{1,2,3}/pilot-20260831-1/comparison.md` and `evidence_audit.json` | Add an uncompressed-D control before attributing score loss to compression |
| `evidence-error-experiment/` | Current comparison code plus offline, human-confirmed atomic evidence audit | 25 paired tasks, 55 comparisons, four finalized item-audit artifacts, and current Sept. 3 prompt/alignment reruns; all 114 offline tests pass | Follow its consolidated `README.md`; inspect manifests, run logs, and `evidence_error_audit/` | This is the best starting point for new work |
| `browser-agent-tasks-hf-update/` | Hugging Face-style source dataset of public, reversible browser tasks | 60 JSONL tasks; own Git repo at `ed01640`; `data.md` is untracked; no trajectories/evaluations in this directory | `wc -l tasks.jsonl`; `git -C browser-agent-tasks-hf-update status --short` | Use as future task input, not as evidence of verifier performance |
| Frozen rubric control | Prevents the two arms from scoring different criteria or denominators | Phase A stores one rubric plus a separate generation receipt; Phase B requires the exact same isolated rubric path and reports zero generation calls | Compare rubric SHA-256, task ID, ordered criteria, maxima, denominator, and `rubric_generation_calls` | Never regenerate one rubric independently per modality |
| Screenshot state alignment | Microsoft consumes one screenshot per action, but paired datasets store initial state plus one state after each action | Current evidence runner rewrites the isolated screenshot answer to `screenshot1..N`, preserving the final state without editing source data | Inspect `scripts/run_comparison.py::prepare_isolated_inputs` and the isolated `*_answer.json` | Rerun earlier headline comparisons under this correction |
| Evidence accuracy | A score gap alone was repeatedly mistaken for an evidence advantage | Finalized audits decompose criteria into atomic items and require manual source citations plus verifier excerpts | Run `audit_evidence_items`, manually complete the review, then run `finalize_evidence_items` | Expand blinded/manual audits before making accuracy claims |
| Token efficiency | DOM representation can be compact, but call count, retries, repeated context, and downstream prompts dominate total usage | Old S3 wins exist, but the 20-task full-DOM report shows +25.43% tokens and all three compressed-D pilots miss the 30–40% target | Use provider `prompt + completion`; reasoning is already inside completion | Optimize validation/call topology and measure against three arms: screenshot, uncompressed DOM, compressed DOM |

## Scope and evidence labels

This handoff covers artifacts currently present under `/data/isha/msexecute` as of 2026-09-03. “Verified” below means directly checked in source, manifests, logs, result JSON, or tests. “Inference” means a conclusion supported by those artifacts but not independently adjudicated. “Unverified” means a rerun, human label, or missing artifact is still required.

Do not read or copy any `.env` file. Each experiment has a local ignored credential file; reports and manifests must remain secret-free. Paid runs send task instructions, action logs, screenshots or DOM states, and final answers to OpenAI and therefore require explicit authorization.

## Workspace structure and folder functions

```text
/data/isha/msexecute/
├── .agents/                         # empty local agent metadata directory
├── .codex/                          # empty local Codex metadata directory
├── .git/                            # empty directory; root is NOT a Git repository
├── .pytest_cache/, .ruff_cache/     # disposable local tool caches
├── PROJECT_HANDOFF.md               # this onboarding and experiment history
├── PROJECT_HANDOFF.mmd              # standalone Mermaid architecture/flow diagram
├── ms-paper-execution/              # historical Git worktree and 34 GB artifact store
├── benchmarks/                      # standalone screenshot vs refined DOM-diff
├── benchmarks-2/                    # screenshot vs complete DOM-model states
├── benchmarks-token-reduction/      # screenshot vs compressed DOM-model pilots
├── evidence-error-experiment/       # current verifier and manual audit workspace
└── browser-agent-tasks-hf-update/   # 60 future browser task definitions
```

### `ms-paper-execution/`: historical workbench

```text
ms-paper-execution/
├── README.md                         # official Day 0/Day 1 result entry points
├── pipeline.md                       # S0–S3 token-efficient summary design/status
├── *_PIPELINE.md, *_PLAN.md          # Stagehand, raw DOM, summary, and grep/read designs
├── config/                           # experiment registry and fixed configs
├── endpoint_configs/                 # secret-free endpoint declarations
├── environment/                      # Python, package, system, and source-commit receipts
├── scripts/
│   ├── inspect_dataset.py            # inspect CUAVerifierBench without labels
│   ├── materialize_trajectory.py     # convert one dataset row to verifier layout
│   ├── validate_materialized.py      # parse actions/images and reject leaked annotations
│   ├── judge_preflight*.py           # validate endpoint/model access
│   ├── run_verifier_openai.py        # launch official verifier with local OpenAI config
│   ├── finalize_*.py                 # freeze curated reports/manifests
│   ├── day2/E0_full_uv/              # prepare, plan, batch, assess, and freeze all 106 tasks
│   └── verifier_comparison/           # canonical rubric, instrumentation, and metric helpers
├── data/, data-*/, dom-data/         # raw/materialized and modality-specific trajectories
├── outputs/                          # heavy raw run workspaces and traces
├── results/                          # curated summaries and per-task comparison reports
├── repo/                             # local upstream Fara and DOM-verifier checkouts
├── vendor/                           # vendored verifier source
└── skills/                           # local dataset/comparison workflow instructions
```

This directory contains both implemented code and design-only documents. A pipeline document is not proof that its proposed repository or command was completed; a run is considered completed only when a score/result, metrics, logs, and a comparison or manifest are present.

### Shared layout of the four standalone experiment directories

`benchmarks/`, `benchmarks-2/`, `benchmarks-token-reduction/`, and `evidence-error-experiment/` intentionally duplicate verifier packages. This avoids hidden imports from the historical workbench and permits package-tree hashes, but fixes must be ported deliberately rather than assumed to propagate.

```text
<experiment>/
├── README.md / RUNBOOK.md            # setup, contracts, commands, interpretation limits
├── .env.example, .env                # template and ignored local secret
├── requirements*.txt, .venv/         # experiment-local Python environment
├── config/endpoints/openai/canonical # gpt-5.2 and o4-mini declarations
├── data/
│   ├── data-new-screenshot/taskN/    # task, actions, answer, screenshot0..N
│   └── data-new-*/taskN/             # matching dom_diff1..N or dom_model0..N
├── rubrics/                          # canonical rubrics and Phase-A usage receipts
├── manifests/                        # expected package and prompt hashes
├── microsoft_verifier/               # frozen screenshot package
├── dom_diff_text/, dom_model/, or
│   compressed_dom_model/             # experimental evidence package
├── scripts/                           # Phase A/B validation, execution, normalization
├── tests/ or scripts/tests/           # control-plane regression tests
└── results/taskN/<run-id>/            # isolated inputs, raw results, metrics, logs, reports
```

### Current `evidence-error-experiment/` file/function map

| Path | Function |
|---|---|
| `scripts/common.py` | Canonical task/rubric parsing and hashing, endpoint validation, safe path checks, `.env` loading, token/call aggregation, JSON writing |
| `scripts/validate_inputs.py` | Parses each modality's action log, enforces semantic action equivalence, requires contiguous `N+1` state inventories, checks allowed files and rubric sidecars |
| `scripts/generate_frozen_rubric.py` | Phase A: offline preflight, one Microsoft rubric-generation workflow, or validated rubric import; writes rubric and separate generation metrics only with `--execute` |
| `scripts/package_manifests.py` | Fails closed when either verifier package differs from its expected file list/tree hash |
| `scripts/run_comparison.py` | Phase B control plane: dry preflight by default; with `--execute`, copies inputs, fixes isolated screenshot references to post-action states, runs Microsoft first and DOM second, then normalizes and compares |
| `scripts/normalize_results.py` | Converts raw package-specific result shapes into one metrics schema with rubric, criterion, call, retry, and token receipts |
| `scripts/compare_results.py` | Validates normalized receipts and emits `comparison.json` plus `comparison.md` |
| `scripts/audit_existing_outputs.py` | Legacy criterion-level extraction of the two completed verifier outputs into a review workspace |
| `scripts/build_audit_review.py`, `summarize_error_metrics.py` | Applies manually confirmed criterion decisions and computes directional recovery metrics |
| `scripts/audit_evidence_items.py` | Preferred audit entry point; creates an atomic evidence-item review template from an existing run |
| `scripts/evidence_item_audit.py` | Validates screenshot locators, DOM line citations, and verbatim verifier excerpts; classifies and summarizes atomic items |
| `scripts/finalize_evidence_items.py` | Writes the finalized evidence-item audit, metrics JSON, and Markdown report after manual review |
| `microsoft_verifier/src/microsoft_verifier/runner.py` | Loads one screenshot task and frozen rubric, initializes model clients, runs the rubric agent, computes process/outcome success, and writes raw `result.json` |
| `microsoft_verifier/.../adapter.py`, `trajectory.py`, `models.py` | Convert task/action/screenshot files into the Microsoft `DataPoint` and typed result structures |
| `microsoft_verifier/.../rubric_agent.py`, `prompts.py` | The shared Universal Verifier waterfall and its scoring, outcome, failure, penalty, and validity prompts |
| `dom_model/src/dom_model/state_parser.py` | Discovers and parses ordered complete DOM states, metadata, section ranges, hashes, refs, warnings, and provenance |
| `dom_model/.../alignment.py` | Checks `dom_model0..N` against initial and after-action URLs; produces explicit warnings instead of inventing coverage |
| `dom_model/.../context_packing.py` | Enforces the per-state character budget while preserving complete source lines and recording omissions |
| `dom_model/.../evidence_backend.py`, `dom_model_agent.py` | Renders DOM evidence, scores relevance, selects top-K states, requests per-state/batched analysis, validates citations/status, and records `evidence_audit.json` |
| `dom_model/.../grounding.py` | Requires explicit DOM support, treats missing evidence as unknown, and validates `DOM_MODEL_STATE_INDEX` citations and status values |
| `dom_model/.../prompts.py`, `rubric_agent.py` | Current Sept. 3 terminology layer rewrites screenshot wording to DOM wording; the external `dom_model_evidence` field is mapped back to the inherited internal `screenshot_evidence` schema |
| `dom_model/.../instrumentation.py`, `package_manifest.py` | Count logical calls/API attempts/tokens and expose the package source identity |

### Variant-specific code

| Variant | Additional function |
|---|---|
| `benchmarks/dom_diff_text/compaction.py` | Parses semantic diffs, removes exact duplicates/contained fragments/geometry-only noise, keeps provenance, and builds compact trajectory ledgers |
| `benchmarks/dom_diff_text/retrieval.py` | Builds criterion queries, scores records, performs safe adaptive packing, and records why whole evidence units were omitted |
| Historical grep/read verifier | Gives the model allowlisted `grep_evidence` and `read_file` tools over immutable raw diff files and records model/tool traces |
| `benchmarks-token-reduction/compressed_dom_model/evidence_units.py` | Converts full DOM states to deterministic, stable evidence units suitable for deduplication and criterion matching |
| `.../token_budget.py`, `token_counting.py` | Derives a DOM budget from screenshot provider usage and estimates model-facing evidence size |
| `.../omission_audit.py` | Records every retained/omitted unit and plausible criterion-level loss mechanism |
| `scripts/run_experiment.py` | Runs screenshot arm S first, writes `token_budget_plan.json`, then runs compressed DOM arm D |

## Current end-to-end execution flow

### 1. Record and prepare a paired trajectory

A recorder or adapter starts from one logical browser task and produces the same task ID, instruction, semantic action sequence, and final answer for both modalities. For `N` actions, the current paired contract is:

```text
screenshot task: screenshot0.png ... screenshotN.png
DOM task:        dom_model0.txt ... dom_modelN.txt

state 0 = initial browser state
state i = state after action i
state N = final browser state
```

The screenshot and DOM action logs may encode targets differently—coordinates versus semantic refs—but `validate_inputs.py` must normalize them to the same action names, values, URLs, scroll direction/amount, keys, and semantic target text. A source state that is absent, off-screen, hidden, truncated, canvas-only, or cross-origin remains unproven.

### 2. Phase A: freeze one rubric

1. `scripts.generate_frozen_rubric` validates the paired task before constructing clients.
2. With no `--execute`, it prints a no-write/no-call receipt.
3. With authorized execution, Microsoft's rubric workflow runs once, or an existing rubric plus generation receipt is imported.
4. It writes `rubrics/taskN.json`, `rubrics/taskN_generation_metrics.json`, and matching provenance sidecars in both experiment-owned task copies.
5. Rubric-generation calls/tokens remain separate from all scoring totals.

### 3. Phase B dry preflight

`python -m scripts.run_comparison --task taskN` performs all of the following without creating a result directory or a model client:

1. Constrains task, rubric, and output paths to the experiment root.
2. Validates task ID, instruction, initial URL, final answer, semantic actions, and `N+1` evidence alignment.
3. Validates both rubric sidecars, canonical hash, ordered criteria, maximum points, denominator, and Phase-A receipt.
4. Verifies package manifests and exact endpoint model IDs.
5. Builds both child commands and fails unless judge model, action judge, threshold, top-K, minimum relevance threshold, vote count, success rule, rubric path, and `--redo-eval` match.
6. Prints the planned manifest. Any failure stops before paid calls.

### 4. Authorized Phase B execution

With `--execute`, the control plane loads the local API key, creates a unique result directory, and copies the two tasks plus frozen controls under `_inputs/`. In the isolated screenshot copy only, it rewrites the answer's screenshot list from all `N+1` stored states to `screenshot1..N`; this matches Microsoft's one-frame-per-action loader and includes the final state without modifying source data.

Microsoft then runs first in a subprocess whose `PYTHONPATH` contains only `microsoft_verifier/src`. DOM runs second with only `dom_model/src`. If Microsoft fails, DOM is not run; this prevents a partial comparison from looking complete.

### 5. Shared Universal Verifier waterfall

Both package runners execute the same inherited scoring topology. The intentional difference is evidence loading and representation.

1. Load and validate the precomputed rubric; `--redo-eval` clears old scores but preserves criteria.
2. Use `o4-mini` to score the action history without screenshots/DOM evidence.
3. Load evidence: Microsoft uses `N` post-action screenshots; current DOM uses all `N+1` complete states.
4. Use `gpt-5.2` to score every evidence state for every rubric criterion.
5. Group by criterion, select up to top five, and retain Microsoft's effective minimum relevance threshold of `0` in both arms.
6. Analyze selected evidence, requiring structured outputs, source indices, DOM evidence statuses, and grounding citations.
7. Resolve conditional criteria when present.
8. Run the rubric reality check.
9. Rescore criteria with evidence and evaluate any unpenalized unsolicited side effects; choose the median score when multiple vote instances are configured (currently one).
10. Independently judge final outcome success.
11. Identify the first point of failure and tool/action-schema problems.
12. Classify task ambiguity/validity once with trajectory evidence and once from the task alone.
13. Wrap process and outcome results, attach all intermediate steps, calls, attempts, retries, and provider token usage, then write `result.json` (plus DOM `evidence_audit.json`).

### 6. Normalize and compare

The parent process normalizes both outputs, writes each `run_metrics.json`, and then emits `comparison.json`, `comparison.md`, and a completed `run_manifest.json`. The top-level binary score defaults to outcome success, so a process score above 0.8 can still have final score `0` when the answer is judged unsuccessful.

### 7. Offline evidence-item audit

The audit is downstream and one-way: it cannot change verifier scores.

1. Extract the frozen rubric, source inventories, relevance/top-K output, evidence analysis, final criterion scores, and justifications from an existing completed run.
2. A human decomposes each criterion into concrete values/states and independently marks whether each source representation actually contains the evidence.
3. Screenshot claims cite a filename, visible text, and visual locator. DOM claims cite a filename, exact `mN:Lx-Ly` range, and quote.
4. The review records whether each verifier caught the evidence and includes a verbatim excerpt from that verifier's existing output.
5. Finalization validates citations/excerpts and computes catch rates only on confirmed common evidence. Missing-source cases are excluded from directional recovery denominators; zero denominators are `N/A`, not 0%.

## Approaches tried, evaluation method, and outcome

“Succeeded” in this table distinguishes operational success from proof of better accuracy or lower cost.

| Date / approach | What changed | How it was evaluated | Outcome and why |
|---|---|---|---|
| 2026-07-21, official screenshot smoke test | Materialized one frozen CUAVerifierBench trajectory and ran Microsoft's released verifier | Parser, 10 actions, 11 screenshots, official score JSON, cache check | Operational success: process 10/11 (0.9091), process pass, but outcome false. Initial Azure path failed because configs were placeholders and authentication was unavailable; OpenAI-only execution succeeded. Not a benchmark reproduction. |
| 2026-07-22, provisional `gpt-4o`/`gpt-4o` E0 | Restored missing Playwright in a repo-local venv and ran three preflight tasks | Three fresh scores followed by a no-call cached rerun | Operationally succeeded but was superseded because it violated the intended distinct `gpt-5.2`/`o4-mini` model roles. The first setup failed only from import order and missing dependency; no judge call was made in those failures. |
| 2026-07-22, canonical 106-task Microsoft E0 | Used exact `gpt-5.2` multimodal and `o4-mini` action/rubric roles, threshold 0.8, top five, one vote, outcome success | 3-task preflight, cache check, 10-task batch, 93-task remainder, manifests/logs/score audit | Strong operational success: 106/106 inputs valid and scored, 0 terminal failures, 370 rubric criteria present. SDK transport and schema retries recovered. This proves execution coverage, not accuracy or human agreement. |
| Late July–Aug., recorder evolution | Manual/custom tasks, agent-browser, Stagehand ARIA/page state, CDP/refined DOM-diff, `getModelDOM`, viewport-only and include-offscreen variants | Artifact-contract checks, action/state alignment, per-task capture reviews, Git history | Mixed. Each iteration addressed missing final states, oversized artifacts, weak grounding, or missing text. Off-screen/hidden content can improve recall but weakens comparability to visible screenshots; viewport-only can miss needed text. Treat recorder choice as part of the evidence representation. |
| 2026-07-31–08-04, Stagehand/ARIA verifier | Replaced pixels with normalized ARIA/page-state evidence and semantic actions | Qatar task, frozen semantic rubric, fresh rerun | Promising cost but not clean parity: fresh Stagehand used 134,279 tokens vs screenshot 196,034 and agreed on outcome false, but excluded a conditional point (5-point vs 6-point denominator), used a different action schema, and its prior outcome call had returned true on identical evidence. Demonstrated policy and judge variance. |
| 2026-07-31–08-04, raw DOM-diff-only | Fed action-aligned semantic diff frames into a UV-style verifier | CarMax and Amazon-style per-task comparisons, frozen rubrics, token/call receipts | Mixed/failed as a general solution. CarMax remained 6/10 because Honda evidence existed in a raw diff but was not selected for the criterion. Raw evidence was large and retrieval-sensitive; Amazon showed different denominators because screenshot reality checking added a runtime penalty. |
| 2026-08-05–08-18, compact DOM-diff-summary S0–S3 | Deterministic compaction, batched relevance, packed analysis, and evidence caps | Frozen-rubric screenshot comparisons; cap sweeps at 5k/10k/15k/20k; call/token instrumentation | Real wins on long tasks: task10 preserved 7/10 while saving 55.64% tokens; task11 preserved 3/12 while saving 47.72%. Not stable: task4 S3 used 9.17% more than screenshots, and uncapped task4 used 119.83% more. Tight caps sometimes saved tokens but omitted exact/numeric records and reduced scores. |
| 2026-08-12 NASA summary fallback | Grounding validator rejected unassigned frame citations and eventually used “analysis unavailable” fallback | Compared action-only and evidence-adjusted scores and inspected validation attempts | Safety validator succeeded at rejecting bad citations, but downstream unknown-evidence handling over-restored credit: DOM rose from 9/15 action-only to 14/15 despite unavailable analysis. This is not a valid modality win and exposed a scoring/fallback interaction. |
| 2026-08-20, raw grep/read tools | Let the judge search immutable raw diff files with allowlisted grep/read calls instead of receiving the corpus directly | Task4 and task6 against saved screenshot and summary baselines; complete model/tool traces | Failed token goal. Task4 used 190,598 tokens (+126.5% vs screenshots); task6 used 256,535 (+147.79%). Only ~9.6% of unique raw evidence was retrieved, but repeated reads, tool receipts, multi-turn context, and one validation retry dominated cost. |
| 2026-08-22, standalone refined DOM-diff benchmark | Isolated both packages and introduced frozen-rubric/control-plane checks | Tasks 2–4 plus offline tests | Isolation succeeded. DOM token deltas were -17.92%, -49.72%, and +79.64%; results therefore did not show consistent cost reduction. Action-only and final allocations sometimes varied despite fixed controls. |
| 2026-08-27–09-01, full DOM-model states | Replaced diffs/summaries with complete ordered `dom_model0..N.txt` states, explicit grounding, source manifests, and paired runner | Existing 20-task selected report, per-task comparisons, task1/task2 repeated ten times, package tests | Broad execution succeeded; research claim did not. The selected 20-task report shows 17/20 outcome agreement but only 67/116 exact criterion agreement and +25.43% DOM tokens. Because Microsoft is not gold, “15% error” is only baseline disagreement. |
| 2026-09-01, parity correction | Changed DOM minimum relevance threshold from 3 to Microsoft's effective 0 and reran selected tasks | Command-parity preflight and new run manifests; 10 repeats each for tasks1 and 2 | Control correction succeeded, but variability remained. Task1 screenshot mean/range was 68.0% / 60–73.3%; DOM 68.7% / 53.3–80%. Task2 screenshot stayed 50%; DOM averaged 64.25% / 60–70%. Every repeat outcome was false. This demonstrates stochastic score spread, not objective DOM superiority. |
| 2026-08-31, compressed full-DOM pilots | Deterministic evidence units, omission receipts, and budgets derived from screenshot usage | Three S-vs-compressed-D pilots | Target failed on all three: DOM changes were -5.50%, -17.23%, and +11.35%; aggregate saving was only about 5.62%. Scores also moved. Without an uncompressed-D arm, compression cannot be isolated from modality and judge variance. |
| 2026-09-02–03, atomic evidence-item audits | Evaluated source availability separately from verifier detection | Manual citations and verbatim verifier excerpts for task1, task2, and two task4 runs | Best current accuracy method, but tiny coverage. On common evidence, screenshot/DOM catch rates were 6/6 vs 5/6 (task1), 5/5 vs 4/5 (task2), and after corrected alignment 7/7 vs 6/7 (task4). No completed audit currently establishes a screenshot miss that DOM recovered; absent-source items are not comparable. |
| 2026-09-03, screenshot final-state correction | Rewrote only the isolated Microsoft answer to use `screenshot1..N`, so the final state reaches the unchanged verifier | Re-ran and manually audited NASA task4 | Alignment fix succeeded. The old audit reported screenshot 2/7 vs DOM 7/7; the corrected audit reported screenshot 7/7 vs DOM 6/7. The score still varied (screenshot 9/18, DOM 15/18), proving that score difference alone was misleading. Earlier screenshot-vs-DOM aggregates need corrected reruns. |
| 2026-09-03, DOM terminology/schema rewrite | Replaced screenshot/pixel language in DOM prompts, requested `dom_model_evidence`, then added an adapter back to the inherited internal field | NASA task4 prompt rerun, Chess task6 rerun, run logs, tests | First rerun exposed an integration failure: task4 made 28 calls and used +58.75% tokens because the old validator still required `screenshot_evidence` and status strings were malformed. The adapter was then added; task6 completed with equal 6/14 scores, but DOM still cost +12.41% and had status-format retries. Current code passes tests, but a positive-evidence audited rerun is still needed. |
| 2026-09-02, browser task expansion | Added public, reversible task definitions 31–60 to the existing set | JSONL structure/history only | Dataset-authoring success: 60 tasks exist. No recorded trajectories or verifier results in that repository, so benchmark suitability and modality balance remain unverified. |

## How evaluations were controlled

The intended comparison fixes task, semantic actions, final answer, frozen rubric, models, thresholds, top-K, vote count, success rule, retry behavior, and result accounting. Package manifests and isolated `PYTHONPATH` values reduce accidental cross-imports. Rubric generation is Phase A; its usage is never added to Phase B scoring. Provider total tokens are `prompt_tokens + completion_tokens`; reasoning tokens are a subset of completion and must not be added again.

Several factors still overlap and cannot be summed or attributed independently:

- modality and capture coverage (visible pixels versus structured/possibly off-screen DOM);
- screenshot `N` post-action frames versus DOM `N+1` complete states;
- action target representation (coordinates versus semantic refs/text);
- stochastic action-only, evidence, and outcome judgments;
- response-validation retries and fallback calls;
- runtime conditional/penalty criteria that can change the effective denominator;
- compression versus modality in the two-arm token experiment;
- incomplete trajectories versus verifier evidence misses.

## Current verified test state

Tests were run on 2026-09-03 with bytecode/cache writes disabled and each same-named package suite isolated as required.

| Project | Control-plane tests | Microsoft tests | Experimental verifier tests | Total |
|---|---:|---:|---:|---:|
| `benchmarks/` | 14 | 21 | 78 | 113 passed |
| `benchmarks-2/` | 23 | 21 | 46 | 90 passed |
| `benchmarks-token-reduction/` | 23 | 21 | 49 | 93 passed |
| `evidence-error-experiment/` | 45 | 21 | 48 | 114 passed |

Do not collect both verifier packages' tests in one pytest process: they intentionally contain modules with identical names such as `test_agent.py`, which produces import-file-mismatch collection errors. Run the three suites separately exactly as documented in each README/runbook.

## Known stale, missing, and conflicting artifacts

- `benchmarks-2/COMPARISON_REPORT.md` describes 20 selected tasks (1–16 and 34–37), but this copy has no `results/task34`–`task37` directories. Its linked score files cannot be locally reverified.
- That report also excludes current task17–25 results and all later Sept. 3 alignment/prompt changes.
- `evidence-error-experiment/results/task1_to_task25_comparison.md` was written when only tasks1–10 were complete and still marks tasks11–25 pending even though result directories now exist.
- The same older task1–10 report documents a DOM relevance threshold of 3; current parity requires 0.
- `benchmarks-token-reduction/README.md` says no paid execution was part of implementation, yet three complete pilot result trees are present. Trust the result manifests for current state.
- Task25's criterion audit has 0/5 classified criteria and is pending; task3 has only a review template. Do not include either in confirmed evidence-error rates.
- The root `.git/` is empty. Version-control history is available only in nested repositories, chiefly `ms-paper-execution/` and `browser-agent-tasks-hf-update/`.

## Directly verified facts, inferences, and unverified boundaries

### Directly verified

- Folder sizes, file layouts, result counts, Git identities, source diffs, run manifests/logs, comparison JSON/Markdown, manual audit artifacts, and the four separated offline test totals above.
- The canonical 106-task baseline completed with 106 successful score artifacts and no terminal input or infrastructure failures.
- Current code sets `gpt-5.2`, `o4-mini`, rubric threshold 0.8, top five evidence items, minimum relevance 0, one vote, outcome success, and `--redo-eval` in both arms.
- The screenshot mapping correction and DOM terminology/adapter changes are present in current `evidence-error-experiment` source.

### Inferences supported by artifacts

- DOM's dominant cost problem is call topology/validation and repeated context rather than raw evidence size alone: small-state tasks can still make many more calls, and grep/read retrieved little unique text while costing much more.
- Several apparent DOM accuracy wins were actually capture/alignment wins. The corrected NASA audit is the strongest example.
- Exact output-schema instructions and validators are a high-leverage reliability target because malformed status/citation responses caused repeated full model calls.

### Unverified boundaries

- Objective accuracy, false-credit rate, precision/recall, and calibration for either verifier: Microsoft is a baseline, not ground truth.
- The current DOM terminology/response adapter on a sufficiently broad set of positive and negative evidence items.
- A corrected aggregate after applying post-action screenshot mapping to every task.
- Compression's causal effect: it needs screenshot, uncompressed DOM, and compressed DOM arms under identical repeated conditions.
- Generality of the current four finalized manual audits and the 60 newly authored browser tasks.

## Recommended starting sequence for the next person

1. Start in `evidence-error-experiment/` and read its consolidated `README.md`, this handoff, and the standalone Mermaid file.
2. Run the three offline suites separately. A combined pytest command is invalid for these duplicate package layouts.
3. Run a dry Phase-B preflight on a small existing task; confirm it performs no writes and that manifest parity reports minimum relevance `0` and post-action screenshot staging.
4. Do not aggregate old scores yet. Select a small representative set with text-positive, visual-only, blocker, and missing-evidence criteria; rerun each modality three times under the current package hash.
5. Complete blinded atomic evidence-item audits for those runs before interpreting score gaps.
6. Only then regenerate a current aggregate report with an explicit run-selection manifest and no broken result links.
7. For token work, add an uncompressed-D control and focus first on preventing schema-validation repeats and resending identical evidence, not on more aggressive omission.

## Conclusion

The project has a solid reproducible control plane and a successful official baseline, but it has not yet shown that DOM verification is both more accurate and cheaper. The dominant remaining risks are stale aggregates, screenshot/DOM capture asymmetry, stochastic scoring, and expensive validation retries; the next concrete check is a corrected three-arm, repeated, human-audited subset under the current Sept. 3 source manifests.
