---
name: run-universal-verifier-comparison
description: Run a controlled Microsoft Universal Verifier comparison for exactly one logical task at a time, using one task-specific frozen rubric through screenshot, full-DOM, and DOM-diff-only pipelines. Use when Codex must generate and store the same GPT-5.2 rubric in that task paired dataset folders, score the task with GPT-5.2 and o4-mini, preserve identical benchmark controls, measure exact LLM calls and token usage, store score and run artifacts, or explain criterion-level differences across the three evidence modes.
---

# Run Universal Verifier Comparison

Execute one reproducible benchmark for exactly one logical task in four paid phases: rubric freezing, screenshot scoring, full-DOM scoring, and DOM-diff-only scoring. Accept one screenshot task folder and its matching DOM task folder only; reject batches or multiple task IDs. Keep every phase auditable and never modify verifier source code during a run.

Read [references/runner-and-artifact-contract.md](references/runner-and-artifact-contract.md) before generating a rubric or calling a judge. Use the bundled scripts for preflight and final consistency checks.

## Non-negotiable controls

1. Use `gpt-5.2` as the main rubric/evidence judge and `o4-mini` as the action/rubric and task-validity judge. Never substitute a model or use one model for both roles.
2. Use OpenAI endpoint configs under `endpoint_configs/openai/canonical/` and `OPENAI_API_KEY`. Never use Azure, Azure CLI, managed identity, or Azure endpoint configs.
3. Generate one rubric for the single requested task only. Run its dependency check, clear all scores, freeze it, store identical task-local copies in that task paired dataset folders, and reuse it in all three scoring modes.
4. Use the canonical WebTailBench TSV for all three runners. Do not rely on the screenshot OM2W loader to carry a frozen rubric.
5. Hold task instruction, initial URL, action history, final answer, rubric, models, thresholds, majority-vote count, and success criterion constant. Change only browser-state evidence.
6. Run each mode in a fresh isolated output directory. Do not write scores into `data-screenshot/` or `dom-data/`.
7. Do not reuse a stale score cache. Use a new output path or `redo_eval` and record the cache identity.
8. Count logical verifier calls and underlying API attempts separately. Record retries rather than hiding them.
9. Treat reasoning tokens as a subset of completion tokens. Never add them again to total tokens.
10. During rubric freezing, the only permitted dataset mutation is creating or updating `task_data_with_canonical_rubric.json` in the two modality folders belonging to the same logical task. Do not modify any other dataset file.
11. Do not stage, commit, push, delete, or restructure datasets unless the user separately requests it.

## Phase 0: Resolve and audit inputs

Resolve the project root containing:

```text
data-screenshot/taskN/
dom-data/taskN/
repo/fara/
repo/fara-dom-verifier/
endpoint_configs/openai/canonical/
benchmarks/rubrics/
outputs/
results/verifier_comparisons/
```

Confirm both paired task folders contain parseable `task_data.json`, `final_answer.json`, and `web_surfer.log`. Require exactly one task row in each file, require the same single task ID in both modalities, and reject multi-task or batch input. Confirm:

- task IDs and instructions match;
- `web_surfer.log` hashes match exactly;
- final-answer text and abort status match;
- screenshot data contains ordered screenshots;
- DOM data contains zero screenshots;
- action count equals complete full-DOM step count;
- every action has `before/chromiumrl_dom.json`, `after/chromiumrl_dom.json`, `dom_diff.json`, before/after `page_state.json`, and `verifier_action.json`;
- every action has one `dom_diff.json` for the diff-only ablation.

Run:

```bash
python skills/run-universal-verifier-comparison/scripts/validate_inputs.py \
  --screenshot-task data-screenshot/taskN \
  --dom-task dom-data/taskN \
  --rubric-json benchmarks/rubrics/<name>_canonical_rubric.json \
  --rubric-tsv benchmarks/rubrics/<name>_canonical_task_data.tsv
```

When the rubric does not exist yet, omit the last two arguments for the dataset-only preflight. Stop before paid calls on any mismatch.

Check that `.env` contains a non-empty `OPENAI_API_KEY` without printing its value. Obtain explicit authorization before transmitting task, action, answer, screenshot, DOM, or DOM-diff evidence to OpenAI.

## Phase 1: Generate and freeze the rubric

Use the full-DOM verifier's `MMRubricAgent._generate_rubric()` with GPT-5.2. This method performs:

1. rubric generation;
2. schema validation;
3. rubric dependency checking and any required reformulation.

Require an unscored rubric shaped as `{"items": [...]}`. Every item must contain `criterion`, `description`, `max_points`, empty `justification`, and empty `earned_points`. Require total `max_points == 10`.

Save:

```text
benchmarks/rubrics/<name>_canonical_rubric.json
benchmarks/rubrics/<name>_canonical_task_data.tsv
benchmarks/rubrics/<name>_rubric_generation_metrics.json
```

The TSV must contain one row with columns:

```text
id  task_summary  init_url  benchmark  precomputed_rubric
```

Serialize `precomputed_rubric` as compact JSON. Add the identical rubric to `data-screenshot/taskN/task_data_with_canonical_rubric.json` and `dom-data/taskN/task_data_with_canonical_rubric.json`. These are two modality copies for one logical task, not two independently generated rubrics. Pass the canonical TSV to every scoring runner.

Compute the normalized rubric SHA-256 from compact, key-sorted JSON. Confirm the canonical JSON, TSV, screenshot task copy, and DOM task copy normalize to exactly the same object and hash. Report the rubric criteria, denominator, task-local paths, adapter paths, generation calls, and generation tokens before scoring.

## Phase 2: Run the screenshot verifier

Use Microsoft's released runner:

```text
repo/fara/webeval/scripts/verify_trajectories.py
```

Create an isolated trajectory under:

```text
outputs/screenshot_verify/<task>_frozen_rubric/traj/<task-id>/
```

Copy only required root metadata and link or copy the screenshot files without modifying the source dataset. Use the frozen TSV with `task_data_format=webtailbench` and fixed settings:

```text
judge_model=gpt-5.2
o4mini_model=o4-mini
rubric_threshold=0.8
max_images_per_criterion=5
mm_keypoint_score_threshold=3
majority_vote_instances=1
success_criterion=outcome
```

Instrument clients before `_run_one()`:

- wrap each `GracefulRetryClient.create()` to count logical calls by model;
- wrap every underlying endpoint `create()` to count API attempts;
- read each endpoint's `total_usage()` after the run;
- preserve prompt, completion, reasoning, and prompt-plus-completion totals.

Load `scripts/instrumentation.py` from the skill and call `instrument_agent(agent)` after `_pool_init()` and before `_run_one()`. Call the returned object's `snapshot(agent)` after the run and store that payload without manual arithmetic.

Write `run.log`, `instrumentation.json`, `run_metrics.json`, and the verifier score JSON. Record source screenshot count and action-aligned screenshots actually loaded.

## Phase 3: Run the full-DOM verifier

Use:

```text
repo/fara-dom-verifier/webeval/scripts/verify_trajectories.py
```

Use `evidence_mode=dom` and schema `chromiumrl-dom-step/v1`. Keep the same frozen TSV and control settings. Also fix:

```text
dom_frame_char_budget=16000
dom_context_char_budget=48000
dom_top_k=None
```

Create:

```text
outputs/dom_verify/<task>_frozen_rubric/traj/<task-id>/
```

Expose the root log/answer plus action-aligned step evidence. Confirm capture coverage reports one complete DOM frame per action and zero screenshot frames. Apply the same call/token instrumentation and artifact contract as the screenshot run.

## Phase 4: Run the DOM-diff-only verifier

Use the isolated ablation runner:

```text
repo/fara-dom-verifier/webeval/scripts/verify_trajectories_dom_diff.py
```

Create a clean bundle under:

```text
outputs/dom_diff_verify/<task>_frozen_rubric/traj/<task-id>/
```

Expose only:

```text
web_surfer.log
final_answer.json
step_001/dom_diff.json
step_002/dom_diff.json
...
```

The frozen TSV remains external runner input. Do not expose screenshots, before/after DOM, page states, or verifier actions to this bundle. Run `preflight_trajectory()` before initializing judge clients. Require `N actions == N diffs`, contiguous ordinals, and `declared_paths == {dom_diff_path}`.

Use the same scoring controls plus:

```text
request_timeout_seconds=180
max_api_retries=2
```

Apply the same instrumentation and write a distinct `dom_diff` score artifact.

## Phase 5: Record every result immediately

After each mode, update exactly one report for the current logical task:

```text
results/verifier_comparisons/<task-name>.md
```

Store screenshot, full-DOM, and DOM-diff results together in this same task report. Do not create separate Markdown reports per mode and do not combine different tasks in one report unless the user explicitly requests it. Do not wait until all modes finish. For each mode record:

- action-only and final evidence score for every criterion;
- earned points, maximum points, normalized process score, and threshold verdict;
- outcome success and concise reasoning;
- first failure step and taxonomy summary;
- ambiguity and invalidity flags/codes;
- action and evidence-frame counts;
- duration;
- calls by model and pipeline stage;
- logical calls, API attempts, retries, and rubric-generation calls;
- prompt, completion, reasoning, and total tokens by model and combined;
- exact score, metrics, raw-instrumentation, log, and isolated-trajectory paths.

Store normalized metrics using the schema in the reference file. Validate each JSON immediately.

## Phase 6: Compare without hiding attribution changes

Run:

```bash
python skills/run-universal-verifier-comparison/scripts/compare_metrics.py \
  --screenshot outputs/screenshot_verify/<run>/run_metrics.json \
  --dom outputs/dom_verify/<run>/run_metrics.json \
  --dom-diff outputs/dom_diff_verify/<run>/run_metrics.json \
  --output /tmp/<task>_comparison.md
```

Require identical task ID, frozen-rubric hash, denominator, models, and fixed scoring controls. Compare:

- total score and outcome;
- criterion-by-criterion attribution;
- action-only versus evidence-adjusted points;
- call counts and API attempts;
- token totals and savings;
- evidence that was supported, contradicted, partial, or unknown.

Never claim modalities agree solely because totals match. A matching total with different criterion allocation is a disagreement. Note that freezing the rubric fixes criteria and denominator, not stochastic action-only judgments. When a strict evidence-only ablation is required, reuse one frozen action-only baseline across modes or explicitly report action-only variance.

## Failure and safety rules

- Fail before paid calls on missing/malformed inputs, task/rubric mismatch, broken action alignment, or wrong evidence exposure.
- Never fabricate missing evidence, scores, token usage, or call counts.
- Do not infer calls from token totals. Instrument them.
- Do not count cached results as fresh calls.
- Preserve partial artifacts for diagnosis, but label failed runs clearly and never compare them as complete.
- Keep source datasets and verifier repos unchanged. Write only to rubric, output, result, and skill-authorized paths.
- Never print or store the API key in artifacts.

## Completion response

Lead with each mode's process score and outcome. Include compact criterion, call, and token tables. Explain meaningful evidence differences and link the canonical rubric, score JSONs, metrics JSONs, and comparison report.
