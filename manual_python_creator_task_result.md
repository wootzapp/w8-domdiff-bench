# Custom Manual Task Result — Universal Verifier

## Task overview

This custom task was created manually in the same trajectory format expected by
Microsoft's Universal Verifier.

Task ID:

```text
ManualWikipediaPython--0001
```

Task type:

```text
Manual browser trajectory / Wikipedia factual extraction
```

Starting URL:

```text
https://en.wikipedia.org/wiki/Python_(programming_language)
```

Task instruction:

```text
Starting from https://en.wikipedia.org/wiki/Python_(programming_language), find who created Python and the year Python first appeared. Final answer should include both the creator name and the first-appearance year. Do not edit the page.
```

Expected final answer:

```text
Python was created by Guido van Rossum and first appeared in 1991.
```

## Dataset format used for the verifier run

The task was materialized in the same structure expected by the verifier. The
actual verifier input folder was:

```text
data/materialized/custom/manual_python_creator/run_inputs/single/
└── ManualWikipediaPython--0001/
    ├── web_surfer.log
    ├── screenshot0.png
    ├── screenshot1.png
    ├── screenshot2.png
    ├── screenshot3.png
    ├── screenshot4.png
    └── ManualWikipediaPython--0001_final_answer.json
```

The task definition file was:

```text
data/materialized/custom/manual_python_creator/tasks.json
```

## Parser validation

The trajectory was parsed successfully by:

```text
webeval.trajectory.Trajectory.from_folder
```

Parsed trajectory summary:

```text
events: 5
actions: 5
thoughts: 5
screenshots: 5
final-answer files: 1
```

This confirmed that the custom manual dataset was compatible with the verifier's
trajectory reader before running the judge pipeline.

## Judge configuration

The verifier used the same two judge roles as the full Universal Verifier run:

| Role | Model |
|---|---|
| Main rubric-generation and multimodal judge | `gpt-5.2` |
| Action/rubric and task-validity judge | `o4-mini` |

Verifier settings:

```bash
--judge-model gpt-5.2
--o4mini-model o4-mini
--processes 1
--rubric-threshold 0.8
--max-images-per-criterion 5
--mm-keypoint-score-threshold 3
--majority-vote-instances 1
--success outcome
```

## Verifier output

First verifier run result:

```text
status: ok
duration_sec: 69.0
n_actions: 5
rubric_score: 1.000
rubric_total_earned_points: 10.0
rubric_total_max_points: 10.0
rubric_is_success: true
outcome_success: true
success_criterion: outcome
is_ambiguous: false
is_invalid: false
```

Because the run used:

```bash
--success outcome
```

the top-level task success follows `outcome_success`. The custom task passed.

## Rubric scores

| Criterion | Score |
|---|---:|
| Use the specified Wikipedia starting page without editing | 2.0 / 2 |
| Identify Python's creator | 4.0 / 4 |
| Identify Python's first-appearance year | 4.0 / 4 |
| Total | 10.0 / 10.0 |

## LLM call and token usage

The verifier made 20 judge calls during the first run.

| Model | Calls | Logged input/request tokens |
|---|---:|---:|
| `gpt-5.2` | 17 | 76,757 |
| `o4-mini` | 3 | 14,127 |
| Total | 20 | 90,884 |

Note: this verifier path logged input/request tokens. Completion/output tokens
were not recorded in the terminal logs.

## Generated artifacts

The main verifier result is stored in the generated score JSON:

```text
data/materialized/custom/manual_python_creator/run_inputs/single/ManualWikipediaPython--0001/scores/mmrubric_0.8-5-3.json
```

The one-line run report is stored in:

```text
outputs/custom/manual_python_creator/reports/verify_report.jsonl
```

Verifier report:

```text
outputs/custom/manual_python_creator/reports/verify_report.jsonl
```

Terminal log:

```text
outputs/custom/manual_python_creator/logs/verifier_run.log
```

Generated score JSON:

```text
data/materialized/custom/manual_python_creator/run_inputs/single/ManualWikipediaPython--0001/scores/mmrubric_0.8-5-3.json
```

Custom task summary:

```text
outputs/custom/manual_python_creator/summary/result_summary.md
```

## Summary

This custom manual trajectory was successfully converted into the Universal
Verifier-compatible dataset format, parsed by the verifier trajectory reader,
and scored using the canonical two-judge setup. The verifier produced a real
`mmrubric_0.8-5-3.json` score file and marked the task as successful with a
perfect final rubric score and successful outcome verification.
