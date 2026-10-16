# `w8-domdiff-bench`: Browser Evidence Infrastructure for Agent Development

`w8-domdiff-bench` records browser-agent tasks in w8-core, a new kind of
browser engine, and evaluates the recorded work through screenshot and
DOM-model evidence. The project focuses on a practical limitation of browser
evaluation: a verifier cannot use evidence that the recorder failed to keep.

The 100-task evaluation contains 639 audited rubric criteria. Screenshot
records were missing required evidence for 26 criteria, while DOM-model
records were missing evidence for 2. The result measures evidence
availability in this dataset; it does not claim that DOM evidence replaces
screenshots for every visual task.

## Start here

Use the [runbook](docs/runbook.md) for all setup and execution commands. It is
the only operational guide in this repository.

| Goal | Follow in the runbook | Result |
| --- | --- | --- |
| Record a browser task | Get the repository, requirements, browser build, Python setup, browser runtime, then Record a task | A raw run under `recordings/` |
| Score an existing benchmark task | Get the repository, requirements, Python setup, then Score a prepared task | Paired verifier output under `evaluation/` |

These are separate workflows. The scoring command consumes prepared
screenshot/DOM pairs downloaded from the hosted dataset. It does not accept a
raw `recordings/` directory. This repository does not currently provide a
public command for converting a new recording into that paired dataset
format.

## Project overview

The repository contains three connected parts:

1. **w8-core and the task recorder** run browser tasks and preserve each page
   state, action, screenshot, and model-facing DOM observation.
2. **The two evidence verifiers** score the same task with either screenshots
   or ordered DOM-model states.
3. **The comparison harness** freezes one rubric, applies the same scoring
   controls to both evidence modes, and audits which required facts each mode
   retained.

The acting model uses DOM-based observations. Screenshots are stored for the
screenshot verifier and human inspection, but they are not attached to the
acting model's prompt.

## Why structured browser evidence is used

A screenshot preserves the rendered viewport, but it can miss content below
the fold and can make exact values, URLs, table entries, or control state hard
to recover. Raw DOM output contains more detail, but it is too large and noisy
for routine model input.

The browser therefore produces a compact DOM model. It groups the captured
state into readable sections for page content, tables, media descriptions,
actions, and scroll regions. Executable action references remain separate
from read-only DOM identifiers.

The approach developed through several stages:

| Stage | Problem | Result |
| --- | --- | --- |
| Detailed DOM capture | Screenshots did not preserve enough structured page state. | The recorder stored text, controls, attributes, relationships, and layout information. |
| DOM difference | Full states did not directly show what changed after an action. | Before and after states could be compared for action-relative changes. |
| Compact DOM model | Repeated snapshots and differences were too large for regular model input. | Each browser state became a compact, independently readable representation. |
| Browser-native model construction | Re-reading the page locally could diverge from the captured browser state. | ChromiumRL constructs the model from the same structured snapshot returned by the browser. |
| Evidence-preservation work | Nested text, labels, notation, control state, and viewport boundaries could be lost. | Generic capture and model-selection rules retain more verifier-relevant evidence. |

The detailed engineering history, measurements, and limitations are in the
[technical report](docs/technical-report.md).

## Recording flow

One task follows this sequence:

```text
task and constraints
        |
        v
w8-core opens the task page
        |
        v
ChromiumRL captures the structured viewport
        |
        +--> dom.json --> dom_full.txt
        |
        +--> getModelDOM --> dom_model.json --> dom_model.txt
        |
        v
model receives DOM evidence, task memory, controls, and recent outcomes
        |
        v
validated action executes through agent-browser
        |
        v
the resulting page becomes the next numbered state
```

An execution with `N` actions records `N+1` states: the initial state and one
state after each action. Screenshots and DOM files describe the same sequence
of browser states.

## Evaluation flow

The paired evaluation keeps the task, action history, final answer, rubric,
models, and scoring settings fixed. Only the evidence source changes.

```text
paired task records
        |
        v
generate or import one rubric
        |
        v
validate and freeze the rubric
        |
        +--> screenshot evidence selection and scoring
        |
        +--> DOM-model evidence selection and scoring
        |
        v
normalize results and audit missing source evidence
```

The verifier validates task identity, ordered states, action alignment,
rubric identity, package receipts, and shared scoring controls before paid
model calls. The two verifier implementations stay separate so that shared
helpers cannot silently make one evidence path depend on the other.

## Evaluation result

| Evidence source | Criteria with missing evidence | Rate |
| --- | ---: | ---: |
| Screenshot | 26 of 639 | 4.07% |
| DOM model | 2 of 639 | 0.31% |

The audit counts a criterion when a required fact is absent from one recorded
representation but present in the other. Facts absent from both sources are
not detected by this measurement. The result therefore measures paired
source-evidence loss, not overall agent accuracy.

Machine-readable counts are stored in
[`results/summary.json`](results/summary.json). The complete method is in the
[evaluation protocol](docs/evaluation-protocol.md).

## Repository map

- `w8bench/task_recorder/` contains task loading, browser capture, action
  execution, model prompts, renderers, and trajectory export.
- `w8bench/dom_model/` contains the DOM-model evidence verifier.
- `w8bench/screenshot_verifier/` contains the screenshot evidence verifier.
- `w8bench/verifier/` contains rubric freezing, paired validation, execution,
  result normalization, and evidence-loss auditing.
- `protocol/` contains the pinned ChromiumRL protocol definition.
- `config/` contains endpoint configuration templates.
- `manifests/` pins the two verifier source packages by file count and hash.
- `data/samples/` contains two small paired trajectory examples.
- `results/` contains the published aggregate result.
- `tests/` contains offline tests and opt-in browser protocol checks.
- `docs/runbook.md` is the operational guide for setup, recording, and
  scoring.
- The other files in `docs/` explain the method, dataset, and engineering
  decisions; they are not required to run the commands.

## Quick commands

Clone the repository and enter it:

```bash
git clone https://github.com/wootzapp/w8-domdiff-bench.git
cd w8-domdiff-bench
```

After building `w8-core:domdiff-bench` as described in the
[runbook](docs/runbook.md#browser-build), create the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
```

Create a runtime configuration with unused local ports:

```bash
python -m w8bench.task_recorder.browser_runtime configure
```

Add `OPENAI_API_KEY` and `OPENAI_MODEL` to `.env`, then start w8-core:

```bash
docker compose --env-file .env up -d --wait w8-core
python -m w8bench.task_recorder.browser_runtime status
```

Record a catalog task:

```bash
./scripts/run-task task8 --output-dir recordings --no-human-intervention
```

To download and validate one prepared task without making paid model calls:

```bash
./scripts/run-comparison --task task_01
```

Add `--execute` only when the configured calls should run and write an
evaluation result. The command downloads the same prepared pair if needed:

```bash
./scripts/run-comparison --task task_01 --execute
```

The full task set is hosted at
[WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks).
Raw recorder output must first be prepared into the paired dataset contract;
that conversion is not implemented as a public command here.

## Tests

Run the complete offline suite:

```bash
python -m pytest
```

Browser-dependent tests skip unless `EVIDENCE_TEST_CDP_URL` points to an
isolated running browser. They must not be run against a browser being used
for task recording.

## Documentation

For commands, read only the [runbook](docs/runbook.md). The remaining
documents are references:

- [Evaluation protocol](docs/evaluation-protocol.md): rubric and scoring
  controls.
- [Dataset card](docs/datacard.md): task data and collection scope.
- [Technical report](docs/technical-report.md): design history and findings.
- [Results](results/README.md): published aggregate result.

## Scope and limitations

DOM evidence does not independently establish every visual property. Color,
spacing, geometry, clipping, z-order, image content, canvas state, and video
may require screenshots or additional instrumentation. Screenshots can omit
off-viewport content or render exact text and notation ambiguously.

Capture is sequential rather than atomic, so rapidly changing pages can
change between evidence operations. The evaluation covers the recorded task
set and does not establish behavior for every website, authenticated flow,
or visual interaction.

The two evidence modes are therefore treated as controlled comparison paths,
not interchangeable descriptions of a webpage.
