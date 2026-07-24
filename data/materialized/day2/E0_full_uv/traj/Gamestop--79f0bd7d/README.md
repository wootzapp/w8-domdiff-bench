# GameStop External Hard Drive Sample Trajectory

This is a short successful CUAVerifierBench trajectory selected from the Day 1
Universal Verifier run.

## Task

```text
Find me the cheapest external Hard Drive for an Xbox One on GameStop.
```

## Why this task was selected

- It is short: 14 original screenshots and 13 actions.
- It has clear browser state changes:
  - GameStop page/search state
  - search results for external hard drives
  - sort dropdown opened
  - products sorted by price
  - product detail page opened
  - product specs/compatibility inspected
  - final selected product visible
- It completed successfully in the Universal Verifier run.

## Result summary

```text
task_id: Gamestop--79f0bd7d
status: ok
outcome_success: true
rubric_score: 0.9
top_level_success: true
screenshots: 14
actions: 13
```

## Files

```text
web_surfer.log
Gamestop--79f0bd7d_final_answer.json
task_data.json
screenshot0.png ... screenshot13.png
scores/mmrubric_0.8-5-3.json
```

## Run command

From the repo root, after configuring the OpenAI API key, stage this single
trajectory into a one-task input directory:

```bash
mkdir -p /tmp/uv_gamestop_input
ln -s "$PWD/data/materialized/day2/E0_full_uv/traj/Gamestop--79f0bd7d" \
  /tmp/uv_gamestop_input/Gamestop--79f0bd7d
```

Then run:

```bash
repo/fara/.venv/bin/python scripts/run_with_openai_env.py repo/fara/webeval/scripts/verify_trajectories.py \
  --input /tmp/uv_gamestop_input \
  --task-data data/materialized/day2/E0_full_uv/traj/Gamestop--79f0bd7d/task_data.json \
  --task-data-format om2w \
  --eval-config endpoint_configs/openai/canonical \
  --judge-model gpt-5.2 \
  --o4mini-model o4-mini \
  --processes 1 \
  --limit 1 \
  --rubric-threshold 0.8 \
  --max-images-per-criterion 5 \
  --mm-keypoint-score-threshold 3 \
  --majority-vote-instances 1 \
  --success outcome
```
