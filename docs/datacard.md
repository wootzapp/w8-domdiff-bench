# Dataset Card

The published dataset contains 100 paired browser-task trajectories. Each
pair uses the same task, executed action history, and final answer. One
side stores screenshots; the other stores model-facing DOM text. The
complete set is hosted at
[WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks).

This checkout includes two example pairs under [data/samples/](../data/samples/).
The comparison command downloads prepared pairs into the ignored `dataset/`
directory. Local samples illustrate the file contract and are not a
representative statistical subset. Saved evaluations and raw recordings are
additional artifacts in the hosted dataset.

## Published dataset layout

| Dataset path | Contents | How to inspect | Local guide |
| --- | --- | --- | --- |
| [`trajectories/data-ss/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/trajectories/data-ss) | 100 screenshot task folders, `task_01` through `task_100`. | Read task metadata, final answers, action logs, and ordered screenshots. | [Evaluation inputs](runbook.md#recording-and-evaluation-inputs) |
| [`trajectories/data-dom/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/trajectories/data-dom) | The corresponding 100 DOM-text task folders. | Read the common task files and ordered `dom_modelN.txt` observations. | [Evaluation protocol](evaluation-protocol.md) |
| [`tasks.jsonl`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/blob/main/tasks.jsonl) | Catalog of task identifiers, categories, instructions, start URLs, stopping conditions, and constraints. | Inspect each task’s requested behavior and restrictions. | [Task recording](runbook.md#record-a-task) |
| [`recordings/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/recordings) | Additional collection artifacts: manifests, decisions, executed actions, and captured states. | Follow a recording manifest through actions and states. | [Recording artifacts](recordings.md) |
| [`evaluation/`](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/main/evaluation) | Frozen rubrics, verifier results, automated audits, and saved provenance. | Match task IDs and selected run timestamps before following citations. | [Technical report](technical-report.md) |

The hosted dataset loader exposes `tasks.jsonl` as the `train` split.
Trajectory artifacts are stored separately in that repository. The split
name describes the loader configuration, not an independent assessment of
the trajectories’ suitability for training.

## Collection

Tasks were executed in `w8-core` through `agent-browser`. The recorder
captured an initial state and one state after every executed action. The
acting model used DOM-based observations. Screenshots were stored as
evaluation artifacts and were not sent to the acting model.

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

The tasks reflect public web pages at recording time. Sites can change,
block automation, require login, or return different content later. The
data can contain text that was publicly visible on those pages. Users
should review task content before redistributing subsets or using them for
training.

Successful, failed, and errored runs are retained. Recorded outcomes describe
collection status; verifier scores and automated evidence-audit judgments
are separate artifacts. Neither constitutes manually verified answer
correctness. The [technical report](technical-report.md) distinguishes
website blockers, execution errors, and source-evidence losses.

Recordings, prepared trajectories, and evaluations can refer to different
run versions. Check task identifiers, timestamps, and saved provenance
before treating them as corresponding records. Current loss rates use all
642 audited criteria across 100 latest selected evaluation runs, not only
the 154 affected criteria shown in the report’s detailed findings table.
