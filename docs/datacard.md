# Dataset Card

## Contents

The full dataset contains 100 paired browser-task trajectories. Each pair
uses the same task, executed action history, and final answer. One side stores
screenshots; the other stores model-facing DOM text.

The repository includes two small pairs under `data/samples/`. The complete
set is hosted at
[WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks).

## Collection

Tasks were executed in w8-core through agent-browser. The recorder captured an
initial state and one state after every executed action. The acting model used
DOM-based observations. Screenshots were stored as evaluation artifacts and
were not sent to the acting model.

## Main files

- `task_data.json`: task text, start URL, and frozen rubric when available
- `final_answer.json`: recorded answer in the required `final_answer` text field;
  other fields are ignored and defaulted by the verifier
- `web_surfer.log`: one normalized row per executed action
- `screenshotN.png`: ordered screenshot state
- `dom_modelN.txt`: ordered DOM-model state

## Limits

The tasks reflect public web pages at their recording time. Sites can change,
block automation, require login, or return different content later. The data
can contain text that was publicly visible on those pages. Users should review
task content before redistributing subsets or using them for training.

The sample folders are examples of the file contract, not a representative
statistical subset.

