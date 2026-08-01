# Universal Verifier Runner and Artifact Contract

## Contents

1. Runner map
2. Frozen rubric contract
3. Evidence isolation
4. Instrumentation contract
5. Metrics schema
6. Comparison interpretation

## Runner map

| Mode | Runner | Evidence argument |
|---|---|---|
| Screenshot | `repo/fara/webeval/scripts/verify_trajectories.py` | Released screenshot default |
| Full DOM | `repo/fara-dom-verifier/webeval/scripts/verify_trajectories.py` | `evidence_mode=dom` |
| DOM-diff only | `repo/fara-dom-verifier/webeval/scripts/verify_trajectories_dom_diff.py` | Dedicated diff-only agent |

Use one process for instrumented single-task runs. Import the runner module, load the canonical WebTailBench TSV, call `_pool_init(args, tasks)`, instrument the initialized clients, then call `_run_one(trajectory_path)`. This retains exact in-process usage counters.

Do not edit runner source to instrument one experiment. Use a temporary or bundled wrapper and store its measured output as `instrumentation.json`.

## Frozen rubric contract

Generate with `MMRubricAgent._generate_rubric(task, init_url_context)` from the full-DOM verifier. This invokes GPT-5.2 for generation and dependency checking. Preserve generation usage separately from scoring usage.

Canonical JSON:

```json
{
  "items": [
    {
      "criterion": "Criterion name",
      "description": "Evidence-aware scoring rule",
      "max_points": 4,
      "justification": "",
      "earned_points": ""
    }
  ]
}
```

Require:

- non-empty `items`;
- unique criteria;
- positive numeric `max_points`;
- total maximum of 10;
- empty scoring fields;
- dependency-check completion;
- stable normalized hash.

Canonical TSV:

```text
id\ttask_summary\tinit_url\tbenchmark\tprecomputed_rubric
taskN\tExact instruction\thttps://example.com/\tmanual_task\t{"items":[...]}
```

Always pass this TSV with `task_data_format=webtailbench`. The trajectory directory name must equal `id`.

Persist the same rubric inside both evidence representations of the one logical task:

```text
data-screenshot/taskN/task_data_with_canonical_rubric.json
dom-data/taskN/task_data_with_canonical_rubric.json
```

Generate the rubric once; never generate separate screenshot and DOM rubrics. Require the canonical JSON, TSV, and both task-local copies to share one normalized hash.

## Evidence isolation

### Screenshot

Permit:

- `web_surfer.log`;
- exactly one `*_answer.json`;
- ordered screenshot files.

### Full DOM

Permit one frame per action containing:

- `before/chromiumrl_dom.json`;
- `after/chromiumrl_dom.json`;
- `dom_diff.json`;
- before/after `page_state.json`;
- `verifier_action.json`.

Require zero screenshot frames.

### DOM-diff only

Permit:

- `web_surfer.log`;
- exactly one `*_answer.json`;
- `step_NNN/dom_diff.json` only.

Declare these omissions:

```text
screenshots
before_dom
after_dom
before_page_state
after_page_state
verifier_action
```

An absent fact in DOM-diff evidence is unknown, not false. DOM-diff can prove only explicit changes recorded in a diff.

## Instrumentation contract

Count two layers:

1. Logical call: invocation of `GracefulRetryClient.create()`.
2. API attempt: invocation of an underlying endpoint client's `create()`.

The difference is retry count. Wrap clients only after `_pool_init()` and before `_run_one()`.

Read token usage from every endpoint's cumulative `total_usage()` and sum within each model role:

```text
prompt_tokens
completion_tokens
reasoning_tokens
total_tokens = prompt_tokens + completion_tokens
```

Reasoning tokens are already included in completion tokens. Never use `prompt + completion + reasoning`.

For a frozen-rubric scoring run, `rubric_generation_calls` must be zero. DOM/full-DOM retrieval-term generation is a scoring call, not a rubric-generation call.

Save raw stdout/stderr to `run.log`. Save the direct wrapper payload to `instrumentation.json` even when the normalized metrics are also written.

## Metrics schema

Write one `run_metrics.json` per mode:

```json
{
  "task_id": "taskN",
  "evidence_mode": "screenshot|dom|dom_diff",
  "input_task": "data-screenshot/taskN",
  "isolated_trajectory": "outputs/.../traj/taskN",
  "frozen_rubric_tsv": "benchmarks/rubrics/...tsv",
  "frozen_rubric_sha256": "...",
  "judge_models": {
    "judge": "gpt-5.2",
    "action_and_validity_judge": "o4-mini"
  },
  "pipeline_settings": {
    "rubric_threshold": 0.8,
    "max_evidence_items_per_criterion": 5,
    "mm_keypoint_score_threshold": 3,
    "majority_vote_instances": 1,
    "success_criterion": "outcome"
  },
  "trajectory": {
    "actions": 0
  },
  "result": {
    "process_score": 0.0,
    "total_earned_points": 0,
    "total_max_points": 10,
    "rubric_is_success": false,
    "outcome_success": false,
    "has_failure": true,
    "first_failure_step": null,
    "is_ambiguous": false,
    "ambiguity_codes": [],
    "is_invalid": false,
    "duration_seconds": 0.0
  },
  "criteria": [
    {
      "criterion": "Criterion name",
      "action_only_points": 0,
      "final_points": 0,
      "max_points": 4
    }
  ],
  "llm_calls": {
    "gpt-5.2": 0,
    "o4-mini": 0,
    "total": 0,
    "api_attempts": 0,
    "retries": 0,
    "rubric_generation_calls": 0
  },
  "token_usage": {
    "gpt-5.2": {
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "reasoning_tokens": 0,
      "total_tokens": 0
    },
    "o4-mini": {
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "reasoning_tokens": 0,
      "total_tokens": 0
    },
    "combined": {
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "reasoning_tokens": 0,
      "total_tokens": 0
    }
  },
  "score_artifact": "outputs/.../scores/mmrubric_....json",
  "raw_instrumentation": "outputs/.../instrumentation.json",
  "run_log": "outputs/.../run.log"
}
```

Model-role key names may differ in raw runner output. Normalize them to model names in `run_metrics.json`.

## Comparison interpretation

Use four separate conclusions:

1. Process score and threshold pass.
2. Binary outcome success.
3. Criterion-level point attribution.
4. Cost: calls, attempts, retries, and tokens.

Matching totals do not imply matching evidence quality. Report when modalities move points between criteria.

The frozen rubric fixes the criteria and denominator. It does not make independent LLM scoring calls deterministic. Compare action-only scores first. If they differ, identify judge variance separately from evidence-stage changes.
