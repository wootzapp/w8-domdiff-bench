# Stagehand-Based Verifier

A standalone, screenshot-free verifier for Stagehand browser trajectories. It
preserves the major evaluation stages of Microsoft’s Universal Verifier while
using Stagehand ARIA trees, page state, actions, and bounded tool results as
evidence.

This repository does **not** import from or modify `fara` or
`fara-dom-verifier`. The Microsoft implementation is a pinned, read-only
behavioral reference recorded in `UPSTREAM_VERIFIER.lock.json`.

## What the verifier does

For each task it:

1. validates all files and action/state alignment before creating an API client;
2. loads a frozen rubric, or generates one with GPT-5.2;
3. derives task-and-criterion concepts at inference time;
4. ranks Stagehand transition frames and selects only criterion-relevant evidence;
5. runs explicit deterministic rubric checks locally;
6. uses o4-mini for unresolved action/rubric and task-validity judgments;
7. uses GPT-5.2 for unresolved semantic criteria, side effects, outcome, and failure analysis;
8. calculates process score, final outcome, and first failure classification;
9. stores evidence links, call counts, and token usage in a Stagehand-specific result.

No task-family keyword list is built into retrieval. A criterion judge never
receives the complete raw trajectory. Cross-step side-effect analysis receives
only a bounded global transition summary.

## Installation

Python 3.11 or newer is required.

```bash
cd stagehand-based-verifier
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Set the key in the shell; do not put it in a dataset or committed config:

```bash
export OPENAI_API_KEY="PASTE_KEY_HERE"
cp configs/openai.example.json configs/openai.json
```

Only OpenAI API-key authentication is used. Azure CLI, managed identity, and
Azure endpoints are not supported.

## Expected source dataset

```text
<stagehand-task>/
├── task.json
├── final_answer.json
├── step_001/
│   ├── action.json
│   ├── tool_result.json
│   ├── aria.txt
│   └── page_state.json
├── ...
└── step_N+1/
    ├── aria.txt
    └── page_state.json
```

There must be `N` action-bearing steps and exactly one final no-action state,
giving `N+1` captured Stagehand states. For current recordings, action 1 must
be `goto` from declared `about:blank`; the loader labels its empty before-state
as synthetic.

Required fields include:

- `task.json`: `task_id`, `task`, `start_url`;
- `final_answer.json`: `message` or `output`;
- `action.json`: `action`, `arguments`;
- `tool_result.json`: `ok`, `error`, and bounded `result` fields;
- `aria.txt`: Stagehand’s semantic/accessibility tree;
- `page_state.json`: URL, title, readiness, scroll, and viewport.

Screenshots, evidence images, agent/model payloads, Stagehand logs, and raw
trajectory JSONL are never loaded as criterion evidence. `result.json.success`
never determines the verifier outcome.

## Example input

`task_data.json` can provide a frozen rubric:

```json
{
  "id": "task01",
  "question": "Find the economy-class baggage allowance on Qatar Airways.",
  "init_url": "about:blank",
  "precomputed_rubric": {
    "items": [
      {
        "id": 0,
        "criterion": "Report the applicable economy baggage weights from Qatar Airways.",
        "description": "The answer must be grounded in official semantic page evidence.",
        "points": 5,
        "depends_on": []
      }
    ]
  }
}
```

Optional exact deterministic checks use a deliberately small DSL:

```json
{"deterministic_check": {"final_url_contains": "/baggage/allowance"}}
```

Supported operators are `final_url_equals`, `final_url_contains`,
`final_domain_equals`, `terminal_contains_all`, `terminal_contains_any`,
`terminal_not_contains`, `action_present`, and `all_tools_ok`. Ordinary
semantic rubric prose is never converted into a guessed deterministic check.

## Prepare a minimal dataset

```bash
stagehand-prepare \
  --input /path/to/raw-stagehand-task \
  --output /path/to/prepared/task01
```

This writes canonical task/answer/action files, the required Stagehand step
evidence, and `stagehand_manifest.json`. It does not copy screenshots, model
traffic, private reasoning, `cdp_url`, or recorder success labels.

## Preflight without API calls

```bash
stagehand-verify \
  --input /path/to/prepared/task01 \
  --preflight-only
```

Preflight completes before endpoint configuration is read. It checks JSON and
UTF-8 validity, contiguous ordinals, action arguments, the one-to-one
action/after-state relation, terminal state, frozen rubric shape, and optional
`web_surfer.log` consistency.

## Run the verifier

```bash
stagehand-verify \
  --input /path/to/prepared/task01 \
  --task-data /path/to/prepared/task01/task_data.json \
  --task-data-format json \
  --eval-config configs/openai.json \
  --judge-model gpt-5.2 \
  --o4mini-model o4-mini \
  --processes 1
```

Use `--redo-eval` to bypass an existing Stagehand cache. A directory containing
multiple task folders is also accepted. Canonical runs intentionally use one
process so output ordering and accounting remain reproducible.

## Output schema

Each task receives:

```text
<task>/scores/mmrubric_<settings>-stagehand-<cache-id>.json
```

The run also writes `verify_report_stagehand.jsonl`. A score contains:

- top-level success score and success criterion;
- evidence, adapter, verifier, and prompt versions;
- frozen rubric SHA-256 and Stagehand-only cache identity;
- judge model roles;
- action/state counts, alignment, coverage, and synthetic-state status;
- per-criterion status, points, explanation, retrieval score, and links to
  step, action ID, before/after URL, Stagehand node IDs, and source artifacts;
- process score and side-effect penalty;
- outcome success, reasoning, unsupported claims, and evidence steps;
- task validity and first-failure taxonomy;
- exact successful LLM call and token counts by role and in total.

## Evidence and scoring pipeline

```text
safe Stagehand files
  -> offline validation
  -> normalized ARIA/page states
  -> N aligned action transitions + terminal state
  -> conservative semantic changes
  -> frozen/generated rubric
  -> criterion-by-frame local relevance ranking
  -> top bounded evidence frames only
  -> deterministic check OR action + semantic judging
  -> dependency/condition handling
  -> process score + compact global side-effect check
  -> terminal outcome check
  -> task validity and first-failure classification
  -> score, evidence links, calls, tokens, and cache identity
```

See [docs/stagehand_based_verifier_pipeline.md](docs/stagehand_based_verifier_pipeline.md)
for implementation details.

## Current limitations

- ARIA is semantic browser evidence, not raw HTML DOM and not pixels.
- It cannot establish color, styling, exact layout, overlap, occlusion, image
  contents without alt text, or canvas/chart/map/video pixels.
- ARIA inclusion does not prove viewport visibility because node geometry is absent.
- Cross-origin or inaccessible content omitted from the ARIA tree remains unknown.
- The first current transition uses a declared synthetic `about:blank` state;
  future recorders should capture an explicit initial state.
- Semantic differences use conservative matching because raw Stagehand node
  references may change after navigation.
- LLM judgments may vary. Frozen rubrics, cache identities, majority settings,
  and exact usage records make controlled comparisons possible.
- Quality claims require evaluation on at least three heterogeneous tasks; a
  passing unit test or single task is not a benchmark result.

## Development checks

```bash
PYTHONPATH=src pytest -q
python -m compileall -q src
```

To audit protected files in a local Microsoft checkout:

```bash
UPSTREAM_VERIFIER_SOURCE=/path/to/fara PYTHONPATH=src pytest -q
```
