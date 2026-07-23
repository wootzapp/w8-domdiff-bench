#!/usr/bin/env bash
# Append every material execution command below, with no credentials or secrets.
# Initialized 2026-07-21.

# Step 1: clone the released verifier repository.
git clone https://github.com/microsoft/fara.git ms-paper-execution/repo/fara

# Step 1: pin the precise released Universal Verifier revision.
(cd ms-paper-execution/repo/fara && git checkout 9f14b6e34094fe469a54a821e81e013a0739520d && git rev-parse HEAD)

# Step 2: create the isolated Python 3.12 environment.
(cd ms-paper-execution/repo/fara && python3.12 -m venv .venv)

# Step 2: install the pinned repository and Day 1 dataset tooling.
(cd ms-paper-execution/repo/fara && .venv/bin/python -m pip install --upgrade pip)
(cd ms-paper-execution/repo/fara && .venv/bin/python -m pip install -e .)
(cd ms-paper-execution/repo/fara && .venv/bin/python -m pip install -e ./webeval)
(cd ms-paper-execution/repo/fara && .venv/bin/python -m pip install datasets pillow)

# Day 1 fallback: the standalone verifier does not invoke the Fara solver,
# so install webeval without its solver-only Torch/CUDA/vLLM dependency set.
(cd ms-paper-execution/repo/fara && .venv/bin/python -m pip install --no-deps -e ./webeval)

# Step 2: imported standalone-verifier smoke test (VerifierAgent is not exported
# by the pinned commit, so this verifies the actual runner imports instead).
(cd ms-paper-execution/repo/fara && .venv/bin/python -c 'from fara import FARA_ACTION_DEFINITIONS; from webeval.trajectory import Trajectory; from webeval.rubric_agent import MMRubricAgent; print("fara import: OK"); print("webeval import: OK"); print("action definitions:", sorted(FARA_ACTION_DEFINITIONS.keys()))')

# Step 3: inspect the public frozen trajectory split using a workspace-local cache.
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/inspect_dataset.py)

# Step 5: materialize the label-safe fields from the selected frozen trajectory.
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/materialize_trajectory.py --indices 1)

# Step 6: validate Fara loading, screenshot integrity, and label isolation.
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/validate_materialized.py)

# Step 7: combine the pinned repository's released Azure AD judge configs.
mkdir -p ms-paper-execution/endpoint_configs/judge_active/prod
ln -sfn /data/isha/msexecute/ms-paper-execution/repo/fara/webeval/endpoint_configs_gpt4o/dev/gpt4o_config.json ms-paper-execution/endpoint_configs/judge_active/prod/gpt4o_config.json
ln -sfn /data/isha/msexecute/ms-paper-execution/repo/fara/endpoint_configs/o4-mini/dev/o4mini-0-config.json ms-paper-execution/endpoint_configs/judge_active/prod/o4mini-0-config.json

# Step 7: make sanitized minimal text and image judge requests.
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/judge_preflight.py)

# Dataset/runtime dependencies added after the standalone-import check.
(cd ms-paper-execution/repo/fara && .venv/bin/python -m pip install datasets tiktoken)

# Step 8: official one-trajectory verifier invocation (released local configs).
(cd ms-paper-execution && repo/fara/.venv/bin/python repo/fara/webeval/scripts/verify_trajectories.py --input data/materialized/traj --task-data data/materialized/tasks.json --task-data-format om2w --eval-config endpoint_configs/judge_active/prod --judge-model gpt-4o --o4mini-model o4-mini --processes 1 --limit 1 --rubric-threshold 0.8 --max-images-per-criterion 5 --mm-keypoint-score-threshold 3 --majority-vote-instances 1 --success outcome --report outputs/day1/verify_report.jsonl)

# Step 10: write sanitized logs, environment freeze, and execution summary.
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/finalize_day1.py)

# OpenAI-only retry: `openai_gpt4o.json` deliberately has no api_key field.
# The OpenAI SDK reads OPENAI_API_KEY from the process environment.
(cd ms-paper-execution && repo/fara/.venv/bin/python repo/fara/webeval/scripts/verify_trajectories.py --input data/materialized/traj --task-data data/materialized/tasks.json --task-data-format om2w --eval-config endpoint_configs/openai/prod --judge-model gpt-4o --o4mini-model gpt-4o --processes 1 --limit 1 --rubric-threshold 0.8 --max-images-per-criterion 5 --mm-keypoint-score-threshold 3 --majority-vote-instances 1 --success outcome --report outputs/day1/verify_report_openai.jsonl)

# The ignored .env is read only by this launcher and never logged.
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/run_with_openai_env.py scripts/judge_preflight_openai.py)
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/run_with_openai_env.py repo/fara/webeval/scripts/verify_trajectories.py --input data/materialized/traj --task-data data/materialized/tasks.json --task-data-format om2w --eval-config endpoint_configs/openai/prod --judge-model gpt-4o --o4mini-model gpt-4o --processes 1 --limit 1 --rubric-threshold 0.8 --max-images-per-criterion 5 --mm-keypoint-score-threshold 3 --majority-vote-instances 1 --success outcome --report outputs/day1/verify_report_openai.jsonl)

# Captures verbose official-run output locally so the execution channel cannot truncate it.
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/run_verifier_openai.py)
(cd ms-paper-execution && repo/fara/.venv/bin/python scripts/finalize_openai_smoke_test.py)
