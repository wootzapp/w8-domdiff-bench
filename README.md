# DOM-Based Universal Verifier Harness

This repository is a reproducible harness for running a DOM-based version of
Microsoft/FARA's Universal Verifier on browser trajectories.

The verifier implementation lives under `vendor/fara-dom-verifier/`. The rest of
this repository provides the minimum surrounding harness: DOM task data,
canonical rubrics, OpenAI endpoint configs, and run instructions.

## What This Runs

The DOM verifier evaluates a completed browser trajectory using:

- task instruction from `task_data.json` / canonical TSV;
- action history from `web_surfer.log`;
- final answer from `final_answer.json`;
- DOM evidence from each `step_XXX/` folder;
- a fixed canonical rubric from `benchmarks/rubrics/`;
- two OpenAI judge roles:
  - `gpt-5.2` as the main rubric / multimodal-style judge;
  - `o4-mini` as the action/rubric validity judge.

Unlike the original screenshot verifier, this verifier runs with
`--evidence-mode dom` and uses structured browser state instead of screenshots.

## Repository Layout

```text
ms-paper-execution/
├── README.md
├── .env.example
├── endpoint_configs/
│   └── openai/
│       └── canonical/
│           ├── openai_gpt5_2.json
│           └── openai_o4_mini.json
├── benchmarks/
│   └── rubrics/
│       ├── task3_canonical_rubric.json
│       └── task3_canonical_task_data.tsv
├── dom-data/
│   ├── task1/
│   ├── task2/
│   ├── task3/
│   └── task4/
└── vendor/
    └── fara-dom-verifier/
```

### `vendor/fara-dom-verifier/`

The DOM-compatible verifier code.

Important files:

```text
vendor/fara-dom-verifier/webeval/scripts/verify_trajectories.py
vendor/fara-dom-verifier/webeval/src/webeval/rubric_agent/mm_rubric_agent.py
vendor/fara-dom-verifier/webeval/src/webeval/rubric_agent/dom_evidence.py
vendor/fara-dom-verifier/webeval/src/webeval/rubric_agent/prompts.py
vendor/fara-dom-verifier/webeval/src/webeval/benchmarks/webtailbench/shared_data_adapter.py
```

### `dom-data/taskX/`

Input data for DOM verification.

Each task should contain:

```text
dom-data/taskX/
├── task_data.json
├── final_answer.json
├── web_surfer.log
├── trajectory.jsonl
├── manifest.json
├── actions.json
└── step_001/
    ├── before/
    │   ├── chromiumrl_dom.json
    │   └── page_state.json
    ├── after/
    │   ├── chromiumrl_dom.json
    │   └── page_state.json
    ├── dom_diff.json
    └── verifier_action.json
```

For each action in `web_surfer.log`, there must be one matching completed DOM
evidence step:

```text
N action events → N complete step_XXX DOM evidence frames
```

Terminal/end-state folders are allowed, but the verifier only requires complete
DOM evidence for actual action events.

### `benchmarks/rubrics/`

Canonical rubrics used for reproducible scoring.

Use the TSV file when running the verifier:

```text
benchmarks/rubrics/task3_canonical_task_data.tsv
```

The TSV is important because it passes the same precomputed rubric into the
verifier every time. This prevents the screenshot and DOM verifiers from
generating different rubrics for the same task.

### `endpoint_configs/openai/canonical/`

Secret-free OpenAI judge configs:

```text
openai_gpt5_2.json
openai_o4_mini.json
```

These files specify model names only. They do not contain API keys.

### `.env.example`

Template for local credentials:

```text
OPENAI_API_KEY=PASTE_KEY_HERE
```

Do not commit a real `.env` file.

## Install Dependencies

Use Python `3.10+`. The local runs were done with Python `3.12`.

Create and activate a virtual environment:

```bash
cd /path/to/ms-paper-execution
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install the DOM verifier packages without development/linter dependencies:

```bash
python -m pip install -e vendor/fara-dom-verifier --no-deps
python -m pip install -e vendor/fara-dom-verifier/webeval --no-deps
```

Install runtime dependencies:

```bash
python -m pip install \
  openai \
  playwright==1.51 \
  pillow \
  tenacity \
  pyyaml \
  jsonschema \
  browserbase \
  docker \
  huggingface_hub \
  tabulate \
  azure-identity \
  pandas \
  scipy \
  pydantic \
  nest_asyncio \
  backoff \
  joblib \
  mlflow \
  rpds-py \
  tiktoken \
  python-dotenv
```

Install Playwright's Chromium browser:

```bash
python -m playwright install chromium
```

No linting step is required to run the verifier. Do not install dev-only tools
such as `ruff` unless you plan to modify/check the code.

## Configure OpenAI API Key

Preferred method:

```bash
export OPENAI_API_KEY="PASTE_KEY_HERE"
```

Alternative local `.env` method:

```bash
cp .env.example .env
```

Then edit `.env`:

```text
OPENAI_API_KEY=PASTE_KEY_HERE
```

Never commit `.env`.

## Run a DOM Task

The verifier scans an input directory and expects each immediate child folder to
be a trajectory. Because `dom-data/` can contain multiple tasks, the safest
reproducible pattern is to create a temporary input root containing only the task
you want to run.

Prepare a one-task input root for task3:

```bash
mkdir -p /tmp/dom_verifier_input
ln -sfn "$(pwd)/dom-data/task3" /tmp/dom_verifier_input/task3
```

Run the verifier:

```bash
python vendor/fara-dom-verifier/webeval/scripts/verify_trajectories.py \
  --input /tmp/dom_verifier_input \
  --task-data benchmarks/rubrics/task3_canonical_task_data.tsv \
  --task-data-format webtailbench \
  --eval-config endpoint_configs/openai/canonical \
  --judge-model gpt-5.2 \
  --o4mini-model o4-mini \
  --processes 1 \
  --evidence-mode dom \
  --redo-eval \
  --report outputs/dom_verify/task3/report.jsonl
```

To run another task, replace both the symlink target and the task-data TSV with
the matching task files.

## Expected Output

The verifier writes:

```text
outputs/dom_verify/task3/report.jsonl
dom-data/task3/scores/mmrubric_*.json
```

If using a temporary symlink input, the score JSON is written into the linked
task folder's `scores/` directory.

The report row contains:

```text
rubric_score
rubric_total_earned_points
rubric_total_max_points
rubric_is_success
outcome_success
n_actions
evidence_format
capture_coverage
```

For DOM mode, `capture_coverage` should show:

```json
{
  "requested_evidence_mode": "dom",
  "complete_for_requested_mode": true,
  "screenshot_frames": 0,
  "dom_frames": 9
}
```

The exact `dom_frames` count depends on the task.

## Reproducibility Notes

For a clean reproducible DOM-verifier package, the required files are:

```text
vendor/fara-dom-verifier/
dom-data/taskX/
benchmarks/rubrics/
endpoint_configs/openai/canonical/
.env.example
README.md
```

Not required for reproducibility:

```text
outputs/
results/
commands/
config/
data/
data-screenshot/
repo/fara/
.venv/
__pycache__/
.pytest_cache/
```

Generated outputs should not be treated as required input. They can be shared
separately as result artifacts, but they are not needed to rerun the verifier.

## Troubleshooting

### `ModuleNotFoundError: No module named 'playwright'`

Install dependencies in the active virtual environment:

```bash
python -m pip install playwright==1.51
python -m playwright install chromium
```

### `No task definition found for taskX`

The task folder name must match a row in the canonical TSV.

Example:

```text
dom-data/task3/
benchmarks/rubrics/task3_canonical_task_data.tsv
```

The TSV must contain an `id` row equal to `task3`.

### `Trajectory.from_folder returned None`

Common causes:

- missing `web_surfer.log`;
- missing `final_answer.json`;
- more than one `*_answer.json` file in the same trajectory folder;
- malformed JSONL in `web_surfer.log`.

### `DOM evidence requested but required step-folder files are missing`

For every action step, verify these files exist:

```text
step_XXX/before/chromiumrl_dom.json
step_XXX/after/chromiumrl_dom.json
step_XXX/dom_diff.json
step_XXX/before/page_state.json
step_XXX/after/page_state.json
step_XXX/verifier_action.json
```

### API authentication error

Confirm:

```bash
echo "$OPENAI_API_KEY"
```

If using `.env`, either export it manually or run with a wrapper that loads
`.env` before invoking the verifier.
