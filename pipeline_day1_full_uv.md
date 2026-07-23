# Day 1 Full-Trajectory Universal Verifier Pipeline

## Experiment scope

Day 1 executed Microsoft’s released Universal Verifier over the complete frozen
CUAVerifierBench Browserbase split. The run was internally named `E0` in the
execution scripts and logs.

```text
Dataset: microsoft/CUAVerifierBench
Configuration: trajectories
Split: fara7b_om2w_browserbase
Total trajectories: 106
Fara commit: 9f14b6e34094fe469a54a821e81e013a0739520d
```

This experiment measured execution coverage. It did not join human labels or
calculate benchmark accuracy.

## End-to-end pipeline

```text
Frozen CUAVerifierBench Arrow shards
        ↓
Label-safe materialization of 106 trajectories
        ↓
Validation of every trajectory
        ↓
Canonical OpenAI judge configuration
        ↓
Three-task short/medium/long preflight
        ↓
Cache and resume validation
        ↓
Fresh 10-task operational batch
        ↓
Remaining 93-task batch
        ↓
Per-trajectory process and outcome scoring
        ↓
Full-corpus validation and artifact freeze
```

## 1. Frozen dataset input

The experiment used locally frozen Arrow shards for the public split rather
than downloading or refreshing the dataset during execution.

Only the following trajectory inputs were allowed:

- task ID;
- instruction;
- initial URL;
- web-surfer action log;
- screenshots;
- final answer;
- aborted state.

Human annotations, previously stored verifier outputs, and benchmark labels
were excluded from materialization, task selection, and judge inputs.

## 2. Trajectory materialization

Each dataset row was converted to Microsoft’s expected trajectory layout:

```text
data/materialized/day2/E0_full_uv/traj/<task_id>/
├── web_surfer.log
├── screenshot0.png
├── screenshot1.png
├── ...
└── <task_id>_final_answer.json
```

The complete OM2W task definitions were written separately to:

```text
data/materialized/day2/E0_full_uv/tasks.json
```

## 3. Input validation

Before any judge request, every trajectory was checked for:

- successful `Trajectory.from_folder()` parsing;
- readable newline-delimited JSON action logs;
- at least one parsed action;
- readable PNG screenshots;
- contiguous screenshot numbering and ordering;
- valid final-answer JSON;
- a matching task ID in `tasks.json`;
- absence of forbidden human-label and stored-verifier fields.

Validation result:

```text
Dataset rows: 106
Valid inputs: 106
Invalid inputs: 0
Missing inputs: 0
Parse failures: 0
```

## 4. Reproducible execution environment

The Fara repository was pinned to:

```text
9f14b6e34094fe469a54a821e81e013a0739520d
```

The Python environment, installed packages, repository commit, sanitized judge
configuration, and fixed execution configuration were captured under:

```text
outputs/day2/E0_full_uv/environment/
```

The OpenAI API key was loaded from the ignored `.env` file into the verifier’s
child-process environment. It was never stored in endpoint JSON, logs, reports,
or score artifacts.

Azure, Azure CLI, managed identity, and vLLM were not used.

## 5. Canonical judge configuration

Two distinct OpenAI judge roles were used:

- `gpt-5.2`: main rubric-generation and multimodal judge;
- `o4-mini`: action/rubric and task-validity judge.

The official verifier command used the following fixed settings:

```bash
--eval-config endpoint_configs/openai/canonical \
--judge-model gpt-5.2 \
--o4mini-model o4-mini \
--processes 1 \
--rubric-threshold 0.8 \
--max-images-per-criterion 5 \
--mm-keypoint-score-threshold 3 \
--majority-vote-instances 1 \
--success outcome
```

No `gpt-4o` substitution or same-model fallback was permitted.

## 6. Why execution was split into 3, 10, and 93 tasks

The three runs were stages of one E0 experiment, not separate experiments.
All stages used identical data rules, judge models, prompts, thresholds, and
runtime settings. Every fresh result counted toward the final corpus.

```text
3-task preflight
    + 10-task operational batch
    + 93-task remainder
    = 106 total trajectories
```

### Stage A: three-task preflight

The preflight answered: **Does the complete pipeline work end to end?**

Exactly three valid trajectories were selected using screenshot-count order
only, without labels or previous scores:

| Length role | Task ID | Actions | Screenshots |
|---|---|---:|---:|
| Short | `Bbb--60cbbbd5` | 3 | 4 |
| Medium | `Cookpad--0632e496` | 18 | 19 |
| Long | `Arxiv--71f8de18` | 100 | 101 |

The preflight tested:

- OpenAI API authentication;
- independent `gpt-5.2` and `o4-mini` client construction;
- text and image requests;
- short, medium, and long trajectory handling;
- production of real `mmrubric_*.json` files;
- absence of Azure authentication;
- absence of `gpt-4o` substitution;
- absence of secrets in logs;
- score-file caching and resume behavior.

Result:

```text
Fresh preflight rows: 3
Status ok: 3
Fresh score files: 3
```

If any preflight task had failed terminally, the larger runs would not have
started.

### Cache and resume check

The same three tasks were invoked again without `--redo-eval`.

For each trajectory, the released verifier checked for:

```text
<trajectory>/scores/mmrubric_0.8-5-3.json
```

Result:

```text
Cached rows: 3
New model calls: 0
```

This confirmed that interrupted execution could be resumed without paying to
rescore completed trajectories.

### Stage B: fresh 10-task operational batch

The 10-task batch answered: **Is the pipeline stable under repeated real use?**

Three successful tasks were enough to validate functionality but not enough to
reveal repeated-use problems. Ten different, previously unscored trajectories
were therefore used to inspect:

- API rate-limit behavior;
- intermittent network and SDK retries;
- model output-format and schema retries;
- runtime variation across trajectories;
- accidental use of cached scores;
- continued separation of the two judge models;
- whether one worker process was sufficiently conservative;
- approximate time and call volume before launching the large remainder.

“Fresh” means none of these trajectories had an active E0 score file before
the batch began. These were real experiment results, not disposable tests.

Result:

```text
Planned tasks: 10
Unique reported tasks: 10
Status ok: 10
Terminal failures: 0
Fresh score files: 10
```

Temporary SDK and schema-format retries recovered internally without changing
prompts, models, or experiment settings.

### Stage C: remaining 93 tasks

After the preflight and fresh 10-task batch, the unscored remainder was:

```text
106 - 3 - 10 = 93
```

The 93-task stage answered: **Can the same validated configuration complete the
entire frozen split?**

No experiment setting was changed. The stage used the same:

- `gpt-5.2` multimodal judge;
- `o4-mini` action/rubric judge;
- one-process execution limit;
- rubric threshold;
- screenshot-selection limit;
- majority-vote count;
- outcome-based top-level success rule.

Result:

```text
Planned tasks: 93
Unique reported tasks: 93
Status ok: 93
Terminal infrastructure failures: 0
Input failures: 0
Fresh score files: 93
```

## 7. Per-trajectory Universal Verifier workflow

For each trajectory, Microsoft’s released verifier performed the following
logical sequence:

```text
Task definition + action trajectory
        ↓
Generate a task-specific rubric
        ↓
Score action-only evidence
        ↓
Load all trajectory screenshots
        ↓
Score screenshot relevance for each criterion
        ↓
Select up to five relevant screenshots per criterion
        ↓
Score multimodal evidence
        ↓
Produce final post-image criterion scores
        ↓
Verify task outcome
        ↓
Analyze the first point of failure
        ↓
Check ambiguity and task validity
        ↓
Write the trajectory score JSON
```

## 8. Rubric, process, and outcome fields

Each generated criterion retains:

- `criterion`;
- `description`;
- `max_points`;
- `earned_points`: action-only baseline score;
- `post_image_earned_points`: final screenshot-informed score;
- criterion justification.

The final process score is derived from the final multimodal criterion values:

```text
rubric_score = rubric_total_earned_points / rubric_total_max_points
```

Process success is:

```text
rubric_is_success = rubric_score >= 0.8
```

Outcome success is stored separately as:

```text
outcome_success
```

Because the experiment used `--success outcome`, the top-level success field
follows `outcome_success`, not `rubric_is_success`.

The action-only and final multimodal criterion fields must not be confused.
Final per-criterion reports use `post_image_earned_points`.

## 9. Retry behavior

The released OpenAI client performed transparent transport retries when a
request did not complete on its first attempt. The verifier also retried some
structured outputs when a model returned an invalid step-number format.

All such retries resolved inside the official execution. No trajectory-level
retry batch was required, and the fixed verifier configuration was never
changed.

## 10. Final artifact freeze

The three fresh stages were combined as follows:

```text
3 preflight scores
    + 10 operational-batch scores
    + 93 remainder scores
    = 106 fresh canonical scores
```

Final operational status:

```text
Total dataset rows: 106
Valid inputs: 106
Successfully scored: 106
Infrastructure failures: 0
Input failures: 0
Unresolved failures: 0
Coverage: 100%
```

Important GitHub-facing artifacts:

| Artifact | Purpose |
|---|---|
| `results/day1_full_uv/reports/full_report.jsonl` | Combined official fresh-run reports |
| `results/day1_full_uv/predictions/full_predictions.jsonl` | Consolidated per-task predictions |
| `results/day1_full_uv/predictions/process_outcome_results.jsonl` | Process and outcome fields for all 106 tasks |
| `results/day1_full_uv/scores/raw_scores/` | Complete criterion-level score files |
| `results/day1_full_uv/summary/execution_summary.md` | Operational coverage summary |
| `results/day1_full_uv/summary/learninglog.md` | Setup, failures, fixes, retries, and learnings |

The raw score audit found 106 complete score files containing 370 individual
rubric criteria. Every audited criterion contains its description, maximum
points, action-only score, and final post-image score.

## Final scope

Day 1 is complete. No later ablation or benchmark-reporting phase is part of
the active repo structure.
