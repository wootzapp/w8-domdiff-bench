# Day 2 Learning Log — Universal Verifier

## Scope

Execute only E0: Microsoft's released Universal Verifier over all 106 frozen
`fara7b_om2w_browserbase` trajectories. No human-label benchmarking, later
ablation work is authorized in this run.

## 2026-07-22 — E0 authorized and protocol reread

- Reread the then-active Day 2 execution protocol. That sequential protocol was
  later superseded and removed after the user cancelled follow-on experiments.
- Fixed the local execution configuration to OpenAI `gpt-4o` for both judge
  roles, rubric threshold 0.8, top-5 screenshots per criterion, one vote,
  outcome-based top-level success, and one worker process.
- Recorded the paper deviation: the paper protocol describes GPT-5.2 plus
  o4-mini; this run uses GPT-4o plus GPT-4o while retaining the released
  Universal Verifier architecture and prompts.
- Confirmed the ignored `.env` contains an `OPENAI_API_KEY` entry without
  printing or copying the key.
- Confirmed no verifier process was left running from the interrupted turn.

## 2026-07-22 — E0 environment snapshot and first setup failure

- Captured the required environment snapshot. The checked-out Fara commit is
  `9f14b6e34094fe469a54a821e81e013a0739520d`, matching the frozen E0 config.
- The first local materialization command stopped before reading the dataset
  because `prepare_corpus.py` imported `cuav_data` before its bootstrap module
  added the repository `scripts/` directory to `sys.path`.
- This was a local script import-order failure, not an OpenAI, Azure, dataset,
  or verifier failure. No judge request was sent and no score was generated.
- Corrected only the import order; the E0 data allow-list and fixed verifier
  configuration were not changed.

## 2026-07-22 — Full corpus materialization and validation

- Materialized all 106 frozen `fara7b_om2w_browserbase` rows using only the
  explicit E0 allow-list. Human labels and stored verifier outputs were not
  copied into the task definitions, action logs, final answers, or manifest.
- Validated all 106 inputs with the pinned `Trajectory.from_folder()` parser,
  JSON parsing, screenshot decoding and contiguous ordering, task-ID lookup,
  and forbidden-field scanning. Result: 106 valid; 0 invalid, missing, or
  parse-failed inputs.
- Selected exactly three operational preflight tasks using screenshot-count
  order only: short `Bbb--60cbbbd5` (4 screenshots), medium
  `Cookpad--0632e496` (19), and long `Arxiv--71f8de18` (101).
- Partitioned the other 103 valid tasks into a fresh 10-task batch and a
  93-task remainder. Together with the preflight, all 106 inputs are accounted
  for exactly once in the fresh execution plan.
- No score file existed before the E0 judge preflight.

## 2026-07-22 — External data-egress approval gate

- Attempted to launch the validated three-task preflight through the official
  verifier wrapper, but the workspace security reviewer blocked process launch
  before any OpenAI request was made.
- The reason is that verifier execution sends benchmark task instructions,
  action-log content, and screenshots to OpenAI for judging. The API key stays
  local in the child-process environment, but the benchmark inputs themselves
  are external API payloads.
- No task content, screenshot, API key, or model request left the workspace;
  no score was generated. This is an authorization gate, not an Azure,
  OpenAI-authentication, rate-limit, model, or Universal Verifier failure.
- E0 is paused before its three-task preflight pending explicit user approval
  of this data transfer. The 10-task and 93-task stages have not started.

## 2026-07-22 — Three-task preflight failed before judge initialization

- After explicit user approval of the external judge payload, launched only the
  three-task preflight. The official entry point exited after 0.16 seconds with
  return code 1 and produced no report row or score file.
- First root cause: the current `/usr/bin/python` environment does not contain
  the `playwright` Python package. Importing `FARA_ACTION_DEFINITIONS` loads
  `fara_agent.py`, which imports `playwright.async_api`, causing
  `ModuleNotFoundError: No module named 'playwright'`.
- The Day 1 frozen environment manifest recorded `playwright==1.51.0`, but the
  new Day 2 environment snapshot does not contain it. This is environment
  drift between sessions, not a trajectory, Azure, OpenAI authentication,
  rate-limit, or verifier-judgment failure.
- Zero OpenAI model calls completed, zero `mmrubric_*.json` files were created,
  no Azure marker appeared in the log, and no API-key-like marker appeared.
- In accordance with the E0 preflight stop rule, the cache check, fresh
  10-task batch, and 93-task remainder were not started. Proposed remediation
  after user review: restore the pinned Day 1 runtime dependency
  `playwright==1.51.0`, recheck verifier imports, then rerun the same three-task
  preflight without changing its inputs or judge configuration.

## 2026-07-22 — Approved dependency repair

- The first `python -m pip install playwright==1.51.0` attempt was correctly
  rejected by the operating system's PEP 668 protection for the externally
  managed system interpreter. No system package was changed and the unsafe
  `--break-system-packages` override was not used.
- Created the repository-local, ignored `.venv` with access to the existing
  system packages and installed only `playwright==1.51.0` plus its required
  Python dependencies there. Browser binaries were not needed or downloaded.
- Re-ran the official entry point's import path and confirmed Playwright,
  Fara action definitions, and the trajectory parser import successfully.
- Refreshed the required E0 environment snapshot using the actual `.venv`
  interpreter. The pinned Fara commit and all judge parameters remain unchanged.

## 2026-07-22 — Three-task preflight and cache validation passed

- Re-ran exactly the same short, medium, and long preflight tasks with the
  approved OpenAI `gpt-4o` + `gpt-4o` configuration and one process.
- The official verifier completed in 184.51 seconds with return code 0. All
  three report rows have operational status `ok`, and each trajectory contains
  a readable `scores/mmrubric_0.8-5-3.json` file.
- The log confirms successful text/image OpenAI requests and contains no Azure
  authentication marker or API-key-like marker.
- Re-ran the same three inputs without `--redo-eval`. It completed in 1.11
  seconds with three `cached` statuses, valid score paths, and no HTTP request
  in the cache-check log. This validates the official resume behavior without
  additional judge calls.
- No benchmark statistics, human-label joins, or process/outcome comparisons
  were performed. The fresh 10-task batch and 93-task remainder remain unrun.
- Reproducibility issue discovered: the first failed preflight log/status were
  accidentally overwritten by the successful retry. Reconstructed copies are
  explicitly labeled as reconstructed from the captured traceback and status;
  the wrapper now archives any existing log, status, or report before a retry.

## 2026-07-22 — User-authorized canonical model correction

- The user explicitly replaced the provisional `gpt-4o` + `gpt-4o` pairing
  with two distinct roles: `gpt-5.2` for the main multimodal judge and
  `o4-mini` for the action/rubric judge. Model substitution and same-model use
  are now prohibited for E0.
- Current official OpenAI model documentation confirms that the exact model
  IDs `gpt-5.2` and `o4-mini` exist and support Chat Completions, image input,
  and structured output, matching the released verifier's API requirements.
- Created a dedicated credential-free endpoint directory containing exactly
  those two OpenAI model configurations. Exact model filtering in the released
  `GracefulRetryClient` prevents either role from silently selecting another
  endpoint configuration.
- The earlier three `gpt-4o` score files and their preflight artifacts are
  superseded and must not be reused as canonical E0 results. They are archived
  before the same short/medium/long preflight is rerun.
- The fresh 10-task batch remains unstarted pending validation of the corrected
  canonical-model preflight.

## 2026-07-22 — Canonical two-model preflight passed

- Archived the earlier `gpt-4o` + `gpt-4o` preflight reports, logs, and three
  score files under `outputs/day2/E0_full_uv/superseded/` so none could be
  mistaken for, or cached into, the canonical run.
- Refreshed the environment snapshot and confirmed the active credential-free
  endpoint directory contains exactly two distinct models: `gpt-5.2` and
  `o4-mini`. The active preflight began with zero score files.
- Ran the official verifier with the exact flags `--judge-model gpt-5.2` and
  `--o4mini-model o4-mini`. It completed in 288.87 seconds with return code 0;
  all three short/medium/long report rows have status `ok`, and three fresh
  `mmrubric_0.8-5-3.json` files exist.
- Operational log validation found 167 `gpt-5.2` create calls and 9 `o4-mini`
  create calls. It found zero `gpt-4o` client/call markers, confirming there was
  no same-model substitution or fallback.
- The canonical cache check completed in 0.83 seconds with three `cached`
  statuses, valid score paths, and zero model or HTTP calls.
- Both fresh and cache logs contain zero Azure-authentication or secret-like
  markers. No benchmark statistics or human-label comparison was performed.
- The fresh 10-task batch has not started. E0 is paused for user review of this
  corrected canonical-model checkpoint.

## 2026-07-22 — Fresh 10-task external-data approval gate

- After the user approved moving forward, attempted to launch the fresh
  canonical 10-task batch. The workspace security reviewer blocked process
  creation because these are ten new external API payloads containing task
  instructions, action-log content, and screenshots.
- No additional task data left the workspace, no OpenAI call was made, and the
  active canonical score count remains three. This is an authorization gate,
  not a verifier, model, authentication, rate-limit, or trajectory failure.
- The batch is paused pending explicit user acknowledgement of the ten-task
  data transfer to OpenAI. The 93-task remainder remains unstarted.

## 2026-07-22 — Fresh 10-task data transfer explicitly approved

- The user explicitly approved sending the ten new benchmark trajectories to
  OpenAI after being informed that the payloads include task instructions,
  action-log content, and screenshots.

## 2026-07-22 — Fresh canonical 10-task batch passed

- Ran the exact planned set of ten fresh trajectories through the official
  verifier with `--judge-model gpt-5.2`, `--o4mini-model o4-mini`, and one
  process. The command completed with return code 0 in 1,753.11 seconds.
- All 10 report rows have status `ok`; task IDs are unique and exactly equal to
  the frozen 10-task execution plan, and every row points to a score file.
- Operational model-role validation found 540 `gpt-5.2` create calls and 30
  `o4-mini` create calls, with zero `gpt-4o` calls or client instantiations.
  The log contains 570 successful HTTP 200 responses and no non-200 response.
- The OpenAI SDK logged 19 transparent transport retries. One request remained
  pending for approximately the SDK's 600-second read-timeout window, then
  automatically retried and succeeded. No terminal timeout, rate limit,
  connection error, server error, or task-level verifier error remained.
- Three tasks collectively triggered four points-of-failure schema-validation
  retries because `gpt-5.2` initially returned mixed step-number formats. The
  released verifier's built-in retry logic corrected all four without prompt,
  configuration, or code changes, and all affected tasks finished `ok`.
- The batch logs contain no Azure-authentication or secret-like markers. The
  canonical corpus now has 13 fresh score files: 3 preflight plus 10 batch.
- The 93-task remainder has not started. E0 is paused for user review of the
  10-task operational checkpoint.

## 2026-07-22 — Canonical 93-task remainder authorized

- The user reviewed the successful 10-task checkpoint and authorized the
  remaining 93 fresh trajectories under the unchanged canonical configuration.
- The user additionally required preservation of both process and outcome
  results for every trajectory. E0 will retain per-task `rubric_score`,
  `rubric_is_success`, `outcome_success`, and outcome-based top-level success
  in the frozen prediction corpus, without performing cross-task analysis or
  joining human annotations.

## 2026-07-22 — 93-task external-data approval gate

- The first remainder launch was blocked before process creation by the
  workspace security reviewer. The larger run would transmit 93 new tasks'
  instructions, action-log content, and screenshots to OpenAI.
- No remainder data left the workspace, no new API call occurred, and the
  canonical score count remains 13. This is an external-data authorization
  gate, not an experiment or infrastructure failure.
- The 93-task run is paused pending explicit acknowledgement of that complete
  transfer.

## 2026-07-22 — Complete 93-task transfer explicitly approved

- After reviewing the exact judge roles, the user explicitly approved sending
  all remaining 93 trajectories to OpenAI for `gpt-5.2` multimodal judging and
  `o4-mini` action/rubric judging.

## 2026-07-22 — Remainder progress checkpoint: 10/93

- The official remainder run loaded exactly 93 fresh trajectories and the two
  canonical endpoint configurations. The first 10 remainder tasks completed
  with status `ok`, bringing the canonical score corpus to 23 files.
- One task required two built-in points-of-failure schema retries for mixed
  step-number formats; it recovered and finished `ok`. No terminal verifier or
  infrastructure failure has occurred at this checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 20/93

- The first 20 remainder trajectories have all completed with status `ok`,
  bringing the canonical corpus to 33 fresh score files when combined with the
  preflight and 10-task batch.
- No new error marker appeared between the 10-task and 20-task checkpoints;
  there is still no terminal verifier or infrastructure failure.

## 2026-07-22 — Remainder progress checkpoint: 25/93

- The first 25 remainder trajectories have all completed with status `ok`.
  Combined with the earlier stages, 38 canonical score files now exist.
- No new error or infrastructure marker appeared since the 20-task checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 30/93

- The first 30 remainder trajectories have all completed with status `ok`, for
  43 fresh canonical score files across all E0 stages.
- The log still contains only the two earlier, resolved schema-validation
  retries and no terminal or infrastructure failure.

## 2026-07-22 — Remainder progress checkpoint: 35/93

- The first 35 remainder trajectories have all completed with status `ok`,
  bringing the complete canonical score count to 48.
- Error state is unchanged: two resolved schema retries and no terminal or
  infrastructure failure.

## 2026-07-22 — Remainder progress checkpoint: 40/93

- The first 40 remainder trajectories have all completed with status `ok`, for
  53 fresh canonical score files overall.
- No new error or infrastructure marker appeared since the prior checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 45/93

- The first 45 remainder trajectories have all completed with status `ok`, for
  58 fresh canonical score files overall.
- Task 46 began with an SDK-level transport retry; the process remained active.
  No terminal failure existed at this checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 50/93

- The first 50 remainder trajectories have all completed with status `ok`, for
  63 fresh canonical score files overall.
- The SDK transport retry noted at the prior checkpoint recovered; no terminal
  verifier or infrastructure failure occurred.

## 2026-07-22 — Remainder progress checkpoint: 55/93

- The first 55 remainder trajectories have all completed with status `ok`, for
  68 fresh canonical score files overall.
- No new schema, terminal, or infrastructure error appeared since the prior
  checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 60/93

- The first 60 remainder trajectories have all completed with status `ok`, for
  73 fresh canonical score files overall.
- One additional task required a single mixed step-range schema retry. It
  recovered automatically; no terminal or infrastructure failure occurred.

## 2026-07-22 — Remainder progress checkpoint: 65/93

- The first 65 remainder trajectories have all completed with status `ok`, for
  78 fresh canonical score files overall.
- No new error or infrastructure marker appeared since the prior checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 70/93

- The first 70 remainder trajectories have all completed with status `ok`, for
  83 fresh canonical score files overall.
- Error state remains three resolved schema retries and no terminal or
  infrastructure failure.

## 2026-07-22 — Remainder progress checkpoint: 75/93

- The first 75 remainder trajectories have all completed with status `ok`, for
  88 fresh canonical score files overall.
- No new error or infrastructure marker appeared since the prior checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 80/93

- The first 80 remainder trajectories have all completed with status `ok`, for
  93 fresh canonical score files overall.
- No new error or infrastructure marker appeared since the prior checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 85/93

- The first 85 remainder trajectories have all completed with status `ok`, for
  98 fresh canonical score files overall.
- Task 86 triggered one built-in mixed step-range schema retry. The run remained
  active with no infrastructure failure at this checkpoint.

## 2026-07-22 — Remainder progress checkpoint: 90/93

- The first 90 remainder trajectories have all completed with status `ok`, for
  103 fresh canonical score files overall. Three remainder tasks remain.
- The task-86 schema retry recovered. The error state is four resolved schema
  retries and no terminal or infrastructure failure.

## 2026-07-22 — E0 full canonical corpus completed and frozen

- The 93-task remainder completed with return code 0 in 9,606.90 seconds. All
  93 planned, unique task IDs were reported with status `ok`, and every report
  row points to a readable canonical score file.
- Remainder operational logs contain 3,790 `gpt-5.2` create calls and 280
  `o4-mini` create calls, with zero `gpt-4o` calls. All 4,070 logged HTTP
  responses were 200; no non-200 response was logged.
- The SDK emitted 184 transparent transport-retry lines during the remainder.
  All resolved within the official run. Four points-of-failure schema retries
  also resolved. There were zero terminal infrastructure, verifier, or input
  failures and no trajectory-level retry batch was necessary.
- Frozen artifacts account for all 106 dataset rows: 106 fresh report rows,
  106 full prediction rows, 106 successful-run rows, and 106 copied raw score
  files. There are zero unresolved, infrastructure, or input failures.
- Preserved both process and outcome data for every task in
  `process_outcome_results.jsonl`: each of 106 unique rows has non-null
  `rubric_score`, `rubric_is_success`, `outcome_success`,
  `top_level_success`, and `success_criterion=outcome` fields.
- No aggregate process/outcome comparison, human-label join, or benchmark
  accuracy calculation was performed.

## 2026-07-22 — Criterion-level rubric-score audit

- Reopened all 106 frozen raw score files and verified that each contains a
  non-empty `rubric_items` list with `criterion`, `description`, `max_points`,
  and `earned_points` for every item.
- All 106 trajectories passed this audit with no missing or incomplete rubric.
  The corpus contains 370 criterion-level rubric items, ranging from 1 to 9
  criteria per trajectory.

## 2026-07-22 — Final-vs-action-only criterion field clarification

- While extracting five example tasks, confirmed that the released rubric
  schema stores the action-only baseline in each item's `earned_points` and the
  final multimodal criterion score in `post_image_earned_points`.
- Reports of final per-criterion scoring must therefore use
  `post_image_earned_points`. For all five extracted examples, those final item
  scores sum exactly to the official `rubric_total_earned_points`; the
  action-only item scores do not necessarily do so.

## 2026-07-23 - Scope cleanup

- User cancelled all later ablation and benchmark-reporting work.
- Retained Day 1 smoke-test artifacts and Day 2 E0 full-trajectory artifacts.
- Removed future-phase configs and the obsolete Day 2 sequential plan, and
  updated registry/state/docs to make E0 the final active experiment scope.
