# Dataset Card

The collection contains 300 retained recordings of 100 tasks and 296 prepared trajectory pairs. Each
pair uses the same task, executed action history, and final answer. One
side stores screenshots; the other stores model-facing DOM text. The
dataset repository is
[WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks).

This checkout includes two example pairs under [data/samples/](../data/samples/).
The samples illustrate the file contract, not a representative statistical
subset. Recordings, trajectories and evaluations are grouped by run.
The collection contains 2,592 captured states per representation;
file-size means use the raw recordings, not duplicated trajectory files.

## Dataset layout

| Dataset path | Contents | How to inspect | Local guide |
| --- | --- | --- | --- |
| [`trajectories/run_1/data-ss/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/trajectories/run_1/data-ss) | 100 prepared screenshot task folders from the 100-task catalog. | Read task metadata, final answers, action logs, and ordered screenshots. | [Evaluation inputs](runbook.md#recording-and-evaluation-inputs) |
| [`trajectories/run_1/data-dom/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/trajectories/run_1/data-dom) | The corresponding 100 DOM-text task folders. | Read the common task files and ordered `dom_modelN.txt` observations. | [Evaluation protocol](evaluation-protocol.md) |
| [`tasks.jsonl`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/main/tasks.jsonl) | Catalog of task identifiers, names, categories, instructions, start URLs, stopping conditions, and constraints. | Inspect each task’s requested behavior and restrictions. | [Task recording](runbook.md#record-a-task) |
| [`trajectories/run_1/pairs.jsonl`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/main/trajectories/run_1/pairs.jsonl) | Loadable paired records with DOM text, common task files, and screenshot paths/checksums. | Select the `trajectory_pairs` configuration and `test` split. | Dataset access commands below |
| [`recordings/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/recordings) | Additional collection artifacts: manifests, decisions, executed actions, and captured states. | Follow a recording manifest through actions and states. | [Recording artifacts](recordings.md) |
| [`evaluations/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/evaluations) | Frozen rubrics, verifier results, automated audits, and saved provenance. | Match run names and task IDs before following citations. | [Technical report](technical-report.md) |

The dataset loader exposes the task catalog through the default configuration
and complete paired records through `trajectory_pairs`. Both use a `test` split.
The pair index contains the original metadata and answers as JSON strings,
the shared action log, ordered DOM text, and repository-relative screenshot
paths with checksums. Image bytes remain in the trajectory folders.

Each paired record includes `run_name`. The `trajectory_pairs` configuration
reads the per-run indices under `trajectories/run_*/pairs.jsonl`.

`task_name` is a descriptive title; `category` groups tasks by their main
operation. The categories are record lookup, reference lookup, search and
filtering, ranking, comparison, linked-page research, and data analysis.
Task IDs identify records independently of these labels. Each recording
stores the task text used for that attempt; prepared inputs and frozen
rubrics must match that text.

Install the optional dataset-reading library:

```bash
python -m pip install datasets
```

```python
from datasets import load_dataset
tasks = load_dataset("WootzappLab/browser-agent-tasks", split="test")
pairs = load_dataset("WootzappLab/browser-agent-tasks", "trajectory_pairs", split="test")
```

Maintainers can build the index from prepared local inputs without model calls:

```bash
./scripts/dataset-sync index --source-dir trajectories
```

The upload command includes each run's `pairs.jsonl` alongside the unchanged
task folders. This index is for dataset access; verifier commands continue to
read the paired task folders.

## Collection

Tasks were executed in `w8-core` through `agent-browser`. The recorder
captured an initial state and one state after every executed action. The
acting model, `gpt-5.6`, generated actions from DOM-based observations.
Screenshots were stored as evaluation artifacts and were not sent to the
acting model.

## Prepared trajectory files

Each task folder contains these shared files:

- `task_data.json`: task text and start URL, with a frozen rubric when available.
- `final_answer.json`: recorded answer and exported outcome metadata.
- `web_surfer.log`: one normalized row per executed action.

Screenshot trajectories additionally contain `screenshotN.png`; DOM
trajectories contain `dom_modelN.txt`. State 0 is the initial captured state;
subsequent states follow executed actions. Raw recordings use a different
layout, documented in [recordings.md](recordings.md).

## Limits and provenance

The evaluated tasks cover public-web research and extraction. The results
do not establish performance on authenticated workflows, transactions, or
visually intensive interaction.

The tasks reflect public web pages at recording time. Sites can change,
block automation, require login, or return different content later. The
data can contain text that was publicly visible on those pages. Users
should review task content before redistributing subsets or using them for
training.

Successful, failed, and errored runs are retained. Recorded outcomes describe
collection status; verifier scores and evidence-audit judgments are separate
artifacts. Evidence inventory uses `gpt-5.6-sol` and adjudication uses `gemini-3.1-pro-preview`; internal WootzApp review is a separate verification role. The
[technical report](technical-report.md) distinguishes website blockers,
execution errors, and source-evidence losses.

Use task identifiers, timestamps, and manifests to follow the evidence from
recordings through prepared trajectories and evaluations. Loss rates use
all 619 criteria per run on the 97-task matched panel, including criteria
without gaps omitted from the detailed findings table.

The matched comparison uses **97 tasks and 619 criteria per run**. Successful, failed and errored recordings with usable evidence are included. Recordings with no captured state remain unscored, not zero-loss audits.
